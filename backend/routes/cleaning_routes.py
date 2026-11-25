from flask import Blueprint, jsonify, request

from database.db import get_cleaning_operations
from services.cleaner import (
    apply_cleaning_operation,
    preview_cleaning_operation,
    reset_to_original,
    undo_cleaning_operation,
)

cleaning_bp = Blueprint("cleaning", __name__, url_prefix="/api/cleaning")


@cleaning_bp.route("/<dataset_id>/history", methods=["GET"])
def api_cleaning_history(dataset_id: str):
    return jsonify({"operations": get_cleaning_operations(dataset_id, active_only=True)})


@cleaning_bp.route("/<dataset_id>/preview", methods=["POST"])
def api_cleaning_preview(dataset_id: str):
    data = request.get_json(silent=True) or {}
    operation = data.get("operation")
    params = data.get("params") or {}
    if not operation:
        return jsonify({"error": "Operation name is required."}), 400
    try:
        res = preview_cleaning_operation(dataset_id, operation, params)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Preview failed: {exc}"}), 500


@cleaning_bp.route("/<dataset_id>/apply", methods=["POST"])
def api_cleaning_apply(dataset_id: str):
    data = request.get_json(silent=True) or {}
    operation = data.get("operation")
    params = data.get("params") or {}
    if not operation:
        return jsonify({"error": "Operation name is required."}), 400
    try:
        res = apply_cleaning_operation(dataset_id, operation, params)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Cleaning failed: {exc}"}), 500


@cleaning_bp.route("/<dataset_id>/undo", methods=["POST"])
def api_cleaning_undo(dataset_id: str):
    try:
        res = undo_cleaning_operation(dataset_id)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@cleaning_bp.route("/<dataset_id>/reset", methods=["POST"])
def api_cleaning_reset(dataset_id: str):
    try:
        res = reset_to_original(dataset_id)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
