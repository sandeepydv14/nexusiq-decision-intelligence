import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from config import WORKING_DIR
from database.db import (
    add_cleaning_operation,
    deactivate_all_cleaning_operations,
    get_cleaning_operations,
    log_activity,
    pop_last_cleaning_operation,
)
from services.dataset_manager import load_original_df, load_working_df, save_working_df
from services.quality import analyze_data_quality
from services.utils import safe_json


def _apply_operation_to_df(df: pd.DataFrame, operation: str, params: Dict[str, Any]) -> Tuple[pd.DataFrame, str]:
    """Pure transformation returning (new_df, human_readable_summary)."""
    out = df.copy()

    if operation == "remove_duplicates":
        before = len(out)
        subset = params.get("subset") or None
        if subset == ["__all__"]:
            subset = None
        out = out.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
        removed = before - len(out)
        return out, f"Removed {removed} duplicate row(s)."

    if operation == "fill_missing":
        col = params.get("column", "__all__")
        strategy = params.get("strategy", "median")
        custom_val = params.get("value")
        cols = list(out.columns) if col == "__all__" else [col]
        filled_total = 0
        for c in cols:
            if c not in out.columns:
                raise ValueError(f"Column '{c}' not found.")
            miss = int(out[c].isna().sum())
            if miss == 0:
                continue
            if strategy == "mean":
                if not pd.api.types.is_numeric_dtype(out[c]):
                    if col != "__all__":
                        raise ValueError(f"Mean imputation requires a numeric column ('{c}' is {out[c].dtype}).")
                    continue
                fill_v = out[c].mean()
            elif strategy == "median":
                if not pd.api.types.is_numeric_dtype(out[c]):
                    if col != "__all__":
                        raise ValueError(f"Median imputation requires a numeric column ('{c}' is {out[c].dtype}).")
                    continue
                fill_v = out[c].median()
            elif strategy == "mode":
                m = out[c].dropna().mode()
                if m.empty:
                    continue
                fill_v = m.iloc[0]
            elif strategy == "constant":
                if custom_val is None or str(custom_val) == "":
                    raise ValueError("Provide a replacement value for constant imputation.")
                fill_v = custom_val
            else:
                raise ValueError(f"Unsupported imputation strategy: {strategy}")
            out[c] = out[c].fillna(fill_v)
            filled_total += miss
        target_label = "all eligible columns" if col == "__all__" else f"'{col}'"
        return out, f"Filled {filled_total} missing cell(s) in {target_label} using {strategy}."

    if operation == "drop_missing":
        col = params.get("column", "__all__")
        before = len(out)
        if col == "__all__":
            out = out.dropna().reset_index(drop=True)
        else:
            if col not in out.columns:
                raise ValueError(f"Column '{col}' not found.")
            out = out.dropna(subset=[col]).reset_index(drop=True)
        removed = before - len(out)
        return out, f"Dropped {removed} row(s) with missing values ({col})."

    if operation == "rename_column":
        col = params.get("column")
        new_name = str(params.get("new_name", "")).strip()
        if not col or col not in out.columns:
            raise ValueError(f"Column '{col}' not found.")
        if not new_name:
            raise ValueError("New column name cannot be empty.")
        if new_name in out.columns and new_name != col:
            raise ValueError(f"Column '{new_name}' already exists.")
        out = out.rename(columns={col: new_name})
        return out, f"Renamed column '{col}' to '{new_name}'."

    if operation == "change_dtype":
        col = params.get("column")
        target = params.get("target_dtype")
        if col not in out.columns:
            raise ValueError(f"Column '{col}' not found.")
        if target == "numeric":
            out[col] = pd.to_numeric(out[col], errors="coerce")
        elif target == "integer":
            out[col] = pd.to_numeric(out[col], errors="coerce").round().astype("Int64")
        elif target == "string":
            out[col] = out[col].astype("string")
        elif target == "boolean":
            out[col] = out[col].astype(bool)
        elif target == "datetime":
            out[col] = pd.to_datetime(out[col], errors="coerce", format="mixed")
        else:
            raise ValueError(f"Unsupported target dtype: {target}")
        return out, f"Converted column '{col}' data type to {target}."

    if operation == "convert_dates":
        col = params.get("column")
        fmt = params.get("date_format") or None
        if col not in out.columns:
            raise ValueError(f"Column '{col}' not found.")
        if fmt:
            out[col] = pd.to_datetime(out[col], format=fmt, errors="coerce")
        else:
            out[col] = pd.to_datetime(out[col], errors="coerce", format="mixed")
        valid_count = int(out[col].notna().sum())
        return out, f"Parsed '{col}' as datetime ({valid_count} valid timestamps)."

    if operation == "trim_spaces":
        col = params.get("column", "__all__")
        norm_case = params.get("normalize_case", "none")
        cols = [c for c in out.columns if out[c].dtype == object or pd.api.types.is_string_dtype(out[c])] if col == "__all__" else [col]
        changed_cells = 0
        for c in cols:
            if c not in out.columns:
                raise ValueError(f"Column '{c}' not found.")
            mask = out[c].notna()
            before_s = out.loc[mask, c].astype(str)
            after_s = before_s.str.strip().str.replace(r"\s+", " ", regex=True)
            if norm_case == "title":
                after_s = after_s.str.title()
            elif norm_case == "upper":
                after_s = after_s.str.upper()
            elif norm_case == "lower":
                after_s = after_s.str.lower()
            changed_cells += int((before_s != after_s).sum())
            out.loc[mask, c] = after_s
        return out, f"Trimmed whitespace in {len(cols)} column(s) ({changed_cells} cells updated)."

    if operation == "drop_columns":
        cols = params.get("columns") or []
        if isinstance(cols, str):
            cols = [cols]
        missing_cols = [c for c in cols if c not in out.columns]
        if missing_cols:
            raise ValueError(f"Columns not found: {missing_cols}")
        if len(cols) >= len(out.columns):
            raise ValueError("Cannot drop all columns from the dataset.")
        out = out.drop(columns=cols)
        return out, f"Removed {len(cols)} column(s): {', '.join(cols)}."

    if operation == "filter_rows":
        col = params.get("column")
        op = params.get("operator", "not_null")
        val = params.get("value", "")
        if col not in out.columns:
            raise ValueError(f"Column '{col}' not found.")
        before = len(out)
        s = out[col]
        if op == "not_null":
            out = out[s.notna()]
        elif op == "contains":
            out = out[s.astype(str).str.contains(str(val), case=False, na=False)]
        elif op in ("eq", "neq", "gt", "gte", "lt", "lte"):
            if pd.api.types.is_numeric_dtype(s):
                num_val = float(val)
                if op == "eq":
                    out = out[s == num_val]
                elif op == "neq":
                    out = out[s != num_val]
                elif op == "gt":
                    out = out[s > num_val]
                elif op == "gte":
                    out = out[s >= num_val]
                elif op == "lt":
                    out = out[s < num_val]
                elif op == "lte":
                    out = out[s <= num_val]
            else:
                str_s = s.astype(str)
                if op == "eq":
                    out = out[str_s == str(val)]
                elif op == "neq":
                    out = out[str_s != str(val)]
                else:
                    raise ValueError(f"Operator '{op}' requires a numeric column.")
        else:
            raise ValueError(f"Unsupported filter operator: {op}")
        out = out.reset_index(drop=True)
        return out, f"Filtered '{col}' ({op} {val}): kept {len(out)} of {before} rows."

    if operation == "handle_outliers":
        col = params.get("column")
        method = params.get("method", "cap_iqr")
        factor = float(params.get("factor", 1.5))
        if col not in out.columns:
            raise ValueError(f"Column '{col}' not found.")
        if not pd.api.types.is_numeric_dtype(out[col]):
            raise ValueError(f"Outlier handling requires a numeric column ('{col}' is not numeric).")
        clean = out[col].dropna()
        q1 = float(clean.quantile(0.25))
        q3 = float(clean.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            return out, f"No IQR spread detected in '{col}'; 0 rows modified."
        low = q1 - factor * iqr
        high = q3 + factor * iqr
        mask = (out[col] < low) | (out[col] > high)
        affected = int(mask.sum())
        if method == "cap_iqr":
            out[col] = out[col].clip(lower=low, upper=high)
            return out, f"Capped {affected} outlier(s) in '{col}' to [{low:.2f}, {high:.2f}]."
        if method == "remove_iqr":
            out = out[~mask.fillna(False)].reset_index(drop=True)
            return out, f"Removed {affected} outlier row(s) in '{col}' outside [{low:.2f}, {high:.2f}]."
        raise ValueError(f"Unsupported outlier handling method: {method}")

    raise ValueError(f"Unknown cleaning operation: {operation}")


def preview_cleaning_operation(dataset_id: str, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    df = load_working_df(dataset_id)
    new_df, summary = _apply_operation_to_df(df, operation, params)

    before_stats = {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "missing": int(df.isna().sum().sum()),
        "duplicates": int(df.duplicated().sum()),
    }
    after_stats = {
        "rows": int(new_df.shape[0]),
        "cols": int(new_df.shape[1]),
        "missing": int(new_df.isna().sum().sum()),
        "duplicates": int(new_df.duplicated().sum()),
    }

    sample_rows = [
        {c: safe_json(row[c]) for c in new_df.columns}
        for _, row in new_df.head(8).iterrows()
    ]

    return safe_json(
        {
            "summary": summary,
            "before": before_stats,
            "after": after_stats,
            "preview_columns": list(new_df.columns),
            "preview_rows": sample_rows,
        }
    )


def apply_cleaning_operation(dataset_id: str, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    df = load_working_df(dataset_id)
    new_df, summary = _apply_operation_to_df(df, operation, params)

    # Save snapshot of BEFORE state for exact undo
    snapshot_path = WORKING_DIR / f"{dataset_id}_undo_{uuid.uuid4().hex[:8]}.pkl"
    df.to_pickle(snapshot_path)

    add_cleaning_operation(
        dataset_id=dataset_id,
        operation=operation,
        params=params,
        summary=summary,
        snapshot_path=str(snapshot_path),
        rows_before=int(df.shape[0]),
        rows_after=int(new_df.shape[0]),
        cols_before=int(df.shape[1]),
        cols_after=int(new_df.shape[1]),
    )

    quality = analyze_data_quality(new_df)
    save_working_df(dataset_id, new_df, quality_score=quality["quality_score"])
    log_activity("CLEANING", summary, dataset_id)

    return safe_json(
        {
            "summary": summary,
            "row_count": int(new_df.shape[0]),
            "col_count": int(new_df.shape[1]),
            "quality_score": quality["quality_score"],
            "history": get_cleaning_operations(dataset_id, active_only=True),
        }
    )


def undo_cleaning_operation(dataset_id: str) -> Dict[str, Any]:
    op = pop_last_cleaning_operation(dataset_id)
    if not op:
        raise ValueError("No cleaning operations to undo.")
    snapshot_path = Path(op["snapshot_path"])
    if not snapshot_path.exists():
        raise FileNotFoundError("Undo snapshot file is missing.")
    restored_df = pd.read_pickle(snapshot_path)
    snapshot_path.unlink(missing_ok=True)

    quality = analyze_data_quality(restored_df)
    save_working_df(dataset_id, restored_df, quality_score=quality["quality_score"])
    log_activity("UNDO_CLEANING", f"Undid: {op['summary']}", dataset_id)

    return safe_json(
        {
            "undone": op["summary"],
            "row_count": int(restored_df.shape[0]),
            "col_count": int(restored_df.shape[1]),
            "quality_score": quality["quality_score"],
            "history": get_cleaning_operations(dataset_id, active_only=True),
        }
    )


def reset_to_original(dataset_id: str) -> Dict[str, Any]:
    orig_df = load_original_df(dataset_id)
    ops = get_cleaning_operations(dataset_id, active_only=True)
    for op in ops:
        Path(op["snapshot_path"]).unlink(missing_ok=True)
    deactivate_all_cleaning_operations(dataset_id)

    quality = analyze_data_quality(orig_df)
    save_working_df(dataset_id, orig_df, quality_score=quality["quality_score"])
    log_activity("RESET_DATASET", "Reset working dataset back to original uploaded state", dataset_id)

    return safe_json(
        {
            "summary": "Dataset reset to original uploaded version.",
            "row_count": int(orig_df.shape[0]),
            "col_count": int(orig_df.shape[1]),
            "quality_score": quality["quality_score"],
            "history": [],
        }
    )
