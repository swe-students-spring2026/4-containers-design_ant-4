import shutil
import subprocess
import uuid
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from bson import ObjectId

from werkzeug.utils import secure_filename

from config import Config
from db.ops.item_ops import (
    create_item,
    get_items_by_fridge,
    update_item_name,
    delete_item,
)


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


def get_inventory_items(fridge_id):
    return get_items_by_fridge(fridge_id)


# def get_recent_uploads(user_id, limit=8):
#     db = get_db()
#     uploads = list(
#         db.uploads.find(
#             {"user_id": user_id},
#             sort=[("created_at", -1)],
#             limit=limit,
#         )
#     )
#     return uploads


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

    if os.name == "nt":
        candidate_python = ml_base_dir / "venv" / "Scripts" / "python.exe"
    else:
        candidate_python = ml_base_dir / "venv" / "bin" / "python"

    ml_python_path = candidate_python if candidate_python.exists() else Path(sys.executable)

    print("ML base dir:", ml_base_dir)
    print("ML script path:", ml_script_path)
    print("ML python path:", ml_python_path)
    print("ML script exists:", ml_script_path.exists())
    print("ML python exists:", Path(ml_python_path).exists())

    if not ml_script_path.exists():
        raise FileNotFoundError(f"ML script not found: {ml_script_path}")

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


def save_detection_results_to_db(fridge_id, json_path):
    with open(json_path, "r", encoding="utf-8") as file:
        detection_data = json.load(file)

    items_by_class = {}

    for image_result in detection_data.get("results", []):
        for detection in image_result.get("detections", []):
            class_name = detection.get("class_name", "unknown")
            confidence = detection.get("confidence", 0)

            if class_name not in items_by_class:
                items_by_class[class_name] = confidence
            else:
                if confidence > items_by_class[class_name]:
                    items_by_class[class_name] = confidence

    inserted_ids = []

    for class_name, confidence in items_by_class.items():
        item_id = create_item(
            fridge_id=fridge_id,
            item_name=class_name,
            item_added_date=None,
            item_expiry_date=None,
            item_confidence=confidence,
        )
        inserted_ids.append(item_id)

    return inserted_ids


def update_inventory_item_name(item_id, new_name):
    return update_item_name(item_id, new_name)


def soft_delete_inventory_item(item_id):
    return delete_item(item_id)
