# transactions.py

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    get_user_by_id,
    get_transactions_by_user,
    get_user_credits,
    update_user_credits,
    update_transaction,
    create_transaction
)
from config import Config
import razorpay
import logging
from datetime import datetime
import hmac
import hashlib
import uuid
from pymongo import MongoClient
from bson import ObjectId
import json
from flask_cors import CORS

transactions_bp = Blueprint('transactions', __name__)

# Apply CORS to the entire blueprint
CORS(transactions_bp, resources={r"/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

# Initialize MongoDB client
mongo_client = MongoClient(Config.MONGO_URI)
db = mongo_client['zyke_data']
transactions_collection = db['transactions']

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(Config.RAZORPAY_KEY, Config.RAZORPAY_SECRET)
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------
# Helper Functions
# ------------------------------

def calculate_amount_usd(original_amount, currency):
    """
    Convert the original amount to USD based on currency.
    For simplicity, using static conversion rates. In production, use real-time rates.
    
    Args:
        original_amount (float): Amount in original currency.
        currency (str): Currency code ('USD' or 'INR').
    
    Returns:
        float: Amount in USD.
    """
    conversion_rates = {
        'USD': 1.0,
        'INR': 0.012  # Example conversion rate; replace with actual rates or use an API
    }
    rate = conversion_rates.get(currency.upper(), 1.0)
    return original_amount * rate

def get_payment_status(payment):
    """
    Determine the payment status based on Razorpay payment object.
    
    Args:
        payment (dict): Razorpay payment object.
    
    Returns:
        str: Payment status ('captured', 'failed', etc.)
    """
    return payment.get('status', 'unknown')

def generate_receipt():
    """
    Generates a unique receipt identifier within 40 characters.
    
    Returns:
        str: Unique receipt string.
    """
    # Using UUID4 and taking first 36 characters to ensure uniqueness and compliance
    return f"receipt_{uuid.uuid4().hex[:36]}"

def verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verifies Razorpay payment signature.
    
    Args:
        razorpay_order_id (str): The order ID.
        razorpay_payment_id (str): The payment ID.
        razorpay_signature (str): The signature received from Razorpay.
    
    Returns:
        bool: True if signature is valid, False otherwise.
    """
    message = f"{razorpay_order_id}|{razorpay_payment_id}"
    secret = Config.RAZORPAY_SECRET.encode()
    generated_signature = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(generated_signature, razorpay_signature)

def verify_webhook_signature(payload, signature):
    """
    Verifies the Razorpay webhook signature.
    
    Args:
        payload (str): The raw request payload.
        signature (str): The 'X-Razorpay-Signature' header from the request.
    
    Returns:
        bool: True if signature is valid, False otherwise.
    """
    secret = Config.RAZORPAY_WEBHOOK_SECRET.encode()  # Use a separate secret for webhooks
    computed_signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_signature, signature)

def is_transaction_already_processed(transaction):
    """
    Checks if the transaction has already been processed.
    
    Args:
        transaction (dict): The transaction document from MongoDB.
    
    Returns:
        bool: True if processed, False otherwise.
    """
    processed_statuses = ['captured', 'failed']
    return transaction.get('status') in processed_statuses

# ------------------------------
# Routes
# ------------------------------

@transactions_bp.route('/credits', methods=['GET'])
@jwt_required()
def get_user_credits_route():
    """
    Fetch the current user's credits.
    
    Returns:
        JSON response containing the user's credits.
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    
    if not user:
        logger.error(f"User not found: {user_id}")
        return jsonify({"msg": "User not found"}), 404
    
    credits = user.get('credits', 0.0)
    
    return jsonify({"credits": credits}), 200


@transactions_bp.route('/add', methods=['POST'])
@jwt_required()
def add_credits():
    """
    Create a Razorpay order for adding credits.
    
    Expects JSON payload:
    {
        "amount": float,  # Amount in USD or INR
        "currency": "USD" | "INR"  # Currency code
    }
    
    Returns:
        JSON response with Razorpay order details.
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    
    if not user:
        return jsonify({"msg": "User not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON payload"}), 400
    
    amount = data.get('amount')
    currency = data.get('currency', 'USD').upper()
    
    if not amount or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"msg": "Invalid amount"}), 400
    
    if currency not in ['USD', 'INR']:
        return jsonify({"msg": "Unsupported currency. Supported: USD, INR"}), 400
    
    # Convert amount to the smallest currency unit (e.g., paise for INR, cents for USD)
    amount_in_currency = int(amount * 100)
    
    # Generate a unique receipt ensuring it doesn't exceed 40 characters
    receipt = generate_receipt()

    try:
        # Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            'amount': amount_in_currency,
            'currency': currency,
            'payment_capture': '1',  # Automatic capture
            'receipt': receipt,
            'notes': {
                'user_id': user_id  # Storing user_id as string
            }
        })
        
        # Create a transaction record
        transaction = {
            "user_id": user_id,  # Ensure this is a string
            "transaction_id": razorpay_order['id'],
            "amount": amount,
            "original_amount": amount_in_currency,
            "currency": currency,
            "status": "created",
            "invoice_link": f"https://dashboard.razorpay.com/payments/{razorpay_order['id']}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        create_transaction(transaction)
        
        return jsonify({
            "order_id": razorpay_order['id'],
            "amount": amount_in_currency,
            "currency": currency,
            "receipt": razorpay_order['receipt'],
            "user_id": user_id
        }), 200

    except razorpay.errors.BadRequestError as e:
        logger.error(f"Razorpay BadRequestError: {e}")
        return jsonify({"msg": "Invalid request to Razorpay", "error": str(e)}), 400
    except razorpay.errors.RazorpayError as e:
        logger.error(f"Razorpay Error: {e}")
        return jsonify({"msg": "Razorpay processing error", "error": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected Error: {str(e)}")
        return jsonify({"msg": "An unexpected error occurred", "error": str(e)}), 500


@transactions_bp.route('/history', methods=['GET'])
@jwt_required()
def get_user_transactions():
    """
    Fetch transaction history from MongoDB for the authenticated user.
    
    Returns:
        JSON response with a list of transactions.
    """
    user_id = get_jwt_identity()
    # print(user_id)
    # limit = request.args.get('limit', default=10, type=int)
    # skip = request.args.get('skip', default=0, type=int)

    try:
        # transactions = get_transactions_by_user(user_id, limit=limit, skip=skip)
        transactions = get_transactions_by_user(user_id)
        # print(transactions)
        # Serialize datetime objects to ISO format
        serialized_transactions = []
        for tx in transactions:
            tx_copy = tx.copy()
            tx_copy['created_at'] = tx_copy['created_at'].isoformat()
            tx_copy['updated_at'] = tx_copy['updated_at'].isoformat()
            serialized_transactions.append(tx_copy)

        return jsonify({"transactions": serialized_transactions}), 200

    except Exception as e:
        logger.error(f"Error fetching user transactions: {str(e)}")
        return jsonify({"msg": "Failed to fetch transactions", "error": str(e)}), 500


@transactions_bp.route('/history/<user_id>', methods=['GET'])
@jwt_required()
def get_user_transactions_admin(user_id):
    """
    Get all transaction history for a specific user.
    Only accessible by admin users.
    
    Args:
        user_id (str): The ID of the user whose transactions are to be fetched.
    
    Returns:
        JSON response with a list of transactions.
    """
    current_user_id = get_jwt_identity()
    current_user = get_user_by_id(current_user_id)
    
    if not current_user:
        logger.error(f"Authenticated user not found: {current_user_id}")
        return jsonify({"msg": "Authenticated user not found"}), 404
    
    if not current_user.get('is_admin', False):
        logger.warning(f"User {current_user_id} attempted to access admin route without permissions.")
        return jsonify({"msg": "Admin privileges required"}), 403
    
    target_user = get_user_by_id(user_id)
    if not target_user:
        logger.error(f"Target user not found: {user_id}")
        return jsonify({"msg": "Target user not found"}), 404
    
    try:
        transactions = get_transactions_by_user(user_id)
        # Serialize datetime objects to ISO format
        serialized_transactions = []
        for tx in transactions:
            tx_copy = tx.copy()
            tx_copy['created_at'] = tx_copy['created_at'].isoformat()
            tx_copy['updated_at'] = tx_copy['updated_at'].isoformat()
            serialized_transactions.append(tx_copy)
        
        logger.info(f"Admin {current_user_id} fetched all transactions for user_id: {user_id}")
        
        return jsonify({"transactions": serialized_transactions}), 200
    
    except Exception as e:
        logger.error(f"Error fetching admin transactions: {str(e)}")
        return jsonify({"msg": "Failed to fetch admin transactions", "error": str(e)}), 500


@transactions_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user_data():
    """
    Fetch the current user's data.
    
    Returns:
        JSON response containing the user's data.
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)

    if not user:
        logger.error(f"User not found: {user_id}")
        return jsonify({"msg": "User not found"}), 404

    user_data = {
        "email": user.get('email'),
        "first_name": user.get('first_name'),
        "last_name": user.get('last_name'),
        "contact": user.get('contact'),
        "is_admin": user.get('is_admin', False)
    }

    return jsonify(user_data), 200


@transactions_bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Handle incoming Razorpay webhook events.
    
    Steps:
    1. Verify the webhook signature.
    2. Parse the event.
    3. Update the corresponding transaction in MongoDB.
    
    Returns:
        A 200 OK response if processed successfully, or appropriate error codes.
    """
    payload = request.get_data(as_text=True)
    signature = request.headers.get('X-Razorpay-Signature')
    logger.debug("Received webhook payload: %s", payload)
    logger.debug("Received webhook signature: %s", signature)

    if not signature:
        logger.warning("Missing Razorpay signature in webhook.")
        return jsonify({"msg": "Missing signature"}), 400

    # Verify the webhook signature
    if not verify_webhook_signature(payload, signature):
        logger.warning("Invalid webhook signature.")
        return jsonify({"msg": "Invalid signature"}), 400

    try:
        event = json.loads(payload)
        event_type = event.get('event')
        data = event.get('payload', {}).get('payment', {})
        
        logger.info(f"Received Razorpay webhook event: {event_type}")

        if event_type == 'payment.captured':
            razorpay_payment_id = data.get('entity', {}).get('id')
            razorpay_order_id = data.get('entity', {}).get('order_id')
            payment_status = data.get('entity', {}).get('status')

            if not all([razorpay_payment_id, razorpay_order_id, payment_status]):
                logger.error("Incomplete payment data in webhook.")
                return jsonify({"msg": "Incomplete payment data"}), 400

            # Fetch the payment details from Razorpay to ensure data integrity
            payment = razorpay_client.payment.fetch(razorpay_payment_id)
            payment_status = get_payment_status(payment)

            # Fetch the corresponding transaction from the database
            transaction = transactions_collection.find_one({"transaction_id": razorpay_order_id})

            if not transaction:
                logger.error(f"Transaction not found for order_id: {razorpay_order_id}")
                return jsonify({"msg": "Transaction not found"}), 404

            if is_transaction_already_processed(transaction):
                logger.info(f"Transaction already processed: {razorpay_order_id}")
                return jsonify({"msg": "Transaction already processed"}), 200

            # Update the transaction status and invoice link
            invoice_link = f"https://dashboard.razorpay.com/payments/{razorpay_payment_id}"
            transaction_update = {
                "status": payment_status,
                "invoice_link": invoice_link,
                "updated_at": datetime.utcnow()
            }

            update_success = update_transaction(str(transaction['_id']), transaction_update)

            if not update_success:
                logger.error(f"Failed to update transaction record for transaction_id: {transaction['_id']}")
                return jsonify({"msg": "Failed to update transaction"}), 500

            # If payment is captured, update user credits
            if payment_status == 'captured':
                user_id = transaction.get('user_id')
                amount = transaction.get('amount')
                currency = transaction.get('currency')

                # Convert amount to USD if necessary
                if currency == 'USD':
                    amount_usd = amount
                elif currency == 'INR':
                    amount_usd = calculate_amount_usd(amount, 'INR')
                else:
                    logger.error(f"Unsupported currency in transaction: {currency}")
                    return jsonify({"msg": "Unsupported currency"}), 400

                # Update user credits
                current_credits = get_user_credits(user_id)
                if current_credits is None:
                    logger.error("User credits not found for user_id: %s", user_id)
                    return jsonify({"msg": "User credits not found"}), 404
                
                new_credits = current_credits + amount_usd
                update_success = update_user_credits(user_id, new_credits)

                if not update_success:
                    logger.error("Failed to update user credits for user_id: %s", user_id)
                    return jsonify({"msg": "Failed to update credits"}), 500

                logger.info(f"User {user_id} credits updated by {amount_usd}. New balance: {new_credits}")

            return jsonify({"msg": "Webhook processed successfully"}), 200

        else:
            logger.info(f"Unhandled event type: {event_type}")
            return jsonify({"msg": "Event type not handled"}), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"msg": "Error processing webhook"}), 500
