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
BUILD_CMD = 'pyinstaller --noconsole --onefile --icon=icons/bin_full.ico --add-data "icons;icons" --name "Binity" main.py'

RELEASES = [
    {
        "tag": "v3.0.0",
        "prev": "v2.9.0",
        "name": "Binity v3.0.0",
        "body": r"""## 🚀 Complete Rewrite (v3.0.0)
Major update introducing a new modular architecture and modern UI.

### ✨ Features
- **Architecture**: Rewrite from scratch using **PyQt6** and modular design (`src/`).
- **Settings**: Configuration migrated to JSON (`%APPDATA%\Binity\settings.json`).
- **UI**: Modern Windows 11 style dialogs and enhanced tray menu.
- **Stability**: Added Single Instance Lock and improved error handling.

### 📝 Notes
- Previous registry settings are automatically migrated.
- Requires Windows 10/11.
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
    
    # Try to cleanup
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
        cmd = "pyinstaller Binity.spec"
    else:
        print("    Using default command...")
        cmd = BUILD_CMD

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError:
        print("  Build failed!")
        return None
    exe_path = os.path.join("dist", "Binity.exe")
    # Some specs might output to dist/Binity/Binity.exe or similar, check logic
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
            body += f"\n**Full Changelog**: {link}"

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
