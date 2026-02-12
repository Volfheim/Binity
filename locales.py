# -*- coding: utf-8 -*-
class Locale:
    def __init__(self):
        self.current = "RU"
        self.translations = {
            "RU": {
                "app_name": "Binity",
                "recycle_bin": "Корзина",
                "open_bin": "Открыть корзину",
                "clear_bin": "Очистить корзину",
                "settings": "Настройки",
                "confirm_clear": "Запрашивать подтверждение при очистке",
                "double_click_action": "Действие при двойном клике",
                "open_bin_action": "Открыть корзину",
                "clear_bin_action": "Очистить корзину",
                "exit": "Выход",
                "confirm_dialog_title": "Подтверждение очистки корзины",
                "confirm_dialog_message": "Вы уверены, что хотите окончательно удалить все элементы в корзине? Это действие нельзя отменить.",
                "clear_btn": "Очистить",
                "cancel_btn": "Отмена",
                "language": "Язык",
                "language_ru": "Русский",
                "language_en": "Английский",
                "about": "О программе",
                "version": "Версия 2.6",
                "author": "Разработчик: Volfheim",
                "website": "Сайт: Лучший ноут",
                "close": "Закрыть"
            },
            "EN": {
                "app_name": "Binity",
                "recycle_bin": "Recycle Bin",
                "open_bin": "Open Recycle Bin",
                "clear_bin": "Empty Recycle Bin",
                "settings": "Settings",
                "confirm_clear": "Ask for confirmation when emptying",
                "double_click_action": "Double-click action",
                "open_bin_action": "Open Recycle Bin",
                "clear_bin_action": "Empty Recycle Bin",
                "exit": "Exit",
                "confirm_dialog_title": "Confirm Empty Recycle Bin",
                "confirm_dialog_message": "Are you sure you want to permanently delete all items in the Recycle Bin? This action cannot be undone.",
                "clear_btn": "Empty",
                "cancel_btn": "Cancel",
                "language": "Language",
                "language_ru": "Russian",
                "language_en": "English",
                "about": "About",
                "version": "Version 2.6",
                "author": "Developer: Volfheim",
                "website": "Website: Best laptop",
                "close": "Close"
            }
        }

    def set_language(self, lang):
        if lang in self.translations:
            self.current = lang
        return self.current

    def tr(self, key):
        return self.translations[self.current].get(key, key)


# Глобальный объект локализации
locale = Locale()