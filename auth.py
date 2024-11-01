from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from models import (
    find_user_by_email,
    create_user,
    update_user_password,
    update_user_razorpay_customer_id,
    get_user_by_id,
    update_transaction
)
from emailservice import (
    send_otp_email,
    send_password_reset_email,
    send_confirmation_email,
    send_password_reset_success_email
)
from otp import generate_otp, verify_otp,store_user_data
from utils import hash_password, verify_password
from authlib.integrations.flask_client import OAuth
from datetime import datetime
import os
import razorpay
from pymongo import MongoClient
import logging

# Initialize MongoDB client and define the users collection
mongo_client = MongoClient(os.environ.get('MONGO_URI'))
db = mongo_client.get_database('zyke_data')
users_collection = db.get_collection('users')

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register User with OTP Verification
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    logging.info("Registration Data: %s", data)
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
        "credits":3,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "otp_verified": False,
        "razorpay_customer_id": None  # Initially none
    }

    # Store user data in otp_storage for later verification
    store_user_data(email, user_data)

    return jsonify({"msg": "OTP sent to email"}), 200

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({"msg": "Email and OTP are required"}), 400

    # Verify the OTP
    success, msg, user_data = verify_otp(email, otp)
    
    if success:
        # Update user data to mark OTP as verified
        user_data['otp_verified'] = True  # Mark email as verified
        
        # Create user and get the user ID
        user_id = create_user(user_data)

        try:
            # Attempt to create a Razorpay customer
            customer = razorpay_client.customer.create({
                'name': f"{user_data.get('first_name')} {user_data.get('last_name')}",
                'email': email,
                'contact': user_data.get('phone', '')  # Assuming phone is collected
            })
            razorpay_customer_id = customer.get('id')

            # Update user with Razorpay customer ID
            update_user_razorpay_customer_id(user_id, razorpay_customer_id)

        except razorpay.errors.BadRequestError as e:
            error_message = str(e)
            if 'Customer already exists for the merchant' in error_message:
                # Fetch the existing customer from Razorpay
                try:
                    # Fetching the customer list from Razorpay to find the existing customer ID
                    customers = razorpay_client.customer.all({'email': email})
                    if customers and 'items' in customers:
                        existing_customer = next((cust for cust in customers['items'] if cust['email'] == email), None)
                        if existing_customer:
                            razorpay_customer_id = existing_customer.get('id')
                            update_user_razorpay_customer_id(user_id, razorpay_customer_id)
                            logging.info("Customer exists. Razorpay Customer ID: %s", razorpay_customer_id)
                        else:
                            raise Exception("Customer exists but could not fetch Razorpay Customer ID.")
                    else:
                        raise Exception("Customer exists but could not fetch Razorpay customer data.")
                except Exception as fetch_error:
                    logging.error("Error fetching Razorpay customer: %s", str(fetch_error))
                    return jsonify({"msg": "User created but failed to fetch existing payment profile."}), 201
            else:
                # For other bad request errors
                logging.error("BadRequestError from Razorpay: %s", error_message)
                return jsonify({"msg": "User created but failed to create payment profile. Bad Request Error."}), 201

        except razorpay.errors.ServerError as e:
            # Log server error from Razorpay
            logging.error("ServerError from Razorpay: %s", str(e))
            return jsonify({"msg": "User created but failed to create payment profile due to Razorpay server issue."}), 201

        except Exception as e:
            # Handle other exceptions
            logging.error("General error creating Razorpay customer: %s", str(e))
            return jsonify({"msg": "User created but failed to create payment profile due to an unexpected error."}), 201

        # Send confirmation email
        send_confirmation_email(email)

        return jsonify({"msg": "Email verified successfully. Confirmation email sent."}), 200

    # If OTP verification failed
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

    # Generate and return access token without otp_verified check
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
    logger.info("Received OAuth Data: %s", data)

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
            "credits": 3.0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "razorpay_customer_id": None  # To be created
        }
        user_id = create_user(user_data)

        try:
            # Attempt to create Razorpay customer
            customer = razorpay_client.customer.create({
                'name': f"{first_name} {last_name}",
                'email': email,
                'contact': user_data.get('contact', '')  # Assuming contact is collected
            })
            razorpay_customer_id = customer.get('id')

            # Update user with Razorpay customer ID
            update_user_razorpay_customer_id(user_id, razorpay_customer_id)

        except razorpay.errors.BadRequestError as e:
            error_message = str(e)
            if 'Customer already exists for the merchant' in error_message:
                # Fetch existing Razorpay customer by email
                try:
                    customers = razorpay_client.customer.all({'email': email})
                    if customers and 'items' in customers:
                        existing_customer = next((cust for cust in customers['items'] if cust['email'] == email), None)
                        if existing_customer:
                            razorpay_customer_id = existing_customer.get('id')
                            update_user_razorpay_customer_id(user_id, razorpay_customer_id)
                            logger.info("Customer exists. Razorpay Customer ID: %s", razorpay_customer_id)
                        else:
                            raise Exception("Customer exists but could not fetch Razorpay Customer ID.")
                    else:
                        raise Exception("Customer exists but could not fetch Razorpay customer data.")
                except Exception as fetch_error:
                    logger.error("Error fetching Razorpay customer: %s", str(fetch_error))
                    return jsonify({"msg": "OAuth login successful, but failed to fetch existing payment profile."}), 200
            else:
                logger.error("BadRequestError from Razorpay: %s", error_message)
                return jsonify({"msg": "OAuth login successful, but failed to create payment profile. Bad Request Error."}), 200

        except razorpay.errors.ServerError as e:
            logger.error("ServerError from Razorpay: %s", str(e))
            return jsonify({"msg": "OAuth login successful, but failed to create payment profile due to Razorpay server issue."}), 200

        except Exception as e:
            logger.error("General error creating Razorpay customer: %s", str(e))
            return jsonify({"msg": "OAuth login successful, but failed to create payment profile due to an unexpected error."}), 200

    return jsonify({"msg": "OAuth login successful"}), 200


@auth_bp.route('/user', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Retrieve the authenticated user's information.

    Returns:
        JSON response containing user details or an error message.
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404

    # Exclude sensitive data like password and Razorpay customer ID
    user_data = {
        "email": user.get("email"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "contact": user.get("contact", ""),  # Assuming contact is stored
        "credits": user.get("credits", 0.0)
        # Add other non-sensitive fields as needed
    }

    return jsonify(user_data), 200
