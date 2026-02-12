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
    def get_level(cls) -> int:
        info = cls.get_info()
        size = info.size_bytes
        if size <= 0 and info.items <= 0:
            return 0
        if size < 1 << 30:
            return 1
        if size < 2 << 30:
            return 2
        if size < 4 << 30:
            return 3
        return 4

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
