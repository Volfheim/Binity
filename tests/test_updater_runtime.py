"""Updater regression tests: local fixtures only, no network or EXE execution."""
import io
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.settings import Settings
from src.core.updater import UpdateInfo, Updater
from src.ui.tray.tray_app import TrayApp


class UpdaterRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for patcher in (
            patch.dict(os.environ, {"APPDATA": temp.name, "LOCALAPPDATA": temp.name}),
            patch.object(Settings, "_import_legacy_registry_values"),
            patch("src.core.updater.urllib.request.urlopen", side_effect=AssertionError("Network forbidden in tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.settings = Settings()
        self.updater = Updater(self.settings)
        self.release = {
            "tag_name": "v3.3.8", "draft": False, "prerelease": False,
            "body": "Latest release", "assets": [{
                "name": "Binity-3.3.8.exe", "size": 12_000_000,
                "browser_download_url": "https://example.test/Binity-3.3.8.exe",
            }],
        }

    def test_release_notes_keep_bullets_and_link_destinations(self) -> None:
        notes = "### Notes\n- **SSD Users**: Please note\n- [Docs](https://example.com/doc)\n"
        self.assertEqual(TrayApp._format_release_notes(notes),
                         "Notes\n- SSD Users: Please note\n- Docs (https://example.com/doc)")

    def test_update_check_uses_latest_release_payload(self) -> None:
        with patch("src.core.updater.__version__", "3.3.7"), patch.object(
            self.updater, "_fetch_latest_release", return_value=self.release
        ):
            info = self.updater.check_for_update(force=True)
        self.assertEqual(info, UpdateInfo("v3.3.8", "https://example.test/Binity-3.3.8.exe",
                                         "Latest release", "Binity-3.3.8.exe", 12_000_000))
        self.assertTrue(self.settings.last_update_check)

    def test_skipped_version_blocks_background_check_but_not_manual_check(self) -> None:
        self.settings.set("skipped_update_version", "v3.3.8")
        with patch("src.core.updater.__version__", "3.3.7"), patch.object(
            Updater, "is_frozen", return_value=True
        ), patch.object(self.updater, "_fetch_latest_release", return_value=self.release) as fetch:
            self.assertIsNone(self.updater.check_for_update(force=False))
            # Prove the skipped-version branch was reached (source mode exits earlier).
            fetch.assert_called_once()
            self.assertIsNotNone(self.updater.check_for_update(force=True))

    def test_draft_prerelease_and_older_releases_are_ignored(self) -> None:
        for changes in ({"draft": True}, {"prerelease": True}, {"tag_name": "v3.3.6"}):
            with self.subTest(changes=changes), patch("src.core.updater.__version__", "3.3.7"), patch.object(
                self.updater, "_fetch_latest_release", return_value=self.release | changes
            ):
                self.assertIsNone(self.updater.check_for_update(force=True))
                self.assertFalse(self.updater.has_update)

    def test_installer_assets_are_not_selected(self) -> None:
        assets = [
            {"name": "Binity-3.3.8-setup.exe", "size": 20_000_000},
            {"name": "Binity.exe", "size": 10_000_000},
            {"name": "Binity-3.3.8.zip", "size": 20_000_000},
        ]
        self.assertEqual(self.updater._select_asset(assets, "v3.3.8"), assets[1])

    def test_source_mode_never_applies_an_update(self) -> None:
        with patch.object(Updater, "is_frozen", return_value=False), patch(
            "src.core.updater.subprocess.Popen"
        ) as launch:
            self.assertFalse(self.updater.apply_update(self.root / "missing.exe"))
        launch.assert_not_called()
        self.assertIn("packaged EXE", self.updater.last_error)

    @unittest.skipUnless(hasattr(subprocess, "STARTUPINFO"), "Windows-only process launch contract")
    def test_packaged_update_schedules_hidden_process_with_clean_environment(self) -> None:
        current = self.root / "Binity.exe"
        staged = self.root / "next-Binity.exe"
        current.write_bytes(b"fixture current")
        staged.write_bytes(b"fixture next")
        with patch.object(Updater, "is_frozen", return_value=True), patch(
            "src.core.updater.sys.executable", str(current)
        ), patch.object(Updater, "_reset_windows_dll_directory"), patch(
            "src.core.updater.subprocess.Popen"
        ) as launch, patch.dict(os.environ, {"_PYI_ARCHIVE_FILE": "old.exe", "_MEIPASS2": "old"}):
            self.assertTrue(self.updater.apply_update(staged))
        args, kwargs = launch.call_args
        script = self.root / "Binity" / "updates" / "_binity-update.cmd"
        self.assertEqual(args[0], ["cmd", "/c", str(script)])
        self.assertTrue(script.is_file())
        self.assertEqual(kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.assertNotIn("_PYI_ARCHIVE_FILE", kwargs["env"])
        self.assertNotIn("_MEIPASS2", kwargs["env"])
        self.assertEqual(kwargs["startupinfo"].wShowWindow, 0)
        self.assertEqual(current.read_bytes(), b"fixture current")

    def test_launch_info_is_consumed_and_reports_fallback(self) -> None:
        folder = self.root / "Binity" / "updates"
        folder.mkdir(parents=True)
        marker = folder / "launch-info.txt"
        marker.write_text("RUN_TARGET=C:\\Temp\\Binity.exe\nFINAL=C:\\Apps\\Binity.exe\n", encoding="utf-8")
        updater = Updater(self.settings)
        self.assertFalse(marker.exists())
        self.assertEqual(updater.launch_target_path, r"C:\Temp\Binity.exe")
        self.assertEqual(updater.launch_final_path, r"C:\Apps\Binity.exe")
        self.assertTrue(updater.launched_from_fallback_path)

    def test_download_rejects_size_mismatch_and_removes_partial_file(self) -> None:
        self._assert_invalid_download(b"MZ" + b"x" * 1_000_000, 1_000_003, "Size mismatch")

    def test_download_rejects_non_exe_and_removes_file(self) -> None:
        self._assert_invalid_download(b"NO" + b"x" * 1_000_000, 1_000_002, "not a valid EXE")

    def _assert_invalid_download(self, payload: bytes, expected_size: int, message: str) -> None:
        self.updater._info = UpdateInfo("v3.3.8", "https://example.test/Binity.exe", "", "Binity.exe", expected_size)
        response = io.BytesIO(payload)
        response.headers = {"Content-Length": str(len(payload))}
        with patch("src.core.updater.urllib.request.urlopen", return_value=response):
            self.assertIsNone(self.updater.download_update())
        self.assertIn(message, self.updater.last_error)
        self.assertFalse(list((self.root / "Binity" / "updates").glob("*.exe")))
        self.assertFalse(self.updater._downloading)


if __name__ == "__main__":
    unittest.main()
