from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from services.utils import (
    get_categorical_columns,
    get_datetime_columns,
    get_numeric_columns,
    safe_float,
    safe_json,
)


def generate_eda(
    df: pd.DataFrame,
    num_col: Optional[str] = None,
    cat_col: Optional[str] = None,
    scatter_x: Optional[str] = None,
    scatter_y: Optional[str] = None,
    date_col: Optional[str] = None,
    agg_metric: str = "sum",
) -> Dict[str, Any]:
    """Generate automated exploratory data analysis visualizations and summary tables."""
    numeric_cols = get_numeric_columns(df)
    cat_cols = get_categorical_columns(df)
    dt_cols = get_datetime_columns(df)

    # Filter out ID-like columns for default picks
    meaningful_num = [c for c in numeric_cols if "id" not in c.lower()] or numeric_cols
    meaningful_cat = [
        c for c in cat_cols if 2 <= df[c].nunique(dropna=True) <= 25 and "id" not in c.lower()
    ] or [c for c in cat_cols if df[c].nunique(dropna=True) <= 30]

    sel_num = num_col if num_col in numeric_cols else (meaningful_num[0] if meaningful_num else None)
    sel_cat = cat_col if cat_col in cat_cols else (meaningful_cat[0] if meaningful_cat else None)
    sel_dt = date_col if date_col in dt_cols else (dt_cols[0] if dt_cols else None)

    # 1. Numeric distributions (top 4 numeric cols + selected)
    numeric_distributions = []
    dist_targets = ([sel_num] if sel_num else []) + [c for c in meaningful_num if c != sel_num]
    for col in dist_targets[:4]:
        clean = pd.to_numeric(df[col], errors="coerce").dropna()
        if clean.empty:
            continue
        numeric_distributions.append(
            {
                "column": col,
                "values": clean.head(2000).tolist(),
                "mean": safe_float(clean.mean()),
                "median": safe_float(clean.median()),
                "std": safe_float(clean.std(ddof=1)) if len(clean) > 1 else 0.0,
                "q1": safe_float(clean.quantile(0.25)),
                "q3": safe_float(clean.quantile(0.75)),
            }
        )

    # 2. Categorical distributions (top 4 categorical cols + selected)
    categorical_distributions = []
    cat_targets = ([sel_cat] if sel_cat else []) + [c for c in meaningful_cat if c != sel_cat]
    for col in cat_targets[:4]:
        vc = df[col].dropna().astype(str).value_counts().head(12)
        categorical_distributions.append(
            {
                "column": col,
                "labels": list(vc.index),
                "counts": [int(v) for v in vc.values],
            }
        )

    # 3. Box plots (selected numeric grouped by selected categorical, or multi-numeric)
    box_plot = None
    if sel_num and sel_cat:
        top_cats = df[sel_cat].dropna().astype(str).value_counts().head(8).index.tolist()
        groups = []
        for cat_val in top_cats:
            vals = pd.to_numeric(df.loc[df[sel_cat].astype(str) == cat_val, sel_num], errors="coerce").dropna()
            if not vals.empty:
                groups.append({"name": cat_val, "values": vals.head(500).tolist()})
        box_plot = {"numeric": sel_num, "category": sel_cat, "groups": groups}
    elif meaningful_num:
        groups = []
        for c in meaningful_num[:5]:
            vals = pd.to_numeric(df[c], errors="coerce").dropna()
            if not vals.empty:
                groups.append({"name": c, "values": vals.head(500).tolist()})
        box_plot = {"numeric": "Multiple", "category": None, "groups": groups}

    # 4. Scatter plot (auto-pick strongest correlated pair if not provided)
    scatter_plot = None
    if len(numeric_cols) >= 2:
        sx, sy = scatter_x, scatter_y
        if not (sx in numeric_cols and sy in numeric_cols and sx != sy):
            corr = df[meaningful_num if len(meaningful_num) >= 2 else numeric_cols].corr(numeric_only=True).abs()
            best_pair = None
            best_val = -1.0
            cols_c = list(corr.columns)
            for i in range(len(cols_c)):
                for j in range(i + 1, len(cols_c)):
                    v = float(corr.iloc[i, j]) if not pd.isna(corr.iloc[i, j]) else 0.0
                    if v > best_val:
                        best_val = v
                        best_pair = (cols_c[i], cols_c[j])
            sx, sy = best_pair if best_pair else (numeric_cols[0], numeric_cols[1])

        sub = df[[sx, sy] + ([sel_cat] if sel_cat else [])].dropna().head(1500)
        scatter_plot = {
            "x_col": sx,
            "y_col": sy,
            "color_col": sel_cat,
            "x": sub[sx].tolist(),
            "y": sub[sy].tolist(),
            "color": sub[sel_cat].astype(str).tolist() if sel_cat else None,
            "correlation": safe_float(df[sx].corr(df[sy]), 4),
        }

    # 5. Correlation heatmap
    correlation = None
    if len(numeric_cols) >= 2:
        corr_cols = numeric_cols[:12]
        corr_mat = df[corr_cols].corr(numeric_only=True).fillna(0.0)
        correlation = {
            "columns": corr_cols,
            "matrix": [[safe_float(v, 3) for v in row] for row in corr_mat.values],
        }

    # 6. Time series chart
    time_series = None
    if sel_dt and sel_num:
        ts_df = pd.DataFrame(
            {
                "dt": pd.to_datetime(df[sel_dt], errors="coerce"),
                "val": pd.to_numeric(df[sel_num], errors="coerce"),
            }
        ).dropna()
        if len(ts_df) >= 3:
            span_days = (ts_df["dt"].max() - ts_df["dt"].min()).days
            freq = "ME" if span_days > 90 else ("W" if span_days > 21 else "D")
            freq_label = "Monthly" if freq == "ME" else ("Weekly" if freq == "W" else "Daily")
            agg_fn = "mean" if agg_metric == "mean" else "sum"
            grouped = ts_df.set_index("dt")["val"].resample(freq).agg(agg_fn).dropna()
            time_series = {
                "date_col": sel_dt,
                "value_col": sel_num,
                "granularity": freq_label,
                "aggregation": agg_fn,
                "dates": [d.strftime("%Y-%m-%d") for d in grouped.index],
                "values": [safe_float(v, 2) for v in grouped.values],
            }

    # 7. Group comparison & Top/Bottom categories
    group_comparison = None
    top_bottom = None
    if sel_cat and sel_num:
        grp = (
            df.dropna(subset=[sel_cat, sel_num])
            .groupby(df[sel_cat].astype(str))[sel_num]
            .agg(["count", "sum", "mean", "median", "min", "max"])
            .sort_values(by="sum", ascending=False)
        )
        group_comparison = {
            "category_col": sel_cat,
            "numeric_col": sel_num,
            "rows": [
                {
                    "category": str(idx),
                    "count": int(r["count"]),
                    "sum": safe_float(r["sum"], 2),
                    "mean": safe_float(r["mean"], 2),
                    "median": safe_float(r["median"], 2),
                    "min": safe_float(r["min"], 2),
                    "max": safe_float(r["max"], 2),
                }
                for idx, r in grp.head(15).iterrows()
            ],
        }
        top_bottom = {
            "category_col": sel_cat,
            "metric_col": sel_num,
            "top": [
                {"category": str(idx), "total": safe_float(r["sum"], 2), "mean": safe_float(r["mean"], 2), "count": int(r["count"])}
                for idx, r in grp.head(5).iterrows()
            ],
            "bottom": [
                {"category": str(idx), "total": safe_float(r["sum"], 2), "mean": safe_float(r["mean"], 2), "count": int(r["count"])}
                for idx, r in grp.tail(5).sort_values(by="sum", ascending=True).iterrows()
            ],
        }

    # Summary statistics table
    summary_table = []
    for col in numeric_cols:
        clean = pd.to_numeric(df[col], errors="coerce").dropna()
        if clean.empty:
            continue
        summary_table.append(
            {
                "column": col,
                "count": int(len(clean)),
                "mean": safe_float(clean.mean(), 3),
                "std": safe_float(clean.std(ddof=1), 3) if len(clean) > 1 else 0.0,
                "min": safe_float(clean.min(), 3),
                "p25": safe_float(clean.quantile(0.25), 3),
                "median": safe_float(clean.median(), 3),
                "p75": safe_float(clean.quantile(0.75), 3),
                "max": safe_float(clean.max(), 3),
            }
        )

    return safe_json(
        {
            "selectors": {
                "numeric_columns": numeric_cols,
                "categorical_columns": cat_cols,
                "datetime_columns": dt_cols,
                "selected": {
                    "num_col": sel_num,
                    "cat_col": sel_cat,
                    "scatter_x": scatter_plot["x_col"] if scatter_plot else None,
                    "scatter_y": scatter_plot["y_col"] if scatter_plot else None,
                    "date_col": sel_dt,
                    "agg_metric": agg_metric,
                },
            },
            "numeric_distributions": numeric_distributions,
            "categorical_distributions": categorical_distributions,
            "box_plot": box_plot,
            "scatter_plot": scatter_plot,
            "correlation": correlation,
            "time_series": time_series,
            "group_comparison": group_comparison,
            "top_bottom": top_bottom,
            "summary_table": summary_table,
        }
    )
