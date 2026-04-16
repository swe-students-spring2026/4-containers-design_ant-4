from unittest.mock import MagicMock, patch

from bson import ObjectId
from werkzeug.security import check_password_hash

from auth import (
    User,
    authenticate_user,
    create_user,
    get_user_by_id,
    normalize_email,
)


def test_normalize_email_strips_and_lowercases():
    assert normalize_email("  Chef@Example.COM  ") == "chef@example.com"


def test_get_user_by_id_returns_user():
    user_id = ObjectId()
    with patch("auth.get_db") as mock_get_db:
        mock_get_db.return_value.users.find_one.return_value = {
            "_id": user_id,
            "email": "chef@example.com",
        }

        user = get_user_by_id(str(user_id))

        assert isinstance(user, User)
        assert user.get_id() == str(user_id)
        assert user.email == "chef@example.com"


def test_get_user_by_id_returns_none_for_missing_document():
    with patch("auth.get_db") as mock_get_db:
        mock_get_db.return_value.users.find_one.return_value = None

        assert get_user_by_id(str(ObjectId())) is None


def test_create_user_requires_email_and_password():
    assert create_user("", "secret-pass") == (
        None,
        "Email and password are required.",
    )
    assert create_user("chef@example.com", "") == (
        None,
        "Email and password are required.",
    )


def test_create_user_rejects_duplicate_email():
    fake_db = MagicMock()
    fake_db.users.find_one.return_value = {"_id": ObjectId()}

    with patch("auth.get_db", return_value=fake_db):
        user, error_message = create_user("  Chef@Example.COM  ", "secret-pass")

    assert user is None
    assert error_message == "An account with that email already exists."
    fake_db.users.find_one.assert_called_once_with({"email": "chef@example.com"})


def test_create_user_hashes_password_and_returns_user():
    inserted_id = ObjectId()
    fake_db = MagicMock()
    fake_db.users.find_one.return_value = None
    fake_db.users.insert_one.return_value.inserted_id = inserted_id

    with patch("auth.get_db", return_value=fake_db):
        user, error_message = create_user("  Chef@Example.COM  ", "secret-pass")

    assert error_message is None
    assert isinstance(user, User)
    assert user.get_id() == str(inserted_id)
    assert user.email == "chef@example.com"

    inserted_document = fake_db.users.insert_one.call_args.args[0]
    assert inserted_document["email"] == "chef@example.com"
    assert check_password_hash(inserted_document["password_hash"], "secret-pass")
    assert "created_at" in inserted_document


def test_authenticate_user_returns_none_when_user_missing():
    fake_db = MagicMock()
    fake_db.users.find_one.return_value = None

    with patch("auth.get_db", return_value=fake_db):
        assert authenticate_user("chef@example.com", "secret-pass") is None

    fake_db.users.find_one.assert_called_once_with({"email": "chef@example.com"})


def test_authenticate_user_returns_none_for_bad_password():
    fake_db = MagicMock()
    fake_db.users.find_one.return_value = {
        "_id": ObjectId(),
        "email": "chef@example.com",
        "password_hash": "not-the-right-hash",
    }

    with patch("auth.get_db", return_value=fake_db), patch(
        "auth.check_password_hash", return_value=False
    ) as mock_check_password_hash:
        assert authenticate_user("  Chef@Example.COM  ", "wrong-pass") is None

    mock_check_password_hash.assert_called_once_with("not-the-right-hash", "wrong-pass")


def test_authenticate_user_returns_user_on_success():
    user_id = ObjectId()
    fake_db = MagicMock()
    fake_db.users.find_one.return_value = {
        "_id": user_id,
        "email": "chef@example.com",
        "password_hash": "hashed-pass",
    }

    with patch("auth.get_db", return_value=fake_db), patch(
        "auth.check_password_hash", return_value=True
    ):
        user = authenticate_user("chef@example.com", "secret-pass")

    assert isinstance(user, User)
    assert user.get_id() == str(user_id)
    assert user.email == "chef@example.com"
