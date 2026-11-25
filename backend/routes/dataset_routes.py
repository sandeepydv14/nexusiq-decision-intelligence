from flask import Blueprint, jsonify, request

from database.db import get_dataset, list_datasets
from services.dataset_manager import (
    create_demo_dataset,
    delete_dataset,
    get_paginated_preview,
    load_working_df,
    save_uploaded_dataset,
    switch_excel_sheet,
)
from services.quality import analyze_data_quality

dataset_bp = Blueprint("datasets", __name__, url_prefix="/api/datasets")


@dataset_bp.route("", methods=["GET"])
def api_list_datasets():
    return jsonify({"datasets": list_datasets()})


@dataset_bp.route("/upload", methods=["POST"])
def api_upload_dataset():
    if "file" not in request.files:
        return jsonify({"error": "No file part provided in request."}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "No file selected."}), 400
    custom_name = request.form.get("name")
    try:
        ds = save_uploaded_dataset(f, custom_name=custom_name)
        df = load_working_df(ds["id"])
        qual = analyze_data_quality(df)
        from database.db import update_dataset_stats
        update_dataset_stats(ds["id"], ds["row_count"], ds["col_count"], quality_score=qual["quality_score"])
        ds = get_dataset(ds["id"])
        return jsonify({"dataset": ds}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Upload failed: {exc}"}), 500


@dataset_bp.route("/demo", methods=["POST"])
def api_load_demo():
    try:
        ds = create_demo_dataset()
        if ds.get("quality_score") is None:
            df = load_working_df(ds["id"])
            qual = analyze_data_quality(df)
            from database.db import update_dataset_stats
            update_dataset_stats(ds["id"], ds["row_count"], ds["col_count"], quality_score=qual["quality_score"])
            ds = get_dataset(ds["id"])
        return jsonify({"dataset": ds}), 200
    except Exception as exc:
        return jsonify({"error": f"Failed to load demo dataset: {exc}"}), 500


@dataset_bp.route("/<dataset_id>", methods=["GET"])
def api_get_dataset(dataset_id: str):
    ds = get_dataset(dataset_id)
    if not ds:
        return jsonify({"error": "Dataset not found."}), 404
    return jsonify({"dataset": ds})


@dataset_bp.route("/<dataset_id>", methods=["DELETE"])
def api_delete_dataset(dataset_id: str):
    try:
        delete_dataset(dataset_id)
        return jsonify({"message": "Dataset deleted."})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@dataset_bp.route("/<dataset_id>/sheet", methods=["POST"])
def api_switch_sheet(dataset_id: str):
    data = request.get_json(silent=True) or {}
    sheet_name = data.get("sheet_name")
    if not sheet_name:
        return jsonify({"error": "sheet_name is required."}), 400
    try:
        ds = switch_excel_sheet(dataset_id, sheet_name)
        df = load_working_df(dataset_id)
        qual = analyze_data_quality(df)
        from database.db import update_dataset_stats
        update_dataset_stats(dataset_id, ds["row_count"], ds["col_count"], quality_score=qual["quality_score"])
        return jsonify({"dataset": get_dataset(dataset_id)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@dataset_bp.route("/<dataset_id>/preview", methods=["GET"])
def api_preview_dataset(dataset_id: str):
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 25, type=int)
    search = request.args.get("search", "", type=str)
    sort_by = request.args.get("sort_by", None, type=str)
    sort_dir = request.args.get("sort_dir", "asc", type=str)
    try:
        result = get_paginated_preview(
            dataset_id, page=page, page_size=page_size, search=search, sort_by=sort_by, sort_dir=sort_dir
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
