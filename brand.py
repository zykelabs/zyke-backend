from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    create_brand_profile, get_brand_profile, update_brand_profile, delete_brand_profile,
    create_brand_voice, get_brand_voice, update_brand_voice, delete_brand_voice
)
from utils import validate_url

brand_bp = Blueprint('brand', __name__, url_prefix='/brand')

@brand_bp.route('/profile', methods=['POST'])
@jwt_required()
def create_profile():
    user_id = get_jwt_identity()
    data = request.get_json()

    # Extract and validate required fields
    brand_name = data.get('brandName')
    brand_description = data.get('brandDescription')
    website = data.get('website')
    instagram_handle = data.get('instagramHandle')
    twitter_handle = data.get('twitterHandle')

    if not all([brand_name, brand_description, website, instagram_handle, twitter_handle]):
        return jsonify({'msg': 'All brand profile fields are required.'}), 400

    if not validate_url(website):
        return jsonify({'msg': 'Invalid website URL.'}), 400

    profile_data = {
        'brandName': brand_name,
        'brandDescription': brand_description,
        'website': website,
        'instagramHandle': instagram_handle,
        'twitterHandle': twitter_handle
    }

    profile_id = create_brand_profile(user_id, profile_data)

    return jsonify({'msg': 'Brand profile created successfully.', 'profile_id': profile_id}), 201

@brand_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    profile = get_brand_profile(user_id)

    if not profile:
        return jsonify({'msg': 'Brand profile not found.'}), 404

    # Convert ObjectId to string for JSON serialization
    profile['_id'] = str(profile['_id'])
    profile['user_id'] = str(profile['user_id'])

    return jsonify(profile), 200

@brand_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile_route():
    user_id = get_jwt_identity()
    data = request.get_json()

    # Optional fields to update
    update_data = {}
    if 'brandName' in data:
        update_data['brandName'] = data['brandName']
    if 'brandDescription' in data:
        update_data['brandDescription'] = data['brandDescription']
    if 'website' in data:
        if not validate_url(data['website']):
            return jsonify({'msg': 'Invalid website URL.'}), 400
        update_data['website'] = data['website']
    if 'instagramHandle' in data:
        update_data['instagramHandle'] = data['instagramHandle']
    if 'twitterHandle' in data:
        update_data['twitterHandle'] = data['twitterHandle']

    if not update_data:
        return jsonify({'msg': 'No valid fields to update.'}), 400

    modified_count = update_brand_profile(user_id, update_data)

    if modified_count == 0:
        return jsonify({'msg': 'No changes made to the brand profile.'}), 200

    return jsonify({'msg': 'Brand profile updated successfully.'}), 200

@brand_bp.route('/profile', methods=['DELETE'])
@jwt_required()
def delete_profile_route():
    user_id = get_jwt_identity()
    deleted_count = delete_brand_profile(user_id)

    if deleted_count == 0:
        return jsonify({'msg': 'Brand profile not found.'}), 404

    # Optionally, delete associated brand voice
    delete_brand_voice(user_id)

    return jsonify({'msg': 'Brand profile deleted successfully.'}), 200

@brand_bp.route('/voice', methods=['POST'])
@jwt_required()
def create_voice():
    user_id = get_jwt_identity()
    data = request.get_json()

    # Extract and validate required fields
    voice_name = data.get('voiceName')
    purpose = data.get('purpose')
    audience = data.get('audience')
    tone = data.get('tone')  # List of strings
    emotion = data.get('emotion')  # List of strings
    character = data.get('character')  # List of strings
    syntax = data.get('syntax')

    if not all([voice_name, purpose, audience, tone, emotion, character, syntax]):
        return jsonify({'msg': 'All brand voice fields are required.'}), 400

    # Ensure lists are actually lists
    if not (isinstance(tone, list) and isinstance(emotion, list) and isinstance(character, list)):
        return jsonify({'msg': 'Tone, Emotion, and Character must be lists of strings.'}), 400

    # Retrieve the user's brand profile
    profile = get_brand_profile(user_id)
    if not profile:
        return jsonify({'msg': 'Brand profile not found. Please create a brand profile first.'}), 404

    voice_data = {
        'voiceName': voice_name,
        'purpose': purpose,
        'audience': audience,
        'tone': tone,
        'emotion': emotion,
        'character': character,
        'syntax': syntax
    }

    voice_id = create_brand_voice(profile['_id'], voice_data)

    return jsonify({'msg': 'Brand voice created successfully.', 'voice_id': voice_id}), 201

@brand_bp.route('/voice', methods=['GET'])
@jwt_required()
def get_voice():
    user_id = get_jwt_identity()

    # Retrieve the user's brand profile
    profile = get_brand_profile(user_id)
    if not profile:
        return jsonify({'msg': 'Brand profile not found.'}), 404

    voice = get_brand_voice(profile['_id'])

    if not voice:
        return jsonify({'msg': 'Brand voice not found.'}), 404

    # Convert ObjectId to string for JSON serialization
    voice['_id'] = str(voice['_id'])
    voice['brand_profile_id'] = str(voice['brand_profile_id'])

    return jsonify(voice), 200

@brand_bp.route('/voice', methods=['PUT'])
@jwt_required()
def update_voice_route():
    user_id = get_jwt_identity()
    data = request.get_json()

    # Optional fields to update
    update_data = {}
    if 'voiceName' in data:
        update_data['voiceName'] = data['voiceName']
    if 'purpose' in data:
        update_data['purpose'] = data['purpose']
    if 'audience' in data:
        update_data['audience'] = data['audience']
    if 'tone' in data:
        if not isinstance(data['tone'], list):
            return jsonify({'msg': 'Tone must be a list of strings.'}), 400
        update_data['tone'] = data['tone']
    if 'emotion' in data:
        if not isinstance(data['emotion'], list):
            return jsonify({'msg': 'Emotion must be a list of strings.'}), 400
        update_data['emotion'] = data['emotion']
    if 'character' in data:
        if not isinstance(data['character'], list):
            return jsonify({'msg': 'Character must be a list of strings.'}), 400
        update_data['character'] = data['character']
    if 'syntax' in data:
        update_data['syntax'] = data['syntax']

    if not update_data:
        return jsonify({'msg': 'No valid fields to update.'}), 400

    # Retrieve the user's brand profile
    profile = get_brand_profile(user_id)
    if not profile:
        return jsonify({'msg': 'Brand profile not found.'}), 404

    modified_count = update_brand_voice(profile['_id'], update_data)

    if modified_count == 0:
        return jsonify({'msg': 'No changes made to the brand voice.'}), 200

    return jsonify({'msg': 'Brand voice updated successfully.'}), 200

@brand_bp.route('/voice', methods=['DELETE'])
@jwt_required()
def delete_voice_route():
    user_id = get_jwt_identity()

    # Retrieve the user's brand profile
    profile = get_brand_profile(user_id)
    if not profile:
        return jsonify({'msg': 'Brand profile not found.'}), 404

    deleted_count = delete_brand_voice(profile['_id'])

    if deleted_count == 0:
        return jsonify({'msg': 'Brand voice not found.'}), 404

    return jsonify({'msg': 'Brand voice deleted successfully.'}), 200
