import pyotp
import time

otp_storage = {}

SECRET_KEY = pyotp.random_base32() 

totp = pyotp.TOTP(SECRET_KEY, interval=600)

def generate_otp(email):
    otp = totp.now()  # Generate the OTP for the current time window
    expiry_time = time.time() + 600  # OTP expires in 10 minutes
    otp_storage[email] = {
        'otp': otp,
        'expiry_time': expiry_time,
        'user_data': None
    }
    return otp

def store_user_data(email, user_data):
    if email in otp_storage:
        otp_storage[email]['user_data'] = user_data

def verify_otp(email, user_otp):
    print("Current OTP Storage:", otp_storage)
    if email in otp_storage:
        record = otp_storage[email]
        otp = record['otp']
        expiry_time = record['expiry_time']

        # Check if the OTP is expired
        if time.time() > expiry_time:
            del otp_storage[email]
            return False, "OTP expired", None

        # Verify if the provided OTP matches the stored OTP
        if otp == user_otp:
            user_data = record.get('user_data')
            if user_data:
                del otp_storage[email]
                return True, "OTP verified", user_data
            else:
                return False, "User data not found", None

    return False, "Invalid OTP", None
