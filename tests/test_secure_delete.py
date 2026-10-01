"""Windows overwrite tests on disposable fixtures, never the real recycle bin."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.services.recycle_bin import RecycleBinService
from src.services.secure_delete import WindowsWiper, WipeStats, current_user_sid


@unittest.skipUnless(os.name == "nt", "Windows handle semantics required")
class SecureDeleteTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "build" / "secure-delete-tests"
        root.mkdir(parents=True, exist_ok=True)
        temporary = TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "$Recycle.Bin"
        self.sid = current_user_sid()
        self.user = self.bin / self.sid
        self.user.mkdir(parents=True)
        self.wiper = WindowsWiper()

    def wipe(self, mode="zero"):
        stats = WipeStats()
        self.wiper.wipe_user_bin(self.bin, self.sid, mode, stats)
        return stats

    def junction(self, link, target):
        command = 'New-Item -ItemType Junction -Path $env:FIXTURE_LINK -Target $env:FIXTURE_TARGET | Out-Null'
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command],
                       env=dict(os.environ, FIXTURE_LINK=str(link), FIXTURE_TARGET=str(target)),
                       capture_output=True, timeout=10, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(link.rmdir)

    def test_only_current_user_payloads_are_overwritten_and_metadata_is_preserved(self):
        file = self.user / "$Rfolder" / "nested" / "file.bin"
        file.parent.mkdir(parents=True)
        file.write_bytes(b"secret" * 100)
        metadata = self.user / "$Ifolder"
        metadata.write_bytes(b"metadata")
        other = self.bin / "S-1-5-21-100-200-300-9999"
        other.mkdir()
        foreign = other / "$Rfile.bin"
        foreign.write_bytes(b"another user")
        stats = self.wipe()
        self.assertEqual((stats.files, stats.bytes, stats.failures), (1, 600, 0))
        self.assertEqual(file.read_bytes(), bytes(600))
        self.assertEqual(metadata.read_bytes(), b"metadata")
        self.assertEqual(foreign.read_bytes(), b"another user")

    def test_random_mode_and_empty_payloads(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"before")
        (self.user / "$Rempty.bin").touch()
        with patch('src.services.secure_delete.os.urandom', side_effect=lambda size: b'X' * size):
            stats = self.wipe('random')
        self.assertEqual(file.read_bytes(), b"XXXXXX")
        self.assertEqual((stats.files, stats.bytes, stats.failures), (2, 6, 0))

    def test_hard_link_never_changes_retained_file(self):
        retained = self.root / "keep.bin"
        retained.write_bytes(b"keep me")
        os.link(retained, self.user / "$Rhard.bin")
        stats = self.wipe()
        self.assertEqual(retained.read_bytes(), b"keep me")
        self.assertEqual((stats.files, stats.bytes, stats.failures), (0, 0, 1))

    def test_junction_payload_and_nested_junction_never_escape_bin(self):
        outside = self.root / "retained"
        outside.mkdir()
        file = outside / "keep.bin"
        file.write_bytes(b"keep me")
        self.junction(self.user / "$Rjunction", outside)
        nested = self.user / "$Rdirectory"
        nested.mkdir()
        self.junction(nested / "junction", outside)
        stats = self.wipe()
        self.assertEqual(file.read_bytes(), b"keep me")
        self.assertEqual((stats.files, stats.bytes, stats.failures), (0, 0, 2))

    def test_reparse_user_root_is_rejected(self):
        self.user.rmdir()
        target = self.root / "outside"
        target.mkdir()
        file = target / "$Rfile.bin"
        file.write_bytes(b"keep me")
        self.junction(self.user, target)
        stats = self.wipe()
        self.assertEqual(file.read_bytes(), b"keep me")
        self.assertEqual((stats.files, stats.failures), (0, 1))

    def test_stat_error_is_reported_not_counted_as_success(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"keep me")
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            if path == file:
                raise PermissionError('fixture denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat):
            stats = self.wipe()
        self.assertEqual((stats.files, stats.bytes, stats.failures), (0, 0, 1))
        self.assertEqual(file.read_bytes(), b"keep me")

    def test_unreadable_directory_is_counted_and_other_payloads_continue(self):
        directory = self.user / "$Rlocked"
        directory.mkdir()
        file = self.user / "$Rnormal.bin"
        file.write_bytes(b"wipe me")
        original = Path.iterdir
        def iterdir(path):
            if path == directory:
                raise PermissionError('fixture denied')
            yield from original(path)
        with patch.object(Path, 'iterdir', iterdir):
            stats = self.wipe()
        self.assertEqual((stats.files, stats.bytes, stats.failures), (1, 7, 1))

    def test_exclusively_open_file_is_skipped(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"keep me")
        with self.wiper.open_checked(file, False):
            stats = self.wipe()
        self.assertEqual((stats.files, stats.failures), (0, 1))
        self.assertEqual(file.read_bytes(), b"keep me")

    def test_link_cannot_be_added_after_handle_validation(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"wipe me")
        with self.wiper.open_checked(file, False):
            with self.assertRaises(OSError):
                os.link(file, self.root / "late-link.bin")

    def test_link_added_just_before_guard_is_detected_without_touching_data(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"keep me")
        link = self.root / "race-link.bin"
        original = self.wiper._set_delete_pending
        def set_pending(handle, pending):
            if pending:
                os.link(file, link)
            original(handle, pending)
        with patch.object(self.wiper, '_set_delete_pending', side_effect=set_pending):
            stats = self.wipe()
        self.assertEqual((stats.files, stats.failures), (0, 1))
        self.assertEqual(link.read_bytes(), b"keep me")
        self.assertEqual(file.read_bytes(), b"keep me")

    def test_failed_write_releases_guard_without_unlinking_payload(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"keep me")
        with patch.object(self.wiper, 'overwrite', side_effect=OSError('fixture write failure')):
            stats = self.wipe()
        self.assertEqual((stats.files, stats.failures), (0, 1))
        self.assertEqual(file.read_bytes(), b"keep me")

    def test_parent_directory_cannot_be_renamed_while_guarded(self):
        with self.wiper.open_checked(self.user, True):
            with self.assertRaises(OSError):
                self.user.rename(self.root / 'moved-user')

    def test_replaced_path_is_revalidated_before_write(self):
        file = self.user / "$Rfile.bin"
        file.write_bytes(b"original")
        outside = self.root / "keep.bin"
        outside.write_bytes(b"keep me")
        original = self.wiper.open_checked
        def open_checked(path, directory, parent_path=None):
            if path == file:
                path.unlink()
                os.link(outside, path)
            return original(path, directory, parent_path)
        with patch.object(self.wiper, 'open_checked', side_effect=open_checked):
            stats = self.wipe()
        self.assertEqual((stats.files, stats.failures), (0, 1))
        self.assertEqual(outside.read_bytes(), b"keep me")


class SecureDeleteResultTests(unittest.TestCase):
    def test_normal_clear_never_starts_wipe(self):
        with patch('src.services.recycle_bin.secure_wipe') as wipe, \
                patch.object(RecycleBinService, '_empty_bin_shell', return_value=True):
            result = RecycleBinService.empty_bin()
        wipe.assert_not_called()
        self.assertTrue(result.success)

    def test_partial_wipe_report_survives_normal_empty(self):
        with patch('src.services.recycle_bin.secure_wipe', return_value=WipeStats(1, 50, 3)), \
                patch.object(RecycleBinService, '_empty_bin_shell', return_value=True):
            result = RecycleBinService.empty_bin('zero')
        self.assertEqual((result.wiped_files, result.wiped_bytes, result.wipe_failures), (1, 50, 3))
