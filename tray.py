import pystray
from PIL import Image, ImageTk
from threading import Thread, Event, Lock
import time
import winreg
import ctypes
from bin_control import get_bin_level, empty_bin, open_recycle_bin, get_bin_size
from utils import resource_path
import tkinter as tk
from tkinter import ttk
import threading
import os
import logging
import webbrowser
from locales import locale

logger = logging.getLogger(__name__)

# Настройки реестра
CONFIRM_KEY = r"Software\Binity"
CONFIRM_VALUE = "ConfirmClear"
DOUBLE_CLICK_ACTION = "DoubleClickAction"
LANGUAGE_VALUE = "Language"

# Возможные действия при двойном клике
OPEN_BIN_ACTION = 0
CLEAR_BIN_ACTION = 1

# Настройка DPI для Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per Monitor DPI aware
except:
    pass


def get_reg_value(name, default, reg_type=winreg.REG_DWORD):
    """Универсальная функция для чтения из реестра"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except:
        return default


def set_reg_value(name, value, reg_type=winreg.REG_DWORD):
    """Универсальная функция для записи в реестр"""
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
        winreg.SetValueEx(key, name, 0, reg_type, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Ошибка записи в реестр: {e}")
        return False


def get_confirm_setting():
    return get_reg_value(CONFIRM_VALUE, 1)


def set_confirm_setting(value):
    return set_reg_value(CONFIRM_VALUE, value)


def get_double_click_action():
    return get_reg_value(DOUBLE_CLICK_ACTION, OPEN_BIN_ACTION)


def set_double_click_action(value):
    return set_reg_value(DOUBLE_CLICK_ACTION, value)


def get_language():
    return get_reg_value(LANGUAGE_VALUE, "RU", winreg.REG_SZ)


def set_language(value):
    return set_reg_value(LANGUAGE_VALUE, value, winreg.REG_SZ)


def format_size(size_bytes):
    """Форматирует размер в байтах в читаемый вид"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class TrayIcon:
    def __init__(self):
        # Устанавливаем язык из реестра
        self.current_language = get_language()
        locale.set_language(self.current_language)

        self.levels = ["bin_0", "bin_25", "bin_50", "bin_75", "bin_full"]
        self.current_icon = None
        self.update_icon()
        self.last_click_time = 0
        self.double_click_time = 0.35  # 350 ms
        self.stop_event = Event()  # Для остановки фоновых потоков

        # Для управления окнами
        self.about_window = None
        self.confirm_window = None
        self.window_lock = Lock()
        self.widget_keys = {}  # Для связи виджетов с ключами переводов
        self.confirm_widgets = {}  # Для виджетов окна подтверждения

        # Создаем иконку в трее
        self.icon = pystray.Icon(locale.tr("app_name"))
        self.icon.icon = self.current_icon
        self.update_tooltip()

        # Создаем меню
        self.create_menu()

        # Назначаем обработчик клика
        self.icon.on_click = self.on_tray_click

        # Запускаем фоновое обновление
        self.update_thread = Thread(target=self.auto_update, daemon=True)
        self.update_thread.start()

        logger.info("Инициализация TrayIcon завершена")

    def create_menu(self):
        """Создает меню с учетом текущего языка"""
        self.icon.menu = pystray.Menu(
            pystray.MenuItem(locale.tr("open_bin"), self.open_bin),
            pystray.MenuItem(locale.tr("clear_bin"), self.clear_bin),
            pystray.MenuItem(locale.tr("settings"),
                             pystray.Menu(
                                 pystray.MenuItem(
                                     locale.tr("confirm_clear"),
                                     self.toggle_confirm,
                                     checked=lambda item: get_confirm_setting() == 1
                                 ),
                                 pystray.MenuItem(
                                     locale.tr("double_click_action"),
                                     pystray.Menu(
                                         pystray.MenuItem(
                                             locale.tr("open_bin_action"),
                                             lambda: self.set_double_click_action(OPEN_BIN_ACTION),
                                             checked=lambda item: get_double_click_action() == OPEN_BIN_ACTION,
                                             radio=True
                                         ),
                                         pystray.MenuItem(
                                             locale.tr("clear_bin_action"),
                                             lambda: self.set_double_click_action(CLEAR_BIN_ACTION),
                                             checked=lambda item: get_double_click_action() == CLEAR_BIN_ACTION,
                                             radio=True
                                         )
                                     )
                                 ),
                                 pystray.MenuItem(
                                     locale.tr("language"),
                                     pystray.Menu(
                                         pystray.MenuItem(
                                             locale.tr("language_ru"),
                                             lambda: self.set_language("RU"),
                                             checked=lambda item: get_language() == "RU",
                                             radio=True
                                         ),
                                         pystray.MenuItem(
                                             locale.tr("language_en"),
                                             lambda: self.set_language("EN"),
                                             checked=lambda item: get_language() == "EN",
                                             radio=True
                                         )
                                     )
                                 )
                             )
                             ),
            pystray.MenuItem(locale.tr("about"), self.show_about),
            pystray.MenuItem(locale.tr("exit"), self.quit_app)
        )

    def update_tooltip(self):
        """Обновляет текст подсказки с текущим размером корзины"""
        try:
            size_bytes = get_bin_size()
            formatted_size = format_size(size_bytes)
            self.icon.title = f"{locale.tr('recycle_bin')}: {formatted_size}"
        except Exception as e:
            logger.error(f"Ошибка обновления тултипа: {e}")

    def on_tray_click(self, icon, event):
        """Обработчик кликов по иконке в трее"""
        if event.button != pystray.MouseButton.LEFT:
            return

        current_time = time.time()
        if current_time - self.last_click_time < self.double_click_time:
            self.execute_double_click_action()
        self.last_click_time = current_time

    def execute_double_click_action(self):
        """Выполняет действие для двойного клика"""
        action = get_double_click_action()
        if action == OPEN_BIN_ACTION:
            logger.info("Двойной клик: открытие корзины")
            self.open_bin()
        elif action == CLEAR_BIN_ACTION:
            logger.info("Двойной клик: очистка корзины")
            self.clear_bin(show_confirmation=get_confirm_setting())

    def set_double_click_action(self, action):
        set_double_click_action(action)
        logger.info(f"Установлено действие при двойном клике: {action}")

    def set_language(self, lang):
        """Устанавливает язык и мгновенно применяет изменения"""
        set_language(lang)
        locale.set_language(lang)
        self.icon.title = locale.tr("app_name")
        self.update_tooltip()
        self.create_menu()
        self.icon.update_menu()

        # Мгновенное обновление открытых окон
        self.update_about_window_language()
        self.update_confirm_window_language()

        logger.info(f"Язык изменен на {lang}")

    def run(self):
        """Запускает иконку в трее"""
        self.icon.run()

    def quit_app(self):
        """Завершает работу приложения"""
        self.stop_event.set()

        # Закрываем все окна перед выходом
        self.close_all_windows()

        # Даем время на закрытие окон
        time.sleep(0.2)

        self.icon.stop()
        logger.info("Приложение завершено")

    def close_all_windows(self):
        """Закрывает все открытые окна"""
        with self.window_lock:
            if self.about_window:
                try:
                    self.about_window.destroy()
                except:
                    pass
                self.about_window = None

            if self.confirm_window:
                try:
                    self.confirm_window.destroy()
                except:
                    pass
                self.confirm_window = None

    def open_bin(self):
        """Открывает корзину"""
        logger.info("Открытие корзины")
        open_recycle_bin()

    def clear_bin(self, show_confirmation=None):
        """Очистка корзины с возможностью отключения подтверждения"""
        if show_confirmation is None:
            show_confirmation = get_confirm_setting()

        if show_confirmation:
            threading.Thread(target=self.show_modern_dialog, daemon=True).start()
        else:
            self.perform_empty_bin()

    def show_modern_dialog(self):
        """Современный диалог подтверждения очистки корзины"""
        try:
            with self.window_lock:
                if self.confirm_window:
                    try:
                        # Активируем окно
                        self.confirm_window.lift()
                        self.confirm_window.focus_force()
                        return
                    except Exception as e:
                        logger.error(f"Ошибка активации окна: {e}")
                        self.confirm_window = None

            # Создаем новое окно в отдельном потоке
            root = tk.Tk()
            with self.window_lock:
                self.confirm_window = root
                self.confirm_widgets = {}  # Сбрасываем предыдущие виджеты

            root.withdraw()  # Скрываем временно
            root.title(locale.tr("confirm_dialog_title"))

            # Устанавливаем иконку приложения
            icon_path = resource_path("icons/bin_full.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)

            # Настройка DPI
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                dpi = user32.GetDpiForWindow(hwnd)
                scaling_factor = dpi / 96.0
                root.tk.call('tk', 'scaling', scaling_factor * 1.5)
            except:
                root.tk.call('tk', 'scaling', 2.0)

            # Создаем главный фрейм
            main_frame = ttk.Frame(root, padding=(30, 25))  # Уменьшили отступы
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Заголовок
            header_label = ttk.Label(
                main_frame,
                text=locale.tr("confirm_dialog_title"),
                font=("Segoe UI", 12, "bold"),
                foreground="#000000"
            )
            header_label.pack(fill=tk.X, pady=(0, 15))
            self.confirm_widgets["header"] = header_label

            # Основной текст (уменьшили wraplength для лучшего отображения)
            content_label = ttk.Label(
                main_frame,
                text=locale.tr("confirm_dialog_message"),
                font=("Segoe UI", 10),
                wraplength=600,  # Уменьшили для лучшего отображения
                foreground="#000000",
                justify=tk.LEFT
            )
            content_label.pack(fill=tk.X, pady=(0, 30))
            self.confirm_widgets["content"] = content_label

            # Кнопки
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            style = ttk.Style()
            style.configure("Accent.TButton",
                            font=("Segoe UI", 10, "bold"),
                            foreground="black",
                            background="#f0f0f0",
                            borderwidth=1,
                            padding=6)
            style.map("Accent.TButton",
                      background=[('active', '#e0e0e0'), ('pressed', '#d0d0d0')])

            # Кнопка "Очистить"
            def on_yes():
                logger.info("Пользователь подтвердил очистку корзины")
                with self.window_lock:
                    self.confirm_window = None
                root.destroy()
                self.perform_empty_bin()

            yes_btn = ttk.Button(
                button_frame,
                text=locale.tr("clear_btn"),
                command=on_yes,
                style="Accent.TButton",
                width=20,
                padding=8
            )
            yes_btn.pack(side=tk.RIGHT)
            self.confirm_widgets["yes_btn"] = yes_btn

            # Кнопка "Отмена"
            def on_no():
                logger.info("Пользователь отменил очистку корзины")
                with self.window_lock:
                    self.confirm_window = None
                root.destroy()

            no_btn = ttk.Button(
                button_frame,
                text=locale.tr("cancel_btn"),
                command=on_no,
                width=15,
                padding=6
            )
            no_btn.pack(side=tk.RIGHT, padx=(15, 0))
            self.confirm_widgets["no_btn"] = no_btn

            # Устанавливаем фокус
            root.after(100, lambda: yes_btn.focus_set())
            root.bind("<Return>", lambda event: on_yes())
            root.bind("<Escape>", lambda event: on_no())

            # Центрирование окна
            root.update_idletasks()
            width = root.winfo_reqwidth()
            height = root.winfo_reqheight()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            root.geometry(f"700x265+{x}+{y}")  # Хорошее соотношение сторон

            # Показываем окно
            root.deiconify()
            root.resizable(False, False)

            # Обработка закрытия окна
            def on_close():
                try:
                    root.destroy()
                except:
                    pass
                with self.window_lock:
                    self.confirm_window = None

            root.protocol("WM_DELETE_WINDOW", on_close)

            # Добавляем метод для обновления языка
            def update_language():
                try:
                    if not root.winfo_exists():
                        return
                    root.title(locale.tr("confirm_dialog_title"))
                    header_label.config(text=locale.tr("confirm_dialog_title"))
                    content_label.config(text=locale.tr("confirm_dialog_message"))
                    yes_btn.config(text=locale.tr("clear_btn"))
                    no_btn.config(text=locale.tr("cancel_btn"))
                except Exception as e:
                    logger.error(f"Ошибка обновления языка диалога: {e}")

            root.update_language = update_language

            # Запускаем главный цикл
            root.mainloop()
        except Exception as e:
            logger.error(f"Ошибка при создании диалогового окна: {e}")
            with self.window_lock:
                self.confirm_window = None

    def show_about(self):
        """Показывает окно 'О программе'"""
        with self.window_lock:
            if self.about_window:
                try:
                    # Активируем окно
                    self.about_window.lift()
                    self.about_window.focus_force()
                    return
                except Exception as e:
                    logger.error(f"Ошибка активации окна: {e}")
                    self.about_window = None

        threading.Thread(target=self._show_about_dialog, daemon=True).start()

    def _show_about_dialog(self):
        """Внутренняя функция для создания окна 'О программе'"""
        try:
            # Создаем новое окно в отдельном потоке
            root = tk.Tk()
            with self.window_lock:
                self.about_window = root
                self.widget_keys = {}  # Очищаем предыдущие привязки

            root.withdraw()  # Скрываем временно

            # Устанавливаем короткое название без приложения
            root.title(locale.tr("about"))

            # Устанавливаем иконку приложения
            icon_path = resource_path("icons/bin_full.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)

            # Устанавливаем размеры окна
            root.geometry("400x450")
            root.resizable(False, False)

            # Основной фрейм
            main_frame = ttk.Frame(root, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Логотип
            try:
                logo_path = resource_path("icons/bin_full.ico")
                logo_img = Image.open(logo_path)
                logo_img = logo_img.resize((80, 80), Image.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)

                # Сохраняем ссылку на изображение в глобальной переменной
                root.logo_image = logo_photo

                logo_label = ttk.Label(main_frame, image=logo_photo)
                logo_label.pack(pady=(10, 20))
            except Exception as e:
                logger.error(f"Ошибка загрузки логотипа: {e}")
                # Заглушка на случай ошибки
                app_label = ttk.Label(main_frame, text=locale.tr("app_name"), font=("Arial", 16, "bold"))
                app_label.pack(pady=10)
                self.widget_keys[app_label] = "app_name"

            # Информация
            app_name_label = ttk.Label(
                main_frame,
                text=locale.tr("app_name"),
                font=("Arial", 20, "bold")
            )
            app_name_label.pack(pady=5)
            self.widget_keys[app_name_label] = "app_name"

            version_label = ttk.Label(
                main_frame,
                text=locale.tr("version"),
                font=("Arial", 18)
            )
            version_label.pack(pady=5)
            self.widget_keys[version_label] = "version"

            author_label = ttk.Label(
                main_frame,
                text=locale.tr("author"),
                font=("Arial", 16)
            )
            author_label.pack(pady=5)
            self.widget_keys[author_label] = "author"

            # Ссылка на сайт
            website_frame = ttk.Frame(main_frame)
            website_frame.pack(pady=14)

            website_label = ttk.Label(
                website_frame,
                text=locale.tr("website"),
                font=("Arial", 14),
                foreground="blue",
                cursor="hand2"
            )
            website_label.pack()
            website_label.bind("<Button-1>", lambda e: webbrowser.open("https://youtu.be/Ok0JhzYFrjA"))
            self.widget_keys[website_label] = "website"

            # Кнопка закрытия
            def on_close():
                try:
                    root.destroy()
                except:
                    pass
                with self.window_lock:
                    self.about_window = None

            close_btn = ttk.Button(
                main_frame,
                text=locale.tr("close"),
                command=on_close,
                width=15
            )
            close_btn.pack(pady=15)
            self.widget_keys[close_btn] = "close"

            # Центрирование окна
            root.update_idletasks()
            width = root.winfo_reqwidth()
            height = root.winfo_reqheight()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            root.geometry(f"+{x}+{y}")

            # Показываем окно
            root.deiconify()

            # Обработка закрытия окна
            root.protocol("WM_DELETE_WINDOW", on_close)
            root.bind("<Escape>", lambda e: on_close())
            root.bind("<Return>", lambda e: on_close())

            # Устанавливаем фокус на кнопке закрытия
            close_btn.focus_set()

            # Добавляем метод для обновления языка
            def update_language():
                try:
                    if not root.winfo_exists():
                        return
                    root.title(locale.tr("about"))
                    for widget, key in self.widget_keys.items():
                        if isinstance(widget, (ttk.Label, ttk.Button)):
                            widget.config(text=locale.tr(key))
                except Exception as e:
                    logger.error(f"Ошибка обновления языка окна: {e}")

            root.update_language = update_language

            # Запускаем главный цикл
            root.mainloop()
        except Exception as e:
            logger.error(f"Ошибка при создании окна 'О программе': {e}")
            with self.window_lock:
                self.about_window = None

    def update_about_window_language(self):
        """Обновляет язык в открытом окне 'О программе'"""
        with self.window_lock:
            if self.about_window:
                try:
                    # Безопасное обновление через основной цикл окна
                    self.about_window.after(0, self.about_window.update_language)
                except Exception as e:
                    logger.error(f"Ошибка обновления окна 'О программе': {e}")

    def update_confirm_window_language(self):
        """Обновляет язык в открытом окне подтверждения"""
        with self.window_lock:
            if self.confirm_window:
                try:
                    # Безопасное обновление через основной цикл окна
                    self.confirm_window.after(0, self.confirm_window.update_language)
                except Exception as e:
                    logger.error(f"Ошибка обновления диалога: {e}")

    def perform_empty_bin(self):
        """Выполняет очистку корзины и обновляет иконку"""
        if empty_bin():
            self.update_icon()

    def toggle_confirm(self, item):
        """Переключает настройку подтверждения очистки"""
        current = get_confirm_setting()
        new_value = 0 if current == 1 else 1
        set_confirm_setting(new_value)
        action = "отключено" if new_value == 0 else "включено"
        logger.info(f"Подтверждение очистки {action}")

    def update_icon(self):
        """Обновляет иконку в зависимости от заполненности корзины"""
        try:
            level = get_bin_level()
            icon_name = self.levels[level] + ".ico"
            icon_path = resource_path(f"icons/{icon_name}")
            self.current_icon = Image.open(icon_path)

            if hasattr(self, 'icon'):
                self.icon.icon = self.current_icon
                self.update_tooltip()
        except Exception as e:
            logger.error(f"Ошибка обновления иконки: {e}")

    def auto_update(self):
        """Автоматическое обновление иконки и тултипа"""
        while not self.stop_event.is_set():
            try:
                self.update_icon()
                # Используем wait с таймаутом вместо sleep для возможности прерывания
                self.stop_event.wait(10)
            except Exception as e:
                logger.error(f"Ошибка в фоновом обновлении: {e}")