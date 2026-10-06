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
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..util import DATA_DIR

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
    def __init__(self, seasons: dict[str, dict[int, dict]], drivers: dict[str, dict]):
        self.seasons = seasons          # data dir -> year -> season dict
        self.drivers = drivers          # wiki title -> bio
        self._sched_cache: dict = {}
        self._careers: Optional[dict] = None

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, directory: Path = HISTORY_DIR) -> Optional["HistoryDB"]:
        if not directory.exists():
            return None
        seasons: dict[str, dict[int, dict]] = {}
        for sub in sorted(p for p in directory.iterdir() if p.is_dir()):
            for f in sorted(sub.glob("*.json")):
                try:
                    year = int(f.stem)
                except ValueError:
                    continue
                with open(f, encoding="utf-8") as fh:
                    seasons.setdefault(sub.name, {})[year] = json.load(fh)
        drivers: dict[str, dict] = {}
        for f in sorted(directory.glob("drivers*.json")):
            with open(f, encoding="utf-8") as fh:
                for k, v in json.load(fh).items():
                    drivers.setdefault(k, v)
        if not seasons:
            return None
        return cls(seasons, drivers)

    @classmethod
    def load_default(cls) -> Optional["HistoryDB"]:
        return _cached_default()

    # ------------------------------------------------------------------ queries
    def season(self, template_key: str, year: int) -> Optional[dict]:
        for d, lo, hi in SOURCES.get(template_key, []):
            if lo <= year <= hi and year in self.seasons.get(d, {}):
                return self.seasons[d][year]
        return None

    def years(self) -> list[int]:
        return sorted(self.seasons.get("nascar_cup", {}))

    def bio(self, wiki: Optional[str]) -> dict:
        return self.drivers.get(wiki or "", {}) if wiki else {}

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
        season = self.season(template_key, year)
        out = None
        if season and season.get("schedule"):
            ids = []
            races = [r for r in season["schedule"] if not r.get("cancelled")]
            for race in races:
                tid = match_track(tracks, race.get("track"), race.get("city"), race.get("state"),
                                  race.get("race") or "", year)
                if tid:
                    ids.append(tid)
            if len(ids) >= max(3, 0.6 * len(races)):
                out = ids
        self._sched_cache[key] = out
        return out

    # ------------------------------------------------------------------ careers
    def careers(self) -> dict[str, list[dict]]:
        """wiki title -> list of seasons {year, template, tier, pos, n, wins, starts, team} (all series)."""
        if self._careers is not None:
            return self._careers
        out: dict[str, list[dict]] = {}
        for tpl, sources in SOURCES.items():
            for d, lo, hi in sources:
                for year, season in self.seasons.get(d, {}).items():
                    if not (lo <= year <= hi):
                        continue
                    st = season.get("standings") or []
                    team_of = {}
                    for t in season.get("teams") or []:
                        for c in t.get("cars", []):
                            for dr in c.get("drivers", []):
                                if dr.get("wiki") and (c.get("full_time") or dr["wiki"] not in team_of):
                                    team_of[dr["wiki"]] = t.get("team") or ""
                    regulars = [r for r in st if (r.get("starts") or 0) >= 0.5 * max(1, len(season.get("schedule") or [])) ]
                    n = max(len(regulars), 1)
                    for r in st:
                        w = r.get("wiki")
                        if not w:
                            continue
                        out.setdefault(w, []).append({
                            "year": year, "template": tpl, "tier": TEMPLATE_TIER[tpl], "pos": r.get("pos"),
                            "n": n, "field": len(st), "wins": r.get("wins") or 0, "starts": r.get("starts"),
                            "top5": r.get("top5"), "top10": r.get("top10"), "points": r.get("points"),
                            "series_name": season.get("official_name"), "team": team_of.get(w, ""),
                        })
        for w in out:
            out[w].sort(key=lambda x: (x["year"], -x["tier"]))
        self._careers = out
        return out


@lru_cache(maxsize=1)
def _cached_default() -> Optional[HistoryDB]:
    return HistoryDB.load(HISTORY_DIR)


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
