from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from auth import authenticate_user, create_user
from services import (
    allowed_file,
    get_inventory_items,
    run_ml_detection,
    save_detection_results_to_db,
    save_uploaded_file,
    soft_delete_inventory_item,
    update_inventory_item_name,
)

main_bp = Blueprint("main", __name__)

# Temporary until current-user -> fridge_id wiring is implemented
TEST_FRIDGE_ID = "69e05e3ca223a7ad8b669446"


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
    items = get_inventory_items(TEST_FRIDGE_ID)
    return render_template("dashboard.html", items=items)


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

    _, saved_path = save_uploaded_file(image_file)

    try:
        _, _, json_path = run_ml_detection(saved_path)
        save_detection_results_to_db(TEST_FRIDGE_ID, json_path)
        flash("Image processed successfully.", "success")
    except Exception as exc:
        print("UPLOAD ERROR:", repr(exc))
        raise

    return redirect(url_for("main.dashboard"))


@main_bp.route("/items/<item_id>/edit", methods=["POST"])
@login_required
def edit_item(item_id):
    new_name = request.form.get("item_name", "").strip()

    if new_name:
        update_inventory_item_name(item_id, new_name)

    return redirect(url_for("main.dashboard"))


@main_bp.route("/items/<item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    soft_delete_inventory_item(item_id)
    return redirect(url_for("main.dashboard"))