from __future__ import annotations

import ctypes
import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.i18n import I18n
from src.core.settings import Settings
from src.core.single_instance import acquire_single_instance_lock
from src.ui.tray.tray_app import TrayApp
from src.version import __app_name__


def _set_windows_app_id() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Volfheim.Binity")
    except Exception:
        pass


def _consume_switch(flag: str) -> bool:
    if flag in sys.argv:
        sys.argv.remove(flag)
        return True
    return False


def main() -> int:
    _set_windows_app_id()
    show_after_update = _consume_switch("--show-after-update")

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

    tray_app = TrayApp(settings=settings, i18n=i18n, show_after_update=show_after_update)
    app._tray_app = tray_app  # type: ignore[attr-defined]

    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
