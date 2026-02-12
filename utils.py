import os
import sys

def resource_path(relative_path: str) -> str:
    """Возвращает абсолютный путь до ресурса (иконки и т.п.), совместим с PyInstaller"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)