from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Binity"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def app_data_dir() -> Path:
    base = os.getenv("APPDATA")
    if base:
        path = Path(base) / APP_DIR_NAME
    else:
        path = Path.home() / f".{APP_DIR_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = project_root()
    return str(base / relative_path)
