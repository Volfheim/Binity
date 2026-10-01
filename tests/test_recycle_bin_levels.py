import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.recycle_bin import (
    RecycleBinService,
    SECURE_DELETE_OFF,
    SECURE_DELETE_RANDOM,
    SECURE_DELETE_ZERO,
)


class RecycleBinLevelTests(unittest.TestCase):
    def test_level_zero_for_empty_bin(self) -> None:
        self.assertEqual(RecycleBinService.level_from_metrics(0, 0), 0)

    def test_level_uses_size_thresholds(self) -> None:
        level = RecycleBinService.level_from_metrics(2 * 1024**3, 0)
        self.assertEqual(level, 2)

    def test_level_uses_item_thresholds(self) -> None:
        level = RecycleBinService.level_from_metrics(10 * 1024**2, 1300)
        self.assertEqual(level, 3)

    def test_level_is_hybrid_max_of_size_and_items(self) -> None:
        # Size implies level 1, item count implies level 4.
        level = RecycleBinService.level_from_metrics(300 * 1024**2, 3000)
        self.assertEqual(level, 4)

    def test_secure_delete_mode_normalization(self) -> None:
        self.assertEqual(RecycleBinService._normalize_secure_mode(SECURE_DELETE_ZERO), SECURE_DELETE_ZERO)
        self.assertEqual(RecycleBinService._normalize_secure_mode(SECURE_DELETE_RANDOM), SECURE_DELETE_RANDOM)
        self.assertEqual(RecycleBinService._normalize_secure_mode("strange"), SECURE_DELETE_OFF)

    def test_secure_delete_safe_path_detection(self) -> None:
        safe_file = Path(r"C:\$Recycle.Bin\S-1-5-21-1000\$RABCD.txt")
        safe_nested = Path(r"D:\$Recycle.Bin\S-1-5-21-1000\$RXYZ\folder\item.bin")
        unsafe_path = Path(r"C:\Users\User\Desktop\file.txt")
        unsafe_meta = Path(r"C:\$Recycle.Bin\S-1-5-21-1000\$IABCD.txt")

        self.assertTrue(RecycleBinService._is_safe_recycle_payload_path(safe_file))
        self.assertTrue(RecycleBinService._is_safe_recycle_payload_path(safe_nested))
        self.assertFalse(RecycleBinService._is_safe_recycle_payload_path(unsafe_path))
        self.assertFalse(RecycleBinService._is_safe_recycle_payload_path(unsafe_meta))

    def test_recycle_bin_query_failure_is_not_reported_as_empty(self) -> None:
        with patch(
            "src.services.recycle_bin.ctypes.windll.shell32.SHQueryRecycleBinW",
            side_effect=OSError("shell unavailable"),
        ):
            info = RecycleBinService.get_info()
        self.assertFalse(info.available)
        self.assertEqual((info.size_bytes, info.items), (0, 0))

    def test_locked_nested_recycle_directory_is_skipped(self) -> None:
        class LockedDirectory:
            @staticmethod
            def rglob(_pattern):
                raise OSError("access denied")

        self.assertEqual(list(RecycleBinService._iter_nested_files(LockedDirectory())), [])


if __name__ == "__main__":
    unittest.main()
