# pylint: disable=protected-access
import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import ml_client_service


def test_run_stores_results_and_notifies_web_app(tmp_path):
    fake_db = MagicMock()
    detection_json = {"results": [], "total_detections": 0}

    def fake_run_detection(args):
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_results.json").write_text(
            json.dumps(detection_json), encoding="utf-8"
        )

    with patch.object(ml_client_service.Config, "RUNTIME_FOLDER", tmp_path), patch(
        "ml_client_service.run_detection", side_effect=fake_run_detection
    ), patch.object(ml_client_service, "db", fake_db), patch(
        "ml_client_service.requests.post"
    ) as mock_post:
        ml_client_service._run("task-1", "fridge.png", b"image-bytes")

    assert (tmp_path / "task-1" / "input" / "fridge.png").read_bytes() == b"image-bytes"

    inserted_document = fake_db.ml_results.insert_one.call_args.args[0]
    assert inserted_document["task_id"] == "task-1"
    assert inserted_document["filename"] == "fridge.png"
    assert inserted_document["detection_json"] == detection_json
    assert "created_at" in inserted_document

    mock_post.assert_called_once_with(
        ml_client_service.Config.WEB_APP_CALLBACK_URL,
        json={"task_id": "task-1", "status": "done"},
        timeout=10,
    )


def test_run_posts_failed_callback_when_detection_raises(tmp_path):
    fake_db = MagicMock()

    with patch.object(ml_client_service.Config, "RUNTIME_FOLDER", tmp_path), patch(
        "ml_client_service.run_detection", side_effect=RuntimeError("boom")
    ), patch.object(ml_client_service, "db", fake_db), patch(
        "ml_client_service.requests.post"
    ) as mock_post:
        ml_client_service._run("task-2", "fridge.png", b"image-bytes")

    fake_db.ml_results.insert_one.assert_not_called()
    mock_post.assert_called_once_with(
        ml_client_service.Config.WEB_APP_CALLBACK_URL,
        json={"task_id": "task-2", "status": "failed", "error": "boom"},
        timeout=10,
    )


def test_run_posts_failed_callback_when_json_is_invalid(tmp_path):
    fake_db = MagicMock()

    def fake_run_detection(args):
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_results.json").write_text(
            "{not-valid-json", encoding="utf-8"
        )

    with patch.object(ml_client_service.Config, "RUNTIME_FOLDER", tmp_path), patch(
        "ml_client_service.run_detection", side_effect=fake_run_detection
    ), patch.object(ml_client_service, "db", fake_db), patch(
        "ml_client_service.requests.post"
    ) as mock_post:
        ml_client_service._run("task-3", "fridge.png", b"image-bytes")

    fake_db.ml_results.insert_one.assert_not_called()
    callback_payload = mock_post.call_args.kwargs["json"]
    assert callback_payload["task_id"] == "task-3"
    assert callback_payload["status"] == "failed"
    assert "Expecting property name enclosed in double quotes" in callback_payload["error"]


def test_receive_task_starts_background_thread_and_returns_accepted():
    thread_instance = MagicMock()
    client = ml_client_service.app.test_client()
    payload = {
        "task_id": "task-4",
        "filename": "fridge.png",
        "image_b64": base64.b64encode(b"image-bytes").decode(),
    }

    with patch("ml_client_service.threading.Thread", return_value=thread_instance) as mock_thread:
        response = client.post("/task", json=payload)

    assert response.status_code == 202
    assert response.get_json() == {"task_id": "task-4"}
    mock_thread.assert_called_once_with(
        target=ml_client_service._run,
        args=("task-4", "fridge.png", b"image-bytes"),
        daemon=True,
    )
    thread_instance.start.assert_called_once()
