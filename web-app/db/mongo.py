import os
from pymongo import MongoClient


def get_database():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    db_name = os.getenv("MONGO_DB_NAME", "fridge_app_db")

    client = MongoClient(mongo_uri)
    return client[db_name]


db = get_database()

users_collection = db["users"]
fridges_collection = db["fridges"]
items_collection = db["items"]

if __name__ == "__main__":
    print("Connected to database:", db.name)
    print("Collections ready: users, fridges, items")
