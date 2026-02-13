from __future__ import annotations

from typing import Dict


_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "RU": {
        "app_name": "Binity",
        "recycle_bin": "Корзина",
        "tooltip_template": "Корзина: {size}",
        "open_bin": "Открыть корзину",
        "clear_bin": "Очистить корзину",
        "settings": "Настройки",
        "confirm_clear": "Запрашивать подтверждение",
        "double_click_action": "Двойной клик",
        "open_bin_action": "Открыть корзину",
        "clear_bin_action": "Очистить корзину",
        "language": "Язык",
        "language_ru": "Русский",
        "language_en": "Английский",
        "autostart": "Запускать с Windows",
        "sound_after_clear": "Звук после очистки",
        "sound_off": "Без звука",
        "sound_windows": "Системный звук Windows",
        "sound_paper": "Сминание бумаги",
        "overflow_notify": "Уведомлять о переполнении",
        "theme_sync": "Синхронизировать тему Windows",
        "about": "О программе",
        "exit": "Выход",
        "confirm_dialog_title": "Подтверждение очистки корзины",
        "confirm_dialog_message": "Удалить все элементы из корзины без возможности восстановления?",
        "confirm": "Очистить",
        "cancel": "Отмена",
        "about_title": "О программе",
        "version": "Версия",
        "author": "Разработчик",
        "website": "Открыть GitHub",
        "close": "Закрыть",
        "already_running": "Binity уже запущен. Проверьте иконку в системном трее.",
        "error_title": "Ошибка",
        "error_open_failed": "Не удалось открыть корзину.",
        "error_empty_failed": "Не удалось очистить корзину.",
        "autostart_enabled": "Автозапуск включен",
        "autostart_disabled": "Автозапуск отключен",
        "clear_success_message": "Корзина успешно очищена.",
        "overflow_title": "Внимание: корзина переполнена",
        "overflow_message": "Корзина переполнена ({size}).",
    },
    "EN": {
        "app_name": "Binity",
        "recycle_bin": "Recycle Bin",
        "tooltip_template": "Recycle Bin: {size}",
        "open_bin": "Open Recycle Bin",
        "clear_bin": "Empty Recycle Bin",
        "settings": "Settings",
        "confirm_clear": "Ask for confirmation",
        "double_click_action": "Double click",
        "open_bin_action": "Open Recycle Bin",
        "clear_bin_action": "Empty Recycle Bin",
        "language": "Language",
        "language_ru": "Russian",
        "language_en": "English",
        "autostart": "Run with Windows",
        "sound_after_clear": "Sound after empty",
        "sound_off": "No sound",
        "sound_windows": "Windows system sound",
        "sound_paper": "Paper crumple",
        "overflow_notify": "Notify when overloaded",
        "theme_sync": "Sync with Windows theme",
        "about": "About",
        "exit": "Exit",
        "confirm_dialog_title": "Confirm Empty Recycle Bin",
        "confirm_dialog_message": "Delete all items from Recycle Bin permanently?",
        "confirm": "Empty",
        "cancel": "Cancel",
        "about_title": "About",
        "version": "Version",
        "author": "Author",
        "website": "Open GitHub",
        "close": "Close",
        "already_running": "Binity is already running. Check the tray icon.",
        "error_title": "Error",
        "error_open_failed": "Failed to open Recycle Bin.",
        "error_empty_failed": "Failed to empty Recycle Bin.",
        "autostart_enabled": "Autostart enabled",
        "autostart_disabled": "Autostart disabled",
        "clear_success_message": "Recycle Bin emptied successfully.",
        "overflow_title": "Warning: recycle bin overloaded",
        "overflow_message": "Recycle Bin is overloaded ({size}).",
    },
}


class I18n:
    def __init__(self, language: str = "RU") -> None:
        self._language = "RU"
        self.set_language(language)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> str:
        candidate = str(language or "RU").upper()
        if candidate not in _TRANSLATIONS:
            candidate = "RU"
        self._language = candidate
        return self._language

    def tr(self, key: str) -> str:
        return _TRANSLATIONS[self._language].get(key, key)
