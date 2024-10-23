from flask import Flask, jsonify
from config import Config
from auth import auth_bp, oauth_init_app
from brand import brand_bp
from trends import trends_bp
from transactions import transactions_bp
from webhooks import webhooks_bp
from flask_jwt_extended import JWTManager
from emailservice import init_mail
from flask_cors import CORS

app = Flask(__name__)
app.config.from_object(Config)

CORS(app)
# Initialize Flask-Mail
init_mail(app)

# Register JWT manager
jwt = JWTManager(app)

# Initialize OAuth
oauth_init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(brand_bp, url_prefix='/brand')
app.register_blueprint(trends_bp, url_prefix='/trends') 
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(webhooks_bp, url_prefix='/webhooks')

@app.route('/')
def home():
    return jsonify({'msg': 'Welcome to the Flask Authentication and Brand API!'})

if __name__ == '__main__':
    app.run(debug=True)
