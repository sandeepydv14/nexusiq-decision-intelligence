from flask import Blueprint, jsonify, request

from database.db import add_analysis_history, log_activity
from services.dataset_manager import load_working_df
from services.forecasting import check_forecasting_suitability, run_forecast
from services.ml_engine import infer_ml_metadata, train_and_evaluate

ml_bp = Blueprint("ml", __name__, url_prefix="/api")


@ml_bp.route("/ml/<dataset_id>/metadata", methods=["GET"])
def api_ml_metadata(dataset_id: str):
    try:
        df = load_working_df(dataset_id)
        return jsonify(infer_ml_metadata(df))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ml_bp.route("/ml/<dataset_id>/train", methods=["POST"])
def api_ml_train(dataset_id: str):
    data = request.get_json(silent=True) or {}
    target_col = data.get("target_column")
    feature_cols = data.get("feature_columns") or []
    task_type = data.get("task_type", "auto")
    algorithms = data.get("algorithms")
    test_size = data.get("test_size", 0.2)

    if not target_col:
        return jsonify({"error": "target_column is required."}), 400

    try:
        df = load_working_df(dataset_id)
        res = train_and_evaluate(
            df,
            target_col=target_col,
            feature_cols=feature_cols,
            task_type=task_type,
            algorithms=algorithms,
            test_size=test_size,
        )
        best = res.get("best_model") or {}
        metric_text = (
            f"F1={best.get('f1_score')}, Acc={best.get('accuracy')}"
            if res["task_type"] == "classification"
            else f"R²={best.get('r2_score')}, RMSE={best.get('rmse')}"
        )
        add_analysis_history(
            dataset_id,
            "ML",
            f"{res['task_type'].title()} on '{target_col}' ({best.get('algorithm')})",
            {
                "task_type": res["task_type"],
                "target": target_col,
                "best_algorithm": best.get("algorithm"),
                "metrics": metric_text,
            },
        )
        log_activity("ML_TRAIN", f"Trained {res['task_type']} models targeting '{target_col}' ({metric_text})", dataset_id)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Model training failed: {exc}"}), 500


@ml_bp.route("/forecast/<dataset_id>/suitability", methods=["GET"])
def api_forecast_suitability(dataset_id: str):
    try:
        df = load_working_df(dataset_id)
        return jsonify(check_forecasting_suitability(df))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@ml_bp.route("/forecast/<dataset_id>/run", methods=["POST"])
def api_forecast_run(dataset_id: str):
    data = request.get_json(silent=True) or {}
    date_col = data.get("date_column")
    target_col = data.get("target_column")
    horizon = data.get("horizon", 6)
    freq = data.get("freq", "auto")
    agg = data.get("agg", "sum")

    if not date_col or not target_col:
        return jsonify({"error": "date_column and target_column are required."}), 400

    try:
        df = load_working_df(dataset_id)
        res = run_forecast(df, date_col=date_col, target_col=target_col, horizon=horizon, freq=freq, agg=agg)
        add_analysis_history(
            dataset_id,
            "FORECAST",
            f"Forecast '{target_col}' ({res['granularity']}, +{res['horizon']} periods)",
            {
                "target": target_col,
                "granularity": res["granularity"],
                "recommended_method": res["recommended_method"],
                "trend": res["trend"]["direction"],
            },
        )
        log_activity("FORECAST", f"Generated {res['horizon']}-step {res['granularity']} forecast for '{target_col}'", dataset_id)
        return jsonify(res)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Forecasting failed: {exc}"}), 500
