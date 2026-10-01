from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QTextOption
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy

from src.core.i18n import I18n
from src.ui.dialogs.rounded_dialog import RoundedDialog


class StatusBadge(QLabel):
    def __init__(self, warning: bool, parent=None) -> None:
        super().__init__(parent)
        self.warning = warning
        self.setFixedSize(44, 44)

    def paintEvent(self, event) -> None:
        colors = self.window().colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["warning_bg"] if self.warning else colors["panel"]))
        painter.drawRoundedRect(QRectF(self.rect()), 13, 13)
        color = QColor(colors["warning"] if self.warning else colors["primary"])
        painter.setPen(QPen(color, 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.warning:
            triangle = QPainterPath(QPointF(22, 10))
            triangle.lineTo(35, 33)
            triangle.lineTo(9, 33)
            triangle.closeSubpath()
            painter.drawPath(triangle)
            painter.drawLine(QPointF(22, 18), QPointF(22, 24))
            painter.drawPoint(QPointF(22, 28))
        else:
            painter.drawEllipse(QRectF(10, 10, 24, 24))
            painter.drawPoint(QPointF(22, 16))
            painter.drawLine(QPointF(22, 21), QPointF(22, 28))


class MessageDialog(RoundedDialog):
    def __init__(self, i18n: I18n, title: str, text: str,
                 severity: QMessageBox.Icon = QMessageBox.Icon.Information,
                 icon: QIcon | None = None, informative_text: str = "", detailed_text: str = "",
                 parent=None) -> None:
        super().__init__(i18n, parent=parent)
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        warning = severity in (QMessageBox.Icon.Warning, QMessageBox.Icon.Critical)
        # Keep network/OS error text selectable but out of the main message layout.
        if warning and not detailed_text and "\n" in text:
            text, detailed_text = text.split("\n", 1)
        if len(text) > 600:
            detailed_text = text + ("\n\n" + detailed_text if detailed_text else "")
            text = i18n.tr("message_details_hint")
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "heading")
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        heading = QHBoxLayout()
        heading.setSpacing(12)
        self.status_badge = StatusBadge(warning, self)
        heading.addWidget(self.status_badge)
        heading.addWidget(self.title_label, 1)
        self.body_layout.addLayout(heading)
        self.message_label = QLabel(text + ("\n\n" + informative_text if informative_text else ""))
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                                   | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.message_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.body_layout.addWidget(self.message_label)
        self.details_button = QPushButton(self)
        self.details_button.setVisible(bool(detailed_text.strip()))
        self.body_layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.details_edit = QPlainTextEdit(self)
        self.details_edit.setReadOnly(True)
        self.details_edit.setPlainText(detailed_text)
        self.details_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.details_edit.setFixedHeight(160)
        self.details_edit.hide()
        self.body_layout.addWidget(self.details_edit)
        self.details_button.clicked.connect(self._toggle_details)
        self.ok_button = QPushButton("OK", self)
        self.ok_button.setProperty("role", "primary")
        self.ok_button.setMinimumWidth(92)
        self.set_initial_button(self.ok_button)
        self.ok_button.clicked.connect(self.accept)
        self.body_layout.addWidget(self.ok_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh_texts()
        self._resize_for_content()

    def _toggle_details(self) -> None:
        self.details_edit.setVisible(self.details_edit.isHidden())
        self.refresh_texts()
        self._resize_for_content()

    def _resize_for_content(self) -> None:
        self.ensurePolished()
        outer = self.layout().contentsMargins()
        inner = self.body_layout.contentsMargins()
        padding = outer.left() + outer.right() + inner.left() + inner.right()
        message_width = max((self.message_label.fontMetrics().horizontalAdvance(line)
                             for line in self.message_label.text().splitlines()), default=0)
        heading_width = self.status_badge.width() + 12 + self.title_label.fontMetrics().horizontalAdvance(
            self.title_label.text())
        content_width = max(message_width, heading_width, self.ok_button.sizeHint().width())
        if not self.details_button.isHidden():
            content_width = max(content_width, self.details_button.sizeHint().width())
        # Keep short messages tight; only the technical-details view needs a wide text area.
        width = max(self.minimumWidth(), min(480, content_width + padding + 2))
        if not self.details_edit.isHidden():
            width = max(width, 500)
        self.body_layout.activate()
        self.layout().activate()
        self.resize(width, self.height())
        self.fit_to_contents()

    def refresh_texts(self) -> None:
        self.refresh_chrome_texts()
        key = "update_show_details" if self.details_edit.isHidden() else "update_hide_details"
        self.details_button.setText(self.i18n.tr(key))
        self.details_edit.setAccessibleName(self.i18n.tr("message_details"))
