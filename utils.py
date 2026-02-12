import os
import sys
import logging

logger = logging.getLogger(__name__)

def resource_path(relative_path: str) -> str:
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        full_path = os.path.join(base_path, relative_path)
        return full_path
    except Exception as e:
        logger.error(f"Ошибка получения пути ресурса: {e}")
        return relative_path