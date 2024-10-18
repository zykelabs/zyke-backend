from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from datetime import timedelta
import re

def hash_password(password):
    return generate_password_hash(password)

def verify_password(password, hashed):
    return check_password_hash(hashed, password)

def generate_jwt(identity):
    return create_access_token(identity=identity, expires_delta=timedelta(hours=1))

def validate_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://' 
        r'(?:\S+(?::\S*)?@)?'
        r'(?:'
        r'(?:(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})'
        r'|'
        r'localhost'
        r'|'
        r'\d{1,3}(?:\.\d{1,3}){3}'
        r')'
        r'(?::\d+)?'
        r'(?:/\S*)?$', re.IGNORECASE)
    return re.match(regex, url) is not None
