# app.py
from flask import Flask, jsonify
from config import Config
from trends import trends_bp
from transactions import transactions_bp
from webhooks import webhooks_bp
from flask_jwt_extended import JWTManager
from emailservice import init_mail
from flask_cors import CORS
from brandvoiceinfo import brand_voice_bp
from auth import oauth_init_app, auth_bp
from trend_to_idea import trend_to_idea_bp
from repurpose import repurpose_bp
from idea_to_post import idea_to_post_bp
from fetch_last_post import fetch_last_post_bp
from inpaint import inpainting_bp
from blend import blend_image_bp
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configure CORS to allow frontend domain
    CORS(app, resources={r"/*": {"origins": ["https://zyke.in","https://www.zyke.in"]}})
    
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
    app.register_blueprint(trend_to_idea_bp, url_prefix='/trend_to_idea')
    app.register_blueprint(repurpose_bp, url_prefix='/repurpose')
    app.register_blueprint(idea_to_post_bp, url_prefix='/idea_to_post')
    app.register_blueprint(fetch_last_post_bp, url_prefix='/fetch_last_post')
    app.register_blueprint(inpainting_bp, url_prefix='/inpaint')
    app.register_blueprint(blend_image_bp, url_prefix='/blend')


    @app.route('/')
    def home():
        return jsonify({'msg': 'Welcome to the Flask Authentication and Brand API!'})

    # Global error handler to include CORS headers
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Log the error
        # logger.error(f"Unhandled Exception: {e}", exc_info=True)

        # Return JSON response with CORS headers
        response = jsonify({"error": "Internal Server Error", "message": str(e)})
        response.status_code = 500
        return response

    return app

app = create_app()

if __name__ == '__main__':
    # app.run(debug=True)
    app.run()
