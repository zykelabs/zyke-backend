from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import create_transaction, get_transactions_by_user, get_user_by_id
from bson.objectid import ObjectId
from datetime import datetime

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/add', methods=['POST'])
@jwt_required()
def add_transaction():
    """
    Endpoint to add a new transaction.
    Expects transaction data in the request body.
    """
    user_id = get_jwt_identity()
    data = request.get_json()

    # Validate required fields
    required_fields = ['transaction_id', 'currency', 'amount', 'original_amount', 'status', 'order_id', 'payment_id', 'signature_verified']
    for field in required_fields:
        if field not in data:
            return jsonify({"msg": f"Missing field: {field}"}), 400

    # Validate signature_verified is boolean
    if not isinstance(data.get('signature_verified'), bool):
        return jsonify({"msg": "Invalid type for signature_verified"}), 400

    # Fetch user
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404

    # Prepare transaction data
    transaction_data = {
        "transaction_id": data['transaction_id'],
        "user_id": ObjectId(user_id),
        "currency": data['currency'],
        "amount": data['amount'],
        "original_amount": data['original_amount'],
        "status": data['status'],
        "invoice_link": data.get('invoice_link', ''),
        "order_id": data['order_id'],
        "payment_id": data['payment_id'],
        "signature_verified": data['signature_verified'],
        "created_at": datetime.utcnow()
    }

    transaction_id = create_transaction(transaction_data)
    return jsonify({"msg": "Transaction added successfully", "transaction_id": transaction_id}), 201

@transactions_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user_transactions_route():
    """
    Endpoint to retrieve transactions for the authenticated user.
    """
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 50, type=int)

    transactions = get_transactions_by_user(user_id, limit)
    
    # Convert ObjectId to string for JSON serialization
    transactions_serialized = []
    for tx in transactions:
        tx_serialized = {
            "id": str(tx['_id']),
            "transaction_id": tx['transaction_id'],
            "currency": tx['currency'],
            "amount": tx['amount'],
            "original_amount": tx['original_amount'],
            "status": tx['status'],
            "invoice_link": tx.get('invoice_link', ''),
            "order_id": tx['order_id'],
            "payment_id": tx['payment_id'],
            "signature_verified": tx['signature_verified'],
            "created_at": tx['created_at'].timestamp()
        }
        transactions_serialized.append(tx_serialized)

    return jsonify({"transactions": transactions_serialized}), 200
