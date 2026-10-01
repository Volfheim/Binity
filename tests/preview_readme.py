"""Render the bilingual README overview from real, isolated Windows Qt widgets.

Run on Windows: py -3.13 tests/preview_readme.py
No tray registration, user settings, recycle-bin operations, or visible windows.
"""
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ.setdefault("QT_SCALE_FACTOR", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QImage, QPainter
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMenu

from src.ui.dialogs.about_dialog import AboutDialog
from src.ui.dialogs.confirm_dialog import ConfirmDialog
from src.ui.theme import ThemeController
from src.version import __version__
from tests.test_themes import ScreenHarness


COPY = {
    "EN": (
        "BINITY  /  WINDOWS TRAY UTILITY",
        "Your Recycle Bin, within reach.",
        "Tray menu · Settings · Confirmation · About",
        f"Actual v{__version__} widgets · Isolated example state",
        "main-window.png",
    ),
    "RU": (
        "BINITY  /  УТИЛИТА ДЛЯ ТРЕЯ WINDOWS",
        "Корзина — всегда под рукой.",
        "Меню трея · Настройки · Подтверждение · О программе",
        f"Реальные виджеты v{__version__} · Изолированный пример",
        "main-window-ru.png",
    ),
}


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(ROOT / "icons/bin_full.ico")))
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    manager = ThemeController(app)
    app.processEvents()
    assert manager.current_theme == "dark"
    output = ROOT / "docs/images"
    output.mkdir(parents=True, exist_ok=True)

    for language, (eyebrow, title, subtitle, footer, filename) in COPY.items():
        controller = ScreenHarness(language, "dark")
        controller.updater.has_update = False
        controller._refresh_update_action_text()
        about = AboutDialog(controller.i18n, "dark")
        confirmation = ConfirmDialog(controller.i18n, theme="dark")
        widgets = (controller.menu, controller.settings_menu, confirmation, about)
        images = []
        for widget in widgets:
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            widget.show()
            app.processEvents()
            # Native menu text can finish painting after the first event cycle.
            if isinstance(widget, QMenu):
                QTest.qWait(250)
            pixmap = widget.grab()
            assert not pixmap.isNull()
            assert widget.palette().color(widget.backgroundRole()).lightness() < 128
            images.append(pixmap)
            widget.hide()
        assert __version__ in about.version_label.text()

        sheet = QImage(2400, 1400, QImage.Format.Format_RGB32)
        sheet.fill(QColor("#0e1522"))
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(2, 2)

        def text(value, x, y, width, height, size, color, bold=False):
            font = QFont("Segoe UI")
            font.setPixelSize(size)
            font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
            painter.setFont(font)
            painter.setPen(QColor(color))
            assert painter.fontMetrics().horizontalAdvance(value) <= width, value
            painter.drawText(QRectF(x, y, width, height), Qt.AlignmentFlag.AlignLeft
                             | Qt.AlignmentFlag.AlignVCenter, value)

        text(eyebrow, 40, 27, 1120, 28, 14, "#82aff5", True)
        text(title, 40, 59, 1120, 58, 36, "#f2f5fb", True)
        text(subtitle, 40, 112, 1120, 26, 14, "#a1b2cb")
        text(footer, 40, 651, 690, 27, 12, "#97a8c0")

        positions = ((40, 177), (300, 177), (32, 446), (792, 132))
        placed = []
        for widget, pixmap, (x, y) in zip(widgets, images, positions):
            rect = QRectF(x, y, widget.width(), widget.height())
            assert QRectF(0, 0, 1200, 700).contains(rect), (language, rect)
            assert all(not rect.intersects(other) for other in placed), (language, rect)
            placed.append(rect)
            painter.drawPixmap(QPointF(x, y), pixmap)
        painter.end()
        assert sheet.save(str(output / filename))
        print(f"{language}: {filename}, 2400x1400, Binity {__version__}")
        for widget in (confirmation, about):
            widget.deleteLater()
        controller.dispose()
        app.processEvents()


if __name__ == "__main__":
    main()
