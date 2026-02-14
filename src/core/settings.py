from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.core.resources import app_data_dir

DEFAULT_SETTINGS: dict[str, Any] = {
    "language": "RU",
    "confirm_clear": True,
    "double_click_action": "open",
    "update_interval_sec": 10,
    "clear_sound": "paper",
    "overflow_notify_enabled": True,
    "overflow_notify_threshold_gb": 15,
    "theme_sync": True,
    "secure_delete_mode": "off",
    "secure_delete_info_ack": False,
    "auto_check_updates": True,
    "last_update_check": "",
    "skipped_update_version": "",
}

LEGACY_REG_KEY = r"Software\Binity"


class Settings:
    def __init__(self) -> None:
        self.config_dir: Path = app_data_dir()
        self.config_file: Path = self.config_dir / "settings.json"
        self.values: dict[str, Any] = deepcopy(DEFAULT_SETTINGS)
        self._load()

    def _load(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    self.values.update(raw)
            except Exception:
                try:
                    broken_file = self.config_file.with_suffix(".broken.json")
                    self.config_file.replace(broken_file)
                except OSError:
                    pass
                self._save()
        else:
            self._import_legacy_registry_values()
            self._save()

        self._normalize()

    def _normalize(self) -> None:
        language = str(self.values.get("language", "RU")).upper()
        if language not in ("RU", "EN"):
            language = "RU"
        self.values["language"] = language

        self.values["confirm_clear"] = bool(self.values.get("confirm_clear", True))

        action = str(self.values.get("double_click_action", "open")).lower()
        if action not in ("open", "clear"):
            action = "open"
        self.values["double_click_action"] = action

        try:
            interval = int(self.values.get("update_interval_sec", 10))
        except Exception:
            interval = 10
        self.values["update_interval_sec"] = max(3, min(interval, 120))

        sound_mode = str(self.values.get("clear_sound", "paper")).lower()
        if sound_mode not in ("off", "windows", "paper", "trash"):
            sound_mode = "off"
        self.values["clear_sound"] = sound_mode

        self.values["overflow_notify_enabled"] = bool(self.values.get("overflow_notify_enabled", True))

        try:
            overflow_threshold = int(self.values.get("overflow_notify_threshold_gb", 15))
        except Exception:
            overflow_threshold = 15
        self.values["overflow_notify_threshold_gb"] = max(1, min(overflow_threshold, 1024))

        self.values["theme_sync"] = bool(self.values.get("theme_sync", True))

        secure_mode = str(self.values.get("secure_delete_mode", "off")).lower()
        if secure_mode not in ("off", "zero", "random"):
            secure_mode = "off"
        self.values["secure_delete_mode"] = secure_mode
        self.values["secure_delete_info_ack"] = bool(self.values.get("secure_delete_info_ack", False))

        self.values["auto_check_updates"] = bool(self.values.get("auto_check_updates", True))

        last_update_check = str(self.values.get("last_update_check", "") or "").strip()
        if last_update_check:
            try:
                from datetime import datetime

                datetime.fromisoformat(last_update_check)
            except Exception:
                last_update_check = ""
        self.values["last_update_check"] = last_update_check

        skipped_update_version = str(self.values.get("skipped_update_version", "") or "").strip()
        self.values["skipped_update_version"] = skipped_update_version

    def _import_legacy_registry_values(self) -> None:
        if os.name != "nt":
            return

        try:
            import winreg
        except Exception:
            return

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LEGACY_REG_KEY, 0, winreg.KEY_READ) as key:
                try:
                    language, _ = winreg.QueryValueEx(key, "Language")
                    if isinstance(language, str):
                        self.values["language"] = language.upper()
                except FileNotFoundError:
                    pass

                try:
                    confirm_clear, _ = winreg.QueryValueEx(key, "ConfirmClear")
                    self.values["confirm_clear"] = bool(int(confirm_clear))
                except FileNotFoundError:
                    pass

                try:
                    dbl_click, _ = winreg.QueryValueEx(key, "DoubleClickAction")
                    self.values["double_click_action"] = "clear" if int(dbl_click) == 1 else "open"
                except FileNotFoundError:
                    pass
        except Exception:
            return

    def _save(self) -> None:
        self._normalize()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.config_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as fh:
            json.dump(self.values, fh, indent=2, ensure_ascii=False)
        temp_file.replace(self.config_file)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value
        self._save()

    def set_many(self, payload: dict[str, Any]) -> None:
        if not payload:
            return
        self.values.update(payload)
        self._save()

    @property
    def language(self) -> str:
        return self.values["language"]

    @property
    def confirm_clear(self) -> bool:
        return self.values["confirm_clear"]

    @property
    def double_click_action(self) -> str:
        return self.values["double_click_action"]

    @property
    def update_interval_sec(self) -> int:
        return self.values["update_interval_sec"]

    @property
    def clear_sound(self) -> str:
        return self.values["clear_sound"]

    @property
    def overflow_notify_enabled(self) -> bool:
        return self.values["overflow_notify_enabled"]

    @property
    def overflow_notify_threshold_gb(self) -> int:
        return self.values["overflow_notify_threshold_gb"]

    @property
    def theme_sync(self) -> bool:
        return self.values["theme_sync"]

    @property
    def auto_check_updates(self) -> bool:
        return self.values["auto_check_updates"]

    @property
    def secure_delete_mode(self) -> str:
        return self.values["secure_delete_mode"]

    @property
    def secure_delete_info_ack(self) -> bool:
        return self.values["secure_delete_info_ack"]

    @property
    def last_update_check(self) -> str:
        return self.values.get("last_update_check", "")

    @property
    def skipped_update_version(self) -> str:
        return self.values.get("skipped_update_version", "")
