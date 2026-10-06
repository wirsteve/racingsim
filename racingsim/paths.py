"""Where things live, both when run from source and when frozen into an app.

* ``DATA_DIR``  read-only reference data (tracks, series, history). In a packaged
  app it sits inside the bundle (``sys._MEIPASS``).
* ``DB_PATH``   the compiled SQLite reference database (``racingsim.db``). Built
  from the JSON sources on first run from source; shipped prebuilt in the app.
* ``USER_DIR``  per-user writable folder for save games and settings:
  Windows ``%APPDATA%\\racingsim``, macOS ``~/Library/Application Support/racingsim``,
  Linux ``~/.local/share/racingsim``. Override with ``RACINGSIM_HOME``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "racingsim" / "ui" / "static" if FROZEN else Path(__file__).resolve().parent / "ui" / "static"


def _user_dir() -> Path:
    if os.environ.get("RACINGSIM_HOME"):
        return Path(os.environ["RACINGSIM_HOME"])
    if not FROZEN:
        return ROOT  # running from a checkout: keep saves next to the code, as before
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home())) / "racingsim"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "racingsim"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "racingsim"


USER_DIR = _user_dir()
SAVE_DIR = USER_DIR / "saves"
DB_PATH = DATA_DIR / "racingsim.db"
