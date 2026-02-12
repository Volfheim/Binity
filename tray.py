import pystray
from PIL import Image
from threading import Thread
import time
from bin_control import is_bin_empty, empty_bin, open_recycle_bin
from utils import resource_path


class TrayIcon:
    def __init__(self):
        icon_path = "bin_0.ico" if is_bin_empty() else "bin_full.ico"
        self.icon = pystray.Icon("Binity")
        self.icon.icon = Image.open(resource_path(f"icons/{icon_path}"))
        self.icon.menu = pystray.Menu(
            pystray.MenuItem("Открыть корзину", self.open_bin),
            pystray.MenuItem("Очистить корзину", self.clear_bin),
            pystray.MenuItem("Выход", self.quit_app)
        )
        self._running = True
        self.update_thread = Thread(target=self.auto_update_icon, daemon=True)
        self.update_thread.start()

    def run(self):
        self.icon.run()

    def quit_app(self):
        self._running = False
        self.icon.stop()

    def open_bin(self):
        open_recycle_bin()

    def clear_bin(self):
        empty_bin()
        self.update_icon()

    def update_icon(self):
        icon_path = "bin_0.ico" if is_bin_empty() else "bin_full.ico"
        self.icon.icon = Image.open(resource_path(f"icons/{icon_path}"))
        self.icon.visible = True

    def auto_update_icon(self):
        while self._running:
            self.update_icon()
            time.sleep(10)