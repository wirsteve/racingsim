"""Compile the racing knowledge layer (``data/knowledge/*.json``) into SQLite.

Every entity keeps its JSON document (``doc``) plus flattened columns for the
fields the game queries. Every *ranged fact* (a dict with ``min``/``max``/``value``/
``category``) anywhere in an entity is also written to the ``fact`` table with its
unit, confidence and sources, so provenance is queryable per attribute:

    SELECT attribute, min, max, unit, confidence, sources FROM fact
    WHERE entity_id = 'series:arca-menards';
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS source(id TEXT PRIMARY KEY, name TEXT, url TEXT, kind TEXT, reliability TEXT,
    license TEXT, accessed TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS source_unavailable(source TEXT, url TEXT, reason TEXT, checked TEXT,
    replacement_source TEXT);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY, source_id TEXT, url TEXT, info TEXT, accessed TEXT,
    reliability TEXT, confidence TEXT, notes TEXT, entities TEXT);
CREATE TABLE IF NOT EXISTS sanctioning_body(id TEXT PRIMARY KEY, name TEXT, abbrev TEXT, country TEXT,
    founded INTEGER, defunct INTEGER, website TEXT, scope TEXT, confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS car_class(id TEXT PRIMARY KEY, name TEXT, discipline TEXT, chassis TEXT,
    drivetrain TEXT, engine TEXT, hp_min REAL, hp_max REAL, weight_lb_min REAL, weight_lb_max REAL,
    new_cost_min REAL, new_cost_max REAL, confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS series_info(id TEXT PRIMARY KEY, name TEXT, sanctioning_body TEXT, discipline TEXT,
    car_class TEXT, level TEXT, game_tier INTEGER, scope TEXT, regions TEXT, year_from INTEGER, year_to INTEGER,
    game_template TEXT, history_source TEXT, team_structure TEXT, equipment_ownership TEXT, licensing TEXT,
    age_min REAL, age_max REAL, cost_min REAL, cost_max REAL, field_min REAL, field_max REAL,
    events_min REAL, events_max REAL, confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS series_name(series_id TEXT, year_from INTEGER, year_to INTEGER, name TEXT);
CREATE TABLE IF NOT EXISTS series_link(series_id TEXT, kind TEXT, other_id TEXT);
CREATE TABLE IF NOT EXISTS career_stage(id TEXT PRIMARY KEY, name TEXT, age_min REAL, age_max REAL,
    confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS career_path(id TEXT PRIMARY KEY, name TEXT, discipline TEXT, description TEXT,
    confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS career_path_step(path_id TEXT, step INTEGER, stage TEXT, series TEXT,
    age_min REAL, age_max REAL, years_min REAL, years_max REAL, advance_min REAL, advance_max REAL,
    gating TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS transition(from_id TEXT, to_id TEXT, frequency TEXT, share_min REAL, share_max REAL,
    age_min REAL, age_max REAL, gating TEXT, confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS advancement_factor(id TEXT PRIMARY KEY, name TEXT, description TEXT,
    confidence TEXT, sources TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS advancement_weight(factor_id TEXT, tier INTEGER, w_min REAL, w_max REAL);
CREATE TABLE IF NOT EXISTS economics(id TEXT PRIMARY KEY, topic TEXT, level TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS dataset(name TEXT PRIMARY KEY, url TEXT, coverage TEXT, accuracy TEXT,
    license TEXT, update_frequency TEXT, usefulness TEXT, decision TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS fact(entity_type TEXT, entity_id TEXT, attribute TEXT, value TEXT, min REAL,
    max REAL, unit TEXT, category TEXT, confidence TEXT, sources TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS team(source TEXT, year INTEGER, team TEXT, team_wiki TEXT, owner TEXT,
    manufacturer TEXT, cars INTEGER, full_time_cars INTEGER);
CREATE INDEX IF NOT EXISTS fact_entity ON fact(entity_id);
CREATE INDEX IF NOT EXISTS ledger_source ON ledger(source_id);
CREATE INDEX IF NOT EXISTS team_name ON team(team);
"""

FACT_KEYS = {"min", "max", "value", "category"}


def _load(path: Path) -> Any:
    if not path.exists():
        return None
    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _items(data) -> list[dict]:
    """Accept either a list of objects or an {id: object} mapping."""
    if data is None:
        return []
    if isinstance(data, dict):
        out = []
        for k, v in data.items():
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("id", k)
                out.append(v)
        return out
    return [x for x in data if isinstance(x, dict)]


def is_fact(v) -> bool:
    return isinstance(v, dict) and bool(FACT_KEYS & set(v))


