from __future__ import annotations

import ctypes
import logging
import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.i18n import I18n
from src.core.logging_setup import setup_logging
from src.core.settings import Settings
from src.core.single_instance import acquire_single_instance_lock
from src.ui.tray.tray_app import TrayApp
from src.version import __app_name__, __version__


def _set_windows_app_id() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Volfheim.Binity")
    except Exception:
        pass


def main() -> int:
    log_path = setup_logging()
    logger = logging.getLogger(__name__)

    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(__app_name__)

    settings = Settings()
    i18n = I18n(settings.language)

    lock = acquire_single_instance_lock()
    if lock is None:
        QMessageBox.information(None, __app_name__, i18n.tr("already_running"))
        return 0

    app._instance_lock = lock  # type: ignore[attr-defined]

    tray_app = TrayApp(settings=settings, i18n=i18n)
    app._tray_app = tray_app  # type: ignore[attr-defined]

    logger.info("%s started v%s", __app_name__, __version__)
    logger.info("Log file: %s", log_path)

    exit_code = app.exec()
    logger.info("%s exited with code %s", __app_name__, exit_code)
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
