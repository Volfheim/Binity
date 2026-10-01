# Local Windows build only. No credentials, tagging, signing, or publication.
from pathlib import Path
import os
import sys

root = Path(SPECPATH)

# Do not bundle unrelated DLLs from tools on the caller's PATH (e.g. Poppler's
# icuuc.dll shadows Windows ICU but does not provide the ABI required by Qt).
# This changes only the build process, never the user's system environment.
windows = Path(os.environ["SystemRoot"])
os.environ["PATH"] = os.pathsep.join(str(path) for path in (
    Path(sys.executable).parent,
    Path(sys.base_prefix),
    Path(sys.base_prefix) / "DLLs",
    windows / "System32",
    windows,
))

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    # Design experiments under icons/light and icons/dark are not release assets.
    datas=[(str(root / "icons" / name), "icons") for name in (
        "bin_0.ico", "bin_25.ico", "bin_50.ico", "bin_75.ico", "bin_full.ico",
        "github.svg", "github_dark.svg",
    )] + [(str(root / "sounds"), "sounds")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Binity",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "icons" / "bin_full.ico"),
    version=str(root / "version_info.txt"),
)
