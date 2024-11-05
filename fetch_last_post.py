from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from pymongo import MongoClient
from config import Config  # Import Config from the appropriate module

# MongoDB setup
client = MongoClient(Config.MONGO_URI)
db = client['zyke_data']
collection = db['user_last_post']

# Blueprint for handling the request
fetch_last_post_bp = Blueprint('fetch_last_post', __name__)

@fetch_last_post_bp.route('/get_stored_post', methods=['POST'])
@jwt_required()
def generate_posts_api():
    user_id = get_jwt_identity()  # Retrieve the user ID from JWT
    # Fetch the document matching the user ID
    user_data = collection.find_one({"user_id": user_id}, {"posts": 1, "_id": 0})
    
    if user_data:
        return jsonify({"posts": user_data.get("posts")}), 200
    
    else:
        return jsonify({"error": "User not found or no posts available"}), 404