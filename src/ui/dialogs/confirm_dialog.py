from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.core.i18n import I18n
from src.core.resources import resource_path


class ConfirmDialog(QDialog):
    def __init__(self, i18n: I18n, message_override: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self._message_override = message_override

        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setMinimumWidth(420)

        app = QApplication.instance()
        app_icon = app.windowIcon() if app else QIcon()
        if app_icon.isNull():
            app_icon = QIcon(resource_path("icons/bin_full.ico"))
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.setStyleSheet(
            """
            QDialog { background: #171a23; color: #f3f4f6; }
            QLabel { color: #e5e7eb; font-size: 13px; }
            QPushButton {
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#confirmBtn { background: #ef4444; color: #ffffff; border: none; }
            QPushButton#confirmBtn:hover { background: #dc2626; }
            QPushButton#cancelBtn { background: transparent; color: #cbd5e1; border: 1px solid #475569; }
            QPushButton#cancelBtn:hover { background: #1e293b; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        root.addWidget(self.title_label)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton()
        self.confirm_btn.setObjectName("confirmBtn")
        self.confirm_btn.clicked.connect(self.accept)
        buttons.addWidget(self.confirm_btn)

        root.addLayout(buttons)
        self.refresh_texts()

    def refresh_texts(self) -> None:
        title = self.i18n.tr("confirm_dialog_title")
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.message_label.setText(self._message_override or self.i18n.tr("confirm_dialog_message"))
        self.cancel_btn.setText(self.i18n.tr("cancel"))
        self.confirm_btn.setText(self.i18n.tr("confirm"))
