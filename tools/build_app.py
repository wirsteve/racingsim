"""Build the stand-alone racingsim app for the current OS.

    pip install pyinstaller
    python tools/build_app.py            # -> dist/racingsim(.exe)

Steps: compile data/racingsim.db fresh from the JSON sources, then bundle the
code, that database, the track/series data and the web UI into one executable.
The raw history JSON is not bundled; the compiled database replaces it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build_db() -> Path:
    from racingsim.knowledge.pipeline import build_database
    from racingsim.paths import DB_PATH
    build_database(DB_PATH, force=True)
    print(f"built {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.1f} MB)")
    return DB_PATH


def main() -> int:
    db = build_db()
    sep = os.pathsep
    data_args = []
    for f in sorted((ROOT / "data").glob("*.json")):
        data_args += ["--add-data", f"{f}{sep}data"]
    data_args += ["--add-data", f"{ROOT / 'data' / 'tracks'}{sep}data/tracks"]
    data_args += ["--add-data", f"{db}{sep}data"]
    data_args += ["--add-data", f"{ROOT / 'racingsim' / 'ui' / 'static'}{sep}racingsim/ui/static"]
    name = "racingsim"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", name,
           "--paths", str(ROOT), "--collect-submodules", "racingsim",
           "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
           *data_args, str(ROOT / "tools" / "launch.py")]
    print(" ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    exe = ROOT / "dist" / (name + (".exe" if sys.platform.startswith("win") else ""))
    print(f"\nbuilt {exe} ({exe.stat().st_size / 1e6:.1f} MB)")
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
