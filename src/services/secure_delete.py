"""Best-effort Windows overwrite with handle-based containment and link checks."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes as wt
from dataclasses import dataclass
import os
from pathlib import Path

REPARSE_POINT = 0x400
DIRECTORY = 0x10
CHUNK_SIZE = 1024 * 1024


class UnsafeWipeTarget(OSError):
    pass


class FileInfo(ctypes.Structure):
    _fields_ = [("attributes", wt.DWORD), ("created", wt.FILETIME),
                ("accessed", wt.FILETIME), ("written", wt.FILETIME),
                ("volume", wt.DWORD), ("size_high", wt.DWORD), ("size_low", wt.DWORD),
                ("links", wt.DWORD), ("index_high", wt.DWORD), ("index_low", wt.DWORD)]


@dataclass
class WipeStats:
    files: int = 0
    bytes: int = 0
    failures: int = 0


class WindowsWiper:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Secure overwrite requires Windows")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID,
                                        wt.DWORD, wt.DWORD, wt.HANDLE]
        self.api.CreateFileW.restype = wt.HANDLE
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.api.CloseHandle.restype = wt.BOOL
        self.api.GetFileInformationByHandle.argtypes = [wt.HANDLE, ctypes.POINTER(FileInfo)]
        self.api.GetFileInformationByHandle.restype = wt.BOOL
        self.api.GetFinalPathNameByHandleW.argtypes = [wt.HANDLE, wt.LPWSTR, wt.DWORD, wt.DWORD]
        self.api.GetFinalPathNameByHandleW.restype = wt.DWORD
        self.api.SetFileInformationByHandle.argtypes = [wt.HANDLE, ctypes.c_int, wt.LPVOID, wt.DWORD]
        self.api.SetFileInformationByHandle.restype = wt.BOOL

    def _set_delete_pending(self, handle, pending: bool) -> None:
        flag = ctypes.c_ubyte(pending)  # FILE_DISPOSITION_INFO contains BOOLEAN, not BOOL.
        if not self.api.SetFileInformationByHandle(handle, 4, ctypes.byref(flag), ctypes.sizeof(flag)):
            raise ctypes.WinError(ctypes.get_last_error())

    def info(self, handle) -> FileInfo:
        info = FileInfo()
        if not self.api.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info

    def final_path(self, handle) -> str:
        size = self.api.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not size:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(size + 1)
        used = self.api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not used or used >= len(buffer):
            raise UnsafeWipeTarget("Cannot resolve opened file")
        return buffer.value.rstrip("\\").casefold()

    @contextmanager
    def open_checked(self, path: Path, directory: bool, parent_path: str | None = None):
        # Do not follow the final reparse point. Keep each parent open without
        # write/delete sharing while inspecting children, so it cannot be replaced.
        # Metadata-only opens do not enforce the sharing guard on Windows.
        access = 0x80000000 if directory else 0xC0010000  # GENERIC_READ / READ|WRITE|DELETE
        share = 1 if directory else 0
        handle = self.api.CreateFileW(str(path), access, share, None, 3,
                                      0x00200000 | 0x02000000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        pending = False
        try:
            info = self.info(handle)
            if info.attributes & REPARSE_POINT or bool(info.attributes & DIRECTORY) != directory:
                raise UnsafeWipeTarget("Reparse points and unexpected file types are not overwritten")
            final = self.final_path(handle)
            if parent_path is not None and final != parent_path + "\\" + path.name.casefold():
                raise UnsafeWipeTarget("Opened file escaped its checked parent")
            if not directory and info.links != 1:
                raise UnsafeWipeTarget("Hard-linked files are not overwritten")
            if not directory:
                # Exclusive sharing alone does NOT prevent new NTFS hard links.
                # Temporarily mark this already-validated recycle payload pending
                # deletion, then recheck link count before any write. Clear the
                # mark before closing so Shell remains responsible for emptying.
                self._set_delete_pending(handle, True)
                pending = True
                info = self.info(handle)
                # NTFS excludes the delete-pending name from this count. No
                # remaining link may refer to retained data outside the bin.
                if info.links != 0:
                    raise UnsafeWipeTarget("Hard link appeared during validation")
            yield handle, info, final
        finally:
            try:
                if pending:
                    self._set_delete_pending(handle, False)
            finally:
                self.api.CloseHandle(handle)

    def overwrite(self, handle, info: FileInfo, mode: str) -> int:
        # Use the validated handle itself; reopening by pathname would reintroduce
        # a race. DuplicateHandle lets the Python file own only the duplicate.
        import msvcrt
        duplicate = wt.HANDLE()
        self.api.GetCurrentProcess.restype = wt.HANDLE
        self.api.DuplicateHandle.argtypes = [wt.HANDLE, wt.HANDLE, wt.HANDLE,
                                            ctypes.POINTER(wt.HANDLE), wt.DWORD, wt.BOOL, wt.DWORD]
        self.api.DuplicateHandle.restype = wt.BOOL
        process = self.api.GetCurrentProcess()
        if not self.api.DuplicateHandle(process, handle, process, ctypes.byref(duplicate), 0, False, 2):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            fd = msvcrt.open_osfhandle(duplicate.value, os.O_RDWR | os.O_BINARY)
        except Exception:
            self.api.CloseHandle(duplicate)
            raise
        size = (info.size_high << 32) | info.size_low
        zeroes = bytes(CHUNK_SIZE)
        with os.fdopen(fd, "r+b", buffering=0) as stream:
            remaining = size
            while remaining:
                count = min(remaining, CHUNK_SIZE)
                chunk = memoryview(zeroes[:count] if mode == "zero" else os.urandom(count))
                while chunk:
                    written = stream.write(chunk)
                    if not written:
                        raise OSError("Incomplete overwrite")
                    chunk = chunk[written:]
                    remaining -= written
            os.fsync(stream.fileno())
        return size

    def wipe_user_bin(self, root: Path, sid: str, mode: str, stats: WipeStats) -> None:
        def visit(path: Path, parent: str) -> None:
            try:
                attributes = path.lstat().st_file_attributes
                if attributes & REPARSE_POINT:
                    raise UnsafeWipeTarget("Reparse point skipped")
                directory = bool(attributes & DIRECTORY)
                with self.open_checked(path, directory, parent) as (handle, info, final):
                    if directory:
                        for child in path.iterdir():
                            visit(child, final)
                    else:
                        stats.bytes += self.overwrite(handle, info, mode)
                        stats.files += 1
            except OSError:
                stats.failures += 1

        # Only the token's SID is considered, even in an elevated process.
        try:
            with self.open_checked(root, True) as (_, _, root_final):
                user_root = root / sid
                with self.open_checked(user_root, True, root_final) as (_, _, user_final):
                    for entry in user_root.iterdir():
                        if entry.name.lower().startswith("$r"):
                            visit(entry, user_final)
        except FileNotFoundError:
            pass  # A drive may have no recycle bin for this user yet.
        except OSError:
            stats.failures += 1


def current_user_sid() -> str:
    if os.name != "nt":
        raise OSError("Windows token required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.LocalFree.argtypes = [wt.HLOCAL]
    kernel.LocalFree.restype = wt.HLOCAL
    advapi.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int, wt.LPVOID,
                                         wt.DWORD, ctypes.POINTER(wt.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [wt.LPVOID, ctypes.POINTER(wt.LPWSTR)]
    token = wt.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wt.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(wt.LPVOID))[0]
        text = wt.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid_pointer, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text, wt.HLOCAL))
    finally:
        kernel.CloseHandle(token)


def secure_wipe(mode: str) -> WipeStats:
    stats = WipeStats()
    try:
        sid = current_user_sid()
        wiper = WindowsWiper()
        mask = int(wiper.api.GetLogicalDrives())
        if not mask:
            raise OSError("Cannot enumerate volumes")
        wiper.api.GetDriveTypeW.argtypes = [wt.LPCWSTR]
        for index in range(26):
            if mask & (1 << index):
                drive = f"{chr(65 + index)}:\\"
                if wiper.api.GetDriveTypeW(drive) in (2, 3):
                    wiper.wipe_user_bin(Path(drive) / "$Recycle.Bin", sid, mode, stats)
    except OSError:
        stats.failures += 1
    return stats
