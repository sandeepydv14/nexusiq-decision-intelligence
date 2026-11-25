import io
import os
import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import config
from app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test_platform.db")

    # Update imported references across modules
    import database.db as db_mod
    import services.dataset_manager as dm_mod
    import services.cleaner as cl_mod
    import services.report_exporter as rep_mod

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test_platform.db")
    monkeypatch.setattr(dm_mod, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(dm_mod, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(cl_mod, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(rep_mod, "REPORT_DIR", tmp_path / "reports")

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_and_demo_workflow(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"

    # Load demo dataset
    demo_resp = client.post("/api/datasets/demo")
    assert demo_resp.status_code == 200
    ds = demo_resp.get_json()["dataset"]
    ds_id = ds["id"]
    assert ds["is_demo"] is True
    assert ds["row_count"] == 408  # 400 + 8 duplicate rows

    # Dashboard
    dash = client.get(f"/api/analysis/{ds_id}/dashboard")
    assert dash.status_code == 200
    dash_json = dash.get_json()
    assert dash_json["total_datasets"] == 1
    assert dash_json["quality"]["score"] < 100
    assert len(dash_json["insights"]) > 0

    # Profile
    prof = client.get(f"/api/analysis/{ds_id}/profile")
    assert prof.status_code == 200
    assert prof.get_json()["overview"]["duplicate_rows"] == 8

    # Quality
    qual = client.get(f"/api/analysis/{ds_id}/quality")
    assert qual.status_code == 200
    issues = qual.get_json()["issues"]
    categories = {i["category"] for i in issues}
    assert "Duplicate Records" in categories
    assert "Missing Data" in categories
    assert "Constant Column" in categories

    # Cleaning preview + apply + undo + reset
    prev = client.post(
        f"/api/cleaning/{ds_id}/preview",
        json={"operation": "remove_duplicates", "params": {}},
    )
    assert prev.status_code == 200
    assert prev.get_json()["before"]["rows"] == 408
    assert prev.get_json()["after"]["rows"] == 400

    applied = client.post(
        f"/api/cleaning/{ds_id}/apply",
        json={"operation": "remove_duplicates", "params": {}},
    )
    assert applied.status_code == 200
    assert applied.get_json()["row_count"] == 400

    undo = client.post(f"/api/cleaning/{ds_id}/undo")
    assert undo.status_code == 200
    assert undo.get_json()["row_count"] == 408

    # Apply again and test reset
    client.post(f"/api/cleaning/{ds_id}/apply", json={"operation": "trim_spaces", "params": {"column": "__all__"}})
    reset = client.post(f"/api/cleaning/{ds_id}/reset")
    assert reset.status_code == 200
    assert reset.get_json()["row_count"] == 408

    # EDA
    eda = client.get(f"/api/analysis/{ds_id}/eda")
    assert eda.status_code == 200
    assert eda.get_json()["correlation"] is not None
    assert eda.get_json()["time_series"] is not None

    # Anomaly detection (IQR, Z-score, Isolation Forest)
    for method in ("iqr", "zscore", "isolation_forest"):
        anom = client.post(
            f"/api/analysis/{ds_id}/anomaly",
            json={"method": method, "columns": ["Revenue", "Profit", "Quantity"]},
        )
        assert anom.status_code == 200
        assert anom.get_json()["anomaly_count"] > 0

    # Machine Learning (Regression + Classification)
    ml_reg = client.post(
        f"/api/ml/{ds_id}/train",
        json={
            "target_column": "Profit",
            "feature_columns": ["Category", "Region", "Quantity", "Revenue", "Discount"],
            "task_type": "regression",
        },
    )
    assert ml_reg.status_code == 200
    assert len(ml_reg.get_json()["models"]) == 3

    ml_cls = client.post(
        f"/api/ml/{ds_id}/train",
        json={
            "target_column": "Category",
            "feature_columns": ["Region", "Quantity", "Revenue", "Discount", "Profit"],
            "task_type": "classification",
        },
    )
    assert ml_cls.status_code == 200
    assert len(ml_cls.get_json()["models"]) == 4

    # Forecasting
    fc = client.post(
        f"/api/forecast/{ds_id}/run",
        json={"date_column": "Date", "target_column": "Revenue", "horizon": 4, "freq": "monthly"},
    )
    assert fc.status_code == 200
    assert len(fc.get_json()["models"]) == 3

    # Ask Your Data
    for q in (
        "What is the average revenue?",
        "Which category performs best?",
        "Which columns contain missing values?",
        "What is the correlation between Revenue and Profit?",
    ):
        q_resp = client.post(f"/api/query/{ds_id}/ask", json={"question": q})
        assert q_resp.status_code == 200
        assert q_resp.get_json()["supported"] is True

    # Report exports (CSV, Excel, PDF)
    for fmt in ("csv", "excel", "pdf"):
        exp = client.get(f"/api/reports/{ds_id}/download/{fmt}")
        assert exp.status_code == 200
        assert len(exp.data) > 100

    # Persistence check: history endpoint
    hist = client.get("/api/history")
    assert hist.status_code == 200
    hist_data = hist.get_json()
    assert len(hist_data["reports"]) == 3
    assert len(hist_data["analyses"]) >= 5


def test_excel_multisheet_and_invalid_inputs(client):
    # Empty file rejected
    resp_empty = client.post(
        "/api/datasets/upload",
        data={"file": (io.BytesIO(b""), "empty.csv")},
        content_type="multipart/form-data",
    )
    assert resp_empty.status_code == 400

    # Unsupported extension rejected
    resp_bad = client.post(
        "/api/datasets/upload",
        data={"file": (io.BytesIO(b"hello"), "bad.txt")},
        content_type="multipart/form-data",
    )
    assert resp_bad.status_code == 400

    # Multi-sheet Excel upload and switching
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Sales"
    ws1.append(["Item", "Amount"])
    ws1.append(["A", 10])
    ws1.append(["B", 20])
    ws2 = wb.create_sheet("Inventory")
    ws2.append(["SKU", "Stock"])
    ws2.append(["S1", 100])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    up = client.post(
        "/api/datasets/upload",
        data={"file": (buf, "multi.xlsx")},
        content_type="multipart/form-data",
    )
    assert up.status_code == 201
    ds = up.get_json()["dataset"]
    assert ds["available_sheets"] == ["Sales", "Inventory"]
    assert ds["sheet_name"] == "Sales"

    sw = client.post(f"/api/datasets/{ds['id']}/sheet", json={"sheet_name": "Inventory"})
    assert sw.status_code == 200
    assert sw.get_json()["dataset"]["sheet_name"] == "Inventory"
    assert sw.get_json()["dataset"]["row_count"] == 1

    # Dataset without date/sufficient rows -> forecasting unsuitable
    suit = client.get(f"/api/forecast/{ds['id']}/suitability")
    assert suit.status_code == 200
    assert suit.get_json()["suitable"] is False

    # Unsupported NL query returns honest explanation
    nl_bad = client.post(f"/api/query/{ds['id']}/ask", json={"question": "Predict next year stock price of Apple"})
    assert nl_bad.status_code == 200
    assert nl_bad.get_json()["supported"] is False


def test_additional_cleaning_and_sqlite_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "persist.db")

    import database.db as db_mod
    import services.dataset_manager as dm_mod
    import services.cleaner as cl_mod
    import services.report_exporter as rep_mod

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "persist.db")
    monkeypatch.setattr(dm_mod, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(dm_mod, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(cl_mod, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(rep_mod, "REPORT_DIR", tmp_path / "reports")

    # Session 1: Load demo, apply multiple cleaning operations
    app1 = create_app()
    with app1.test_client() as c1:
        ds_id = c1.post("/api/datasets/demo").get_json()["dataset"]["id"]
        r1 = c1.post(f"/api/cleaning/{ds_id}/apply", json={"operation": "remove_duplicates", "params": {}})
        assert r1.status_code == 200
        r2 = c1.post(f"/api/cleaning/{ds_id}/apply", json={"operation": "fill_missing", "params": {"column": "__all__", "strategy": "median"}})
        assert r2.status_code == 200
        r3 = c1.post(f"/api/cleaning/{ds_id}/apply", json={"operation": "drop_columns", "params": {"columns": ["Currency"]}})
        assert r3.status_code == 200
        assert r3.get_json()["col_count"] == 10
        r4 = c1.post(f"/api/cleaning/{ds_id}/apply", json={"operation": "handle_outliers", "params": {"column": "Revenue", "method": "cap_iqr", "factor": 1.5}})
        assert r4.status_code == 200
        r5 = c1.post(f"/api/cleaning/{ds_id}/apply", json={"operation": "filter_rows", "params": {"column": "Quantity", "operator": "gte", "value": "0"}})
        assert r5.status_code == 200

    # Session 2: Fresh Flask app instance reading same SQLite DB
    app2 = create_app()
    with app2.test_client() as c2:
        listed = c2.get("/api/datasets").get_json()["datasets"]
        assert len(listed) == 1
        assert listed[0]["col_count"] == 10
        hist = c2.get(f"/api/cleaning/{ds_id}/history").get_json()["operations"]
        assert len(hist) == 5
