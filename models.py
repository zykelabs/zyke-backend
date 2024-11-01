from pymongo import MongoClient, DESCENDING, ReturnDocument
from config import Config
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import logging
from pymongo.errors import PyMongoError

# Configure logging
logger = logging.getLogger(__name__)

# Establish MongoDB connection
client = MongoClient(Config.MONGO_URI)
db = client.get_database(name="zyke_data")

# Define MongoDB collections
users_collection = db.users
otp_storage_collection = db.otp_storage
transactions_collection = db.transactions
brand_profiles_collection = db.brand_profiles
brand_voices_collection = db.brand_voices
user_trends_collection = db.user_trends  # Added collection for user trends
user_last_post_collection = db.user_last_posts  # Added collection for user last posts
total_costs_collection = db.total_costs  # New collection for total costs

# Initialize total cost document if not exists
def initialize_total_cost():
    if total_costs_collection.count_documents({}) == 0:
        total_costs_collection.insert_one({"total_cost": 0.0})
        
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

def store_temporary_user_data(email, user_data):
    """Store user data temporarily with OTP and expiration time."""
    otp = user_data.get('otp')
    otp_expires_at = user_data.get('otp_expires_at')
    otp_storage_collection.update_one(
        {'email': email},
        {
            "$set": {
                "email": email,
                "otp": otp,
                "otp_expires_at": otp_expires_at,
                "user_data": user_data  # Store other user data
            }
        },
        upsert=True
    )

def get_temporary_user_data(email):
    """Retrieve temporarily stored user data by email."""
    data = otp_storage_collection.find_one({'email': email})
    if data:
        return {
            "otp": data.get("otp"),
            "otp_expires_at": data.get("otp_expires_at"),
            **data.get("user_data", {})
        }
    return None

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
    """Update a user's Razorpay customer ID."""
    users_collection.update_one(
        {'_id': ObjectId(user_id)},
        {
            "$set": {
                "razorpay_customer_id": razorpay_customer_id,
                "updated_at": datetime.utcnow()
            }
        }
    )

