from bson import ObjectId
from db.mongo import items_collection


def create_item(fridge_id, item_name, item_added_date, item_expiry_date, item_confidence):
    item_doc = {
        "fridge_id": fridge_id,
        "item_name": item_name,
        "item_added_date": item_added_date,
        "item_expiry_date": item_expiry_date,
        "item_confidence": item_confidence,
    }

    result = items_collection.insert_one(item_doc)
    return result.inserted_id


def get_items_by_fridge(fridge_id):
    return list(items_collection.find({"fridge_id": fridge_id}))


def get_item_by_id(item_id):
    return items_collection.find_one({"_id": ObjectId(item_id)})


def update_item_name(item_id, new_name):
    return items_collection.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"item_name": new_name}},
    )


def delete_item(item_id):
    return items_collection.delete_one({"_id": ObjectId(item_id)})


def update_item_expiry_date(item_id, new_expiry_date):
    return items_collection.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"item_expiry_date": new_expiry_date}},
    )