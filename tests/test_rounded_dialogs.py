import ctypes
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from src.core.i18n import I18n
from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.dialogs.confirm_dialog import ConfirmDialog
from src.ui.dialogs.download_dialog import DownloadDialog
from src.ui.dialogs.message_dialog import MessageDialog
from src.ui.dialogs.rounded_dialog import TitleBar
from src.ui.dialogs.update_dialog import UpdateDialog
from tests.test_themes import ScreenHarness, contrast


class RoundedDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialogs = []
        self.i18n = I18n("RU")

    def show(self, dialog):
        self.dialogs.append(dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.show()
        self.app.processEvents()
        return dialog

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.hide()
            dialog.deleteLater()
        self.app.processEvents()

    def all_dialogs(self):
        return [AboutDialog(self.i18n), ConfirmDialog(self.i18n),
                UpdateDialog(self.i18n, "v9.0.0", "Notes", QIcon()),
                DownloadDialog(self.i18n, QIcon()),
                MessageDialog(self.i18n, "Binity", "Message", QMessageBox.Icon.Warning)]

    def focus_dialog(self, dialog):
        # Exercise real Qt focus without activating a native window on the desktop.
        QApplication.setActiveWindow(dialog)
        self.app.processEvents()

    def initial_button(self, dialog):
        attribute = {AboutDialog: "close_btn", ConfirmDialog: "cancel_btn",
                     UpdateDialog: "later_button", DownloadDialog: "hide_button",
                     MessageDialog: "ok_button"}[type(dialog)]
        return getattr(dialog, attribute)

    def test_initial_and_reopened_focus_is_on_safe_content_action_not_title_bar(self):
        for language in ("RU", "EN"):
            self.i18n = I18n(language)
            for theme in ("dark", "light"):
                for dialog in self.all_dialogs():
                    with self.subTest(language=language, theme=theme, dialog=type(dialog).__name__):
                        self.show(dialog)
                        dialog.set_theme(theme)
                        self.focus_dialog(dialog)
                        expected = self.initial_button(dialog)
                        self.assertIs(dialog.focusWidget(), expected)
                        self.assertTrue(expected.hasFocus())
                        for control in (dialog.title_bar.minimize_button, dialog.title_bar.close_button):
                            control.setFocus(Qt.FocusReason.TabFocusReason)
                            self.assertTrue(control.hasFocus())
                            dialog.hide()
                            dialog.show()
                            self.focus_dialog(dialog)
                            self.assertIs(dialog.focusWidget(), expected)
                            self.assertFalse(control.hasFocus())
                        dialog.hide()

    def test_initial_enter_and_space_never_confirm_deletion_or_installation(self):
        for constructor in (lambda: ConfirmDialog(self.i18n),
                            lambda: UpdateDialog(self.i18n, "v9.0", "Notes", QIcon())):
            for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                dialog = self.show(constructor())
                self.focus_dialog(dialog)
                accepted = Mock()
                dialog.accepted.connect(accepted)
                with self.subTest(dialog=type(dialog).__name__, key=key):
                    QTest.keyClick(dialog.focusWidget(), key)
                    self.assertFalse(dialog.isVisible())
                    self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
                    accepted.assert_not_called()

    def test_tab_navigation_still_reaches_every_action_including_window_controls(self):
        for dialog in self.all_dialogs():
            self.show(dialog)
            self.focus_dialog(dialog)
            initial = self.initial_button(dialog)
            with self.subTest(dialog=type(dialog).__name__):
                self.assertIs(dialog.focusWidget(), initial)
                visited = []
                for _ in range(20):
                    visited.append(dialog.focusWidget())
                    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
                    if dialog.focusWidget() is initial:
                        break
                self.assertIs(dialog.focusWidget(), initial)
                self.assertIn(dialog.title_bar.minimize_button, visited)
                self.assertIn(dialog.title_bar.close_button, visited)
                if isinstance(dialog, ConfirmDialog):
                    self.assertIn(dialog.confirm_btn, visited)
                elif isinstance(dialog, UpdateDialog):
                    self.assertIn(dialog.details_button, visited)
                    self.assertIn(dialog.install_button, visited)
                    self.assertIn(dialog.skip_button, visited)
                elif isinstance(dialog, AboutDialog):
                    self.assertIn(dialog.github_btn, visited)
                QTest.keyClick(initial, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
                self.assertIs(dialog.focusWidget(), visited[-1])
                dialog.hide()

    def test_explicitly_focused_confirm_and_install_actions_still_work_from_keyboard(self):
        for constructor, attribute in ((lambda: ConfirmDialog(self.i18n), "confirm_btn"),
                                       (lambda: UpdateDialog(self.i18n, "v9.0", "Notes", QIcon()),
                                        "install_button")):
            for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                dialog = self.show(constructor())
                self.focus_dialog(dialog)
                button = getattr(dialog, attribute)
                button.setFocus(Qt.FocusReason.TabFocusReason)
                with self.subTest(dialog=type(dialog).__name__, key=key):
                    QTest.keyClick(button, key)
                    self.assertFalse(dialog.isVisible())
                    self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_visible_dialog_keeps_user_focus_when_refreshed_or_shown_again(self):
        dialog = self.show(UpdateDialog(self.i18n, "v9.0", "Notes", QIcon()))
        self.focus_dialog(dialog)
        dialog.details_button.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(dialog.details_button, Qt.Key.Key_Return)
        self.assertFalse(dialog.details_panel.isHidden())
        dialog.i18n.set_language("EN")
        dialog.refresh_texts()
        dialog.set_theme("light")
        dialog.show()
        self.app.processEvents()
        self.assertIs(dialog.focusWidget(), dialog.details_button)
        self.assertTrue(dialog.isVisible())

    def test_modal_exec_uses_safe_initial_action(self):
        for dialog in (ConfirmDialog(self.i18n), UpdateDialog(self.i18n, "v9.0", "Notes", QIcon())):
            self.dialogs.append(dialog)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            focused = []

            def dismiss():
                self.focus_dialog(dialog)
                focused.append(dialog.focusWidget())
                QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Return)
                dialog.hide()

            QTimer.singleShot(0, dismiss)
            result = dialog.exec()
            with self.subTest(dialog=type(dialog).__name__):
                self.assertEqual(focused, [self.initial_button(dialog)])
                self.assertEqual(result, QDialog.DialogCode.Rejected)

    def test_minimize_and_restore_preserve_explicit_keyboard_focus(self):
        dialog = self.show(ConfirmDialog(self.i18n))
        self.focus_dialog(dialog)
        dialog.confirm_btn.setFocus(Qt.FocusReason.TabFocusReason)
        dialog.showMinimized()
        self.app.processEvents()
        dialog.showNormal()
        self.focus_dialog(dialog)
        self.assertIs(dialog.focusWidget(), dialog.confirm_btn)
        self.assertTrue(dialog.isVisible())

    def test_all_windows_have_real_transparent_corners_and_no_native_caption(self):
        for dialog in self.all_dialogs():
            self.show(dialog)
            for theme in ("light", "dark"):
                with self.subTest(dialog=type(dialog).__name__, theme=theme):
                    dialog.set_theme(theme)
                    self.app.processEvents()
                    self.assertTrue(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
                    self.assertTrue(dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
                    self.assertFalse(dialog.windowIcon().isNull())
                    image = dialog.grab().toImage()
                    for x, y in ((0, 0), (image.width() - 1, 0),
                                 (0, image.height() - 1), (image.width() - 1, image.height() - 1)):
                        self.assertEqual(image.pixelColor(x, y).alpha(), 0)
                    self.assertEqual(image.pixelColor(image.width() // 2, image.height() // 2).alpha(), 255)

    @unittest.skipUnless(os.name == "nt" and os.environ.get("QT_QPA_PLATFORM") == "windows",
                         "Requires opt-in native Windows Qt backend")
    def test_native_window_styles_are_layered_without_windows_caption(self):
        get_style = ctypes.windll.user32.GetWindowLongW
        get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_style.restype = ctypes.c_long
        for dialog in self.all_dialogs():
            self.show(dialog)
            self.assertEqual(get_style(int(dialog.winId()), -16) & 0x00C00000, 0)  # WS_CAPTION
            self.assertNotEqual(get_style(int(dialog.winId()), -20) & 0x00080000, 0)  # WS_EX_LAYERED

    def test_close_and_escape_never_accept_a_confirmation_or_update(self):
        for constructor in (lambda: ConfirmDialog(self.i18n),
                            lambda: UpdateDialog(self.i18n, "v9.0", "Notes", QIcon())):
            for method in ("close_button", "escape", "enter_on_close", "window_close"):
                dialog = self.show(constructor())
                accepted = Mock()
                dialog.accepted.connect(accepted)
                if method == "close_button":
                    dialog.title_bar.close_button.click()
                elif method == "escape":
                    QTest.keyClick(dialog, Qt.Key.Key_Escape)
                elif method == "enter_on_close":
                    dialog.title_bar.close_button.setFocus()
                    QTest.keyClick(dialog.title_bar.close_button, Qt.Key.Key_Return)
                else:
                    dialog.close()
                self.assertFalse(dialog.isVisible())
                self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
                accepted.assert_not_called()

    def test_minimize_control_does_not_finish_dialog(self):
        dialog = self.show(ConfirmDialog(self.i18n))
        finished = Mock()
        dialog.finished.connect(finished)
        QTest.keyClick(dialog.title_bar.minimize_button, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertTrue(dialog.isMinimized())
        finished.assert_not_called()
        dialog.showNormal()
        self.app.processEvents()
        self.assertFalse(dialog.isMinimized())

    def test_title_bar_uses_native_movement_and_fallback_without_dragging_buttons(self):
        dialog = self.show(AboutDialog(self.i18n))
        bar = dialog.title_bar
        with patch.object(TitleBar, "_start_system_move", return_value=True) as move:
            QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(100, 20))
            move.assert_called_once()
            self.assertIsNone(bar._drag_offset)
        with patch.object(TitleBar, "_start_system_move", return_value=False):
            origin = dialog.pos()
            QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=QPoint(100, 20))
            self.assertIsNotNone(bar._drag_offset)
            position = QPoint(130, 30)
            event = QMouseEvent(QEvent.Type.MouseMove, QPointF(position),
                                QPointF(bar.mapToGlobal(position)), Qt.MouseButton.NoButton,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(bar, event)
            self.assertEqual(dialog.pos(), origin + QPoint(30, 10))
            QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=position)
            self.assertIsNone(bar._drag_offset)
        with patch.object(TitleBar, "_start_system_move") as move:
            QTest.mouseClick(bar.close_button, Qt.MouseButton.LeftButton)
            move.assert_not_called()

    def test_download_close_hides_without_finishing_resetting_or_reappearing(self):
        dialog = self.show(DownloadDialog(self.i18n, QIcon()))
        finished = Mock()
        dialog.finished.connect(finished)
        dialog.setValue(42)
        for hide in (dialog.title_bar.close_button.click, dialog.hide_button.click,
                     lambda: QTest.keyClick(dialog, Qt.Key.Key_Escape), dialog.close):
            dialog.show()
            hide()
            self.assertFalse(dialog.isVisible())
            dialog.setValue(72)
            self.app.processEvents()
            self.assertFalse(dialog.isVisible())
            self.assertEqual(dialog.bar.value(), 72)
        finished.assert_not_called()

    def test_tray_download_action_remains_clickable_and_reopens_same_window(self):
        controller = ScreenHarness()
        self.dialogs.append(controller.menu)
        dialog = self.show(DownloadDialog(controller.i18n, QIcon()))
        controller._update_progress_dialog = dialog
        controller._update_download_in_progress = True
        controller._start_update_download = Mock()
        controller._refresh_update_action_text()
        self.assertTrue(controller.update_now_action.isEnabled())
        dialog.setValue(61)
        dialog.hide()
        # Hidden native test windows cannot meaningfully take Windows foreground focus.
        with patch.object(dialog, "activateWindow") as activate:
            controller.update_now_action.trigger()
            self.app.processEvents()
            activate.assert_called_once_with()
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.bar.value(), 61)
        controller._start_update_download.assert_not_called()

    def test_message_details_are_plain_text_scrollable_and_compact_when_collapsed(self):
        technical = "<script>not HTML</script>\n" + "C:/long-path/" * 1000
        dialog = self.show(MessageDialog(self.i18n, "Error", "Failed\n" + technical,
                                         QMessageBox.Icon.Warning))
        self.assertEqual(dialog.message_label.text(), "Failed")
        self.assertEqual(dialog.details_edit.toPlainText(), technical)
        self.assertTrue(dialog.details_edit.isReadOnly())
        self.assertTrue(dialog.details_edit.isHidden())
        width, height = dialog.width(), dialog.height()
        dialog.details_button.click()
        self.app.processEvents()
        self.assertFalse(dialog.details_edit.isHidden())
        self.assertGreater(dialog.height(), height)
        self.assertGreater(dialog.width(), width)
        self.assertLessEqual(dialog.width(), 500)
        self.assertLessEqual(dialog.height(), 600)
        dialog.details_button.click()
        self.app.processEvents()
        self.assertEqual(dialog.height(), height)
        self.assertEqual(dialog.width(), width)

    def test_short_errors_are_narrow_without_wrapping_their_message(self):
        for language in ("RU", "EN"):
            i18n = I18n(language)
            for theme in ("dark", "light"):
                for key in ("error_open_failed", "error_empty_failed", "error_update_download", "error_update_apply"):
                    dialog = self.show(MessageDialog(i18n, i18n.tr("error_title"), i18n.tr(key),
                                                     QMessageBox.Icon.Warning))
                    dialog.set_theme(theme)
                    self.app.processEvents()
                    with self.subTest(language=language, theme=theme, message=key):
                        text_width = dialog.message_label.fontMetrics().horizontalAdvance(i18n.tr(key))
                        # Offscreen Qt may use wider fallback fonts than native Windows.
                        self.assertLessEqual(dialog.width(), max(340, text_width + 64))
                        self.assertGreaterEqual(dialog.message_label.width(),
                                                text_width)
                        self.assertGreaterEqual(dialog.ok_button.width(), dialog.ok_button.sizeHint().width())

    def test_long_message_expands_within_limit_and_wraps_without_clipping(self):
        i18n = I18n("RU")
        short = self.show(MessageDialog(i18n, i18n.tr("error_title"), i18n.tr("error_open_failed")))
        long = self.show(MessageDialog(i18n, i18n.tr("secure_delete_info_title"),
                                      i18n.tr("secure_delete_info_message")))
        self.assertGreater(long.width(), short.width())
        self.assertLessEqual(long.width(), 480)
        self.assertGreaterEqual(long.message_label.height(),
                                long.message_label.heightForWidth(long.message_label.width()))

    def test_short_messages_fit_actual_width_without_extra_blank_rows(self):
        for language in ("RU", "EN"):
            i18n = I18n(language)
            for key in ("already_running", "secure_delete_info_message", "error_open_failed", "error_autostart"):
                dialog = self.show(MessageDialog(i18n, "Binity", i18n.tr(key)))
                with self.subTest(language=language, message=key):
                    self.assertLessEqual(dialog.height(), dialog.layout().totalHeightForWidth(dialog.width()) + 1)
                    self.assertLess(dialog.height(), 280)
                    self.assertGreaterEqual(dialog.message_label.height(),
                                            dialog.message_label.heightForWidth(dialog.message_label.width()))

    def test_control_labels_are_translated_and_buttons_have_sufficient_contrast(self):
        for language in ("RU", "EN"):
            dialog = self.show(DownloadDialog(I18n(language), QIcon()))
            self.assertEqual(dialog.title_bar.close_button.accessibleName(), dialog.i18n.tr("hide_window"))
            self.assertEqual(dialog.title_bar.minimize_button.accessibleName(), dialog.i18n.tr("minimize"))
            for theme in ("light", "dark"):
                dialog.set_theme(theme)
                colors = dialog.colors
                for foreground, background in (("text", "button"), ("muted", "surface"),
                                                ("primary_text", "primary"), ("warning", "warning_bg")):
                    self.assertGreaterEqual(contrast(colors[foreground], colors[background]), 4.5)


if __name__ == "__main__":
    unittest.main()
