from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    root_mean_squared_error,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from services.utils import get_column_roles, safe_float, safe_json

CLASSIFICATION_MODELS = {
    "logistic_regression": ("Logistic Regression", lambda: LogisticRegression(max_iter=1000, random_state=42)),
    "decision_tree": ("Decision Tree", lambda: DecisionTreeClassifier(max_depth=8, random_state=42)),
    "random_forest": ("Random Forest", lambda: RandomForestClassifier(n_estimators=120, max_depth=12, random_state=42)),
    "knn": ("K-Nearest Neighbors (KNN)", lambda: KNeighborsClassifier(n_neighbors=5)),
}

REGRESSION_MODELS = {
    "linear_regression": ("Linear Regression", lambda: LinearRegression()),
    "decision_tree_regressor": ("Decision Tree Regressor", lambda: DecisionTreeRegressor(max_depth=8, random_state=42)),
    "random_forest_regressor": ("Random Forest Regressor", lambda: RandomForestRegressor(n_estimators=120, max_depth=12, random_state=42)),
}


def infer_ml_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    roles = get_column_roles(df)
    targets = []
    for col in df.columns:
        role = roles[col]
        nunique = int(df[col].nunique(dropna=True))
        if nunique < 2:
            continue
        if role == "datetime" or role == "text":
            continue
        if role == "numeric":
            suggested = "classification" if nunique <= 10 else "regression"
        else:
            if nunique > 25:
                continue
            suggested = "classification"
        targets.append({"column": col, "role": role, "unique": nunique, "suggested_task": suggested})

    features = [
        {"column": col, "role": roles[col], "missing": int(df[col].isna().sum())}
        for col in df.columns
        if roles[col] != "text" and df[col].nunique(dropna=True) > 1
    ]
    return safe_json({"targets": targets, "features": features})


def _extract_feature_importances(pipeline: Pipeline, num_cols: List[str], cat_cols: List[str]) -> List[Dict[str, Any]]:
    pre: ColumnTransformer = pipeline.named_steps["preprocessor"]
    model = pipeline.named_steps["model"]

    try:
        feature_names = list(pre.get_feature_names_out())
    except Exception:
        feature_names = [f"f_{i}" for i in range(len(num_cols) + len(cat_cols))]

    raw_importances = None
    if hasattr(model, "feature_importances_"):
        raw_importances = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        coef = np.asarray(model.coef_, dtype=float)
        if coef.ndim > 1:
            raw_importances = np.mean(np.abs(coef), axis=0)
        else:
            raw_importances = np.abs(coef)

    if raw_importances is None or len(raw_importances) != len(feature_names):
        return []

    # Aggregate one-hot encoded categorical importances back to original column names
    agg: Dict[str, float] = {}
    for fname, val in zip(feature_names, raw_importances):
        clean_name = fname.split("__", 1)[-1]
        orig_col = clean_name
        for c in cat_cols:
            if clean_name.startswith(f"{c}_"):
                orig_col = c
                break
        agg[orig_col] = agg.get(orig_col, 0.0) + float(val)

    total = sum(agg.values()) or 1.0
    items = [
        {"feature": k, "importance": round(v / total, 4), "raw_score": round(v, 4)}
        for k, v in agg.items()
    ]
    items.sort(key=lambda x: x["importance"], reverse=True)
    return items[:15]


