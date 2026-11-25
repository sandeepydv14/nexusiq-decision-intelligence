import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
WORKING_DIR = DATA_DIR / "working"
REPORT_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "platform.db"

MAX_UPLOAD_MB = 50
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def ensure_directories() -> None:
    """Create runtime data directories if they do not exist."""
    for folder in (DATA_DIR, UPLOAD_DIR, WORKING_DIR, REPORT_DIR):
        os.makedirs(folder, exist_ok=True)
