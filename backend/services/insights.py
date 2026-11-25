from typing import Any, Dict, List

import numpy as np
import pandas as pd

from services.quality import analyze_data_quality
from services.utils import (
    get_categorical_columns,
    get_datetime_columns,
    get_numeric_columns,
    safe_float,
    safe_json,
)


def generate_insights_and_recommendations(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate evidence-backed analytical insights and actionable recommendations
    directly computed from the active dataset.
    """
    insights: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []

    num_cols = [c for c in get_numeric_columns(df) if "id" not in c.lower()] or get_numeric_columns(df)
    cat_cols = [
        c for c in get_categorical_columns(df)
        if "id" not in c.lower() and 2 <= df[c].nunique(dropna=True) <= 30
    ]
    dt_cols = get_datetime_columns(df)

    # 1. Data quality insight & recommendation
    quality = analyze_data_quality(df)
    q_score = quality["quality_score"]
    high_issues = [i for i in quality["issues"] if i["severity"] == "High"]
    if quality["total_issues"] > 0:
        insights.append(
            {
                "id": "insight_quality",
                "type": "Data Quality",
                "severity": "warning" if q_score < 85 else "info",
                "title": f"Dataset Quality Score is {q_score}/100 ({quality['grade']})",
                "summary": (
                    f"Detected {quality['total_issues']} data quality issue(s), including {len(high_issues)} high-severity issue(s)."
                ),
                "evidence": "; ".join(d["detail"] for d in quality["score_breakdown"][:3]),
            }
        )
        top_issue = quality["issues"][0]
        recommendations.append(
            {
                "id": "rec_quality",
                "priority": "High" if high_issues else "Medium",
                "category": "Data Hygiene",
                "title": f"Resolve {top_issue['category']} in '{top_issue['column']}'",
                "rationale": f"{top_issue['problem']} Current overall quality score is {q_score}/100.",
                "action": top_issue["recommended_solution"],
                "target_page": "cleaning",
            }
        )
    else:
        insights.append(
            {
                "id": "insight_quality_clean",
                "type": "Data Quality",
                "severity": "positive",
                "title": f"High Data Integrity ({q_score}/100)",
                "summary": "No missing values, duplicate rows, or structural quality issues detected.",
                "evidence": f"Evaluated across {len(df)} rows and {len(df.columns)} columns.",
            }
        )

    # 2. Highest & lowest performing categories + group disparity
    if cat_cols and num_cols:
        primary_num = num_cols[0]
        for pref in ("revenue", "sales", "profit", "amount", "score"):
            match = [c for c in num_cols if pref in c.lower()]
            if match:
                primary_num = match[0]
                break

        for ccol in cat_cols[:2]:
            grp = (
                df.dropna(subset=[ccol, primary_num])
                .groupby(df[ccol].astype(str))[primary_num]
                .agg(["sum", "mean", "count"])
                .sort_values(by="sum", ascending=False)
            )
            if len(grp) < 2:
                continue
            total_sum = float(grp["sum"].sum()) or 1.0
            best_name = str(grp.index[0])
            best_sum = float(grp.iloc[0]["sum"])
            best_share = round((best_sum / abs(total_sum)) * 100, 1)
            worst_name = str(grp.index[-1])
            worst_sum = float(grp.iloc[-1]["sum"])
            worst_share = round((worst_sum / abs(total_sum)) * 100, 1)

            insights.append(
                {
                    "id": f"insight_top_{ccol}",
                    "type": "Performance Leader",
                    "severity": "positive",
                    "title": f"'{best_name}' leads {ccol} in {primary_num}",
                    "summary": (
                        f"'{best_name}' generated {best_sum:,.2f} ({best_share}% of total {primary_num}) "
                        f"across {int(grp.iloc[0]['count'])} records, while '{worst_name}' contributed {worst_sum:,.2f} ({worst_share}%)."
                    ),
                    "evidence": f"Top avg: {grp.iloc[0]['mean']:,.2f} vs Lowest avg: {grp.iloc[-1]['mean']:,.2f}",
                }
            )

            recommendations.append(
                {
                    "id": f"rec_cat_{ccol}",
                    "priority": "Medium",
                    "category": "Segment Optimization",
                    "title": f"Investigate '{worst_name}' underperformance and scale '{best_name}'",
                    "rationale": (
                        f"In '{ccol}', '{best_name}' accounts for {best_share}% of {primary_num} "
                        f"compared to {worst_share}% for '{worst_name}'."
                    ),
                    "action": f"Compare pricing, volume, or conversion drivers between '{best_name}' and '{worst_name}' in EDA.",
                    "target_page": "eda",
                }
            )

    # 3. Time-series trend insight
    if dt_cols and num_cols:
        dcol = dt_cols[0]
        vcol = num_cols[0]
        for pref in ("revenue", "sales", "profit", "amount"):
            match = [c for c in num_cols if pref in c.lower()]
            if match:
                vcol = match[0]
                break
        ts = pd.DataFrame(
            {"dt": pd.to_datetime(df[dcol], errors="coerce"), "val": pd.to_numeric(df[vcol], errors="coerce")}
        ).dropna()
        if len(ts) >= 8:
            span = (ts["dt"].max() - ts["dt"].min()).days
            freq = "ME" if span >= 120 else ("W" if span >= 28 else "D")
            freq_label = {"ME": "monthly", "W": "weekly", "D": "daily"}[freq]
            grouped = ts.set_index("dt")["val"].resample(freq).sum().dropna()
            if len(grouped) >= 4:
                x = np.arange(len(grouped), dtype=float)
                slope = float(np.polyfit(x, grouped.values.astype(float), 1)[0])
                first_v = float(grouped.iloc[0])
                last_v = float(grouped.iloc[-1])
                pct_change = ((last_v - first_v) / abs(first_v)) * 100.0 if first_v != 0 else 0.0
                direction = "upward" if slope > 0 else "downward"
                insights.append(
                    {
                        "id": "insight_trend",
                        "type": "Trend Analysis",
                        "severity": "positive" if slope > 0 else "warning",
                        "title": f"{freq_label.title()} {vcol} shows an {direction} trajectory ({pct_change:+.1f}%)",
                        "summary": (
                            f"Across {len(grouped)} {freq_label} periods, {vcol} moved from {first_v:,.2f} "
                            f"to {last_v:,.2f} (slope: {slope:+.2f} per period)."
                        ),
                        "evidence": f"Peak period: {grouped.idxmax().strftime('%Y-%m-%d')} ({grouped.max():,.2f})",
                    }
                )
                recommendations.append(
                    {
                        "id": "rec_forecast",
                        "priority": "High" if slope < 0 else "Medium",
                        "category": "Forecasting & Planning",
                        "title": f"{'Mitigate decline in' if slope < 0 else 'Forecast future demand for'} {vcol}",
                        "rationale": f"{vcol} exhibits a {pct_change:+.1f}% shift over the observed {freq_label} horizon.",
                        "action": f"Run Holt-Winters Exponential Smoothing on '{vcol}' in the Forecasting module to project upcoming periods.",
                        "target_page": "forecasting",
                    }
                )

    # 4. Correlation insight
    if len(num_cols) >= 2:
        corr = df[num_cols].corr(numeric_only=True).fillna(0.0)
        best_pair = None
        best_r = 0.0
        cols_list = list(corr.columns)
        for i in range(len(cols_list)):
            for j in range(i + 1, len(cols_list)):
                r = float(corr.iloc[i, j])
                if abs(r) > abs(best_r):
                    best_r = r
                    best_pair = (cols_list[i], cols_list[j])
        if best_pair and abs(best_r) >= 0.35:
            c1, c2 = best_pair
            rel = "positive" if best_r > 0 else "negative"
            strength = "strong" if abs(best_r) >= 0.7 else "moderate"
            insights.append(
                {
                    "id": "insight_corr",
                    "type": "Statistical Relationship",
                    "severity": "info",
                    "title": f"{strength.title()} {rel} correlation between '{c1}' and '{c2}' (r = {best_r:.3f})",
                    "summary": (
                        f"Changes in '{c1}' are {'positively' if best_r > 0 else 'inversely'} associated with '{c2}' "
                        f"across {len(df[[c1, c2]].dropna())} complete pairs."
                    ),
                    "evidence": f"Pearson r = {best_r:.4f}",
                }
            )
            if best_r < -0.35:
                recommendations.append(
                    {
                        "id": "rec_neg_corr",
                        "priority": "High",
                        "category": "Margin & Driver Control",
                        "title": f"Monitor inverse trade-off between '{c1}' and '{c2}'",
                        "rationale": f"'{c1}' and '{c2}' show an inverse correlation (r = {best_r:.3f}), indicating potential trade-off pressure.",
                        "action": f"Train a regression model targeting '{c2}' in Machine Learning to quantify feature impact.",
                        "target_page": "ml",
                    }
                )

    # 5. Outlier / anomaly insight
    for col in num_cols[:4]:
        clean = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(clean) < 10:
            continue
        q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            continue
        outliers = clean[(clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)]
        if len(outliers) > 0:
            pct = round((len(outliers) / len(clean)) * 100, 2)
            insights.append(
                {
                    "id": f"insight_outliers_{col}",
                    "type": "Anomaly Pattern",
                    "severity": "warning",
                    "title": f"{len(outliers)} statistical outlier(s) detected in '{col}' ({pct}%)",
                    "summary": (
                        f"Values in '{col}' fall outside the IQR fence [{q1 - 1.5*iqr:,.2f}, {q3 + 1.5*iqr:,.2f}], "
                        f"ranging from {clean.min():,.2f} to {clean.max():,.2f}."
                    ),
                    "evidence": f"Median = {clean.median():,.2f}, IQR = {iqr:,.2f}",
                }
            )
            recommendations.append(
                {
                    "id": f"rec_anomaly_{col}",
                    "priority": "Medium",
                    "category": "Risk & Anomaly Review",
                    "title": f"Audit {len(outliers)} unusual record(s) in '{col}'",
                    "rationale": f"{pct}% of '{col}' values deviate significantly from normal distribution bounds.",
                    "action": "Inspect flagged records using Isolation Forest and Z-Score in Anomaly Detection.",
                    "target_page": "anomaly",
                }
            )
            break

    return safe_json(
        {
            "insights": insights,
            "recommendations": recommendations,
            "summary_counts": {
                "total_insights": len(insights),
                "total_recommendations": len(recommendations),
                "high_priority": sum(1 for r in recommendations if r["priority"] == "High"),
            },
        }
    )
