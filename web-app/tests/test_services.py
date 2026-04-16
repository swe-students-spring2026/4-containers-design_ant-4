import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_get_inventory_items():
    with patch("services.get_items_by_fridge") as mock_get_items:
        mock_get_items.return_value = [{"item_name": "milk"}]

        result = get_inventory_items("fake_fridge_id")

        assert result == [{"item_name": "milk"}]
        mock_get_items.assert_called_once_with("fake_fridge_id")


def test_update_inventory_item_name():
    with patch("services.update_item_name") as mock_update:
        update_inventory_item_name("fake_item_id", "green cucumber")
        mock_update.assert_called_once_with("fake_item_id", "green cucumber")


def test_soft_delete_inventory_item():
    with patch("services.delete_item") as mock_delete:
        soft_delete_inventory_item("fake_item_id")
        mock_delete.assert_called_once_with("fake_item_id")


def test_save_detection_results_to_db():
    temp_dir = Path(tempfile.mkdtemp())
    json_path = temp_dir / "detection_results.json"
    json_path.write_text(
        """
        {
          "results": [
            {
              "filename": "fridge.png",
              "detections": [
                {
                  "class_name": "tomato",
                  "confidence": 0.4,
                  "bbox_xyxy": [1, 2, 3, 4]
                },
                {
                  "class_name": "tomato",
                  "confidence": 0.8,
                  "bbox_xyxy": [5, 6, 7, 8]
                },
                {
                  "class_name": "cucumber",
                  "confidence": 0.5,
                  "bbox_xyxy": [9, 10, 11, 12]
                }
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    with patch("services.create_item") as mock_create_item:
        mock_create_item.side_effect = ["id1", "id2"]

        inserted_ids = save_detection_results_to_db("fake_fridge_id", json_path)

        assert inserted_ids == ["id1", "id2"]
        assert mock_create_item.call_count == 2

        mock_create_item.assert_any_call(
            fridge_id="fake_fridge_id",
            item_name="tomato",
            item_added_date=None,
            item_expiry_date=None,
            item_confidence=0.8,
        )
        mock_create_item.assert_any_call(
            fridge_id="fake_fridge_id",
            item_name="cucumber",
            item_added_date=None,
            item_expiry_date=None,
            item_confidence=0.5,
        )


# Old database-coupled tests from the callback/uploads/inventory_items design
# are obsolete after refactoring services.py to use item_ops directly.
# Keep them commented for reference.

# def test_update_inventory_item_name():
#     fake_db = MagicMock()
#
#     with patch("services.get_db", return_value=fake_db):
#         item_id = str(ObjectId())
#         update_inventory_item_name(item_id, "green cucumber")
#
#         fake_db.inventory_items.update_one.assert_called_once()
#         args, kwargs = fake_db.inventory_items.update_one.call_args
#         assert args[0]["_id"] == ObjectId(item_id)
#         assert args[1]["$set"]["display_name"] == "green cucumber"
#         assert isinstance(args[1]["$set"]["updated_at"], datetime)


# def test_soft_delete_inventory_item():
#     fake_db = MagicMock()
#
#     with patch("services.get_db", return_value=fake_db):
#         item_id = str(ObjectId())
#         soft_delete_inventory_item(item_id)
#
#         fake_db.inventory_items.update_one.assert_called_once()
#         args, kwargs = fake_db.inventory_items.update_one.call_args
#         assert args[0]["_id"] == ObjectId(item_id)
#         assert args[1]["$set"]["is_deleted"] is True
#         assert isinstance(args[1]["$set"]["updated_at"], datetime)


# def test_save_detection_results_to_db():
#     fake_db = MagicMock()
#     fake_db.ml_results.find_one.return_value = {
#         "task_id": "task123",
#         "filename": "fridge.png",
#         "detection_json": {
#             "total_detections": 3,
#             "results": [
#                 {
#                     "filename": "fridge.png",
#                     "detections": [
#                         {
#                             "class_name": "tomato",
#                             "confidence": 0.4,
#                             "bbox_xyxy": [1, 2, 3, 4],
#                         },
#                         {
#                             "class_name": "tomato",
#                             "confidence": 0.8,
#                             "bbox_xyxy": [5, 6, 7, 8],
#                         },
#                         {
#                             "class_name": "cucumber",
#                             "confidence": 0.5,
#                             "bbox_xyxy": [9, 10, 11, 12],
#                         },
#                     ],
#                 }
#             ],
#         },
#     }
#
#     with patch("services.get_db", return_value=fake_db):
#         save_detection_results_to_db("task123")
#
#         fake_db.uploads.update_one.assert_called_once()
#         fake_db.inventory_items.insert_many.assert_called_once()