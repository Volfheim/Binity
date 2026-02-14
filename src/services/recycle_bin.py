from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004

SECURE_DELETE_OFF = "off"
SECURE_DELETE_ZERO = "zero"
SECURE_DELETE_RANDOM = "random"
SECURE_DELETE_MODES = {SECURE_DELETE_OFF, SECURE_DELETE_ZERO, SECURE_DELETE_RANDOM}

_WIPE_CHUNK_SIZE = 1024 * 1024


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_ulonglong),
        ("i64NumItems", ctypes.c_ulonglong),
    ]


@dataclass(slots=True)
class RecycleBinInfo:
    size_bytes: int
    items: int


@dataclass(slots=True)
class BinClearResult:
    success: bool
    secure_mode: str
    wiped_files: int = 0
    wiped_bytes: int = 0
    wipe_failures: int = 0


class RecycleBinService:
    SIZE_THRESHOLDS_BYTES = (
        256 * 1024 * 1024,  # 256 MB
        int(1.5 * 1024**3),  # 1.5 GB
        4 * 1024**3,  # 4 GB
        8 * 1024**3,  # 8 GB
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
    def _normalize_secure_mode(mode: str) -> str:
        candidate = str(mode or SECURE_DELETE_OFF).lower()
        return candidate if candidate in SECURE_DELETE_MODES else SECURE_DELETE_OFF

    @staticmethod
    def _is_safe_recycle_payload_path(path: Path) -> bool:
        text = str(path).replace("/", "\\").lower()
        if "\\$recycle.bin\\" not in text:
            return False
        suffix = text.split("\\$recycle.bin\\", 1)[1]
        parts = [part for part in suffix.split("\\") if part]
        if len(parts) < 2:
            return False
        # Expected pattern: <sid>\\$Rxxxxx[\\...]
        return parts[1].startswith("$r")

    @staticmethod
    def _iter_drive_letters():
        if os.name != "nt":
            return

        try:
            mask = int(ctypes.windll.kernel32.GetLogicalDrives())
            if mask <= 0:
                raise RuntimeError("no drives mask")
            for index in range(26):
                if mask & (1 << index):
                    yield chr(ord("A") + index)
            return
        except Exception:
            pass

        for index in range(26):
            yield chr(ord("A") + index)

    @classmethod
    def _iter_wipe_targets(cls):
        if os.name != "nt":
            return

        for letter in cls._iter_drive_letters() or []:
            recycle_root = Path(f"{letter}:\\$Recycle.Bin")
            if not recycle_root.exists() or not recycle_root.is_dir():
                continue

            try:
                sid_dirs = recycle_root.iterdir()
            except OSError:
                continue

            for sid_dir in sid_dirs:
                if not sid_dir.is_dir():
                    continue

                try:
                    entries = sid_dir.iterdir()
                except OSError:
                    continue

                for entry in entries:
                    if not entry.name.lower().startswith("$r"):
                        continue
                    if entry.is_symlink():
                        continue

                    if entry.is_file():
                        if cls._is_safe_recycle_payload_path(entry):
                            yield entry
                        continue

                    if not entry.is_dir():
                        continue

                    try:
                        nested_items = entry.rglob("*")
                    except OSError:
                        continue

                    for nested in nested_items:
                        if nested.is_symlink() or not nested.is_file():
                            continue
                        if cls._is_safe_recycle_payload_path(nested):
                            yield nested

    @staticmethod
    def _wipe_file(path: Path, mode: str) -> int:
        try:
            size = int(path.stat().st_size)
        except OSError:
            return 0

        if size <= 0:
            return 0

        zero_chunk = b"\x00" * _WIPE_CHUNK_SIZE if mode == SECURE_DELETE_ZERO else b""

        with open(path, "r+b") as fh:
            remaining = size
            while remaining > 0:
                chunk_size = _WIPE_CHUNK_SIZE if remaining >= _WIPE_CHUNK_SIZE else remaining
                if mode == SECURE_DELETE_ZERO:
                    fh.write(zero_chunk[:chunk_size])
                else:
                    fh.write(os.urandom(chunk_size))
                remaining -= chunk_size
            fh.flush()
            os.fsync(fh.fileno())

        return size

    @classmethod
    def _best_effort_secure_wipe(cls, mode: str) -> tuple[int, int, int]:
        wiped_files = 0
        wiped_bytes = 0
        wipe_failures = 0

        for target in cls._iter_wipe_targets() or []:
            try:
                bytes_written = cls._wipe_file(target, mode)
                wiped_files += 1
                wiped_bytes += bytes_written
            except Exception:
                wipe_failures += 1

        return wiped_files, wiped_bytes, wipe_failures

    @staticmethod
    def _empty_bin_shell() -> bool:
        try:
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return result == 0
        except Exception:
            return False

    @classmethod
    def empty_bin(cls, secure_mode: str = SECURE_DELETE_OFF) -> BinClearResult:
        mode = cls._normalize_secure_mode(secure_mode)

        wiped_files = 0
        wiped_bytes = 0
        wipe_failures = 0
        if mode != SECURE_DELETE_OFF:
            wiped_files, wiped_bytes, wipe_failures = cls._best_effort_secure_wipe(mode)

        success = cls._empty_bin_shell()
        return BinClearResult(
            success=success,
            secure_mode=mode,
            wiped_files=wiped_files,
            wiped_bytes=wiped_bytes,
            wipe_failures=wipe_failures,
        )

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
