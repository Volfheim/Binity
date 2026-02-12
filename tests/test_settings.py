import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_settings_save_is_atomic_and_persistent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"APPDATA": temp_dir}, clear=False):
                settings = Settings()
                settings.set("language", "EN")

                app_dir = Path(temp_dir) / "Binity"
                config_file = app_dir / "settings.json"
                temp_file = app_dir / "settings.tmp"

                self.assertTrue(config_file.exists())
                self.assertFalse(temp_file.exists())

                payload = json.loads(config_file.read_text(encoding="utf-8"))
                self.assertEqual(payload.get("language"), "EN")

    def test_corrupted_settings_file_is_rotated_and_restored(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"APPDATA": temp_dir}, clear=False):
                app_dir = Path(temp_dir) / "Binity"
                app_dir.mkdir(parents=True, exist_ok=True)

                config_file = app_dir / "settings.json"
                config_file.write_text("{broken-json", encoding="utf-8")

                settings = Settings()
                broken_file = app_dir / "settings.broken.json"

                self.assertTrue(broken_file.exists())
                self.assertTrue(config_file.exists())
                self.assertEqual(settings.language, "RU")


if __name__ == "__main__":
    unittest.main()
