import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import DB_PATH, ensure_directories


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_connection():
    ensure_directories()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialize SQLite schema for datasets, cleaning ops, analyses, reports, and activity."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                sheet_name TEXT,
                available_sheets TEXT,
                is_demo INTEGER DEFAULT 0,
                original_path TEXT NOT NULL,
                working_path TEXT NOT NULL,
                row_count INTEGER DEFAULT 0,
                col_count INTEGER DEFAULT 0,
                original_row_count INTEGER DEFAULT 0,
                original_col_count INTEGER DEFAULT 0,
                quality_score REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cleaning_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                params_json TEXT NOT NULL,
                summary TEXT NOT NULL,
                snapshot_path TEXT NOT NULL,
                rows_before INTEGER NOT NULL,
                rows_after INTEGER NOT NULL,
                cols_before INTEGER NOT NULL,
                cols_after INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                analysis_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS saved_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def log_activity(action: str, details: str, dataset_id: Optional[str] = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO activity_log (dataset_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (dataset_id, action, details, utc_now()),
        )


def create_dataset_record(record: Dict[str, Any]) -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO datasets (
                id, name, original_filename, file_type, sheet_name, available_sheets,
                is_demo, original_path, working_path, row_count, col_count,
                original_row_count, original_col_count, quality_score, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["name"],
                record["original_filename"],
                record["file_type"],
                record.get("sheet_name"),
                json.dumps(record.get("available_sheets", [])),
                1 if record.get("is_demo") else 0,
                record["original_path"],
                record["working_path"],
                record["row_count"],
                record["col_count"],
                record["original_row_count"],
                record["original_col_count"],
                record.get("quality_score"),
                now,
                now,
            ),
        )


def update_dataset_stats(
    dataset_id: str,
    row_count: int,
    col_count: int,
    quality_score: Optional[float] = None,
    sheet_name: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        fields = ["row_count = ?", "col_count = ?", "updated_at = ?"]
        values: List[Any] = [row_count, col_count, utc_now()]
        if quality_score is not None:
            fields.append("quality_score = ?")
            values.append(quality_score)
        if sheet_name is not None:
            fields.append("sheet_name = ?")
            values.append(sheet_name)
        values.append(dataset_id)
        conn.execute(f"UPDATE datasets SET {', '.join(fields)} WHERE id = ?", values)


def list_datasets() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM datasets ORDER BY updated_at DESC").fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["available_sheets"] = json.loads(item["available_sheets"] or "[]")
            item["is_demo"] = bool(item["is_demo"])
            result.append(item)
        return result


def get_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["available_sheets"] = json.loads(item["available_sheets"] or "[]")
        item["is_demo"] = bool(item["is_demo"])
        return item


def delete_dataset_record(dataset_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))


def add_cleaning_operation(
    dataset_id: str,
    operation: str,
    params: Dict[str, Any],
    summary: str,
    snapshot_path: str,
    rows_before: int,
    rows_after: int,
    cols_before: int,
    cols_after: int,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO cleaning_operations (
                dataset_id, operation, params_json, summary, snapshot_path,
                rows_before, rows_after, cols_before, cols_after, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                dataset_id,
                operation,
                json.dumps(params),
                summary,
                snapshot_path,
                rows_before,
                rows_after,
                cols_before,
                cols_after,
                utc_now(),
            ),
        )
        return cur.lastrowid


def get_cleaning_operations(dataset_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        query = "SELECT * FROM cleaning_operations WHERE dataset_id = ?"
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY id ASC"
        rows = conn.execute(query, (dataset_id,)).fetchall()
        res = []
        for r in rows:
            item = dict(r)
            item["params"] = json.loads(item["params_json"])
            res.append(item)
        return res


def pop_last_cleaning_operation(dataset_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cleaning_operations WHERE dataset_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
            (dataset_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute("UPDATE cleaning_operations SET is_active = 0 WHERE id = ?", (row["id"],))
        return dict(row)


def deactivate_all_cleaning_operations(dataset_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE cleaning_operations SET is_active = 0 WHERE dataset_id = ?", (dataset_id,))


def add_analysis_history(
    dataset_id: str,
    analysis_type: str,
    title: str,
    summary: Dict[str, Any],
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO analysis_history (dataset_id, analysis_type, title, summary_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dataset_id, analysis_type, title, json.dumps(summary, default=str), utc_now()),
        )
        return cur.lastrowid


def get_analysis_history(dataset_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if dataset_id:
            rows = conn.execute(
                """
                SELECT h.*, d.name as dataset_name FROM analysis_history h
                LEFT JOIN datasets d ON h.dataset_id = d.id
                WHERE h.dataset_id = ? ORDER BY h.id DESC LIMIT ?
                """,
                (dataset_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.*, d.name as dataset_name FROM analysis_history h
                LEFT JOIN datasets d ON h.dataset_id = d.id
                ORDER BY h.id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        res = []
        for r in rows:
            item = dict(r)
            item["summary"] = json.loads(item["summary_json"])
            res.append(item)
        return res


def add_saved_report(
    dataset_id: str,
    dataset_name: str,
    report_type: str,
    file_path: str,
    file_size: int,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO saved_reports (dataset_id, dataset_name, report_type, file_path, file_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (dataset_id, dataset_name, report_type, file_path, file_size, utc_now()),
        )
        return cur.lastrowid


def get_saved_reports(dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if dataset_id:
            rows = conn.execute(
                "SELECT * FROM saved_reports WHERE dataset_id = ? ORDER BY id DESC",
                (dataset_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM saved_reports ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_saved_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM saved_reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None


def get_recent_activity(limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
