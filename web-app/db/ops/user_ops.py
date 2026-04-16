from bson import ObjectId
from db.mongo import users_collection


def create_user(fridge_id, user_name, user_email, user_password_hash):
    user_doc = {
        "fridge_id": fridge_id,
        "user_name": user_name,
        "user_email": user_email,
        "user_password_hash": user_password_hash,
    }

    result = users_collection.insert_one(user_doc)
    return result.inserted_id


def get_user_by_id(user_id):
    return users_collection.find_one({"_id": ObjectId(user_id)})


def get_user_by_email(user_email):
    return users_collection.find_one({"user_email": user_email})


def get_users_by_fridge(fridge_id):
    return list(users_collection.find({"fridge_id": fridge_id}))