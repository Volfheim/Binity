import logging
from tray import TrayIcon

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("binity.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Запуск приложения Binity")

    try:
        tray = TrayIcon()
        tray.run()  # Запускаем главный цикл
    except Exception:
        logger.exception("Критическая ошибка в приложении")
        raise

    logger.info("Приложение успешно завершено")
