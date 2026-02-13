from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QProgressDialog, QSystemTrayIcon

from src.core.formatting import format_size
from src.core.i18n import I18n
from src.core.resources import resource_path
from src.core.settings import Settings
from src.core.updater import UpdateInfo, Updater
from src.services.autostart import AutostartService
from src.services.recycle_bin import (
    BinClearResult,
    RecycleBinService,
    SECURE_DELETE_MODES,
    SECURE_DELETE_OFF,
    SECURE_DELETE_RANDOM,
    SECURE_DELETE_ZERO,
)
from src.services.sound import SOUND_OFF, SOUND_PAPER, SOUND_WINDOWS, SoundService
from src.services.system_theme import SystemThemeService
from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.dialogs.confirm_dialog import ConfirmDialog

OPEN_ACTION = "open"
CLEAR_ACTION = "clear"
UPDATE_TIMER_INTERVAL_MS = 30 * 60 * 1000

ICON_MAP = {
    0: "icons/bin_0.ico",
    1: "icons/bin_25.ico",
    2: "icons/bin_50.ico",
    3: "icons/bin_75.ico",
    4: "icons/bin_full.ico",
}


class _ClearBinTaskSignals(QObject):
    finished = pyqtSignal(object)


class _ClearBinTask(QRunnable):
    def __init__(self, recycle_bin: RecycleBinService, secure_mode: str) -> None:
        super().__init__()
        self.recycle_bin = recycle_bin
        self.secure_mode = secure_mode
        self.signals = _ClearBinTaskSignals()

    def run(self) -> None:
        result = self.recycle_bin.empty_bin(self.secure_mode)
        self.signals.finished.emit(result)


class _UpdateCheckTaskSignals(QObject):
    finished = pyqtSignal(object, str, bool)


class _UpdateCheckTask(QRunnable):
    def __init__(self, updater: Updater, force: bool, manual: bool) -> None:
        super().__init__()
        self.updater = updater
        self.force = bool(force)
        self.manual = bool(manual)
        self.signals = _UpdateCheckTaskSignals()

    def run(self) -> None:
        info = self.updater.check_for_update(force=self.force)
        error = str(self.updater.last_error or "")
        self.signals.finished.emit(info, error, self.manual)


class _UpdateDownloadTaskSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, str)


class _UpdateDownloadTask(QRunnable):
    def __init__(self, updater: Updater) -> None:
        super().__init__()
        self.updater = updater
        self.signals = _UpdateDownloadTaskSignals()

    def run(self) -> None:
        downloaded = self.updater.download_update(on_progress=self.signals.progress.emit)
        downloaded_path = str(downloaded) if downloaded else ""
        error = str(self.updater.last_error or "")
        self.signals.finished.emit(downloaded_path, error)


