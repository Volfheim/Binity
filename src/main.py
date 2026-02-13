from __future__ import annotations

import ctypes
import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.i18n import I18n
from src.core.resources import resource_path
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


def _consume_arg(flag: str) -> str:
    if flag not in sys.argv:
        return ""
    idx = sys.argv.index(flag)
    value = ""
    if idx + 1 < len(sys.argv):
        value = sys.argv[idx + 1]
        del sys.argv[idx:idx + 2]
    else:
        del sys.argv[idx]
    return value


def _write_ready_flag(path: str) -> None:
    if not path:
        return
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("ready")
    except Exception:
        pass


def _resolve_app_icon() -> QIcon:
    icon = QIcon()
    if getattr(sys, "frozen", False):
        exe_icon = QIcon(sys.executable)
        if not exe_icon.isNull():
            icon = exe_icon

    if icon.isNull():
        fallback_path = resource_path("icons/bin_full.ico")
        if os.path.exists(fallback_path):
            icon = QIcon(fallback_path)

    return icon


def main() -> int:
    _set_windows_app_id()
    show_after_update = _consume_switch("--show-after-update")
    update_ready_flag = _consume_arg("--update-ready-flag")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(__app_name__)

    app_icon = _resolve_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    settings = Settings()
    i18n = I18n(settings.language)

    lock = acquire_single_instance_lock()
    if lock is None:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle(__app_name__)
        msg.setText(i18n.tr("already_running"))
        if not app_icon.isNull():
            msg.setWindowIcon(app_icon)
        msg.exec()
        return 0

    app._instance_lock = lock  # type: ignore[attr-defined]

    tray_app = TrayApp(settings=settings, i18n=i18n, show_after_update=show_after_update)
    app._tray_app = tray_app  # type: ignore[attr-defined]
    _write_ready_flag(update_ready_flag)

    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
