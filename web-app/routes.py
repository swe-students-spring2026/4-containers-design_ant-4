import base64
import uuid
from datetime import datetime
from urllib.parse import urlsplit

import requests
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from auth import authenticate_user, create_user
from config import Config
from db import get_db
from services import (
    allowed_file,
    get_inventory_items,
    get_recent_uploads,
    save_detection_results_to_db,
    save_uploaded_file,
    soft_delete_inventory_item,
    update_inventory_item_name,
)

main_bp = Blueprint("main", __name__)


def _get_safe_redirect_target():
    next_url = request.args.get("next") or request.form.get("next")
    if not next_url:
        return None

    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc or not next_url.startswith("/"):
        return None

    return next_url


@main_bp.route("/")
def home():
    return render_template("index.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    next_url = _get_safe_redirect_target()
    if request.method == "POST":
        user = authenticate_user(
            request.form.get("email", ""), request.form.get("password", "")
        )
        if user:
            login_user(user)
            flash("Signed in successfully.", "success")
            return redirect(next_url or url_for("main.dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html", next_url=next_url or "")


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    next_url = _get_safe_redirect_target()
    if request.method == "POST":
        user, error_message = create_user(
            request.form.get("email", ""), request.form.get("password", "")
        )
        if user:
            login_user(user)
            flash("Account created.", "success")
            return redirect(next_url or url_for("main.dashboard"))

        flash(error_message, "error")

    return render_template("register.html", next_url=next_url or "")


@main_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("main.home"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    items = get_inventory_items(current_user.get_id())
    return render_template("dashboard.html", items=items)


@main_bp.route("/scans")
@login_required
def scans():
    recent_uploads = get_recent_uploads(current_user.get_id())
    pending_uploads = sum(
        1 for upload in recent_uploads if upload.get("status") == "pending"
    )
    return render_template(
        "scans.html",
        recent_uploads=recent_uploads,
        pending_uploads=pending_uploads,
    )


@main_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    if "image" not in request.files:
        return "No file part in request", 400

    image_file = request.files["image"]
    if image_file.filename == "":
        return "No selected file", 400
    if not allowed_file(image_file.filename):
        return "Unsupported file type", 400

    task_id = uuid.uuid4().hex
    saved_filename, saved_path = save_uploaded_file(image_file)

    get_db().uploads.insert_one(
        {
            "task_id": task_id,
            "filename": saved_filename,
            "user_id": current_user.get_id(),
            "status": "pending",
            "created_at": datetime.utcnow(),
        }
    )

    with open(saved_path, "rb") as fh:
        image_b64 = base64.b64encode(fh.read()).decode()

    requests.post(
        f"{Config.ML_SERVICE_URL}/task",
        json={"task_id": task_id, "filename": saved_filename, "image_b64": image_b64},
        timeout=10,
    )
    flash(
        "Image queued for analysis. Processing can take a bit; the scan queue will update automatically.",
        "success",
    )
    return redirect(url_for("main.scans"))


@main_bp.route("/ml-callback", methods=["POST"])
def ml_callback():
    payload = request.get_json(force=True)
    task_id = payload["task_id"]
    if payload.get("status") == "done":
        save_detection_results_to_db(task_id)
    else:
        get_db().uploads.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "error": payload.get("error")}},
        )
    return "", 200


@main_bp.route("/items/<item_id>/edit", methods=["POST"])
@login_required
def edit_item(item_id):
    new_name = request.form.get("display_name", "").strip()

    if new_name:
        update_inventory_item_name(item_id, new_name, current_user.get_id())

    return redirect(url_for("main.dashboard"))


@main_bp.route("/items/<item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    soft_delete_inventory_item(item_id, current_user.get_id())
    return redirect(url_for("main.dashboard"))
