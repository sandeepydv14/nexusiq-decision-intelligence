from flask import Blueprint, jsonify, request

from database.db import log_activity
from services.dataset_manager import load_working_df
from services.nl_query import answer_natural_language_query

query_bp = Blueprint("query", __name__, url_prefix="/api/query")


@query_bp.route("/<dataset_id>/ask", methods=["POST"])
def api_ask_data(dataset_id: str):
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")
    try:
        df = load_working_df(dataset_id)
        res = answer_natural_language_query(df, question)
        log_activity("NL_QUERY", f"Asked: '{question[:60]}'", dataset_id)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Query failed: {exc}"}), 500
