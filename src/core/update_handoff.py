"""Windows update helper. Paths are JSON data, never shell source code."""

from __future__ import annotations

import base64
import time
from encodings.utf_16_le import encode as _encode_utf16le
from pathlib import Path
from subprocess import Popen


POWERSHELL_FUNCTIONS = r'''
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Write-UpdateLog($c, [string]$message) {
    try { [IO.File]::AppendAllText($c.Log, "$(Get-Date -Format o) $message`r`n", $utf8) } catch {}
}

function Get-PayloadDigest([string]$path) {
    # Avoid Get-FileHash autoloading from an inherited PowerShell 7 module path.
    $stream = [IO.File]::OpenRead($path)
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '') }
    finally { $hash.Dispose(); $stream.Dispose() }
}

function Start-UpdateTarget($c, [string]$target, [bool]$updated = $true) {
    if ([IO.File]::Exists($c.Ready)) { [IO.File]::Delete($c.Ready) }
    # Write before starting: the new process consumes this during construction.
    [IO.File]::WriteAllLines($c.LaunchInfo, @("RUN_TARGET=$target", "FINAL=$($c.Final)"), $utf8)
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $target
    $start.Arguments = '--update-ready-flag "' + $c.Ready + '"'
    if ($updated) { $start.Arguments = '--show-after-update ' + $start.Arguments }
    $start.WorkingDirectory = [IO.Path]::GetDirectoryName($target)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    # A one-file PyInstaller child must unpack independently from the updater.
    $start.EnvironmentVariables['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    $start.EnvironmentVariables.Remove('BINITY_UPDATE_CONFIG')
    foreach ($name in @('_MEIPASS2', '_PYI_APPLICATION_HOME_DIR', '_PYI_ARCHIVE_FILE',
                        '_PYI_PARENT_PROCESS_LEVEL', '_PYI_SPLASH_IPC')) {
        $start.EnvironmentVariables.Remove($name)
    }
    try { $process = [Diagnostics.Process]::Start($start) }
    catch {
        Write-UpdateLog $c "Could not start target: $_"
        return $false
    }
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

function Prepare-UpdatePayload($c) {
    if (-not [IO.File]::Exists($c.Downloaded)) { throw 'Downloaded file missing' }
    if ((Get-PayloadDigest $c.Downloaded) -ne $c.Digest) {
        throw 'Downloaded file changed before handoff'
    }
    # Check destination write access and copy integrity BEFORE asking Binity to exit.
    [IO.File]::Copy($c.Downloaded, $c.Candidate, $false)
    if ((Get-PayloadDigest $c.Candidate) -ne $c.Digest) {
        throw 'Staged copy SHA-256 mismatch'
    }
}

function Install-UpdatePayload($c) {
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        try {
            if ((Get-PayloadDigest $c.Candidate) -ne $c.Digest) {
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

function Wait-ForBinityExit($c, [int]$processId, [string]$label) {
    if ($processId -le 0) { return }
    $process = $null
    try { $process = [Diagnostics.Process]::GetProcessById($processId) }
    catch [ArgumentException] { return }
    try {
        if (-not $process.WaitForExit(30000)) {
            throw "$label is still running; update aborted without killing it"
        }
    } finally { $process.Dispose() }
}

function Restore-PreviousVersion($c) {
    if (-not [IO.File]::Exists($c.Backup)) { return $false }
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        try {
            if ([IO.File]::Exists($c.Final)) {
                [IO.File]::Replace($c.Backup, $c.Final, $c.Candidate)
            } else {
                [IO.File]::Move($c.Backup, $c.Final)
            }
            Write-UpdateLog $c 'Previous executable restored after startup failure'
            return $true
        } catch {
            Write-UpdateLog $c "Rollback attempt $($attempt + 1): $_"
            if ($attempt -lt 7) { Start-Sleep -Milliseconds 500 }
        }
    }
    return $false
}

function Invoke-BinityUpdate($c) {
    Prepare-UpdatePayload $c
    Write-UpdateLog $c 'Helper ready; waiting for the application to exit'
    [IO.File]::WriteAllText($c.HelperReady, 'ready', $utf8)
    Wait-ForBinityExit $c ([int]$c.ParentPid) 'Application process'
    # PyInstaller one-file mode has an outer bootloader process that owns the
    # extraction directory and executable handle after the Python child exits.
    Wait-ForBinityExit $c ([int]$c.BootloaderPid) 'PyInstaller bootloader'

    if (-not (Install-UpdatePayload $c)) {
        # Never silently change the installed path. Keep the verified download.
        Write-UpdateLog $c 'Replacement failed; restarting the existing executable'
        if ([IO.File]::Exists($c.Final)) { $null = Start-UpdateTarget $c $c.Final $false }
        throw 'Could not replace the installed EXE; download retained for retry'
    }

    $ready = $false
    try { $ready = Start-UpdateTarget $c $c.Final }
    catch {
        # Do not launch a second copy if startup timed out while it is alive.
        Write-UpdateLog $c "Startup error: $_"
        throw
    }
    if (-not $ready) {
        if (Restore-PreviousVersion $c) {
            $null = Start-UpdateTarget $c $c.Final $false
        }
        throw 'New version exited before readiness; update was not acknowledged'
    }

    foreach ($file in @($c.Downloaded, $c.Candidate, $c.Backup)) {
        try { if ([IO.File]::Exists($file)) { [IO.File]::Delete($file) } } catch {}
    }
    [IO.File]::WriteAllText($c.Flag, '1', $utf8)
    try {
        $handoff = [IO.Path]::GetDirectoryName($c.Ready)
        if ([IO.Directory]::Exists($handoff)) { [IO.Directory]::Delete($handoff, $true) }
    } catch {}
    Write-UpdateLog $c "Startup acknowledged: $($c.Final)"
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
    # Load the codec at startup, not lazily from a possibly cleaned _MEI archive.
    return base64.b64encode(_encode_utf16le(script)[0]).decode("ascii")


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
