from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QLabel, QPushButton, QToolButton

from src.core.i18n import I18n
from src.core.resources import resource_path
from src.ui.dialogs.rounded_dialog import AppIconBadge, RoundedDialog
from src.ui.theme import THEME_DARK, THEME_LIGHT
from src.version import __app_name__, __author__, __version__

REPO_URL = "https://github.com/Volfheim/Binity"


class AboutDialog(RoundedDialog):
    def __init__(self, i18n: I18n, theme: str = THEME_DARK, parent=None) -> None:
        super().__init__(i18n, theme, parent)
        self.setModal(False)
        self.setFixedSize(360, 540)
        self.setWindowIcon(self._bin_icon(theme))
        self.root = self.body_layout
        self.root.setSpacing(12)
        self.root.addStretch(1)
        self.logo_label = AppIconBadge(self._bin_icon(theme), 104, self)
        self.root.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.title_label = QLabel(__app_name__)
        self.title_label.setObjectName("aboutTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setProperty("role", "muted")
        self.subtitle_label.setWordWrap(True)
        self.version_label = QLabel()
        self.author_label = QLabel()
        for label in (self.title_label, self.subtitle_label, self.version_label, self.author_label):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.root.addWidget(label)
        self.github_btn = QToolButton()
        self.github_btn.setObjectName("githubBtn")
        self.github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.github_btn.setIconSize(QSize(28, 28))
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        self.root.addWidget(self.github_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.github_hint = QLabel("GitHub")
        self.github_hint.setProperty("role", "muted")
        self.github_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(self.github_hint)
        self.close_btn = QPushButton()
        self.close_btn.setMinimumWidth(136)
        self.close_btn.clicked.connect(self.close)
        self.set_initial_button(self.close_btn)
        self.root.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.root.addStretch(1)
        self.set_theme(theme)
        self.refresh_texts()

    def set_theme(self, theme: str) -> None:
        super().set_theme(theme)
        name = "icons/github_dark.svg" if self.theme == THEME_LIGHT else "icons/github.svg"
        icon = QIcon(resource_path(name))
        self.github_btn.setIcon(icon)
        self.github_btn.setText("GH" if icon.isNull() else "")

    @staticmethod
    def _bin_icon(_theme: str) -> QIcon:
        return QIcon(resource_path("icons/bin_full.ico"))

    def refresh_texts(self) -> None:
        self.refresh_chrome_texts()
        self.setWindowTitle(self.i18n.tr("about_title"))
        self.subtitle_label.setText(self.i18n.tr("about_description"))
        self.version_label.setText(f"{self.i18n.tr('version')}: {__version__}")
        self.author_label.setText(f"{self.i18n.tr('author')}: {__author__}")
        self.github_btn.setToolTip(self.i18n.tr("website"))
        self.github_btn.setAccessibleName(self.i18n.tr("website"))
        self.close_btn.setText(self.i18n.tr("close"))
