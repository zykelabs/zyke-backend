from pymongo import MongoClient
from config import Config
from bson.objectid import ObjectId
from datetime import datetime

# Establish MongoDB connection
client = MongoClient(Config.MONGO_URI)
db = client.get_database(name="zyke_data")

# Define MongoDB collections
users_collection = db.users
brand_profiles_collection = db.brand_profiles
brand_voices_collection = db.brand_voices

# User-related functions
def find_user_by_username(username):
    """
    Find a user by their username.
    :param username: str
    :return: dict or None
    """
    return users_collection.find_one({'username': username})

def find_user_by_email(email):
    """
    Find a user by their email.
    :param email: str
    :return: dict or None
    """
    return users_collection.find_one({'email': email})

def create_user(user_data):
    """
    Create a new user.
    :param user_data: dict
    :return: str (user_id)
    """
    # Ensure email uniqueness is enforced at the database level
    user_data.setdefault("created_at", datetime.utcnow())
    user_data.setdefault("updated_at", datetime.utcnow())
    user_data.setdefault("auth_provider", "manual")
    user_data.setdefault("provider_id", None)
    user_data.setdefault("otp_verified", False)

    result = users_collection.insert_one(user_data)
    return str(result.inserted_id)

def get_user_by_id(user_id):
    """
    Get user information by user ID.
    :param user_id: str
    :return: dict or None
    """
    return users_collection.find_one({'_id': ObjectId(user_id)})

def update_user_otp(email, verified):
    """
    Update the OTP verification status of a user.
    :param email: str
    :param verified: bool
    :return: None
    """
    users_collection.update_one(
        {"email": email},
        {
            "$set": {
                "otp_verified": verified,
                "updated_at": datetime.utcnow()
            }
        }
    )

def update_user_password(email, new_password):
    """
    Update the user's password.
    :param email: str
    :param new_password: str
    :return: None
    """
    users_collection.update_one(
        {"email": email},
        {
            "$set": {
                "password": new_password,
                "updated_at": datetime.utcnow()
            }
        }
    )

def save_google_user(user_info):
    """
    Save a new Google OAuth user.
    :param user_info: dict
    :return: str (user_id)
    """
    user_data = {
        "email": user_info.get("email"),
        "password": None,  # Nullable for OAuth users
        "first_name": user_info.get("given_name"),
        "last_name": user_info.get("family_name"),
        "auth_provider": "google",
        "provider_id": user_info.get("sub"),  # Google's unique user ID
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "otp_verified": True  # Assume verified via OAuth
    }
    result = users_collection.insert_one(user_data)
    return str(result.inserted_id)

# Brand Profile-related functions
def create_brand_profile(user_id, profile_data):
    """
    Create a brand profile for a user.
    :param user_id: str
    :param profile_data: dict
    :return: str (profile_id)
    """
    profile_data['user_id'] = ObjectId(user_id)
    profile_data['created_at'] = datetime.utcnow()
    profile_data['updated_at'] = datetime.utcnow()
    result = brand_profiles_collection.insert_one(profile_data)
    return str(result.inserted_id)

def get_brand_profile(user_id):
    """
    Retrieve a brand profile by user ID.
    :param user_id: str
    :return: dict or None
    """
    return brand_profiles_collection.find_one({'user_id': ObjectId(user_id)})

def update_brand_profile(user_id, update_data):
    """
    Update a brand profile for a user.
    :param user_id: str
    :param update_data: dict
    :return: int (modified count)
    """
    update_data['updated_at'] = datetime.utcnow()
    result = brand_profiles_collection.update_one(
        {'user_id': ObjectId(user_id)},
        {'$set': update_data}
    )
    return result.modified_count

def delete_brand_profile(user_id):
    """
    Delete a brand profile associated with a user.
    :param user_id: str
    :return: int (deleted count)
    """
    result = brand_profiles_collection.delete_one({'user_id': ObjectId(user_id)})
    return result.deleted_count

# Brand Voice-related functions
def create_brand_voice(profile_id, voice_data):
    """
    Create a brand voice associated with a brand profile.
    :param profile_id: str
    :param voice_data: dict
    :return: str (voice_id)
    """
    voice_data['brand_profile_id'] = ObjectId(profile_id)
    voice_data['created_at'] = datetime.utcnow()
    voice_data['updated_at'] = datetime.utcnow()
    result = brand_voices_collection.insert_one(voice_data)
    return str(result.inserted_id)

def get_brand_voice(profile_id):
    """
    Retrieve a brand voice by profile ID.
    :param profile_id: str
    :return: dict or None
    """
    return brand_voices_collection.find_one({'brand_profile_id': ObjectId(profile_id)})

def update_brand_voice(profile_id, update_data):
    """
    Update a brand voice for a specific brand profile.
    :param profile_id: str
    :param update_data: dict
    :return: int (modified count)
    """
    update_data['updated_at'] = datetime.utcnow()
    result = brand_voices_collection.update_one(
        {'brand_profile_id': ObjectId(profile_id)},
        {'$set': update_data}
    )
    return result.modified_count

def delete_brand_voice(profile_id):
    """
    Delete a brand voice associated with a brand profile.
    :param profile_id: str
    :return: int (deleted count)
    """
    result = brand_voices_collection.delete_one({'brand_profile_id': ObjectId(profile_id)})
    return result.deleted_count
