from flask import Blueprint, redirect, render_template, request, url_for

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

TEST_FRIDGE_ID = "69e05e3ca223a7ad8b669446"

@main_bp.route("/")
def home():
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    items = get_inventory_items(TEST_FRIDGE_ID)
    return render_template("dashboard.html", items=items)


@main_bp.route("/upload", methods=["POST"])
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
    except Exception as exc:
        print("UPLOAD ERROR:", repr(exc))
        raise

    return redirect(url_for("main.dashboard"))


@main_bp.route("/items/<item_id>/edit", methods=["POST"])
def edit_item(item_id):
    new_name = request.form.get("item_name", "").strip()

    if new_name:
        update_inventory_item_name(item_id, new_name)

    return redirect(url_for("main.dashboard"))


@main_bp.route("/items/<item_id>/delete", methods=["POST"])
def delete_item(item_id):
    soft_delete_inventory_item(item_id)
    return redirect(url_for("main.dashboard"))
