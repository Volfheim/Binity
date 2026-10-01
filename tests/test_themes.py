import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.i18n import I18n
from src.core.settings import DEFAULT_SETTINGS
from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.dialogs.confirm_dialog import ConfirmDialog
from src.ui.dialogs.update_dialog import UpdateDialog
from src.ui.theme import ThemeController, dialog_colors
from src.ui.tray.tray_app import TrayApp
from src.ui.wave_progress import WaveProgressBar


def contrast(first, second):
    def luminance(color):
        values = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                  for v in QColor(color).getRgbF()[:3]]
        return sum(v * weight for v, weight in zip(values, (0.2126, 0.7152, 0.0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class FakeHints(QObject):
    colorSchemeChanged = pyqtSignal(object)

    def __init__(self, scheme):
        super().__init__()
        self.system_scheme = scheme
        self.override = None
        self.scheme = scheme

    def colorScheme(self):
        return self.scheme

    def _update(self):
        scheme = self.system_scheme if self.override is None else self.override
        if scheme != self.scheme:
            self.scheme = scheme
            self.colorSchemeChanged.emit(scheme)

    def setColorScheme(self, scheme):
        self.override = scheme
        self._update()

    def unsetColorScheme(self):
        self.override = None
        self._update()

    def change_system_scheme(self, scheme):
        self.system_scheme = scheme
        self._update()


class FakeApplication(QObject):
    paletteChanged = pyqtSignal(QPalette)

    def __init__(self, scheme=Qt.ColorScheme.Dark, background="#202020"):
        super().__init__()
        self.hints = FakeHints(scheme)
        self.colors = QPalette()
        self.colors.setColor(QPalette.ColorRole.Window, QColor(background))

    def styleHints(self):
        return self.hints

    def palette(self):
        return self.colors


class ScreenHarness(TrayApp):
    """Real UI factories, without timers, filesystem, registry or tray registration."""

    def __init__(self, language="RU", theme="dark"):
        QObject.__init__(self)
        self.i18n = I18n(language)
        self.settings = SimpleNamespace(**{**DEFAULT_SETTINGS, "language": language}, set=Mock())
        self.tray = Mock()
        self.autostart = Mock()
        self.autostart.is_enabled.return_value = False
        self.updater = SimpleNamespace(has_update=True, update_version="v9.0.0")
        self._update_download_in_progress = False
        self._update_check_in_progress = False
        self._update_apply_in_progress = False
        self._pending_update_path = None
        self._clear_in_progress = False
        self._state_task = None
        self._about_dialog = self._confirm_dialog = self._update_dialog = None
        self._update_progress_dialog = None
        self._shutting_down = False
        self.current_theme = theme
        self.current_level = 0
        self.icons = self._load_icons(theme)
        self._build_menu()
        self._apply_menu_state()
        self._update_texts()

    def dispose(self):
        for widget in (self.menu, self._about_dialog, self._confirm_dialog,
                       self._update_dialog, self._update_progress_dialog):
            if widget is not None:
                widget.close()
                widget.deleteLater()


class ThemeControllerTests(unittest.TestCase):
    def test_uses_qt_scheme_not_a_second_windows_theme_source(self):
        for scheme, background, expected in ((Qt.ColorScheme.Dark, "white", "dark"),
                                             (Qt.ColorScheme.Light, "black", "light")):
            app = FakeApplication(scheme, background)
            controller = ThemeController(app)
            self.assertEqual(controller.current_theme, expected)
            self.assertIsNone(app.hints.override)

    def test_unknown_scheme_follows_actual_palette_and_palette_changes(self):
        app = FakeApplication(Qt.ColorScheme.Unknown, "white")
        controller = ThemeController(app)
        self.assertEqual(controller.current_theme, "light")
        app.colors.setColor(QPalette.ColorRole.Window, QColor("black"))
        app.paletteChanged.emit(app.colors)
        self.assertEqual(controller.current_theme, "dark")

    def test_theme_event_emits_once_without_polling_recycle_bin(self):
        app = FakeApplication()
        controller = ThemeController(app)
        changed = Mock()
        controller.changed.connect(changed)
        app.hints.change_system_scheme(Qt.ColorScheme.Light)
        app.paletteChanged.emit(app.colors)
        changed.assert_called_once_with("light")

    def test_disabled_sync_pins_qt_and_reenable_uses_latest_system_theme(self):
        app = FakeApplication()
        controller = ThemeController(app)
        controller.set_sync_enabled(False)
        self.assertEqual(app.hints.override, Qt.ColorScheme.Dark)
        app.hints.change_system_scheme(Qt.ColorScheme.Light)
        self.assertEqual(app.hints.colorScheme(), Qt.ColorScheme.Dark)
        self.assertEqual(controller.current_theme, "dark")
        controller.set_sync_enabled(True)
        self.assertIsNone(app.hints.override)
        self.assertEqual(app.hints.colorScheme(), Qt.ColorScheme.Light)
        self.assertEqual(controller.current_theme, "light")

    def test_start_with_sync_disabled_keeps_startup_scheme_not_forced_dark(self):
        app = FakeApplication(Qt.ColorScheme.Light)
        controller = ThemeController(app, sync_enabled=False)
        app.hints.change_system_scheme(Qt.ColorScheme.Dark)
        self.assertEqual(controller.current_theme, "light")
        self.assertEqual(app.hints.override, Qt.ColorScheme.Light)

    def test_setting_toggle_controls_native_and_custom_themes(self):
        app = FakeApplication()
        controller = SimpleNamespace(settings=Mock(), theme_controller=ThemeController(app))
        TrayApp._on_theme_sync_toggled(controller, False)
        controller.settings.set.assert_called_once_with("theme_sync", False)
        self.assertEqual(app.hints.override, Qt.ColorScheme.Dark)


class ThemeScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widgets = []
        self.original_palette = self.app.palette()

    def tearDown(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        self.app.setPalette(self.original_palette)
        self.app.processEvents()

    def show(self, widget):
        self.widgets.append(widget)
        widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        widget.show()
        self.app.processEvents()
        return widget

    def test_confirmation_text_and_destructive_button_contrast_in_both_themes(self):
        for language in ("RU", "EN"):
            for theme in ("light", "dark"):
                with self.subTest(language=language, theme=theme):
                    dialog = self.show(ConfirmDialog(I18n(language), theme=theme))
                    background = dialog.palette().color(QPalette.ColorRole.Window)
                    for label in (dialog.title_label, dialog.message_label, dialog.cancel_btn):
                        foreground = label.palette().color(label.foregroundRole())
                        self.assertGreaterEqual(contrast(foreground, background), 4.5)
                    button_palette = dialog.confirm_btn.palette()
                    self.assertGreaterEqual(contrast(button_palette.color(QPalette.ColorRole.ButtonText),
                                                     button_palette.color(QPalette.ColorRole.Button)), 4.5)

    def test_about_text_contrast_on_both_gradient_endpoints(self):
        for theme, backgrounds in (("light", ("#f7f9fc", "#eef2f8")),
                                    ("dark", ("#111827", "#0b1220"))):
            dialog = self.show(AboutDialog(I18n("RU"), theme=theme))
            for label in (dialog.title_label, dialog.subtitle_label, dialog.version_label,
                          dialog.author_label, dialog.github_hint, dialog.close_btn):
                for background in backgrounds:
                    with self.subTest(theme=theme, label=label.objectName(), background=background):
                        self.assertGreaterEqual(contrast(label.palette().color(label.foregroundRole()),
                                                         background), 4.5)

    def test_about_description_updates_with_language_in_open_and_reopened_window(self):
        expected = {"RU": "Управление корзиной Windows из трея",
                    "EN": "Binity - Modern recycle bin tray manager"}
        controller = ScreenHarness("RU")
        self.widgets.append(controller.menu)
        controller._refresh_state = Mock()
        dialog = self.show(AboutDialog(controller.i18n))
        controller._about_dialog = dialog
        for theme in ("dark", "light"):
            dialog.set_theme(theme)
            for language in ("RU", "EN", "RU"):
                with self.subTest(theme=theme, language=language):
                    controller._set_language(language)
                    self.app.processEvents()
                    self.assertTrue(dialog.isVisible())
                    self.assertEqual(dialog.subtitle_label.text(), expected[language])
                    self.assertGreaterEqual(dialog.subtitle_label.height(),
                                            dialog.subtitle_label.heightForWidth(dialog.subtitle_label.width()))
        dialog.hide()
        controller._set_language("EN")
        with patch.object(dialog, "activateWindow"):
            controller.show_about()
            self.app.processEvents()
        self.assertIs(controller._about_dialog, dialog)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.subtitle_label.text(), expected["EN"])

    def test_theme_change_updates_open_confirmation_and_hidden_about(self):
        controller = ScreenHarness()
        self.widgets.append(controller.menu)
        controller._confirm_dialog = self.show(ConfirmDialog(controller.i18n, theme="dark"))
        controller._about_dialog = self.show(AboutDialog(controller.i18n, theme="dark"))
        controller._about_dialog.hide()
        for theme, expected in (("light", "#0f172a"), ("dark", "#f8fafc")):
            controller._on_theme_changed(theme)
            self.app.processEvents()
            self.assertTrue(controller._confirm_dialog.isVisible())
            self.assertFalse(controller._about_dialog.isVisible())
            for dialog in (controller._about_dialog, controller._confirm_dialog):
                self.assertEqual(dialog.theme, theme)
                self.assertEqual(dialog.title_label.palette().color(QPalette.ColorRole.WindowText).name(),
                                 expected)

    def test_menus_and_rounded_screens_follow_palette_without_recreation(self):
        controller = ScreenHarness()
        self.widgets.append(controller.menu)
        update = self.show(UpdateDialog(controller.i18n, "v9.0.0", "Release notes", QIcon()))
        update.details_button.click()
        message = self.show(controller._build_message_box(QMessageBox.Icon.Warning, "Binity", "Error"))
        controller._show_update_progress_dialog()
        progress = controller._update_progress_dialog
        self.widgets.append(progress)
        bar = progress.findChild(WaveProgressBar)
        menus = [controller.menu, *controller.menu.findChildren(type(controller.menu))]
        self.addCleanup(self.app.styleHints().unsetColorScheme)
        for background, foreground in (("#ffffff", "#000000"), ("#202020", "#ffffff")):
            self.app.styleHints().setColorScheme(Qt.ColorScheme.Light if background == "#ffffff"
                                                else Qt.ColorScheme.Dark)
            palette = QPalette(self.original_palette)
            for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
                palette.setColor(role, QColor(background))
            for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
                palette.setColor(role, QColor(foreground))
            self.app.setPalette(palette)
            self.app.processEvents()
            for widget in menus:
                with self.subTest(widget=type(widget).__name__, background=background):
                    self.assertEqual(widget.palette().color(QPalette.ColorRole.Window).name(), background)
                    self.assertEqual(widget.palette().color(QPalette.ColorRole.Text).name(), foreground)
            theme = "light" if background == "#ffffff" else "dark"
            colors = dialog_colors(theme)
            for widget in (update, message, progress):
                self.assertEqual(widget.theme, theme)
                self.assertEqual(widget.palette().color(QPalette.ColorRole.Window).name(), colors["surface"])
            for widget in (update.notes_edit, bar):
                self.assertEqual(widget.palette().color(QPalette.ColorRole.Text).name(), colors["text"])
            self.assertFalse(bar.grab().isNull())


if __name__ == "__main__":
    unittest.main()
