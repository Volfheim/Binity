"""Keep custom dialogs and native Qt widgets on the same application theme."""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

THEME_DARK = "dark"
THEME_LIGHT = "light"


def application_theme(app: QApplication) -> str:
    scheme = app.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return THEME_DARK
    if scheme == Qt.ColorScheme.Light:
        return THEME_LIGHT
    background = app.palette().color(QPalette.ColorRole.Window)
    return THEME_DARK if background.lightness() < 128 else THEME_LIGHT


def dialog_colors(theme: str) -> dict[str, str]:
    if theme == THEME_LIGHT:
        return dict(surface="#f7f9fc", bottom="#eef2f8", text="#26344d", title="#0f172a",
                    muted="#52647c", border="#b8c5d6", button="#ffffff", hover="#e2eaf5",
                    panel="#ffffff", primary="#295fbd", primary_text="#ffffff",
                    primary_hover="#214e9c", danger="#c9364d", danger_hover="#aa2940",
                    badge="#e5edf8", warning="#915400", warning_bg="#fff0d4")
    return dict(surface="#111827", bottom="#0b1220", text="#d8e1ee", title="#f8fafc",
                muted="#a3b4cc", border="#40516b", button="#182438", hover="#25354d",
                panel="#182438", primary="#a9c7ff", primary_text="#102143",
                primary_hover="#c3d8ff", danger="#c9364d", danger_hover="#aa2940",
                badge="#d3deef", warning="#ffd18a", warning_bg="#352b20")


class ThemeController(QObject):
    changed = pyqtSignal(str)

    def __init__(self, app: QApplication, sync_enabled: bool = True) -> None:
        super().__init__(app)
        self._app = app
        self._hints = app.styleHints()
        self._sync_enabled = bool(sync_enabled)
        self.current_theme = self._read_theme()
        self._hints.colorSchemeChanged.connect(self._refresh)
        app.paletteChanged.connect(self._refresh)
        if not self._sync_enabled:
            self._pin_current_theme()

    def _read_theme(self) -> str:
        return application_theme(self._app)

    def _refresh(self, _value=None) -> None:
        if not self._sync_enabled:
            return
        theme = self._read_theme()
        if theme != self.current_theme:
            self.current_theme = theme
            self.changed.emit(theme)

    def _pin_current_theme(self) -> None:
        scheme = Qt.ColorScheme.Dark if self.current_theme == THEME_DARK else Qt.ColorScheme.Light
        # This changes only Binity, never the Windows personalization settings.
        self._hints.setColorScheme(scheme)

    def set_sync_enabled(self, enabled: bool) -> None:
        self._sync_enabled = bool(enabled)
        if self._sync_enabled:
            self._hints.unsetColorScheme()
            self._refresh()
        else:
            self._pin_current_theme()