def train_and_evaluate(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: List[str],
    task_type: Optional[str] = None,
    algorithms: Optional[List[str]] = None,
    test_size: float = 0.2,
) -> Dict[str, Any]:
    """
    Train and compare supervised ML models using leakage-free sklearn Pipelines:
    1) Drop missing target rows
    2) Train/test split BEFORE imputation, scaling, or encoding
    3) Fit preprocessing strictly on X_train, evaluate on X_test
    """
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found.")

    clean_features = [c for c in feature_cols if c in df.columns and c != target_col]
    if not clean_features:
        raise ValueError("Select at least one feature column distinct from the target.")

    # Drop rows with missing target
    work = df[clean_features + [target_col]].dropna(subset=[target_col]).copy()
    if len(work) < 20:
        raise ValueError(f"At least 20 valid rows are required for ML training (found {len(work)}).")

    roles = get_column_roles(work)
    # Expand datetime features into numeric year/month/dayofweek safely
    expanded_features: List[str] = []
    for c in list(clean_features):
        if roles.get(c) == "datetime":
            dt = pd.to_datetime(work[c], errors="coerce")
            work[f"{c}_month"] = dt.dt.month
            work[f"{c}_dayofweek"] = dt.dt.dayofweek
            expanded_features.extend([f"{c}_month", f"{c}_dayofweek"])
        else:
            expanded_features.append(c)

    X = work[expanded_features]
    y_raw = work[target_col]

    if not task_type or task_type == "auto":
        if pd.api.types.is_numeric_dtype(y_raw) and not pd.api.types.is_bool_dtype(y_raw) and y_raw.nunique() > 15:
            task = "regression"
        else:
            task = "classification"
    else:
        task = task_type.lower()

    if task not in ("classification", "regression"):
        raise ValueError("task_type must be 'classification' or 'regression'.")

    test_ratio = min(0.4, max(0.1, float(test_size)))

    num_cols = [c for c in expanded_features if pd.api.types.is_numeric_dtype(X[c]) and not pd.api.types.is_bool_dtype(X[c])]
    cat_cols = [c for c in expanded_features if c not in num_cols]

    # Convert booleans in cat_cols to string so OneHotEncoder handles consistently
    for c in cat_cols:
        X.loc[:, c] = X[c].astype("string")

    transformers = []
    if num_cols:
        transformers.append(
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
                num_cols,
            )
        )
    if cat_cols:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore", max_categories=20, sparse_output=False)),
                    ]
                ),
                cat_cols,
            )
        )

    if not transformers:
        raise ValueError("No usable numeric or categorical features remain.")

    results = []
    best_detail = None

    if task == "classification":
        y_str = y_raw.astype(str)
        if y_str.nunique() < 2:
            raise ValueError("Classification requires at least 2 distinct target classes.")
        if y_str.nunique() > 30:
            raise ValueError(f"Target '{target_col}' has {y_str.nunique()} unique values; choose Regression or fewer classes.")

        le = LabelEncoder()
        y_enc = le.fit_transform(y_str)
        class_counts = pd.Series(y_enc).value_counts()
        stratify_arg = y_enc if class_counts.min() >= 2 and len(work) * test_ratio >= len(le.classes_) else None

        X_train, X_test, y_train, y_test = train_test_split(
            X, y_enc, test_size=test_ratio, random_state=42, stratify=stratify_arg
        )

        chosen_algos = [a for a in (algorithms or list(CLASSIFICATION_MODELS.keys())) if a in CLASSIFICATION_MODELS]
        if not chosen_algos:
            chosen_algos = list(CLASSIFICATION_MODELS.keys())

        best_f1 = -1.0
        for key in chosen_algos:
            label, builder = CLASSIFICATION_MODELS[key]
            preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
            pipe = Pipeline([("preprocessor", preprocessor), ("model", builder())])
            pipe.fit(X_train, y_train)
            y_pred = pipe.predict(X_test)

            acc = float(accuracy_score(y_test, y_pred))
            prec = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
            rec = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
            f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
            cm = confusion_matrix(y_test, y_pred, labels=list(range(len(le.classes_))))
            fi = _extract_feature_importances(pipe, num_cols, cat_cols)

            entry = {
                "algorithm_key": key,
                "algorithm": label,
                "accuracy": round(acc, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "confusion_matrix": {
                    "labels": [str(c) for c in le.classes_],
                    "matrix": cm.tolist(),
                },
                "feature_importance": fi,
                "actual_vs_predicted": {
                    "labels": [str(c) for c in le.classes_],
                    "actual_counts": [int((y_test == i).sum()) for i in range(len(le.classes_))],
                    "predicted_counts": [int((y_pred == i).sum()) for i in range(len(le.classes_))],
                },
            }
            results.append(entry)
            if f1 > best_f1:
                best_f1 = f1
                best_detail = entry

        results.sort(key=lambda r: r["f1_score"], reverse=True)

    else:
        y_num = pd.to_numeric(y_raw, errors="coerce")
        valid = y_num.notna()
        X = X.loc[valid]
        y_num = y_num.loc[valid]
        if len(y_num) < 20:
            raise ValueError("Regression requires at least 20 valid numeric target rows.")

        X_train, X_test, y_train, y_test = train_test_split(X, y_num, test_size=test_ratio, random_state=42)

        chosen_algos = [a for a in (algorithms or list(REGRESSION_MODELS.keys())) if a in REGRESSION_MODELS]
        if not chosen_algos:
            chosen_algos = list(REGRESSION_MODELS.keys())

        best_r2 = -1e9
        for key in chosen_algos:
            label, builder = REGRESSION_MODELS[key]
            preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
            pipe = Pipeline([("preprocessor", preprocessor), ("model", builder())])
            pipe.fit(X_train, y_train)
            y_pred = pipe.predict(X_test)

            r2 = float(r2_score(y_test, y_pred))
            mae = float(mean_absolute_error(y_test, y_pred))
            rmse = float(root_mean_squared_error(y_test, y_pred))
            fi = _extract_feature_importances(pipe, num_cols, cat_cols)

            sample_n = min(300, len(y_test))
            entry = {
                "algorithm_key": key,
                "algorithm": label,
                "r2_score": round(r2, 4),
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "feature_importance": fi,
                "actual_vs_predicted": {
                    "actual": [safe_float(v, 3) for v in y_test.iloc[:sample_n].tolist()],
                    "predicted": [safe_float(v, 3) for v in y_pred[:sample_n].tolist()],
                },
            }
            results.append(entry)
            if r2 > best_r2:
                best_r2 = r2
                best_detail = entry

        results.sort(key=lambda r: r["r2_score"], reverse=True)

    return safe_json(
        {
            "task_type": task,
            "target_column": target_col,
            "feature_columns": clean_features,
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "test_size": test_ratio,
            "leakage_prevention": (
                "Train/test split applied prior to fitting median/mode imputers, "
                "StandardScaler, and OneHotEncoder strictly on training data."
            ),
            "best_model": best_detail,
            "models": results,
        }
    )
