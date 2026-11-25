import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import ALLOWED_EXTENSIONS, UPLOAD_DIR, WORKING_DIR, ensure_directories
from database.db import (
    create_dataset_record,
    deactivate_all_cleaning_operations,
    delete_dataset_record,
    get_dataset,
    list_datasets,
    log_activity,
    update_dataset_stats,
)
from services.utils import get_column_roles, safe_json, try_parse_datetime


def _read_file_to_df(
    file_path: Path, ext: str, sheet_name: Optional[str] = None
) -> Tuple[pd.DataFrame, Optional[str], List[str]]:
    if ext == ".csv":
        last_err = None
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(file_path, encoding=enc)
                return df, None, []
            except UnicodeDecodeError as exc:
                last_err = exc
        raise ValueError(f"Unable to decode CSV file: {last_err}")

    if ext in (".xlsx", ".xls"):
        engine = "openpyxl" if ext == ".xlsx" else "xlrd"
        excel = pd.ExcelFile(file_path, engine=engine)
        sheets = list(excel.sheet_names)
        if not sheets:
            raise ValueError("Excel workbook contains no sheets.")
        chosen = sheet_name if sheet_name in sheets else sheets[0]
        df = pd.read_excel(file_path, sheet_name=chosen, engine=engine)
        return df, chosen, sheets

    raise ValueError(f"Unsupported file extension: {ext}")


def _auto_parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            # Auto-convert clean date columns whose column name hints at date or >=90% parse cleanly
            parsed = try_parse_datetime(df[col])
            non_null_ratio = df[col].notna().mean()
            if non_null_ratio > 0 and parsed.notna().mean() >= 0.9 * non_null_ratio:
                col_lower = str(col).lower()
                if any(k in col_lower for k in ("date", "time", "day", "month", "year", "dt")) or (
                    df[col].dropna().astype(str).str.contains(r"[-/]").mean() > 0.8
                ):
                    df[col] = parsed
    return df


def save_uploaded_dataset(file_storage, custom_name: Optional[str] = None) -> Dict[str, Any]:
    ensure_directories()
    filename = file_storage.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type '{ext}'. Allowed types: CSV, XLSX, XLS.")

    dataset_id = uuid.uuid4().hex[:12]
    safe_filename = f"{dataset_id}{ext}"
    original_path = UPLOAD_DIR / safe_filename
    file_storage.save(str(original_path))

    if original_path.stat().st_size == 0:
        original_path.unlink(missing_ok=True)
        raise ValueError("Uploaded file is empty (0 bytes).")

    try:
        df, chosen_sheet, sheets = _read_file_to_df(original_path, ext)
    except Exception as exc:
        original_path.unlink(missing_ok=True)
        raise ValueError(f"Failed to parse file: {exc}") from exc

    if df.empty or df.shape[1] == 0:
        original_path.unlink(missing_ok=True)
        raise ValueError("Dataset contains no rows or columns.")

    # Normalize column names to strings
    df.columns = [str(c).strip() if str(c).strip() else f"Column_{i}" for i, c in enumerate(df.columns)]
    df = _auto_parse_dates(df)

    original_snapshot_path = WORKING_DIR / f"{dataset_id}_original.pkl"
    working_path = WORKING_DIR / f"{dataset_id}_working.pkl"
    df.to_pickle(original_snapshot_path)
    df.to_pickle(working_path)

    display_name = (custom_name or Path(filename).stem).strip() or f"Dataset_{dataset_id}"
    record = {
        "id": dataset_id,
        "name": display_name,
        "original_filename": filename,
        "file_type": ext.lstrip(".").upper(),
        "sheet_name": chosen_sheet,
        "available_sheets": sheets,
        "is_demo": False,
        "original_path": str(original_path),
        "working_path": str(working_path),
        "row_count": int(df.shape[0]),
        "col_count": int(df.shape[1]),
        "original_row_count": int(df.shape[0]),
        "original_col_count": int(df.shape[1]),
    }
    create_dataset_record(record)
    log_activity("UPLOAD", f"Uploaded dataset '{display_name}' ({df.shape[0]} rows, {df.shape[1]} cols)", dataset_id)
    return get_dataset(dataset_id)


