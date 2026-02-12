from __future__ import annotations

import logging
from pathlib import Path

from src.core.resources import app_data_dir


def setup_logging() -> Path:
    log_file = app_data_dir() / "binity.log"

    root = logging.getLogger()
    if root.handlers:
        return log_file

    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    return log_file
