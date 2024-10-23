# otp.py

import random
import string
from typing import Tuple, Dict
from datetime import datetime, timedelta

# Simple in-memory storage for OTPs
otp_storage: Dict[str, Tuple[str, datetime]] = {}
user_data_storage: Dict[str, Dict] = {}

def generate_otp(email: str, length: int = 6) -> str:
    """Generates a random OTP of specified length."""
    otp = ''.join(random.choices(string.digits, k=length))
    expiration_time = datetime.utcnow() + timedelta(minutes=10)  # OTP valid for 10 minutes
    otp_storage[email] = (otp, expiration_time)
    return otp

def verify_otp(email: str, otp: str) -> Tuple[bool, str, Dict]:
    """Verifies the OTP for the given email."""
    stored_otp, expiration_time = otp_storage.get(email, (None, None))
    if not stored_otp:
        return False, 'No OTP found for this email.', {}
    if datetime.utcnow() > expiration_time:
        del otp_storage[email]
        return False, 'OTP has expired.', {}
    if otp != stored_otp:
        return False, 'Invalid OTP.', {}
    
    # OTP is valid
    del otp_storage[email]
    
    # Retrieve user_data
    user_data = user_data_storage.get(email)
    if not user_data:
        return False, 'User data not found.', {}
    
    # Delete user_data after verification
    del user_data_storage[email]
    
    return True, 'OTP verified successfully.', user_data

def store_user_data(email: str, user_data: Dict):
    """Stores user data temporarily before OTP verification."""
    user_data_storage[email] = user_data
