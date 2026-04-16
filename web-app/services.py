import shutil
import subprocess
import uuid
from datetime import datetime
from bson import ObjectId

from werkzeug.utils import secure_filename

from config import Config
from db import get_db


def allowed_file(filename):
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in Config.ALLOWED_EXTENSIONS


def save_uploaded_file(file_storage):
    original_filename = secure_filename(file_storage.filename)
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    save_path = Config.UPLOAD_FOLDER / unique_filename
    file_storage.save(save_path)
    return unique_filename, save_path


def get_inventory_items(user_id):
    db = get_db()
    items = list(
        db.inventory_items.find(
            {"is_deleted": False, "user_id": user_id},
            sort=[("created_at", -1)],
        )
    )
    return items


def create_runtime_folders(task_id):
    task_dir = Config.RUNTIME_FOLDER / task_id
    input_dir = task_dir / "input"
    output_dir = task_dir / "output"

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    return task_dir, input_dir, output_dir


def run_ml_detection(uploaded_file_path):
    task_id = uuid.uuid4().hex
    _, input_dir, output_dir = create_runtime_folders(task_id)

    runtime_input_path = input_dir / uploaded_file_path.name
    shutil.copy(uploaded_file_path, runtime_input_path)

    ml_base_dir = Config.BASE_DIR.parent / "machine-learning-client"
    ml_script_path = ml_base_dir / "food_detection.py"
    ml_python_path = ml_base_dir / "venv" / "bin" / "python"

    command = [
        str(ml_python_path),
        str(ml_script_path),
        "--input",
        str(input_dir),
        "--output",
        str(output_dir),
    ]

    result = subprocess.run(  # pylint: disable=subprocess-run-check
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ML detection failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    json_path = output_dir / "detection_results.json"
    if not json_path.exists():
        raise FileNotFoundError("detection_results.json was not generated.")

    return task_id, output_dir, json_path


def save_detection_results_to_db(task_id):
    db = get_db()

    raw = db.ml_results.find_one({"task_id": task_id})
    if not raw:
        return

    upload_record = db.uploads.find_one({"task_id": task_id})
    detection_data = raw["detection_json"]
    image_filename = raw.get("filename")
    user_id = upload_record.get("user_id") if upload_record else None

    db.uploads.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "status": "done",
                "total_detections": detection_data.get("total_detections", 0),
            }
        },
    )

    items_by_class = {}

    for image_result in detection_data.get("results", []):
        for detection in image_result.get("detections", []):
            class_name = detection.get("class_name", "unknown")
            confidence = detection.get("confidence", 0)

            item_data = {
                "display_name": class_name,
                "original_name": class_name,
                "confidence": confidence,
                "bbox_xyxy": detection.get("bbox_xyxy", []),
                "image_filename": image_result.get("filename", image_filename),
                "task_id": task_id,
                "user_id": user_id,
                "is_deleted": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            # keep only the highest-confidence detection for each class
            if class_name not in items_by_class:
                items_by_class[class_name] = item_data
            else:
                if confidence > items_by_class[class_name]["confidence"]:
                    items_by_class[class_name] = item_data

    items_to_insert = [item for item in items_by_class.values() if item.get("user_id")]

    if items_to_insert:
        db.inventory_items.insert_many(items_to_insert)


def update_inventory_item_name(item_id, new_name, user_id):
    db = get_db()
    db.inventory_items.update_one(
        {"_id": ObjectId(item_id), "user_id": user_id},
        {
            "$set": {
                "display_name": new_name,
                "updated_at": datetime.utcnow(),
            }
        },
    )


def soft_delete_inventory_item(item_id, user_id):
    db = get_db()
    db.inventory_items.update_one(
        {"_id": ObjectId(item_id), "user_id": user_id},
        {
            "$set": {
                "is_deleted": True,
                "updated_at": datetime.utcnow(),
            }
        },
    )
