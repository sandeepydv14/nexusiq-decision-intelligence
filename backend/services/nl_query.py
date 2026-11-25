import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.anomaly import detect_anomalies
from services.quality import analyze_data_quality
from services.utils import (
    get_categorical_columns,
    get_datetime_columns,
    get_numeric_columns,
    safe_float,
    safe_json,
)

COLUMN_SYNONYMS = {
    "sales": ["revenue", "sales", "amount", "turnover"],
    "revenue": ["revenue", "sales", "income"],
    "profit": ["profit", "margin", "earnings", "net"],
    "quantity": ["quantity", "qty", "units", "volume", "count"],
    "product": ["product", "item", "sku", "goods"],
    "category": ["category", "type", "department", "class", "group"],
    "region": ["region", "area", "zone", "location", "country", "state", "city"],
    "segment": ["customer_segment", "segment", "tier", "customer"],
    "date": ["date", "time", "order_date", "created_at", "timestamp"],
}


def _match_columns_in_query(query_lower: str, df: pd.DataFrame) -> List[str]:
    """Match column names mentioned directly or via common analytics synonyms."""
    matched: List[str] = []
    # Exact / normalized column matches (longest names first)
    sorted_cols = sorted(df.columns, key=lambda c: len(str(c)), reverse=True)
    for col in sorted_cols:
        norm = col.lower().replace("_", " ")
        if re.search(rf"\b{re.escape(col.lower())}\b", query_lower) or re.search(rf"\b{re.escape(norm)}\b", query_lower):
            if col not in matched:
                matched.append(col)

    # Synonym fallback
    for word, syns in COLUMN_SYNONYMS.items():
        if re.search(rf"\b{word}s?\b", query_lower):
            for col in df.columns:
                col_norm = col.lower().replace("_", " ")
                if any(s in col_norm for s in syns) and col not in matched:
                    matched.append(col)
                    break
    return matched


def _extract_top_n(query_lower: str, default: int = 5) -> int:
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "ten": 10}
    m = re.search(r"\b(?:top|bottom|first|last)\s+(\d+|one|two|three|four|five|six|seven|eight|ten)\b", query_lower)
    if m:
        token = m.group(1)
        return int(token) if token.isdigit() else word_map.get(token, default)
    return default


