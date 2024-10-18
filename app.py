from flask import Flask, jsonify
from config import Config
from auth import auth_bp
from brand import brand_bp
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from emailservice import init_mail

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Mail
init_mail(app)

# Register JWT manager
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(brand_bp, url_prefix='/brand')

@app.route('/')
def home():
    return jsonify({'msg': 'Welcome to the Flask Authentication and Brand API!'})

# Example protected route
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({'msg': f'Hello, user {current_user}! This is a protected route.'})

if __name__ == '__main__':
    app.run(debug=True)