def create_demo_dataset() -> Dict[str, Any]:
    """Generate a realistic retail sales demo dataset with intentional quality flaws."""
    ensure_directories()
    # Reuse existing demo dataset if already loaded
    for existing in list_datasets():
        if existing["is_demo"]:
            return existing

    rng = np.random.default_rng(42)
    n_base = 400
    dates = pd.date_range("2025-01-01", periods=n_base, freq="D")

    catalog = {
        "Electronics": [
            ("Wireless Headphones", 120, 0.34),
            ("Smart Watch Pro", 240, 0.30),
            ("USB-C Docking Hub", 85, 0.40),
            ("4K Portable Monitor", 360, 0.26),
        ],
        "Office Supplies": [
            ("Ergonomic Chair", 290, 0.28),
            ("Standing Desk Mat", 55, 0.45),
            ("Mechanical Keyboard", 110, 0.36),
            ("LED Desk Lamp", 48, 0.42),
        ],
        "Home & Living": [
            ("Air Purifier X2", 195, 0.32),
            ("Smart Thermostat", 160, 0.35),
            ("Espresso Brewer", 210, 0.29),
        ],
        "Accessories": [
            ("Laptop Sleeve 15in", 35, 0.50),
            ("GaN Fast Charger", 45, 0.46),
            ("Webcam HD 1080p", 78, 0.38),
        ],
    }

    regions = ["North", "South", "East", "West"]
    region_weights = [0.28, 0.22, 0.20, 0.30]
    segments = ["Consumer", "Corporate", "Home Office"]
    seg_weights = [0.50, 0.32, 0.18]

    rows = []
    for i in range(n_base):
        dt = dates[i]
        # Seasonal uplift toward Q4
        month_factor = 1.0 + 0.04 * (dt.month - 1)
        cat = rng.choice(list(catalog.keys()), p=[0.36, 0.26, 0.20, 0.18])
        products = catalog[cat]
        prod_name, base_price, base_margin = products[int(rng.integers(0, len(products)))]
        region = str(rng.choice(regions, p=region_weights))
        segment = str(rng.choice(segments, p=seg_weights))

        qty = int(rng.integers(1, 12))
        if segment == "Corporate":
            qty += int(rng.integers(1, 6))

        discount = float(np.round(rng.choice([0.0, 0.05, 0.10, 0.15, 0.20, 0.25], p=[0.30, 0.20, 0.22, 0.15, 0.08, 0.05]), 2))
        # West region slightly higher volume/revenue
        reg_mult = 1.15 if region == "West" else (0.90 if region == "East" else 1.0)
        unit_price = base_price * month_factor * reg_mult * rng.uniform(0.92, 1.08)
        revenue = round(qty * unit_price * (1.0 - discount), 2)
        # Higher discount erodes profit margin
        effective_margin = base_margin - discount * 0.85 + rng.normal(0, 0.03)
        profit = round(revenue * effective_margin, 2)

        rows.append(
            {
                "Order_ID": f"ORD-{1001 + i}",
                "Date": dt.strftime("%Y-%m-%d"),
                "Product": prod_name,
                "Category": cat,
                "Region": region,
                "Quantity": qty,
                "Revenue": revenue,
                "Discount": discount,
                "Profit": profit,
                "Customer_Segment": segment,
                "Currency": "USD",  # Intentional constant column for quality check
            }
        )

    df = pd.DataFrame(rows)

    # Inject realistic data quality issues for demonstration
    # 1. Missing values (~18 cells)
    df.loc[[12, 45, 108, 215, 310], "Revenue"] = np.nan
    df.loc[[23, 88, 174, 290], "Discount"] = np.nan
    df.loc[[31, 95, 160, 240, 355], "Customer_Segment"] = np.nan
    df.loc[[52, 142, 275], "Region"] = np.nan

    # 2. Trailing spaces / messy text in categorical columns
    df.loc[[5, 19, 77, 130], "Region"] = "  West "
    df.loc[[14, 66, 185], "Category"] = " Electronics  "
    df.loc[[40, 121], "Product"] = "  Smart Watch Pro "

    # 3. Suspicious anomalies / outliers
    df.loc[50, "Revenue"] = 18450.00
    df.loc[50, "Profit"] = 6200.00
    df.loc[150, "Revenue"] = 22900.00
    df.loc[150, "Quantity"] = 48
    df.loc[220, "Discount"] = 0.85
    df.loc[220, "Profit"] = -1420.50
    df.loc[330, "Quantity"] = -3  # Invalid negative quantity

    # 4. Exact duplicate rows (8 rows)
    dup_rows = df.iloc[[10, 25, 60, 110, 180, 230, 280, 340]].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

    dataset_id = "demo_retail"
    original_csv = UPLOAD_DIR / f"{dataset_id}.csv"
    df.to_csv(original_csv, index=False)

    # Parse Date column for working/original pkl
    df_typed = _auto_parse_dates(df)
    original_snapshot_path = WORKING_DIR / f"{dataset_id}_original.pkl"
    working_path = WORKING_DIR / f"{dataset_id}_working.pkl"
    df_typed.to_pickle(original_snapshot_path)
    df_typed.to_pickle(working_path)

    record = {
        "id": dataset_id,
        "name": "Demo: Retail Sales Dataset (Sample)",
        "original_filename": "demo_retail_sales.csv",
        "file_type": "CSV",
        "sheet_name": None,
        "available_sheets": [],
        "is_demo": True,
        "original_path": str(original_csv),
        "working_path": str(working_path),
        "row_count": int(df_typed.shape[0]),
        "col_count": int(df_typed.shape[1]),
        "original_row_count": int(df_typed.shape[0]),
        "original_col_count": int(df_typed.shape[1]),
    }
    create_dataset_record(record)
    log_activity("DEMO_LOADED", f"Loaded sample retail dataset ({df_typed.shape[0]} rows, {df_typed.shape[1]} cols)", dataset_id)
    return get_dataset(dataset_id)


