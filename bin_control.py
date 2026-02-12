import ctypes
import os
import subprocess


def is_bin_empty():
    """Проверяет, пуста ли корзина"""
    path = os.path.expandvars(r'%SystemDrive%\$Recycle.Bin')
    for root, dirs, files in os.walk(path):
        if files:
            return False
    return True


def empty_bin():
    """Очищает корзину с помощью API Windows"""
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004

    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND

    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)


def open_recycle_bin():
    """Открывает корзину в проводнике"""
    subprocess.run(['explorer.exe', 'shell:RecycleBinFolder'])