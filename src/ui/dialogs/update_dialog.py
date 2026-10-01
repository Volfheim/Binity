from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QTextOption
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from src.core.i18n import I18n
from src.ui.dialogs.rounded_dialog import AppIconBadge, RoundedDialog


class UpdateDialog(RoundedDialog):
    SKIP_VERSION = 2

    def __init__(self, i18n: I18n, version: str, notes: str, icon: QIcon, parent=None) -> None:
        super().__init__(i18n, parent=parent)
        self.version = version
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setMinimumWidth(480)

        root = self.body_layout
        hero = QHBoxLayout()
        hero.setSpacing(20)
        copy = QVBoxLayout()
        copy.setSpacing(8)

        self.title_label = QLabel()
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        self.title_label.setProperty("role", "heading")
        copy.addWidget(self.title_label)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setProperty("role", "muted")
        copy.addWidget(self.hint_label)
        hero.addLayout(copy, 1)
        self.app_icon = AppIconBadge(self.windowIcon(), parent=self)
        hero.addWidget(self.app_icon, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(hero)

        self.details_button = QPushButton(self)
        self.details_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.details_button.setVisible(bool(notes.strip()))
        root.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.details_panel = QWidget()
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_title = QLabel()
        details_layout.addWidget(self.notes_title)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setPlainText(notes)
        self.notes_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.notes_edit.setMinimumHeight(180)
        details_layout.addWidget(self.notes_edit)
        self.details_panel.hide()
        root.addWidget(self.details_panel)
        self.details_button.clicked.connect(lambda: self._toggle_details(self.details_panel.isHidden()))

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch()
        self.install_button = QPushButton()
        self.install_button.setProperty("role", "primary")
        self.skip_button = QPushButton()
        self.later_button = QPushButton()
        for button in (self.install_button, self.skip_button, self.later_button):
            buttons.addWidget(button)
        self.install_button.clicked.connect(self.accept)
        self.skip_button.clicked.connect(lambda: self.done(self.SKIP_VERSION))
        self.later_button.clicked.connect(self.reject)
        self.set_initial_button(self.later_button)
        root.addLayout(buttons)
        self.refresh_texts()
        self.resize(500, self.sizeHint().height())
        self.fit_to_contents()

    def _toggle_details(self, expanded: bool) -> None:
        self.details_panel.setVisible(expanded)
        self.refresh_texts()
        self.fit_to_contents()

    def refresh_texts(self) -> None:
        self.refresh_chrome_texts()
        self.setWindowTitle(self.i18n.tr("update_dialog_title"))
        self.title_label.setText(self.i18n.tr("update_dialog_message").format(version=self.version))
        self.hint_label.setText(self.i18n.tr("update_dialog_hint"))
        key = "update_show_details" if self.details_panel.isHidden() else "update_hide_details"
        self.details_button.setText(self.i18n.tr(key))
        self.notes_title.setText(self.i18n.tr("release_notes"))
        self.notes_edit.setAccessibleName(self.i18n.tr("release_notes"))
        self.install_button.setText(self.i18n.tr("update_install"))
        self.skip_button.setText(self.i18n.tr("update_skip"))
        self.later_button.setText(self.i18n.tr("update_later"))
        for button in (self.install_button, self.skip_button, self.later_button):
            button.setMinimumWidth(button.sizeHint().width())