def load_working_df(dataset_id: str) -> pd.DataFrame:
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError(f"Dataset '{dataset_id}' not found.")
    working_path = Path(ds["working_path"])
    if not working_path.exists():
        raise FileNotFoundError(f"Working file missing for dataset '{dataset_id}'.")
    return pd.read_pickle(working_path)


def load_original_df(dataset_id: str) -> pd.DataFrame:
    original_snapshot = WORKING_DIR / f"{dataset_id}_original.pkl"
    if original_snapshot.exists():
        return pd.read_pickle(original_snapshot)
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError(f"Dataset '{dataset_id}' not found.")
    ext = "." + ds["file_type"].lower()
    df, _, _ = _read_file_to_df(Path(ds["original_path"]), ext, ds.get("sheet_name"))
    return _auto_parse_dates(df)


def save_working_df(dataset_id: str, df: pd.DataFrame, quality_score: Optional[float] = None) -> None:
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError(f"Dataset '{dataset_id}' not found.")
    df.to_pickle(ds["working_path"])
    update_dataset_stats(dataset_id, int(df.shape[0]), int(df.shape[1]), quality_score=quality_score)


def switch_excel_sheet(dataset_id: str, sheet_name: str) -> Dict[str, Any]:
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError(f"Dataset '{dataset_id}' not found.")
    if ds["file_type"] not in ("XLSX", "XLS"):
        raise ValueError("Sheet selection is only supported for Excel files.")
    if sheet_name not in ds["available_sheets"]:
        raise ValueError(f"Sheet '{sheet_name}' does not exist in workbook.")

    ext = "." + ds["file_type"].lower()
    df, chosen, _ = _read_file_to_df(Path(ds["original_path"]), ext, sheet_name)
    if df.empty or df.shape[1] == 0:
        raise ValueError(f"Selected sheet '{sheet_name}' is empty.")

    df.columns = [str(c).strip() if str(c).strip() else f"Column_{i}" for i, c in enumerate(df.columns)]
    df = _auto_parse_dates(df)

    original_snapshot_path = WORKING_DIR / f"{dataset_id}_original.pkl"
    df.to_pickle(original_snapshot_path)
    df.to_pickle(ds["working_path"])
    deactivate_all_cleaning_operations(dataset_id)
    update_dataset_stats(dataset_id, int(df.shape[0]), int(df.shape[1]), sheet_name=chosen)
    log_activity("SHEET_SWITCH", f"Switched dataset '{ds['name']}' to sheet '{chosen}'", dataset_id)
    return get_dataset(dataset_id)


def delete_dataset(dataset_id: str) -> None:
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError(f"Dataset '{dataset_id}' not found.")
    for path_str in (ds["original_path"], ds["working_path"], str(WORKING_DIR / f"{dataset_id}_original.pkl")):
        try:
            if path_str and os.path.exists(path_str):
                os.remove(path_str)
        except OSError:
            pass
    delete_dataset_record(dataset_id)
    log_activity("DELETE", f"Deleted dataset '{ds['name']}'", None)


def get_paginated_preview(
    dataset_id: str,
    page: int = 1,
    page_size: int = 25,
    search: str = "",
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
) -> Dict[str, Any]:
    df = load_working_df(dataset_id)
    roles = get_column_roles(df)

    filtered = df
    if search and search.strip():
        q = search.strip().lower()
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.lower().str.contains(q, regex=False, na=False)
        filtered = df[mask]

    if sort_by and sort_by in filtered.columns:
        ascending = sort_dir.lower() != "desc"
        try:
            filtered = filtered.sort_values(by=sort_by, ascending=ascending, na_position="last")
        except Exception:
            filtered = filtered.assign(_sort_key=filtered[sort_by].astype(str)).sort_values(
                by="_sort_key", ascending=ascending
            ).drop(columns=["_sort_key"])

    total_rows = int(len(filtered))
    page_size = max(1, min(int(page_size), 200))
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = max(1, min(int(page), total_pages))

    start = (page - 1) * page_size
    end = start + page_size
    slice_df = filtered.iloc[start:end]

    columns_meta = [
        {
            "name": col,
            "dtype": str(df[col].dtype),
            "role": roles[col],
            "missing": int(df[col].isna().sum()),
            "unique": int(df[col].nunique(dropna=True)),
        }
        for col in df.columns
    ]

    records = []
    for idx, row in slice_df.iterrows():
        rec = {"_row_index": int(idx) if isinstance(idx, (int, np.integer)) else str(idx)}
        for col in df.columns:
            rec[col] = safe_json(row[col])
        records.append(rec)

    return safe_json(
        {
            "columns": columns_meta,
            "rows": records,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_rows": total_rows,
                "total_pages": total_pages,
                "dataset_total_rows": int(len(df)),
            },
        }
    )
