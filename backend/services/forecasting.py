from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

from services.utils import get_datetime_columns, get_numeric_columns, safe_float, safe_json


def check_forecasting_suitability(df: pd.DataFrame) -> Dict[str, Any]:
    dt_cols = get_datetime_columns(df)
    num_cols = [c for c in get_numeric_columns(df) if "id" not in c.lower()] or get_numeric_columns(df)
    if not dt_cols:
        return {
            "suitable": False,
            "reason": "No valid datetime/date column was detected. Convert a date column in Cleaning Studio first.",
            "date_columns": [],
            "numeric_columns": num_cols,
        }
    if not num_cols:
        return {
            "suitable": False,
            "reason": "No numerical target columns were found for forecasting.",
            "date_columns": dt_cols,
            "numeric_columns": [],
        }
    return {
        "suitable": True,
        "reason": "Dataset contains valid date and numeric columns suitable for time-series forecasting.",
        "date_columns": dt_cols,
        "numeric_columns": num_cols,
    }


def run_forecast(
    df: pd.DataFrame,
    date_col: str,
    target_col: str,
    horizon: int = 6,
    freq: str = "auto",
    agg: str = "sum",
) -> Dict[str, Any]:
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found.")
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found.")

    ts_df = pd.DataFrame(
        {
            "dt": pd.to_datetime(df[date_col], errors="coerce"),
            "val": pd.to_numeric(df[target_col], errors="coerce"),
        }
    ).dropna()

    if len(ts_df) < 8:
        raise ValueError(
            f"Time-series forecasting requires at least 8 valid (date, value) observations (found {len(ts_df)})."
        )

    span_days = int((ts_df["dt"].max() - ts_df["dt"].min()).days)
    if freq == "auto":
        chosen_freq = "ME" if span_days >= 120 else ("W" if span_days >= 28 else "D")
    else:
        chosen_freq = {"daily": "D", "weekly": "W", "monthly": "ME"}.get(freq.lower(), freq)

    freq_names = {"D": "Daily", "W": "Weekly", "ME": "Monthly"}
    agg_fn = "mean" if agg == "mean" else "sum"

    series = ts_df.set_index("dt")["val"].resample(chosen_freq).agg(agg_fn)
    # Fill intermediate missing periods with linear interpolation if sparse, else drop leading/trailing NaN
    series = series.dropna()

    if len(series) < 6:
        raise ValueError(
            f"Aggregating by {freq_names.get(chosen_freq, chosen_freq)} yielded only {len(series)} periods; "
            f"need at least 6 periods. Try a finer frequency (Daily or Weekly)."
        )

    horizon = max(1, min(int(horizon), 24))
    last_date = series.index[-1]
    future_dates = pd.date_range(start=last_date, periods=horizon + 1, freq=chosen_freq)[1:]

    # Holdout backtest on last k periods
    val_len = min(max(2, len(series) // 5), max(2, len(series) - 4))
    train_s = series.iloc[:-val_len]
    test_s = series.iloc[-val_len:]

    window = min(4, max(2, len(train_s) // 3))

    def _predict_naive(s: pd.Series, steps: int) -> np.ndarray:
        return np.repeat(float(s.iloc[-1]), steps)

    def _predict_ma(s: pd.Series, steps: int) -> np.ndarray:
        w = min(window, len(s))
        ma_val = float(s.iloc[-w:].mean())
        return np.repeat(ma_val, steps)

    def _predict_es(s: pd.Series, steps: int) -> tuple:
        try:
            if len(s) >= 6:
                model = ExponentialSmoothing(s.values.astype(float), trend="add", damped_trend=True, initialization_method="estimated")
                fit = model.fit(optimized=True)
                return fit.forecast(steps), "Holt Damped Trend"
            model = SimpleExpSmoothing(s.values.astype(float), initialization_method="estimated")
            fit = model.fit(optimized=True)
            return fit.forecast(steps), "Simple Exponential Smoothing"
        except Exception:
            model = SimpleExpSmoothing(s.values.astype(float), initialization_method="heuristic")
            fit = model.fit()
            return fit.forecast(steps), "Simple Exponential Smoothing"

    # Backtest metrics
    bt_naive = _predict_naive(train_s, val_len)
    bt_ma = _predict_ma(train_s, val_len)
    bt_es, es_label = _predict_es(train_s, val_len)

    # Full-series future forecasts
    fc_naive = _predict_naive(series, horizon)
    fc_ma = _predict_ma(series, horizon)
    fc_es, es_label = _predict_es(series, horizon)

    models_summary = [
        {
            "method": "Naive Baseline",
            "key": "naive",
            "mae": round(float(mean_absolute_error(test_s.values, bt_naive)), 3),
            "rmse": round(float(root_mean_squared_error(test_s.values, bt_naive)), 3),
            "forecast": [safe_float(v, 2) for v in fc_naive],
        },
        {
            "method": f"Moving Average (w={window})",
            "key": "moving_average",
            "mae": round(float(mean_absolute_error(test_s.values, bt_ma)), 3),
            "rmse": round(float(root_mean_squared_error(test_s.values, bt_ma)), 3),
            "forecast": [safe_float(v, 2) for v in fc_ma],
        },
        {
            "method": f"Exponential Smoothing ({es_label})",
            "key": "exponential_smoothing",
            "mae": round(float(mean_absolute_error(test_s.values, bt_es)), 3),
            "rmse": round(float(root_mean_squared_error(test_s.values, bt_es)), 3),
            "forecast": [safe_float(v, 2) for v in fc_es],
        },
    ]

    # Simple linear trend check across historical series
    x_idx = np.arange(len(series), dtype=float)
    slope = float(np.polyfit(x_idx, series.values.astype(float), 1)[0])
    start_val = float(series.iloc[0]) if float(series.iloc[0]) != 0 else 1.0
    total_change_pct = ((float(series.iloc[-1]) - float(series.iloc[0])) / abs(start_val)) * 100.0
    trend_dir = "Increasing" if slope > 0 else ("Decreasing" if slope < 0 else "Flat")

    best_model = min(models_summary, key=lambda m: m["rmse"])

    return safe_json(
        {
            "suitable": True,
            "date_column": date_col,
            "target_column": target_col,
            "granularity": freq_names.get(chosen_freq, chosen_freq),
            "aggregation": agg_fn,
            "horizon": horizon,
            "periods_observed": int(len(series)),
            "backtest_periods": int(val_len),
            "trend": {
                "direction": trend_dir,
                "slope_per_period": safe_float(slope, 3),
                "change_pct": safe_float(total_change_pct, 2),
            },
            "historical": {
                "dates": [d.strftime("%Y-%m-%d") for d in series.index],
                "values": [safe_float(v, 2) for v in series.values],
            },
            "future_dates": [d.strftime("%Y-%m-%d") for d in future_dates],
            "models": models_summary,
            "recommended_method": best_model["method"],
        }
    )
