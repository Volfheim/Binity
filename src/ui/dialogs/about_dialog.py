from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QToolButton, QVBoxLayout

from src.core.i18n import I18n
from src.core.resources import resource_path
from src.services.system_theme import THEME_DARK, THEME_LIGHT
from src.version import __app_name__, __author__, __description__, __version__


REPO_URL = "https://github.com/Volfheim/Binity"


class AboutDialog(QDialog):
    def __init__(self, i18n: I18n, theme: str = THEME_DARK, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.theme = THEME_DARK

        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(False)
        self.setFixedSize(360, 520)

        icon_path = resource_path("icons/bin_full.ico")
        self.setWindowIcon(QIcon(icon_path))

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 24, 24, 24)
        self.root.setSpacing(10)

        self.root.addStretch(1)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QPixmap(resource_path("icons/bin_full.ico"))
        if not logo_pixmap.isNull():
            self.logo_label.setPixmap(
                logo_pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        self.root.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel(__app_name__)
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(self.title_label)

        self.subtitle_label = QLabel(__description__)
        self.subtitle_label.setObjectName("subtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.root.addWidget(self.subtitle_label)

        self.version_label = QLabel()
        self.version_label.setObjectName("meta")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(self.version_label)

        self.author_label = QLabel()
        self.author_label.setObjectName("meta")
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(self.author_label)

        self.github_btn = QToolButton()
        self.github_btn.setObjectName("githubBtn")
        self.github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.github_btn.setIconSize(QSize(28, 28))
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))

        github_icon = QIcon(resource_path("icons/github.svg"))
        if not github_icon.isNull():
            self.github_btn.setIcon(github_icon)
        else:
            self.github_btn.setText("GH")

        self.root.addWidget(self.github_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.github_hint = QLabel()
        self.github_hint.setObjectName("githubHint")
        self.github_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(self.github_hint)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setMinimumWidth(136)
        self.close_btn.clicked.connect(self.close)
        self.root.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.root.addStretch(1)

        self.set_theme(theme)
        self.refresh_texts()


    def set_theme(self, theme: str) -> None:
        candidate = str(theme or THEME_DARK).lower()
        if candidate not in (THEME_DARK, THEME_LIGHT):
            candidate = THEME_DARK
        self.theme = candidate

        if candidate == THEME_LIGHT:
            icon_name = "icons/github_dark.svg"
            btn_style = """
                QToolButton#githubBtn {
                    background: rgba(59, 130, 246, 0.12);
                    border: 1px solid #8fb2ef;
                    border-radius: 24px;
                    padding: 10px;
                }
                QToolButton#githubBtn:hover {
                    background: rgba(59, 130, 246, 0.24);
                    border: 1px solid #5e8ee0;
                }
            """
            dialog_style = """
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f7f9fc,
                        stop:1 #eef2f8);
                    color: #0f172a;
                    border: 1px solid #d5deea;
                    border-radius: 14px;
                }
                QLabel#title {
                    font-size: 26px;
                    font-weight: 800;
                    color: #0f172a;
                }
                QLabel#subtitle {
                    font-size: 12px;
                    color: #3b4f72;
                    font-weight: 600;
                }
                QLabel#meta {
                    font-size: 13px;
                    color: #1f2937;
                }
                QLabel#githubHint {
                    font-size: 11px;
                    color: #334155;
                }
                QPushButton#closeBtn {
                    background: transparent;
                    border: 1px solid #94a3b8;
                    border-radius: 10px;
                    color: #1e293b;
                    padding: 9px 22px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton#closeBtn:hover {
                    background: #e2e8f0;
                }
            """
        else:
            icon_name = "icons/github.svg"
            btn_style = """
                QToolButton#githubBtn {
                    background: rgba(30, 58, 138, 0.24);
                    border: 1px solid #34538a;
                    border-radius: 24px;
                    padding: 10px;
                }
                QToolButton#githubBtn:hover {
                    background: rgba(59, 130, 246, 0.35);
                    border: 1px solid #4f7fd8;
                }
            """
            dialog_style = """
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #111827,
                        stop:1 #0b1220);
                    color: #f8fafc;
                    border: 1px solid #23314f;
                    border-radius: 14px;
                }
                QLabel#title {
                    font-size: 26px;
                    font-weight: 800;
                    color: #f8fafc;
                }
                QLabel#subtitle {
                    font-size: 12px;
                    color: #8aa3d8;
                    font-weight: 600;
                }
                QLabel#meta {
                    font-size: 13px;
                    color: #d1d5db;
                }
                QLabel#githubHint {
                    font-size: 11px;
                    color: #8aa3d8;
                }
                QPushButton#closeBtn {
                    background: transparent;
                    border: 1px solid #334155;
                    border-radius: 10px;
                    color: #cbd5e1;
                    padding: 9px 22px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton#closeBtn:hover {
                    background: #1e293b;
                }
            """

        icon_obj = QIcon(resource_path(icon_name))
        if not icon_obj.isNull():
            self.github_btn.setIcon(icon_obj)
        else:
            self.github_btn.setText("GH")

        self.setStyleSheet(dialog_style + btn_style)

    def refresh_texts(self) -> None:
        self.setWindowTitle(self.i18n.tr("about_title"))
        self.version_label.setText(f"{self.i18n.tr('version')}: {__version__}")
        self.author_label.setText(f"{self.i18n.tr('author')}: {__author__}")
        self.github_btn.setToolTip(self.i18n.tr("website"))
        self.github_hint.setText("GitHub")
        self.close_btn.setText(self.i18n.tr("close"))

