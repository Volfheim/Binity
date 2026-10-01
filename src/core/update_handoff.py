"""Windows update helper. Paths are JSON data, never shell source code."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from subprocess import Popen


POWERSHELL_FUNCTIONS = r'''
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Write-UpdateLog($c, [string]$message) {
    try { [IO.File]::AppendAllText($c.Log, "$(Get-Date -Format o) $message`r`n", $utf8) } catch {}
}

function Start-UpdateTarget($c, [string]$target) {
    if ([IO.File]::Exists($c.Ready)) { [IO.File]::Delete($c.Ready) }
    # Write before starting: the new process consumes this during construction.
    [IO.File]::WriteAllLines($c.LaunchInfo, @("RUN_TARGET=$target", "FINAL=$($c.Final)"), $utf8)
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $target
    $start.Arguments = '--show-after-update --update-ready-flag "' + $c.Ready + '"'
    $start.WorkingDirectory = [IO.Path]::GetDirectoryName($target)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    # A one-file PyInstaller child must unpack independently from the updater.
    $start.EnvironmentVariables['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    foreach ($name in @('_MEIPASS2', '_PYI_APPLICATION_HOME_DIR', '_PYI_ARCHIVE_FILE',
                        '_PYI_PARENT_PROCESS_LEVEL', '_PYI_SPLASH_IPC')) {
        $start.EnvironmentVariables.Remove($name)
    }
    $process = [Diagnostics.Process]::Start($start)
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(60)
        while ([DateTime]::UtcNow -lt $deadline) {
            if ([IO.File]::Exists($c.Ready)) { return $true }
            if ($process.HasExited) { return $false }
            Start-Sleep -Milliseconds 250
        }
        # A slow process must not be duplicated or killed just for missing an ACK.
        throw 'New process is still running but did not report readiness. Files retained.'
    } finally { $process.Dispose() }
}

function Install-UpdatePayload($c) {
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        try {
            [IO.File]::Copy($c.Downloaded, $c.Candidate, $true)
            if ((Get-FileHash -LiteralPath $c.Candidate -Algorithm SHA256).Hash -ne $c.Digest) {
                throw 'Staged copy SHA-256 mismatch'
            }
            if ([IO.File]::Exists($c.Final)) {
                [IO.File]::Replace($c.Candidate, $c.Final, $c.Backup)
            } else {
                [IO.File]::Move($c.Candidate, $c.Final)
            }
            return $true
        } catch {
            Write-UpdateLog $c "Replacement attempt $($attempt + 1): $_"
            if ($attempt -lt 7) { Start-Sleep -Milliseconds 500 }
        }
    }
    return $false
}

function Wait-ForBinityExit($c, [int]$pid, [string]$label) {
    if ($pid -le 0) { return }
    $process = $null
    try { $process = [Diagnostics.Process]::GetProcessById($pid) }
    catch [ArgumentException] { return }
    try {
        if (-not $process.WaitForExit(30000)) {
            throw "$label is still running; update aborted without killing it"
        }
    } finally { $process.Dispose() }
}

function Invoke-BinityUpdate($c) {
    if (-not [IO.File]::Exists($c.Downloaded)) { throw 'Downloaded file missing' }
    if ((Get-FileHash -LiteralPath $c.Downloaded -Algorithm SHA256).Hash -ne $c.Digest) {
        throw 'Downloaded file changed before handoff'
    }
    Write-UpdateLog $c 'Helper ready; waiting for the application to exit'
    [IO.File]::WriteAllText($c.HelperReady, 'ready', $utf8)
    Wait-ForBinityExit $c ([int]$c.ParentPid) 'Application process'
    # PyInstaller one-file mode has an outer bootloader process that owns the
    # extraction directory and executable handle after the Python child exits.
    Wait-ForBinityExit $c ([int]$c.BootloaderPid) 'PyInstaller bootloader'

    $target = $c.Downloaded
    if (Install-UpdatePayload $c) { $target = $c.Final }
    else { Write-UpdateLog $c 'Replacement failed; starting the retained staging copy' }

    $ready = $false
    try { $ready = Start-UpdateTarget $c $target }
    catch {
        # Do not launch a second copy if startup timed out while it is alive.
        Write-UpdateLog $c "Startup error: $_"
        throw
    }
    if (-not $ready -and $target -ne $c.Downloaded) {
        Write-UpdateLog $c 'Final process exited before readiness; trying staging copy'
        $target = $c.Downloaded
        $ready = Start-UpdateTarget $c $target
    }
    if (-not $ready) { throw 'No startup acknowledgement; staging and backup retained' }

    if ($target -eq $c.Final) {
        foreach ($file in @($c.Downloaded, $c.Candidate, $c.Backup)) {
            try { if ([IO.File]::Exists($file)) { [IO.File]::Delete($file) } } catch {}
        }
    }
    [IO.File]::WriteAllText($c.Flag, '1', $utf8)
    try {
        $handoff = [IO.Path]::GetDirectoryName($c.Ready)
        if ([IO.Directory]::Exists($handoff)) { [IO.Directory]::Delete($handoff, $true) }
    } catch {}
    Write-UpdateLog $c "Startup acknowledged: $target"
}
'''

POWERSHELL_SCRIPT = POWERSHELL_FUNCTIONS + r'''
$config = $null
try {
    $config = $env:BINITY_UPDATE_CONFIG | ConvertFrom-Json
    Invoke-BinityUpdate $config
    exit 0
} catch {
    if ($null -ne $config) { Write-UpdateLog $config "Update failed: $_" }
    exit 1
}
'''


def encoded_command(script: str = POWERSHELL_SCRIPT) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def wait_for_helper(process: Popen, ready_file: Path, timeout_sec: float = 15) -> None:
    """Fail before quitting Binity if PowerShell cannot initialize the helper."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise RuntimeError(f"Update helper exited before handoff (code {code}). See updates/update.log")
        if ready_file.is_file():
            return
        time.sleep(0.05)
    # This is only our newly spawned helper, still waiting for the parent.
    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError("Update helper initialization timed out; application left running")