def answer_natural_language_query(df: pd.DataFrame, question: str) -> Dict[str, Any]:
    """
    Safe, local deterministic Pandas query engine.
    Returns calculated answer text, optional structured table, and optional Plotly chart spec.
    """
    q = (question or "").strip()
    if not q:
        raise ValueError("Please enter a question about your dataset.")
    ql = q.lower()

    num_cols = get_numeric_columns(df)
    cat_cols = get_categorical_columns(df)
    dt_cols = get_datetime_columns(df)
    matched_cols = _match_columns_in_query(ql, df)

    matched_nums = [c for c in matched_cols if c in num_cols]
    matched_cats = [c for c in matched_cols if c in cat_cols]

    # 1. Missing values / Data Quality questions
    if any(k in ql for k in ("missing", "null", "nan", "empty")):
        miss = df.isna().sum()
        miss_cols = miss[miss > 0].sort_values(ascending=False)
        if miss_cols.empty:
            return safe_json(
                {
                    "supported": True,
                    "intent": "missing_values",
                    "answer": "No columns in the active dataset contain missing values.",
                    "table": [],
                    "chart": None,
                }
            )
        rows = [
            {
                "Column": str(col),
                "Missing Count": int(cnt),
                "Missing %": round((int(cnt) / max(len(df), 1)) * 100, 2),
            }
            for col, cnt in miss_cols.items()
        ]
        return safe_json(
            {
                "supported": True,
                "intent": "missing_values",
                "answer": f"{len(rows)} column(s) contain missing values, totaling {int(miss_cols.sum())} missing cells.",
                "table": rows,
                "chart": {
                    "type": "bar",
                    "title": "Missing Values by Column",
                    "x": [r["Column"] for r in rows],
                    "y": [r["Missing Count"] for r in rows],
                    "x_title": "Column",
                    "y_title": "Missing Cells",
                },
            }
        )

    if any(k in ql for k in ("duplicate", "quality score", "data quality")):
        qual = analyze_data_quality(df)
        dup = int(df.duplicated().sum())
        return safe_json(
            {
                "supported": True,
                "intent": "data_quality",
                "answer": (
                    f"The current Data Quality Score is {qual['quality_score']}/100 ({qual['grade']}). "
                    f"There are {dup} duplicate rows and {qual['total_issues']} detected quality issues."
                ),
                "table": [
                    {
                        "Dimension": d["dimension"],
                        "Weight": d["weight"],
                        "Score": d["score"],
                        "Detail": d["detail"],
                    }
                    for d in qual["score_breakdown"]
                ],
                "chart": None,
            }
        )

    # 2. Anomaly / unusual records query
    if any(k in ql for k in ("unusual", "anomaly", "anomalies", "outlier", "outliers")):
        target_cols = matched_nums or None
        anom = detect_anomalies(df, method="iqr", columns=target_cols)
        return safe_json(
            {
                "supported": True,
                "intent": "anomalies",
                "answer": (
                    f"Detected {anom['anomaly_count']} anomalous record(s) ({anom['anomaly_pct']}% of rows) "
                    f"using IQR across {', '.join(anom['selected_columns'])}."
                ),
                "table": anom["anomalous_records"][:15],
                "chart": None,
            }
        )

    # 3. Correlation query
    if "correlat" in ql or "relationship between" in ql:
        if len(num_cols) < 2:
            return safe_json(
                {
                    "supported": False,
                    "intent": "correlation",
                    "answer": "At least two numerical columns are required to compute correlations.",
                    "table": [],
                    "chart": None,
                }
            )
        if len(matched_nums) >= 2:
            c1, c2 = matched_nums[0], matched_nums[1]
            r = safe_float(df[c1].corr(df[c2]), 4)
            strength = "strong" if abs(r or 0) >= 0.7 else ("moderate" if abs(r or 0) >= 0.4 else "weak")
            direction = "positive" if (r or 0) >= 0 else "negative"
            sub = df[[c1, c2]].dropna().head(600)
            return safe_json(
                {
                    "supported": True,
                    "intent": "correlation_pair",
                    "answer": f"The Pearson correlation between '{c1}' and '{c2}' is {r} ({strength} {direction} correlation).",
                    "table": [{"Column A": c1, "Column B": c2, "Pearson r": r, "Strength": f"{strength} {direction}"}],
                    "chart": {
                        "type": "scatter",
                        "title": f"{c1} vs {c2} (r = {r})",
                        "x": sub[c1].tolist(),
                        "y": sub[c2].tolist(),
                        "x_title": c1,
                        "y_title": c2,
                    },
                }
            )
        corr_df = df[num_cols].corr().fillna(0.0)
        pairs = []
        for i in range(len(num_cols)):
            for j in range(i + 1, len(num_cols)):
                val = float(corr_df.iloc[i, j])
                pairs.append({"Column A": num_cols[i], "Column B": num_cols[j], "Pearson r": round(val, 4)})
        pairs.sort(key=lambda x: abs(x["Pearson r"]), reverse=True)
        top_p = pairs[0]
        return safe_json(
            {
                "supported": True,
                "intent": "correlation_top",
                "answer": (
                    f"Strongest correlation is between '{top_p['Column A']}' and '{top_p['Column B']}' "
                    f"(r = {top_p['Pearson r']})."
                ),
                "table": pairs[:10],
                "chart": None,
            }
        )

    # 4. Time-series trends
    if any(k in ql for k in ("trend", "over time", "monthly", "weekly", "daily", "time series")):
        if not dt_cols or not num_cols:
            return safe_json(
                {
                    "supported": False,
                    "intent": "trend",
                    "answer": "Time-trend analysis requires both a valid date column and a numeric metric column.",
                    "table": [],
                    "chart": None,
                }
            )
        dcol = dt_cols[0]
        vcol = matched_nums[0] if matched_nums else ([c for c in num_cols if "id" not in c.lower()] or num_cols)[0]
        freq = "W" if "weekly" in ql else ("D" if "daily" in ql else "ME")
        freq_name = {"D": "Daily", "W": "Weekly", "ME": "Monthly"}[freq]
        ts = pd.DataFrame({"dt": pd.to_datetime(df[dcol], errors="coerce"), "val": pd.to_numeric(df[vcol], errors="coerce")}).dropna()
        grouped = ts.set_index("dt")["val"].resample(freq).sum().dropna()
        dates_str = [d.strftime("%Y-%m-%d") for d in grouped.index]
        vals = [safe_float(v, 2) for v in grouped.values]
        table_rows = [{"Period": d, f"Total {vcol}": v} for d, v in zip(dates_str, vals)]
        direction = "upward" if len(vals) >= 2 and vals[-1] >= vals[0] else "downward"
        return safe_json(
            {
                "supported": True,
                "intent": "time_trend",
                "answer": f"{freq_name} trend for '{vcol}' across {len(vals)} periods shows an overall {direction} movement (latest: {vals[-1] if vals else 'N/A'}).",
                "table": table_rows,
                "chart": {
                    "type": "line",
                    "title": f"{freq_name} {vcol} Trend",
                    "x": dates_str,
                    "y": vals,
                    "x_title": dcol,
                    "y_title": vcol,
                },
            }
        )

    # 5. Group comparison / Top-N / Highest / Lowest / Best performing
    is_top = any(k in ql for k in ("top", "highest", "best", "most", "largest", "leading"))
    is_bottom = any(k in ql for k in ("bottom", "lowest", "worst", "least", "smallest"))
    is_compare = any(k in ql for k in ("compare", "between", "by ", "per ", "across", "breakdown"))

    if is_top or is_bottom or is_compare or (matched_cats and matched_nums):
        if not cat_cols or not num_cols:
            if num_cols:
                vcol = matched_nums[0] if matched_nums else num_cols[0]
                return safe_json(
                    {
                        "supported": True,
                        "intent": "metric_extremes",
                        "answer": f"For '{vcol}': Min = {safe_float(df[vcol].min(), 2)}, Mean = {safe_float(df[vcol].mean(), 2)}, Max = {safe_float(df[vcol].max(), 2)}.",
                        "table": [],
                        "chart": None,
                    }
                )
        else:
            cat_col = matched_cats[0] if matched_cats else ([c for c in cat_cols if "id" not in c.lower()] or cat_cols)[0]
            val_col = matched_nums[0] if matched_nums else ([c for c in num_cols if "id" not in c.lower()] or num_cols)[0]
            agg_mode = "mean" if any(k in ql for k in ("average", "avg", "mean")) else "sum"
            n_items = _extract_top_n(ql, default=10 if is_compare else 5)

            grp = (
                df.dropna(subset=[cat_col, val_col])
                .groupby(df[cat_col].astype(str))[val_col]
                .agg(["sum", "mean", "count"])
                .sort_values(by=agg_mode, ascending=is_bottom)
            )
            sub_grp = grp.head(n_items)
            rows = [
                {
                    cat_col: str(idx),
                    f"Total {val_col}": safe_float(r["sum"], 2),
                    f"Average {val_col}": safe_float(r["mean"], 2),
                    "Records": int(r["count"]),
                }
                for idx, r in sub_grp.iterrows()
            ]
            top_name = rows[0][cat_col] if rows else "N/A"
            top_val = rows[0][f"{'Average' if agg_mode == 'mean' else 'Total'} {val_col}"] if rows else "N/A"
            qualifier = "lowest" if is_bottom else "highest"
            return safe_json(
                {
                    "supported": True,
                    "intent": "group_ranking",
                    "answer": (
                        f"Grouped '{val_col}' ({agg_mode}) by '{cat_col}'. "
                        f"'{top_name}' ranks {qualifier} at {top_val:,.2f}."
                        if isinstance(top_val, (int, float))
                        else f"Grouped '{val_col}' by '{cat_col}'."
                    ),
                    "table": rows,
                    "chart": {
                        "type": "bar",
                        "title": f"{'Average' if agg_mode == 'mean' else 'Total'} {val_col} by {cat_col}",
                        "x": [r[cat_col] for r in rows],
                        "y": [r[f"{'Average' if agg_mode == 'mean' else 'Total'} {val_col}"] for r in rows],
                        "x_title": cat_col,
                        "y_title": val_col,
                    },
                }
            )

    # 6. Single numeric column statistics (average, total, min, max, median)
    agg_keywords = {
        "mean": ("average", "avg", "mean"),
        "sum": ("total", "sum"),
        "median": ("median",),
        "min": ("minimum", "min"),
        "max": ("maximum", "max"),
    }
    requested_agg = None
    for fn, kws in agg_keywords.items():
        if any(re.search(rf"\b{kw}\b", ql) for kw in kws):
            requested_agg = fn
            break

    if requested_agg and num_cols:
        target = matched_nums[0] if matched_nums else ([c for c in num_cols if "id" not in c.lower()] or num_cols)[0]
        s = pd.to_numeric(df[target], errors="coerce").dropna()
        stat_map = {
            "mean": safe_float(s.mean(), 2),
            "sum": safe_float(s.sum(), 2),
            "median": safe_float(s.median(), 2),
            "min": safe_float(s.min(), 2),
            "max": safe_float(s.max(), 2),
        }
        return safe_json(
            {
                "supported": True,
                "intent": "single_aggregation",
                "answer": f"The {requested_agg} of '{target}' across {len(s)} valid rows is {stat_map[requested_agg]:,.2f}.",
                "table": [
                    {
                        "Column": target,
                        "Count": int(len(s)),
                        "Mean": stat_map["mean"],
                        "Median": stat_map["median"],
                        "Sum": stat_map["sum"],
                        "Min": stat_map["min"],
                        "Max": stat_map["max"],
                    }
                ],
                "chart": None,
            }
        )

    # 7. Dataset overview query
    if any(k in ql for k in ("how many rows", "how many columns", "describe", "overview", "summary", "columns")):
        return safe_json(
            {
                "supported": True,
                "intent": "dataset_overview",
                "answer": (
                    f"The dataset has {df.shape[0]} rows and {df.shape[1]} columns. "
                    f"Numeric: {len(num_cols)}, Categorical: {len(cat_cols)}, Datetime: {len(dt_cols)}."
                ),
                "table": [
                    {"Column": c, "Type": str(df[c].dtype), "Missing": int(df[c].isna().sum()), "Unique": int(df[c].nunique())}
                    for c in df.columns
                ],
                "chart": None,
            }
        )

    # Honest fallback for unsupported questions
    return safe_json(
        {
            "supported": False,
            "intent": "unsupported",
            "answer": (
                "I could not map that question to a verified local Pandas operation on your dataset. "
                "Try asking about column averages/totals, top/bottom categories, group comparisons, "
                "monthly/weekly trends, missing values, correlations, or unusual/anomalous records."
            ),
            "table": [],
            "chart": None,
        }
    )
