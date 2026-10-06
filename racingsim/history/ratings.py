"""Ratings from real results (OOTP's "calculate ratings from historical stats").

For real NASCAR drivers the race-by-race results (start, finish, laps, laps led, status, track)
say more than season standings: who qualifies better than they race, who leads laps, who gains
spots, who wrecks, and who is a superspeedway or road-course specialist. ``profiles`` turns a
driver's results up to the start season into skill offsets (``racingsim.world.skills``):

* qualifying vs race: average start percentile minus average finish percentile;
* speed: share of laps led;
* racecraft: positions gained from start to finish on running finishes;
* consistency / car control: crash-out rate (mechanical failures are the car's);
* track types: finish percentile on each kind of track vs the driver's overall average,
  plus experience from the number of races run there.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from functools import lru_cache
from typing import Optional

from ..util import clamp

SOURCES = ("nascar_cup", "nascar_xfinity", "nascar_trucks")
CRASH_WORDS = ("crash", "accident", "wreck", "spun", "collision")


def _track_type(name: str, length: Optional[float], surface: Optional[str]) -> str:
    s = (surface or "").lower()
    n = (name or "").lower()
    if "dirt" in s:
        return "dirt"
    if "road" in s or "road" in n or "glen" in n or "sonoma" in n or "riverside" in n:
        return "road"
    if ("daytona" in n or "talladega" in n) and (length or 0) >= 2.4:
        return "superspeedway"
    if (length or 0) > 1.0:
        return "intermediate"
    return "short"


@lru_cache(maxsize=4)
def _rows(db_path: str, upto: int) -> dict[str, list[tuple]]:
    """name -> [(track type, start pct, finish pct, led share, crashed, running, gained)] for races <= upto."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'race_result'").fetchone():
            return {}
        info = {(s, y, r): (t, ln, sf) for s, y, r, t, ln, sf in conn.execute(
            "SELECT source, year, round, track, track_length_mi, surface FROM race_info")}
        races: dict[tuple, list] = defaultdict(list)
        q = ("SELECT source, year, round, pos, start, driver, laps, status, led FROM race_result "
             f"WHERE year <= ? AND year >= ? AND source IN ({','.join('?' * len(SOURCES))})")
        for row in conn.execute(q, (upto, upto - 12, *SOURCES)):
            races[row[:3]].append(row[3:])
    finally:
        conn.close()
    out: dict[str, list[tuple]] = defaultdict(list)
    for key, rows in races.items():
        n = len(rows)
        if n < 8:
            continue
        name, length, surface = info.get(key, ("", None, None))
        tt = _track_type(name, length, surface)
        max_laps = max((r[3] or 0) for r in rows) or 1
        for pos, start, driver, laps, status, led in rows:
            if not driver or not pos:
                continue
            fin = 1 - (pos - 1) / (n - 1)
            st = 1 - ((start or n) - 1) / (n - 1)
            stat = (status or "").lower()
            crashed = any(w in stat for w in CRASH_WORDS)
            running = stat.startswith("running") or (laps or 0) >= max_laps
            gained = ((start or pos) - pos) / n if running else 0.0
            out[driver].append((tt, st, fin, (led or 0) / max_laps, crashed, running, gained))
    return dict(out)


def profile(db_path: str, name: str, upto: int) -> Optional[dict]:
    """Skill offsets and track experience from a real driver's results; None if too few races."""
    rows = _rows(db_path, upto).get(name)
    if not rows or len(rows) < 10:
        return None
    n = len(rows)
    fin = sum(r[2] for r in rows) / n
    st = sum(r[1] for r in rows) / n
    led = sum(r[3] for r in rows) / n
    crash = sum(r[4] for r in rows) / n
    gained = sum(r[6] for r in rows if r[5]) / max(1, sum(1 for r in rows if r[5]))
    weight = min(1.0, n / 60)          # small samples move ratings less
    sk = {
        "qualifying": clamp((st - fin) * 30, -8, 8) * weight,
        "speed": clamp((led - 0.02) * 110, -4, 10) * weight,
        "racecraft_bonus": clamp(gained * 40, -6, 6) * weight,
        "car_control": clamp((0.07 - crash) * 60, -6, 4) * weight,
    }
    by_type: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_type[r[0]].append(r[2])
    tracks, exp = {}, {}
    for tt, fins in by_type.items():
        exp[tt] = round(1 - math.exp(-len(fins) / 15), 3)
        if len(fins) >= 6:
            tracks[tt] = clamp((sum(fins) / len(fins) - fin) * 25, -6, 6) * min(1.0, len(fins) / 25)
    return {"skills": sk, "track_talent": tracks, "track_exp": exp, "races": n}


def apply(d, prof: dict) -> None:
    """Blend a results profile into a driver's skills (keeps a little of the random profile)."""
    from ..world import skills as S
    S.ensure(d)
    sk = prof["skills"]
    for k in ("qualifying", "speed", "car_control"):
        d.skills[k] = round(0.3 * d.skills.get(k, 0.0) + sk[k], 2)
    # Racecraft is a v1 trait (0-100): nudge it by positions gained.
    d.racecraft = clamp(d.racecraft + sk["racecraft_bonus"] * 2.5, 5, 95)
    for tt, v in prof["track_talent"].items():
        d.skills[f"tt_{tt}"] = round(v, 2)
    for tt, v in prof["track_exp"].items():
        d.track_skill[tt] = max(d.track_skill.get(tt, 0.0), v)
