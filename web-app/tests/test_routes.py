from io import BytesIO
from unittest.mock import MagicMock, patch

from auth import User
from routes import _get_safe_redirect_target


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Fridge Food Detector" in response.data
    assert b"Log In" in response.data


def test_login_page_get(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Log In" in response.data
    assert b"Enter Dashboard" in response.data


def test_register_page_get(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Register" in response.data
    assert b"Create Account" in response.data


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


def test_login_route_failure(client):
    with patch("routes.authenticate_user", return_value=None):
        response = client.post(
            "/login",
            data={"email": "chef@example.com", "password": "wrong-pass"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Invalid email or password." in response.data

        with client.session_transaction() as session:
            assert "_user_id" not in session


def test_login_route_ignores_unsafe_next_redirect(client, user_document):
    fake_user = User(user_document)

    with patch("routes.authenticate_user", return_value=fake_user):
        response = client.post(
            "/login?next=https://evil.com",
            data={"email": "chef@example.com", "password": "secret-pass"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_route_honors_safe_next_redirect(client, user_document):
    fake_user = User(user_document)

    with patch("routes.authenticate_user", return_value=fake_user):
        response = client.post(
            "/login?next=/scans",
            data={"email": "chef@example.com", "password": "secret-pass"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/scans")


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


def test_register_route_failure(client):
    with patch(
        "routes.create_user", return_value=(None, "An account with that email already exists.")
    ):
        response = client.post(
            "/register",
            data={"email": "chef@example.com", "password": "secret-pass"},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"An account with that email already exists." in response.data


def test_logout_route(logged_in_client):
    response = logged_in_client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"Signed out." in response.data

    with logged_in_client.session_transaction() as session:
        assert "_user_id" not in session


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


def test_get_safe_redirect_target_allows_internal_path(app):
    with app.test_request_context("/login", query_string={"next": "/scans"}):
        assert _get_safe_redirect_target() == "/scans"


def test_get_safe_redirect_target_uses_form_value_when_query_missing(app):
    with app.test_request_context("/login", method="POST", data={"next": "/dashboard"}):
        assert _get_safe_redirect_target() == "/dashboard"


def test_get_safe_redirect_target_rejects_external_targets(app):
    unsafe_targets = [
        "https://evil.com",
        "//evil.com",
        "http://evil.com/path",
        "javascript:alert(1)",
        "dashboard",
    ]

    for target in unsafe_targets:
        with app.test_request_context("/login", query_string={"next": target}):
            assert _get_safe_redirect_target() is None


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
