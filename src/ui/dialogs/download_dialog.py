from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.core.i18n import I18n
from src.ui.dialogs.rounded_dialog import AppIconBadge, RoundedDialog
from src.ui.wave_progress import WaveProgressBar


class DownloadDialog(RoundedDialog):
    def __init__(self, i18n: I18n, icon: QIcon, parent=None) -> None:
        super().__init__(i18n, parent=parent)
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setMinimumWidth(440)
        self.setWindowModality(Qt.WindowModality.NonModal)
        hero = QHBoxLayout()
        hero.setSpacing(20)
        copy = QVBoxLayout()
        copy.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setProperty("role", "heading")
        self.title_label.setWordWrap(True)
        copy.addWidget(self.title_label)
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setProperty("role", "muted")
        copy.addWidget(self.hint_label)
        hero.addLayout(copy, 1)
        self.app_icon = AppIconBadge(self.windowIcon(), 64, self)
        hero.addWidget(self.app_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.body_layout.addLayout(hero)
        self.bar = WaveProgressBar(self)
        self.bar.setPalette(self.palette())
        self.bar.setMinimumHeight(32)
        self.body_layout.addWidget(self.bar)
        self.hide_button = QPushButton()
        self.hide_button.clicked.connect(self.hide)
        self.body_layout.addWidget(self.hide_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh_texts()
        self.resize(460, self.sizeHint().height())
        self.fit_to_contents()

    def set_theme(self, theme: str) -> None:
        super().set_theme(theme)
        self.bar.setPalette(self.palette())

    def refresh_texts(self) -> None:
        self.refresh_chrome_texts("hide_window")
        self.setWindowTitle(self.i18n.tr("update_dialog_title"))
        self.title_label.setText(self.i18n.tr("update_downloading"))
        self.hint_label.setText(self.i18n.tr("update_background_hint"))
        self.bar.setAccessibleName(self.i18n.tr("update_downloading"))
        self.hide_button.setText(self.i18n.tr("hide_window"))

    def setValue(self, value: int) -> None:
        self.bar.setValue(max(0, min(100, int(value))))

    def labelText(self) -> str:
        return self.title_label.text()

    def reject(self) -> None:
        # Esc/Alt+F4/close only hide the view; the controller still owns the download.
        self.hide()

    def closeEvent(self, event) -> None:
        self.hide()
        event.accept()
