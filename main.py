from tray import TrayIcon
import logging
import os

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("binity.log"),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Запуск приложения Binity")

    try:
        tray = TrayIcon()
        tray.run()
    except Exception as e:
        logger.exception("Критическая ошибка в приложении")
        raise

    logger.info("Приложение успешно завершено")