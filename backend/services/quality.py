from typing import Any, Dict, List

import numpy as np
import pandas as pd

from services.utils import get_numeric_columns, safe_json

NON_NEGATIVE_HINTS = ("qty", "quantity", "price", "revenue", "sales", "amount", "cost", "age", "count", "units")


def analyze_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluate dataset quality transparently across 4 weighted dimensions:
    1. Completeness (35%): ratio of non-missing cells
    2. Uniqueness (20%): ratio of non-duplicate rows
    3. Validity & Consistency (25%): absence of empty/constant cols, whitespace, mixed types, invalid negatives
    4. Outlier Integrity (20%): absence of extreme IQR outliers (3 * IQR)
    """
    n_rows, n_cols = df.shape
    total_cells = max(n_rows * n_cols, 1)
    issues: List[Dict[str, Any]] = []

    # 1. Missing values per column
    total_missing = int(df.isna().sum().sum())
    for col in df.columns:
        miss = int(df[col].isna().sum())
        if miss > 0:
            pct = round((miss / max(n_rows, 1)) * 100, 2)
            severity = "High" if pct >= 20 else ("Medium" if pct >= 5 else "Low")
            is_num = pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col])
            strategy = "median" if is_num else "mode"
            issues.append(
                {
                    "id": f"missing_{col}",
                    "category": "Missing Data",
                    "problem": f"Column '{col}' has {miss} missing values ({pct}%).",
                    "column": col,
                    "affected_records": miss,
                    "severity": severity,
                    "recommended_solution": (
                        f"Fill missing values using {strategy} imputation or drop incomplete rows in Cleaning Studio."
                    ),
                    "suggested_action": {
                        "operation": "fill_missing",
                        "params": {"column": col, "strategy": strategy},
                    },
                }
            )

    # 2. Duplicate records
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        dup_pct = round((dup_count / max(n_rows, 1)) * 100, 2)
        issues.append(
            {
                "id": "duplicates",
                "category": "Duplicate Records",
                "problem": f"Dataset contains {dup_count} exact duplicate rows ({dup_pct}%).",
                "column": "All Columns",
                "affected_records": dup_count,
                "severity": "High" if dup_pct >= 5 else "Medium",
                "recommended_solution": "Remove duplicate rows while keeping the first occurrence.",
                "suggested_action": {"operation": "remove_duplicates", "params": {}},
            }
        )

    # 3. Empty columns, Constant columns, Whitespace, Mixed Types, Invalid Values
    validity_flagged_cells = 0
    for col in df.columns:
        s = df[col]
        non_null = s.dropna()

        # Empty column
        if non_null.empty:
            validity_flagged_cells += n_rows
            issues.append(
                {
                    "id": f"empty_{col}",
                    "category": "Empty Column",
                    "problem": f"Column '{col}' is completely empty (100% missing).",
                    "column": col,
                    "affected_records": n_rows,
                    "severity": "High",
                    "recommended_solution": f"Drop empty column '{col}' as it carries no information.",
                    "suggested_action": {"operation": "drop_columns", "params": {"columns": [col]}},
                }
            )
            continue

        # Constant column
        if non_null.nunique() <= 1 and n_rows > 1:
            validity_flagged_cells += n_rows
            issues.append(
                {
                    "id": f"constant_{col}",
                    "category": "Constant Column",
                    "problem": f"Column '{col}' has only 1 unique value ('{non_null.iloc[0]}') across all rows.",
                    "column": col,
                    "affected_records": n_rows,
                    "severity": "Low",
                    "recommended_solution": f"Consider removing constant column '{col}' before ML modeling.",
                    "suggested_action": {"operation": "drop_columns", "params": {"columns": [col]}},
                }
            )

        # String/object-column checks: trailing/leading whitespace & mixed numeric/text types
        if s.dtype == object or pd.api.types.is_string_dtype(s):
            str_vals = non_null.astype(str)
            ws_mask = str_vals != str_vals.str.strip()
            ws_count = int(ws_mask.sum())
            if ws_count > 0:
                validity_flagged_cells += ws_count
                issues.append(
                    {
                        "id": f"whitespace_{col}",
                        "category": "Inconsistent Formatting",
                        "problem": f"Column '{col}' has {ws_count} values with leading/trailing whitespace.",
                        "column": col,
                        "affected_records": ws_count,
                        "severity": "Medium",
                        "recommended_solution": f"Trim whitespace in '{col}' to prevent duplicate category splits.",
                        "suggested_action": {"operation": "trim_spaces", "params": {"column": col}},
                    }
                )

            # Inconsistent/mixed data type detection (e.g. mostly numbers stored as text with a few bad strings)
            stripped = str_vals.str.strip()
            numeric_parsed = pd.to_numeric(stripped, errors="coerce")
            num_ratio = float(numeric_parsed.notna().mean())
            if 0.6 <= num_ratio < 1.0:
                bad_count = int(numeric_parsed.isna().sum())
                validity_flagged_cells += bad_count
                issues.append(
                    {
                        "id": f"mixed_type_{col}",
                        "category": "Inconsistent Data Type",
                        "problem": (
                            f"Column '{col}' is stored as text; {round(num_ratio*100,1)}% values are numeric "
                            f"but {bad_count} entries are non-numeric."
                        ),
                        "column": col,
                        "affected_records": bad_count,
                        "severity": "High",
                        "recommended_solution": f"Convert '{col}' to numeric dtype (invalid entries become NaN for cleaning).",
                        "suggested_action": {
                            "operation": "change_dtype",
                            "params": {"column": col, "target_dtype": "numeric"},
                        },
                    }
                )

        # Invalid negative values for strictly positive domain columns
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            col_lower = str(col).lower()
            if any(hint in col_lower for hint in NON_NEGATIVE_HINTS):
                neg_count = int((non_null < 0).sum())
                if neg_count > 0:
                    validity_flagged_cells += neg_count
                    issues.append(
                        {
                            "id": f"invalid_neg_{col}",
                            "category": "Invalid Value",
                            "problem": f"Column '{col}' contains {neg_count} negative value(s), which is unusual for '{col}'.",
                            "column": col,
                            "affected_records": neg_count,
                            "severity": "High",
                            "recommended_solution": f"Inspect and filter out negative values in '{col}' (e.g., keep {col} >= 0).",
                            "suggested_action": {
                                "operation": "filter_rows",
                                "params": {"column": col, "operator": "gte", "value": "0"},
                            },
                        }
                    )

    # 4. Suspicious Outliers (1.5*IQR flagged, 3*IQR extreme used in score)
    numeric_cols = get_numeric_columns(df)
    total_numeric_cells = 0
    extreme_outlier_cells = 0

    for col in numeric_cols:
        clean = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(clean) < 10:
            continue
        total_numeric_cells += len(clean)
        q1 = float(clean.quantile(0.25))
        q3 = float(clean.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            continue
        mild_outliers = int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
        extreme_outliers = int(((clean < q1 - 3.0 * iqr) | (clean > q3 + 3.0 * iqr)).sum())
        extreme_outlier_cells += extreme_outliers

        if mild_outliers > 0:
            pct = round((mild_outliers / len(clean)) * 100, 2)
            issues.append(
                {
                    "id": f"outlier_{col}",
                    "category": "Suspicious Outliers",
                    "problem": (
                        f"Column '{col}' has {mild_outliers} IQR outlier(s) ({pct}%), "
                        f"including {extreme_outliers} extreme outlier(s) beyond 3×IQR."
                    ),
                    "column": col,
                    "affected_records": mild_outliers,
                    "severity": "Medium" if extreme_outliers > 0 else "Low",
                    "recommended_solution": f"Inspect in Anomaly Detection or cap/winsorize '{col}' using IQR bounds.",
                    "suggested_action": {
                        "operation": "handle_outliers",
                        "params": {"column": col, "method": "cap_iqr", "factor": 1.5},
                    },
                }
            )

    # Transparent score computation
    completeness_score = 100.0 * (1.0 - (total_missing / total_cells))
    uniqueness_score = 100.0 * (1.0 - (dup_count / max(n_rows, 1)))
    validity_score = max(0.0, 100.0 * (1.0 - min(1.0, validity_flagged_cells / total_cells * 3.0)))
    outlier_score = (
        100.0 * (1.0 - min(1.0, (extreme_outlier_cells / max(total_numeric_cells, 1)) * 5.0))
        if total_numeric_cells > 0
        else 100.0
    )

    overall_score = round(
        0.35 * completeness_score
        + 0.20 * uniqueness_score
        + 0.25 * validity_score
        + 0.20 * outlier_score,
        1,
    )

    grade = (
        "Excellent"
        if overall_score >= 90
        else ("Good" if overall_score >= 75 else ("Fair" if overall_score >= 55 else "Needs Cleaning"))
    )

    severity_counts = {
        "High": sum(1 for i in issues if i["severity"] == "High"),
        "Medium": sum(1 for i in issues if i["severity"] == "Medium"),
        "Low": sum(1 for i in issues if i["severity"] == "Low"),
    }

    # Sort High -> Medium -> Low
    sev_order = {"High": 0, "Medium": 1, "Low": 2}
    issues.sort(key=lambda x: (sev_order.get(x["severity"], 3), -x["affected_records"]))

    return safe_json(
        {
            "quality_score": overall_score,
            "grade": grade,
            "formula": "0.35 × Completeness + 0.20 × Uniqueness + 0.25 × Validity + 0.20 × Outlier Integrity",
            "score_breakdown": [
                {
                    "dimension": "Completeness",
                    "weight": "35%",
                    "score": round(completeness_score, 1),
                    "detail": f"{total_missing} missing cells out of {total_cells} total cells",
                },
                {
                    "dimension": "Uniqueness",
                    "weight": "20%",
                    "score": round(uniqueness_score, 1),
                    "detail": f"{dup_count} duplicate rows out of {n_rows} total rows",
                },
                {
                    "dimension": "Validity & Consistency",
                    "weight": "25%",
                    "score": round(validity_score, 1),
                    "detail": f"{validity_flagged_cells} cells flagged for invalid, constant, whitespace, or mixed-type issues",
                },
                {
                    "dimension": "Outlier Integrity",
                    "weight": "20%",
                    "score": round(outlier_score, 1),
                    "detail": f"{extreme_outlier_cells} extreme (>3×IQR) values across {total_numeric_cells} numeric cells",
                },
            ],
            "severity_counts": severity_counts,
            "total_issues": len(issues),
            "issues": issues,
        }
    )
