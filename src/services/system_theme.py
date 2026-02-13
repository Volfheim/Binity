from __future__ import annotations

import os

THEME_DARK = "dark"
THEME_LIGHT = "light"


class SystemThemeService:
    @staticmethod
    def get_theme() -> str:
        if os.name != "nt":
            return THEME_DARK

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return THEME_LIGHT if int(value) == 1 else THEME_DARK
        except Exception:
            return THEME_DARK
