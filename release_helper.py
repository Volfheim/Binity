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
        "tag": "v3.2.1",
        "prev": "v3.2.0",
        "name": "Binity v3.2.1",
        "body": """## 🛠️ UX Improvements (v3.2.1)
Hotfix release improving the Auto-Updater user experience.

### improvements
- **User Feedback**: "Check for updates" now displays an immediate "Checking..." notification.
- **Dialogs**: "No updates found" and errors are now shown in a dialog box instead of a transient notification, ensuring you don't miss the result.

### 📝 Notes
- Release to ensure users have the best updater experience out-of-the-box.
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
