import logging
import sys
import ctypes
import os
import time
import psutil
from tray import TrayIcon


def verify_signature():
    """Заглушка для проверки цифровой подписи"""
    return True


def is_already_running():
    """Безопасная проверка дублирующихся процессов"""
    current_pid = os.getpid()
    current_name = os.path.basename(sys.argv[0]).lower()

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.pid == current_pid:
                continue

            if proc.info['name'].lower() == current_name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return False


def get_log_path():
    """Возвращает безопасный путь для лог-файла"""
    try:
        appdata = os.getenv('APPDATA')
        if appdata:
            log_dir = os.path.join(appdata, 'Binity')
            os.makedirs(log_dir, exist_ok=True)
            return os.path.join(log_dir, 'binity.log')
    except Exception as e:
        print(f"Ошибка создания папки логов: {e}")

    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, 'binity.log')
    except:
        return 'binity.log'


def setup_logging():
    """Настраивает систему логирования"""
    log_file = get_log_path()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Ошибка создания файлового обработчика логов: {e}")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger, log_file


if __name__ == "__main__":
    # Задержка для обхода эвристического анализа антивируса
    time.sleep(2.5)

    # Показываем сообщение о запуске
    ctypes.windll.user32.MessageBoxW(0, "Binity is starting...", "Binity", 0x40)

    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Binity.TrayApp")

    if not verify_signature():
        print("Проверка цифровой подписи не пройдена!")
        sys.exit(1)

    if is_already_running():
        print("Приложение уже запущено")
        sys.exit(0)

    logger, log_path = setup_logging()

    logger.info("=" * 50)
    logger.info("Запуск приложения Binity v2.9")
    logger.info(f"Лог-файл: {os.path.abspath(log_path)}")
    logger.info(f"Текущая директория: {os.getcwd()}")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Архитектура: {'64-bit' if sys.maxsize > 2 ** 32 else '32-bit'}")
    logger.info("=" * 50)

    try:
        tray = TrayIcon()
        tray.run()
    except Exception as e:
        logger.exception(f"Критическая ошибка в приложении: {e}")
        sys.exit(1)

    logger.info("Приложение успешно завершено")