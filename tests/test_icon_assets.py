import unittest
from pathlib import Path


class IconAssetTests(unittest.TestCase):
    def test_each_theme_ships_all_tray_levels_as_svg(self) -> None:
        root = Path(__file__).resolve().parents[1] / "icons"
        names = ("bin_0.svg", "bin_25.svg", "bin_50.svg", "bin_75.svg", "bin_full.svg")

        for theme in ("light", "dark"):
            for name in names:
                path = root / theme / name
                with self.subTest(theme=theme, name=name):
                    self.assertTrue(path.is_file())
                    payload = path.read_text(encoding="utf-8")
                    self.assertIn("<svg", payload)
                    self.assertIn("viewBox='0 0 64 64'", payload)
                    self.assertIn("stroke=", payload)


if __name__ == "__main__":
    unittest.main()
