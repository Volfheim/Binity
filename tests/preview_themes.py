"""Opt-in native Qt visual audit with synthetic data and no visible test windows.

Run on Windows: py -3.13 tests/preview_themes.py
Repeat with QT_SCALE_FACTOR=1.5 or 2 for scaled rendering.
Does not change Windows personalization, startup, settings files, or recycle bin.
"""
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "windows"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPalette
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox

from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.dialogs.confirm_dialog import ConfirmDialog
from src.ui.dialogs.download_dialog import DownloadDialog
from src.ui.dialogs.rounded_dialog import RoundedDialog
from src.ui.dialogs.update_dialog import UpdateDialog
from src.ui.theme import ThemeController
from src.ui.wave_progress import WaveProgressBar
from tests.test_themes import ScreenHarness


class HiddenProgressDialog(DownloadDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)


def contact_sheet(frames, path):
    width = max(image.width() for _, image in frames) + 24
    height = max(image.height() for _, image in frames) + 40
    sheet = QImage(width * 2, height * ((len(frames) + 1) // 2), QImage.Format.Format_RGB32)
    sheet.fill(QColor("#767676"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Segoe UI", 10))
    painter.setPen(QColor("white"))
    for index, (name, image) in enumerate(frames):
        x, y = index % 2 * width + 12, index // 2 * height + 12
        painter.drawText(QRect(x, y, width - 24, 20), Qt.AlignmentFlag.AlignLeft, name)
        painter.drawImage(x, y + 24, image)
    painter.end()
    assert sheet.save(str(path))


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(ROOT / "icons/bin_full.ico")))
    out = ROOT / "build/rounded-dialog-preview" / os.environ.get("QT_SCALE_FACTOR", "1")
    out.mkdir(parents=True, exist_ok=True)
    manager = ThemeController(app)
    count = 0

    for language in ("RU", "EN"):
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
        app.processEvents()
        controller = ScreenHarness(language, manager.current_theme)
        manager.changed.connect(controller._on_theme_changed)
        i18n = controller.i18n
        about = AboutDialog(i18n, theme=manager.current_theme)
        controller._about_dialog = about
        confirms = [ConfirmDialog(i18n, i18n.tr(key), theme=manager.current_theme) for key in
                    ("confirm_dialog_message", "confirm_dialog_message_secure_zero",
                     "confirm_dialog_message_secure_random")]
        controller._confirm_dialog = confirms[0]
        for dialog in confirms[1:]:
            manager.changed.connect(dialog.set_theme)
        update = UpdateDialog(i18n, "v9.0.0", "Binity\n\n" + i18n.tr("secure_delete_info_message") +
                              "\n" + "Long release notes " * 150, app.windowIcon())
        def message_title(key):
            if key.startswith("error_"):
                return i18n.tr("error_title")
            if key == "secure_delete_info_message":
                return i18n.tr("secure_delete_info_title")
            if key == "update_not_found":
                return i18n.tr("update_dialog_title")
            return i18n.tr("app_name")

        messages = [(key, controller._build_message_box(icon, message_title(key), i18n.tr(key)))
                    for key, icon in (("already_running", QMessageBox.Icon.Information),
                                      ("update_not_found", QMessageBox.Icon.Information),
                                      ("secure_delete_info_message", QMessageBox.Icon.Information),
                                      ("error_open_failed", QMessageBox.Icon.Warning),
                                      ("error_empty_failed", QMessageBox.Icon.Warning),
                                      ("error_update_download", QMessageBox.Icon.Warning),
                                      ("error_update_apply", QMessageBox.Icon.Warning))]
        with patch("src.ui.tray.tray_app.DownloadDialog", HiddenProgressDialog):
            controller._show_update_progress_dialog()
        progress = controller._update_progress_dialog
        menus = [controller.menu, *controller.menu.findChildren(QMenu)]
        widgets = [about, *confirms, update, progress, *menus, *[box for _, box in messages]]
        snapshots = {}

        def capture(widget, name, frames):
            nonlocal count
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            widget.show()
            app.processEvents()
            image = widget.grab().toImage()
            image.setDevicePixelRatio(1)
            assert not image.isNull()
            if isinstance(widget, RoundedDialog):
                assert image.pixelColor(0, 0).alpha() == 0, name
                assert image.pixelColor(image.width() - 1, image.height() - 1).alpha() == 0, name
            assert image.save(str(out / f"{theme}-{language}-{name}.png"))
            frames.append((name, image))
            snapshots[name] = image
            count += 1

        for theme, scheme in (("dark", Qt.ColorScheme.Dark), ("light", Qt.ColorScheme.Light)):
            app.styleHints().setColorScheme(scheme)
            app.processEvents()
            assert manager.current_theme == theme
            assert all(dialog.theme == theme for dialog in (about, *confirms))
            assert all(widget.palette().color(QPalette.ColorRole.Window).lightness() < 128
                       if theme == "dark" else
                       widget.palette().color(QPalette.ColorRole.Window).lightness() >= 128
                       for widget in [update, progress, *menus, *[box for _, box in messages]])
            frames = []
            for index, menu in enumerate(menus):
                menu.setActiveAction(next(action for action in menu.actions() if action.isEnabled()))
                capture(menu, f"menu-{index}", frames)
                menu.hide()
            contact_sheet(frames, out / f"{theme}-{language}-menus.png")

            frames = []
            capture(about, "about", frames)
            for index, dialog in enumerate(confirms):
                capture(dialog, f"confirmation-{index}", frames)
            contact_sheet(frames, out / f"{theme}-{language}-dialogs.png")

            frames = []
            update._toggle_details(False)
            capture(update, "update", frames)
            update._toggle_details(True)
            capture(update, "update-details", frames)
            for value in (0, 2, 43, 100):
                progress.setValue(value)
                progress.findChild(WaveProgressBar)._timer.stop()
                capture(progress, f"progress-{value}", frames)
            contact_sheet(frames, out / f"{theme}-{language}-updater.png")

            frames = []
            for name, box in messages:
                capture(box, name, frames)
            contact_sheet(frames, out / f"{theme}-{language}-messages.png")
            overview = [(name, snapshots[name]) for name in
                        ("about", "update", "progress-43", "error_open_failed")]
            contact_sheet(overview, out / f"{theme}-{language}-overview.png")

        manager.changed.disconnect(controller._on_theme_changed)
        for dialog in confirms[1:]:
            manager.changed.disconnect(dialog.set_theme)
        for widget in widgets:
            widget.close()
        controller.dispose()
        for widget in [*confirms[1:], update, *[box for _, box in messages]]:
            widget.deleteLater()
        app.processEvents()
    print(f"PASS: {count} native Qt renders, RU/EN, dark/light, live theme changes: {out}")


if __name__ == "__main__":
    main()
