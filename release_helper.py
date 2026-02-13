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
        "tag": "v3.3.1",
        "prev": "v3.3.0",
        "name": "Binity v3.3.1",
        "body": """## 🛠️ Updater Stability & UI Polish (v3.3.1)
Update focused on making the auto-updater rock solid and improving visual consistency.

### 🔄 Updater Improvements
- **Robustness**: Updater script now has fallback mechanisms. If replacing the EXE fails (e.g. locked file), it runs from a staging area to ensure the app still launches.
- **Fail-Safe**: New handshake system ensures the new version started successfully; otherwise, it reverts or retries.
- **Visibility**: Added a progress bar dialog during download so you know what's happening.
- **Logs**: Updater now writes to `update.log` in the local app data folder for easier troubleshooting.

### 🎨 UI & Polish
- **Icons**: Fixed missing icons in dialogs (e.g. "Already running", "Confirm Delete") to ensure no empty window headers.
- **Release Notes**: Cleaned up the "What's New" text in the update dialog to remove raw Markdown symbols (###, **) for a cleaner look.

### 📝 Notes
- This release ensures seamless updates for future versions.
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
    
    for release_info in RELEASES:
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
