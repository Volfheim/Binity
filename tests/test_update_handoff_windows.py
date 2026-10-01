"""Execute the actual Windows PowerShell helper against isolated local fixtures."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from src.core.update_handoff import POWERSHELL_FUNCTIONS, POWERSHELL_SCRIPT, encoded_command


POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
    "System32/WindowsPowerShell/v1.0/powershell.exe"
)


@unittest.skipUnless(os.name == "nt" and POWERSHELL.is_file(), "Windows PowerShell required")
class WindowsHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "space & quote' %value% [test] \u0411\u0438\u043d\u0438\u0442\u0438 \u6d4b\u8bd5"
        self.root.mkdir()
        self.handoff = self.root / "handoff"
        self.handoff.mkdir()
        self.old = b"original executable fixture"
        self.new = b"updated executable fixture"
        self.config = {
            "ParentPid": 0, "BootloaderPid": 0,
            "Downloaded": str(self.root / "next-Binity.exe"),
            "Final": str(self.root / "Binity.exe"),
            "Candidate": str(self.root / ".Binity.new"),
            "Backup": str(self.root / ".Binity.bak"),
            "Ready": str(self.handoff / "app-ready.flag"),
            "HelperReady": str(self.handoff / "helper-ready.flag"),
            "Flag": str(self.root / "applied.flag"),
            "LaunchInfo": str(self.root / "launch-info.txt"),
            "Log": str(self.root / "update.log"),
            "Digest": hashlib.sha256(self.new).hexdigest(),
        }
        Path(self.config["Downloaded"]).write_bytes(self.new)
        Path(self.config["Final"]).write_bytes(self.old)

    def run_script(self, script, expected=0):
        result = subprocess.run(
            [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_command(script)],
            env=dict(os.environ, BINITY_UPDATE_CONFIG=json.dumps(self.config)),
            capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, expected, result.stderr.decode("utf-8", errors="replace"))
        return result

    def run_functions(self, body, overrides="", expected=0):
        return self.run_script(POWERSHELL_FUNCTIONS + overrides + "\n" +
                               "$c = $env:BINITY_UPDATE_CONFIG | ConvertFrom-Json\n" + body, expected)

    def test_pid_parameter_executes_and_waits_for_a_real_process(self):
        # A real child exits on an isolated sentinel, no user process is touched.
        sentinel = self.root / "release-child"
        child = subprocess.Popen([sys.executable, "-c",
            "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); "
            "\nwhile not p.exists(): time.sleep(.05)", str(sentinel)],
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self.config["ParentPid"] = child.pid
            self.config["Sentinel"] = str(sentinel)
            self.run_functions("""
Wait-ForBinityExit $c 0 'No parent'
[IO.File]::WriteAllText($c.Sentinel, 'exit')
Wait-ForBinityExit $c ([int]$c.ParentPid) 'Fixture parent'
Wait-ForBinityExit $c ([int]$c.ParentPid) 'Already exited parent'
""")
            child.wait(timeout=5)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)

    def test_success_replaces_exact_path_and_cleans_backup_after_ack(self):
        self.run_functions("Invoke-BinityUpdate $c", overrides="""
function Start-UpdateTarget($c, [string]$target, [bool]$updated = $true) {
    if ($target -ne $c.Final -or -not $updated) { throw 'Wrong installed target' }
    [IO.File]::WriteAllText($c.Ready, 'ready')
    return $true
}
""")
        self.assertEqual(Path(self.config["Final"]).read_bytes(), self.new)
        self.assertTrue(Path(self.config["Flag"]).exists())
        for name in ("Candidate", "Backup", "Downloaded"):
            self.assertFalse(Path(self.config[name]).exists(), name)

    def test_tampered_download_fails_before_handoff_and_preserves_old_file(self):
        Path(self.config["Downloaded"]).write_bytes(b"tampered")
        self.run_script(POWERSHELL_SCRIPT, expected=1)
        self.assertFalse(Path(self.config["HelperReady"]).exists())
        self.assertEqual(Path(self.config["Final"]).read_bytes(), self.old)

    def test_unwritable_destination_fails_before_acknowledging_handoff(self):
        Path(self.config["Candidate"]).mkdir()
        self.run_script(POWERSHELL_SCRIPT, expected=1)
        self.assertFalse(Path(self.config["HelperReady"]).exists())
        self.assertEqual(Path(self.config["Final"]).read_bytes(), self.old)

    def test_exited_new_version_restores_and_restarts_old_not_staging(self):
        self.run_functions("Invoke-BinityUpdate $c", expected=1, overrides="""
function Start-UpdateTarget($c, [string]$target, [bool]$updated = $true) {
    if ($target -ne $c.Final) { throw 'Must never launch staging' }
    if ($updated) { return $false }
    [IO.File]::WriteAllText($c.LaunchInfo, 'rollback launched')
    return $true
}
""")
        self.assertEqual(Path(self.config["Final"]).read_bytes(), self.old)
        self.assertEqual(Path(self.config["LaunchInfo"]).read_text(), "rollback launched")
        self.assertTrue(Path(self.config["Downloaded"]).exists())
        self.assertFalse(Path(self.config["Flag"]).exists())

    def test_live_startup_timeout_does_not_rollback_or_launch_a_second_copy(self):
        self.run_functions("Invoke-BinityUpdate $c", expected=1, overrides="""
function Start-UpdateTarget($c, [string]$target, [bool]$updated = $true) {
    [IO.File]::AppendAllText($c.LaunchInfo, 'attempt')
    throw 'Fixture is still alive without ACK'
}
""")
        self.assertEqual(Path(self.config["Final"]).read_bytes(), self.new)
        self.assertEqual(Path(self.config["Backup"]).read_bytes(), self.old)
        self.assertEqual(Path(self.config["LaunchInfo"]).read_text(), "attempt")
        self.assertFalse(Path(self.config["Flag"]).exists())

    def test_failed_replacement_restarts_existing_exe_only(self):
        self.run_functions("Invoke-BinityUpdate $c", expected=1, overrides="""
function Install-UpdatePayload($c) { return $false }
function Start-UpdateTarget($c, [string]$target, [bool]$updated = $true) {
    if ($target -ne $c.Final -or $updated) { throw 'Must restart original only' }
    [IO.File]::WriteAllText($c.LaunchInfo, 'original launched')
    return $true
}
""")
        self.assertEqual(Path(self.config["Final"]).read_bytes(), self.old)
        self.assertEqual(Path(self.config["LaunchInfo"]).read_text(), "original launched")
        self.assertTrue(Path(self.config["Downloaded"]).exists())
        self.assertFalse(Path(self.config["Flag"]).exists())

    def test_unlaunchable_executable_returns_failure_for_rollback(self):
        self.run_functions("if (Start-UpdateTarget $c $c.Final) { throw 'Invalid EXE acknowledged' }")
        self.assertFalse(Path(self.config["Ready"]).exists())


if __name__ == "__main__":
    unittest.main()
