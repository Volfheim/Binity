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
                self.assertIn('--update-ready-flag "%READY%"', content)


if __name__ == "__main__":
    unittest.main()
