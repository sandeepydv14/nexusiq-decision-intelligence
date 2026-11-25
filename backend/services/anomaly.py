from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from services.utils import get_numeric_columns, safe_float, safe_json


def detect_anomalies(
    df: pd.DataFrame,
    method: str = "iqr",
    columns: Optional[List[str]] = None,
    threshold: float = 1.5,
    contamination: float = 0.05,
) -> Dict[str, Any]:
    """Run real anomaly detection using IQR, Z-score, or Isolation Forest."""
    numeric_cols = get_numeric_columns(df)
    if not numeric_cols:
        raise ValueError("Dataset has no numerical columns available for anomaly detection.")

    selected = [c for c in (columns or []) if c in numeric_cols]
    if not selected:
        selected = [c for c in numeric_cols if "id" not in c.lower()][:4] or numeric_cols[:3]

    work = df[selected].apply(pd.to_numeric, errors="coerce")
    valid_mask = work.notna().any(axis=1)
    if valid_mask.sum() < 5:
        raise ValueError("Need at least 5 non-null numeric rows for anomaly detection.")

    reasons: Dict[int, List[str]] = {idx: [] for idx in df.index}
    scores = pd.Series(0.0, index=df.index)
    is_anomaly = pd.Series(False, index=df.index)

    method_lower = method.lower()
    if method_lower == "iqr":
        factor = float(threshold) if threshold > 0 else 1.5
        bounds_info = {}
        for col in selected:
            s = work[col].dropna()
            if len(s) < 4:
                continue
            q1 = float(s.quantile(0.25))
            q3 = float(s.quantile(0.75))
            iqr = q3 - q1
            if iqr <= 0:
                continue
            low = q1 - factor * iqr
            high = q3 + factor * iqr
            bounds_info[col] = {"low": round(low, 3), "high": round(high, 3)}
            col_mask = (work[col] < low) | (work[col] > high)
            for idx in df.index[col_mask.fillna(False)]:
                val = work.loc[idx, col]
                direction = "below lower" if val < low else "above upper"
                reasons[idx].append(f"{col}={val:.2f} ({direction} bound [{low:.2f}, {high:.2f}])")
                dist = abs(val - (low if val < low else high)) / iqr
                scores.loc[idx] = max(scores.loc[idx], float(dist))
                is_anomaly.loc[idx] = True

        explanation = (
            f"Interquartile Range (IQR × {factor}) evaluated {len(selected)} column(s). "
            f"Values falling outside [Q1 − {factor}×IQR, Q3 + {factor}×IQR] are flagged."
        )

    elif method_lower == "zscore":
        z_thresh = float(threshold) if threshold > 0 else 3.0
        for col in selected:
            s = work[col].dropna()
            if len(s) < 4:
                continue
            mean_v = float(s.mean())
            std_v = float(s.std(ddof=1))
            if std_v <= 0:
                continue
            z = (work[col] - mean_v) / std_v
            col_mask = z.abs() > z_thresh
            for idx in df.index[col_mask.fillna(False)]:
                zv = float(z.loc[idx])
                reasons[idx].append(f"{col}={work.loc[idx, col]:.2f} (z={zv:+.2f}, |z|>{z_thresh})")
                scores.loc[idx] = max(scores.loc[idx], abs(zv))
                is_anomaly.loc[idx] = True

        explanation = (
            f"Z-Score analysis standardized each selected feature (mean=0, std=1). "
            f"Records with |z| > {z_thresh} standard deviations from the mean are flagged."
        )

    elif method_lower == "isolation_forest":
        contam = min(0.4, max(0.01, float(contamination)))
        sub = work.loc[valid_mask]
        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        X_imputed = imputer.fit_transform(sub)
        X_scaled = scaler.fit_transform(X_imputed)

        iso = IsolationForest(contamination=contam, random_state=42, n_estimators=150)
        preds = iso.fit_predict(X_scaled)
        raw_scores = -iso.decision_function(X_scaled)  # higher = more anomalous

        for pos, idx in enumerate(sub.index):
            scores.loc[idx] = float(raw_scores[pos])
            if preds[pos] == -1:
                is_anomaly.loc[idx] = True
                # Identify top contributing features via absolute z-score
                abs_z = np.abs(X_scaled[pos])
                top_i = int(np.argmax(abs_z))
                top_col = selected[top_i]
                reasons[idx].append(
                    f"Multivariate isolation score={raw_scores[pos]:.3f}; primary driver {top_col}={X_imputed[pos, top_i]:.2f} (|z|={abs_z[top_i]:.2f})"
                )

        explanation = (
            f"Isolation Forest trained 150 isolation trees across {len(selected)} scaled feature(s) "
            f"with contamination={contam:.2f}. Records isolated in shorter tree paths are flagged."
        )
    else:
        raise ValueError(f"Unsupported anomaly method '{method}'. Choose iqr, zscore, or isolation_forest.")

    flagged_indices = df.index[is_anomaly].tolist()
    anomaly_count = len(flagged_indices)
    total_records = len(df)
    anomaly_pct = round((anomaly_count / max(total_records, 1)) * 100, 2)

    # Sort flagged records by severity score descending
    flagged_indices.sort(key=lambda i: float(scores.loc[i]), reverse=True)
    display_cols = list(df.columns)
    anomalous_records = []
    for idx in flagged_indices[:100]:
        rec = {
            "_row_index": int(idx) if isinstance(idx, (int, np.integer)) else str(idx),
            "_anomaly_score": safe_float(scores.loc[idx], 3),
            "_reason": "; ".join(reasons[idx]),
        }
        for c in display_cols:
            rec[c] = safe_json(df.loc[idx, c])
        anomalous_records.append(rec)

    # Chart data: 2D scatter if >=2 columns selected, else 1D index vs value
    sample_idx = df.index[:1500]
    if len(selected) >= 2:
        x_col, y_col = selected[0], selected[1]
        normal_mask = (~is_anomaly).loc[sample_idx]
        anom_mask = is_anomaly.loc[sample_idx]
        chart_data = {
            "type": "scatter2d",
            "x_col": x_col,
            "y_col": y_col,
            "normal": {
                "x": [safe_json(v) for v in work.loc[sample_idx[normal_mask], x_col]],
                "y": [safe_json(v) for v in work.loc[sample_idx[normal_mask], y_col]],
            },
            "anomaly": {
                "x": [safe_json(v) for v in work.loc[sample_idx[anom_mask], x_col]],
                "y": [safe_json(v) for v in work.loc[sample_idx[anom_mask], y_col]],
                "text": ["; ".join(reasons[i]) for i in sample_idx[anom_mask]],
            },
        }
    else:
        x_col = selected[0]
        normal_mask = (~is_anomaly).loc[sample_idx]
        anom_mask = is_anomaly.loc[sample_idx]
        chart_data = {
            "type": "scatter1d",
            "y_col": x_col,
            "normal": {
                "x": [int(i) for i in sample_idx[normal_mask]],
                "y": [safe_json(v) for v in work.loc[sample_idx[normal_mask], x_col]],
            },
            "anomaly": {
                "x": [int(i) for i in sample_idx[anom_mask]],
                "y": [safe_json(v) for v in work.loc[sample_idx[anom_mask], x_col]],
                "text": ["; ".join(reasons[i]) for i in sample_idx[anom_mask]],
            },
        }

    return safe_json(
        {
            "method": method_lower,
            "selected_columns": selected,
            "available_numeric_columns": numeric_cols,
            "total_records": total_records,
            "anomaly_count": anomaly_count,
            "anomaly_pct": anomaly_pct,
            "explanation": explanation,
            "anomalous_records": anomalous_records,
            "columns": display_cols,
            "chart": chart_data,
        }
    )
