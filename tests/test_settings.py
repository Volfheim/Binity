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

    def test_new_options_are_normalized(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"APPDATA": temp_dir}, clear=False):
                settings = Settings()
                settings.set_many(
                    {
                        "clear_sound": "INVALID",
                        "overflow_notify_threshold_gb": 99999,
                        "overflow_notify_enabled": "yes",
                        "theme_sync": "",
                    }
                )

                reloaded = Settings()
                self.assertEqual(reloaded.clear_sound, "off")
                self.assertEqual(reloaded.overflow_notify_threshold_gb, 1024)
                self.assertTrue(reloaded.overflow_notify_enabled)
                self.assertFalse(reloaded.theme_sync)


if __name__ == "__main__":
    unittest.main()
