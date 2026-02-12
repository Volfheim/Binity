import ctypes
import subprocess
import logging

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
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        result = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

        if result != 0:
            return 0

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
    except Exception as e:
        logger.error(f"Ошибка получения уровня корзины: {e}")
        return 0

def get_bin_size():
    try:
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        result = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

        if result != 0:
            return 0

        return info.i64Size
    except Exception as e:
        logger.error(f"Ошибка получения размера корзины: {e}")
        return 0

def empty_bin():
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004

        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        logger.info("Корзина успешно очищена")
        return True
    except Exception as e:
        logger.error(f"Ошибка очистки корзины: {e}")
        return False

def open_recycle_bin():
    try:
        subprocess.Popen(['explorer.exe', 'shell:RecycleBinFolder'],
                         shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        logger.info("Корзина успешно открыта")
        return True
    except Exception as e:
        logger.error(f"Ошибка открытия корзины: {e}")
        return False