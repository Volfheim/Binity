from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QIcon
from PyQt6.QtWidgets import QDialog, QMenu, QMessageBox, QSystemTrayIcon

from src.core.formatting import format_size
from src.core.i18n import I18n
from src.core.resources import resource_path
from src.core.settings import Settings
from src.services.autostart import AutostartService
from src.services.recycle_bin import RecycleBinService
from src.services.sound import SOUND_OFF, SOUND_PAPER, SOUND_WINDOWS, SoundService
from src.services.system_theme import SystemThemeService
from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.dialogs.confirm_dialog import ConfirmDialog

OPEN_ACTION = "open"
CLEAR_ACTION = "clear"

ICON_MAP = {
    0: "icons/bin_0.ico",
    1: "icons/bin_25.ico",
    2: "icons/bin_50.ico",
    3: "icons/bin_75.ico",
    4: "icons/bin_full.ico",
}


class _ClearBinTaskSignals(QObject):
    finished = pyqtSignal(bool)


class _ClearBinTask(QRunnable):
    def __init__(self, recycle_bin: RecycleBinService) -> None:
        super().__init__()
        self.recycle_bin = recycle_bin
        self.signals = _ClearBinTaskSignals()

    def run(self) -> None:
        success = self.recycle_bin.empty_bin()
        self.signals.finished.emit(success)


