import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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


if __name__ == "__main__":
    unittest.main()
