import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from auth import User


@pytest.fixture
def app():
    temp_upload_dir = tempfile.mkdtemp()
    temp_runtime_dir = tempfile.mkdtemp()

    app = create_app(
        {
            "TESTING": True,
            "UPLOAD_FOLDER": temp_upload_dir,
            "RUNTIME_FOLDER": temp_runtime_dir,
        }
    )

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user_document():
    return {"_id": ObjectId(), "email": "chef@example.com"}


@pytest.fixture
def logged_in_client(client, user_document):
    user = User(user_document)

    with patch("app.get_user_by_id", return_value=user):
        with client.session_transaction() as session:
            session["_user_id"] = user.get_id()
            session["_fresh"] = True

        yield client
