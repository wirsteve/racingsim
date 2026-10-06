"""The racing pyramid: series templates (data/series.json) instantiated onto real tracks.

Each template describes one *rung type*; it may be instantiated once nationally,
once per macro-region (regional tours), or once per local track (weekly divisions),
which is what produces a wide base of hundreds of local championships under a
narrow professional top.

Templates carry **eras** (data/series_eras.json): the real series name in each
season from 1995 on (e.g. "NASCAR Winston Cup Series" 1995-2003 ... "NASCAR Cup
Series" 2020+), and the years a rung did not exist. The pyramid is refreshed each
season: series are renamed, rungs appear or go dormant, and venues open or close.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..tracks import Track, TrackDatabase
from ..util import load_json
from .regions import Geography


@dataclass
class SeriesTemplate:
    key: str
    name: str
    discipline: str
    tier: int
    scope: str                       # "track" | "region" | "national"
    venues: list[str]
    min_age: int
    max_age: Optional[int]
    season_cost: float               # USD to run a full competitive season (car side)
    events: int
    field_size: int
    prestige: int
    visibility: int                  # scouting visibility 0-100
    car_weight: float                # share of performance driven by equipment
    team_based: bool = False
    pro: bool = False                # funded seats pay salaries
    cars: int = 0                    # team-based: number of full-time cars
    drivers_per_car: int = 1
    pro_am: bool = False             # sports-car style: one pro + one paying amateur per car
    venue_levels: list[str] = field(default_factory=list)
    macro_regions: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    purse_win: float = 0.0
    salary_top: float = 0.0
    champion_scholarship: float = 0.0
    license_min_starts: int = 0      # starts at tier-1 or above needed to be approved
    license_min_tier: int = 0
    typical_age: list[int] = field(default_factory=lambda: [16, 40])
    regional_draw_mi: float = 0.0    # for track-scope: how far racers will tow weekly
    full_age: Optional[int] = None   # below this age: only ovals <= 1.25 mi and road courses
    selection: dict = field(default_factory=dict)  # owner weighting override for seat decisions
    team_funding_floor: Optional[float] = None
    macro_hint: str = ""             # regions where a local division is common (others: rarer)
    note: str = ""
    eras: list = field(default_factory=list)          # [{from, to, name}] real names by season
    region_names: dict = field(default_factory=dict)  # macro -> [{from, to, name}]

    def era(self, year: int) -> Optional[dict]:
        for e in self.eras:
            if e["from"] <= year <= e["to"]:
                return e
        if self.eras:
            last = max(self.eras, key=lambda e: e["to"])
            if year > last["to"]:
                return last  # beyond the researched range: the latest era continues
            first = min(self.eras, key=lambda e: e["from"])
            if year < first["from"]:
                return first
        return None

    def exists_in(self, year: int) -> bool:
        if not self.eras:
            return True
        e = self.era(year)
        return e is not None and e.get("name") is not None

    def display_name(self, year: int, label: str = "", macro: Optional[str] = None) -> str:
        name = self.name
        e = self.era(year)
        if e and e.get("name"):
            name = e["name"]
        if macro and macro in self.region_names:
            spans = self.region_names[macro]
            y = min(year, max(r["to"] for r in spans))
            for r in spans:
                if r["from"] <= y <= r["to"] and r.get("name"):
                    return r["name"]
        return name.replace("{track}", label).replace("{region}", label)

    def age_allows_track(self, age: int, track: Track) -> bool:
        """NASCAR-style age-by-track-type approval (research A, section 3)."""
        if self.full_age is None or age >= self.full_age:
            return True
        if track.facts.is_road:
            return True
        return (track.facts.length_mi or 0) <= 1.25


@dataclass
class Series:
    id: str
    template: SeriesTemplate
    name: str
    region_key: Optional[str]        # macro region for regional series, track id for local
    schedule: list[str]              # track ids, in calendar order
    anchor_lat: float = 0.0
    anchor_lon: float = 0.0
    label: str = ""                  # track short name / region label used in the name
    dormant: bool = False            # rung or venue does not exist this season
    real_schedule: bool = False      # schedule taken from the real calendar of that year

    # Convenience pass-throughs
    @property
    def tier(self) -> int:
        return self.template.tier

    @property
    def discipline(self) -> str:
        return self.template.discipline

    @property
    def scope(self) -> str:
        return self.template.scope


@dataclass
class CrownJewel:
    key: str
    name: str
    track_id: str
    discipline: str
    min_tier: int
    max_tier: int
    entrants: int
    visibility: int
    purse_win: float
    note: str = ""
    week: int = 0  # season week (1-30) the event runs
    since: int = 0  # first year the event was held

    def exists_in(self, year: int) -> bool:
        return year >= self.since


class Pyramid:
    def __init__(self, templates: list[SeriesTemplate], series: list[Series],
                 crown_jewels: list[CrownJewel], tier_names: dict[int, str], year: int = 2026):
        self.templates = {t.key: t for t in templates}
        self.series = {s.id: s for s in series}
        self.all_crown_jewels = crown_jewels
        self.tier_names = tier_names
        self.year = year

    @property
    def crown_jewels(self) -> list[CrownJewel]:
        return [cj for cj in self.all_crown_jewels if cj.exists_in(self.year)]

    def active(self) -> list[Series]:
        return [s for s in self.series.values() if not s.dormant]

    def by_tier(self, tier: int) -> list[Series]:
        return [s for s in self.active() if s.tier == tier]

    def by_discipline(self, discipline: str) -> list[Series]:
        return [s for s in self.active() if s.discipline == discipline]

    def max_tier(self) -> int:
        return max(t.tier for t in self.templates.values())

    def get(self, series_id: str) -> Series:
        return self.series[series_id]

    def refresh(self, year: int, tracks: TrackDatabase, geo: Geography, rng: random.Random,
                schedule_provider=None) -> tuple[list[Series], list[Series]]:
        """Move the pyramid to ``year``. Returns (newly active series, newly dormant series)."""
        self.year = year
        born, died = [], []
        for tpl in self.templates.values():
            exists = tpl.exists_in(year)
            if tpl.scope == "track":
                eligible = {t.id: t for t in _eligible(tpl, tracks, year=year, geo=geo,
                                                       macro_regions=_hint(tpl) or None)}
                for t in eligible.values():
                    sid = f"{tpl.key}@{t.id}"
                    if sid not in self.series and exists and t.facts.lat is not None:
                        s = _local_series(tpl, t)
                        self.series[sid] = s
                        born.append(s)
                for s in [x for x in self.series.values() if x.template is tpl]:
                    alive = exists and s.region_key in eligible
                    _flip(s, alive, born, died)
            elif tpl.scope == "region":
                for macro in (tpl.macro_regions or geo.macro_regions()):
                    sid = f"{tpl.key}@{macro}"
                    sched = _regional_schedule(tpl, tracks, geo, rng, macro, year) if exists else []
                    if sid not in self.series:
                        if not sched:
                            continue
                        s = _make_regional(tpl, tracks, macro, sched)
                        self.series[sid] = s
                        born.append(s)
                    s = self.series[sid]
                    if sched:
                        s.schedule = sched
                    _flip(s, exists and bool(sched), born, died)
            else:
                real = schedule_provider(tpl.key, year) if (schedule_provider and exists) else None
                sched = real or (_national_schedule(tpl, tracks, rng, year) if exists else [])
                if tpl.key not in self.series:
                    if not sched:
                        continue
                    s = Series(id=tpl.key, template=tpl, name=tpl.name, region_key=None, schedule=sched)
                    self.series[tpl.key] = s
                    born.append(s)
                s = self.series[tpl.key]
                if sched:
                    s.schedule = sched
                    s.real_schedule = bool(real)
                    pts = [tracks.get(x).facts for x in sched]
                    s.anchor_lat = sum(f.lat or 0 for f in pts) / len(pts)
                    s.anchor_lon = sum(f.lon or 0 for f in pts) / len(pts)
                _flip(s, exists and bool(sched), born, died)
        for s in self.series.values():
            s.name = s.template.display_name(year, s.label, s.region_key if s.scope == "region" else None)
        return born, died


def _flip(s: "Series", alive: bool, born: list, died: list) -> None:
    if alive and s.dormant:
        s.dormant = False
        born.append(s)
    elif not alive and not s.dormant:
        s.dormant = True
        died.append(s)


def _hint(tpl: SeriesTemplate) -> set[str]:
    return {m.strip() for m in tpl.macro_hint.split(",") if m.strip()}


def _short_track_name(name: str) -> str:
    for suffix in (" Motor Speedway", " International Speedway", " Speedway", " Raceway Park",
                   " Raceway", " Motorplex", " Fairgrounds", " Motorsports Park", " Race Track"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def load_templates() -> tuple[list[SeriesTemplate], list[dict], dict[int, str]]:
    raw = load_json("series.json")
    try:
        eras = load_json("series_eras.json").get("templates", {})
    except FileNotFoundError:
        eras = {}
    known = set(SeriesTemplate.__dataclass_fields__)
    templates = []
    for t in raw["series"]:
        tpl = SeriesTemplate(**{k: v for k, v in t.items() if k in known})
        e = eras.get(tpl.key, {})
        tpl.eras = e.get("eras", [])
        tpl.region_names = e.get("region_names", {})
        templates.append(tpl)
    tiers = {int(t["level"]): t["name"] for t in raw["tiers"]}
    return templates, raw.get("crown_jewels", []), tiers


def build_pyramid(tracks: TrackDatabase, geo: Geography, rng: random.Random,
                  templates: Optional[list[SeriesTemplate]] = None, year: int = 2026,
                  schedule_provider=None) -> Pyramid:
    loaded, jewels_raw, tier_names = load_templates()
    templates = templates or loaded
    known = set(CrownJewel.__dataclass_fields__)
    jewels = [CrownJewel(**{k: v for k, v in j.items() if k in known})
              for j in jewels_raw if j["track_id"] in tracks]
    pyramid = Pyramid(templates, [], jewels, tier_names, year)
    pyramid.refresh(year, tracks, geo, rng, schedule_provider)
    # Start-of-world series are not "new" in any narrative sense.
    for s in list(pyramid.series.values()):
        if s.dormant or not s.schedule:
            del pyramid.series[s.id]
    return pyramid


def _eligible(tpl: SeriesTemplate, tracks: TrackDatabase, *, macro_regions=None, geo=None,
              year: Optional[int] = None) -> list[Track]:
    pool = []
    for venue in tpl.venues:
        pool.extend(tracks.suitable(venue, levels=set(tpl.venue_levels) or None,
                                    countries=set(tpl.countries) or None, year=year))
    seen, out = set(), []
    for t in pool:
        if t.id in seen:
            continue
        if macro_regions and geo is not None:
            region = geo.regions.get(t.facts.region or "")
            if region is None or region.macro_region not in macro_regions:
                continue
        seen.add(t.id)
        out.append(t)
    return out


def _local_series(tpl: SeriesTemplate, t: Track) -> Series:
    label = _short_track_name(t.name)
    return Series(id=f"{tpl.key}@{t.id}", template=tpl, name=tpl.name.replace("{track}", label),
                  region_key=t.id, schedule=[t.id] * tpl.events, anchor_lat=t.facts.lat,
                  anchor_lon=t.facts.lon, label=label)


def _regional_schedule(tpl: SeriesTemplate, tracks: TrackDatabase, geo: Geography, rng: random.Random,
                       macro: str, year: int) -> list[str]:
    pool = _eligible(tpl, tracks, macro_regions={macro}, geo=geo, year=year)
    if len(pool) < 2:
        return []
    pool.sort(key=lambda t: (-t.profile.prestige, t.id))
    top = pool[: max(tpl.events, 6)]
    schedule = [top[i % len(top)].id for i in range(tpl.events)]
    rng.shuffle(schedule)
    return schedule


def _make_regional(tpl: SeriesTemplate, tracks: TrackDatabase, macro: str, schedule: list[str]) -> Series:
    lat = sum(tracks.get(s).facts.lat for s in schedule) / len(schedule)
    lon = sum(tracks.get(s).facts.lon for s in schedule) / len(schedule)
    label = macro.replace("_", " ").title()
    return Series(id=f"{tpl.key}@{macro}", template=tpl, name=tpl.name.replace("{region}", label),
                  region_key=macro, schedule=schedule, anchor_lat=lat, anchor_lon=lon, label=label)


def _national_schedule(tpl: SeriesTemplate, tracks: TrackDatabase, rng: random.Random, year: int) -> list[str]:
    pool = _eligible(tpl, tracks, year=year)
    # North American championships: the odd border crossing, never a European tour.
    home = [t for t in pool if t.facts.country in ("USA", "CAN")]
    pool = home if len(home) >= min(tpl.events, 8) else [t for t in pool if t.facts.country in ("USA", "CAN", "MEX")]
    pool.sort(key=lambda t: (-t.profile.prestige, t.id))
    top = pool[: max(tpl.events, 8)]
    schedule = [top[i % len(top)].id for i in range(tpl.events)] if top else []
    rng.shuffle(schedule)
    return schedule
