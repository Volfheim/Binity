import os
import time
import threading
import logging
import ctypes
import tkinter as tk
from tkinter import ttk
import winreg
import webbrowser
import sys

import pystray
from PIL import Image, ImageTk, ImageDraw, ImageFont

from bin_control import get_bin_level, get_bin_size, empty_bin, open_recycle_bin
from utils import resource_path, format_size
from locales import locale

logger = logging.getLogger(__name__)

# Константы реестра
CONFIRM_KEY = r"Software\Binity"
CONFIRM_VALUE = "ConfirmClear"
DOUBLE_CLICK_VALUE = "DoubleClickAction"
LANGUAGE_VALUE = "Language"
AUTOSTART_VALUE = "Autostart"
AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Возможные действия двойного клика
OPEN_BIN_ACTION = 0
CLEAR_BIN_ACTION = 1

# Размеры иконок
TRAY_ICON_SIZE = 64

class TrayIcon:
    def __init__(self):
        self._init_dpi_awareness()
        self.current_language = self._reg_read(LANGUAGE_VALUE, "RU", winreg.REG_SZ)
        locale.set_language(self.current_language)

        self.last_click = 0.0
        self.double_interval = 0.35

        self.stop_event = threading.Event()
        self.window_lock = threading.Lock()
        self.root = None
        self.about_window = None
        self.confirm_window = None
        self.widget_keys = {}
        self.confirm_widgets = {}

        self.levels = ["bin_0", "bin_25", "bin_50", "bin_75", "bin_full"]
        self.icons = self._load_ico_icons()
        self.current_level = -1

        self.gui_thread = threading.Thread(target=self._create_root_window, daemon=True)
        self.gui_thread.start()
        time.sleep(0.5)

        self.icon = pystray.Icon(
            locale.tr("app_name"),
            self.icons.get(0, self._create_fallback_icon(0))
        )
        self._update_tooltip()
        self._update_menu()

        threading.Thread(target=self._auto_update, daemon=True).start()
        logger.info("TrayIcon инициализирован")

    def _init_dpi_awareness(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            logger.debug("DPI awareness установлен: Per Monitor v2")
        except Exception as dpi_error:
            logger.debug(f"Ошибка настройки DPI: {dpi_error}")
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                logger.debug("DPI awareness установлен: System DPI")
            except:
                logger.debug("Не удалось установить DPI awareness")

    def _get_dpi_scaling(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            dpi = user32.GetDpiForWindow(hwnd)
            return dpi / 96.0
        except:
            return 1.0

    def _get_screen_size(self):
        try:
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            return screen_width, screen_height
        except:
            return 1920, 1080

    def _load_ico_icons(self):
        icons = {}
        for i, name in enumerate(self.levels):
            try:
                path = resource_path(f"icons/{name}.ico")
                if os.path.exists(path):
                    img = Image.open(path)
                    icons[i] = img
                    logger.debug(f"Иконка загружена: {name}.ico")
                else:
                    logger.error(f"Файл иконки не найден: {path}")
                    icons[i] = self._create_fallback_icon(i)
            except Exception as e:
                logger.error(f"Ошибка загрузки иконки: {e}", exc_info=True)
                icons[i] = self._create_fallback_icon(i)
        return icons

    def _create_fallback_icon(self, level):
        try:
            size = TRAY_ICON_SIZE
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            bin_top = size // 6
            bin_bottom = 5 * size // 6
            bin_left = size // 4
            bin_right = 3 * size // 4

            draw.rectangle([bin_left, bin_top, bin_right, bin_bottom],
                           outline='white', fill='#2d2d2d', width=2)
            draw.rectangle([size // 3, size // 12, 2 * size // 3, bin_top],
                           outline='white', fill='#2d2d2d', width=2)

            bin_height = bin_bottom - bin_top
            fill_height = bin_height * level // 4
            fill_top = bin_bottom - fill_height

            if fill_top < bin_bottom:
                draw.rectangle(
                    [bin_left + 2, fill_top, bin_right - 2, bin_bottom - 2],
                    fill='#4a76cf'
                )

            font_size = max(10, size // 6)
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()

            text = f"{level * 25}%"
            text_width = draw.textlength(text, font=font)
            text_height = font_size
            draw.text(
                ((size - text_width) // 2, (size - text_height) // 2),
                text,
                fill='white',
                font=font
            )
            return img
        except Exception as e:
            logger.error(f"Ошибка создания fallback иконки: {e}")
            img = Image.new('RGBA', (TRAY_ICON_SIZE, TRAY_ICON_SIZE), (255, 0, 0, 255))
            return img

    def _create_root_window(self):
        self.root = tk.Tk()
        self.root.withdraw()

        try:
            scaling = self._get_dpi_scaling()
            self.root.tk.call('tk', 'scaling', scaling * 1.5)
            logger.debug(f"Масштабирование DPI установлено: {scaling * 1.5:.1f}")
        except Exception as dpi_error:
            logger.debug(f"Ошибка масштабирования DPI: {dpi_error}")
            try:
                self.root.tk.call('tk', 'scaling', 1.5)
            except:
                pass

        self._set_window_icon(self.root)
        self.root.mainloop()

    def _set_window_icon(self, window):
        try:
            icon_path = resource_path("icons/bin_25.ico")
            if os.path.exists(icon_path):
                window.iconbitmap(icon_path)
                logger.debug("Иконка окна установлена")
        except Exception as e:
            logger.error(f"Ошибка установки иконки окна: {e}")

    def _update_menu(self):
        hidden_item = pystray.MenuItem(
            "",
            self._on_default,
            default=True,
            visible=False
        )

        self.icon.menu = pystray.Menu(
            hidden_item,
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
                ),
                pystray.MenuItem(
                    locale.tr("autostart"),
                    self._toggle_autostart,
                    checked=lambda _: self._is_autostart_enabled()
                )
            )),
            pystray.MenuItem(locale.tr("about"), self.show_about),
            pystray.MenuItem(locale.tr("exit"), self.quit_app)
        )

    def _on_default(self, icon, item):
        now = time.time()
        if now - self.last_click < self.double_interval:
            action = self._reg_read(DOUBLE_CLICK_VALUE, OPEN_BIN_ACTION)
            if action == OPEN_BIN_ACTION:
                logger.info("Двойной клик: Открыть корзину")
                self.open_bin()
            else:
                logger.info("Двойной клик: Очистить корзину")
                self.clear_bin()
        self.last_click = now

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
        if self.root and self.root.winfo_exists():
            try:
                self.root.quit()
            except:
                pass
        logger.info("Приложение завершено")
        sys.exit(0)

    def _close_about_window(self):
        with self.window_lock:
            if self.about_window and self.about_window.winfo_exists():
                try:
                    if hasattr(self.about_window, 'logo_img'):
                        self.about_window.logo_img = None
                    self.about_window.destroy()
                except Exception as e:
                    logger.error(f"Ошибка при закрытии окна 'О программе': {e}")
                finally:
                    self.about_window = None
                    self.widget_keys = {}

    def _close_confirm_window(self):
        with self.window_lock:
            if self.confirm_window and self.confirm_window.winfo_exists():
                try:
                    self.confirm_window.destroy()
                except Exception as e:
                    logger.error(f"Ошибка при закрытии окна подтверждения: {e}")
                finally:
                    self.confirm_window = None
                    self.confirm_widgets = {}

    def _close_windows(self):
        self._close_about_window()
        self._close_confirm_window()

    def show_modern_dialog(self):
        self._close_about_window()
        self._show_modern_dialog_gui()

    def _show_modern_dialog_gui(self):
        try:
            with self.window_lock:
                if self.confirm_window and self.confirm_window.winfo_exists():
                    try:
                        self.confirm_window.lift()
                        self.confirm_window.focus_force()
                        return
                    except Exception as e:
                        logger.error(f"Ошибка активации окна: {e}")
                        self.confirm_window = None

            dlg = tk.Toplevel(self.root)
            dlg.title(locale.tr("confirm_dialog_title"))
            dlg.resizable(False, False)
            dlg.transient(self.root)
            dlg.grab_set()

            self._set_window_icon(dlg)

            padding = int(20 * self._get_dpi_scaling())
            main_frame = ttk.Frame(dlg, padding=(padding, padding))
            main_frame.pack(fill=tk.BOTH, expand=True)

            header_label = ttk.Label(
                main_frame,
                text=locale.tr("confirm_dialog_title"),
                font=("Segoe UI", 12, "bold"),
                foreground="#000000"
            )
            header_label.pack(fill=tk.X, pady=(0, padding // 2))

            content_label = ttk.Label(
                main_frame,
                text=locale.tr("confirm_dialog_message"),
                font=("Segoe UI", 10),
                wraplength=int(400 * self._get_dpi_scaling()),
                foreground="#000000",
                justify=tk.LEFT
            )
            content_label.pack(fill=tk.X, pady=(0, padding))

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
                width=15,
                padding=6
            )
            yes_btn.pack(side=tk.RIGHT)

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
            no_btn.pack(side=tk.RIGHT, padx=(padding // 2, 0))

            scaling = self._get_dpi_scaling()
            base_width = 450
            base_height = 180
            width = int(base_width * scaling)
            height = int(base_height * scaling)

            screen_width, screen_height = self._get_screen_size()
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
            dlg.geometry(f"{width}x{height}+{x}+{y}")

            dlg.deiconify()
            dlg.lift()
            dlg.focus_force()
            yes_btn.focus_set()

            dlg.bind("<Return>", lambda e: on_yes())
            dlg.bind("<Escape>", lambda e: on_no())
            dlg.protocol("WM_DELETE_WINDOW", on_no)

            with self.window_lock:
                self.confirm_window = dlg
                self.confirm_widgets = {
                    "header": header_label,
                    "content": content_label,
                    "yes_btn": yes_btn,
                    "no_btn": no_btn
                }

        except Exception as e:
            logger.error(f"Ошибка диалога подтверждения: {e}", exc_info=True)
            with self.window_lock:
                self.confirm_window = None

    def show_about(self, icon=None, item=None):
        self._close_confirm_window()
        self._show_about_gui()

    def _show_about_gui(self):
        try:
            with self.window_lock:
                if self.about_window and self.about_window.winfo_exists():
                    try:
                        self.about_window.lift()
                        self.about_window.focus_force()
                        return
                    except Exception as e:
                        logger.error(f"Ошибка активации окна: {e}")
                        self.about_window = None

            about = tk.Toplevel(self.root)
            about.title(locale.tr("about"))
            about.resizable(False, False)
            about.transient(self.root)

            self._set_window_icon(about)

            padding = int(20 * self._get_dpi_scaling())
            main_frame = ttk.Frame(about, padding=padding)
            main_frame.pack(fill=tk.BOTH, expand=True)

            scaling = self._get_dpi_scaling()
            base_width = 320
            base_height = 460
            width = int(base_width * scaling)
            height = int(base_height * scaling)
            about.geometry(f"{width}x{height}")

            logo_label = None
            try:
                img_path = resource_path("icons/bin_25.ico")
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    logo_size = int(128 * scaling)
                    img = img.resize((logo_size, logo_size), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    about.logo_img = photo

                    logo_label = ttk.Label(main_frame, image=photo)
                    logo_label.pack(pady=(padding // 2, padding))
                else:
                    raise FileNotFoundError("Файл иконки не найден")
            except Exception as e:
                logger.error(f"Ошибка загрузки логотипа: {e}")
                logo_label = ttk.Label(
                    main_frame,
                    text=locale.tr("app_name"),
                    font=("Arial", 14, "bold")
                )
                logo_label.pack(pady=padding)

            app_name_label = ttk.Label(
                main_frame,
                text=locale.tr("app_name"),
                font=("Arial", 20, "bold")
            )
            app_name_label.pack(pady=padding // 4)

            version_label = ttk.Label(
                main_frame,
                text=locale.tr("version"),
                font=("Arial", 18)
            )
            version_label.pack(pady=padding // 4)

            author_label = ttk.Label(
                main_frame,
                text=locale.tr("author"),
                font=("Arial", 16)
            )
            author_label.pack(pady=padding // 4)

            web_frame = ttk.Frame(main_frame)
            web_frame.pack(pady=padding)

            website_label = ttk.Label(
                web_frame,
                text=locale.tr("website"),
                font=("Arial", 14),
                foreground="blue",
                cursor="hand2"
            )
            website_label.pack()
            website_label.bind(
                "<Button-1>",
                lambda e: webbrowser.open("https://youtu.be/Ok0JhzYFrjA")
            )

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
            close_btn.pack(pady=padding)

            screen_width, screen_height = self._get_screen_size()
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
            about.geometry(f"+{x}+{y}")

            about.deiconify()
            about.lift()
            about.focus_force()
            close_btn.focus_set()

            about.bind("<Return>", lambda e: on_close())
            about.bind("<Escape>", lambda e: on_close())
            about.protocol("WM_DELETE_WINDOW", on_close)

            with self.window_lock:
                self.about_window = about
                self.widget_keys = {
                    "logo": logo_label,
                    "app_name": app_name_label,
                    "version": version_label,
                    "author": author_label,
                    "website": website_label,
                    "close_btn": close_btn
                }

        except Exception as e:
            logger.error(f"Ошибка создания окна 'О программе': {e}", exc_info=True)
            with self.window_lock:
                self.about_window = None

    def _update_icon_image(self):
        try:
            lvl = get_bin_level()
            if lvl == self.current_level:
                return

            icon = self.icons.get(lvl)
            if icon:
                self.current_level = lvl
                self.icon.icon = icon
                logger.debug(f"Иконка обновлена: уровень {lvl}")
        except Exception as e:
            logger.error(f"Ошибка обновления иконки: {e}", exc_info=True)

    def _update_tooltip(self):
        try:
            size = get_bin_size()
            self.icon.title = f"{locale.tr('recycle_bin')}: {format_size(size)}"
        except Exception as e:
            logger.error(f"Ошибка обновления подсказки: {e}", exc_info=True)

    def _auto_update(self):
        update_interval = 10

        while not self.stop_event.is_set():
            try:
                self._update_icon_image()
                self._update_tooltip()

                for _ in range(update_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Ошибка автообновления: {e}", exc_info=True)
                time.sleep(30)

    def run(self):
        self.icon.run()

    def _reg_read(self, name, default, reg_type=winreg.REG_DWORD):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, name)
                return val
        except FileNotFoundError:
            return default
        except Exception as e:
            logger.error(f"Ошибка чтения из реестра: {name} - {e}", exc_info=True)
            return default

    def _reg_write(self, name, value, reg_type=winreg.REG_DWORD):
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY) as key:
                winreg.SetValueEx(key, name, 0, reg_type, value)
            return True
        except Exception as e:
            logger.error(f"Ошибка записи в реестр: {name} - {e}", exc_info=True)
            return False

    def _toggle_confirm(self, icon=None, item=None):
        cur = self._reg_read(CONFIRM_VALUE, 1)
        new_val = 0 if cur == 1 else 1
        self._reg_write(CONFIRM_VALUE, new_val)
        logger.info(f"Подтверждение очистки: {'включено' if new_val == 1 else 'отключено'}")

    def _set_double_click_action(self, action):
        self._reg_write(DOUBLE_CLICK_VALUE, action)
        logger.info(f"Действие двойного клика установлено: {action}")

    def _set_language(self, lang):
        self._reg_write(LANGUAGE_VALUE, lang, winreg.REG_SZ)
        locale.set_language(lang)
        self.icon.title = locale.tr("app_name")
        self._update_tooltip()
        self._update_menu()
        self._update_open_windows()
        logger.info(f"Язык изменен на {lang}")

    def _update_open_windows(self):
        self._update_about_window_language()
        self._update_confirm_window_language()

    def _update_about_window_language(self):
        with self.window_lock:
            if self.about_window and self.about_window.winfo_exists():
                try:
                    self.about_window.title(locale.tr("about"))
                    widgets = self.widget_keys
                    if "app_name" in widgets and widgets["app_name"]:
                        widgets["app_name"].config(text=locale.tr("app_name"))
                    if "version" in widgets and widgets["version"]:
                        widgets["version"].config(text=locale.tr("version"))
                    if "author" in widgets and widgets["author"]:
                        widgets["author"].config(text=locale.tr("author"))
                    if "website" in widgets and widgets["website"]:
                        widgets["website"].config(text=locale.tr("website"))
                    if "close_btn" in widgets and widgets["close_btn"]:
                        widgets["close_btn"].config(text=locale.tr("close"))
                except Exception as e:
                    logger.error(f"Ошибка обновления окна 'О программе': {e}")

    def _update_confirm_window_language(self):
        with self.window_lock:
            if self.confirm_window and self.confirm_window.winfo_exists():
                try:
                    self.confirm_window.title(locale.tr("confirm_dialog_title"))
                    widgets = self.confirm_widgets
                    if "header" in widgets and widgets["header"]:
                        widgets["header"].config(text=locale.tr("confirm_dialog_title"))
                    if "content" in widgets and widgets["content"]:
                        widgets["content"].config(text=locale.tr("confirm_dialog_message"))
                    if "yes_btn" in widgets and widgets["yes_btn"]:
                        widgets["yes_btn"].config(text=locale.tr("clear_btn"))
                    if "no_btn" in widgets and widgets["no_btn"]:
                        widgets["no_btn"].config(text=locale.tr("cancel_btn"))
                except Exception as e:
                    logger.error(f"Ошибка обновления диалога подтверждения: {e}")

    def _is_autostart_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_KEY, 0, winreg.KEY_READ) as key:
                try:
                    winreg.QueryValueEx(key, "Binity")
                    return True
                except FileNotFoundError:
                    return False
        except Exception as e:
            logger.error(f"Ошибка проверки автозапуска: {e}", exc_info=True)
            return False

    def _toggle_autostart(self, icon=None, item=None):
        enabled = self._is_autostart_enabled()

        try:
            if enabled:
                try:
                    with winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            AUTOSTART_REG_KEY,
                            0,
                            winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.DeleteValue(key, "Binity")
                    logger.info("Автозапуск отключен")
                except Exception as e:
                    logger.error(f"Ошибка отключения автозапуска: {e}", exc_info=True)
            else:
                try:
                    if getattr(sys, 'frozen', False):
                        app_path = sys.executable
                    else:
                        app_path = os.path.abspath(sys.argv[0])

                    if ' ' in app_path and not app_path.startswith('"'):
                        app_path = f'"{app_path}"'

                    with winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            AUTOSTART_REG_KEY,
                            0,
                            winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.SetValueEx(
                            key,
                            "Binity",
                            0,
                            winreg.REG_SZ,
                            app_path
                        )
                    logger.info(f"Автозапуск включен: {app_path}")
                except Exception as e:
                    logger.error(f"Ошибка включения автозапуска: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Общая ошибка при работе с автозапуском: {e}", exc_info=True)

        self._update_menu()