# webhooks.py

from flask import Blueprint, request, jsonify
from models import create_transaction, get_user_by_razorpay_customer_id
from config import Config
import hmac
import hashlib
import razorpay
from datetime import datetime
from bson.objectid import ObjectId

webhooks_bp = Blueprint('webhooks', __name__)

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(Config.RAZORPAY_KEY, Config.RAZORPAY_SECRET)
)

@webhooks_bp.route('/razorpay', methods=['POST'])
def razorpay_webhook():
    payload = request.data
    signature = request.headers.get('X-Razorpay-Signature')
    secret = Config.RAZORPAY_WEBHOOK_SECRET.encode()

    computed_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_signature, signature):
        return jsonify({"msg": "Invalid signature"}), 400

    event = request.json.get('event')
    data = request.json.get('payload', {}).get('payment', {})

    if event in ['payment.captured', 'payment.authorized']:
        # Extract necessary data
        payment_entity = data.get('entity', {})
        transaction_data = {
            "transaction_id": payment_entity.get('id'),
            "currency": payment_entity.get('currency'),
            "amount": payment_entity.get('amount') / 100,  # Assuming amount is in paise or cents
            "original_amount": payment_entity.get('amount'),
            "status": payment_entity.get('status'),
            "invoice_link": f"https://dashboard.razorpay.com/payments/{payment_entity.get('id')}",
            "order_id": payment_entity.get('order_id'),
            "payment_id": payment_entity.get('id'),
            "signature_verified": True,
            "created_at": datetime.utcnow()
        }

        # Fetch order to get user info, assuming order notes include user_id
        order_id = payment_entity.get('order_id')
        if not order_id:
            return jsonify({"msg": "Order ID not found in payment data"}), 400

        try:
            order = razorpay_client.order.fetch(order_id)
            notes = order.get('notes', {})
            user_id = notes.get('user_id')

            if not user_id:
                return jsonify({"msg": "User ID not found in order notes"}), 400

            transaction_data['user_id'] = ObjectId(user_id)

            # Create transaction
            create_transaction(transaction_data)

        except Exception as e:
            print("Error processing webhook:", e)
            return jsonify({"msg": "Error processing webhook"}), 500

    return jsonify({"msg": "Webhook received"}), 200
