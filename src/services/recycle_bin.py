from __future__ import annotations

import ctypes
import subprocess
from dataclasses import dataclass


SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_ulonglong),
        ("i64NumItems", ctypes.c_ulonglong),
    ]


@dataclass
class RecycleBinInfo:
    size_bytes: int
    items: int


class RecycleBinService:
    SIZE_THRESHOLDS_BYTES = (
        256 * 1024 * 1024,        # 256 MB
        int(1.5 * 1024**3),       # 1.5 GB
        4 * 1024**3,              # 4 GB
        8 * 1024**3,              # 8 GB
    )
    ITEM_THRESHOLDS = (
        25,
        250,
        1000,
        2000,
    )

    @staticmethod
    def get_info() -> RecycleBinInfo:
        try:
            info = SHQUERYRBINFO()
            info.cbSize = ctypes.sizeof(info)
            result = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
            if result != 0:
                return RecycleBinInfo(size_bytes=0, items=0)
            return RecycleBinInfo(size_bytes=int(info.i64Size), items=int(info.i64NumItems))
        except Exception:
            return RecycleBinInfo(size_bytes=0, items=0)

    @classmethod
    def get_size_bytes(cls) -> int:
        return cls.get_info().size_bytes

    @classmethod
    def _score_by_thresholds(cls, value: int, thresholds: tuple[int, ...]) -> int:
        score = 0
        for threshold in thresholds:
            if value >= threshold:
                score += 1
        return min(score, 4)

    @classmethod
    def level_from_metrics(cls, size_bytes: int, items: int) -> int:
        size = max(0, int(size_bytes))
        item_count = max(0, int(items))
        if size <= 0 and item_count <= 0:
            return 0

        size_score = cls._score_by_thresholds(size, cls.SIZE_THRESHOLDS_BYTES)
        item_score = cls._score_by_thresholds(item_count, cls.ITEM_THRESHOLDS)
        return max(size_score, item_score)

    @classmethod
    def get_level(cls) -> int:
        info = cls.get_info()
        return cls.level_from_metrics(info.size_bytes, info.items)

    @staticmethod
    def empty_bin() -> bool:
        try:
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return result == 0
        except Exception:
            return False

    @staticmethod
    def open_bin() -> bool:
        try:
            subprocess.Popen(
                ["explorer.exe", "shell:RecycleBinFolder"],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
