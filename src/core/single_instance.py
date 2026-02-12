from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QLockFile

from src.core.resources import app_data_dir


def acquire_single_instance_lock(timeout_ms: int = 250) -> Optional[QLockFile]:
    lock_file = app_data_dir() / "instance.lock"
    lock = QLockFile(str(lock_file))
    lock.setStaleLockTime(15000)
    if not lock.tryLock(timeout_ms):
        return None
    return lock
