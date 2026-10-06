"""SQLite storage for the historical database.

The JSON files under ``data/history/`` are the source of truth (they diff well and
the scrapers in ``tools/history/`` write them). ``build()`` compiles them into one
SQLite file with indexed tables, so the game never has to parse thousands of JSON
files at start-up, and race venues are matched to track ids once, at build time.

Tables
    season(source, year, official_name, data_level, n_regulars, field, doc)
    standing(source, year, pos, name, wiki, points, wins, starts, top5, top10, team)
    race(source, year, round, date, race, track, city, state, winner, winner_wiki, cancelled, track_id)
    driver(wiki, name, qid, birth_date, birth_place, state, country)
    series(source, doc)          -- optional series metadata (touring series)
    meta(key, value)
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, Optional

SCHEMA_VERSION = "4"

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE season(source TEXT, year INTEGER, official_name TEXT, data_level TEXT,
                    n_regulars INTEGER, field INTEGER, doc TEXT, PRIMARY KEY(source, year));
CREATE TABLE standing(source TEXT, year INTEGER, pos INTEGER, name TEXT, wiki TEXT, points REAL,
                      wins INTEGER, starts INTEGER, top5 INTEGER, top10 INTEGER, team TEXT);
CREATE TABLE race(source TEXT, year INTEGER, round INTEGER, date TEXT, race TEXT, track TEXT, city TEXT,
                  state TEXT, winner TEXT, winner_wiki TEXT, cancelled INTEGER, track_id TEXT);
CREATE TABLE driver(wiki TEXT PRIMARY KEY, name TEXT, qid TEXT, birth_date TEXT, birth_place TEXT,
                    state TEXT, country TEXT);
CREATE TABLE series(source TEXT PRIMARY KEY, doc TEXT);
CREATE INDEX standing_wiki ON standing(wiki);
CREATE INDEX standing_season ON standing(source, year);
CREATE INDEX race_season ON race(source, year);
CREATE INDEX race_track ON race(track_id);
"""


def source_files(directory: Path) -> list[Path]:
    """Every JSON input under ``directory`` (season files, driver files, series metadata)."""
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.json"))


def inputs_stamp(directory: Path, extra: Iterable[Path] = ()) -> str:
    """Cheap fingerprint of the inputs: newest mtime + file count + schema version."""
    files = source_files(directory) + [p for p in extra if p.exists()]
    newest = max((p.stat().st_mtime for p in files), default=0.0)
    return f"{SCHEMA_VERSION}:{len(files)}:{newest:.0f}"


def _season_dirs(directory: Path) -> list[Path]:
    """Folders holding ``<year>.json`` files (nested folders such as touring/<series>/ too)."""
    out = []
    for sub in sorted(p for p in directory.rglob("*") if p.is_dir()):
        if any(f.stem.isdigit() for f in sub.glob("*.json")):
            out.append(sub)
    return out


def build(directory: Path, target: str | Path, tracks=None, stamp: str = "",
          knowledge_dir: Optional[Path] = None) -> sqlite3.Connection:
    """Compile ``directory`` into SQLite at ``target`` (a path or ``":memory:"``).

    With ``tracks`` (a TrackDatabase) every race is matched to a track id now, so
    calendars load with one query later.
    """
    from .db import match_track

    if target != ":memory:":
        target = Path(target)
        tmp = target.with_suffix(".building")
        if tmp.exists():
            tmp.unlink()
        conn = sqlite3.connect(tmp)
    else:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(SCHEMA)
    track_list = list(tracks) if tracks is not None else None
    seasons, standings, races = [], [], []
    for sub in _season_dirs(directory):
        source = sub.name
        for f in sorted(sub.glob("*.json")):
            if not f.stem.isdigit():
                continue
            year = int(f.stem)
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
            sched = doc.get("schedule") or []
            st = doc.get("standings") or []
            n_races = len([r for r in sched if not r.get("cancelled")]) or len(sched)
            regulars = [r for r in st if (r.get("starts") or 0) >= 0.5 * max(1, n_races)]
            team_of: dict[str, str] = {}
            for t in doc.get("teams") or []:
                for c in t.get("cars", []):
                    for dr in c.get("drivers", []):
                        if dr.get("wiki") and (c.get("full_time") or dr["wiki"] not in team_of):
                            team_of[dr["wiki"]] = t.get("team") or ""
            seasons.append((source, year, doc.get("official_name"), doc.get("data_level"),
                            max(len(regulars), 1), len(st), json.dumps(doc, ensure_ascii=False)))
            for r in st:
                standings.append((source, year, r.get("pos"), r.get("name"), r.get("wiki"), r.get("points"),
                                  r.get("wins") or 0, r.get("starts"), r.get("top5"), r.get("top10"),
                                  team_of.get(r.get("wiki") or "", "")))
            for i, r in enumerate(sched):
                tid = None
                if track_list is not None and not r.get("cancelled"):
                    tid = match_track(track_list, r.get("track"), r.get("city"), r.get("state"),
                                      r.get("race") or "", year)
                races.append((source, year, r.get("round") or i + 1, r.get("date"), r.get("race"), r.get("track"),
                              r.get("city"), r.get("state"), r.get("winner"), r.get("winner_wiki"),
                              1 if r.get("cancelled") else 0, tid))
    conn.executemany("INSERT OR REPLACE INTO season VALUES (?,?,?,?,?,?,?)", seasons)
    conn.executemany("INSERT INTO standing VALUES (?,?,?,?,?,?,?,?,?,?,?)", standings)
    conn.executemany("INSERT INTO race VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", races)
    drivers = []
    for f in sorted(directory.rglob("drivers*.json")):
        with open(f, encoding="utf-8") as fh:
            for wiki, b in json.load(fh).items():
                drivers.append((wiki, b.get("name"), b.get("qid"), b.get("birth_date"), b.get("birth_place"),
                                b.get("state"), b.get("country")))
    conn.executemany("INSERT OR IGNORE INTO driver VALUES (?,?,?,?,?,?,?)", drivers)
    for f in sorted(directory.rglob("series.json")):
        with open(f, encoding="utf-8") as fh:
            for key, meta in json.load(fh).items():
                conn.execute("INSERT OR REPLACE INTO series VALUES (?,?)", (key, json.dumps(meta)))
    from ..knowledge.build import build_knowledge, build_teams
    build_teams(conn)
    if knowledge_dir is not None and knowledge_dir.exists():
        build_knowledge(conn, knowledge_dir)
        results_dir = knowledge_dir.parent / "results"
        if results_dir.exists():
            from ..knowledge.build import build_results
            build_results(conn, results_dir)
    if tracks is not None and hasattr(tracks, "write_sqlite"):
        tracks.write_sqlite(conn)
    conn.execute("INSERT INTO meta VALUES ('stamp', ?)", (stamp,))
    conn.execute("INSERT INTO meta VALUES ('tracks_matched', ?)", ("1" if track_list is not None else "0",))
    conn.commit()
    if target == ":memory:":
        return conn
    conn.close()
    os.replace(tmp, target)
    return open_db(target)


def open_db(path: Path) -> sqlite3.Connection:
    uri = f"file:{Path(path).as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def stored_stamp(path: Path) -> Optional[str]:
    if not Path(path).exists():
        return None
    try:
        conn = open_db(path)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='stamp'").fetchone()
        finally:
            conn.close()
        return row[0] if row else None
    except sqlite3.Error:
        return None


_LOCK = threading.Lock()
