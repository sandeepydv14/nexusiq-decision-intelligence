from typing import Any, Dict, List

import numpy as np
import pandas as pd

from services.utils import get_column_roles, get_numeric_columns, safe_float, safe_json


def profile_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute comprehensive column-level and dataset-level statistical profile."""
    n_rows, n_cols = df.shape
    roles = get_column_roles(df)
    numeric_cols = get_numeric_columns(df)
    categorical_cols = [c for c, r in roles.items() if r in ("categorical", "boolean")]
    datetime_cols = [c for c, r in roles.items() if r == "datetime"]
    text_cols = [c for c, r in roles.items() if r == "text"]

    total_cells = max(n_rows * n_cols, 1)
    total_missing = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    memory_kb = round(float(df.memory_usage(deep=True).sum()) / 1024.0, 2)

    column_profiles: List[Dict[str, Any]] = []
    for col in df.columns:
        s = df[col]
        role = roles[col]
        missing_count = int(s.isna().sum())
        missing_pct = round((missing_count / max(n_rows, 1)) * 100, 2)
        unique_count = int(s.nunique(dropna=True))

        mode_series = s.dropna().mode()
        mode_val = safe_json(mode_series.iloc[0]) if not mode_series.empty else None

        col_info: Dict[str, Any] = {
            "name": col,
            "dtype": str(s.dtype),
            "role": role,
            "count": int(s.notna().sum()),
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": unique_count,
            "mode": mode_val,
        }

        if role == "numeric" and pd.api.types.is_numeric_dtype(s):
            clean = pd.to_numeric(s, errors="coerce").dropna()
            if not clean.empty:
                q1 = float(clean.quantile(0.25))
                q3 = float(clean.quantile(0.75))
                iqr = q3 - q1
                lower_fence = q1 - 1.5 * iqr
                upper_fence = q3 + 1.5 * iqr
                outlier_count = int(((clean < lower_fence) | (clean > upper_fence)).sum()) if iqr > 0 else 0

                hist_counts, hist_edges = np.histogram(clean, bins=min(15, max(5, int(np.sqrt(len(clean))))))
                col_info.update(
                    {
                        "mean": safe_float(clean.mean()),
                        "median": safe_float(clean.median()),
                        "std": safe_float(clean.std(ddof=1)) if len(clean) > 1 else 0.0,
                        "min": safe_float(clean.min()),
                        "q1": safe_float(q1),
                        "q3": safe_float(q3),
                        "max": safe_float(clean.max()),
                        "skewness": safe_float(clean.skew()) if len(clean) > 2 else 0.0,
                        "outlier_count": outlier_count,
                        "outlier_pct": round((outlier_count / len(clean)) * 100, 2),
                        "histogram": {
                            "counts": [int(c) for c in hist_counts],
                            "edges": [safe_float(e, 3) for e in hist_edges],
                        },
                    }
                )
        elif role == "datetime":
            parsed = pd.to_datetime(s, errors="coerce").dropna()
            if not parsed.empty:
                col_info.update(
                    {
                        "min": parsed.min().isoformat(),
                        "max": parsed.max().isoformat(),
                        "span_days": int((parsed.max() - parsed.min()).days),
                    }
                )
        else:
            vc = s.dropna().astype(str).value_counts().head(10)
            col_info["top_values"] = [
                {
                    "value": str(k),
                    "count": int(v),
                    "pct": round((int(v) / max(n_rows - missing_count, 1)) * 100, 2),
                }
                for k, v in vc.items()
            ]

        column_profiles.append(col_info)

    # Correlation matrix for numeric columns
    correlation = {"columns": [], "matrix": [], "top_pairs": []}
    if len(numeric_cols) >= 2:
        corr_df = df[numeric_cols].corr(numeric_only=True).fillna(0.0)
        correlation["columns"] = list(corr_df.columns)
        correlation["matrix"] = [
            [safe_float(corr_df.iloc[i, j], 3) for j in range(len(corr_df.columns))]
            for i in range(len(corr_df.columns))
        ]
        pairs = []
        cols_list = list(corr_df.columns)
        for i in range(len(cols_list)):
            for j in range(i + 1, len(cols_list)):
                val = float(corr_df.iloc[i, j])
                pairs.append(
                    {
                        "col_a": cols_list[i],
                        "col_b": cols_list[j],
                        "correlation": round(val, 4),
                        "abs_correlation": round(abs(val), 4),
                    }
                )
        pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
        correlation["top_pairs"] = pairs[:10]

    return safe_json(
        {
            "overview": {
                "row_count": int(n_rows),
                "col_count": int(n_cols),
                "total_cells": int(total_cells),
                "missing_cells": total_missing,
                "missing_pct": round((total_missing / total_cells) * 100, 2),
                "duplicate_rows": duplicate_rows,
                "duplicate_pct": round((duplicate_rows / max(n_rows, 1)) * 100, 2),
                "memory_kb": memory_kb,
                "numeric_columns": numeric_cols,
                "categorical_columns": categorical_cols,
                "datetime_columns": datetime_cols,
                "text_columns": text_cols,
            },
            "columns": column_profiles,
            "correlation": correlation,
        }
    )
