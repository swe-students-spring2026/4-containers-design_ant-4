from io import BytesIO
from pathlib import Path
from unittest.mock import patch


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Fridge Food Detector" in response.data


def test_dashboard_page(client):
    with patch("routes.get_inventory_items") as mock_get_inventory_items:
        mock_get_inventory_items.return_value = [
            {
                "item_name": "tomato",
                "item_confidence": 0.91,
                "item_added_date": None,
                "item_expiry_date": None,
                "_id": "fake-id-1",
            }
        ]

        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Inventory Dashboard" in response.data
        assert b"tomato" in response.data


def test_upload_route_success(client):
    with patch("routes.save_uploaded_file") as mock_save_uploaded_file, patch(
        "routes.run_ml_detection"
    ) as mock_run_ml_detection, patch(
        "routes.save_detection_results_to_db"
    ) as mock_save_detection_results:
        mock_save_uploaded_file.return_value = (
            "abc_fridge.png",
            Path("/fake/upload/fridge.png"),
        )
        mock_run_ml_detection.return_value = (
            "fake-task-id",
            Path("/fake/output"),
            Path("/fake/output/detection_results.json"),
        )
        mock_save_detection_results.return_value = ["item1", "item2"]

        data = {"image": (BytesIO(b"fake image data"), "fridge.png")}
        response = client.post(
            "/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_save_uploaded_file.assert_called_once()
        mock_run_ml_detection.assert_called_once()
        mock_save_detection_results.assert_called_once()


# Old callback-based tests are obsolete after switching to the
# local sync flow:
# - requests.post to ML service
# - uploads collection
# - /ml-callback route
#
# Keep them commented for reference only.

# def test_ml_callback_done(client):
#     fake_db = MagicMock()
#     with patch("routes.get_db", return_value=fake_db), patch(
#         "routes.save_detection_results_to_db"
#     ) as mock_save:
#         response = client.post(
#             "/ml-callback",
#             json={"task_id": "task123", "status": "done"},
#         )
#         assert response.status_code == 200
#         mock_save.assert_called_once_with("task123")


# def test_ml_callback_failed(client):
#     fake_db = MagicMock()
#     with patch("routes.get_db", return_value=fake_db):
#         response = client.post(
#             "/ml-callback",
#             json={"task_id": "task123", "status": "failed", "error": "boom"},
#         )
#         assert response.status_code == 200
#         fake_db.uploads.update_one.assert_called_once()


def test_upload_route_missing_file(client):
    response = client.post(
        "/upload",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"No file part in request" in response.data


def test_upload_route_empty_filename(client):
    data = {
        "image": (BytesIO(b""), ""),
    }

    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"No selected file" in response.data


def test_upload_route_invalid_extension(client):
    data = {
        "image": (BytesIO(b"fake data"), "bad.txt"),
    }

    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Unsupported file type" in response.data


def test_edit_item_route(client):
    with patch("routes.update_inventory_item_name") as mock_update:
        response = client.post(
            "/items/1234567890abcdef12345678/edit",
            data={"item_name": "green cucumber"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_update.assert_called_once_with(
            "1234567890abcdef12345678", "green cucumber"
        )


def test_delete_item_route(client):
    with patch("routes.soft_delete_inventory_item") as mock_delete:
        response = client.post(
            "/items/1234567890abcdef12345678/delete",
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_delete.assert_called_once_with("1234567890abcdef12345678")