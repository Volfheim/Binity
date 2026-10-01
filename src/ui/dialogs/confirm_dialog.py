from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from src.core.i18n import I18n
from src.ui.dialogs.rounded_dialog import RoundedDialog
from src.ui.theme import THEME_DARK


class ConfirmDialog(RoundedDialog):
    def __init__(self, i18n: I18n, message_override: str | None = None,
                 theme: str = THEME_DARK, parent=None) -> None:
        super().__init__(i18n, theme, parent)
        self._message_override = message_override
        self.setModal(True)
        self.setMinimumWidth(440)
        root = self.body_layout
        self.title_label = QLabel()
        self.title_label.setProperty("role", "heading")
        self.title_label.setWordWrap(True)
        root.addWidget(self.title_label)
        self.message_label = QLabel()
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch()
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.reject)
        self.set_initial_button(self.cancel_btn)
        buttons.addWidget(self.cancel_btn)
        self.confirm_btn = QPushButton()
        self.confirm_btn.setProperty("role", "danger")
        self.confirm_btn.clicked.connect(self.accept)
        buttons.addWidget(self.confirm_btn)
        root.addLayout(buttons)
        self.refresh_texts()
        self.resize(460, self.sizeHint().height())
        self.fit_to_contents()

    def refresh_texts(self) -> None:
        self.refresh_chrome_texts()
        title = self.i18n.tr("confirm_dialog_title")
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.message_label.setText(self._message_override or self.i18n.tr("confirm_dialog_message"))
        self.cancel_btn.setText(self.i18n.tr("cancel"))
        self.confirm_btn.setText(self.i18n.tr("confirm"))
