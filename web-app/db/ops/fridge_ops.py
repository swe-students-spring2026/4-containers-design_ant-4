from bson import ObjectId
from db.mongo import fridges_collection


def create_fridge():
    fridge_doc = {
    }

    result = fridges_collection.insert_one(fridge_doc)
    return result.inserted_id


def get_fridge_by_id(fridge_id):
    return fridges_collection.find_one({"_id": ObjectId(fridge_id)})

