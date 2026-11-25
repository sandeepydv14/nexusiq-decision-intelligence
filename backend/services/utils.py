import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def safe_float(val: Any, decimals: int = 4) -> Any:
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def safe_json(obj: Any) -> Any:
    """Recursively convert numpy/pandas objects to pure JSON-safe Python primitives."""
    if obj is None:
        return None
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        if math.isnan(float(obj)) or math.isinf(float(obj)):
            return None
        return float(obj)
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        if pd.isna(obj):
            return None
        return pd.Timestamp(obj).isoformat()
    if isinstance(obj, dict):
        return {str(k): safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray, pd.Series, pd.Index)):
        return [safe_json(x) for x in obj]
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return str(obj) if not isinstance(obj, (str, int, float, bool)) else obj


def try_parse_datetime(series: pd.Series) -> pd.Series:
    """Attempt to parse an object/string series as datetime without coercing pure numbers."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return pd.Series([pd.NaT] * len(series), index=series.index)
    non_null = series.dropna().astype(str).str.strip()
    if non_null.empty:
        return pd.Series([pd.NaT] * len(series), index=series.index)
    # Reject strings that are purely numeric (e.g. "12345")
    if non_null.str.fullmatch(r"-?\d+(\.\d+)?").mean() > 0.5:
        return pd.Series([pd.NaT] * len(series), index=series.index)
    sample = non_null.head(200)
    parsed_sample = pd.to_datetime(sample, errors="coerce", format="mixed")
    if parsed_sample.notna().mean() >= 0.8:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    return pd.Series([pd.NaT] * len(series), index=series.index)


def infer_column_role(series: pd.Series) -> str:
    """Classify a column as numeric, datetime, boolean, categorical, or text."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    parsed_dt = try_parse_datetime(series)
    if parsed_dt.notna().sum() > 0 and parsed_dt.notna().mean() >= 0.8 * max(series.notna().mean(), 0.01):
        return "datetime"
    non_null = series.dropna()
    if non_null.empty:
        return "categorical"
    unique_ratio = non_null.nunique() / max(len(non_null), 1)
    avg_len = non_null.astype(str).str.len().mean()
    if unique_ratio > 0.85 and len(non_null) > 30 and avg_len > 20:
        return "text"
    return "categorical"


def get_column_roles(df: pd.DataFrame) -> Dict[str, str]:
    return {col: infer_column_role(df[col]) for col in df.columns}


def get_numeric_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]


def get_datetime_columns(df: pd.DataFrame) -> List[str]:
    roles = get_column_roles(df)
    return [c for c, r in roles.items() if r == "datetime"]


def get_categorical_columns(df: pd.DataFrame) -> List[str]:
    roles = get_column_roles(df)
    return [c for c, r in roles.items() if r in ("categorical", "boolean")]
