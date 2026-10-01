import json
import os
import sys
import urllib.request
import urllib.error
import subprocess
import shutil
import time

# --- CONFIGURATION ---
REPO = "Volfheim/Binity"
BUILD_CMD = 'pyinstaller --noconsole --onefile --icon=icons/bin_full.ico --add-data "icons;icons" --add-data "sounds;sounds" --name "Binity" main.py'

RELEASES = [
    {
        "tag": "v3.3.11",
        "prev": "v3.3.10",
        "name": "Binity v3.3.11",
        "body": """## English
This hotfix restores the original v3.3.7 icon artwork. Experimental icons were unintentionally included with the architecture changes in v3.3.8 through v3.3.10.

### Fixes
- Restored all five original ICO files byte-for-byte, including their transparency and fill-level colors.
- The tray, About window, and EXE icon use the original artwork in both Windows themes.
- Experimental light/dark SVG bin icons are excluded from the packaged application.
- All updater and Windows packaging fixes from v3.3.10 are retained.

### Verification
- Added regression checks for the original icon hashes and rendering at small tray sizes in both themes.
- Checked the icons inside the packaged EXE, including its native Windows icon resources.
- Verified EXE startup and the packaged update path on Windows 11. Test code is not included in the EXE.

### Compatibility
- Windows 10 version 1809+ and Windows 11 x64 remain the target platforms. Windows 10 has not been runtime-tested for this release.
- Updates are delivered through the existing in-app updater. No separate launcher or .NET installation is required.

## Русский
Этот корректирующий выпуск возвращает оригинальные иконки из v3.3.7. Экспериментальные иконки непреднамеренно попали в версии v3.3.8–v3.3.10 вместе с архитектурными изменениями.

### Исправления
- Все пять оригинальных ICO восстановлены побайтово, включая прозрачность и цвета уровней заполнения.
- Трей, окно «О программе» и значок EXE используют оригинальное оформление в обеих темах Windows.
- Экспериментальные светлые и тёмные SVG-иконки корзины исключены из сборки приложения.
- Все исправления обновления и сборки для Windows из v3.3.10 сохранены.

### Проверка
- Добавлены регрессионные проверки хешей оригинальных иконок и отрисовки в малых размерах трея в обеих темах.
- Проверены иконки внутри собранного EXE, включая его нативные ресурсы значка Windows.
- Проверены запуск EXE и путь обновления упакованной программы на Windows 11. Код тестов не входит в EXE.

### Совместимость
- Целевыми платформами остаются Windows 10 версии 1809+ и Windows 11 x64. Проверка запуска этого релиза на Windows 10 не проводилась.
- Обновление устанавливается через существующий механизм внутри программы. Отдельный launcher и установка .NET не требуются.
"""
    },
    {
        "tag": "v3.3.10",
        "prev": "v3.3.9",
        "name": "Binity v3.3.10",
        "body": """## English
This maintenance release repairs the Windows update helper while keeping Binity a single portable EXE. The interface and tray icons are unchanged.

### Fixes
- Isolated DLL discovery during packaging so unrelated tools on the build machine cannot shadow Windows ICU and prevent Qt from starting.
- Fixed the PowerShell process-ID parameter conflict that stopped update installation.
- Removed the helper's dependency on `Get-FileHash` module discovery and loaded the command encoding at application startup.
- Check destination write access and copy integrity before closing Binity.
- Replace the EXE at its existing path. If the new process exits before confirming startup, restore and restart the previous version instead of launching from the download folder.
- Preserve recovery files on a startup timeout without killing a running process or launching a duplicate.

### Verification
- Added execution-level Windows PowerShell regression tests for Unicode paths, process waiting, integrity checks, installation failures, and rollback.
- Verified EXE startup on Windows 11 and installation of this EXE by the unchanged v3.3.7 updater in an isolated packaged test (not UI automation of the old release).
- Verified the current updater with and without its temporary Python archive; reproduced the old updater's missing-archive failure separately.
- Test code is not included in the application EXE.

### Compatibility
- Windows 10 version 1809+ and Windows 11 x64 remain the target platforms. No separate launcher or .NET installation is required.
- Windows 10 has not been runtime-tested for this release.
- If an older running copy reports a missing `_MEI/base_library.zip`, exit and reopen that same copy before retrying the update. The downloaded version cannot repair an old process that fails before launching it.

## Русский
Этот корректирующий выпуск исправляет Windows-helper обновления, сохраняя Binity в виде одного portable EXE. Интерфейс и значки трея не изменены.

### Исправления
- Изолирован поиск DLL при сборке: библиотеки посторонних инструментов больше не подменяют Windows ICU и не мешают запуску Qt.
- Устранён конфликт параметра идентификатора процесса PowerShell, который останавливал установку обновления.
- Убрана зависимость helper от поиска модуля `Get-FileHash`; кодировка команды загружается при старте приложения.
- Возможность записи в папку назначения и целостность копии проверяются до закрытия Binity.
- EXE заменяется по прежнему пути. Если новый процесс завершился до подтверждения запуска, восстанавливается и запускается предыдущая версия вместо копии из папки загрузки.
- При таймауте запуска сохраняются файлы для восстановления, без принудительного завершения работающего процесса и запуска дубликата.

### Проверка
- Добавлены регрессионные тесты с исполнением Windows PowerShell для Unicode-путей, ожидания процессов, проверки целостности, ошибок установки и отката.
- Проверены запуск EXE на Windows 11 и установка этого EXE неизменённым updater из v3.3.7 в изолированном упакованном тесте (не автоматизация интерфейса старого релиза).
- Проверен текущий updater с временным Python-архивом и без него; отдельно воспроизведён сбой старого updater при отсутствии архива.
- Код тестов не входит в EXE приложения.

### Совместимость
- Целевыми платформами остаются Windows 10 версии 1809+ и Windows 11 x64. Отдельный launcher и установка .NET не требуются.
- Проверка запуска этого релиза на Windows 10 не проводилась.
- Если старая запущенная копия сообщает об отсутствии `_MEI/base_library.zip`, выйдите из неё и запустите ту же копию перед повторной попыткой обновления. Скачанная версия не может исправить старый процесс, который падает до её запуска.
"""
    },
    {
        "tag": "v3.3.9",
        "prev": "v3.3.8",
        "name": "Binity v3.3.9",
        "body": """## 🛠️ Update Handoff Fix (v3.3.9)
Исправлена ошибка запуска новой версии после обновления one-file EXE.

### ✨ Changes
- **PyInstaller**: Новый процесс получает независимое окружение и не переиспользует временную папку старого процесса.
- **Windows**: Перед handoff сбрасывается DLL-directory старого `_MEI`-каталога.
- **Надёжность**: Updater дожидается завершения Python-процесса и внешнего PyInstaller bootloader.

### 📝 Notes
- **Compatibility**: Windows 10 version 1809+ and Windows 11 x64.
- **Безопасность**: Обновление не завершает зависшие процессы принудительно; при проблеме файлы сохраняются для диагностики.

## 🇬🇧 English
The release fixes startup of the new one-file EXE after an update.
"""
    },
    {
        "tag": "v3.3.6",
        "prev": "v3.3.5",
        "name": "Binity v3.3.6",
        "body": """## 🛠️ Code Refactoring & Stability (v3.3.6)
Internal code cleanup and improved crash resilience.

### 🔧 Improvements
- **Stability**: Added global crash handler — unhandled exceptions are now logged to `crash.log` instead of silently terminating the app.
- **Code**: Refactored settings, updater, and sound service internals for cleaner structure and reduced redundancy.
- **Code**: Simplified property accessors and consolidated repetitive logic patterns.
"""
    },
    {
        "tag": "v3.3.5",
        "prev": "v3.3.4",
        "name": "Binity v3.3.5",
        "body": """## 📐 UI Tweak (v3.3.5)
More compact update dialog.

### 🖼️ Changes
- **UI**: Reduced the width of the update prompt to remove excess empty space.
"""
    },
    {
        "tag": "v3.3.4",
        "prev": "v3.3.3",
        "name": "Binity v3.3.4",
        "body": """## ⌨️ UX Improvements (v3.3.4)
Better keyboard navigation and text formatting.

### ✨ Features
- **UX**: Pressing Enter in the "Confirm Clear" dialog now confirms the action (focus is on "Clear" button).
- **UI**: Improved release notes formatting (better Markdown stripping).
"""
    },
    {
        "tag": "v3.3.3",
        "prev": "v3.3.2",
        "name": "Binity v3.3.3",
        "body": """## 🛠️ UI Polish & Sound Fix (v3.3.3)
Fixes for update dialog resizing and sound packaging.

### 🐛 Fixes
- **UI**: Normalized update dialog size (was too wide) and increased progress bar size.
- **Sound**: Fixed packaging issue where the new "Throw in trash" sound was missing in the release.
"""
    },
    {
        "tag": "v3.3.2",
        "prev": "v3.3.1",
        "name": "Binity v3.3.2",
        "body": """## 🔊 New Sound (v3.3.2)
Minor update adding a new sound effect.

### 🔊 Features
- **Sound**: Added a new "Throw in trash" sound effect.

### 📝 Notes
- Enjoy the satisfying sound of cleaning up!
"""
    },
    {
        "tag": "v3.3.1",
        "prev": "v3.3.0",
        "name": "Binity v3.3.1",
        "body": """## 🚀 Updater Stability (v3.3.1)
Major reliability improvements for the auto-updater and UI polish.

### 🔄 Updater
- **Robustness**: Increased download timeouts (180s) and added retry logic to prevent failures on slow connections.
- **Fallbacks**: If replacing the file fails, the app now launches from a temporary location and notifies the user.
- **UI**: Added a wider update dialog and explicit progress bar for downloads.

### 🐛 Fixes
- **Icons**: Fixed missing icons in "Already running" and confirmation dialogs.
- **Notes**: Cleaner release notes display (removed raw Markdown).
"""
    },

    {
        "tag": "v3.3.0",
        "prev": "v3.2.1",
        "name": "Binity v3.3.0",
        "body": """## 🛡️ Secure Delete (Best Effort) & UX (v3.3.0)
Major update introducing privacy-focused deletion features and enhanced settings.

### 🔥 New Features
- **🛡️ Secure Delete**:
  - Added "Secure Delete" modes in Settings: **1-pass zeros** and **1-pass random data**.
  - **Best Effort**: Attempts to overwrite file content before deletion.
  - **Payload Protection**: Strictly wipes only files within `$Recycle.Bin` matching specific patterns (`$R...`), ensuring safety of other data.
  - **Feedback**: Detailed notifications about how many files were successfully overwritten and if any were locked.
- **Improved UX**:
  - **Confirmation Dialogs**: Now clearly state which mode is active (Normal vs Secure) and warn about disk load.
  - **Warnings**: One-time warning when enabling secure mode about SSD wear and limitations.

### 🛠️ Improvements
- **Tests**: Added unit tests for secure deletion logic and settings normalization.
- **I18n**: Fully localized (RU/EN) for all new dialogs and menus.

### 📝 Notes
- **SSD Users**: Please note that due to hardware wear leveling, absolute secure deletion cannot be guaranteed on modern SSDs/NVMe drives without full disk encryption/sanitization. Binity does its best to overwrite data at the OS level.
"""
    }
]

