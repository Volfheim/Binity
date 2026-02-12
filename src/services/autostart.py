from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Binity"


class AutostartService:
    def _build_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}"'

        python_exe = Path(sys.executable).resolve()
        main_py = Path(__file__).resolve().parents[2] / "main.py"
        return f'"{python_exe}" "{main_py}"'

    @staticmethod
    def _startup_dir() -> Path:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
        return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    def _legacy_startup_paths(self) -> list[Path]:
        startup_dir = self._startup_dir()
        return [
            startup_dir / "Binity-Autostart.cmd",
            startup_dir / "Binity.cmd",
            startup_dir / "Binity Autostart.cmd",
        ]

    def _cleanup_legacy_startup_files(self) -> None:
        for path in self._legacy_startup_paths():
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    @staticmethod
    def _extract_executable_path(command: str) -> str:
        tokens = AutostartService._split_command_tokens(command)
        if not tokens:
            return ""
        return tokens[0]

    @staticmethod
    def _split_command_tokens(command: str) -> list[str]:
        candidate = str(command or "").strip()
        if not candidate:
            return []
        try:
            raw_tokens = shlex.split(candidate, posix=False)
        except ValueError:
            return []
        return [token.strip().strip('"') for token in raw_tokens if token and token.strip()]

    def _is_valid_command(self, command: str) -> bool:
        tokens = self._split_command_tokens(command)
        if not tokens:
            return False

        executable = tokens[0]
        if not executable:
            return False
        try:
            exe_exists = Path(executable).exists()
        except OSError:
            return False

        if not exe_exists:
            return False

        if len(tokens) >= 2 and tokens[1].lower().endswith(".py"):
            try:
                return Path(tokens[1]).exists()
            except OSError:
                return False
        return True

    def is_enabled(self) -> bool:
        if os.name != "nt":
            return False

        import winreg

        self._cleanup_legacy_startup_files()

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                command = str(value or "").strip()
                if not command:
                    return False
                return self._is_valid_command(command)
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def set_enabled(self, enabled: bool) -> bool:
        if os.name != "nt":
            return False

        import winreg

        self._cleanup_legacy_startup_files()

        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, self._build_command())
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            if enabled:
                return self.is_enabled()
            return not self.is_enabled()
        except OSError:
            return False
