import unittest

from src.services.recycle_bin import RecycleBinService


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


if __name__ == "__main__":
    unittest.main()
