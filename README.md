# Binity ⚡
**Binity** — fast and elegant recycle bin manager for Windows system tray.

![Version](https://img.shields.io/github/v/release/Volfheim/Binity)
![License](https://img.shields.io/github/license/Volfheim/Binity)
![Platform](https://img.shields.io/badge/platform-Windows-blue)

**Binity** brings the recycle bin to your system tray. Check fullness at a glance and empty it without minimizing windows. Inspired by the legendary MiniBin.

![Binity Icon](icons/bin_full.ico)

## ✨ Features
*   **📊 Live Icon**: 5 dynamic levels (0%, 25%, 50%, 75%, 100%) reflect bin status immediately.
*   **🛡️ Safe**: Confirmation dialogs (modern Windows 11 style) prevent accidental clicks.
*   **🚀 Autostart**: Optional integration with Windows startup.
*   **🌍 Modern**: Written in Python, fully localized (EN/RU), and optimized for High DPI.

## 📦 Download
Download the latest version from **[GitHub Releases](https://github.com/Volfheim/Binity/releases)**.

## 🏗 Build
To build from source, you need Python 3.10+.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build EXE (requires PyInstaller)
pyinstaller --noconsole --onefile --icon=icons/bin_full.ico --add-data "icons;icons" --name "Binity" main.py
```

## 📝 Changelog
All notable changes are documented in **[Releases](https://github.com/Volfheim/Binity/releases)**.

## 💡 Tribute
Inspired by **MiniBin** (by Mike Edward Moras / e-sushi).
*Binity is a modern, open-source re-imagining of the original concept.*

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.