"""Opt-in Windows packaging test; never operates on the installed user's Binity.

Usage: python tests/packaged_update_smoke.py --candidate path/to/Binity.exe
Requires the build dependencies. Builds a one-file driver with the unchanged
v3.3.7 updater and the current updater, then installs the real candidate EXE.
This tests the legacy update engine, not clicks in the legacy application's UI.
"""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

import psutil

ROOT = Path(__file__).resolve().parents[1]

DRIVER = r'''
import json
import os
from pathlib import Path
import sys
import traceback

import legacy_updater
from src.core import updater as current_updater

root = Path(os.environ["BINITY_SMOKE_ROOT"])
mode = os.environ["BINITY_SMOKE_MODE"]
module = legacy_updater if mode.startswith("legacy") else current_updater
module.__version__ = "3.3.7" if mode.startswith("legacy") else "0.0.0"
module.GITHUB_API_LATEST = os.environ["BINITY_SMOKE_API"]

class Settings(dict):
    def set(self, key, value):
        self[key] = value

result = {"mode": mode, "pid": os.getpid(), "bootloader_pid": os.getppid()}
try:
    service = module.Updater(Settings())
    assert service.check_for_update(force=True), service.last_error
    payload = service.download_update()
    assert payload, service.last_error
    if mode.endswith("missing-archive"):
        archive = Path(sys._MEIPASS) / "base_library.zip"
        archive.rename(archive.with_suffix(".withheld"))
    result["scheduled"] = service.apply_update(payload)
    result["error"] = service.last_error
except Exception:
    result["exception"] = traceback.format_exc()
(root / "driver-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
'''


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def wait_until(check, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    raise TimeoutError("Packaged smoke condition not met")


def matching_processes(path):
    expected = str(path.resolve()).casefold()
    return [p for p in psutil.process_iter(["exe", "pid", "ppid"])
            if (p.info["exe"] or "").casefold() == expected]


def stop_fixture(path):
    processes = matching_processes(path)
    parents = {p.pid for p in processes}
    # Terminate the fixture's Python child first, letting its bootloader clean up.
    for p in processes:
        if p.info["ppid"] in parents:
            try:
                p.terminate()
            except psutil.NoSuchProcess:
                pass
    _, alive = psutil.wait_procs(processes, timeout=5)
    for p in alive:
        try:
            if (p.exe() or "").casefold() == str(path.resolve()).casefold():
                p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve(strict=True)
    assert os.name == "nt"
    from src.version import __version__

    output = ROOT / "build" / ("packaged-smoke-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    legacy = subprocess.check_output(["git", "show", "v3.3.7:src/core/updater.py"], cwd=ROOT)
    (output / "legacy_updater.py").write_bytes(legacy)
    (output / "driver.py").write_text(DRIVER, encoding="utf-8")
    with (output / "build.log").open("wb") as log:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                        "--onefile", "--noconsole", "--name", "Binity",
                        "--paths", str(ROOT), "--specpath", str(output),
                        "--distpath", str(output / "dist"), "--workpath", str(output / "work"),
                        str(output / "driver.py")], cwd=ROOT, check=True, stdout=log, stderr=log)
    candidate_hash = digest(candidate)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == "/latest":
                body = json.dumps({"tag_name": "v" + __version__, "draft": False,
                    "prerelease": False, "body": "Isolated package test", "assets": [{
                        "name": "Binity.exe", "size": candidate.stat().st_size,
                        "digest": "sha256:" + candidate_hash,
                        "browser_download_url": endpoint + "/Binity.exe"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/Binity.exe":
                self.send_response(200)
                self.send_header("Content-Length", str(candidate.stat().st_size))
                self.end_headers()
                with candidate.open("rb") as stream:
                    shutil.copyfileobj(stream, self.wfile)
            else:
                self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    endpoint = "http://127.0.0.1:" + str(server.server_port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = {"candidate_sha256": candidate_hash, "legacy_updater_sha256":
               hashlib.sha256(legacy).hexdigest(), "cases": []}
    print("Evidence:", output, flush=True)
    try:
        for mode in ("startup", "legacy", "current", "current-missing-archive", "legacy-missing-archive"):
            case = output / mode
            case.mkdir()
            # Legacy batch has known non-CP866 limitations; new helper gets Unicode paths.
            installation = case if mode.startswith("legacy") else case / "\u0411\u0438\u043d\u0438\u0442\u0438 & [test] %value% ' \u6d4b\u8bd5"
            installation.mkdir(exist_ok=True)
            installed = installation / "Binity.exe"
            shutil.copy2(candidate if mode == "startup" else output / "dist" / "Binity.exe", installed)
            roaming, local, temporary = case / "roaming", case / "local", case / "temp"
            for folder in (roaming / "Binity", local, temporary):
                folder.mkdir(parents=True)
            (roaming / "Binity" / "settings.json").write_text(json.dumps({
                "language": "EN", "auto_check_updates": False, "clear_sound": "off",
                "overflow_notify_enabled": False}), encoding="utf-8")
            env = dict(os.environ, APPDATA=str(roaming), LOCALAPPDATA=str(local),
                TEMP=str(temporary), TMP=str(temporary), QT_QPA_PLATFORM="offscreen",
                PYINSTALLER_RESET_ENVIRONMENT="1", BINITY_SMOKE_ROOT=str(case),
                BINITY_SMOKE_MODE=mode, BINITY_SMOKE_API=endpoint + "/latest")
            env = {k: v for k, v in env.items() if not k.upper().startswith("_PYI_") and k.upper() != "_MEIPASS2"}
            ready = case / "startup-ready.flag"
            command = [str(installed)]
            if mode == "startup":
                command += ["--update-ready-flag", str(ready)]
            process = subprocess.Popen(command, env=env, cwd=installation,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                if mode == "startup":
                    wait_until(ready.is_file)
                else:
                    result_file = case / "driver-result.json"
                    wait_until(result_file.is_file)
                    result = json.loads(result_file.read_text())
                    if mode == "legacy-missing-archive":
                        assert not result.get("scheduled"), result
                        assert "base_library.zip" in result.get("error", ""), result
                        process.wait(timeout=15)
                        results["cases"].append({"mode": mode, "expected_failure": result["error"]})
                        print(mode, "EXPECTED MISSING-ARCHIVE FAILURE", flush=True)
                        continue
                    assert result.get("scheduled"), result
                    process.wait(timeout=30)
                    wait_until((local / "Binity" / "updates" / "applied.flag").is_file)
                    assert digest(installed) == candidate_hash
                    assert not list((local / "Binity" / "updates").glob("next-*.exe"))
                assert matching_processes(installed), "New EXE is not running at the installed path"
                assert not (local / "Binity" / "crash.log").exists(), "Application crash log created"
                results["cases"].append({"mode": mode, "installed_sha256": digest(installed), "startup_ack": True})
                print(mode, "PASS", flush=True)
            finally:
                stop_fixture(installed)
    finally:
        server.shutdown()
        server.server_close()
        (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
