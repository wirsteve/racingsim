"""Local web server for the racingsim UI (standard library only).

    python -m racingsim serve            # http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import mimetypes
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from ..game.session import Game
from . import api

STATIC = Path(__file__).resolve().parent / "static"


class AppState:
    def __init__(self) -> None:
        self.game: Optional[Game] = None
        self.lock = threading.Lock()


STATE = AppState()


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _game() -> Game:
    if STATE.game is None:
        raise ApiError("No game loaded", 409)
    return STATE.game


def handle(method: str, path: str, query: dict, body: dict):
    parts = [unquote(p) for p in path.strip("/").split("/")]
    if parts[0] != "api":
        raise ApiError("not found", 404)
    route = parts[1:] or [""]
    head = route[0]

    if head == "setup":
        return api.setup_options()
    if head == "saves":
        return Game.saves()
    if head == "new" and method == "POST":
        STATE.game = Game.new(
            first=body.get("first", ""), last=body.get("last", ""), region=body["region"],
            age=int(body.get("age", 10)), discipline=body.get("discipline", "karting"),
            background=body.get("background", "middle"), talent=body.get("talent", "unknown"),
            seed=int(body.get("seed") or 2026), scale=float(body.get("scale") or 0.6),
            start_year=int(body.get("start_year") or 2026))
        return api.status(STATE.game)
    if head == "load" and method == "POST":
        try:
            STATE.game = Game.load(body["name"])
        except FileNotFoundError:
            raise ApiError("save not found", 404)
        return api.status(STATE.game)
    if head == "status":
        if STATE.game is None:
            return {"phase": "none"}
        return api.status(STATE.game)

    g = _game()
    w = g.world
    if head == "save" and method == "POST":
        path = g.save(body.get("name") or f"{w.player.last_name if w.player else 'world'}_{w.year}")
        return {"saved": path.stem}
    if head == "sim" and method == "POST":
        ran = g.sim_until(body.get("until", "week"))
        return {"status": api.status(g), "races": len(ran)}
    if head == "dashboard":
        return api.dashboard(g)
    if head == "news":
        return api.news(w, limit=int(query.get("limit", 100)), kind=query.get("kind") or None)
    if head == "drivers":
        return api.drivers_query(w, query)
    if head == "driver" and len(route) > 1:
        did = int(route[1])
        if did not in w.drivers:
            raise ApiError("no such driver", 404)
        out = api.driver_detail(w, did)
        out["news"] = api.news(w, limit=30, driver_id=did)
        return out
    if head == "pyramid":
        return api.pyramid(w)
    if head == "instances" and len(route) > 1:
        return api.series_instances(w, route[1])
    if head == "series" and len(route) > 1:
        if route[1] not in w.pyramid.series:
            raise ApiError("no such series", 404)
        return api.series_detail(w, route[1])
    if head == "race" and len(route) > 2:
        res = api.race_result(w, route[1], int(route[2]), int(query["year"]) if query.get("year") else None)
        if res is None:
            raise ApiError("no result recorded for that race", 404)
        return res
    if head == "team" and len(route) > 1:
        return api.team_detail(w, int(route[1]))
    if head == "tracks":
        return api.tracks_query(w, query)
    if head == "track" and len(route) > 1:
        if route[1] not in w.tracks:
            raise ApiError("no such track", 404)
        return api.track_detail(w, route[1])
    if head == "jewels":
        if method == "POST":
            key = body["key"]
            if body.get("enter"):
                from ..sim.season import MAX_JEWELS_PER_SEASON
                if len(w.player_jewels) >= MAX_JEWELS_PER_SEASON and key not in w.player_jewels:
                    raise ApiError(f"You can enter at most {MAX_JEWELS_PER_SEASON} crown jewels a season.")
                w.player_jewels.add(key)
            else:
                w.player_jewels.discard(key)
        return api.jewels(g)
    if head == "apply" and method == "POST":
        if body.get("apply"):
            w.player_applications.add(body["key"])
        else:
            w.player_applications.discard(body["key"])
        return api.opportunities(g)
    if head == "offseason":
        if method == "POST":
            if body.get("action"):
                msg = g.act(body["action"], body.get("arg"))
                return {"message": msg, **api.offseason(g)}
            msg = g.choose(body["choice"])
            return {"message": msg, "status": api.status(g)}
        return api.offseason(g)
    if head == "regions":
        return api.regions(w)
    raise ApiError("not found", 404)


class Handler(BaseHTTPRequestHandler):
    server_version = "racingsim/1.0"

    def log_message(self, fmt, *args):  # quieter console
        if "/api/" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _send(self, status: int, payload: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj, default=_default).encode(), "application/json")

    def _dispatch(self, method: str) -> None:
        url = urlparse(self.path)
        if url.path.startswith("/api/"):
            query = {k: v[-1] for k, v in parse_qs(url.query).items()}
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    body = json.loads(self.rfile.read(n) or b"{}")
            try:
                with STATE.lock:
                    out = handle(method, url.path, query, body)
                self._json(200, out)
            except ApiError as e:
                self._json(e.status, {"error": str(e)})
            except (ValueError, KeyError) as e:
                self._json(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover - surfaced to the UI
                traceback.print_exc()
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
            return
        rel = url.path.lstrip("/") or "index.html"
        f = (STATIC / rel).resolve()
        if not str(f).startswith(str(STATIC)) or not f.is_file():
            f = STATIC / "index.html"
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        self._send(200, f.read_bytes(), ctype)

    def do_GET(self):  # noqa: N802
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")


def _default(o):
    if isinstance(o, set):
        return sorted(o)
    if hasattr(o, "__dict__"):
        return o.__dict__
    return str(o)


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"racingsim running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
