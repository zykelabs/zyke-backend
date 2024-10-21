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
    return users_collection.find_one({'username': username})

def find_user_by_email(email):
    return users_collection.find_one({'email': email})

def create_user(user_data):
    # Ensure email uniqueness is enforced at the database level
    user_data.setdefault("created_at", datetime.utcnow())
    user_data.setdefault("updated_at", datetime.utcnow())
    user_data.setdefault("auth_provider", "manual")
    user_data.setdefault("provider_id", None)
    user_data.setdefault("otp_verified", False)

    result = users_collection.insert_one(user_data)
    return str(result.inserted_id)

def get_user_by_id(user_id):
    return users_collection.find_one({'_id': ObjectId(user_id)})

def update_user_otp(email, verified):
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
    users_collection.update_one(
        {"email": email},
        {
            "$set": {
                "password": new_password,
                "updated_at": datetime.utcnow()
            }
        }
    )


# Brand Profile-related functions
def create_brand_profile(user_id, profile_data):
    profile_data['user_id'] = ObjectId(user_id)
    profile_data['created_at'] = datetime.utcnow()
    profile_data['updated_at'] = datetime.utcnow()
    result = brand_profiles_collection.insert_one(profile_data)
    return str(result.inserted_id)

def get_brand_profile(user_id):
    return brand_profiles_collection.find_one({'user_id': ObjectId(user_id)})

def update_brand_profile(user_id, update_data):
    update_data['updated_at'] = datetime.utcnow()
    result = brand_profiles_collection.update_one(
        {'user_id': ObjectId(user_id)},
        {'$set': update_data}
    )
    return result.modified_count

def delete_brand_profile(user_id):
    result = brand_profiles_collection.delete_one({'user_id': ObjectId(user_id)})
    return result.deleted_count

# Brand Voice-related functions
def create_brand_voice(profile_id, voice_data):
    voice_data['brand_profile_id'] = ObjectId(profile_id)
    voice_data['created_at'] = datetime.utcnow()
    voice_data['updated_at'] = datetime.utcnow()
    result = brand_voices_collection.insert_one(voice_data)
    return str(result.inserted_id)

def get_brand_voice(profile_id):
    return brand_voices_collection.find_one({'brand_profile_id': ObjectId(profile_id)})

def update_brand_voice(profile_id, update_data):
    update_data['updated_at'] = datetime.utcnow()
    result = brand_voices_collection.update_one(
        {'brand_profile_id': ObjectId(profile_id)},
        {'$set': update_data}
    )
    return result.modified_count

def delete_brand_voice(profile_id):
    result = brand_voices_collection.delete_one({'brand_profile_id': ObjectId(profile_id)})
    return result.deleted_count
