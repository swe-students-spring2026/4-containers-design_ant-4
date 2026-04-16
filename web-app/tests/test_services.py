import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from bson import ObjectId
from werkzeug.datastructures import FileStorage

from services import (
    allowed_file,
    create_runtime_folders,
    get_inventory_items,
    run_ml_detection,
    save_detection_results_to_db,
    save_uploaded_file,
    soft_delete_inventory_item,
    update_inventory_item_name,
)


def test_allowed_file_accepts_valid_extensions():
    assert allowed_file("test.png") is True
    assert allowed_file("test.jpg") is True
    assert allowed_file("test.jpeg") is True
    assert allowed_file("test.webp") is True


def test_allowed_file_rejects_invalid_extensions():
    assert allowed_file("test.txt") is False
    assert allowed_file("test.pdf") is False
    assert allowed_file("test") is False


def test_save_uploaded_file(app):
    file_storage = FileStorage(
        stream=BytesIO(b"fake image content"),
        filename="fridge.png",
        content_type="image/png",
    )

    saved_filename, saved_path = save_uploaded_file(file_storage)

    assert saved_filename.endswith("_fridge.png")
    assert Path(saved_path).exists()


def test_create_runtime_folders():
    task_id = "test_task_id"

    with patch("services.Config.RUNTIME_FOLDER", Path(tempfile.mkdtemp())):
        task_dir, input_dir, output_dir = create_runtime_folders(task_id)

        assert task_dir.exists()
        assert input_dir.exists()
        assert output_dir.exists()


def test_get_inventory_items_filters_by_user():
    fake_db = MagicMock()

    with patch("services.get_db", return_value=fake_db):
        get_inventory_items("user-1")

        fake_db.inventory_items.find.assert_called_once_with(
            {"is_deleted": False, "user_id": "user-1"},
            sort=[("created_at", -1)],
        )


def test_run_ml_detection_success():
    temp_dir = Path(tempfile.mkdtemp())
    uploaded_file = temp_dir / "fridge.png"
    uploaded_file.write_bytes(b"fake image")

    fake_output_dir = temp_dir / "output"
    fake_output_dir.mkdir()
    fake_json = fake_output_dir / "detection_results.json"
    fake_json.write_text("{}")

    with patch("services.create_runtime_folders") as mock_create_runtime_folders, patch(
        "services.subprocess.run"
    ) as mock_run, patch("services.shutil.copy") as mock_copy:
        mock_create_runtime_folders.return_value = (
            temp_dir / "task",
            temp_dir / "input",
            fake_output_dir,
        )
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        task_id, output_dir, json_path = run_ml_detection(uploaded_file)

        assert output_dir == fake_output_dir
        assert json_path == fake_json
        mock_copy.assert_called_once()
        mock_run.assert_called_once()


def test_update_inventory_item_name():
    fake_db = MagicMock()

    with patch("services.get_db", return_value=fake_db):
        item_id = str(ObjectId())
        update_inventory_item_name(item_id, "green cucumber", "user-1")

        fake_db.inventory_items.update_one.assert_called_once()
        args, kwargs = fake_db.inventory_items.update_one.call_args
        assert args[0]["_id"] == ObjectId(item_id)
        assert args[0]["user_id"] == "user-1"
        assert args[1]["$set"]["display_name"] == "green cucumber"
        assert isinstance(args[1]["$set"]["updated_at"], datetime)


def test_soft_delete_inventory_item():
    fake_db = MagicMock()

    with patch("services.get_db", return_value=fake_db):
        item_id = str(ObjectId())
        soft_delete_inventory_item(item_id, "user-1")

        fake_db.inventory_items.update_one.assert_called_once()
        args, kwargs = fake_db.inventory_items.update_one.call_args
        assert args[0]["_id"] == ObjectId(item_id)
        assert args[0]["user_id"] == "user-1"
        assert args[1]["$set"]["is_deleted"] is True
        assert isinstance(args[1]["$set"]["updated_at"], datetime)


def test_save_detection_results_to_db():
    fake_db = MagicMock()
    fake_db.ml_results.find_one.return_value = {
        "task_id": "task123",
        "filename": "fridge.png",
        "detection_json": {
            "total_detections": 3,
            "results": [
                {
                    "filename": "fridge.png",
                    "detections": [
                        {
                            "class_name": "tomato",
                            "confidence": 0.4,
                            "bbox_xyxy": [1, 2, 3, 4],
                        },
                        {
                            "class_name": "tomato",
                            "confidence": 0.8,
                            "bbox_xyxy": [5, 6, 7, 8],
                        },
                        {
                            "class_name": "cucumber",
                            "confidence": 0.5,
                            "bbox_xyxy": [9, 10, 11, 12],
                        },
                    ],
                }
            ],
        },
    }
    fake_db.uploads.find_one.return_value = {"task_id": "task123", "user_id": "user-1"}

    with patch("services.get_db", return_value=fake_db):
        save_detection_results_to_db("task123")

        fake_db.uploads.update_one.assert_called_once()
        fake_db.inventory_items.insert_many.assert_called_once()

        inserted_items = fake_db.inventory_items.insert_many.call_args[0][0]
        assert len(inserted_items) == 2

        names = {item["original_name"] for item in inserted_items}
        assert names == {"tomato", "cucumber"}

        tomato_item = next(
            item for item in inserted_items if item["original_name"] == "tomato"
        )
        assert tomato_item["confidence"] == 0.8
        assert all(item["user_id"] == "user-1" for item in inserted_items)
