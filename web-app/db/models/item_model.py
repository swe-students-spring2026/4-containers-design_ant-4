def make_item(fridge_id, item_name, item_added_date, item_expiry_date, item_confidence):
    return {
        "fridge_id": fridge_id,
        "item_name": item_name,
        "item_added_date": item_added_date,
        "item_expiry_date": item_expiry_date,
        "item_confidence": item_confidence,
    }
