from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.core.i18n import I18n


class ConfirmDialog(QDialog):
    def __init__(self, i18n: I18n, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n

        self.setWindowTitle(self.i18n.tr("confirm_dialog_title"))
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setMinimumWidth(420)
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

        title = QLabel(self.i18n.tr("confirm_dialog_title"))
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        root.addWidget(title)

        message = QLabel(self.i18n.tr("confirm_dialog_message"))
        message.setWordWrap(True)
        root.addWidget(message)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_btn = QPushButton(self.i18n.tr("cancel"))
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        confirm_btn = QPushButton(self.i18n.tr("confirm"))
        confirm_btn.setObjectName("confirmBtn")
        confirm_btn.clicked.connect(self.accept)
        buttons.addWidget(confirm_btn)

        root.addLayout(buttons)
