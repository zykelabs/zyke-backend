import os
from dotenv import load_dotenv

load_dotenv()
class Config:
    # Mongo Secrets
    MONGO_URI = os.environ.get('MONGO_URI')
    JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY')
    
    # Email settings for OTP
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = os.environ.get('MAIL_PORT')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Website URLs
    FRONTEND_URL= os.environ.get('FRONTEND_URL')
    BACKEND_URL= os.environ.get('BACKEND_URL')
    
    # Google cloud authentication secrets
    GOOGLE_CLOUD_PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT')
    GOOGLE_CLOUD_JSON_AUTH_PATH = os.environ.get('GOOGLE_CLOUD_JSON_AUTH_PATH')
    
    # Scrapping Keys
    APIFY_API_KEY = os.environ.get("APIFY_API_KEY")
    BRIGHT_DATA_TOKEN = os.environ.get("BRIGHT_DATA_TOKEN")
    BRIGHT_DATA_INSTA_POST_DATASET_ID = os.environ.get("BRIGHT_DATA_INSTA_POST_DATASET_ID")
    BRIGHT_DATA_INSTA_REEL_DATASET_ID = os.environ.get("BRIGHT_DATA_INSTA_REEL_DATASET_ID")

    # Razorpay Configurations
    RAZORPAY_KEY = os.environ.get('RAZORPAY_KEY')
    RAZORPAY_SECRET = os.environ.get('RAZORPAY_SECRET')
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET')
    
    # Model API Keys
    DEEPINFRA_API_KEY = os.environ.get('DEEPINFRA_API_KEY')
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
    PERPLEXITY_TOKEN = os.environ.get('PERPLEXITY_TOKEN')
    TOGETHER_API_KEY = os.environ.get('TOGETHER_API_KEY')
    
    # Google search API Secrets
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    GOOGLE_CSE_ID = os.environ.get('GOOGLE_CSE_ID')