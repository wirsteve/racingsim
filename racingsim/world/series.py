"""The racing pyramid: series templates (data/series.json) instantiated onto real tracks.

Series names are fictional abstractions of real-world structures (see
LICENSING_IP_REVIEW.md). Each template describes one *rung type*; it may be
instantiated once nationally, once per macro-region (regional tours), or once per
local track (weekly divisions), which is what produces a wide base of hundreds of
local championships under a narrow professional top.
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
    macro_hint: str = ""             # regions where a local division is common (others: rarer)
    note: str = ""

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


class Pyramid:
    def __init__(self, templates: list[SeriesTemplate], series: list[Series],
                 crown_jewels: list[CrownJewel], tier_names: dict[int, str]):
        self.templates = {t.key: t for t in templates}
        self.series = {s.id: s for s in series}
        self.crown_jewels = crown_jewels
        self.tier_names = tier_names

    def by_tier(self, tier: int) -> list[Series]:
        return [s for s in self.series.values() if s.tier == tier]

    def by_discipline(self, discipline: str) -> list[Series]:
        return [s for s in self.series.values() if s.discipline == discipline]

    def max_tier(self) -> int:
        return max(t.tier for t in self.templates.values())

    def get(self, series_id: str) -> Series:
        return self.series[series_id]


def _short_track_name(name: str) -> str:
    for suffix in (" Motor Speedway", " International Speedway", " Speedway", " Raceway Park",
                   " Raceway", " Motorplex", " Fairgrounds", " Motorsports Park", " Race Track"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def load_templates() -> tuple[list[SeriesTemplate], list[dict], dict[int, str]]:
    raw = load_json("series.json")
    known = set(SeriesTemplate.__dataclass_fields__)
    templates = [SeriesTemplate(**{k: v for k, v in t.items() if k in known}) for t in raw["series"]]
    tiers = {int(t["level"]): t["name"] for t in raw["tiers"]}
    return templates, raw.get("crown_jewels", []), tiers


def build_pyramid(tracks: TrackDatabase, geo: Geography, rng: random.Random,
                  templates: Optional[list[SeriesTemplate]] = None) -> Pyramid:
    loaded, jewels_raw, tier_names = load_templates()
    templates = templates or loaded
    series: list[Series] = []
    for tpl in templates:
        if tpl.scope == "track":
            series.extend(_instantiate_local(tpl, tracks, geo))
        elif tpl.scope == "region":
            series.extend(_instantiate_regional(tpl, tracks, geo, rng))
        else:
            series.append(_instantiate_national(tpl, tracks, rng))
    jewels = []
    for j in jewels_raw:
        if j["track_id"] in tracks:
            jewels.append(CrownJewel(**j))
    return Pyramid(templates, [s for s in series if s.schedule], jewels, tier_names)


def _eligible(tpl: SeriesTemplate, tracks: TrackDatabase, *, macro_regions=None, geo=None) -> list[Track]:
    pool = []
    for venue in tpl.venues:
        pool.extend(tracks.suitable(venue, levels=set(tpl.venue_levels) or None,
                                    countries=set(tpl.countries) or None))
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


def _instantiate_local(tpl: SeriesTemplate, tracks: TrackDatabase, geo: Geography) -> list[Series]:
    out = []
    hint = {m.strip() for m in tpl.macro_hint.split(",") if m.strip()}
    for t in _eligible(tpl, tracks, macro_regions=hint or None, geo=geo):
        if t.facts.lat is None:
            continue
        out.append(Series(
            id=f"{tpl.key}@{t.id}",
            template=tpl,
            name=tpl.name.replace("{track}", _short_track_name(t.name)),
            region_key=t.id,
            schedule=[t.id] * tpl.events,
            anchor_lat=t.facts.lat,
            anchor_lon=t.facts.lon,
        ))
    return out


def _instantiate_regional(tpl: SeriesTemplate, tracks: TrackDatabase, geo: Geography,
                          rng: random.Random) -> list[Series]:
    out = []
    macros = tpl.macro_regions or geo.macro_regions()
    for macro in macros:
        pool = _eligible(tpl, tracks, macro_regions={macro}, geo=geo)
        if len(pool) < 2:
            continue
        pool.sort(key=lambda t: (-t.profile.prestige, t.id))
        top = pool[: max(tpl.events, 6)]
        schedule = [top[i % len(top)].id for i in range(tpl.events)]
        rng.shuffle(schedule)
        lat = sum(tracks.get(s).facts.lat for s in schedule) / len(schedule)
        lon = sum(tracks.get(s).facts.lon for s in schedule) / len(schedule)
        label = macro.replace("_", " ").title()
        out.append(Series(
            id=f"{tpl.key}@{macro}", template=tpl,
            name=tpl.name.replace("{region}", label), region_key=macro,
            schedule=schedule, anchor_lat=lat, anchor_lon=lon,
        ))
    return out


def _instantiate_national(tpl: SeriesTemplate, tracks: TrackDatabase, rng: random.Random) -> Series:
    pool = _eligible(tpl, tracks)
    pool.sort(key=lambda t: (-t.profile.prestige, t.id))
    top = pool[: max(tpl.events, 8)]
    schedule = [top[i % len(top)].id for i in range(tpl.events)] if top else []
    rng.shuffle(schedule)
    if schedule:
        lat = sum(tracks.get(s).facts.lat or 0 for s in schedule) / len(schedule)
        lon = sum(tracks.get(s).facts.lon or 0 for s in schedule) / len(schedule)
    else:
        lat = lon = 0.0
    return Series(id=tpl.key, template=tpl, name=tpl.name, region_key=None,
                  schedule=schedule, anchor_lat=lat, anchor_lon=lon)
