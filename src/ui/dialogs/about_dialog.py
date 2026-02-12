from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.core.i18n import I18n
from src.core.resources import resource_path
from src.version import __app_name__, __author__, __version__


REPO_URL = "https://github.com/Volfheim/Binity"


class AboutDialog(QDialog):
    def __init__(self, i18n: I18n, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n

        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(False)
        self.setMinimumWidth(420)
        self.setStyleSheet(
            """
            QDialog { background: #121826; color: #f8fafc; }
            QLabel#title { font-size: 18px; font-weight: 700; color: #f8fafc; }
            QLabel { font-size: 13px; color: #cbd5e1; }
            QPushButton {
                background: #1d4ed8;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #1e40af; }
            QPushButton#closeBtn { background: transparent; border: 1px solid #334155; color: #cbd5e1; }
            QPushButton#closeBtn:hover { background: #1e293b; }
            """
        )

        icon_path = resource_path("icons/bin_full.ico")
        self.setWindowIcon(QIcon(icon_path))

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(20, 20, 20, 20)
        self.root.setSpacing(10)

        self.title_label = QLabel(__app_name__)
        self.title_label.setObjectName("title")
        self.root.addWidget(self.title_label)

        self.version_label = QLabel()
        self.root.addWidget(self.version_label)

        self.author_label = QLabel()
        self.root.addWidget(self.author_label)

        self.repo_label = QLabel(f"<a href='{REPO_URL}'>{REPO_URL}</a>")
        self.repo_label.setOpenExternalLinks(False)
        self.repo_label.linkActivated.connect(lambda _: QDesktopServices.openUrl(QUrl(REPO_URL)))
        self.repo_label.setStyleSheet("color: #60a5fa;")
        self.root.addWidget(self.repo_label)

        actions = QHBoxLayout()
        actions.addStretch()

        self.website_btn = QPushButton()
        self.website_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        actions.addWidget(self.website_btn)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.clicked.connect(self.close)
        actions.addWidget(self.close_btn)

        self.root.addLayout(actions)

        self.refresh_texts()

    def refresh_texts(self) -> None:
        self.setWindowTitle(self.i18n.tr("about_title"))
        self.version_label.setText(f"{self.i18n.tr('version')}: {__version__}")
        self.author_label.setText(f"{self.i18n.tr('author')}: {__author__}")
        self.website_btn.setText(self.i18n.tr("website"))
        self.close_btn.setText(self.i18n.tr("close"))
