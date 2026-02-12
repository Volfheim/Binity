import pystray
from PIL import Image
from threading import Thread
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
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("binity.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Настройки реестра
CONFIRM_KEY = r"Software\Binity"
CONFIRM_VALUE = "ConfirmClear"
DOUBLE_CLICK_ACTION = "DoubleClickAction"

# Возможные действия при двойном клике
OPEN_BIN_ACTION = 0
CLEAR_BIN_ACTION = 1

# Настройка DPI для Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per Monitor DPI aware
except:
    pass


def get_confirm_setting():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
        value, _ = winreg.QueryValueEx(key, CONFIRM_VALUE)
        winreg.CloseKey(key)
        return value
    except:
        return 1  # По умолчанию показывать подтверждение


def set_confirm_setting(value):
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
        winreg.SetValueEx(key, CONFIRM_VALUE, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
    except Exception as e:
        logger.error(f"Ошибка записи в реестр: {e}")


def get_double_click_action():
    """Получаем настройку действия при двойном клике"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
        value, _ = winreg.QueryValueEx(key, DOUBLE_CLICK_ACTION)
        winreg.CloseKey(key)
        return value
    except:
        return OPEN_BIN_ACTION  # По умолчанию открывать корзину


def set_double_click_action(value):
    """Устанавливаем настройку действия при двойном клике"""
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIRM_KEY)
        winreg.SetValueEx(key, DOUBLE_CLICK_ACTION, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
    except Exception as e:
        logger.error(f"Ошибка записи настройки двойного клика: {e}")


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
        self.levels = ["bin_0", "bin_25", "bin_50", "bin_75", "bin_full"]
        self.current_icon = None
        self.update_icon()
        self.last_click_time = 0
        self.double_click_time = 0.35  # 350 ms

        # Создаем иконку в трее
        self.icon = pystray.Icon("Binity")
        self.icon.icon = self.current_icon
        self.update_tooltip()  # Устанавливаем начальный тултип

        # Создаем меню с новыми настройками
        self.icon.menu = pystray.Menu(
            pystray.MenuItem("Открыть корзину", self.open_bin),
            pystray.MenuItem("Очистить корзину", self.clear_bin),
            pystray.MenuItem("Настройки",
                             pystray.Menu(
                                 pystray.MenuItem(
                                     "Запрашивать подтверждение при очистке",
                                     self.toggle_confirm,
                                     checked=lambda item: get_confirm_setting() == 1
                                 ),
                                 pystray.MenuItem(
                                     "Действие при двойном клике",
                                     pystray.Menu(
                                         pystray.MenuItem(
                                             "Открыть корзину",
                                             lambda: self.set_double_click_action(OPEN_BIN_ACTION),
                                             checked=lambda item: get_double_click_action() == OPEN_BIN_ACTION,
                                             radio=True
                                         ),
                                         pystray.MenuItem(
                                             "Очистить корзину",
                                             lambda: self.set_double_click_action(CLEAR_BIN_ACTION),
                                             checked=lambda item: get_double_click_action() == CLEAR_BIN_ACTION,
                                             radio=True
                                         )
                                     )
                                 )
                             )
                             ),
            pystray.MenuItem("Выход", self.quit_app)
        )

        # Назначаем обработчик клика
        self.icon.on_click = self.on_tray_click

        self._running = True
        self.update_thread = Thread(target=self.auto_update, daemon=True)
        self.update_thread.start()

    def update_tooltip(self):
        """Обновляет текст подсказки с текущим размером корзины"""
        size_bytes = get_bin_size()
        formatted_size = format_size(size_bytes)
        self.icon.title = f"Корзина: {formatted_size}"

    def on_tray_click(self, icon, event):
        """Обработчик кликов по иконке в трее"""
        # Обрабатываем только левую кнопку мыши
        if event.button != pystray.MouseButton.LEFT:
            return

        current_time = time.time()
        # Двойной клик определяется как 2 клика в течение 0.35 секунд
        if current_time - self.last_click_time < self.double_click_time:
            # Двойной клик
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
        """Устанавливает действие при двойном клике"""
        set_double_click_action(action)
        self.icon.update_menu()

    def run(self):
        self.icon.run()

    def quit_app(self):
        self._running = False
        self.icon.stop()

    def open_bin(self):
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
        """Современный диалог с гарантированным центрированием"""
        root = tk.Tk()
        root.title("Подтверждение очистки корзины")

        # Определяем путь к иконке приложения
        icon_path = resource_path("icons/bin_full.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)

        # Настройка DPI для Tkinter
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            dpi = user32.GetDpiForWindow(hwnd)
            scaling_factor = dpi / 96.0
            root.tk.call('tk', 'scaling', scaling_factor * 1.5)
        except:
            root.tk.call('tk', 'scaling', 2.0)

        # Стиль Windows 11
        bg_color = "#ffffff"  # Чистый белый фон
        text_color = "#000000"  # Черный текст
        accent_color = "#0078d7"  # Синий акцент Windows

        # Увеличиваем размеры окна
        root.geometry("720x400")  # Ширина 720, высота 400

        # Основной фрейм
        main_frame = ttk.Frame(root, padding=(40, 30))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        # Текст заголовка
        header_label = ttk.Label(
            header_frame,
            text="Очистить корзину?",
            font=("Segoe UI", 12, "bold"),
            foreground=text_color
        )
        header_label.pack(fill=tk.X)

        # Основной текст
        content_label = ttk.Label(
            main_frame,
            text="Вы уверены, что хотите окончательно удалить все элементы в корзине? Это действие нельзя отменить.",
            font=("Segoe UI", 10),
            wraplength=650,
            foreground=text_color,
            justify=tk.LEFT
        )
        content_label.pack(fill=tk.X, pady=(0, 40))

        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        # Стиль для акцентной кнопки (черный текст)
        style = ttk.Style()
        style.configure("Accent.TButton",
                        font=("Segoe UI", 10, "bold"),
                        foreground="black",  # Черный текст
                        background="#f0f0f0",  # Светло-серый фон
                        borderwidth=1,
                        padding=6)
        style.map("Accent.TButton",
                  background=[('active', '#e0e0e0'), ('pressed', '#d0d0d0')])

        # Кнопка "Очистить"
        def on_yes():
            root.destroy()
            self.perform_empty_bin()

        yes_btn = ttk.Button(
            button_frame,
            text="Очистить",
            command=on_yes,
            style="Accent.TButton",
            width=15
        )
        yes_btn.pack(side=tk.RIGHT)

        # Кнопка "Отмена"
        def on_no():
            root.destroy()

        no_btn = ttk.Button(
            button_frame,
            text="Отмена",
            command=on_no,
            width=15,
            padding=6
        )
        no_btn.pack(side=tk.RIGHT, padx=(15, 0))

        # Устанавливаем кнопку "Очистить" как активную по умолчанию
        root.after(100, lambda: yes_btn.focus_set())
        root.bind("<Return>", lambda event: on_yes())

        # Принудительное центрирование окна
        root.withdraw()  # Скрываем окно
        root.update_idletasks()  # Обновляем геометрию

        # Получаем размеры окна
        width = root.winfo_reqwidth()
        height = root.winfo_reqheight()

        # Получаем размеры экрана
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # Вычисляем позицию для центрирования
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        # Устанавливаем позицию
        root.geometry(f"+{x}+{y}")

        # Показываем окно
        root.deiconify()

        # Поверх всех окон
        root.attributes("-topmost", True)
        root.resizable(False, False)

        # Запуск главного цикла
        root.mainloop()

    def perform_empty_bin(self):
        empty_bin()
        self.update_icon()

    def toggle_confirm(self, item):
        current = get_confirm_setting()
        new_value = 0 if current == 1 else 1
        set_confirm_setting(new_value)

    def update_icon(self):
        level = get_bin_level()
        icon_name = self.levels[level] + ".ico"
        try:
            icon_path = resource_path(f"icons/{icon_name}")
            self.current_icon = Image.open(icon_path)

            if hasattr(self, 'icon'):
                self.icon.icon = self.current_icon
                # Обновляем тултип при обновлении иконки
                self.update_tooltip()
        except Exception as e:
            logger.error(f"Ошибка загрузки иконки: {e}")

    def auto_update(self):
        """Автоматическое обновление иконки и тултипа"""
        while self._running:
            self.update_icon()
            time.sleep(10)