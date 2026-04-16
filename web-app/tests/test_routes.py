from io import BytesIO
from unittest.mock import MagicMock, patch

from auth import User


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Fridge Food Detector" in response.data
    assert b"Log In" in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_page(logged_in_client, user_document):
    with patch("routes.get_inventory_items") as mock_get_inventory_items:
        mock_get_inventory_items.return_value = [
            {
                "display_name": "tomato",
                "original_name": "tomato",
                "confidence": 0.91,
                "image_filename": "fridge.png",
                "created_at": None,
                "_id": "fake-id-1",
            }
        ]

        response = logged_in_client.get("/dashboard")
        assert response.status_code == 200
        assert b"Inventory Dashboard" in response.data
        assert b"tomato" in response.data
        mock_get_inventory_items.assert_called_once_with(str(user_document["_id"]))


def test_scans_page(logged_in_client, user_document):
    with patch("routes.get_recent_uploads") as mock_get_recent_uploads:
        mock_get_recent_uploads.return_value = [
            {
                "filename": "fridge.png",
                "status": "pending",
                "created_at": None,
                "total_detections": 0,
            }
        ]

        response = logged_in_client.get("/scans")
        assert response.status_code == 200
        assert b"Scan Queue" in response.data
        assert b"fridge.png" in response.data
        mock_get_recent_uploads.assert_called_once_with(str(user_document["_id"]))


def test_login_route_success(client, user_document):
    fake_user = User(user_document)

    with patch("routes.authenticate_user", return_value=fake_user):
        response = client.post(
            "/login",
            data={"email": "chef@example.com", "password": "secret-pass"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        with client.session_transaction() as session:
            assert session["_user_id"] == fake_user.get_id()


def test_register_route_success(client, user_document):
    fake_user = User(user_document)

    with patch("routes.create_user", return_value=(fake_user, None)):
        response = client.post(
            "/register",
            data={"email": "chef@example.com", "password": "secret-pass"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")


def test_upload_route_success(logged_in_client, user_document):
    fake_db = MagicMock()
    with patch("routes.requests.post") as mock_post, patch(
        "routes.get_db", return_value=fake_db
    ):
        data = {"image": (BytesIO(b"fake image data"), "fridge.png")}
        response = logged_in_client.post(
            "/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/scans")
        fake_db.uploads.insert_one.assert_called_once()
        upload_document = fake_db.uploads.insert_one.call_args.args[0]
        assert upload_document["user_id"] == str(user_document["_id"])
        mock_post.assert_called_once()
        posted_json = mock_post.call_args.kwargs["json"]
        assert "task_id" in posted_json
        assert "image_b64" in posted_json
        assert posted_json["filename"].endswith("_fridge.png")


def test_upload_route_sets_processing_flash(logged_in_client):
    fake_db = MagicMock()

    with patch("routes.requests.post"), patch(
        "routes.get_db", return_value=fake_db
    ), patch(
        "routes.get_recent_uploads", return_value=[]
    ):
        response = logged_in_client.post(
            "/upload",
            data={"image": (BytesIO(b"fake image data"), "fridge.png")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Image queued for analysis" in response.data
    assert b"Scan Queue" in response.data


def test_ml_callback_done(client):
    fake_db = MagicMock()
    with patch("routes.get_db", return_value=fake_db), patch(
        "routes.save_detection_results_to_db"
    ) as mock_save:
        response = client.post(
            "/ml-callback",
            json={"task_id": "task123", "status": "done"},
        )
        assert response.status_code == 200
        mock_save.assert_called_once_with("task123")


def test_ml_callback_failed(client):
    fake_db = MagicMock()
    with patch("routes.get_db", return_value=fake_db):
        response = client.post(
            "/ml-callback",
            json={"task_id": "task123", "status": "failed", "error": "boom"},
        )
        assert response.status_code == 200
        fake_db.uploads.update_one.assert_called_once()


def test_upload_route_missing_file(client):
    response = client.post(
        "/upload",
        data={},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_upload_route_empty_filename(client):
    data = {
        "image": (BytesIO(b""), ""),
    }

    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_upload_route_invalid_extension(client):
    data = {
        "image": (BytesIO(b"fake data"), "bad.txt"),
    }

    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_upload_route_invalid_extension_when_logged_in(logged_in_client):
    data = {
        "image": (BytesIO(b"fake data"), "bad.txt"),
    }

    response = logged_in_client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Unsupported file type" in response.data


def test_edit_item_route(logged_in_client, user_document):
    with patch("routes.update_inventory_item_name") as mock_update:
        response = logged_in_client.post(
            "/items/1234567890abcdef12345678/edit",
            data={"display_name": "green cucumber"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_update.assert_called_once_with(
            "1234567890abcdef12345678",
            "green cucumber",
            str(user_document["_id"]),
        )


def test_delete_item_route(logged_in_client, user_document):
    with patch("routes.soft_delete_inventory_item") as mock_delete:
        response = logged_in_client.post(
            "/items/1234567890abcdef12345678/delete",
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_delete.assert_called_once_with(
            "1234567890abcdef12345678", str(user_document["_id"])
        )
