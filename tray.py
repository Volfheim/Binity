import os
import time
import threading
import logging
import ctypes
import tkinter as tk
from tkinter import ttk
import winreg
import webbrowser

import pystray
from PIL import Image, ImageTk

from bin_control import get_bin_level, get_bin_size, empty_bin, open_recycle_bin
from utils import resource_path, format_size
from locales import locale

logger = logging.getLogger(__name__)

# Константы реестра
CONFIRM_KEY = r"Software\Binity"
CONFIRM_VALUE = "ConfirmClear"
DOUBLE_CLICK_VALUE = "DoubleClickAction"
LANGUAGE_VALUE = "Language"

# Возможные действия двойного клика
OPEN_BIN_ACTION = 0
CLEAR_BIN_ACTION = 1

# Настройка DPI для Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per Monitor DPI aware
except Exception as dpi_error:
    logger.debug(f"DPI awareness setting error: {dpi_error}")


class TrayIcon:
    def __init__(self):
        # --- Локализация ---
        self.current_language = self._reg_read(LANGUAGE_VALUE, "RU", winreg.REG_SZ)
        locale.set_language(self.current_language)

        # --- Двойной клик ---
        self.last_click = 0.0
        self.double_interval = 0.35  # секунды

        # --- Потоки и окна ---
        self.stop_event = threading.Event()
        self.window_lock = threading.Lock()
        self.root = None
        self.about_window = None
        self.confirm_window = None
        self.widget_keys = {}
        self.confirm_widgets = {}

        # Создаем корневое окно в отдельном потоке
        self.gui_thread = threading.Thread(target=self._create_root_window, daemon=True)
        self.gui_thread.start()
        # Ожидаем инициализации GUI
        time.sleep(0.5)

        # --- Иконки уровней ---
        self.levels = ["bin_0", "bin_25", "bin_50", "bin_75", "bin_full"]

        # --- Текущая иконка и тултип ---
        self.current_icon = None
        self._update_icon_image()
        self.icon = pystray.Icon(
            locale.tr("app_name"),
            self.current_icon,
            menu=None  # Меню будет установлено ниже
        )
        self._update_tooltip()

        # --- Меню (со скрытым пунктом для двойного клика) ---
        self._update_menu()

        # --- Фоновое обновление ---
        threading.Thread(target=self._auto_update, daemon=True).start()
        logger.info("TrayIcon инициализирован")

    def _create_root_window(self):
        """Создает скрытое корневое окно для управления дочерними окнами"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Настройка DPI
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            dpi = user32.GetDpiForWindow(hwnd)
            scaling_factor = dpi / 96.0
            self.root.tk.call('tk', 'scaling', scaling_factor * 1.5)
        except Exception as dpi_error:
            logger.debug(f"DPI scaling error: {dpi_error}")
            try:
                self.root.tk.call('tk', 'scaling', 2.0)
            except:
                pass

        # Устанавливаем иконку
        ico = resource_path("icons/bin_full.ico")
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception as icon_error:
                logger.error(f"Ошибка установки иконки: {icon_error}")

        # Запускаем цикл обработки событий
        self.root.mainloop()

    def _update_menu(self):
        """Обновляет меню иконки с текущими настройками"""
        self.icon.menu = pystray.Menu(
            pystray.MenuItem("", self._on_default, default=True),
            pystray.MenuItem(locale.tr("open_bin"), self.open_bin),
            pystray.MenuItem(locale.tr("clear_bin"), self.clear_bin),
            pystray.MenuItem(locale.tr("settings"), pystray.Menu(
                pystray.MenuItem(
                    locale.tr("confirm_clear"),
                    self._toggle_confirm,
                    checked=lambda _: self._reg_read(CONFIRM_VALUE, 1) == 1
                ),
                pystray.MenuItem(
                    locale.tr("double_click_action"), pystray.Menu(
                        pystray.MenuItem(
                            locale.tr("open_bin_action"),
                            lambda _: self._set_double_click_action(OPEN_BIN_ACTION),
                            checked=lambda _: self._reg_read(DOUBLE_CLICK_VALUE, OPEN_BIN_ACTION) == OPEN_BIN_ACTION,
                            radio=True
                        ),
                        pystray.MenuItem(
                            locale.tr("clear_bin_action"),
                            lambda _: self._set_double_click_action(CLEAR_BIN_ACTION),
                            checked=lambda _: self._reg_read(DOUBLE_CLICK_VALUE, CLEAR_BIN_ACTION) == CLEAR_BIN_ACTION,
                            radio=True
                        )
                    )
                ),
                pystray.MenuItem(
                    locale.tr("language"), pystray.Menu(
                        pystray.MenuItem(
                            locale.tr("language_ru"),
                            lambda _: self._set_language("RU"),
                            checked=lambda _: self._reg_read(LANGUAGE_VALUE, "RU", winreg.REG_SZ) == "RU",
                            radio=True
                        ),
                        pystray.MenuItem(
                            locale.tr("language_en"),
                            lambda _: self._set_language("EN"),
                            checked=lambda _: self._reg_read(LANGUAGE_VALUE, "EN", winreg.REG_SZ) == "EN",
                            radio=True
                        )
                    )
                )
            )),
            pystray.MenuItem(locale.tr("about"), self.show_about),
            pystray.MenuItem(locale.tr("exit"), self.quit_app)
        )

    # ---------------- Double-click handler ----------------
    def _on_default(self, icon, item):
        """Обработчик двойного клика через скрытый пункт меню"""
        now = time.time()
        if now - self.last_click < self.double_interval:
            action = self._reg_read(DOUBLE_CLICK_VALUE, OPEN_BIN_ACTION)
            if action == OPEN_BIN_ACTION:
                logger.info("Double-click: Open Recycle Bin")
                self.open_bin()
            else:
                logger.info("Double-click: Empty Recycle Bin")
                self.clear_bin()
        self.last_click = now

    # --------------- Core actions ---------------
    def open_bin(self, icon=None, item=None):
        open_recycle_bin()

    def clear_bin(self, icon=None, item=None):
        if self._reg_read(CONFIRM_VALUE, 1) == 1:
            self.show_modern_dialog()
        else:
            if empty_bin():
                self._update_icon_image()

    def quit_app(self, icon=None, item=None):
        self.stop_event.set()
        self._close_windows()
        time.sleep(0.2)
        self.icon.stop()
        if self.root:
            try:
                self.root.quit()
            except:
                pass
        logger.info("Приложение завершено")

    # --------------- Windows management ---------------
    def _close_about_window(self):
        """Закрывает окно 'О программе'"""
        with self.window_lock:
            if self.about_window:
                try:
                    # Освобождаем ресурсы изображений
                    if hasattr(self.about_window, 'logo_img'):
                        del self.about_window.logo_img
                    self.about_window.destroy()
                except Exception as e:
                    logger.error(f"Ошибка при закрытии окна 'О программе': {e}")
                finally:
                    self.about_window = None
                    self.widget_keys = {}

    def _close_confirm_window(self):
        """Закрывает окно подтверждения очистки"""
        with self.window_lock:
            if self.confirm_window:
                try:
                    self.confirm_window.destroy()
                except Exception as e:
                    logger.error(f"Ошибка при закрытии окна подтверждения: {e}")
                finally:
                    self.confirm_window = None
                    self.confirm_widgets = {}

    def _close_windows(self):
        """Закрывает все открытые окна"""
        self._close_about_window()
        self._close_confirm_window()

    # --------------- Windows and dialogs ---------------
    def show_modern_dialog(self):
        """Современный диалог подтверждения очистки корзины"""
        # Сначала закрываем окно "О программе"
        self._close_about_window()
        # Затем показываем диалог подтверждения
        self._show_modern_dialog_gui()

    def _show_modern_dialog_gui(self):
        try:
            with self.window_lock:
                if self.confirm_window:
                    try:
                        self.confirm_window.lift()
                        self.confirm_window.focus_force()
                        return
                    except Exception as e:
                        logger.error(f"Ошибка активации окна: {e}")
                        self.confirm_window = None

            # Создаем окно как Toplevel от корневого окна
            dlg = tk.Toplevel(self.root)
            dlg.title(locale.tr("confirm_dialog_title"))
            dlg.resizable(False, False)
            dlg.transient(self.root)  # Устанавливаем отношение родитель-потомок
            dlg.grab_set()  # Захватываем фокус

            # Устанавливаем иконку
            try:
                ico = resource_path("icons/bin_full.ico")
                if os.path.exists(ico):
                    dlg.iconbitmap(ico)
            except Exception as icon_error:
                logger.error(f"Ошибка установки иконки: {icon_error}")

            # Главный фрейм
            main_frame = ttk.Frame(dlg, padding=(30, 25))
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Заголовок
            header_label = ttk.Label(
                main_frame,
                text=locale.tr("confirm_dialog_title"),
                font=("Segoe UI", 12, "bold"),
                foreground="#000000"
            )
            header_label.pack(fill=tk.X, pady=(0, 15))

            # Основной текст
            content_label = ttk.Label(
                main_frame,
                text=locale.tr("confirm_dialog_message"),
                font=("Segoe UI", 10),
                wraplength=600,
                foreground="#000000",
                justify=tk.LEFT
            )
            content_label.pack(fill=tk.X, pady=(0, 30))

            # Фрейм для кнопок
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            # Стиль для кнопки подтверждения
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
                dlg.destroy()
                with self.window_lock:
                    self.confirm_window = None
                if empty_bin():
                    self._update_icon_image()

            yes_btn = ttk.Button(
                button_frame,
                text=locale.tr("clear_btn"),
                command=on_yes,
                style="Accent.TButton",
                width=20,
                padding=8
            )
            yes_btn.pack(side=tk.RIGHT)

            # Кнопка "Отмена"
            def on_no():
                logger.info("Пользователь отменил очистку корзины")
                dlg.destroy()
                with self.window_lock:
                    self.confirm_window = None

            no_btn = ttk.Button(
                button_frame,
                text=locale.tr("cancel_btn"),
                command=on_no,
                width=15,
                padding=6
            )
            no_btn.pack(side=tk.RIGHT, padx=(15, 0))

            # Центрирование окна
            dlg.update_idletasks()
            width = 700
            height = 265
            screen_width = dlg.winfo_screenwidth()
            screen_height = dlg.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            dlg.geometry(f"{width}x{height}+{x}+{y}")

            # Принудительно делаем окно активным и получаем фокус
            dlg.deiconify()
            dlg.lift()
            dlg.focus_force()

            # Устанавливаем фокус на кнопку "Очистить"
            yes_btn.focus_set()

            # Настраиваем обработчики клавиш
            dlg.bind("<Return>", lambda e: on_yes())
            dlg.bind("<Escape>", lambda e: on_no())

            # Обработка закрытия окна
            dlg.protocol("WM_DELETE_WINDOW", on_no)

            with self.window_lock:
                self.confirm_window = dlg
                # Сохраняем виджеты для обновления языка
                self.confirm_widgets = {
                    "header": header_label,
                    "content": content_label,
                    "yes_btn": yes_btn,
                    "no_btn": no_btn
                }

        except Exception as e:
            logger.error(f"Ошибка диалога подтверждения: {e}")
            with self.window_lock:
                self.confirm_window = None

    def show_about(self, icon=None, item=None):
        """Показать окно 'О программе'"""
        # Сначала закрываем окно подтверждения
        self._close_confirm_window()
        # Затем показываем окно "О программе"
        self._show_about_gui()

    def _show_about_gui(self):
        try:
            with self.window_lock:
                if self.about_window:
                    try:
                        self.about_window.lift()
                        self.about_window.focus_force()
                        return
                    except Exception as e:
                        logger.error(f"Ошибка активации окна: {e}")
                        self.about_window = None

            # Создаем окно как Toplevel от корневого окна
            about = tk.Toplevel(self.root)
            about.title(locale.tr("about"))
            about.resizable(False, False)
            about.transient(self.root)  # Устанавливаем отношение родитель-потомок
            about.grab_set()  # Захватываем фокус

            # Устанавливаем иконку
            try:
                ico = resource_path("icons/bin_full.ico")
                if os.path.exists(ico):
                    about.iconbitmap(ico)
            except Exception as icon_error:
                logger.error(f"Ошибка установки иконки: {icon_error}")

            # Главный фрейм
            main_frame = ttk.Frame(about, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Устанавливаем размеры окна
            about.geometry("400x450")

            # Логотип
            logo_label = None
            try:
                img_path = resource_path("icons/bin_full.ico")
                img = Image.open(img_path)
                img = img.resize((80, 80), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                about.logo_img = photo  # Сохраняем ссылку

                logo_label = ttk.Label(main_frame, image=photo)
                logo_label.pack(pady=(10, 15))
            except Exception as e:
                logger.error(f"Ошибка логотипа: {e}")
                logo_label = ttk.Label(
                    main_frame,
                    text=locale.tr("app_name"),
                    font=("Arial", 14, "bold")
                )
                logo_label.pack(pady=10)

            # Название приложения
            app_name_label = ttk.Label(
                main_frame,
                text=locale.tr("app_name"),
                font=("Arial", 16, "bold")
            )
            app_name_label.pack(pady=5)

            # Версия
            version_label = ttk.Label(
                main_frame,
                text=locale.tr("version"),
                font=("Arial", 14)
            )
            version_label.pack(pady=5)

            # Автор
            author_label = ttk.Label(
                main_frame,
                text=locale.tr("author"),
                font=("Arial", 12)
            )
            author_label.pack(pady=5)

            # Ссылка на сайт
            web_frame = ttk.Frame(main_frame)
            web_frame.pack(pady=10)

            website_label = ttk.Label(
                web_frame,
                text=locale.tr("website"),
                font=("Arial", 10),
                foreground="blue",
                cursor="hand2"
            )
            website_label.pack()
            website_label.bind("<Button-1>",
                               lambda e: webbrowser.open("https://youtu.be/Ok0JhzYFrjA"))

            # Кнопка закрытия
            def on_close():
                about.destroy()
                with self.window_lock:
                    self.about_window = None

            close_btn = ttk.Button(
                main_frame,
                text=locale.tr("close"),
                command=on_close,
                width=15
            )
            close_btn.pack(pady=15)

            # Центрирование окна
            about.update_idletasks()
            width = about.winfo_reqwidth()
            height = about.winfo_reqheight()
            screen_width = about.winfo_screenwidth()
            screen_height = about.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            about.geometry(f"+{x}+{y}")

            # Принудительно делаем окно активным и получаем фокус
            about.deiconify()
            about.lift()
            about.focus_force()

            # Устанавливаем фокус на кнопку "Закрыть"
            close_btn.focus_set()

            # Настраиваем обработчики клавиш
            about.bind("<Return>", lambda e: on_close())
            about.bind("<Escape>", lambda e: on_close())

            # Обработка закрытия окна
            about.protocol("WM_DELETE_WINDOW", on_close)

            with self.window_lock:
                self.about_window = about
                # Сохраняем виджеты для обновления языка
                self.widget_keys = {
                    logo_label: "app_name",
                    app_name_label: "app_name",
                    version_label: "version",
                    author_label: "author",
                    website_label: "website",
                    close_btn: "close"
                }

        except Exception as e:
            logger.error(f"Ошибка About: {e}")
            with self.window_lock:
                self.about_window = None

    # ---------------- Helper Methods ----------------
    def _update_icon_image(self):
        try:
            lvl = get_bin_level()
            name = f"{self.levels[lvl]}.ico"
            path = resource_path(f"icons/{name}")
            img = Image.open(path)
            self.current_icon = img
            if hasattr(self, 'icon'):
                self.icon.icon = img
        except Exception as e:
            logger.error(f"Ошибка обновления иконки: {e}")

    def _update_tooltip(self):
        try:
            size = get_bin_size()
            self.icon.title = f"{locale.tr('recycle_bin')}: {format_size(size)}"
        except Exception as e:
            logger.error(f"Ошибка тултипа: {e}")

    def _auto_update(self):
        """Автоматическое обновление иконки и тултипа"""
        while not self.stop_event.is_set():
            try:
                self._update_icon_image()
                self._update_tooltip()
                time.sleep(10)
            except Exception as e:
                logger.error(f"Auto-update error: {e}")
                time.sleep(30)  # Увеличиваем задержку при ошибках

    def run(self):
        self.icon.run()

    # ---------------- Registry Helpers ----------------
    def _reg_read(self, name, default, reg_type=winreg.REG_DWORD):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
            val, _ = winreg.QueryValueEx(key, name)
            winreg.CloseKey(key)
            return val
        except Exception as e:
            logger.debug(f"Ошибка чтения из реестра: {e}")
            return default

    def _reg_write(self, name, value, reg_type=winreg.REG_DWORD):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
            winreg.SetValueEx(key, name, 0, reg_type, value)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            logger.error(f"Ошибка записи в реестр: {e}")
            return False

    def _toggle_confirm(self, icon=None, item=None):
        cur = self._reg_read(CONFIRM_VALUE, 1)
        self._reg_write(CONFIRM_VALUE, 0 if cur == 1 else 1)

    def _set_double_click_action(self, action):
        self._reg_write(DOUBLE_CLICK_VALUE, action)
        logger.info(f"Действие двойного клика установлено: {action}")

    def _set_language(self, lang):
        """Устанавливает язык и обновляет интерфейс"""
        self._reg_write(LANGUAGE_VALUE, lang, winreg.REG_SZ)
        locale.set_language(lang)
        self.icon.title = locale.tr("app_name")
        self._update_tooltip()
        self._update_menu()  # Обновляем меню с новым языком
        self._update_open_windows()  # Обновляем открытые окна
        logger.info(f"Язык изменен на {lang}")

    def _update_open_windows(self):
        """Обновляет язык во всех открытых окнах"""
        self._update_about_window_language()
        self._update_confirm_window_language()

    def _update_about_window_language(self):
        """Обновляет язык в открытом окне 'О программе'"""
        with self.window_lock:
            if self.about_window:
                try:
                    self.about_window.title(locale.tr("about"))
                    for widget, key in self.widget_keys.items():
                        if widget and key:
                            if isinstance(widget, (ttk.Label, ttk.Button)):
                                widget.config(text=locale.tr(key))
                except Exception as e:
                    logger.error(f"Ошибка обновления окна 'О программе': {e}")

    def _update_confirm_window_language(self):
        """Обновляет язык в открытом окне подтверждения"""
        with self.window_lock:
            if self.confirm_window:
                try:
                    self.confirm_window.title(locale.tr("confirm_dialog_title"))
                    if "header" in self.confirm_widgets and self.confirm_widgets["header"]:
                        self.confirm_widgets["header"].config(
                            text=locale.tr("confirm_dialog_title")
                        )
                    if "content" in self.confirm_widgets and self.confirm_widgets["content"]:
                        self.confirm_widgets["content"].config(
                            text=locale.tr("confirm_dialog_message")
                        )
                    if "yes_btn" in self.confirm_widgets and self.confirm_widgets["yes_btn"]:
                        self.confirm_widgets["yes_btn"].config(
                            text=locale.tr("clear_btn")
                        )
                    if "no_btn" in self.confirm_widgets and self.confirm_widgets["no_btn"]:
                        self.confirm_widgets["no_btn"].config(
                            text=locale.tr("cancel_btn")
                        )
                except Exception as e:
                    logger.error(f"Ошибка обновления диалога подтверждения: {e}")