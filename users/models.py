import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Connect to MongoDB
mongo_uri = os.getenv("MONGO_URI")
mongo_db_name = os.getenv("MONGO_DB_NAME")

client = MongoClient(mongo_uri)
db = client[mongo_db_name]
users = db["users"]
# Add at the top
otp_codes = db["otp_codes"]

# Ensure TTL index exists (run once or during app startup)
otp_codes.create_index("created_at", expireAfterSeconds=300)

def save_otp(email, hashed_otp):
    otp_entry = {
        "email": email,
        "otp": hashed_otp,
        "used": False,
        "created_at": datetime.utcnow()
    }
    otp_codes.insert_one(otp_entry)

def get_latest_otp(email):
    return otp_codes.find_one({"email": email, "used": False}, sort=[("created_at", -1)])

def mark_otp_used(email):
    otp_codes.update_many({"email": email, "used": False}, {"$set": {"used": True}})


def create_user(email, hashed_pw, name, mobile, organization, organization_type, country):
    user = {
        "email": email,
        "password": hashed_pw,
        "name": name,
        "mobile": mobile,
        "organization": organization,
        "organization_type": organization_type,
        "country": country,
        "created_at": datetime.utcnow(),
        "trial_ends_at": datetime.utcnow() + timedelta(days=5),
        "paid_ends_at": None,
        "is_verified": False
    }
    print("User to insert:", user)
    try:
        result = users.insert_one(user)
        print("Inserted ID:", result.inserted_id)
        return user
    except Exception as e:
        print("Error inserting user:", str(e))
        return None


def find_user(email):
    return users.find_one({"email": email})

def mark_user_verified(email):
    return update_user(email, {"is_verified": True})

def update_user(email, update_dict):
    """
    Updates a user document in the database by email.

    :param email: The user's email address.
    :param update_dict: A dictionary of fields to update.
    :return: The result of the update operation.
    """
    try:
        result = users.update_one(
            {"email": email},
            {"$set": update_dict}
        )
        return result
    except Exception as e:
        print(f"Error updating user ({email}): {str(e)}")
        return None
