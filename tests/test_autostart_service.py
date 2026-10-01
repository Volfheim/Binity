import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from src.services.autostart import AutostartService


class AutostartServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AutostartService()

    def test_build_command_points_to_existing_python(self) -> None:
        command = self.service._build_command()
        tokens = self.service._split_command_tokens(command)
        self.assertGreaterEqual(len(tokens), 1)
        self.assertTrue(Path(tokens[0]).exists())

    def test_split_command_handles_quoted_paths(self) -> None:
        command = f'"{sys.executable}" "C:\\Program Files\\Binity\\main.py"'
        tokens = self.service._split_command_tokens(command)
        self.assertEqual(tokens[0], sys.executable)
        self.assertEqual(tokens[1], "C:\\Program Files\\Binity\\main.py")

    def test_is_valid_command_requires_existing_script_for_python_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "main.py"
            script_path.write_text("print('ok')\n", encoding="utf-8")

            valid_command = f'"{sys.executable}" "{script_path}"'
            self.assertTrue(self.service._is_valid_command(valid_command))

            missing_script = Path(temp_dir) / "missing.py"
            invalid_command = f'"{sys.executable}" "{missing_script}"'
            self.assertFalse(self.service._is_valid_command(invalid_command))

    def test_reading_state_preserves_legacy_only_autostart(self):
        with TemporaryDirectory() as folder:
            script = Path(folder) / 'Binity-Autostart.cmd'
            script.write_text('rem fixture only')
            with patch.object(self.service, '_startup_dir', return_value=Path(folder)), \
                    patch('winreg.OpenKey', side_effect=FileNotFoundError):
                self.assertTrue(self.service.is_enabled())
                self.assertTrue(self.service.is_enabled())
            self.assertTrue(script.exists())

    def test_failed_enable_never_removes_working_legacy_entry(self):
        with TemporaryDirectory() as folder:
            script = Path(folder) / 'Binity.cmd'
            script.write_text('rem fixture only')
            with patch.object(self.service, '_startup_dir', return_value=Path(folder)), \
                    patch('winreg.CreateKeyEx', side_effect=PermissionError):
                self.assertFalse(self.service.set_enabled(True))
            self.assertTrue(script.exists())

    def test_legacy_cleanup_only_happens_after_new_entry_is_verified(self):
        with TemporaryDirectory() as folder:
            script = Path(folder) / 'Binity.cmd'
            script.write_text('rem fixture only')
            for verified in (False, True):
                with patch.object(self.service, '_startup_dir', return_value=Path(folder)), \
                        patch('winreg.CreateKeyEx', return_value=MagicMock()), \
                        patch('winreg.SetValueEx'), \
                        patch.object(self.service, '_run_key_enabled', return_value=verified):
                    self.assertEqual(self.service.set_enabled(True), verified)
                self.assertEqual(script.exists(), not verified)

    def test_explicit_disable_removes_legacy_entry_without_real_registry_access(self):
        with TemporaryDirectory() as folder:
            script = Path(folder) / 'Binity.cmd'
            script.write_text('rem fixture only')
            with patch.object(self.service, '_startup_dir', return_value=Path(folder)), \
                    patch('winreg.CreateKeyEx', return_value=MagicMock()), \
                    patch('winreg.DeleteValue') as remove_value, \
                    patch.object(self.service, '_run_key_enabled', return_value=False):
                self.assertTrue(self.service.set_enabled(False))
                remove_value.assert_called_once()
            self.assertFalse(script.exists())

    def test_cleanup_failure_is_reported_even_if_run_key_is_enabled(self):
        with TemporaryDirectory() as folder:
            script = Path(folder) / 'Binity.cmd'
            script.write_text('rem fixture only')
            with patch.object(self.service, '_startup_dir', return_value=Path(folder)), \
                    patch('winreg.CreateKeyEx', return_value=MagicMock()), \
                    patch('winreg.SetValueEx'), \
                    patch.object(self.service, '_run_key_enabled', return_value=True), \
                    patch.object(Path, 'unlink', side_effect=PermissionError):
                self.assertFalse(self.service.set_enabled(True))
            self.assertTrue(script.exists())


if __name__ == "__main__":
    unittest.main()
