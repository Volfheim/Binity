import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.settings import Settings


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        # A fresh fixture must not import the developer's legacy registry values.
        legacy = patch.object(Settings, "_import_legacy_registry_values")
        legacy.start()
        self.addCleanup(legacy.stop)

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
                self.assertEqual(Settings().language, "EN")

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
                self.assertEqual(broken_file.read_text(encoding="utf-8"), "{broken-json")
                self.assertTrue(config_file.exists())
                self.assertEqual(settings.language, "RU")

    def test_failed_replace_preserves_previous_settings_file(self) -> None:
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"APPDATA": temp_dir}):
            settings = Settings()
            original = settings.config_file.read_bytes()
            with patch.object(Path, "replace", side_effect=PermissionError("fixture lock")):
                with self.assertRaises(PermissionError):
                    settings.set("language", "EN")
            self.assertEqual(settings.config_file.read_bytes(), original)
            self.assertEqual(Settings().language, "RU")

    def test_new_options_are_normalized(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"APPDATA": temp_dir}, clear=False):
                settings = Settings()
                settings.set_many(
                    {
                        "clear_sound": "INVALID",
                        "secure_delete_mode": "ALL_IN",
                        "secure_delete_info_ack": "sure",
                        "overflow_notify_threshold_gb": 99999,
                        "overflow_notify_enabled": "yes",
                        "theme_sync": "",
                        "auto_check_updates": "",
                        "last_update_check": "not-a-date",
                        "skipped_update_version": 321,
                    }
                )

                reloaded = Settings()
                self.assertEqual(reloaded.clear_sound, "off")
                self.assertEqual(reloaded.secure_delete_mode, "off")
                self.assertTrue(reloaded.secure_delete_info_ack)
                self.assertEqual(reloaded.overflow_notify_threshold_gb, 1024)
                self.assertTrue(reloaded.overflow_notify_enabled)
                self.assertFalse(reloaded.theme_sync)
                self.assertFalse(reloaded.auto_check_updates)
                self.assertEqual(reloaded.last_update_check, "")
                self.assertEqual(reloaded.skipped_update_version, "321")


if __name__ == "__main__":
    unittest.main()
