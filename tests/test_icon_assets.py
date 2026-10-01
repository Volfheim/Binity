import hashlib
import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.tray.tray_app import ICON_MAP, TrayApp


# SHA-256 of the original artwork shipped in v3.3.7, not a redraw.
ORIGINAL_ICONS = {
    "bin_0.ico": "4ccf0155affb1f89b59154c5d4c28cf737bca48d7e11c12c3f27bd96e39dc8bd",
    "bin_25.ico": "ab805f37ca929097e1de4b67fdf161353f28a046c8eb2de22e50c22707c4cc76",
    "bin_50.ico": "e4e3585f00b9273d1dd17201c68b376630e07536308d571402401d1a8c9690d8",
    "bin_75.ico": "210fccbb1b5f2cd12ebd271d813c13772dcb4e109745dc7530dbe08ed39e3a00",
    "bin_full.ico": "4a5ca6db87a0c54ecc64eb50140548e454e2fb6fe32fde431c146df00aa7f3aa",
}


class IconLoader:
    # Exercise the production loader without initializing the tray or services.
    _theme_icon_path = TrayApp._theme_icon_path
    _load_icons = TrayApp._load_icons


class IconAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.root = Path(__file__).resolve().parents[1] / "icons"

    def test_ico_artwork_is_byte_identical_to_v337(self) -> None:
        for name, expected in ORIGINAL_ICONS.items():
            with self.subTest(icon=name):
                self.assertEqual(hashlib.sha256((self.root / name).read_bytes()).hexdigest(), expected)

    def test_all_fill_levels_use_original_ico_files(self) -> None:
        self.assertEqual(ICON_MAP, {i: "icons/" + name for i, name in enumerate(ORIGINAL_ICONS)})

    def test_both_themes_render_original_tray_icons_at_small_sizes(self) -> None:
        loader = IconLoader()
        for theme in ("light", "dark"):
            icons = loader._load_icons(theme)
            for level, name in enumerate(ORIGINAL_ICONS):
                reference = QIcon(str(self.root / name))
                for size in (16, 20, 24, 32):
                    with self.subTest(theme=theme, level=level, size=size):
                        actual = icons[level].pixmap(QSize(size, size)).toImage()
                        self.assertFalse(actual.isNull())
                        self.assertEqual(actual, reference.pixmap(QSize(size, size)).toImage())
                        self.assertTrue(actual.hasAlphaChannel())
                        self.assertEqual(actual.pixelColor(0, 0).alpha(), 0)

    def test_about_window_and_logo_use_original_icon_in_both_themes(self) -> None:
        reference = QIcon(str(self.root / "bin_full.ico"))
        for theme in ("light", "dark"):
            for size in (16, 32, 110):
                with self.subTest(theme=theme, size=size):
                    self.assertEqual(AboutDialog._bin_icon(theme).pixmap(QSize(size, size)).toImage(),
                                     reference.pixmap(QSize(size, size)).toImage())


if __name__ == "__main__":
    unittest.main()