def _num(x):
    try:
        return float(x) if x is not None and not isinstance(x, bool) else None
    except (TypeError, ValueError):
        return None


def _rng(doc: dict, key: str) -> tuple:
    v = doc.get(key)
    if is_fact(v):
        lo = _num(v.get("min", v.get("value")))
        hi = _num(v.get("max", v.get("value")))
        return lo, hi
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v), float(v)
    return None, None


def walk_facts(entity_type: str, entity_id: str, doc: dict, prefix: str = "") -> Iterable[tuple]:
    for k, v in doc.items():
        name = f"{prefix}{k}"
        if is_fact(v):
            val = v.get("value")
            yield (entity_type, entity_id, name, json.dumps(val) if val is not None else None,
                   _num(v.get("min")), _num(v.get("max")), v.get("unit"), v.get("category"),
                   v.get("confidence"), json.dumps(v.get("sources") or []), v.get("notes"))
        elif isinstance(v, dict) and k not in ("sources",):
            yield from walk_facts(entity_type, entity_id, v, prefix=name + ".")


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def build_knowledge(conn: sqlite3.Connection, directory: Path) -> dict:
    """Load every knowledge file in ``directory`` into ``conn``. Returns row counts."""
    conn.executescript(SCHEMA)
    counts: dict[str, int] = {}
    facts: list[tuple] = []

    for sid, s in (_load(directory / "sources.json") or {}).items():
        conn.execute("INSERT OR REPLACE INTO source VALUES (?,?,?,?,?,?,?,?)",
                     (sid, s.get("name"), s.get("url"), s.get("kind"), s.get("reliability"), s.get("license"),
                      s.get("accessed"), s.get("notes")))
    for u in _items(_load(directory / "unavailable.json")):
        conn.execute("INSERT INTO source_unavailable VALUES (?,?,?,?,?)",
                     (u.get("source"), u.get("url"), u.get("reason"), u.get("checked"), u.get("replacement_source")))
    for e in _load(directory / "ledger.jsonl") or []:
        conn.execute("INSERT INTO ledger(source_id,url,info,accessed,reliability,confidence,notes,entities) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (e.get("source"), e.get("url"), e.get("info"), e.get("accessed"), e.get("reliability"),
                      e.get("confidence"), e.get("notes"), _j(e.get("entities") or [])))

    for b in _items(_load(directory / "sanctioning_bodies.json")):
        conn.execute("INSERT OR REPLACE INTO sanctioning_body VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (b["id"], b.get("name"), b.get("abbrev"), b.get("country"), b.get("founded"), b.get("defunct"),
                      b.get("website"), b.get("scope"), b.get("confidence"), _j(b.get("sources") or []), _j(b)))
        facts += walk_facts("sanctioning_body", b["id"], b)

    for c in _items(_load(directory / "car_classes.json")):
        hp, wt, cost = _rng(c, "horsepower"), _rng(c, "weight_lb"), _rng(c, "new_car_cost_usd")
        conn.execute("INSERT OR REPLACE INTO car_class VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (c["id"], c.get("name"), c.get("discipline"), _s(c.get("chassis")), _s(c.get("drivetrain")),
                      _s(c.get("engine")), *hp, *wt, *cost, c.get("confidence"), _j(c.get("sources") or []), _j(c)))
        facts += walk_facts("car_class", c["id"], c)

    for s in _items(_load(directory / "series.json")):
        years = s.get("years") or {}
        age, cost = _rng(s, "typical_age"), _rng(s, "annual_cost_usd")
        field, events = _rng(s, "field_size"), _rng(s, "season_events")
        conn.execute("INSERT OR REPLACE INTO series_info VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (s["id"], s.get("name"), s.get("sanctioning_body"), s.get("discipline"), s.get("car_class"),
                      s.get("level"), s.get("game_tier"), s.get("scope"), _j(s.get("regions") or []),
                      years.get("from") if isinstance(years, dict) else None,
                      years.get("to") if isinstance(years, dict) else None,
                      s.get("game_template"), s.get("history_source"), _s(s.get("team_structure")),
                      _s(s.get("equipment_ownership")), _s(s.get("licensing")), *age, *cost, *field, *events,
                      s.get("confidence"), _j(s.get("sources") or []), _j(s)))
        for n in s.get("names_by_year") or []:
            conn.execute("INSERT INTO series_name VALUES (?,?,?,?)", (s["id"], n.get("from"), n.get("to"), n.get("name")))
        for kind, key in (("feeder", "feeder_series"), ("next", "next_steps")):
            for other in s.get(key) or []:
                if isinstance(other, str):
                    conn.execute("INSERT INTO series_link VALUES (?,?,?)", (s["id"], kind, other))
        facts += walk_facts("series", s["id"], s)

    for st in _items(_load(directory / "career_stages.json")):
        a = _rng(st, "age_range")
        conn.execute("INSERT OR REPLACE INTO career_stage VALUES (?,?,?,?,?,?,?)",
                     (st["id"], st.get("name"), *a, st.get("confidence"), _j(st.get("sources") or []), _j(st)))
        facts += walk_facts("career_stage", st["id"], st)

    for p in _items(_load(directory / "career_paths.json")):
        conn.execute("INSERT OR REPLACE INTO career_path VALUES (?,?,?,?,?,?,?)",
                     (p["id"], p.get("name"), p.get("discipline"), p.get("description"), p.get("confidence"),
                      _j(p.get("sources") or []), _j(p)))
        for i, step in enumerate(p.get("steps") or [], start=1):
            conn.execute("INSERT INTO career_path_step VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (p["id"], step.get("order", i), step.get("stage"), _j(step.get("series") or []),
                          *_rng(step, "typical_age"), *_rng(step, "typical_years"), *_rng(step, "advance_share"),
                          _j(step.get("gating") or {}), step.get("notes")))
        facts += walk_facts("career_path", p["id"], {k: v for k, v in p.items() if k != "steps"})

    for t in _items(_load(directory / "transitions.json")):
        conn.execute("INSERT INTO transition VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (t.get("from"), t.get("to"), t.get("frequency"), *_rng(t, "share_of_movers"),
                      *_rng(t, "typical_age"), _j(t.get("gating") or {}), t.get("confidence"),
                      _j(t.get("sources") or []), _j(t)))

    for f in _items(_load(directory / "advancement_factors.json")):
        conn.execute("INSERT OR REPLACE INTO advancement_factor VALUES (?,?,?,?,?,?)",
                     (f["id"], f.get("name"), _s(f.get("description")), f.get("confidence"),
                      _j(f.get("sources") or []), _j(f)))
        for tier, w in (f.get("weight_by_level") or {}).items():
            lo, hi = (_num(w.get("min", w.get("mid", w.get("value")))), _num(w.get("max", w.get("mid", w.get("value"))))) \
                if isinstance(w, dict) else (_num(w), _num(w))
            try:
                conn.execute("INSERT INTO advancement_weight VALUES (?,?,?,?)", (f["id"], int(str(tier).lstrip("T")), lo, hi))
            except ValueError:
                continue

    econ = _load(directory / "economics.json")
    for i, e in enumerate(_items(econ)):
        eid = e.get("id") or f"econ:{i}"
        conn.execute("INSERT OR REPLACE INTO economics VALUES (?,?,?,?)", (eid, e.get("topic"), str(e.get("level")), _j(e)))
        facts += walk_facts("economics", eid, e)

    for d in _items(_load(directory / "datasets.json")):
        conn.execute("INSERT OR REPLACE INTO dataset VALUES (?,?,?,?,?,?,?,?,?)",
                     (d.get("name") or d.get("id"), d.get("url"), _s(d.get("coverage")), _s(d.get("accuracy")),
                      _s(d.get("license")), _s(d.get("update_frequency")), _s(d.get("usefulness")),
                      _s(d.get("decision")), _s(d.get("notes"))))

    conn.executemany("INSERT INTO fact VALUES (?,?,?,?,?,?,?,?,?,?,?)", facts)
    for table in ("source", "source_unavailable", "ledger", "sanctioning_body", "car_class", "series_info",
                  "career_stage", "career_path", "career_path_step", "transition", "advancement_factor",
                  "economics", "dataset", "fact"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def build_teams(conn: sqlite3.Connection) -> int:
    """HistoricalTeam rows derived from the season documents already in the database."""
    conn.executescript(SCHEMA)
    rows = []
    for source, year, doc in conn.execute("SELECT source, year, doc FROM season").fetchall():
        for t in json.loads(doc).get("teams") or []:
            cars = t.get("cars") or []
            rows.append((source, year, t.get("team"), t.get("team_wiki"), t.get("owner"), t.get("manufacturer"),
                         len(cars), sum(1 for c in cars if c.get("full_time"))))
    conn.executemany("INSERT INTO team VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def _s(v):
    """Text column from a value that may be a ranged fact or a list."""
    if v is None or isinstance(v, str):
        return v
    if is_fact(v):
        return v.get("category") or v.get("value") if isinstance(v.get("category") or v.get("value"), str) \
            else json.dumps(v)
    return json.dumps(v, ensure_ascii=False)
