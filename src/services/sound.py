from __future__ import annotations

import os
from pathlib import Path

from src.core.resources import resource_path

SOUND_OFF = "off"
SOUND_WINDOWS = "windows"
SOUND_PAPER = "paper"
SOUND_TRASH = "trash"


class SoundService:
    def __init__(self) -> None:
        self.paper_sound_path = Path(resource_path("sounds/paper-crumpling.wav"))
        self.trash_sound_path = Path(resource_path("sounds/throwing-paper.wav"))

    def play_clear_success(self, mode: str) -> None:
        """Plays the configured sound effect on successful bin clear."""
        mode = (mode or SOUND_OFF).lower()
        if mode == SOUND_OFF or os.name != "nt":
            return

        try:
            import winsound
        except ImportError:
            return

        sound_file = None
        if mode == SOUND_PAPER:
            sound_file = self.paper_sound_path
        elif mode == SOUND_TRASH:
            sound_file = self.trash_sound_path

        if sound_file and sound_file.exists():
            try:
                winsound.PlaySound(str(sound_file), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except RuntimeError:
                pass  # Fallback to system sound

        # Fallback for Windows mode or failed custom sound
        if mode in (SOUND_WINDOWS, SOUND_PAPER, SOUND_TRASH):
            try:
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except RuntimeError:
                pass
