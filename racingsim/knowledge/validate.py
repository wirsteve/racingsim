"""Validation of the compiled database: schema, references, ranges and cross-source checks.

Returns a list of ``Issue``s; ``error`` issues fail ``python -m racingsim data validate``.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass

CONFIDENCE = {"high", "medium", "low"}


@dataclass
class Issue:
    level: str      # error | warning | info
    check: str
    entity: str
    detail: str


def validate(conn: sqlite3.Connection) -> list[Issue]:
    out: list[Issue] = []
    out += _ranges_and_confidence(conn)
    out += _references(conn)
    out += _history(conn)
    out += _tracks(conn)
    out += _conflicts(conn)
    return out


def _ids(conn, table: str) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT id FROM {table}")}


def _ranges_and_confidence(conn) -> list[Issue]:
    out = []
    for etype, eid, attr, lo, hi, conf, sources in conn.execute(
            "SELECT entity_type, entity_id, attribute, min, max, confidence, sources FROM fact"):
        if lo is not None and hi is not None and lo > hi:
            out.append(Issue("error", "range", eid, f"{attr}: min {lo} > max {hi}"))
        if conf is not None and conf not in CONFIDENCE:
            out.append(Issue("warning", "confidence", eid, f"{attr}: confidence {conf!r}"))
        if conf is None:
            out.append(Issue("info", "confidence", eid, f"{attr}: no confidence given"))
    for table in ("series_info", "sanctioning_body", "car_class", "career_path", "advancement_factor"):
        for eid, conf, sources in conn.execute(f"SELECT id, confidence, sources FROM {table}"):
            if conf not in CONFIDENCE:
                out.append(Issue("warning", "confidence", eid, f"entity confidence {conf!r}"))
            if not json.loads(sources or "[]"):
                out.append(Issue("warning", "provenance", eid, "no sources listed"))
    return out


def _references(conn) -> list[Issue]:
    out = []
    sources = _ids(conn, "source")
    series = _ids(conn, "series_info")
    bodies = _ids(conn, "sanctioning_body")
    classes = _ids(conn, "car_class")
    from ..world.series import load_templates
    templates = {t.key for t in load_templates()[0]}
    hist_sources = {r[0] for r in conn.execute("SELECT DISTINCT source FROM season")}
    for sid, body, cls, tpl, hsrc in conn.execute(
            "SELECT id, sanctioning_body, car_class, game_template, history_source FROM series_info"):
        if body and body not in bodies:
            out.append(Issue("warning", "reference", sid, f"unknown sanctioning body {body}"))
        if cls and cls not in classes:
            out.append(Issue("warning", "reference", sid, f"unknown car class {cls}"))
        if tpl and tpl not in templates:
            out.append(Issue("error", "reference", sid, f"unknown game_template {tpl}"))
        if hsrc and hsrc not in hist_sources:
            out.append(Issue("info", "reference", sid, f"history_source {hsrc} has no season data yet"))
    for sid, kind, other in conn.execute("SELECT series_id, kind, other_id FROM series_link"):
        if other not in series:
            out.append(Issue("info", "reference", sid, f"{kind} link to unknown series {other}"))
    for pid, step, ser in conn.execute("SELECT path_id, step, series FROM career_path_step"):
        for s in json.loads(ser or "[]"):
            if isinstance(s, str) and s.startswith("series:") and s not in series:
                out.append(Issue("info", "reference", pid, f"step {step}: unknown series {s}"))
    used = Counter()
    for (srcs,) in conn.execute("SELECT sources FROM fact UNION ALL SELECT sources FROM series_info"):
        for s in json.loads(srcs or "[]"):
            used[s] += 1
            if s not in sources and s.startswith("src:"):
                out.append(Issue("warning", "provenance", s, "source id used but not defined in sources.json"))
    return _dedupe(out)


def _history(conn) -> list[Issue]:
    out = []
    for source, year, doc in conn.execute("SELECT source, year, doc FROM season"):
        d = json.loads(doc)
        sched = [r for r in d.get("schedule") or [] if not r.get("cancelled")]
        winners = Counter(r.get("winner_wiki") or r.get("winner") for r in sched if r.get("winner"))
        st_wins = sum(r.get("wins") or 0 for r in d.get("standings") or [])
        if winners and st_wins and abs(sum(winners.values()) - st_wins) > max(1, 0.05 * st_wins):
            out.append(Issue("warning", "history", f"{source}/{year}",
                             f"schedule winners {sum(winners.values())} vs standings wins {st_wins}"))
    total, matched = conn.execute(
        "SELECT COUNT(*), SUM(track_id IS NOT NULL) FROM race WHERE cancelled=0").fetchone()
    if total:
        level = "warning" if matched / total < 0.95 else "info"
        out.append(Issue(level, "history", "race.track_id", f"{matched}/{total} races matched to a track"))
    st, bio = conn.execute("SELECT COUNT(DISTINCT s.wiki), COUNT(DISTINCT d.wiki) FROM standing s "
                           "LEFT JOIN driver d ON d.wiki = s.wiki WHERE s.wiki IS NOT NULL").fetchone()
    out.append(Issue("info", "history", "driver", f"{bio}/{st} drivers with standings have a bio"))
    return out


def _tracks(conn) -> list[Issue]:
    out = []
    rows = conn.execute("SELECT id, name, country, latlon, track_type, surface, length_mi FROM track_facts").fetchall()
    pts = []
    for tid, name, country, latlon, ttype, surface, length in rows:
        lat, lon = json.loads(latlon or "[null, null]")
        if lat is None:
            out.append(Issue("warning", "track", tid, "no coordinates"))
            continue
        if country in ("USA", "CAN") and not (18 <= lat <= 72 and -170 <= lon <= -50):
            out.append(Issue("error", "track", tid, f"coordinates {lat},{lon} outside North America"))
        pts.append((tid, name, lat, lon, ttype, surface or f"unknown:{tid}", length))
    grid = defaultdict(list)
    for p in pts:
        grid[(round(p[2], 1), round(p[3], 1))].append(p)
    for a in pts:
        for dx in (-0.1, 0, 0.1):
            for dy in (-0.1, 0, 0.1):
                for b in grid.get((round(a[2] + dx, 1), round(a[3] + dy, 1)), []):
                    if (a[0] < b[0] and a[4:6] == b[4:6] and _same_length(a[6], b[6]) and _km(a, b) < 0.4  # sister layouts differ in type/surface
                            and _similar(a[1], b[1])):
                        out.append(Issue("warning", "track-duplicate", a[0], f"possible duplicate of {b[0]}"))
    return out


def _conflicts(conn) -> list[Issue]:
    """Same entity + attribute reported with non-overlapping ranges (different sources disagree)."""
    out = []
    groups = defaultdict(list)
    for eid, attr, lo, hi, srcs in conn.execute(
            "SELECT entity_id, attribute, min, max, sources FROM fact WHERE min IS NOT NULL AND max IS NOT NULL"):
        groups[(eid, attr)].append((lo, hi, srcs))
    for (eid, attr), vals in groups.items():
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                (a_lo, a_hi, _), (b_lo, b_hi, _) = vals[i], vals[j]
                if a_hi < b_lo or b_hi < a_lo:
                    out.append(Issue("warning", "conflict", eid, f"{attr}: [{a_lo},{a_hi}] vs [{b_lo},{b_hi}]"))
    return out


def _same_length(x, y) -> bool:
    return x is None or y is None or abs(x - y) <= 0.25 * max(x, y)


def _km(a, b) -> float:
    dlat = math.radians(b[2] - a[2])
    dlon = math.radians(b[3] - a[3]) * math.cos(math.radians(a[2]))
    return 6371 * math.hypot(dlat, dlon)


def _similar(x: str, y: str) -> bool:
    from ..history.db import _tokens
    tx, ty = _tokens(x), _tokens(y)
    return bool(tx & ty) or not tx or not ty


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen, out = set(), []
    for i in issues:
        k = (i.level, i.check, i.entity, i.detail)
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out
