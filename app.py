from flask import Flask, jsonify
from config import Config
from trends import trends_bp
from transactions import transactions_bp
from webhooks import webhooks_bp
from flask_jwt_extended import JWTManager
from emailservice import init_mail
from flask_cors import CORS
from brandvoiceinfo import brand_voice_bp
from auth import oauth_init_app,auth_bp

app = Flask(__name__)
app.config.from_object(Config)

# Configure CORS to allow frontend domain
CORS(app)

# Initialize Flask-Mail
init_mail(app)

# Initialize JWT
jwt = JWTManager(app)

# Initialize OAuth
oauth_init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(trends_bp, url_prefix='/trends') 
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
app.register_blueprint(brand_voice_bp, url_prefix='/brand_voice_info')

@app.route('/')
def home():
    return jsonify({'msg': 'Welcome to the Flask Authentication and Brand API!'})

if __name__ == '__main__':
    app.run(debug=True)
