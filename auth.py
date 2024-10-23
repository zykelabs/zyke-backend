from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import find_user_by_email, create_user, update_user_password, update_user_razorpay_customer_id
from emailservice import (
    send_otp_email,
    send_password_reset_email,
    send_confirmation_email,
    send_password_reset_success_email
)
from otp import generate_otp, verify_otp, store_user_data
from utils import hash_password, verify_password
from authlib.integrations.flask_client import OAuth
from datetime import datetime
import os
import razorpay  # Import Razorpay SDK

# Allow OAuthlib to use HTTP for development (disable in production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

auth_bp = Blueprint('auth', __name__)

# Initialize OAuth
oauth = OAuth()

def oauth_init_app(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(os.environ.get('RAZORPAY_KEY'), os.environ.get('RAZORPAY_SECRET'))
)

# Register User with OTP Verification
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    print("Registration Data:", data)
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')

    # Validate required fields
    if not email or not password or not first_name or not last_name:
        return jsonify({"msg": "Email, password, first name, and last name are required"}), 400

    if find_user_by_email(email):
        return jsonify({"msg": "User already exists"}), 409

    # Generate OTP
    otp = generate_otp(email)

    # Send OTP email
    send_otp_email(email, otp)

    # Prepare user data but do not save to main collection yet
    hashed_password = hash_password(password)
    user_data = {
        "email": email,
        "password": hashed_password,
        "first_name": first_name,
        "last_name": last_name,
        "auth_provider": "manual",
        "provider_id": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "otp_verified": False,
        "razorpay_customer_id": None  # Initially none
    }

    # Store user data in otp_storage for later verification
    store_user_data(email, user_data)

    return jsonify({"msg": "OTP sent to email"}), 200

# Verify OTP and save user
@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({"msg": "Email and OTP are required"}), 400

    success, msg, user_data = verify_otp(email, otp)
    if success:
        # Update user data to mark OTP as verified
        user_id = create_user(user_data)

        # Create Razorpay customer
        try:
            customer = razorpay_client.customer.create({
                'name': f"{user_data.get('first_name')} {user_data.get('last_name')}",
                'email': email,
                'contact': user_data.get('phone', '')  # Assuming phone is collected
            })
            razorpay_customer_id = customer.get('id')

            # Update user with Razorpay customer ID
            update_user_razorpay_customer_id(user_id, razorpay_customer_id)
        except Exception as e:
            print("Error creating Razorpay customer:", e)
            # Optionally handle customer creation failure
            return jsonify({"msg": "User created but failed to create payment profile"}), 201

        # Send confirmation email
        send_confirmation_email(email)

        return jsonify({"msg": "Email verified successfully. Confirmation email sent."}), 200
    return jsonify({"msg": msg}), 400

# Login User
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "Email and password are required"}), 400

    user = find_user_by_email(email)
    if not user or not user.get('password') or not verify_password(password, user['password']):
        return jsonify({"msg": "Invalid email or password"}), 401

    if not user.get('otp_verified'):
        return jsonify({"msg": "Email not verified. Please verify your email"}), 403

    access_token = create_access_token(identity=str(user['_id']))
    return jsonify({"access_token": access_token}), 200

# Request Password Reset
@auth_bp.route('/request-reset', methods=['POST'])
def request_reset():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"msg": "Email is required"}), 400

    user = find_user_by_email(email)
    if not user:
        return jsonify({"msg": "Email not found"}), 404

    reset_token = create_access_token(identity=email, expires_delta=False)
    send_password_reset_email(email, reset_token)

    return jsonify({"msg": "Password reset email sent"}), 200

# Reset Password and send confirmation email
@auth_bp.route('/reset-password', methods=['POST'])
@jwt_required()
def reset_password():
    data = request.get_json()
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({"msg": "New password is required"}), 400

    email = get_jwt_identity()

    user = find_user_by_email(email)
    if not user:
        return jsonify({"msg": "Invalid reset token"}), 400

    hashed_password = hash_password(new_password)
    update_user_password(email, hashed_password)
    
    # Send confirmation email after successful password reset
    send_password_reset_success_email(email)

    return jsonify({"msg": "Password reset successful. Confirmation email sent."}), 200

# OAuth Login
@auth_bp.route('/oauth-login', methods=['POST'])
def oauth_login():
    data = request.get_json()
    print("Received OAuth Data:", data)  # Debugging line to see incoming data

    email = data.get('email')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    provider_id = data.get('provider_id')
    auth_provider = data.get('auth_provider')

    if not email:
        return jsonify({"msg": "Email is required"}), 400

    user = find_user_by_email(email)

    if not user:
        # Create a new user if they don't exist
        user_data = {
            "email": email,
            "password": None,
            "first_name": first_name,
            "last_name": last_name,
            "auth_provider": auth_provider,
            "provider_id": provider_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "otp_verified": True,  # OAuth users are considered verified
            "razorpay_customer_id": None  # To be created
        }
        user_id = create_user(user_data)

        # Create Razorpay customer
        try:
            customer = razorpay_client.customer.create({
                'name': f"{first_name} {last_name}",
                'email': email,
                'contact': user_data.get('phone', '')  # Assuming phone is collected
            })
            razorpay_customer_id = customer.get('id')

            # Update user with Razorpay customer ID
            update_user_razorpay_customer_id(user_id, razorpay_customer_id)
        except Exception as e:
            print("Error creating Razorpay customer:", e)
            # Optionally handle customer creation failure
            return jsonify({"msg": "OAuth login successful, but failed to create payment profile"}), 200

    return jsonify({"msg": "OAuth login successful"}), 200  # Ensure the response is JSON
