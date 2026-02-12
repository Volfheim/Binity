import json
import os
import sys
import urllib.request
import urllib.error
import subprocess
import shutil

# --- CONFIGURATION ---
REPO = "Volfheim/Binity"
BUILD_CMD = 'pyinstaller --noconsole --onefile --icon=icons/bin_full.ico --add-data "icons;icons" --name "Binity" main.py'

# Validating user request:
# Title: "Binity vX.X.X"
# Body Header: "## 💎 Descriptive Title (vX.X.X)"
# Footer: "Full Changelog: url..."

RELEASES = [
    {
        "tag": "v1.2.0",
        "prev": None,
        "name": "Binity v1.2.0",
        "body": """## 🐣 MVP Release (v1.2.0)
First working version of Binity.
*Dev Period: Summer 2025*

### ✨ Features
- **Core**: Open and Empty Recycle Bin from system tray.
- **UI**: Simple context menu integration.

### 📝 Note
- Basic Windows 10 style interface.
"""
    },
    {
        "tag": "v1.6.0",
        "prev": "v1.2.0",
        "name": "Binity v1.6.0",
        "body": """## ✨ Visual Update (v1.6.0)
Added visual indicators for bin status.

### 💄 UI Polish
- **Live Icon**: Added 5 icon levels (0, 25, 50, 75, 100%) to reflect bin status.
- **Settings**: Configuration via Registry integration.
- **Safety**: Added confirmation dialog before emptying.
"""
    },
    {
        "tag": "v1.9.0",
        "prev": "v1.6.0",
        "name": "Binity v1.9.0",
        "body": """## 🌍 Localization Update (v1.9.0)
Support for multiple languages.

### ✨ Features
- **Localization**: Added English and Russian language support.
- **About Window**: New information window with version details.
- **Refactoring**: Code structure improvements.
"""
    },
    {
        "tag": "v2.5.0",
        "prev": "v1.9.0",
        "name": "Binity v2.5.0",
        "body": """## 🛡️ Stability Update (v2.5.0)
Technical update focused on reliability and debugging.

### 🐛 Fixes
- **Error Handling**: Improved resilience against system errors.
- **Logging**: Added `binity.log` for troubleshooting.
- **Tray**: Optimized tray icon behavior.
"""
    },
    {
        "tag": "v2.6.0",
        "prev": "v2.5.0",
        "name": "Binity v2.6.0",
        "body": """## 🔧 Hotfix (v2.6.0)
Maintenance update.

### 🐛 Fixes
- **Initialization**: Fixed bugs during app startup.
- **Resources**: Optimized icon loading process.
"""
    },
    {
        "tag": "v2.9.0",
        "prev": "v2.6.0",
        "name": "Binity v2.9.0",
        "body": """## 💎 Final Polish (v2.9.0)
Final version with complete feature set.

### ✨ Features
- **Live Icon**: 5 dynamic icon levels.
- **Autostart**: Automatic Windows startup integration.
- **Modern UI**: Updated confirmation dialogs (Windows 10/11 style).
- **Tribute**: Added credits to original MiniBin author.

### 🚀 Verification
- Tested on Windows 10 & 11.
- High DPI support confirmed.
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
    if os.path.exists("dist"): shutil.rmtree("dist")
    if os.path.exists("build"): shutil.rmtree("build")
    try:
        subprocess.check_call(BUILD_CMD, shell=True)
    except subprocess.CalledProcessError:
        print("  Build failed!")
        return None
    exe_path = os.path.join("dist", "Binity.exe")
    if os.path.exists(exe_path): return exe_path
    return None

def process_releases():
    subprocess.call("git checkout main", shell=True)
    
    for release_info in RELEASES:
        tag = release_info["tag"]
        prev = release_info["prev"]
        print(f"\nProcessing {tag}...")

        # Construct Full Changelog link
        body = release_info["body"]
        if prev:
            link = f"https://github.com/{REPO}/compare/{prev}...{tag}"
            body += f"\n**Full Changelog**: {link}"
        else:
            # First release
            body += f"\n**Full Changelog**: https://github.com/{REPO}/commits/{tag}"

        # 1. DELETE EXISTING
        try:
            existing = request(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
            print(f"  Deleting existing release {existing['id']}...")
            request(existing['url'], method="DELETE")
        except urllib.error.HTTPError as e:
            if e.code != 404: print(f"  Error checking release: {e}")

        # 2. CHECKOUT TAG
        subprocess.check_call(f"git checkout {tag}", shell=True)
        
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
