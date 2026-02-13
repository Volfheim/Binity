from __future__ import annotations

import os
from pathlib import Path

from src.core.resources import resource_path

SOUND_OFF = "off"
SOUND_WINDOWS = "windows"
SOUND_PAPER = "paper"


class SoundService:
    def __init__(self) -> None:
        self.paper_sound_path = Path(resource_path("sounds/paper-crumpling.wav"))
        self.trash_sound_path = Path(resource_path("sounds/throwing-paper.wav"))

    def play_clear_success(self, mode: str) -> None:
        mode = str(mode or SOUND_OFF).lower()
        if mode == SOUND_OFF:
            return

        if os.name != "nt":
            return

        try:
            import winsound
        except Exception:
            return

        if mode == SOUND_PAPER and self.paper_sound_path.exists():
            try:
                winsound.PlaySound(str(self.paper_sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except RuntimeError:
                pass

        if mode in (SOUND_WINDOWS, SOUND_PAPER):
            try:
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except RuntimeError:
                try:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except RuntimeError:
                    pass