def update_transaction(transaction_id, update_data):
    """Update a transaction record."""
    result = transactions_collection.update_one(
        {"_id": ObjectId(transaction_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0

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
        return str(existing_user["_id"])
    else:
        # If the user doesn't exist, create a new user with OAuth data
        user_data = {
            "email": email,
            "password": None,
            "first_name": oauth_data.get("first_name"),
            "last_name": oauth_data.get("last_name"),
            "auth_provider": "google",
            "provider_id": oauth_data.get("provider_id"),
            "credits": 3.0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "razorpay_customer_id": None,  # To be created
            "otp_verified": True  # OAuth users are considered verified
        }
        result = users_collection.insert_one(user_data)
        return str(result.inserted_id)

# Brand Profile-related functions
def create_brand_profile(user_id, profile_data):
    """Create a new brand profile."""
    result = brand_profiles_collection.insert_one(profile_data)
    return str(result.inserted_id)

def get_brand_profile(user_id):
    """Retrieve a brand profile by user ID."""
    return brand_profiles_collection.find_one({'user_id':user_id})

def create_brand_voice(profile_id, voice_data):
    """Create a new brand voice associated with a brand profile."""
    voice_data['brand_profile_id'] = ObjectId(profile_id)
    result = brand_voices_collection.insert_one(voice_data)
    return str(result.inserted_id)

def get_brand_voice(profile_id):
    """Retrieve a brand voice by brand profile ID."""
    return brand_voices_collection.find_one({'brand_profile_id': ObjectId(profile_id)})

def update_brand_voice(profile_id, voice_data):
    """Update an existing brand voice associated with a brand profile."""
    result = brand_voices_collection.update_one(
        {'brand_profile_id': ObjectId(profile_id)},
        {'$set': voice_data},
        upsert=True
    )
    return result.modified_count

# Transaction-related functions
def create_transaction(transaction_data):
    """Inserts a new transaction into the transactions collection."""
    transaction_data.setdefault("created_at", datetime.utcnow())
    result = transactions_collection.insert_one(transaction_data)
    return str(result.inserted_id)

def serialize_transaction(transaction):
    transaction["_id"] = str(transaction["_id"])
    transaction["user_id"] = str(transaction["user_id"])
    return transaction

def get_transactions_by_user(user_id):
    """
    Retrieve transactions for a specific user.
    
    Args:
        user_id (str): The ID of the user.
    
    Returns:
        List[dict]: List of serialized transactions.
    """
    try:
        transactions_cursor = transactions_collection.find({"user_id": user_id}).sort("created_at", DESCENDING)
        return [serialize_transaction(tx) for tx in transactions_cursor]
    except Exception as e:
        logger.error(f"Error fetching transactions for user_id {user_id}: {str(e)}")
        return []

# Additional user collections (if not already defined)
# Ensure these collections are defined in your MongoDB
user_trends_collection = db.user_trends  # Collection for user trends
user_last_post_collection = db.user_last_posts  # Collection for user last posts

# Credit-related functions
def get_user_by_razorpay_customer_id(razorpay_customer_id):
    """Retrieves a user by their Razorpay customer ID."""
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

# def deduct_user_credits(user_id, amount):
#     """Deduct a specified amount of credits from a user's account."""
#     result = users_collection.update_one(
#         {"_id": ObjectId(user_id)},
#         {"$inc": {"credits": -amount}, "$set": {"updated_at": datetime.utcnow()}}
#     )
#     return result.modified_count > 0

def increment_total_cost(amount, session):
    """Increment the total cost used by all users."""
    result = total_costs_collection.update_one(
        {},
        {"$inc": {"total_cost": amount}},
        session=session
    )
    return result.modified_count == 1

def deduct_and_log_user_credits(user_id, amount, description, transaction_type="credit_deduction"):
    """
    Deducts credits from a user and logs the transaction.

    Parameters:
    - user_id (str): The unique identifier of the user.
    - amount (float): The amount of credits to deduct. Must be positive.
    - description (str): A description for the transaction.
    - transaction_type (str): The type of transaction. Defaults to "credit_deduction".

    Raises:
    - ValueError: If the amount is not positive or if the user has insufficient credits.
    - PyMongoError: If there is an issue with the MongoDB operations.
    """
    if amount <= 0:
        raise ValueError("Amount to deduct must be positive.")

    try:
        # users_collection
        # total_costs_collection

        # Atomically find the user and deduct credits if sufficient
        updated_user = users_collection.find_one_and_update(
            {"_id": ObjectId(user_id)},  # Only match on user_id without checking credits balance
            {"$inc": {"credits": -amount}},
            return_document=ReturnDocument.AFTER
        )
        
        # print(updated_user)
        # print(user_id)

        if not updated_user:
            return False, "User not found."

        # Prepare the transaction log
        transaction = {
            "user_id": user_id,
            "amount": amount,  # Storing as positive value
            "description": description,
            "transaction_type": transaction_type,
            "timestamp": datetime.utcnow()
        }

        # Insert the transaction log
        total_costs_collection.insert_one(transaction)

        # print(f"Successfully deducted {amount} credits from user '{user_id}'.")
        # print(f"New balance: {updated_user['credits']} credits.")
        
        return True, ""

    except PyMongoError as e:
        # Handle MongoDB-related errors
        print(f"MongoDB error occurred: {e}")
        error_msg = f"Transaction failed for user {user_id}: {e}"
        logger.error(error_msg)
        return False, error_msg
    
    except Exception as ex:
        # Handle other unforeseen errors
        print(f"An error occurred: {ex}")
        error_msg = f"Transaction failed for user {user_id}: {e}"
        logger.error(error_msg)
        return False, error_msg
    
def log_credit_usage(user_id, amount, description, transaction_type="credit_deduction"):
    """
    Deducts credits from a user and logs the transaction.

    Parameters:
    - user_id (str): The unique identifier of the user.
    - amount (float): The amount of credits to deduct. Must be positive.
    - description (str): A description for the transaction.
    - transaction_type (str): The type of transaction. Defaults to "credit_deduction".

    Raises:
    - ValueError: If the amount is not positive or if the user has insufficient credits.
    - PyMongoError: If there is an issue with the MongoDB operations.
    """
    if amount <= 0:
        raise ValueError("Amount to deduct must be positive.")

    try:
        # Prepare the transaction log
        transaction = {
            "user_id": user_id,
            "amount": amount,  # Storing as positive value
            "description": description,
            "transaction_type": transaction_type,
            "timestamp": datetime.utcnow()
        }

        # Insert the transaction log
        total_costs_collection.insert_one(transaction)
        
        return True, ""

    except PyMongoError as e:
        # Handle MongoDB-related errors
        print(f"MongoDB error occurred: {e}")
        error_msg = f"Transaction failed for user {user_id}: {e}"
        logger.error(error_msg)
        return False, error_msg
    
    except Exception as ex:
        # Handle other unforeseen errors
        print(f"An error occurred: {ex}")
        error_msg = f"Transaction failed for user {user_id}: {e}"
        logger.error(error_msg)
        return False, error_msg

def get_total_cost():
    """Retrieve the total cost used by all users."""
    total = total_costs_collection.find_one({})
    return total.get("total_cost", 0.0) if total else 0.0