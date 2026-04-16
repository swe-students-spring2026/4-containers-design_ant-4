from datetime import datetime

from bson import ObjectId
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db


class User(UserMixin):
    def __init__(self, document):
        self.id = str(document["_id"])
        self.email = document["email"]


def normalize_email(email):
    return email.strip().lower()


def get_user_by_id(user_id):
    try:
        document = get_db().users.find_one({"_id": ObjectId(user_id)})
    except (TypeError, ValueError):
        return None

    if not document:
        return None

    return User(document)


def create_user(email, password):
    normalized_email = normalize_email(email)
    if not normalized_email or not password:
        return None, "Email and password are required."

    db = get_db()
    if db.users.find_one({"email": normalized_email}):
        return None, "An account with that email already exists."

    inserted = db.users.insert_one(
        {
            "email": normalized_email,
            "password_hash": generate_password_hash(password),
            "created_at": datetime.utcnow(),
        }
    )

    return User({"_id": inserted.inserted_id, "email": normalized_email}), None


def authenticate_user(email, password):
    normalized_email = normalize_email(email)
    document = get_db().users.find_one({"email": normalized_email})

    if not document:
        return None

    if not check_password_hash(document["password_hash"], password):
        return None

    return User(document)
