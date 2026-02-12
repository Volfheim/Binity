import ctypes
import subprocess
import logging
import time

logger = logging.getLogger(__name__)

class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_ulong),
        ('i64Size', ctypes.c_ulonglong),
        ('i64NumItems', ctypes.c_ulonglong)
    ]

def get_bin_level():
    try:
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res != 0 or info.i64Size == 0:
            return 0
        size = info.i64Size
        if size < 1 << 30:
            return 1
        if size < 2 << 30:
            return 2
        if size < 4 << 30:
            return 3
        return 4
    except Exception as e:
        logger.error(f"Ошибка получения уровня корзины: {e}")
        return 0

def get_bin_size():
    try:
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        return info.i64Size if res == 0 else 0
    except Exception as e:
        logger.error(f"Ошибка получения размера корзины: {e}")
        return 0

def empty_bin():
    try:
        flags = 0x00000001
        time.sleep(1)
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        logger.info("Корзина успешно очищена")
        return True
    except Exception as e:
        logger.error(f"Ошибка очистки корзины: {e}")
        return False

def open_recycle_bin():
    try:
        subprocess.Popen(
            ['explorer.exe', 'shell:RecycleBinFolder'],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info("Корзина успешно открыта")
        return True
    except Exception as e:
        logger.error(f"Ошибка открытия корзины: {e}")
        return False