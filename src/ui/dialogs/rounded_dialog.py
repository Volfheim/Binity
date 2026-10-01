"""Shared, alpha-rounded dialog chrome with native window movement on Windows."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from src.core.i18n import I18n
from src.core.resources import resource_path
from src.ui.theme import THEME_DARK, THEME_LIGHT, application_theme, dialog_colors


class WindowControl(QAbstractButton):
    def __init__(self, kind: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(32, 28)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        colors = self.window().colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        close_hover = self.kind == "close" and (self.underMouse() or self.isDown())
        foreground = "#ffffff" if close_hover else colors["muted"]
        if self.underMouse() or self.isDown() or self.hasFocus():
            painter.setPen(QPen(QColor(colors["primary"]), 1) if self.hasFocus() else Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["danger"] if close_hover else colors["hover"]))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 7, 7)
        pen = QPen(QColor(foreground), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "close":
            painter.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
            painter.drawLine(QPointF(cx + 4, cy - 4), QPointF(cx - 4, cy + 4))
        else:
            painter.drawLine(QPointF(cx - 5, cy + 2), QPointF(cx + 5, cy + 2))


class TitleBar(QWidget):
    def __init__(self, dialog: "RoundedDialog") -> None:
        super().__init__(dialog)
        self._drag_offset = None
        self.setFixedHeight(42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 5, 10, 3)
        layout.setSpacing(4)
        self.caption = QLabel("Binity", self)
        self.caption.setObjectName("windowCaption")
        self.caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.caption, 1)
        self.minimize_button = WindowControl("minimize", self)
        self.minimize_button.clicked.connect(dialog.showMinimized)
        layout.addWidget(self.minimize_button)
        self.close_button = WindowControl("close", self)
        self.close_button.clicked.connect(dialog.close)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            if not self._start_system_move():
                self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def _start_system_move(self) -> bool:
        handle = self.window().windowHandle()
        return handle is not None and handle.startSystemMove()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class AppIconBadge(QWidget):
    """An unchanged transparent ICO on a quiet, contrasting backing surface."""

    def __init__(self, icon: QIcon, size: int = 80, parent=None) -> None:
        super().__init__(parent)
        self.icon = icon if not icon.isNull() else QIcon(resource_path("icons/bin_full.ico"))
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.window().colors["badge"]))
        painter.drawRoundedRect(QRectF(self.rect()), 18, 18)
        side = int(self.width() * 0.72)
        target = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        pixmap = self.icon.pixmap(QSize(side, side), self.devicePixelRatioF())
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))


class RoundedDialog(QDialog):
    MARGIN = 8
    RADIUS = 18

    def __init__(self, i18n: I18n, theme: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.theme = theme or application_theme(QApplication.instance())
        self.colors = dialog_colors(self.theme)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        app_icon = QApplication.instance().windowIcon()
        self.setWindowIcon(app_icon if not app_icon.isNull() else QIcon(resource_path("icons/bin_full.ico")))
        root = QVBoxLayout(self)
        root.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        root.setSpacing(0)
        self.title_bar = TitleBar(self)
        root.addWidget(self.title_bar)
        self.content = QWidget(self)
        self.content.setObjectName("dialogContent")
        self.body_layout = QVBoxLayout(self.content)
        self.body_layout.setContentsMargins(20, 8, 20, 20)
        self.body_layout.setSpacing(16)
        root.addWidget(self.content, 1)
        RoundedDialog.set_theme(self, self.theme)
        self.refresh_chrome_texts()
        # The same source as native menus; no registry polling or OS preference writes.
        app = QApplication.instance()
        app.paletteChanged.connect(self._follow_application_theme)
        app.styleHints().colorSchemeChanged.connect(self._follow_application_theme)

    def _follow_application_theme(self, _value=None) -> None:
        theme = application_theme(QApplication.instance())
        if theme != self.theme:
            self.set_theme(theme)

    def refresh_chrome_texts(self, close_key: str = "close") -> None:
        for button, key in ((self.title_bar.close_button, close_key),
                            (self.title_bar.minimize_button, "minimize")):
            button.setToolTip(self.i18n.tr(key))
            button.setAccessibleName(self.i18n.tr(key))

    def fit_to_contents(self) -> None:
        self.ensurePolished()
        self.body_layout.activate()
        self.layout().activate()
        # sizeHint() wraps labels at a guessed width, leaving large empty gaps.
        height = self.layout().totalHeightForWidth(self.width())
        self.resize(self.width(), height if height >= 0 else self.sizeHint().height())

    def set_theme(self, theme: str) -> None:
        self.theme = THEME_LIGHT if theme == THEME_LIGHT else THEME_DARK
        self.colors = c = dialog_colors(self.theme)
        palette = QPalette(QApplication.palette())
        for role, key in ((QPalette.ColorRole.Window, "surface"), (QPalette.ColorRole.WindowText, "text"),
                          (QPalette.ColorRole.Base, "panel"), (QPalette.ColorRole.Text, "text"),
                          (QPalette.ColorRole.Button, "button"), (QPalette.ColorRole.ButtonText, "text"),
                          (QPalette.ColorRole.Highlight, "primary"),
                          (QPalette.ColorRole.HighlightedText, "primary_text")):
            palette.setColor(role, QColor(c[key]))
        self.setStyleSheet(f"""
            QLabel {{ color: {c['text']}; background: transparent; font-size: 13px; }}
            QLabel[role="heading"] {{ color: {c['title']}; font-size: 18px; font-weight: 700; }}
            QLabel[role="muted"], QLabel#windowCaption {{ color: {c['muted']}; font-size: 12px; }}
            QLabel#aboutTitle {{ color: {c['title']}; font-size: 26px; font-weight: 800; }}
            QPushButton {{ color: {c['text']}; background: {c['button']}; border: 1px solid {c['border']};
                border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {c['hover']}; }}
            QPushButton:pressed {{ background: {c['hover']}; }}
            QPushButton:focus {{ border: 1px solid {c['primary']}; }}
            QPushButton[role="primary"] {{ background: {c['primary']}; color: {c['primary_text']};
                border: 1px solid {c['primary']}; }}
            QPushButton[role="primary"]:hover {{ background: {c['primary_hover']}; }}
            QPushButton[role="danger"] {{ background: {c['danger']}; color: white; border: 1px solid {c['danger']}; }}
            QPushButton[role="danger"]:hover {{ background: {c['danger_hover']}; }}
            QPushButton[role="danger"]:focus {{ border: 1px solid {c['title']}; }}
            QPushButton:disabled {{ color: {c['muted']}; background: {c['surface']}; }}
            QPlainTextEdit {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']};
                border-radius: 8px; padding: 8px; font-size: 13px;
                selection-background-color: {c['primary']}; selection-color: {c['primary_text']}; }}
            QToolButton#githubBtn {{ background: {c['button']}; border: 1px solid {c['border']};
                border-radius: 24px; padding: 10px; }}
            QToolButton#githubBtn:hover {{ background: {c['hover']}; }}
            QToolButton#githubBtn:focus {{ border: 1px solid {c['primary']}; }}
        """)
        self.setPalette(palette)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for spread in range(6, 0, -1):
            painter.setPen(QPen(QColor(0, 0, 0, 5 + (6 - spread) * 2), spread * 2))
            painter.drawRoundedRect(surface.translated(0, 1), self.RADIUS, self.RADIUS)
        gradient = QLinearGradient(surface.topLeft(), surface.bottomLeft())
        gradient.setColorAt(0, QColor(self.colors["surface"]))
        gradient.setColorAt(1, QColor(self.colors["bottom"]))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(self.colors["border"]), 1))
        painter.drawRoundedRect(surface, self.RADIUS, self.RADIUS)
