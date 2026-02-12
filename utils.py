# templates.py
import os
import sys
import logging

logger = logging.getLogger(__name__)

def resource_path(relative_path: str) -> str:
    """
    Абсолютный путь до ресурса (иконки и т.п.), работает с PyInstaller.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, relative_path)

def format_size(size_bytes: int) -> str:
    """Форматируем байты в удобочитаемый размер."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes/1024:.2f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.2f} MB"
    return f"{size_bytes/1024**3:.2f} GB"