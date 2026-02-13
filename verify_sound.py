
import sys
import os
import winsound
import time
from pathlib import Path

# Mock resource_path logic
def resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        # Assuming we run this from project root
        base = Path(os.getcwd())
    return str(base / relative_path)

def test_sound():
    sound_path = Path("sounds/throwing-paper.wav").resolve()
    print(f"Testing sound file: {sound_path}")
    
    if not sound_path.exists():
        print("ERROR: File does not exist!")
        print(f"Current working dir: {os.getcwd()}")
        print(f"Directory listing: {os.listdir('.')}")
        if os.path.exists("sounds"):
             print(f"Sounds dir listing: {os.listdir('sounds')}")
        return

    print(f"File size: {sound_path.stat().st_size} bytes")

    print("Attempting to play via winsound...")
    try:
        # verifying format by just reading header
        with open(sound_path, 'rb') as f:
            header = f.read(4)
            print(f"Header: {header}")
            
        winsound.PlaySound(str(sound_path), winsound.SND_FILENAME)
        print("Success! Sound should have played.")
    except Exception as e:
        print(f"ERROR playing sound: {e}")

if __name__ == "__main__":
    test_sound()