class TrayApp(QObject):
    def __init__(self, settings: Settings, i18n: I18n) -> None:
        super().__init__()
        self.settings = settings
        self.i18n = i18n

        self.recycle_bin = RecycleBinService()
        self.autostart = AutostartService()
        self.sound_service = SoundService()
        self.theme_service = SystemThemeService()

        self.current_theme = self.theme_service.get_theme()
        self.icons = self._load_icons(self.current_theme)
        self.current_level = -1

        self.tray = QSystemTrayIcon(self)
        self.tray.activated.connect(self._on_tray_activated)

        self._about_dialog: AboutDialog | None = None
        self._confirm_dialog: ConfirmDialog | None = None
        self._clear_in_progress = False
        self._clear_task: _ClearBinTask | None = None
        self._overflow_notified = False
        self._thread_pool = QThreadPool.globalInstance()

        self._build_menu()
        self._apply_menu_state()
        self._update_texts()

        self._refresh_state()
        self.tray.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_state)
        self.timer.start(self.settings.update_interval_sec * 1000)

    def _theme_icon_path(self, relative_path: str, theme: str) -> str:
        filename = Path(relative_path).name
        themed_path = resource_path(f"icons/{theme}/{filename}")
        if Path(themed_path).exists():
            return themed_path
        return resource_path(relative_path)

    def _load_icons(self, theme: str) -> Dict[int, QIcon]:
        icons: Dict[int, QIcon] = {}
        for level, relative_path in ICON_MAP.items():
            candidate = self._theme_icon_path(relative_path, theme)
            if Path(candidate).exists():
                icons[level] = QIcon(str(candidate))

        fallback = icons.get(0) or icons.get(4)
        if fallback is None:
            fallback = QIcon(resource_path("icons/bin_full.ico"))

        for level in ICON_MAP:
            icons.setdefault(level, fallback)
        return icons

    def _build_menu(self) -> None:
        self.menu = QMenu()

        self.open_action = QAction(self.menu)
        self.open_action.triggered.connect(self.open_bin)
        self.menu.addAction(self.open_action)

        self.clear_action = QAction(self.menu)
        self.clear_action.triggered.connect(self.clear_bin)
        self.menu.addAction(self.clear_action)

        self.settings_menu = QMenu(self.menu)

        self.confirm_action = QAction(self.settings_menu)
        self.confirm_action.setCheckable(True)
        self.confirm_action.toggled.connect(self._on_confirm_toggled)
        self.settings_menu.addAction(self.confirm_action)

        self.double_click_menu = QMenu(self.settings_menu)
        self.double_click_group = QActionGroup(self.double_click_menu)
        self.double_click_group.setExclusive(True)

        self.double_click_open_action = QAction(self.double_click_menu)
        self.double_click_open_action.setCheckable(True)
        self.double_click_open_action.triggered.connect(
            lambda: self._set_double_click_action(OPEN_ACTION)
        )

        self.double_click_clear_action = QAction(self.double_click_menu)
        self.double_click_clear_action.setCheckable(True)
        self.double_click_clear_action.triggered.connect(
            lambda: self._set_double_click_action(CLEAR_ACTION)
        )

        self.double_click_group.addAction(self.double_click_open_action)
        self.double_click_group.addAction(self.double_click_clear_action)

        self.double_click_menu.addAction(self.double_click_open_action)
        self.double_click_menu.addAction(self.double_click_clear_action)
        self.settings_menu.addMenu(self.double_click_menu)

        self.language_menu = QMenu(self.settings_menu)
        self.language_group = QActionGroup(self.language_menu)
        self.language_group.setExclusive(True)

        self.language_ru_action = QAction(self.language_menu)
        self.language_ru_action.setCheckable(True)
        self.language_ru_action.triggered.connect(lambda: self._set_language("RU"))

        self.language_en_action = QAction(self.language_menu)
        self.language_en_action.setCheckable(True)
        self.language_en_action.triggered.connect(lambda: self._set_language("EN"))

        self.language_group.addAction(self.language_ru_action)
        self.language_group.addAction(self.language_en_action)

        self.language_menu.addAction(self.language_ru_action)
        self.language_menu.addAction(self.language_en_action)
        self.settings_menu.addMenu(self.language_menu)

        self.autostart_action = QAction(self.settings_menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.toggled.connect(self._on_autostart_toggled)
        self.settings_menu.addAction(self.autostart_action)

        self.sound_menu = QMenu(self.settings_menu)
        self.sound_group = QActionGroup(self.sound_menu)
        self.sound_group.setExclusive(True)

        self.sound_off_action = QAction(self.sound_menu)
        self.sound_off_action.setCheckable(True)
        self.sound_off_action.triggered.connect(lambda: self._set_clear_sound(SOUND_OFF))

        self.sound_windows_action = QAction(self.sound_menu)
        self.sound_windows_action.setCheckable(True)
        self.sound_windows_action.triggered.connect(lambda: self._set_clear_sound(SOUND_WINDOWS))

        self.sound_paper_action = QAction(self.sound_menu)
        self.sound_paper_action.setCheckable(True)
        self.sound_paper_action.triggered.connect(lambda: self._set_clear_sound(SOUND_PAPER))

        self.sound_group.addAction(self.sound_off_action)
        self.sound_group.addAction(self.sound_windows_action)
        self.sound_group.addAction(self.sound_paper_action)

        self.sound_menu.addAction(self.sound_off_action)
        self.sound_menu.addAction(self.sound_windows_action)
        self.sound_menu.addAction(self.sound_paper_action)
        self.settings_menu.addMenu(self.sound_menu)

        self.overflow_notify_action = QAction(self.settings_menu)
        self.overflow_notify_action.setCheckable(True)
        self.overflow_notify_action.toggled.connect(self._on_overflow_notify_toggled)
        self.settings_menu.addAction(self.overflow_notify_action)

        self.theme_sync_action = QAction(self.settings_menu)
        self.theme_sync_action.setCheckable(True)
        self.theme_sync_action.toggled.connect(self._on_theme_sync_toggled)
        self.settings_menu.addAction(self.theme_sync_action)

        self.menu.addMenu(self.settings_menu)
        self.menu.addSeparator()

        self.about_action = QAction(self.menu)
        self.about_action.triggered.connect(self.show_about)
        self.menu.addAction(self.about_action)

        self.exit_action = QAction(self.menu)
        self.exit_action.triggered.connect(self.quit_app)
        self.menu.addAction(self.exit_action)

        self.tray.setContextMenu(self.menu)

    def _apply_menu_state(self) -> None:
        self.confirm_action.blockSignals(True)
        self.confirm_action.setChecked(self.settings.confirm_clear)
        self.confirm_action.blockSignals(False)

        current_action = self.settings.double_click_action
        self.double_click_open_action.setChecked(current_action == OPEN_ACTION)
        self.double_click_clear_action.setChecked(current_action == CLEAR_ACTION)

        current_language = self.settings.language
        self.language_ru_action.setChecked(current_language == "RU")
        self.language_en_action.setChecked(current_language == "EN")

        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(self.autostart.is_enabled())
        self.autostart_action.blockSignals(False)

        sound_mode = self.settings.clear_sound
        self.sound_off_action.setChecked(sound_mode == SOUND_OFF)
        self.sound_windows_action.setChecked(sound_mode == SOUND_WINDOWS)
        self.sound_paper_action.setChecked(sound_mode == SOUND_PAPER)

        self.overflow_notify_action.blockSignals(True)
        self.overflow_notify_action.setChecked(self.settings.overflow_notify_enabled)
        self.overflow_notify_action.blockSignals(False)

        self.theme_sync_action.blockSignals(True)
        self.theme_sync_action.setChecked(self.settings.theme_sync)
        self.theme_sync_action.blockSignals(False)

    def _update_texts(self) -> None:
        self.open_action.setText(self.i18n.tr("open_bin"))
        self.clear_action.setText(self.i18n.tr("clear_bin"))

        self.settings_menu.setTitle(self.i18n.tr("settings"))
        self.confirm_action.setText(self.i18n.tr("confirm_clear"))

        self.double_click_menu.setTitle(self.i18n.tr("double_click_action"))
        self.double_click_open_action.setText(self.i18n.tr("open_bin_action"))
        self.double_click_clear_action.setText(self.i18n.tr("clear_bin_action"))

        self.language_menu.setTitle(self.i18n.tr("language"))
        self.language_ru_action.setText(self.i18n.tr("language_ru"))
        self.language_en_action.setText(self.i18n.tr("language_en"))

        self.autostart_action.setText(self.i18n.tr("autostart"))

        self.sound_menu.setTitle(self.i18n.tr("sound_after_clear"))
        self.sound_off_action.setText(self.i18n.tr("sound_off"))
        self.sound_windows_action.setText(self.i18n.tr("sound_windows"))
        self.sound_paper_action.setText(self.i18n.tr("sound_paper"))

        self.overflow_notify_action.setText(self.i18n.tr("overflow_notify"))
        self.theme_sync_action.setText(self.i18n.tr("theme_sync"))

        self.about_action.setText(self.i18n.tr("about"))
        self.exit_action.setText(self.i18n.tr("exit"))

        if self._about_dialog and self._about_dialog.isVisible():
            self._about_dialog.refresh_texts()
        if self._confirm_dialog and self._confirm_dialog.isVisible():
            self._confirm_dialog.refresh_texts()

    def _sync_system_theme(self) -> None:
        if not self.settings.theme_sync:
            return

        detected_theme = self.theme_service.get_theme()
        if detected_theme == self.current_theme:
            return

        self.current_theme = detected_theme
        self.icons = self._load_icons(self.current_theme)
        self.current_level = -1

        if self._about_dialog and self._about_dialog.isVisible():
            self._about_dialog.set_theme(self.current_theme)

    def _handle_overflow_notification(self, size_bytes: int) -> None:
        if not self.settings.overflow_notify_enabled:
            self._overflow_notified = False
            return

        threshold = self.settings.overflow_notify_threshold_gb * 1024**3
        if size_bytes >= threshold:
            if not self._overflow_notified:
                self._overflow_notified = True
                self.tray.showMessage(
                    self.i18n.tr("overflow_title"),
                    self.i18n.tr("overflow_message").format(size=format_size(size_bytes)),
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000,
                )
        else:
            self._overflow_notified = False

    def _refresh_state(self) -> None:
        self._sync_system_theme()

        info = self.recycle_bin.get_info()
        level = self.recycle_bin.level_from_metrics(info.size_bytes, info.items)
        if level != self.current_level:
            self.current_level = level
            self.tray.setIcon(self.icons.get(level, self.icons[0]))

        tooltip = self.i18n.tr("tooltip_template").format(size=format_size(info.size_bytes))
        self.tray.setToolTip(tooltip)

        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(self.autostart.is_enabled())
        self.autostart_action.blockSignals(False)

        self._handle_overflow_notification(info.size_bytes)

    def _on_confirm_toggled(self, enabled: bool) -> None:
        self.settings.set("confirm_clear", bool(enabled))

    def _set_double_click_action(self, action: str) -> None:
        if action not in (OPEN_ACTION, CLEAR_ACTION):
            return
        self.settings.set("double_click_action", action)
        self._apply_menu_state()

    def _set_clear_sound(self, mode: str) -> None:
        if mode not in (SOUND_OFF, SOUND_WINDOWS, SOUND_PAPER):
            return
        self.settings.set("clear_sound", mode)
        self._apply_menu_state()

    def _on_overflow_notify_toggled(self, enabled: bool) -> None:
        self.settings.set("overflow_notify_enabled", bool(enabled))
        if not enabled:
            self._overflow_notified = False

    def _on_theme_sync_toggled(self, enabled: bool) -> None:
        self.settings.set("theme_sync", bool(enabled))
        if enabled:
            self._sync_system_theme()

    def _set_language(self, language: str) -> None:
        self.settings.set("language", language)
        self.i18n.set_language(language)
        self._apply_menu_state()
        self._update_texts()
        self._refresh_state()

    def _on_autostart_toggled(self, enabled: bool) -> None:
        success = self.autostart.set_enabled(bool(enabled))
        if not success:
            self._show_error(self.i18n.tr("autostart_disabled"))
            self._apply_menu_state()
            return

        message = self.i18n.tr("autostart_enabled") if enabled else self.i18n.tr("autostart_disabled")
        self.tray.showMessage(self.i18n.tr("app_name"), message, QSystemTrayIcon.MessageIcon.Information, 1800)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason != QSystemTrayIcon.ActivationReason.DoubleClick:
            return
        if self.settings.double_click_action == CLEAR_ACTION:
            self.clear_bin()
        else:
            self.open_bin()

    def open_bin(self) -> None:
        if not self.recycle_bin.open_bin():
            self._show_error(self.i18n.tr("error_open_failed"))

    def clear_bin(self) -> None:
        if self._clear_in_progress:
            return

        if self.settings.confirm_clear:
            if self._confirm_dialog and self._confirm_dialog.isVisible():
                self._focus_dialog(self._confirm_dialog)
                return

            self._confirm_dialog = ConfirmDialog(self.i18n)
            try:
                if self._confirm_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
            finally:
                self._confirm_dialog = None

        self._start_clear_task()

    def _start_clear_task(self) -> None:
        self._clear_in_progress = True
        self.clear_action.setEnabled(False)
        self.double_click_clear_action.setEnabled(False)

        task = _ClearBinTask(self.recycle_bin)
        task.signals.finished.connect(self._on_clear_task_finished)
        self._clear_task = task
        self._thread_pool.start(task)

    def _on_clear_task_finished(self, success: bool) -> None:
        self._clear_in_progress = False
        self.clear_action.setEnabled(True)
        self.double_click_clear_action.setEnabled(True)
        self._clear_task = None

        if not success:
            self._show_error(self.i18n.tr("error_empty_failed"))
            return

        self.sound_service.play_clear_success(self.settings.clear_sound)
        self.tray.showMessage(
            self.i18n.tr("app_name"),
            self.i18n.tr("clear_success_message"),
            QSystemTrayIcon.MessageIcon.Information,
            2200,
        )
        self._refresh_state()

    def show_about(self) -> None:
        if self._about_dialog is None:
            self._about_dialog = AboutDialog(self.i18n, theme=self.current_theme)

        self._about_dialog.set_theme(self.current_theme)
        self._about_dialog.refresh_texts()
        self._about_dialog.show()
        self._about_dialog.raise_()
        self._about_dialog.activateWindow()

    def quit_app(self) -> None:
        self.timer.stop()
        self.tray.hide()
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _show_error(self, message: str) -> None:
        self.tray.showMessage(self.i18n.tr("error_title"), message, QSystemTrayIcon.MessageIcon.Warning, 3500)
        QMessageBox.warning(None, self.i18n.tr("error_title"), message)

    @staticmethod
    def _focus_dialog(dialog: QDialog) -> None:
        dialog.showNormal()
        dialog.raise_()
        dialog.activateWindow()
