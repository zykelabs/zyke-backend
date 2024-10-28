from pymongo import MongoClient
from config import Config
from bson.objectid import ObjectId
from datetime import datetime
from typing import Optional

# Establish MongoDB connection
client = MongoClient(Config.MONGO_URI)
db = client.get_database(name="zyke_data")

# Define MongoDB collections
users_collection = db.users
otp_storage_collection = db.otp_storage
transactions_collection = db.transactions
brand_profiles_collection = db.brand_profiles
brand_voices_collection = db.brand_voices

# User-related functions
def find_user_by_email(email):
    """Find a user by email."""
    return users_collection.find_one({'email': email})

def get_user_by_id(user_id):
    """Find a user by their ObjectId."""
    return users_collection.find_one({'_id': ObjectId(user_id)})

def create_user(user_data):
    """Create a new user."""
    user_data.setdefault("created_at", datetime.utcnow())
    user_data.setdefault("updated_at", datetime.utcnow())
    user_data.setdefault("auth_provider", "manual")
    user_data.setdefault("provider_id", None)
    user_data.setdefault("otp_verified", False)
    user_data.setdefault("credits", 3.0)  # Set default credits

    result = users_collection.insert_one(user_data)
    return str(result.inserted_id)

def update_user_otp(email, verified):
    """Update the OTP verification status of a user."""
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
    """Update a user's password."""
    users_collection.update_one(
        {"email": email},
        {
            "$set": {
                "password": new_password,
                "updated_at": datetime.utcnow()
            }
        }
    )

def store_temporary_user_data(user_data, otp, expiration_time):
    """Store user data temporarily with OTP and expiration time."""
    user_data["otp"] = otp
    user_data["otp_expires_at"] = expiration_time
    otp_storage_collection.insert_one(user_data)

def get_temporary_user_data(email):
    """Retrieve temporarily stored user data by email."""
    return otp_storage_collection.find_one({'email': email})

def delete_temporary_user_data(email):
    """Delete temporarily stored user data by email."""
    otp_storage_collection.delete_one({'email': email})

def move_user_to_main_collection(email):
    """Move user from temporary collection to main users collection upon OTP verification."""
    user_data = get_temporary_user_data(email)
    if user_data:
        user_data.pop("otp", None)
        user_data.pop("otp_expires_at", None)
        create_user(user_data)
        delete_temporary_user_data(email)

def update_user_razorpay_customer_id(user_id, razorpay_customer_id):
    users_collection.update_one(
        {'_id': ObjectId(user_id)},
        {
            "$set": {
                "razorpay_customer_id": razorpay_customer_id,
                "updated_at": datetime.utcnow()
            }
        }
    )

# OAuth-related functions
def update_user_oauth(email, oauth_data):
    """Update or create a user based on Google OAuth."""
    existing_user = find_user_by_email(email)
    
    # If the user exists, update their data
    if existing_user:
        users_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "provider_id": oauth_data.get("provider_id"),
                    "auth_provider": oauth_data.get("auth_provider", "google"),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return existing_user["_id"]
    else:
        # If the user doesn't exist, create a new user with OAuth data
        user_data = {
            "email": email,
            "first_name": oauth_data.get("first_name"),
            "last_name": oauth_data.get("last_name"),
            "auth_provider": "google",
            "provider_id": oauth_data.get("provider_id"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "otp_verified": True  # OAuth users are considered verified
        }
        result = users_collection.insert_one(user_data)
        return str(result.inserted_id)

# Brand Profile-related functions
def create_brand_profile(user_id, profile_data):
    """
    Create a new brand profile.
    """
    result = brand_profiles_collection.insert_one(profile_data)
    return str(result.inserted_id)

def get_brand_profile(user_id):
    """
    Retrieve a brand profile by user ID.
    """
    return brand_profiles_collection.find_one({'user_id': user_id})

def create_brand_voice(profile_id, voice_data):
    """
    Create a new brand voice associated with a brand profile.
    """
    voice_data['brand_profile_id'] = ObjectId(profile_id)
    result = brand_voices_collection.insert_one(voice_data)
    return str(result.inserted_id)

def get_brand_voice(profile_id):
    """
    Retrieve a brand voice by brand profile ID.
    """
    return brand_voices_collection.find_one({'brand_profile_id': ObjectId(profile_id)})

def update_brand_voice(profile_id, voice_data):
    """
    Update an existing brand voice associated with a brand profile.
    """
    result = brand_voices_collection.update_one(
        {'brand_profile_id': ObjectId(profile_id)},
        {'$set': voice_data},
        upsert=True
    )
    return result.modified_count

# Transaction-related functions
def create_transaction(transaction_data):
    """
    Inserts a new transaction into the transactions collection.
    """
    transaction_data.setdefault("created_at", datetime.utcnow())
    result = transactions_collection.insert_one(transaction_data)
    return str(result.inserted_id)

def get_transactions_by_user(user_id, limit=50):
    """
    Retrieves transactions for a specific user, limited by the 'limit' parameter.
    """
    return list(transactions_collection.find({"user_id": ObjectId(user_id)}).sort("created_at", -1).limit(limit))

def get_transaction_by_id(transaction_id):
    """
    Retrieves a single transaction by its ID.
    """
    return transactions_collection.find_one({"_id": ObjectId(transaction_id)})

def get_user_by_razorpay_customer_id(razorpay_customer_id):
    """
    Retrieves a user by their Razorpay customer ID.
    """
    return users_collection.find_one({'razorpay_customer_id': razorpay_customer_id})

def get_user_credits(user_id):
    """Retrieve the current credits for a user by user_id."""
    user = users_collection.find_one({"_id": ObjectId(user_id)}, {"credits": 1})
    return user.get("credits") if user else None

def update_user_credits(user_id, credits):
    """Update a user's credits."""
    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"credits": credits, "updated_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
