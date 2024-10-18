import random
import time
from models import find_user_by_email, update_user_otp
from utils import hash_password, verify_password

otp_storage = {}

def generate_otp(email):
    otp = random.randint(100000, 999999)
    expiry_time = time.time() + 600
    otp_storage[email] = (otp, expiry_time)
    return otp

def verify_otp(email, user_otp):
    print(otp_storage)
    if email in otp_storage:
        otp, expiry_time = otp_storage[email]
        if time.time() > expiry_time:
            return False, "OTP expired"
        if otp == int(user_otp):
            del otp_storage[email]
            return True, "OTP verified"
    return False, "Invalid OTP"
