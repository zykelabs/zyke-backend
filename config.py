import os
from dotenv import load_dotenv

load_dotenv()
class Config:
    MONGO_URI = os.environ.get('MONGO_URI')
    JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY')
    # Email settings for OTP
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = os.environ.get('MAIL_PORT')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    FRONTEND_URL=os.environ.get('FRONTEND_URL')
    BACKEND_URL=os.environ.get('BACKEND_URL')
    
    PERPLEXITY_TOKEN = os.getenv('PERPLEXITY_TOKEN')

    # Razorpay Configurations
    RAZORPAY_KEY = os.environ.get('RAZORPAY_KEY')
    RAZORPAY_SECRET = os.environ.get('RAZORPAY_SECRET')
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET')
    
    DEEPINFRA_API_KEY=os.environ.get('DEEPINFRA_API_KEY')

    OPENROUTER_API_KEY=os.environ.get('OPENROUTER_API_KEY')
    GOOGLE_API_KEY=os.environ.get('GOOGLE_API_KEY')
    GOOGLE_CSE_ID=os.environ.get('GOOGLE_CSE_ID')