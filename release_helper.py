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
        "tag": "v3.3.7",
        "prev": "v3.3.6",
        "name": "Binity v3.3.7",
        "body": """## ⚙️ Settings & Updates (v3.3.7)
Reorganized settings menu and improved update checking.

### ✨ Features
- **Settings**: Added \"Windows\" submenu grouping autostart, overflow notification, and theme sync settings.
- **Updates**: App now checks for updates on every launch (with 24h cooldown for background rechecks).

### 🔧 Improvements
- **UX**: Cleaner settings menu layout with logical grouping.
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
