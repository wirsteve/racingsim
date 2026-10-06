"""Historical database: real national-series seasons (1995 onward).

Data lives in ``data/history/<series_dir>/<year>.json`` (rosters, final standings,
schedules; built from Wikipedia season articles) plus ``data/history/drivers.json``
(birth dates and birthplaces from Wikidata). It is used to

* seed the start year's national series with the real teams and drivers,
* place real *future* drivers in the world as prospects at their real ages,
* run each season's national series on that year's real calendar.

After the start year the simulation is free to diverge (alternate history).
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..util import DATA_DIR
from . import store

HISTORY_DIR = DATA_DIR / "history"

# template key -> list of (data dir, first year, last year)
SOURCES = {
    "cup_series": [("nascar_cup", 1995, 2100)],
    "stock_national": [("nascar_xfinity", 1995, 2100)],
    "truck_series": [("nascar_trucks", 1995, 2100)],
    "open_wheel_top": [("cart_champcar", 1995, 2007), ("irl_indycar", 2008, 2100)],
    "open_wheel_top_irl": [("irl_indycar", 1996, 2007)],
    "formula_lights": [("indy_lights", 1995, 2100)],
    "formula_pro": [("pro_mazda", 1995, 2100)],
    "formula_2000": [("usf2000", 1995, 2100)],
}
TEMPLATE_TIER = {"cup_series": 7, "open_wheel_top": 7, "open_wheel_top_irl": 7, "stock_national": 6,
                 "truck_series": 5, "formula_lights": 5, "formula_pro": 4, "formula_2000": 3}
TEMPLATE_DISCIPLINE = {"cup_series": "stock_car", "stock_national": "stock_car", "truck_series": "stock_car",
                       "open_wheel_top": "open_wheel", "open_wheel_top_irl": "open_wheel",
                       "formula_lights": "open_wheel", "formula_pro": "open_wheel", "formula_2000": "open_wheel"}

GENERIC = {"speedway", "raceway", "international", "motor", "motorsports", "park", "the", "circuit", "of",
           "course", "track", "superspeedway", "speedways", "sports", "car", "race", "street", "grand", "prix",
           "at", "and", "complex", "motorplex", "ring", "road", "club", "fairgrounds", "mile"}
# Former / sponsor names seen in season articles -> our canonical names.
ALIASES = {
    "sears point": "Sonoma Raceway", "infineon": "Sonoma Raceway", "sonoma": "Sonoma Raceway",
    "lowe's motor speedway": "Charlotte Motor Speedway", "lowes motor speedway": "Charlotte Motor Speedway",
    "north carolina motor speedway": "Rockingham Speedway", "north carolina speedway": "Rockingham Speedway",
    "rockingham": "Rockingham Speedway",
    "phoenix international raceway": "Phoenix Raceway", "ism raceway": "Phoenix Raceway",
    "dover downs": "Dover Motor Speedway", "dover international": "Dover Motor Speedway",
    "new hampshire international": "New Hampshire Motor Speedway",
    "richmond international": "Richmond Raceway",
    "gateway international": "Gateway Motorsports Park", "world wide technology": "Gateway Motorsports Park",
    "auto club speedway": "California Speedway", "california speedway": "California Speedway",
    "echopark": "Atlanta Motor Speedway", "atlanta motor speedway": "Atlanta Motor Speedway",
    "homestead": "Homestead-Miami Speedway", "miami-dade homestead": "Homestead-Miami Speedway",
    "o'reilly raceway park": "Indianapolis Raceway Park", "lucas oil raceway": "Indianapolis Raceway Park",
    "lucas oil indianapolis raceway park": "Indianapolis Raceway Park",
    "mid-ohio": "Mid-Ohio Sports Car Course", "laguna seca": "Laguna Seca Raceway",
    "mazda raceway laguna seca": "Laguna Seca Raceway", "weathertech raceway": "Laguna Seca Raceway",
    "road atlanta": "Road Atlanta", "mosport": "Mosport Park", "canadian tire motorsport park": "Mosport Park",
    "circuit of the americas": "Circuit of the Americas", "texas world speedway": "Texas World Speedway",
    "nazareth": "Nazareth Speedway", "pennsylvania international raceway": "Nazareth Speedway",
    "memphis": "Memphis Motorsports Park", "pikes peak": "Pikes Peak International Raceway",
    "iowa speedway": "Iowa Speedway", "kentucky speedway": "Kentucky Speedway",
    "chicagoland": "Chicagoland Speedway", "kansas speedway": "Kansas Speedway",
    "nashville speedway usa": "Nashville Fairgrounds Speedway", "fairgrounds speedway": "Nashville Fairgrounds Speedway",
    "nashville superspeedway": "Nashville Superspeedway", "las vegas motor speedway": "Las Vegas Motor Speedway",
    "watkins glen": "Watkins Glen International", "michigan international": "Michigan International Speedway",
    "michigan speedway": "Michigan International Speedway", "pocono": "Pocono Raceway",
    "exhibition place": "Toronto Street Circuit", "streets of toronto": "Toronto Street Circuit",
    "milwaukee mile": "Milwaukee Mile", "wisconsin state fair park": "Milwaukee Mile",
    "texas motor speedway": "Texas Motor Speedway", "bristol": "Bristol Motor Speedway",
    "bristol international": "Bristol Motor Speedway",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("–", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", _norm(s)) if t not in GENERIC and len(t) > 1}


class HistoryDB:
    """Read access to the compiled history database (see ``store.py``)."""

    def __init__(self, conn: sqlite3.Connection, path: Optional[Path] = None, source_dir: Optional[Path] = None):
        self.conn = conn
        self.path = path              # compiled file, or None for an in-memory build
        self.source_dir = source_dir  # JSON sources (in-memory builds re-create from these)
        self._reset()

    def _reset(self) -> None:
        self._sched_cache: dict = {}
        self._season_cache: dict = {}
        self._careers: Optional[dict] = None
        self._bios: Optional[dict] = None
        row = self.conn.execute("SELECT value FROM meta WHERE key='tracks_matched'").fetchone()
        self._matched = bool(row and row[0] == "1")

    # A world (and so every save game) holds a reference: pickle the location, not the connection.
    def __getstate__(self) -> dict:
        return {"path": str(self.path) if self.path else None,
                "source_dir": str(self.source_dir) if self.source_dir else None}

    def __setstate__(self, state: dict) -> None:
        path = Path(state["path"]) if state.get("path") else None
        if path is not None and path.exists():
            self.__init__(store.open_db(path), path=path)
            return
        if state.get("source_dir") and Path(state["source_dir"]).exists():
            other = HistoryDB.load(Path(state["source_dir"]))
        else:
            other = HistoryDB.load_default()  # e.g. the app moved: use the copy that ships with it
        if other is None:
            raise RuntimeError("history database not found")
        self.__init__(other.conn, path=other.path, source_dir=other.source_dir)

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, directory: Path = HISTORY_DIR, tracks=None) -> Optional["HistoryDB"]:
        """Build an in-memory database straight from a folder of JSON files."""
        if not directory.exists() or not store._season_dirs(directory):
            return None
        return cls(store.build(directory, ":memory:", tracks), source_dir=directory)

    @classmethod
    def open(cls, path: Path) -> "HistoryDB":
        return cls(store.open_db(path), path=path)

    @classmethod
    def load_default(cls) -> Optional["HistoryDB"]:
        return _cached_default()

    # ------------------------------------------------------------------ queries
    @property
    def seasons(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for src, year in self.conn.execute("SELECT source, year FROM season ORDER BY source, year"):
            out.setdefault(src, []).append(year)
        return out

    def _source_for(self, template_key: str, year: int) -> Optional[str]:
        for d, lo, hi in SOURCES.get(template_key, []):
            if lo <= year <= hi and self._has(d, year):
                return d
        return None

    def _has(self, source: str, year: int) -> bool:
        key = ("has", source, year)
        if key not in self._season_cache:
            self._season_cache[key] = self.conn.execute(
                "SELECT 1 FROM season WHERE source=? AND year=?", (source, year)).fetchone() is not None
        return self._season_cache[key]

    def raw_season(self, source: str, year: int) -> Optional[dict]:
        key = (source, year)
        if key not in self._season_cache:
            row = self.conn.execute("SELECT doc FROM season WHERE source=? AND year=?", key).fetchone()
            self._season_cache[key] = json.loads(row[0]) if row else None
        return self._season_cache[key]

    def season(self, template_key: str, year: int) -> Optional[dict]:
        src = self._source_for(template_key, year)
        return self.raw_season(src, year) if src else None

    def years(self) -> list[int]:
        return [y for (y,) in self.conn.execute("SELECT year FROM season WHERE source='nascar_cup' ORDER BY year")]

    def bio(self, wiki: Optional[str]) -> dict:
        if not wiki:
            return {}
        if self._bios is None:
            self._bios = {w: {"name": n, "qid": q, "birth_date": b, "birth_place": bp, "state": st, "country": c}
                          for w, n, q, b, bp, st, c in self.conn.execute("SELECT * FROM driver")}
        return self._bios.get(wiki, {})

    def birth_year(self, wiki: Optional[str]) -> Optional[int]:
        b = self.bio(wiki).get("birth_date")
        if not b:
            return None
        m = re.match(r"(\d{4})", str(b))
        return int(m.group(1)) if m else None

    # ------------------------------------------------------------------ calendars
    def schedule(self, template_key: str, year: int, tracks) -> Optional[list[str]]:
        key = (template_key, year)
        if key in self._sched_cache:
            return self._sched_cache[key]
        src = self._source_for(template_key, year)
        out = None
        if src:
            rows = self.conn.execute(
                "SELECT track_id, track, city, state, race FROM race WHERE source=? AND year=? AND cancelled=0 "
                "ORDER BY round", (src, year)).fetchall()
            ids = []
            for tid, name, city, state, race in rows:
                if not self._matched or (tid and tid not in tracks):
                    tid = match_track(tracks, name, city, state, race or "", year)
                if tid:
                    ids.append(tid)
            if rows and len(ids) >= max(3, 0.6 * len(rows)):
                out = ids
        self._sched_cache[key] = out
        return out

    # ------------------------------------------------------------------ careers
    def careers(self) -> dict[str, list[dict]]:
        """wiki title -> list of seasons {year, template, tier, pos, n, wins, starts, team} (all series)."""
        if self._careers is not None:
            return self._careers
        meta = {(src, y): (name, n, field) for src, y, name, n, field in
                self.conn.execute("SELECT source, year, official_name, n_regulars, field FROM season")}
        rows_by_source: dict[str, list] = {}
        for row in self.conn.execute("SELECT source, year, pos, wiki, points, wins, starts, top5, top10, team "
                                     "FROM standing WHERE wiki IS NOT NULL"):
            rows_by_source.setdefault(row[0], []).append(row)
        out: dict[str, list[dict]] = {}
        for tpl, sources in SOURCES.items():
            for d, lo, hi in sources:
                for src, year, pos, w, points, wins, starts, top5, top10, team in rows_by_source.get(d, []):
                    if not (lo <= year <= hi):
                        continue
                    name, n, field = meta[(src, year)]
                    out.setdefault(w, []).append({
                        "year": year, "template": tpl, "tier": TEMPLATE_TIER[tpl], "pos": pos,
                        "n": n, "field": field, "wins": wins or 0, "starts": starts,
                        "top5": top5, "top10": top10, "points": points,
                        "series_name": name, "team": team or "",
                    })
        for w in out:
            out[w].sort(key=lambda x: (x["year"], -x["tier"]))
        self._careers = out
        return out


@lru_cache(maxsize=1)
def _cached_default() -> Optional[HistoryDB]:
    """The compiled database, rebuilt from the JSON sources when they changed (source checkouts only)."""
    from ..paths import DB_PATH, FROZEN
    if FROZEN:
        return HistoryDB.open(DB_PATH) if DB_PATH.exists() else None
    if not HISTORY_DIR.exists():
        return None
    stamp = store.inputs_stamp(HISTORY_DIR, _code_and_track_inputs())
    if store.stored_stamp(DB_PATH) != stamp:
        from ..tracks.database import TrackDatabase
        try:
            with store._LOCK:
                store.build(HISTORY_DIR, DB_PATH, TrackDatabase.load(), stamp=stamp).close()
        except OSError:  # read-only checkout: fall back to memory
            return HistoryDB.load(HISTORY_DIR, TrackDatabase.load())
    return HistoryDB.open(DB_PATH)


def _code_and_track_inputs() -> list[Path]:
    here = Path(__file__).resolve().parent
    return ([here / "db.py", here / "store.py", DATA_DIR / "track_years.json", DATA_DIR / "track_rating_overrides.json"]
            + sorted((DATA_DIR / "tracks").glob("*.json")))


_INDEX: dict = {}


def _name_index(tracks) -> dict:
    idx = _INDEX.get(id(tracks))
    if idx is None:
        idx = {}
        for t in tracks:
            idx.setdefault(_norm(t.facts.name), []).append(t)
            for a in t.facts.aliases:
                idx.setdefault(_norm(a), []).append(t)
        _INDEX.clear()
        _INDEX[id(tracks)] = idx
    return idx


def match_track(tracks, name: Optional[str], city: Optional[str], state: Optional[str], race: str,
                year: int) -> Optional[str]:
    """Map a period track name from a season article to a track id in our database."""
    if not name:
        return None
    n = _norm(name)
    by_name = _name_index(tracks)
    road_hint = any(k in _norm(race) + " " + n for k in ("road course", "roval", "grand prix", "road"))
    cands = [t for t in by_name.get(n, []) if t.facts.available_in(year)] or by_name.get(n)
    if not cands:
        for alias, canon in ALIASES.items():
            if alias in n:
                cands = by_name.get(_norm(canon))
                if cands:
                    break
    if not cands:
        toks = _tokens(name)
        best, best_score = None, 0.0
        for t in tracks:
            if not t.facts.available_in(year):
                continue  # a venue that did not exist (or was idle) that year
            tt = _tokens(t.facts.name) | {x for a in t.facts.aliases for x in _tokens(a)}
            score = len(toks & tt) / max(1, len(toks))
            if city and t.facts.city and _norm(city) == _norm(t.facts.city):
                score += 0.6
            if state and t.facts.region and state.upper() == (t.facts.region or "").upper():
                score += 0.2
            if score > best_score:
                best, best_score = t, score
        if best is not None and best_score >= 0.75:
            cands = [best]
    if not cands:
        return None
    # Same facility, several layouts (Daytona oval vs road course, Charlotte oval vs Roval, Indy oval vs road).
    family = []
    for c in cands:
        family += [t for t in tracks if t.facts.city == c.facts.city and t.facts.region == c.facts.region
                   and _tokens(t.facts.name) & _tokens(c.facts.name)]
    family = family or cands
    dirt_hint = "dirt" in _norm(race) + " " + n
    family = [t for t in family if t.facts.is_dirt == dirt_hint] or family
    family = [t for t in family if t.facts.available_in(year)] or family
    # The named venue itself first, then its sister layouts.
    family.sort(key=lambda t: (t not in cands, -(t.profile.prestige or 0)))
    if road_hint:
        roads = [t for t in family if t.facts.is_road]
        if roads:
            return roads[0].id
    ovals = [t for t in family if not t.facts.is_road] or family
    return ovals[0].id
