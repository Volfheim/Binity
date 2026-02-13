import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.settings import Settings
from src.core.updater import Updater
from src.ui.tray.tray_app import TrayApp


class UpdaterRuntimeTests(unittest.TestCase):
    def test_release_notes_markdown_is_normalized(self) -> None:
        notes = """### Notes
- **SSD Users**: Please note
- [Docs](https://example.com/doc)
"""
        normalized = TrayApp._format_release_notes(notes)
        self.assertIn("Notes", normalized)
        self.assertIn("- SSD Users: Please note", normalized)
        self.assertIn("- Docs (https://example.com/doc)", normalized)
        self.assertNotIn("###", normalized)
        self.assertNotIn("**", normalized)

    def test_apply_update_script_contains_fallback_run_target(self) -> None:
        if not hasattr(subprocess, "STARTUPINFO"):
            self.skipTest("Windows-only updater script test")

        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {"APPDATA": temp_dir, "LOCALAPPDATA": temp_dir},
                clear=False,
            ):
                settings = Settings()
                updater = Updater(settings)

                current_exe = Path(temp_dir) / "Binity.exe"
                current_exe.write_bytes(b"MZ" + b"\x00" * 64)

                staged_exe = Path(temp_dir) / "next-Binity.exe"
                staged_exe.write_bytes(b"MZ" + b"\x00" * 64)

                with patch.object(Updater, "is_frozen", return_value=True), patch(
                    "src.core.updater.sys.executable", str(current_exe)
                ), patch("src.core.updater.subprocess.Popen") as popen_mock:
                    popen_mock.return_value = object()
                    ok = updater.apply_update(staged_exe)

                self.assertTrue(ok)

                script_path = Path(temp_dir) / "Binity" / "updates" / "_binity-update.cmd"
                self.assertTrue(script_path.exists())
                content = script_path.read_text(encoding="cp866", errors="ignore")
                self.assertIn('set "RUN_TARGET=%DOWNLOADED%"', content)
                self.assertIn("fallback to staged executable", content)
                self.assertIn('call :start_target "%RUN_TARGET%"', content)
                self.assertIn('set "READY=', content)
                self.assertIn('set "LAUNCH_INFO=', content)
                self.assertIn('call :copy_with_retry "%DOWNLOADED%" "%FINAL%"', content)
                self.assertIn('--update-ready-flag "%READY%"', content)

    def test_update_check_uses_latest_release_payload(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {"APPDATA": temp_dir, "LOCALAPPDATA": temp_dir},
                clear=False,
            ):
                settings = Settings()
                updater = Updater(settings)

                latest_release_payload = {
                    "tag_name": "v3.3.2",
                    "draft": False,
                    "prerelease": False,
                    "body": "latest release",
                    "assets": [
                        {
                            "name": "Binity-3.3.2.exe",
                            "size": 12_000_000,
                            "browser_download_url": "https://example.test/Binity-3.3.2.exe",
                        }
                    ],
                }

                with patch("src.core.updater.__version__", "3.3.1"), patch.object(
                    updater, "_fetch_latest_release", return_value=latest_release_payload
                ):
                    info = updater.check_for_update(force=True)

                self.assertIsNotNone(info)
                self.assertEqual(info.version, "v3.3.2")
                self.assertEqual(info.asset_name, "Binity-3.3.2.exe")

    def test_update_check_skipped_version_blocks_non_forced(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {"APPDATA": temp_dir, "LOCALAPPDATA": temp_dir},
                clear=False,
            ):
                settings = Settings()
                settings.set("skipped_update_version", "v3.3.2")
                updater = Updater(settings)

                latest_release_payload = {
                    "tag_name": "v3.3.2",
                    "draft": False,
                    "prerelease": False,
                    "body": "latest release",
                    "assets": [
                        {
                            "name": "Binity-3.3.2.exe",
                            "size": 12_000_000,
                            "browser_download_url": "https://example.test/Binity-3.3.2.exe",
                        }
                    ],
                }

                with patch("src.core.updater.__version__", "3.3.1"), patch.object(
                    updater, "_fetch_latest_release", return_value=latest_release_payload
                ):
                    info = updater.check_for_update(force=False)

                self.assertIsNone(info)

    def test_launch_info_is_loaded_and_rotated(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {"APPDATA": temp_dir, "LOCALAPPDATA": temp_dir},
                clear=False,
            ):
                updates_dir = Path(temp_dir) / "Binity" / "updates"
                updates_dir.mkdir(parents=True, exist_ok=True)
                marker = updates_dir / "launch-info.txt"
                marker.write_text(
                    "RUN_TARGET=C:\\\\Users\\\\test\\\\AppData\\\\Local\\\\Binity\\\\updates\\\\Binity.exe\n"
                    "FINAL=C:\\\\Program Files\\\\Binity\\\\Binity.exe\n",
                    encoding="utf-8",
                )

                settings = Settings()
                updater = Updater(settings)

                self.assertFalse(marker.exists())
                self.assertTrue(updater.launch_target_path.endswith("Binity.exe"))
                self.assertTrue(updater.launch_final_path.endswith("Binity.exe"))
                self.assertTrue(updater.launched_from_fallback_path)


if __name__ == "__main__":
    unittest.main()
