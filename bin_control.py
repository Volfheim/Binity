import ctypes
import os
import subprocess


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_ulong),
        ('i64Size', ctypes.c_ulonglong),
        ('i64NumItems', ctypes.c_ulonglong)
    ]


def get_bin_level():
    """Возвращает уровень заполненности корзины (0-4)"""
    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
    result = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

    if result != 0:
        return 0  # Пустая при ошибке

    size = info.i64Size
    if size == 0:
        return 0
    elif size < 1073741824:  # < 1GB
        return 1
    elif size < 2147483648:  # < 2GB
        return 2
    elif size < 4294967296:  # < 4GB
        return 3
    else:
        return 4

def get_bin_size():
    """Возвращает общий размер корзины в байтах"""
    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
    result = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

    if result != 0:
        return 0  # Пустая при ошибке

    return info.i64Size

def empty_bin():
    """Очищает корзину с помощью API Windows"""
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004

    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND

    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)

def open_recycle_bin():
    """Открывает корзину в проводнике"""
    subprocess.run(['explorer.exe', 'shell:RecycleBinFolder'], shell=True)