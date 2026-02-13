from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.version import __version__

GITHUB_API_LATEST = "https://api.github.com/repos/Volfheim/Binity/releases/latest"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Binity-Updater",
}
CHECK_INTERVAL_HOURS = 12


@dataclass(slots=True)
class UpdateInfo:
    version: str
    download_url: str
    body: str
    asset_name: str
    asset_size: int


class Updater:
    def __init__(self, settings) -> None:
        self.settings = settings
        self._info: UpdateInfo | None = None
        self._checking = False
        self._downloading = False
        self._just_updated = self._check_and_clear_flag()
        self.last_error = ""
        self._cleanup_runtime_leftovers()

    @staticmethod
    def is_frozen() -> bool:
        return getattr(sys, "frozen", False)

    @property
    def just_updated(self) -> bool:
        return self._just_updated

    @property
    def has_update(self) -> bool:
        return self._info is not None

    @property
    def info(self) -> UpdateInfo | None:
        return self._info

    @property
    def update_version(self) -> str:
        return self._info.version if self._info else ""

    @property
    def update_body(self) -> str:
        return self._info.body if self._info else ""

    def _update_dir(self) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if not local_app_data:
            local_app_data = os.path.expanduser("~\\AppData\\Local")
        return Path(local_app_data) / "Binity" / "updates"

    def _should_check(self) -> bool:
        if self._just_updated:
            return False
        if not self.is_frozen():
            return False
        if not self.settings.get("auto_check_updates", True):
            return False

        last_check = str(self.settings.get("last_update_check", "") or "")
        if not last_check:
            return True

        try:
            last_dt = datetime.fromisoformat(last_check)
            hours = (datetime.now() - last_dt).total_seconds() / 3600
            return hours >= CHECK_INTERVAL_HOURS
        except Exception:
            return True

    @staticmethod
    def _parse_version(text: str) -> tuple[int, ...]:
        clean = str(text or "").lstrip("vV").strip()
        if not clean:
            return (0,)

        parts: list[int] = []
        for part in clean.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts) or (0,)

    @staticmethod
    def _powershell_exe() -> str:
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.exists():
            return str(candidate)
        return "powershell"

    @staticmethod
    def _sanitized_child_env() -> dict[str, str]:
        env = {str(key): str(value) for key, value in os.environ.items()}
        for key in list(env.keys()):
            upper = key.upper()
            if upper == "_MEIPASS2" or upper.startswith("_PYI_"):
                env.pop(key, None)
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        return env

    @staticmethod
    def _reset_windows_dll_directory() -> None:
        if os.name != "nt":
            return
        try:
            import ctypes

            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass

    def _fetch_latest_release(self) -> dict:
        request = urllib.request.Request(GITHUB_API_LATEST, headers=GITHUB_HEADERS, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload)

    def _select_asset(self, assets: list[dict], tag_name: str) -> dict | None:
        version_hint = str(tag_name or "").lstrip("vV").strip().lower()
        candidates: list[tuple[int, dict]] = []

        for asset in assets:
            name = str(asset.get("name", "") or "")
            name_l = name.lower()
            if not name_l.endswith(".exe"):
                continue
            if "setup" in name_l or "installer" in name_l:
                continue

            score = 0
            if version_hint and version_hint in name_l:
                score += 100
            if name_l.startswith("binity"):
                score += 20
            if name_l == "binity.exe":
                score += 10

            size = int(asset.get("size", 0) or 0)
            if size > 1_000_000:
                score += 5
            candidates.append((score, asset))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (-item[0], str(item[1].get("name", "")).lower()))
        return candidates[0][1]

    def check_for_update(self, force: bool = False) -> UpdateInfo | None:
        if self._checking:
            return self._info
        if not force and not self._should_check():
            return self._info

        self._checking = True
        self.last_error = ""

        try:
            data = self._fetch_latest_release()
            tag_name = str(data.get("tag_name", "") or "")
            if not tag_name:
                self.settings.set("last_update_check", datetime.now().isoformat())
                self._info = None
                return None

            remote_ver = self._parse_version(tag_name)
            local_ver = self._parse_version(__version__)
            if remote_ver <= local_ver:
                self.settings.set("last_update_check", datetime.now().isoformat())
                self._info = None
                return None

            skipped = str(self.settings.get("skipped_update_version", "") or "")
            if not force and skipped == tag_name:
                self.settings.set("last_update_check", datetime.now().isoformat())
                self._info = None
                return None

            asset = self._select_asset(list(data.get("assets", [])), tag_name)
            if not asset:
                self.settings.set("last_update_check", datetime.now().isoformat())
                self._info = None
                return None

            download_url = str(asset.get("browser_download_url", "") or "")
            asset_name = str(asset.get("name", "") or "")
            asset_size = int(asset.get("size", 0) or 0)
            if not download_url:
                self.settings.set("last_update_check", datetime.now().isoformat())
                self._info = None
                return None

            self._info = UpdateInfo(
                version=tag_name,
                download_url=download_url,
                body=str(data.get("body", "") or ""),
                asset_name=asset_name,
                asset_size=asset_size,
            )
            self.settings.set("last_update_check", datetime.now().isoformat())
            return self._info

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            self.last_error = str(exc)
            return None
        finally:
            self._checking = False

    def _download_target_path(self) -> Path:
        update_dir = self._update_dir()
        desired_name = os.path.basename(str(self._info.asset_name or "").strip()) or "Binity.exe"
        if not desired_name.lower().endswith(".exe"):
            desired_name += ".exe"

        if not self.is_frozen():
            return update_dir / desired_name

        current_exe = Path(sys.executable).resolve()
        app_dir = current_exe.parent
        preferred = app_dir / desired_name

        try:
            if preferred.resolve().samefile(current_exe):
                return update_dir / f"next-{desired_name}"
        except Exception:
            if str(preferred).lower() == str(current_exe).lower():
                return update_dir / f"next-{desired_name}"
        return preferred

    def download_update(self, on_progress: Callable[[int], None] | None = None) -> Path | None:
        if self._downloading:
            return None
        if not self._info:
            self.last_error = "No update metadata available"
            return None

        self._downloading = True
        self.last_error = ""
        target: Path | None = None

        try:
            update_dir = self._update_dir()
            update_dir.mkdir(parents=True, exist_ok=True)

            target = self._download_target_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()

            request = urllib.request.Request(self._info.download_url, headers=GITHUB_HEADERS, method="GET")
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")

                total_size = int(response.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                with open(target, "wb") as output:
                    while True:
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and on_progress:
                            pct = int(downloaded / total_size * 100)
                            on_progress(max(0, min(100, pct)))

            if not target.exists():
                raise RuntimeError("Downloaded file not found")

            actual_size = target.stat().st_size
            if self._info.asset_size and actual_size != self._info.asset_size:
                raise RuntimeError(f"Size mismatch: expected {self._info.asset_size}, got {actual_size}")
            if actual_size < 1_000_000:
                raise RuntimeError("Downloaded file too small (<1MB)")

            with open(target, "rb") as fh:
                header = fh.read(2)
            if header != b"MZ":
                raise RuntimeError("Downloaded file is not a valid EXE")

            try:
                quoted_target = str(target).replace("'", "''")
                subprocess.run(
                    [
                        self._powershell_exe(),
                        "-NoProfile",
                        "-Command",
                        f"Unblock-File -LiteralPath '{quoted_target}'",
                    ],
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                )
            except Exception:
                pass

            return target

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            self.last_error = str(exc)
            try:
                if target and target.exists():
                    target.unlink()
            except OSError:
                pass
            return None
        finally:
            self._downloading = False

    def _check_and_clear_flag(self) -> bool:
        try:
            flag = self._update_dir() / "applied.flag"
            if flag.exists():
                flag.unlink()
                return True
        except OSError:
            pass
        return False

    def _cleanup_runtime_leftovers(self) -> None:
        try:
            update_dir = self._update_dir()
            if update_dir.exists():
                for pattern in ("next-*.exe", "*.tmp", "*.old"):
                    for path in update_dir.glob(pattern):
                        try:
                            path.unlink()
                        except OSError:
                            pass
        except OSError:
            pass

    def apply_update(self, downloaded_exe: Path) -> bool:
        if not self.is_frozen():
            self.last_error = "Auto-update is available only in packaged EXE build."
            return False

        try:
            if not downloaded_exe.exists():
                self.last_error = "Update file not found"
                return False

            current_exe = Path(sys.executable).resolve()
            current_pid = os.getpid()
            update_dir = self._update_dir()
            update_dir.mkdir(parents=True, exist_ok=True)
            downloaded_exe = downloaded_exe.resolve()

            if downloaded_exe.parent == update_dir and downloaded_exe.name.lower().startswith("next-"):
                final_exe = current_exe
            else:
                final_exe = current_exe.parent / downloaded_exe.name

            script_path = update_dir / "_binity-update.cmd"
            flag_file = update_dir / "applied.flag"

            script_template = """@echo off
setlocal enableextensions
set "PID=@@PID@@"
set "CURRENT=@@CURRENT_EXE@@"
set "DOWNLOADED=@@DOWNLOADED_EXE@@"
set "FINAL=@@FINAL_EXE@@"
set "FLAG=@@FLAG_FILE@@"

set "PYINSTALLER_RESET_ENVIRONMENT=1"
set "_MEIPASS2="
set "_PYI_APPLICATION_HOME_DIR="
set "_PYI_ARCHIVE_FILE="
set "_PYI_PARENT_PROCESS_LEVEL="
set "_PYI_SPLASH_IPC="

for /L %%A in (1,1,25) do (
  tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
  if errorlevel 1 goto wait_done
  timeout /t 1 /nobreak >NUL
)
taskkill /PID %PID% /F >NUL 2>&1
timeout /t 1 /nobreak >NUL

:wait_done
if not exist "%DOWNLOADED%" goto cleanup

if /I not "%DOWNLOADED%"=="%FINAL%" (
  copy /Y /B "%DOWNLOADED%" "%FINAL%" >NUL
  if errorlevel 1 goto cleanup
)

start "" "%FINAL%" --show-after-update
echo 1>"%FLAG%"

if /I not "%DOWNLOADED%"=="%FINAL%" (
  del /F /Q "%DOWNLOADED%" >NUL 2>&1
)

:cleanup
(goto) 2>NUL & del "%~f0"
endlocal
exit /b 0
"""

            script = (
                script_template
                .replace("@@PID@@", str(int(current_pid)))
                .replace("@@CURRENT_EXE@@", str(current_exe))
                .replace("@@DOWNLOADED_EXE@@", str(downloaded_exe))
                .replace("@@FINAL_EXE@@", str(final_exe))
                .replace("@@FLAG_FILE@@", str(flag_file))
            )
            script_path.write_text(script, encoding="cp866", errors="ignore")

            self._reset_windows_dll_directory()

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            subprocess.Popen(
                ["cmd", "/c", str(script_path)],
                env=self._sanitized_child_env(),
                startupinfo=startupinfo,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                close_fds=True,
            )
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def skip_version(self) -> None:
        if not self._info:
            return
        self.settings.set("skipped_update_version", self._info.version)
        self._info = None
