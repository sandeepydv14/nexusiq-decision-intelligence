from flask import Blueprint, jsonify, request

from database.db import (
    add_analysis_history,
    get_analysis_history,
    get_cleaning_operations,
    get_dataset,
    get_recent_activity,
    get_saved_reports,
    list_datasets,
    log_activity,
    update_dataset_stats,
)
from services.anomaly import detect_anomalies
from services.dataset_manager import load_working_df
from services.eda import generate_eda
from services.insights import generate_insights_and_recommendations
from services.profiler import profile_dataset
from services.quality import analyze_data_quality
from services.utils import safe_json

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api")


@analysis_bp.route("/analysis/<dataset_id>/dashboard", methods=["GET"])
def api_dashboard(dataset_id: str):
    try:
        ds = get_dataset(dataset_id)
        if not ds:
            return jsonify({"error": "Dataset not found."}), 404
        df = load_working_df(dataset_id)
        profile = profile_dataset(df)
        quality = analyze_data_quality(df)
        intel = generate_insights_and_recommendations(df)
        update_dataset_stats(dataset_id, int(df.shape[0]), int(df.shape[1]), quality_score=quality["quality_score"])

        datasets_all = list_datasets()
        recent = get_recent_activity(limit=12)
        cleaning_ops = get_cleaning_operations(dataset_id, active_only=True)

        return jsonify(
            safe_json(
                {
                    "total_datasets": len(datasets_all),
                    "dataset": get_dataset(dataset_id),
                    "overview": profile["overview"],
                    "quality": {
                        "score": quality["quality_score"],
                        "grade": quality["grade"],
                        "total_issues": quality["total_issues"],
                        "severity_counts": quality["severity_counts"],
                        "score_breakdown": quality["score_breakdown"],
                    },
                    "insights": intel["insights"][:5],
                    "recommendations": intel["recommendations"][:4],
                    "cleaning_steps_count": len(cleaning_ops),
                    "recent_activity": recent,
                }
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Dashboard computation failed: {exc}"}), 500


@analysis_bp.route("/analysis/<dataset_id>/profile", methods=["GET"])
def api_profile(dataset_id: str):
    try:
        df = load_working_df(dataset_id)
        return jsonify(profile_dataset(df))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@analysis_bp.route("/analysis/<dataset_id>/quality", methods=["GET"])
def api_quality(dataset_id: str):
    try:
        df = load_working_df(dataset_id)
        qual = analyze_data_quality(df)
        update_dataset_stats(dataset_id, int(df.shape[0]), int(df.shape[1]), quality_score=qual["quality_score"])
        return jsonify(qual)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@analysis_bp.route("/analysis/<dataset_id>/eda", methods=["GET"])
def api_eda(dataset_id: str):
    try:
        df = load_working_df(dataset_id)
        res = generate_eda(
            df,
            num_col=request.args.get("num_col"),
            cat_col=request.args.get("cat_col"),
            scatter_x=request.args.get("scatter_x"),
            scatter_y=request.args.get("scatter_y"),
            date_col=request.args.get("date_col"),
            agg_metric=request.args.get("agg_metric", "sum"),
        )
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@analysis_bp.route("/analysis/<dataset_id>/anomaly", methods=["POST"])
def api_anomaly(dataset_id: str):
    data = request.get_json(silent=True) or {}
    method = data.get("method", "iqr")
    columns = data.get("columns")
    threshold = data.get("threshold", 1.5 if method == "iqr" else 3.0)
    contamination = data.get("contamination", 0.05)
    try:
        df = load_working_df(dataset_id)
        res = detect_anomalies(df, method=method, columns=columns, threshold=threshold, contamination=contamination)
        add_analysis_history(
            dataset_id,
            "ANOMALY",
            f"Anomaly Detection ({method.upper()})",
            {
                "method": method,
                "columns": res["selected_columns"],
                "anomaly_count": res["anomaly_count"],
                "anomaly_pct": res["anomaly_pct"],
            },
        )
        log_activity(
            "ANOMALY",
            f"Ran {method.upper()} anomaly scan: {res['anomaly_count']} anomalies ({res['anomaly_pct']}%)",
            dataset_id,
        )
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@analysis_bp.route("/analysis/<dataset_id>/insights", methods=["GET"])
def api_insights(dataset_id: str):
    try:
        df = load_working_df(dataset_id)
        return jsonify(generate_insights_and_recommendations(df))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@analysis_bp.route("/history", methods=["GET"])
def api_history():
    dataset_id = request.args.get("dataset_id")
    return jsonify(
        safe_json(
            {
                "datasets": list_datasets(),
                "analyses": get_analysis_history(dataset_id=dataset_id, limit=50),
                "reports": get_saved_reports(dataset_id=dataset_id),
                "activity": get_recent_activity(limit=40),
            }
        )
    )
