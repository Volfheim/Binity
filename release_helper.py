"""Retired publishing entry point. This module has no external side effects."""


def main() -> int:
    print("release_helper.py is retired. No build, credentials, tags or GitHub releases were changed.")
    print("For a local build use: py -3.13 -m PyInstaller --clean --noconfirm Binity.spec")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
