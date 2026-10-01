import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from src.core.i18n import I18n
from src.ui.dialogs.update_dialog import UpdateDialog
from src.ui.tray.tray_app import TrayApp
from src.ui.wave_progress import WaveProgressBar


class UpdateDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.close()
            dialog.deleteLater()
        self.app.processEvents()

    def prompt(self, language="RU", notes="Release notes\n" * 40):
        dialog = UpdateDialog(I18n(language), "v3.3.12", notes, QIcon())
        self.dialogs.append(dialog)
        dialog.show()
        self.app.processEvents()
        return dialog

    def progress(self):
        controller = SimpleNamespace(
            i18n=I18n("RU"), _update_progress_dialog=None,
            _window_icon=lambda: QIcon(), _shutting_down=False,
            update_now_action=QAction(),
        )
        TrayApp._show_update_progress_dialog(controller)
        self.dialogs.append(controller._update_progress_dialog)
        self.app.processEvents()
        return controller

    def test_details_toggle_is_translated_and_does_not_close_the_dialog(self):
        for language in ("RU", "EN"):
            dialog = self.prompt(language)
            width, height = dialog.width(), dialog.height()
            self.assertFalse(dialog.details_button.isCheckable())
            self.assertEqual(dialog.details_button.text(), dialog.i18n.tr("update_show_details"))
            self.assertTrue(dialog.details_panel.isHidden())
            dialog.details_button.click()
            self.app.processEvents()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.details_panel.isHidden())
            self.assertEqual(dialog.details_button.text(), dialog.i18n.tr("update_hide_details"))
            self.assertGreater(dialog.height(), height)
            self.assertEqual(dialog.width(), width)
            dialog.details_button.click()
            self.app.processEvents()
            self.assertEqual(dialog.height(), height)

    def test_language_change_updates_an_expanded_dialog(self):
        dialog = self.prompt()
        dialog.details_button.click()
        dialog.i18n.set_language("EN")
        dialog.refresh_texts()
        self.assertEqual(dialog.details_button.text(), "Hide details")
        self.assertEqual(dialog.install_button.text(), "Update")
        self.assertEqual(dialog.skip_button.text(), "Skip this version")
        self.assertEqual(dialog.later_button.text(), "Later")

    def test_empty_notes_have_no_details_button(self):
        self.assertTrue(self.prompt(notes="  ").details_button.isHidden())

    def test_constructor_does_not_show_a_detached_details_button(self):
        shown_windows = []

        class WatchShows(QObject):
            def eventFilter(self, watched, event):
                if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
                    shown_windows.append(watched)
                return False

        watcher = WatchShows()
        self.app.installEventFilter(watcher)
        try:
            dialog = UpdateDialog(I18n("RU"), "v9.0.0", "Notes", QIcon())
            self.dialogs.append(dialog)
            self.assertEqual(shown_windows, [])
        finally:
            self.app.removeEventFilter(watcher)

    def test_notes_are_read_only_plain_text(self):
        notes = '<b>Not HTML</b>\nhttps://example.test/' + "a" * 500
        dialog = self.prompt(notes=notes)
        self.assertEqual(dialog.notes_edit.toPlainText(), notes)
        self.assertTrue(dialog.notes_edit.isReadOnly())

    def test_actions_and_escape_have_distinct_results(self):
        for button, result in (("install_button", QDialog.DialogCode.Accepted),
                               ("skip_button", UpdateDialog.SKIP_VERSION),
                               ("later_button", QDialog.DialogCode.Rejected)):
            dialog = self.prompt()
            getattr(dialog, button).click()
            self.assertEqual(dialog.result(), result)
        dialog = self.prompt()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_enter_on_details_does_not_start_installation(self):
        dialog = self.prompt()
        dialog.details_button.setFocus()
        QTest.keyClick(dialog.details_button, Qt.Key.Key_Return)
        self.assertTrue(dialog.isVisible())
        self.assertFalse(dialog.details_panel.isHidden())

    def test_compact_layout_places_original_icon_to_the_right_of_the_heading(self):
        for language in ("RU", "EN"):
            dialog = self.prompt(language)
            self.assertLessEqual(dialog.width(), 560)
            self.assertLess(dialog.title_label.x(), 30)
            self.assertGreater(dialog.title_label.width(), dialog.width() * 0.6)
            self.assertGreater(dialog.app_icon.x(), dialog.title_label.geometry().right())
            self.assertFalse(dialog.app_icon.icon.isNull())
            for button in (dialog.install_button, dialog.skip_button, dialog.later_button):
                self.assertGreaterEqual(button.width(), button.sizeHint().width())

    def test_progress_percentage_is_only_in_the_bar_not_heading(self):
        controller = self.progress()
        dialog = controller._update_progress_dialog
        bar = dialog.findChild(WaveProgressBar)
        self.assertIsNotNone(bar)
        for value in (0, 2, 43, 100):
            TrayApp._on_update_download_progress(controller, value)
            self.assertEqual(bar.value(), value)
            self.assertEqual(bar.text(), f"{value}%")
            self.assertNotIn("%", dialog.labelText())
            self.assertNotIn("%", dialog.windowTitle())
            self.assertTrue(dialog.isVisible())

    def test_wave_stops_when_hidden_complete_or_motion_disabled(self):
        with patch("src.ui.wave_progress._system_animations_enabled", return_value=True):
            controller = self.progress()
            dialog = controller._update_progress_dialog
            bar = dialog.findChild(WaveProgressBar)
            dialog.setValue(43)
            self.assertTrue(bar._timer.isActive())
            dialog.hide()
            self.assertFalse(bar._timer.isActive())
            dialog.show()
            self.app.processEvents()
            self.assertTrue(bar._timer.isActive())
            dialog.setValue(100)
            self.assertFalse(bar._timer.isActive())
        with patch("src.ui.wave_progress._system_animations_enabled", return_value=False):
            dialog.setValue(43)
            self.assertFalse(bar._timer.isActive())

    def test_wave_stops_when_window_is_minimized_and_resumes(self):
        with patch("src.ui.wave_progress._system_animations_enabled", return_value=True):
            controller = self.progress()
            dialog = controller._update_progress_dialog
            bar = dialog.findChild(WaveProgressBar)
            dialog.setValue(43)
            dialog.showMinimized()
            self.app.processEvents()
            self.assertFalse(bar._timer.isActive())
            dialog.showNormal()
            self.app.processEvents()
            self.assertTrue(bar._timer.isActive())

    def test_wave_renders_for_both_palettes_and_different_widths(self):
        controller = self.progress()
        bar = controller._update_progress_dialog.findChild(WaveProgressBar)
        bar._timer.stop()
        for background, foreground in (("#2b2b2b", "#eeeeee"), ("#f7f7f7", "#202020")):
            palette = bar.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor(background))
            palette.setColor(QPalette.ColorRole.Text, QColor(foreground))
            bar.setPalette(palette)
            for width in (200, 350, 600):
                bar.resize(width, 24)
                for value in (0, 2, 50, 100):
                    bar.setValue(value)
                    self.assertFalse(bar.grab().toImage().isNull())

    def test_reopening_prompt_focuses_the_existing_dialog(self):
        dialog = self.prompt()
        controller = SimpleNamespace(
            _shutting_down=False, _update_download_in_progress=False,
            _update_dialog=dialog, _focus_dialog=Mock(),
        )
        with patch("src.ui.tray.tray_app.UpdateDialog") as constructor:
            TrayApp._show_update_dialog(controller)
        constructor.assert_not_called()
        controller._focus_dialog.assert_called_once_with(dialog)

    def test_tray_dispatches_only_the_selected_action(self):
        for result in (QDialog.DialogCode.Accepted, UpdateDialog.SKIP_VERSION, QDialog.DialogCode.Rejected):
            controller = SimpleNamespace(
                _shutting_down=False, _update_download_in_progress=False, _update_dialog=None,
                i18n=I18n("RU"), updater=Mock(has_update=True, update_body="Notes", update_version="v9.0"),
                _format_release_notes=lambda notes: notes, _window_icon=lambda: QIcon(),
                _start_update_download=Mock(), _refresh_update_action_text=Mock(),
                _update_notified_version="v9.0",
            )
            with patch("src.ui.tray.tray_app.UpdateDialog.exec", return_value=result):
                TrayApp._show_update_dialog(controller)
            self.assertIsNone(controller._update_dialog)
            self.assertEqual(controller._start_update_download.call_count, int(result == QDialog.DialogCode.Accepted))
            self.assertEqual(controller.updater.skip_version.call_count, int(result == UpdateDialog.SKIP_VERSION))


if __name__ == "__main__":
    unittest.main()
