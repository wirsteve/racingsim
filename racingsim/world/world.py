"""World state container and initial ecosystem generation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..tracks import TrackDatabase
from ..util import clamp, load_json, weighted_choice
from .entities import ACTIVE, RETIRED, Driver, Manufacturer, Sponsor, Team
from .factory import (
    ability_for_tier, make_driver, make_manufacturers, make_sponsors, make_teams_for_series,
)
from .regions import Geography, Region
from .series import Pyramid, Series, build_pyramid


@dataclass
class WorldConfig:
    seed: int = 2026
    start_year: int = 2026
    population_scale: float = 1.0      # scales local/regional field fill (tests use < 1)
    # Local field fill vs nominal field size: there are more entry-level racers than
    # headline-division racers at every short track (research F 5.1).
    fill_by_tier: tuple = (1.0, 1.35, 0.85, 1.0, 1.0, 1.0, 1.0, 1.0)


@dataclass
class MarketState:
    """Per-off-season decisions made once per driver (not once per seat evaluated)."""
    expired: dict[int, int] = field(default_factory=dict)   # driver -> team whose deal expired
    switch_open: set[int] = field(default_factory=set)      # open to a sideways discipline move
    comeback_open: set[int] = field(default_factory=set)    # grassroots veterans open to a comeback
    queue: list = field(default_factory=list)               # open seats (heap) between open/close
    buckets: dict = field(default_factory=dict)             # candidate prefilter by tier
    signed: set[int] = field(default_factory=set)
    event_marks: dict[int, int] = field(default_factory=dict)  # for turning new events into news
    player_actions: set[str] = field(default_factory=set)   # once-per-off-season player actions used
    player_offers: Optional[list] = None                    # cached team offers for the player


@dataclass
class YearSummary:
    year: int
    drivers_by_tier: dict[int, int] = field(default_factory=dict)
    new_entrants: int = 0
    retirements: int = 0
    promotions: int = 0
    first_top_tier: list[int] = field(default_factory=list)
    champions: dict[str, int] = field(default_factory=dict)
    signings: list[str] = field(default_factory=list)


class World:
    def __init__(self, config: Optional[WorldConfig] = None,
                 tracks: Optional[TrackDatabase] = None):
        self.config = config or WorldConfig()
        self.rng = random.Random(self.config.seed)
        self.year = self.config.start_year
        self.geo = Geography.load()
        self.tracks = tracks or TrackDatabase.load()
        self._transfer = load_json("disciplines.json")["transfer"]
        self.pyramid: Pyramid = build_pyramid(self.tracks, self.geo, self.rng)
        self.drivers: dict[int, Driver] = {}
        self.teams: dict[int, Team] = {}
        self.sponsors: dict[int, Sponsor] = {}
        self.manufacturers: dict[int, Manufacturer] = {}
        self._ids: dict[str, int] = {}
        self.summaries: list[YearSummary] = []
        self.shootouts = load_json("series.json").get("shootouts", [])
        self.last_season: dict = {}
        self.seat_coverage: dict[int, float] = {}   # share of a pay seat's gap actually funded
        self.market = MarketState()
        self.cache: dict = {}                       # derived indexes (travel costs, series lookup)
        self.target_population = 0
        self.player_id: Optional[int] = None
        self.player_jewels: set[str] = set()        # crown jewels the player chose to enter
        self.player_applications: set[str] = set()  # combines/shootouts the player applied to
        self.news: list[dict] = []
        self.season = None                          # current SeasonRunner (UI / career mode)
        self.race_logs: dict[int, dict] = {}        # year -> series/jewel key -> race summaries

    # ----------------------------------------------------------------- helpers
    def next_id(self, kind: str) -> int:
        self._ids[kind] = self._ids.get(kind, 0) + 1
        return self._ids[kind]

    def transfer(self, from_disc: str, to_disc: str) -> float:
        return self._transfer.get(from_disc, {}).get(to_disc, 0.4)

    def series(self, series_id: str) -> Series:
        return self.pyramid.series[series_id]

    def active_drivers(self) -> Iterable[Driver]:
        return (d for d in self.drivers.values() if d.status != RETIRED)

    def teams_in(self, series_id: str) -> list[Team]:
        return [t for t in self.teams.values() if t.series_id == series_id]

    def region(self, code: str) -> Region:
        return self.geo.get(code)

    # -------------------------------------------------------------- generation
    @classmethod
    def generate(cls, config: Optional[WorldConfig] = None,
                 tracks: Optional[TrackDatabase] = None) -> "World":
        w = cls(config, tracks)
        for m in make_manufacturers(w):
            w.manufacturers[m.id] = m
        for s in make_sponsors(w, scale=w.config.population_scale):
            w.sponsors[s.id] = s
        for series in sorted(w.pyramid.series.values(), key=lambda s: -s.tier):
            if series.template.team_based:
                w._populate_team_series(series)
            else:
                w._populate_self_run_series(series)
        from ..career.sponsorship import initial_personal_sponsors
        initial_personal_sponsors(w)
        w.target_population = sum(1 for _ in w.active_drivers())
        return w

    def _age_for(self, series: Series) -> int:
        lo, hi = series.template.typical_age
        age = int(round(self.rng.triangular(lo - 1, hi + 4, lo + (hi - lo) * 0.35)))
        age = max(age, series.template.min_age)
        if series.template.max_age:
            age = min(age, series.template.max_age)
        return age

    def _home_for(self, series: Series) -> tuple[Region, Optional[tuple[float, float]]]:
        tpl = series.template
        if tpl.scope == "track":
            track = self.tracks.get(series.region_key)
            region = self.geo.regions.get(track.facts.region or "")
            if region is not None:
                return region, (track.facts.lat, track.facts.lon)
        if tpl.scope == "region" and series.region_key:
            pool = self.geo.in_macro(series.region_key)
            if pool:
                weights = [r.racer_weight * (0.2 + r.culture.get(tpl.discipline, 0) / 100) for r in pool]
                return weighted_choice(self.rng, pool, weights), None
        return self.geo.random_home(self.rng, tpl.discipline), None

    def _populate_self_run_series(self, series: Series) -> None:
        tpl = series.template
        n = max(4, int(round(tpl.field_size * self.config.fill_by_tier[tpl.tier]
                             * self.config.population_scale * self.rng.uniform(0.7, 1.3))))
        for _ in range(n):
            region, near = self._home_for(series)
            age = self._age_for(series)
            d = make_driver(self, discipline=tpl.discipline, age=age, region=region,
                            ability=ability_for_tier(self.rng, tpl.tier), near=near,
                            budget_floor=tpl.season_cost * (1.0 if tpl.scope == "track" else 1.25))
            self._seat(d, series, None)

    def _populate_team_series(self, series: Series) -> None:
        tpl = series.template
        from ..career.market import seat_gap, seat_role
        for team in make_teams_for_series(self, series):
            self.teams[team.id] = team
            team.roster = [None] * team.seats
            for slot in range(team.seats):
                role = seat_role(tpl, slot)
                gap = seat_gap(team, tpl, role)
                region = self.geo.random_home(self.rng, tpl.discipline)
                if role == "am":
                    age = int(clamp(self.rng.gauss(44, 9), 30, 68))
                    ability = ability_for_tier(self.rng, max(0, tpl.tier - 2))
                    d = make_driver(self, discipline="club_road", age=age, region=region,
                                    ability=ability, years_racing=self.rng.uniform(2, 12),
                                    budget_floor=gap * 1.1)
                    d.first_license_age = max(30, age - 8)
                    d.proficiency[tpl.discipline] = max(d.proficiency.get(tpl.discipline, 0), 0.6)
                else:
                    age = self._age_for(series)
                    bias = (team.equipment - 50) * 0.08
                    d = make_driver(self, discipline=tpl.discipline, age=age, region=region,
                                    ability=ability_for_tier(self.rng, tpl.tier, bias),
                                    budget_floor=gap * 1.05 if gap > 0 else 0.0)
                    d.proficiency[tpl.discipline] = max(d.proficiency[tpl.discipline], 0.7)
                d.max_tier = tpl.tier
                d.reputation = clamp(10 + tpl.tier * 9 + (d.ability - 50) * 0.5 + self.rng.gauss(0, 6))
                self._seat(d, series, team, slot=slot, funded=gap <= 0)
                if gap <= 0 and tpl.pro:
                    d.salary = tpl.salary_top * clamp((team.equipment - 25) / 70, 0.05, 1.0) * self.rng.uniform(0.6, 1.1)
                d.contract_years = self.rng.randint(1, 3)

    def _seat(self, d: Driver, series: Series, team: Optional[Team], slot: int = 0,
              funded: bool = False) -> None:
        tpl = series.template
        d.series_id = series.id
        d.tier = tpl.tier
        d.max_tier = max(d.max_tier, tpl.tier)
        d.status = ACTIVE
        if d.reputation == 0:
            d.reputation = clamp(3 + tpl.tier * 8 + (d.ability - 40) * 0.4 + self.rng.gauss(0, 5))
        if team is not None:
            team.roster[slot] = d.id
            d.team_id = team.id
            d.seat_funded = funded
        else:
            d.team_id = None
            d.seat_funded = False
            if tpl.scope == "track":
                d.home_track_id = series.region_key
        self.drivers[d.id] = d

    # ------------------------------------------------------------------- loop
    def run_year(self) -> YearSummary:
        """AI-only batch year: season, then the whole off-season."""
        from ..career.offseason import begin_offseason, complete_offseason
        from ..sim.season import SeasonRunner
        summary = YearSummary(year=self.year)
        self.season = SeasonRunner(self, summary)
        results = self.season.run_to_end()
        begin_offseason(self, results, summary)
        complete_offseason(self, summary)
        return self.end_year(summary)

    def end_year(self, summary: YearSummary) -> YearSummary:
        if self.season is not None:
            self.race_logs[self.year] = dict(self.season.race_log)
            for y in [y for y in self.race_logs if y < self.year - 2]:
                del self.race_logs[y]
        summary.drivers_by_tier = self.tier_counts()
        self.summaries.append(summary)
        self.year += 1
        self.player_jewels = set()
        self.player_applications = set()
        return summary

    def post(self, kind: str, text: str, driver_id: Optional[int] = None,
             series_id: Optional[str] = None, week: Optional[int] = None, importance: int = 1) -> None:
        """Add an item to the news wire shown in the UI."""
        if week is None:
            week = self.season.week if self.season is not None and not self.season.finished else 0
        self.news.append({"year": self.year, "week": week, "kind": kind, "text": text,
                          "driver_id": driver_id, "series_id": series_id, "importance": importance})
        if len(self.news) > 3000:
            del self.news[:1000]

    @property
    def player(self) -> Optional[Driver]:
        return self.drivers.get(self.player_id) if self.player_id is not None else None

    def tier_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for d in self.drivers.values():
            if d.status != RETIRED and d.series_id:
                counts[d.tier] = counts.get(d.tier, 0) + 1
        return dict(sorted(counts.items()))
