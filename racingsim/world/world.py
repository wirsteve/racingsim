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
    real_history: bool = True          # seed national series with the real teams/drivers of start_year
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
                 tracks: Optional[TrackDatabase] = None, history=None):
        self.config = config or WorldConfig()
        self.rng = random.Random(self.config.seed)
        self.year = self.config.start_year
        self.geo = Geography.load()
        self.tracks = tracks or TrackDatabase.load()
        self._transfer = load_json("disciplines.json")["transfer"]
        self.history = history
        if self.history is None and self.config.real_history:
            from ..history import HistoryDB
            self.history = HistoryDB.load_default()
        self.pyramid: Pyramid = build_pyramid(self.tracks, self.geo, self.rng, year=self.year,
                                              schedule_provider=self.schedule_provider,
                                              tours=self.tour_provider)
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
        self.real_drivers: dict[str, int] = {}      # Wikipedia title -> driver id (historical mode)
        self.history_entrants: dict[int, list] = {}  # year -> real drivers who start racing then
        self.staff: dict = {}                       # staff id -> Staff (crew chiefs, spotters, ...)
        self.player_crew: dict = {}                 # role -> staff id the player hired for their own car
        self.annals: dict = {}                      # almanac, track winners, Hall of Fame (world/annals.py)

    # Derived indexes are rebuilt on demand: keep them out of save games.
    def __getstate__(self) -> dict:
        state = dict(self.__dict__)
        state["cache"] = {}
        return state

    def __setstate__(self, state: dict) -> None:
        state.setdefault("staff", {})   # saves from before staff existed are staffed on the next season
        state.setdefault("player_crew", {})
        state.setdefault("annals", {})
        self.__dict__.update(state)

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

    def advance_pyramid(self, year: int) -> None:
        """Move the racing world to ``year``: renamed series, new/dormant rungs, venues opening/closing."""
        from .factory import make_teams_for_series
        born, died = self.pyramid.refresh(year, self.tracks, self.geo, self.rng, self.schedule_provider,
                                          self.tour_provider)
        dead_ids = {s.id for s in died}
        for d in self.drivers.values():
            if d.series_id in dead_ids:
                if d.team_id is not None:
                    team = self.teams.get(d.team_id)
                    if team:
                        team.roster = [None if x == d.id else x for x in team.roster]
                    d.team_id = None
                    d.seat_funded = False
                    d.contract_years = 0
                d.series_id = None
        for s in born:
            if s.template.team_based and not self.teams_in(s.id):
                for team in make_teams_for_series(self, s):
                    team.roster = [None] * team.seats
                    self.teams[team.id] = team
        for s in born:
            if s.scope != "track" and s.tier >= 3:
                self.post("series", f"New for {year}: the {s.name}", series_id=s.id, week=0)
        local = self.cache.get("travel_local")
        self.cache.clear()
        if local is not None:
            self.cache["travel_local"] = local

    def schedule_provider(self, template_key: str, year: int):
        """Real national calendars when the historical database has them."""
        hist = getattr(self, "history", None)
        return hist.schedule(template_key, year, self.tracks) if hist is not None else None

    def tour_provider(self, tpl, year: int) -> list[dict]:
        """Real regional touring series playing rung ``tpl`` in ``year`` (from the knowledge layer + history)."""
        hist = getattr(self, "history", None)
        if hist is None:
            return []
        out = []
        for link in hist.linked_series():
            if link["template"] != tpl.key or not (link["from"] <= year <= link["to"]):
                continue
            sched = hist.schedule_source(link["source"], year, self.tracks)
            real = bool(sched)
            if not sched:
                # No calendar for this season in the data: race at the venues the series is known to use.
                pool = [t for t in hist.venues(link["source"], year)
                        if t in self.tracks and self.tracks.get(t).facts.available_in(year)]
                if len(pool) < 2:
                    continue
                local = random.Random(f"{link['key']}:{year}:{self.config.seed}")
                pool = pool[: max(tpl.events, 6)]
                sched = [pool[i % len(pool)] for i in range(tpl.events)]
                local.shuffle(sched)
            macro = self._macro_of(sched + hist.venues(link["source"], year)[:12], link.get("regions") or [])
            if macro is None:
                continue
            out.append({"key": link["key"], "source": link["source"], "name": hist.series_name(link, year),
                        "macro": macro, "schedule": sched, "real": real})
        return out

    def _macro_of(self, track_ids: list[str], states: list[str]):
        from collections import Counter
        votes = Counter()
        for tid in track_ids:
            if tid in self.tracks:
                r = self.geo.regions.get(self.tracks.get(tid).facts.region or "")
                if r:
                    votes[r.macro_region] += 1
        for code in states:
            r = self.geo.regions.get(code)
            if r:
                votes[r.macro_region] += 0.5
        return votes.most_common(1)[0][0] if votes else None

    def region(self, code: str) -> Region:
        return self.geo.get(code)

    # -------------------------------------------------------------- generation
    @classmethod
    def generate(cls, config: Optional[WorldConfig] = None,
                 tracks: Optional[TrackDatabase] = None, history=None) -> "World":
        w = cls(config, tracks, history)
        for m in make_manufacturers(w):
            w.manufacturers[m.id] = m
        for s in make_sponsors(w, scale=w.config.population_scale):
            w.sponsors[s.id] = s
        seeded: set[str] = set()
        if w.history is not None:
            from ..history.seed import seed_national
            seeded = seed_national(w, w.history)
            from ..history.seed import seed_tours
            seed_tours(w, w.history)
        for series in sorted(w.pyramid.series.values(), key=lambda s: -s.tier):
            if series.template.team_based:
                w._populate_team_series(series, existing=series.id in seeded)
            else:
                w._populate_self_run_series(series)
        if w.history is not None:
            from ..history.seed import seed_prospects
            seed_prospects(w, w.history)
        from ..career.sponsorship import initial_personal_sponsors
        initial_personal_sponsors(w)
        from .staff import seed_staff
        seed_staff(w)
        from . import fans, finance
        fans.ensure(w)
        finance.ensure(w)
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
        if series.source:  # real tour: its real regulars are already seated; fill up around them
            n -= sum(1 for d in self.drivers.values() if d.series_id == series.id)
        for _ in range(max(0, n)):
            region, near = self._home_for(series)
            age = self._age_for(series)
            d = make_driver(self, discipline=tpl.discipline, age=age, region=region,
                            ability=ability_for_tier(self.rng, tpl.tier), near=near,
                            budget_floor=tpl.season_cost * (1.0 if tpl.scope == "track" else 1.25))
            self._seat(d, series, None)

    def _populate_team_series(self, series: Series, existing: bool = False) -> None:
        """Fill a team series with generated drivers (only the empty seats if real teams exist)."""
        tpl = series.template
        from ..career.market import seat_gap, seat_role
        if existing:
            teams = self.teams_in(series.id)
            # Real entry lists can be short (only winners known): top the grid up with generated teams.
            have = sum(t.cars for t in teams)
            want = tpl.cars if getattr(tpl, "cars", None) else tpl.field_size
            if have < want * 0.8:
                for team in make_teams_for_series(self, series):
                    if have >= want:
                        break
                    team.roster = [None] * team.seats
                    self.teams[team.id] = team
                    teams.append(team)
                    have += team.cars
        else:
            teams = make_teams_for_series(self, series)
            for team in teams:
                self.teams[team.id] = team
                team.roster = [None] * team.seats
        for team in teams:
            for slot in range(team.seats):
                if team.roster[slot] is not None:
                    continue
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
            for y, logs in self.race_logs.items():       # replays are big: keep the season just run
                if y < self.year:
                    for infos in logs.values():
                        for info in infos:
                            info.pop("replay", None)
        summary.drivers_by_tier = self.tier_counts()
        self.summaries.append(summary)
        self.year += 1
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