class TrayApp(QObject):
    def __init__(self, settings: Settings, i18n: I18n, show_after_update: bool = False) -> None:
        super().__init__()
        self.settings = settings
        self.i18n = i18n

        self.recycle_bin = RecycleBinService()
        self.autostart = AutostartService()
        self.sound_service = SoundService()
        self.theme_service = SystemThemeService()
        self.updater = Updater(settings)

        self.current_theme = self.theme_service.get_theme()
        self.icons = self._load_icons(self.current_theme)
        self.current_level = -1

        self.tray = QSystemTrayIcon(self)
        self.tray.activated.connect(self._on_tray_activated)

        self._about_dialog: AboutDialog | None = None
        self._confirm_dialog: ConfirmDialog | None = None
        self._clear_in_progress = False
        self._clear_task: _ClearBinTask | None = None

        self._update_check_in_progress = False
        self._update_download_in_progress = False
        self._update_check_task: _UpdateCheckTask | None = None
        self._update_download_task: _UpdateDownloadTask | None = None
        self._update_progress_dialog: QProgressDialog | None = None
        self._update_notified_version = ""

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

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._schedule_auto_update_check)
        self.update_timer.start(UPDATE_TIMER_INTERVAL_MS)
        QTimer.singleShot(5000, self._schedule_auto_update_check)

        if show_after_update or self.updater.just_updated:
            QTimer.singleShot(
                1800,
                self._show_post_update_notification,
            )

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

        self.secure_delete_menu = QMenu(self.settings_menu)
        self.secure_delete_group = QActionGroup(self.secure_delete_menu)
        self.secure_delete_group.setExclusive(True)

        self.secure_delete_off_action = QAction(self.secure_delete_menu)
        self.secure_delete_off_action.setCheckable(True)
        self.secure_delete_off_action.triggered.connect(
            lambda: self._set_secure_delete_mode(SECURE_DELETE_OFF)
        )

        self.secure_delete_zero_action = QAction(self.secure_delete_menu)
        self.secure_delete_zero_action.setCheckable(True)
        self.secure_delete_zero_action.triggered.connect(
            lambda: self._set_secure_delete_mode(SECURE_DELETE_ZERO)
        )

        self.secure_delete_random_action = QAction(self.secure_delete_menu)
        self.secure_delete_random_action.setCheckable(True)
        self.secure_delete_random_action.triggered.connect(
            lambda: self._set_secure_delete_mode(SECURE_DELETE_RANDOM)
        )

        self.secure_delete_group.addAction(self.secure_delete_off_action)
        self.secure_delete_group.addAction(self.secure_delete_zero_action)
        self.secure_delete_group.addAction(self.secure_delete_random_action)

        self.secure_delete_menu.addAction(self.secure_delete_off_action)
        self.secure_delete_menu.addAction(self.secure_delete_zero_action)
        self.secure_delete_menu.addAction(self.secure_delete_random_action)
        self.secure_delete_menu.addSeparator()

        self.secure_delete_load_note_action = QAction(self.secure_delete_menu)
        self.secure_delete_load_note_action.setEnabled(False)
        self.secure_delete_menu.addAction(self.secure_delete_load_note_action)
        self.settings_menu.addMenu(self.secure_delete_menu)

        self.overflow_notify_action = QAction(self.settings_menu)
        self.overflow_notify_action.setCheckable(True)
        self.overflow_notify_action.toggled.connect(self._on_overflow_notify_toggled)
        self.settings_menu.addAction(self.overflow_notify_action)

        self.theme_sync_action = QAction(self.settings_menu)
        self.theme_sync_action.setCheckable(True)
        self.theme_sync_action.toggled.connect(self._on_theme_sync_toggled)
        self.settings_menu.addAction(self.theme_sync_action)

        self.auto_updates_action = QAction(self.settings_menu)
        self.auto_updates_action.setCheckable(True)
        self.auto_updates_action.toggled.connect(self._on_auto_updates_toggled)
        self.settings_menu.addAction(self.auto_updates_action)

        self.menu.addMenu(self.settings_menu)

        self.check_updates_action = QAction(self.menu)
        self.check_updates_action.triggered.connect(lambda: self._check_for_updates(force=True, manual=True))
        self.menu.addAction(self.check_updates_action)

        self.update_now_action = QAction(self.menu)
        self.update_now_action.triggered.connect(self._show_update_dialog)
        self.update_now_action.setVisible(False)
        self.menu.addAction(self.update_now_action)

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

        secure_mode = self.settings.secure_delete_mode
        self.secure_delete_off_action.setChecked(secure_mode == SECURE_DELETE_OFF)
        self.secure_delete_zero_action.setChecked(secure_mode == SECURE_DELETE_ZERO)
        self.secure_delete_random_action.setChecked(secure_mode == SECURE_DELETE_RANDOM)

        self.overflow_notify_action.blockSignals(True)
        self.overflow_notify_action.setChecked(self.settings.overflow_notify_enabled)
        self.overflow_notify_action.blockSignals(False)

        self.theme_sync_action.blockSignals(True)
        self.theme_sync_action.setChecked(self.settings.theme_sync)
        self.theme_sync_action.blockSignals(False)

        self.auto_updates_action.blockSignals(True)
        self.auto_updates_action.setChecked(self.settings.auto_check_updates)
        self.auto_updates_action.blockSignals(False)

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

        self.secure_delete_menu.setTitle(self.i18n.tr("secure_delete"))
        self.secure_delete_off_action.setText(self.i18n.tr("secure_delete_off"))
        self.secure_delete_zero_action.setText(self.i18n.tr("secure_delete_zero"))
        self.secure_delete_random_action.setText(self.i18n.tr("secure_delete_random"))
        self.secure_delete_load_note_action.setText(self.i18n.tr("secure_delete_load_note"))

        self.overflow_notify_action.setText(self.i18n.tr("overflow_notify"))
        self.theme_sync_action.setText(self.i18n.tr("theme_sync"))
        self.auto_updates_action.setText(self.i18n.tr("auto_check_updates"))
        self.check_updates_action.setText(self.i18n.tr("check_updates"))

        self.about_action.setText(self.i18n.tr("about"))
        self.exit_action.setText(self.i18n.tr("exit"))

        self._refresh_update_action_text()

        if self._about_dialog and self._about_dialog.isVisible():
            self._about_dialog.refresh_texts()
        if self._confirm_dialog and self._confirm_dialog.isVisible():
            self._confirm_dialog.refresh_texts()

    def _refresh_update_action_text(self) -> None:
        if self._update_download_in_progress:
            self.update_now_action.setVisible(True)
            self.update_now_action.setEnabled(False)
            return

        if self.updater.has_update:
            version = self.updater.update_version.lstrip("vV")
            self.update_now_action.setText(self.i18n.tr("update_now").format(version=version))
            self.update_now_action.setVisible(True)
            self.update_now_action.setEnabled(True)
        else:
            self.update_now_action.setVisible(False)
            self.update_now_action.setEnabled(False)

    def _window_icon(self) -> QIcon:
        app = QApplication.instance()
        if app is not None:
            app_icon = app.windowIcon()
            if not app_icon.isNull():
                return app_icon

        tray_icon = self.icons.get(self.current_level)
        if tray_icon and not tray_icon.isNull():
            return tray_icon

        fallback = QIcon(resource_path("icons/bin_full.ico"))
        return fallback

    def _build_message_box(
        self,
        icon: QMessageBox.Icon,
        title: str,
        text: str,
        informative_text: str = "",
        detailed_text: str = "",
    ) -> QMessageBox:
        box = QMessageBox()
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        if informative_text:
            box.setInformativeText(informative_text)
        if detailed_text:
            box.setDetailedText(detailed_text)

        window_icon = self._window_icon()
        if not window_icon.isNull():
            box.setWindowIcon(window_icon)

        return box

    def _show_update_progress_dialog(self) -> None:
        if self._update_progress_dialog is None:
            dialog = QProgressDialog(
                self.i18n.tr("update_downloading_progress").format(percent=0),
                "",
                0,
                100,
                None,
            )
            dialog.setWindowModality(Qt.WindowModality.NonModal)
            dialog.setAutoClose(False)
            dialog.setAutoReset(False)
            dialog.setCancelButton(None)
            dialog.setMinimumDuration(0)
            window_icon = self._window_icon()
            if not window_icon.isNull():
                dialog.setWindowIcon(window_icon)
            self._update_progress_dialog = dialog

        self._update_progress_dialog.setWindowTitle(self.i18n.tr("update_dialog_title"))
        self._update_progress_dialog.setLabelText(self.i18n.tr("update_downloading_progress").format(percent=0))
        self._update_progress_dialog.setValue(0)
        self._update_progress_dialog.show()

    def _close_update_progress_dialog(self) -> None:
        if self._update_progress_dialog is None:
            return
        self._update_progress_dialog.hide()
        self._update_progress_dialog.deleteLater()
        self._update_progress_dialog = None

    @staticmethod
    def _format_release_notes(raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            return "-"

        lines = []
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            current = line.rstrip()
            if not current.strip():
                lines.append("")
                continue

            current = re.sub(r"^\s{0,3}#{1,6}\s*", "", current)
            bullet = bool(re.match(r"^\s*[-*+]\s+", current))
            if bullet:
                current = re.sub(r"^\s*[-*+]\s+", "", current)

            current = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\1", current)
            current = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", current)
            current = re.sub(r"`([^`]*)`", r"\1", current)
            current = current.replace("**", "").replace("__", "")
            current = re.sub(r"~~([^~]+)~~", r"\1", current)
            current = current.strip()

            if bullet and current:
                current = f"- {current}"
            lines.append(current)

        normalized = "\n".join(lines)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        return normalized or "-"

    def _show_post_update_notification(self) -> None:
        if self.updater.launched_from_fallback_path:
            self.tray.showMessage(
                self.i18n.tr("app_name"),
                self.i18n.tr("update_running_from_fallback").format(
                    path=self.updater.launch_target_path,
                    final=self.updater.launch_final_path,
                ),
                QSystemTrayIcon.MessageIcon.Warning,
                6500,
            )
            return

        self.tray.showMessage(
            self.i18n.tr("app_name"),
            self.i18n.tr("update_installed"),
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

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

    def _set_secure_delete_mode(self, mode: str) -> None:
        if mode not in SECURE_DELETE_MODES:
            return

        current_mode = self.settings.secure_delete_mode
        if current_mode == mode:
            self._apply_menu_state()
            return

        self.settings.set("secure_delete_mode", mode)
        self._apply_menu_state()

        if mode != SECURE_DELETE_OFF and not self.settings.secure_delete_info_ack:
            info_box = self._build_message_box(
                QMessageBox.Icon.Information,
                self.i18n.tr("secure_delete_info_title"),
                self.i18n.tr("secure_delete_info_message"),
            )
            info_box.exec()
            self.settings.set("secure_delete_info_ack", True)

    def _build_confirm_message(self) -> str:
        mode = self.settings.secure_delete_mode
        if mode == SECURE_DELETE_ZERO:
            return self.i18n.tr("confirm_dialog_message_secure_zero")
        if mode == SECURE_DELETE_RANDOM:
            return self.i18n.tr("confirm_dialog_message_secure_random")
        return self.i18n.tr("confirm_dialog_message")

    def _on_overflow_notify_toggled(self, enabled: bool) -> None:
        self.settings.set("overflow_notify_enabled", bool(enabled))
        if not enabled:
            self._overflow_notified = False

    def _on_theme_sync_toggled(self, enabled: bool) -> None:
        self.settings.set("theme_sync", bool(enabled))
        if enabled:
            self._sync_system_theme()

    def _on_auto_updates_toggled(self, enabled: bool) -> None:
        self.settings.set("auto_check_updates", bool(enabled))
        if enabled:
            self._schedule_auto_update_check()

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

            self._confirm_dialog = ConfirmDialog(self.i18n, message_override=self._build_confirm_message())
            try:
                if self._confirm_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
            finally:
                self._confirm_dialog = None

        self._start_clear_task(self.settings.secure_delete_mode)

    def _start_clear_task(self, secure_mode: str) -> None:
        self._clear_in_progress = True
        self.clear_action.setEnabled(False)
        self.double_click_clear_action.setEnabled(False)

        if secure_mode != SECURE_DELETE_OFF:
            self.tray.showMessage(
                self.i18n.tr("app_name"),
                self.i18n.tr("secure_clear_started"),
                QSystemTrayIcon.MessageIcon.Information,
                2400,
            )

        task = _ClearBinTask(self.recycle_bin, secure_mode=secure_mode)
        task.signals.finished.connect(self._on_clear_task_finished)
        self._clear_task = task
        self._thread_pool.start(task)

    def _on_clear_task_finished(self, result_obj: object) -> None:
        self._clear_in_progress = False
        self.clear_action.setEnabled(True)
        self.double_click_clear_action.setEnabled(True)
        self._clear_task = None

        result = result_obj if isinstance(result_obj, BinClearResult) else BinClearResult(False, SECURE_DELETE_OFF)
        if not result.success:
            self._show_error(self.i18n.tr("error_empty_failed"))
            return

        self.sound_service.play_clear_success(self.settings.clear_sound)
        if result.secure_mode == SECURE_DELETE_OFF:
            message = self.i18n.tr("clear_success_message")
        else:
            message = self.i18n.tr("secure_clear_success_message").format(
                files=result.wiped_files,
                size=format_size(result.wiped_bytes),
            )
            if result.wipe_failures > 0:
                message = f"{message}\n{self.i18n.tr('secure_clear_partial_message').format(failed=result.wipe_failures)}"

        self.tray.showMessage(self.i18n.tr("app_name"), message, QSystemTrayIcon.MessageIcon.Information, 3500)
        self._refresh_state()

    def _schedule_auto_update_check(self) -> None:
        if not self.settings.auto_check_updates:
            return
        self._check_for_updates(force=False, manual=False)

    def _check_for_updates(self, force: bool, manual: bool) -> None:
        if self._update_check_in_progress or self._update_download_in_progress:
            return

        self._update_check_in_progress = True
        self.check_updates_action.setEnabled(False)

        if manual:
            self.tray.showMessage(
                self.i18n.tr("app_name"),
                self.i18n.tr("update_checking"),
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

        task = _UpdateCheckTask(self.updater, force=force, manual=manual)
        task.signals.finished.connect(self._on_update_check_finished)
        self._update_check_task = task
        self._thread_pool.start(task)

    def _on_update_check_finished(self, info_obj: object, error: str, manual: bool) -> None:
        self._update_check_in_progress = False
        self._update_check_task = None
        if not self._update_download_in_progress:
            self.check_updates_action.setEnabled(True)

        info = info_obj if isinstance(info_obj, UpdateInfo) else None
        self._refresh_update_action_text()

        if info:
            if info.version != self._update_notified_version:
                self._update_notified_version = info.version
                self.tray.showMessage(
                    self.i18n.tr("update_available_title"),
                    self.i18n.tr("update_available_message").format(version=info.version),
                    QSystemTrayIcon.MessageIcon.Information,
                    4200,
                )
            if manual:
                self._show_update_dialog()
            return

        if error and manual:
            self._show_error(f"{self.i18n.tr('error_update_check')}\n{error}")
            return

        if manual:
            info_box = self._build_message_box(
                QMessageBox.Icon.Information,
                self.i18n.tr("update_dialog_title"),
                self.i18n.tr("update_not_found"),
            )
            info_box.exec()

    def _show_update_dialog(self) -> None:
        if self._update_download_in_progress:
            return
        if not self.updater.has_update:
            self._check_for_updates(force=True, manual=True)
            return

        release_notes = self._format_release_notes(self.updater.update_body)
        msg = self._build_message_box(
            QMessageBox.Icon.Information,
            self.i18n.tr("update_dialog_title"),
            self.i18n.tr("update_dialog_message").format(version=self.updater.update_version),
            informative_text=self.i18n.tr("update_dialog_hint"),
            detailed_text=f"{self.i18n.tr('release_notes')}:\n\n{release_notes}",
        )
        msg.setStyleSheet(
            """
            QLabel {
                min-width: 520px;
            }
            QTextEdit {
                min-width: 560px;
                min-height: 260px;
            }
            """
        )

        btn_update = msg.addButton(self.i18n.tr("update_install"), QMessageBox.ButtonRole.AcceptRole)
        btn_skip = msg.addButton(self.i18n.tr("update_skip"), QMessageBox.ButtonRole.DestructiveRole)
        btn_later = msg.addButton(self.i18n.tr("update_later"), QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_update)
        msg.exec()

        if msg.clickedButton() == btn_update:
            self._start_update_download()
        elif msg.clickedButton() == btn_skip:
            self.updater.skip_version()
            self._update_notified_version = ""
            self._refresh_update_action_text()
        elif msg.clickedButton() == btn_later:
            pass

    def _start_update_download(self) -> None:
        if self._update_download_in_progress:
            return
        if not self.updater.has_update:
            return

        self._update_download_in_progress = True
        self.check_updates_action.setEnabled(False)
        self.update_now_action.setVisible(True)
        self.update_now_action.setEnabled(False)
        self.update_now_action.setText(self.i18n.tr("update_downloading_progress").format(percent=0))
        self._show_update_progress_dialog()

        self.tray.showMessage(
            self.i18n.tr("app_name"),
            self.i18n.tr("update_downloading"),
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

        task = _UpdateDownloadTask(self.updater)
        task.signals.progress.connect(self._on_update_download_progress)
        task.signals.finished.connect(self._on_update_download_finished)
        self._update_download_task = task
        self._thread_pool.start(task)

    def _on_update_download_progress(self, percent: int) -> None:
        self.update_now_action.setText(self.i18n.tr("update_downloading_progress").format(percent=percent))
        if self._update_progress_dialog is not None:
            self._update_progress_dialog.setLabelText(self.i18n.tr("update_downloading_progress").format(percent=percent))
            self._update_progress_dialog.setValue(max(0, min(100, int(percent))))

    def _on_update_download_finished(self, downloaded_path: str, error: str) -> None:
        self._update_download_in_progress = False
        self._update_download_task = None
        self.check_updates_action.setEnabled(True)
        self._close_update_progress_dialog()

        if not downloaded_path:
            message = self.i18n.tr("error_update_download")
            if error:
                message = f"{message}\n{error}"
            self._refresh_update_action_text()
            self._show_error(message)
            return

        self.tray.showMessage(
            self.i18n.tr("app_name"),
            self.i18n.tr("update_applying"),
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )

        if not self.updater.apply_update(Path(downloaded_path)):
            message = self.i18n.tr("error_update_apply")
            if self.updater.last_error:
                message = f"{message}\n{self.updater.last_error}"
            self._refresh_update_action_text()
            self._show_error(message)
            return

        self.quit_app()

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
        self.update_timer.stop()
        self._close_update_progress_dialog()
        self.tray.hide()
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _show_error(self, message: str) -> None:
        self.tray.showMessage(self.i18n.tr("error_title"), message, QSystemTrayIcon.MessageIcon.Warning, 3500)
        warning_box = self._build_message_box(
            QMessageBox.Icon.Warning,
            self.i18n.tr("error_title"),
            message,
        )
        warning_box.exec()

    @staticmethod
    def _focus_dialog(dialog: QDialog) -> None:
        dialog.showNormal()
        dialog.raise_()
        dialog.activateWindow()
