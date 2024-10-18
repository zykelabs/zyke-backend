from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    decode_token,
)
from models import (
    find_user_by_email,
    create_user,
    update_user_otp,
    update_user_password,
    save_google_user,
)
from emailservice import send_otp_email, send_password_reset_email
from otp import generate_otp, verify_otp
from utils import hash_password, verify_password
from oauth import get_google_provider_cfg, oauth_init, fetch_google_user_info
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

# Register User with OTP Verification
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')

    # Validate required fields
    if not email or not password or not first_name or not last_name:
        return jsonify({"msg": "Email, password, first name, and last name are required"}), 400

    if find_user_by_email(email):
        return jsonify({"msg": "User already exists"}), 409

    # Send OTP email
    otp = generate_otp(email)
    send_otp_email(email, otp)

    # Save user with pending OTP verification
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
        "otp_verified": False  # Additional field for OTP verification
    }
    create_user(user_data)

    return jsonify({"msg": "OTP sent to email"}), 200

# Verify OTP
@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({"msg": "Email and OTP are required"}), 400

    success, msg = verify_otp(email, otp)
    if success:
        update_user_otp(email, verified=True)
        return jsonify({"msg": "Email verified successfully"}), 200
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

# Reset Password
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

    return jsonify({"msg": "Password reset successful"}), 200

# Google OAuth2 login
@auth_bp.route('/google-login')
def google_login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = oauth_init(authorization_endpoint)
    return redirect(request_uri)

@auth_bp.route('/google-callback')
def google_callback():
    google_user_info = fetch_google_user_info()

    if google_user_info:
        email = google_user_info.get("email")
        first_name = google_user_info.get("given_name")
        last_name = google_user_info.get("family_name")
        provider_id = google_user_info.get("sub")

        if not email:
            return jsonify({"msg": "Failed to retrieve email from Google"}), 400

        user = find_user_by_email(email)

        if not user:
            # Create a new user with Google OAuth details
            user_data = {
                "email": email,
                "password": None,  # Nullable for OAuth users
                "first_name": first_name,
                "last_name": last_name,
                "auth_provider": "google",
                "provider_id": provider_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "otp_verified": True  # Assume verified via OAuth
            }
            create_user(user_data)

        access_token = create_access_token(identity=email)
        return jsonify({"access_token": access_token}), 200

    return jsonify({"msg": "Failed to login with Google"}), 400
