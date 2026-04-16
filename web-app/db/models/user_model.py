from bson import ObjectId


def make_user(user_name, user_email, user_password_hash, fridge_id):
    return {
        "user_name": user_name,
        "user_email": user_email,
        "user_password_hash": user_password_hash,
        "fridge_id": fridge_id,
    }
