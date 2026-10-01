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
from PyQt6.QtGui import QColor, QFont, QIcon, QImage, QLinearGradient, QPainter, QPen
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
        "Tray menu · Settings · Double click · Confirmation · About",
        f"Actual v{__version__} widgets · Isolated example state",
        "main-window.png",
    ),
    "RU": (
        "BINITY  /  УТИЛИТА ДЛЯ ТРЕЯ WINDOWS",
        "Корзина — всегда под рукой.",
        "Меню трея · Настройки · Двойной клик · Подтверждение · О программе",
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
        widgets = (controller.menu, controller.settings_menu, controller.double_click_menu,
                   confirmation, about)
        images = []
        for widget in widgets:
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            widget.show()
            app.processEvents()
            # Warm up native menu text before taking the final rendered frame.
            if isinstance(widget, QMenu):
                widget.grab()
                QTest.qWait(250)
            snapshot = widget.grab().toImage().copy()
            assert not snapshot.isNull()
            assert widget.palette().color(widget.backgroundRole()).lightness() < 128
            images.append(snapshot)
            widget.hide()
        assert __version__ in about.version_label.text()

        sheet = QImage(2400, 1400, QImage.Format.Format_RGB32)
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(2, 2)
        background = QLinearGradient(0, 0, 1200, 700)
        background.setColorAt(0, QColor("#28374b"))
        background.setColorAt(1, QColor("#1d293a"))
        painter.fillRect(QRectF(0, 0, 1200, 700), background)

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

        menu_position = QPointF(40, 177)
        settings_row = controller.menu.actionGeometry(controller.settings_menu.menuAction())
        double_click_row = controller.settings_menu.actionGeometry(controller.double_click_menu.menuAction())
        settings_position = QPointF(300, menu_position.y() + settings_row.top())
        double_click_position = QPointF(586, settings_position.y() + double_click_row.top())
        positions = (menu_position, settings_position, double_click_position,
                     QPointF(32, 446), QPointF(792, 132))

        def arrow(menu, row, source, target):
            start = QPointF(source.x() + menu.width() + 9, source.y() + row.center().y())
            end = QPointF(target.x() - 10, start.y())
            assert end.x() > start.x() + 20
            pen = QPen(QColor("#94bdf5"), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(start, end)
            painter.drawLine(end - QPointF(6, 4), end)
            painter.drawLine(end - QPointF(6, -4), end)

        arrow(controller.menu, settings_row, menu_position, settings_position)
        arrow(controller.settings_menu, double_click_row, settings_position, double_click_position)
        menu_labels = (("01  TRAY MENU", "02  SETTINGS", "03  DOUBLE CLICK") if language == "EN" else
                       ("01  МЕНЮ ТРЕЯ", "02  НАСТРОЙКИ", "03  ДВОЙНОЙ КЛИК"))
        for label, position in zip(menu_labels, positions):
            text(label, position.x(), position.y() - 27, 206, 20, 11, "#bdcde2", True)

        placed = []
        for widget, snapshot, position in zip(widgets, images, positions):
            x, y = position.x(), position.y()
            rect = QRectF(x, y, widget.width(), widget.height())
            assert QRectF(0, 0, 1200, 700).contains(rect), (language, rect)
            assert all(not rect.intersects(other) for other in placed), (language, rect)
            placed.append(rect)
            painter.drawImage(QPointF(x, y), snapshot)
        painter.end()
        assert sheet.save(str(output / filename))
        print(f"{language}: {filename}, 2400x1400, Binity {__version__}")
        for widget in (confirmation, about):
            widget.deleteLater()
        controller.dispose()
        app.processEvents()


if __name__ == "__main__":
    main()
