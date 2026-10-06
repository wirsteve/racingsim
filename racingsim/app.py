"""Double-click entry point (the packaged app runs this).

Starts the local game server on a free port, opens the browser, and keeps a small
console window open; closing that window quits the game. If the game is already
running, it just opens another browser tab.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.request
import webbrowser

PORTS = range(8765, 8785)


def _running_instance() -> int | None:
    for port in PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=0.4) as r:
                if r.headers.get("Server", "").startswith("racingsim"):
                    json.loads(r.read() or b"{}")
                    return port
        except (OSError, ValueError):
            continue
    return None


def _free_port() -> int:
    for port in PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("No free port between 8765 and 8784 - is something else using them?")


def main() -> int:
    port = _running_instance()
    if port is not None:
        webbrowser.open(f"http://127.0.0.1:{port}/")
        return 0
    from .history import HistoryDB
    from .paths import SAVE_DIR
    from .ui.server import serve
    print("racingsim - starting up...", flush=True)
    HistoryDB.load_default()  # first run from source compiles the history database
    port = _free_port()
    print(f"Saves are kept in {SAVE_DIR}")
    print("Close this window to quit.\n", flush=True)
    serve(port=port, open_browser=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
