import contextlib
import io
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


class RetiredReleaseHelperTests(unittest.TestCase):
    def test_import_and_execution_cannot_publish_or_build(self):
        path = Path(__file__).resolve().parents[1] / 'release_helper.py'
        with patch('subprocess.Popen', side_effect=AssertionError('No process allowed')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('No network allowed')), \
                patch('pathlib.Path.unlink', side_effect=AssertionError('No removal allowed')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            module = runpy.run_path(str(path))
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(module['main'](), 2)
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(path), run_name='__main__')
            self.assertEqual(raised.exception.code, 2)
        self.assertIn('retired', output.getvalue())
        self.assertIn('PyInstaller', output.getvalue())