def get_token():
    token = os.environ.get("GH_TOKEN")
    if token: return token
    try:
        input_data = "protocol=https\nhost=github.com\n"
        process = subprocess.Popen(["git", "credential", "fill"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, _ = process.communicate(input=input_data)
        if process.returncode == 0:
            for line in stdout.splitlines():
                if line.startswith("password="): return line.split("=", 1)[1]
    except: pass
    return None

TOKEN = get_token()
if not TOKEN:
    print("Error: No GitHub Token found.")
    sys.exit(1)

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

def request(url, method="GET", data=None, content_type="application/json"):
    if data and content_type == "application/json": data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": content_type}, method=method)
    try:
        with urllib.request.urlopen(req) as f:
            if method == "DELETE": return None
            return json.load(f)
    except urllib.error.HTTPError as e:
        print(f"Request failed: {e.code} {e.reason}")
        try: print(e.read().decode())
        except: pass
        raise

def build_exe():
    print("  Building EXE...")
    
    for _ in range(3):
        try:
            if os.path.exists("dist"): shutil.rmtree("dist")
            if os.path.exists("build"): shutil.rmtree("build")
            break
        except Exception as e:
            print(f"    Cleanup warning: {e}. Retrying...")
            time.sleep(1)

    if os.path.exists("Binity.spec"):
        print("    Using Binity.spec...")
        cmd = "pyinstaller --clean --noconfirm Binity.spec"
    else:
        print("    Using default command...")
        cmd = BUILD_CMD

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError:
        print("  Build failed!")
        return None
    exe_path = os.path.join("dist", "Binity.exe")
    if os.path.exists(exe_path): return exe_path
    return None

def process_releases():
    subprocess.call("git checkout main", shell=True)
    
    for release_info in RELEASES[:1]:
        tag = release_info["tag"]
        prev = release_info["prev"]
        print(f"\nProcessing {tag}...")

        body = release_info["body"]
        if prev:
            link = f"https://github.com/{REPO}/compare/{prev}...{tag}"
            body += f"\n\n**Full Changelog**: {link}"

        # 1. DELETE EXISTING RELEASE (if any, for idempotency)
        try:
            existing = request(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
            print(f"  Deleting existing release {existing['id']}...")
            request(existing['url'], method="DELETE")
        except urllib.error.HTTPError as e:
            if e.code != 404: print(f"  Error checking release: {e}")

        # 2. TAGGING IS ASSUMED DONE OR WE ARE ON HEAD
        # For this workflow, we will build from CURRENT HEAD which should be tagged.
        
        # 3. BUILD EXE
        exe_path = build_exe()
        if not exe_path: pass

        # 4. CREATE RELEASE
        print(f"  Creating release {tag}...")
        release = request(
            f"https://api.github.com/repos/{REPO}/releases",
            method="POST",
            data={
                "tag_name": tag,
                "target_commitish": "main",
                "name": release_info["name"],
                "body": body,
                "draft": False,
                "prerelease": False
            }
        )
        print(f"  Release created: {release['html_url']}")

        # 5. UPLOAD ASSET
        if exe_path:
            print(f"  Uploading Binity.exe...")
            upload_url = release['upload_url'].replace("{?name,label}", f"?name=Binity.exe")
            with open(exe_path, 'rb') as f:
                file_content = f.read()
            req = urllib.request.Request(
                upload_url, 
                data=file_content, 
                headers={**headers, "Content-Type": "application/vnd.microsoft.portable-executable"}, 
                method="POST"
            )
            try:
                with urllib.request.urlopen(req): print("  Asset uploaded!")
            except Exception as e: print(f"  Upload failed: {e}")

    subprocess.call("git checkout main", shell=True)

if __name__ == "__main__":
    process_releases()
