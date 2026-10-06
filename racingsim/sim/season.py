"""Season simulation: every series in the pyramid runs its calendar.

Key systemic behaviours produced here:
* Self-run racers' equipment is bought with money: a family that can spend 2x the
  typical budget shows up with a faster car (research A 14.3 "front-runner" budgets).
* Under-age drivers sit out big ovals (NASCAR-style track approval), creating
  one-off seats for substitutes.
* Injuries open substitute drives; a strong substitute run sets a "breakout" flag
  that scouts and owners react to in the off-season (research C 5.3).
* Crown-jewel events pull drivers from several tiers onto one grid at a real track,
  giving local racers rare national visibility (research A 7, F 4).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..constants import SUBSTITUTE_BREAKOUT_FINISH_PCT
from ..util import clamp
from ..world.entities import ACTIVE, PART_TIME, RETIRED, SIDELINED, Driver, SeasonRecord
from ..world.skills import track_type_of as skill_track_type
from ..world import annals
from ..world import staff as staff_mod
from ..career import morale as morale_mod
from ..rules import car as C
from ..rules import garage
from ..rules.payouts import Purse
from ..rules.points import format_for, heat_points, score_box, score_race, system_for
from . import engine
from .race import Entry, Finish, heats, run_race

if TYPE_CHECKING:
    from ..world.series import CrownJewel, Series
    from ..world.world import World, YearSummary


@dataclass
class _Acc:
    series_id: str
    starts: int = 0
    wins: int = 0
    top5: int = 0
    fin_pct_sum: float = 0.0     # 0 = last, 1 = win
    exp_pct_sum: float = 0.0
    finish_sum: float = 0.0
    expected_sum: float = 0.0
    field_sum: int = 0
    points: float = 0.0
    purse: float = 0.0
    team_id: Optional[int] = None
    top10: int = 0
    dnq: int = 0
    poles: int = 0
    laps_led: int = 0
    laps: int = 0
    dnfs: int = 0
    start_sum: int = 0
    rating_sum: float = 0.0
    rated: int = 0
    fast_laps: int = 0
    eq_sum: float = 0.0          # the cars they drove (PAR baseline)
    splits: dict = field(default_factory=dict)   # track type -> [starts, wins, top5, finish sum, laps led]

    def __setstate__(self, state: dict) -> None:
        state.setdefault("eq_sum", 0.0)
        state.setdefault("splits", {})
        self.__dict__.update(state)


@dataclass
class SeasonResults:
    records: dict[int, SeasonRecord] = field(default_factory=dict)
    champions: dict[str, int] = field(default_factory=dict)
    crown_jewel_results: list[tuple[str, list[int]]] = field(default_factory=list)
    substitute_runs: list[tuple[int, str, float]] = field(default_factory=list)  # (driver, series, finish pct)
    injuries: list[tuple[int, int]] = field(default_factory=list)                 # (driver, races)
    equipment: dict[int, float] = field(default_factory=dict)
    track_laps: dict[int, dict] = field(default_factory=dict)  # driver -> {track type: laps run}

    par_fit: dict[str, list] = field(default_factory=dict)     # series -> [n, sum eq, sum pct, sum eq*pct, sum eq^2]

    def __setstate__(self, state: dict) -> None:
        state.setdefault("track_laps", {})   # mid-season saves from before the lap-by-lap engine
        state.setdefault("par_fit", {})
        self.__dict__.update(state)


def purse_for(position: int, field_size: int, purse_win: float) -> float:
    if purse_win <= 0:
        return 0.0
    return purse_win * max(0.04, 1.0 / (1.0 + 0.45 * (position - 1)))


def self_run_equipment(world: "World", d: Driver, series: "Series") -> tuple[float, float]:
    """Return (equipment rating, attendance share) for a driver running their own car.

    In classes with researched rules the car is built from real parts (rules/car.py);
    elsewhere money buys equipment directly."""
    from ..career.market import season_cost_for
    cost = season_cost_for(world, d, series)
    funds = d.available_funding()
    ratio = funds / cost if cost > 0 else 1.0
    attendance = 1.0 if ratio >= 0.8 else clamp(ratio / 0.8, 0.25, 1.0)
    cls = garage.class_of(series)
    if cls is not None:
        return garage.prepare(world, d, series, cls, funds, cost), (1.0 if d.is_player else attendance)
    spend_ratio = clamp(ratio, 0.4, 2.5)
    equipment = 48 + 20 * math.log2(spend_ratio) + (d.feedback - 50) * 0.12 + world.rng.gauss(0, 5)
    return clamp(equipment, 8, 95), attendance


SEASON_WEEKS = 30  # roughly late January to early December


class SeasonRunner:
    """Runs one season week by week so the UI can show it unfolding.

    Every series' calendar is spread across ``SEASON_WEEKS``; crown-jewel events sit
    on fixed weeks (``week`` in data/series.json). ``run_to_end`` reproduces the
    batch behaviour used by the AI-only simulation and the tests.
    """

    def __init__(self, world: "World", summary: "YearSummary"):
        self.world = world
        self.summary = summary
        self.res = SeasonResults()
        self.acc: dict[int, _Acc] = {}
        self.attendance: dict[int, float] = {}
        self.week = 0
        self.finished = False
        self.busy: set[int] = set()
        self.injury_mark = 0
        self.entered_jewels: dict[int, int] = {}
        self.race_log: dict[str, list[dict]] = defaultdict(list)
        self.mech: dict[int, float] = {}          # own cars: mechanical-failure chance per race
        self.systems: dict[str, object] = {}      # series -> points system this season
        self.purses: dict[str, Purse] = {}
        self.playoffs: dict[str, dict] = {}       # series -> Chase / playoff state
        self.player_notes: list[str] = []
        self.crews: dict = {}
        if not world.staff:              # a save from before staff existed: hire everyone now
            staff_mod.seed_staff(world)
        rng = world.rng
        res = self.res

        self.by_series: dict[str, list[Driver]] = defaultdict(list)
        for d in world.drivers.values():
            if d.status in (ACTIVE, PART_TIME) and d.series_id in world.pyramid.series:
                self.by_series[d.series_id].append(d)

        # Pre-season: equipment for every entrant.
        for sid, drivers in self.by_series.items():
            s = world.series(sid)
            for d in drivers:
                if s.template.team_based and d.team_id in world.teams:
                    team = world.teams[d.team_id]
                    covered = world_seat_coverage(world, d)
                    res.equipment[d.id] = clamp(team.equipment - (1 - covered) * 25 + rng.gauss(0, 2), 5, 99)
                    self.attendance[d.id] = 1.0 if covered >= 0.6 else clamp(covered / 0.6, 0.3, 1.0)
                else:
                    eq, att = self_run_equipment(world, d, s)
                    res.equipment[d.id] = eq
                    self.attendance[d.id] = att * (0.6 if d.status == PART_TIME else 1.0)
                    cls = garage.class_of(s)
                    if cls is not None and d.car is not None:
                        ht = garage.home_track(world, s)
                        self.mech[d.id] = C.mech_risk(cls, d.car, ht.sim.mechanical_stress if ht else 50)

        self.sub_pool = _substitute_pool(world)
        self.calendar: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for sid in sorted(self.by_series):
            n = len(world.series(sid).schedule)
            for i in range(n):
                self.calendar[1 + (i * SEASON_WEEKS) // max(n, 1)].append((sid, i))
        self.jewels: dict[int, list] = defaultdict(list)
        for i, cj in enumerate(world.pyramid.crown_jewels):
            self.jewels[cj.week or (3 + i * 2) % SEASON_WEEKS + 1].append(cj)

    def __setstate__(self, state: dict) -> None:
        # Saves from before the rules system (mid-season) lack these.
        state.setdefault("mech", {})
        state.setdefault("systems", {})
        state.setdefault("purses", {})
        state.setdefault("playoffs", {})
        state.setdefault("player_notes", [])
        state.setdefault("crews", {})
        self.__dict__.update(state)

    # ------------------------------------------------------------------ stepping
    def step(self) -> list[dict]:
        """Run the next week. Returns the races that ran (summaries for the UI)."""
        if self.finished:
            return []
        self.week += 1
        ran = []
        week_events = self.calendar.get(self.week, [])
        # Nobody can race twice in a week: regulars of series racing this week are taken.
        self.busy = {d.id for sid, _ in week_events for d in self.by_series.get(sid, ())}
        self.injury_mark = len(self.res.injuries)
        for sid, idx in week_events:
            info = self._run_event(sid, idx)
            if info:
                ran.append(info)
        for cj in self.jewels.get(self.week, []):
            info = _crown_jewel(self.world, self, cj)
            if info:
                ran.append(info)
        self._heal()
        if self.week >= SEASON_WEEKS:
            _finalise_records(self.world, self.res, self.acc, self.summary, self)
            for d in self.world.drivers.values():
                if d.injury_races > 0:  # the winter break heals too
                    d.injury_races = max(0, d.injury_races - OFFSEASON_HEAL)
                d.season_spend = 0.0
            if self.world.player is not None:
                garage.close_account(self.world, self.world.player)
            self.world.player_jewels = set()
            self.finished = True
        return ran

    def _heal(self) -> None:
        """Injuries are counted in race weekends missed: one passes every week."""
        fresh = {did for did, _ in self.res.injuries[self.injury_mark:]}
        for d in self.world.drivers.values():
            if d.injury_races > 0 and d.id not in fresh:
                d.injury_races -= 1

    def run_to_end(self) -> SeasonResults:
        while not self.finished:
            self.step()
        return self.res

    def next_week_for(self, driver: Driver) -> Optional[int]:
        """Next week in which this driver's series races (for 'sim to next race')."""
        if not driver.series_id:
            return None
        for w in range(self.week + 1, SEASON_WEEKS + 1):
            if any(sid == driver.series_id for sid, _ in self.calendar.get(w, [])):
                return w
        return None

    def standings(self, series_id: str) -> list[tuple[int, "_Acc"]]:
        rows = [(did, a) for did, a in self.acc.items() if a.series_id == series_id]
        rows.sort(key=self.rank_key(series_id))
        return rows

    # ------------------------------------------------------------------ rules of the series
    def system(self, s: "Series"):
        sysm = self.systems.get(s.id)
        if sysm is None:
            sysm = self.systems[s.id] = system_for(s.template.key, self.world.year, s.scope, series_state(self.world, s))
        return sysm

    def purse(self, s: "Series") -> Purse:
        p = self.purses.get(s.id)
        if p is None:
            p = self.purses[s.id] = Purse(s.template, self.world.year)
        return p

    def rank_key(self, sid: str):
        """Standings order: points then wins; in a Chase/playoff, the playoff field first
        (survivors, then eliminated), and the finale decided by finishing order."""
        st = self.playoffs.get(sid)
        if not st:
            return lambda r: (-r[1].points, -r[1].wins)
        alive = set(st["alive"])
        field_ = set(st["field"])
        final = {d: i for i, d in enumerate(st.get("final_order") or [])}

        def key(r):
            did, a = r
            grp = 0 if did in alive else 1 if did in field_ else 2
            return (grp, final.get(did, 99) if grp == 0 else 0, -a.points, -a.wins)
        return key

    def _playoff_step(self, s: "Series", idx: int, finishes: list[Finish]) -> None:
        fmt = format_for(s.template.key, self.world.year, s.scope, series_state(self.world, s))
        if fmt is None or fmt.kind == "points" or not fmt.drivers:
            return
        n = len(s.schedule)
        start = n - fmt.races            # index of the first playoff race
        if start < 1:
            return
        st = self.playoffs.get(s.id)
        acc = self.acc
        if st is None:
            if idx + 1 < start:
                return
            rows = self.standings(s.id)
            field_: list[int] = []
            if fmt.win_in:  # win and you're in (if you're inside the top 30 in points)
                winners = sorted((r for r in rows[:30] if r[1].wins > 0), key=lambda r: (-r[1].wins, -r[1].points))
                field_ = [did for did, _ in winners[: fmt.drivers]]
            for did, _ in rows:
                if len(field_) >= fmt.drivers:
                    break
                if did not in field_:
                    field_.append(did)
            seeded = sorted(field_, key=lambda did: (-acc[did].points, -acc[did].wins))
            for rank, did in enumerate(seeded):
                a = acc[did]
                bonus = fmt.seed_steps[rank] if rank < len(fmt.seed_steps) else 0.0
                a.points = fmt.base + bonus + fmt.per_win * a.wins
            self.playoffs[s.id] = {"field": seeded, "alive": list(seeded), "round": 0,
                                   "next_cut": start + (fmt.round_races[0] if fmt.round_races else fmt.races),
                                   "wins0": {did: acc[did].wins for did in seeded}, "label": fmt.label}
            if self.world.player_id in seeded:
                self.world.post("player", f"You're in the {fmt.label}!", driver_id=self.world.player_id,
                                series_id=s.id, week=self.week, importance=3)
            return
        if fmt.kind != "elimination" or not fmt.rounds:
            return
        r = st["round"]
        if fmt.finale and r == len(fmt.rounds) and idx + 1 == n:
            alive = set(st["alive"])
            st["final_order"] = [f.entry.drivers[0].id for f in finishes if f.entry.drivers[0].id in alive]
            return
        if idx + 1 < st["next_cut"] or r >= len(fmt.rounds):
            return
        keep = fmt.rounds[r]
        # Race winners in the round advance; the rest of the spots go on points.
        won = [d for d in st["alive"] if acc[d].wins > st["wins0"].get(d, 0)]
        rest = sorted((d for d in st["alive"] if d not in won), key=lambda d: (-acc[d].points, -acc[d].wins))
        alive = (won + rest)[:keep]
        r += 1
        last = fmt.finale and r == len(fmt.rounds)
        for d in alive:
            a = acc[d]
            a.points = fmt.base + 1000 * r + (0 if last else fmt.per_win * a.wins)
        st.update(alive=alive, round=r, wins0={d: acc[d].wins for d in alive},
                  next_cut=idx + 1 + (fmt.round_races[r] if r < len(fmt.round_races) else 1))
        if self.world.player_id in st["field"]:
            me = self.world.player_id
            self.world.post("player", ("You advance in the playoffs" if me in alive else "You've been eliminated from the playoffs"),
                            driver_id=me, series_id=s.id, week=self.week, importance=2)

    # ------------------------------------------------------------------ events
    def _run_event(self, sid: str, event_idx: int) -> Optional[dict]:
        world, res, rng = self.world, self.res, self.world.rng
        s = world.series(sid)
        tpl = s.template
        track_id = s.schedule[event_idx]
        track = world.tracks.get(track_id)
        drivers = self.by_series[sid]
        entries: list[Entry] = []
        suspended: list[Driver] = []     # serve the race only if it actually runs
        if tpl.team_based:
            for team in world.teams_in(sid):
                for car in range(team.cars):
                    car_drivers = []
                    car_eq = team.equipment
                    for slot in range(car * team.drivers_per_car, (car + 1) * team.drivers_per_car):
                        did = team.roster[slot] if slot < len(team.roster) else None
                        d = world.drivers.get(did) if did else None
                        if d is None or d.status == RETIRED:
                            continue
                        car_eq = res.equipment.get(d.id, car_eq)
                        if d.suspension > 0:
                            suspended.append(d)
                        if (d.injury_races > 0 or d.suspension > 0 or not tpl.age_allows_track(d.age(world.year), track)
                                or rng.random() > self.attendance.get(d.id, 1.0)):
                            sub = _pick_substitute(world, self.sub_pool, s, track, team, self.busy)
                            if sub is not None:
                                res.substitute_runs.append((sub.id, sid, -1.0))
                                self.busy.add(sub.id)
                                car_drivers.append(sub)
                            continue
                        car_drivers.append(d)
                    if car_drivers:
                        # The car is the team's, whoever drives it - and so are the people around it.
                        crew = self.crew(team.id, car, car_drivers[0])
                        eq = car_eq + (crew["development"] * 2.0 * self.week / SEASON_WEEKS if crew else 0.0)
                        entries.append(Entry(car_drivers, eq, team_id=team.id, car_key=f"{team.id}:{car}",
                                             crew=crew))
        else:
            cls = garage.class_of(s)
            pool = []
            for d in drivers:
                if d.suspension > 0:
                    suspended.append(d)
                if d.injury_races > 0 or d.suspension > 0:
                    continue
                if d.is_player:
                    if cls is not None and d.car is not None and not garage.can_race(
                            d, cls, garage.travel_per_night(world, d, s)):
                        why = ("the engine is blown - rebuild or replace it in the Garage" if d.car.engine_health <= 0
                               else "there isn't enough money left for entry, fuel and travel")
                        world.post("player", f"You couldn't race at {track.name}: {why}",
                                   driver_id=d.id, series_id=sid, week=self.week, importance=2)
                        continue
                    pool.append(d)
                elif rng.random() < self.attendance.get(d.id, 1.0):
                    pool.append(d)
            cap = int(tpl.field_size * 1.5)
            if len(pool) > cap:
                keep = [d for d in pool if d.is_player]
                pool = keep + rng.sample([d for d in pool if not d.is_player], cap - len(keep))
            for d in pool:
                entries.append(Entry([d], res.equipment[d.id], mech=self.mech.get(d.id),
                                     crew=staff_mod.player_effects(world, d) if d.is_player else None))
        if len(entries) < 3:
            return None
        for d in suspended:
            _serve_suspension(world, d, track, sid, self.week)
        if not tpl.team_based:
            cls = garage.class_of(s)
            for e in entries:
                d = e.drivers[0]
                if d.is_player and cls is not None and d.car is not None:
                    # Pay for tonight only once we know the race runs.
                    e.equipment = garage.before_race(world, d, cls, track, self.week,
                                                     garage.travel_per_night(world, d, s), C.overhead_per_night(cls, tpl))
                    e.mech = C.mech_risk(cls, d.car, track.sim.mechanical_stress)
        system = self.system(s)
        purse = self.purse(s)
        heat_pts: dict[int, float] = {}
        dnq: list[Entry] = []
        if not tpl.team_based and (len(entries) > tpl.field_size or system.heat):
            # Heat races set the feature field (and pay heat points where the track does).
            order, groups = heats(entries, track, tpl.discipline, tpl.tier, tpl.car_weight, rng)
            if system.heat:
                for g in groups:
                    heat_pts.update(heat_points(system, [e.drivers[0].id for e in g]))
            if len(entries) > tpl.field_size:
                keep_ids = {id(e) for e in order[: tpl.field_size]}
                dnq = [e for e in entries if id(e) not in keep_ids]
                entries = [e for e in entries if id(e) in keep_ids]
        rr = None
        if self.lap_by_lap(s, entries):
            # Tours, national series and any race the player is in run lap by lap.
            player_in = any(d.is_player for e in entries for d in e.drivers)
            rr = engine.run(entries, track, tpl.tier, tpl.car_weight, rng, detail=player_in,
                            stages=system.stages, free_pass=world.year >= 2003, discipline=tpl.discipline)
            finishes = rr.finishes
            pts = score_box(system, finishes)
        else:
            finishes = run_race(entries, track, tpl.discipline, tpl.tier, tpl.car_weight, rng)
            pts = score_race(system, [(f.entry.drivers[0].id, f.pace) for f in finishes], rng)
        _tally(world, res, self.acc, finishes, s, pts, purse, heat_pts, dnq, system, track)
        self._personal(finishes, rr, tpl.tier, s.name, track.name, s.id)
        self._after_race(s, track, finishes, dnq, purse)
        self._playoff_step(s, event_idx, finishes)
        return self._log(s, track, finishes, event_idx, race=rr)

    def _personal(self, finishes: list[Finish], rr, tier: int, series_name: str, track_name: str,
                  series_id: str) -> None:
        """Morale after the race; grudges from wrecks; the sanctioning body's answer to paybacks."""
        n = len(finishes)
        for f in finishes:
            for d in f.entry.drivers:
                morale_mod.after_race(d, f.position, n, f.expected_position or f.position, f.dnf, f.crashed)
        if rr is None:
            return
        morale_mod.incidents(self.world, rr.incidents)
        for att, tgt in rr.paybacks:
            morale_mod.payback(self.world, att, tgt, tier, series_name, track_name, self.week, self.acc, series_id)

    def crew(self, team_id: int, car: int, driver: Driver) -> Optional[dict]:
        """Race-day effects of this car's crew chief, spotter, pit crew, engine shop and doctor (cached per
        season and driver: staff don't change jobs mid-season)."""
        key = (team_id, car, driver.id)
        if key not in self.crews:
            eff = staff_mod.crew_effects(self.world, team_id, car, driver)
            if eff is not None:
                eff["injury"] = staff_mod.medical(self.world, driver)[0]
                team = self.world.teams.get(team_id)
                chem = morale_mod.chemistry(self.world, team) if team else 0.0
                eff["team_chemistry"] = chem
                eff["setup_mean"] += chem * 0.6     # a shop that works together finds speed
            self.crews[key] = eff
        return self.crews[key]

    def lap_by_lap(self, s: "Series", entries: list[Entry]) -> bool:
        return s.tier >= 3 or any(d.is_player for e in entries for d in e.drivers)

    def _after_race(self, s: "Series", track, finishes: list[Finish], dnq: list[Entry], purse: Purse) -> None:
        """Own cars after the feature: the player's car race by race, AI wrecks from the season reserve."""
        world, res = self.world, self.res
        cls = garage.class_of(s)
        if cls is None:
            return
        n = len(finishes)
        for f in finishes:
            d = f.entry.drivers[0]
            if d.car is None or d.series_id != s.id:
                continue
            if d.is_player:
                notes = garage.after_race(world, d, cls, track, self.week, f, purse.pay(f.position, n))
                claim = garage.claim_check(world, d, cls, f, self.week)
                if claim:
                    notes.append(claim)
                res.equipment[d.id] = garage.player_rating(world, d, cls, None)
                for msg in notes:
                    world.post("player", msg, driver_id=d.id, series_id=s.id, week=self.week, importance=2)
            elif f.dnf:
                new = garage.ai_wreck(world, d, s, cls, f.crashed)
                if new is not None:
                    res.equipment[d.id] = new
                    self.mech[d.id] = C.mech_risk(cls, d.car, 50)
        for e in dnq:
            d = e.drivers[0]
            if d.is_player and d.car is not None:
                pay = purse.dnq()
                d.car.tire_wear = clamp(d.car.tire_wear + C.wear_per_race(cls, track) * 0.3, 0, 1)
                if pay:
                    d.car.account = (d.car.account or 0.0) + pay
                    d.car.winnings += pay
                    garage.log(d.car, self.week, "Tow money (missed the feature)", pay)
                world.post("player", f"You missed the feature at {track.name} (DNQ)", driver_id=d.id,
                           series_id=s.id, week=self.week, importance=2)

    def _log(self, s: "Series", track, finishes: list[Finish], event_idx: int,
             jewel: Optional[str] = None, jewel_name: Optional[str] = None, race=None) -> Optional[dict]:
        world = self.world
        player_in = any(d.is_player for f in finishes for d in f.entry.drivers)
        winner = finishes[0].entry.drivers[0]
        info = {"week": self.week, "series_id": s.id if s else None, "event": event_idx,
                "track_id": track.id, "track": track.name, "winner": winner.id,
                "jewel": jewel, "jewel_name": jewel_name, "player": player_in, "field": len(finishes)}
        keep = jewel is not None or player_in or (s is not None and (s.tier >= 3 or s.scope != "track"))
        if keep:
            info["results"] = [
                [f.entry.drivers[0].id, f.entry.team_id, f.position, f.dnf,
                 [d.id for d in f.entry.drivers[1:]], f.box]
                for f in finishes]
            if race is not None:
                info["race"] = {"laps": race.laps, "cautions": race.cautions, "caution_laps": race.caution_laps,
                                "lead_changes": race.lead_changes, "leaders": race.leaders, "margin": race.margin}
                if player_in:
                    info["log"] = race.log[-400:]
        # Weekly local divisions keep just the winner (full results only where someone looks).
        self.race_log[jewel or s.id].append(info)
        if jewel is not None or (s is not None and s.tier >= 3):
            annals.note_race(world, track.id, jewel_name or s.name, winner.id)
        if s is not None:
            a = self.acc.get(winner.id)
            if a is not None and a.series_id == s.id:
                annals.first_win(world, winner, s, a.wins, track.name, self.week)
        if s is not None and s.tier == 7:
            world.post("race", f"{winner.name} wins the {s.name} race at {track.name}",
                       driver_id=winner.id, series_id=s.id, week=self.week)
        if player_in:
            me = next(f for f in finishes for d in f.entry.drivers if d.is_player)
            name = jewel_name or s.name
            pos = me.position
            text = (f"You won at {track.name} ({name})!" if pos == 1 else
                    f"You finished P{pos} of {len(finishes)} at {track.name} ({name})"
                    + (" - DNF" if me.dnf else ""))
            world.post("player", text, driver_id=world.player_id,
                       series_id=s.id if s else None, week=self.week, importance=3 if pos <= 3 else 1)
        return info


def series_state(world: "World", s: "Series") -> str:
    """Home state of a weekly division (its track); '' for tours and national series."""
    if s.scope != "track" or not s.schedule:
        return ""
    t = world.tracks.get(s.schedule[0])
    return (t.facts.region or "") if t is not None else ""


def run_season(world: "World", summary: "YearSummary") -> SeasonResults:
    runner = SeasonRunner(world, summary)
    world.season = runner
    return runner.run_to_end()


def world_seat_coverage(world: "World", d: Driver) -> float:
    """Share of the required seat funding actually delivered (set by the market)."""
    return world.seat_coverage.get(d.id, 1.0)


OFFSEASON_HEAL = 10


def _tally(world: "World", res: SeasonResults, acc: dict[int, _Acc], finishes: list[Finish],
           s: "Series", points: dict[int, float], purses: Purse, heat_pts: Optional[dict] = None,
           dnq: list[Entry] = (), system=None, track=None) -> None:
    n = len(finishes)
    heat_pts = heat_pts or {}
    tt = skill_track_type(track) if track is not None else None
    est_laps = engine.race_laps(track, s.tier) if track is not None else 0
    for f in finishes:
        pct = 1 - (f.position - 1) / max(1, n - 1)
        exp_pct = 1 - (f.expected_position - 1) / max(1, n - 1)
        lead = f.entry.drivers[0].id
        pts = points.get(lead, 0.0) + heat_pts.get(lead, 0.0)
        purse = purses.pay(f.position, n)
        for d in f.entry.drivers:
            if d.series_id != s.id:
                # Substitute appearance: tracked for breakout, not for the regular record.
                for i, (sid_d, sid, p) in enumerate(res.substitute_runs):
                    if sid_d == d.id and sid == s.id and p < 0:
                        res.substitute_runs[i] = (d.id, s.id, pct)
                        break
                d.career_starts += 1
                d.savings += purse * 0.35
                continue
            a = acc.get(d.id)
            if a is None:
                a = acc[d.id] = _Acc(series_id=s.id, team_id=d.team_id)
            a.starts += 1
            a.wins += f.position == 1
            a.top5 += f.position <= 5
            a.fin_pct_sum += pct
            a.exp_pct_sum += exp_pct
            eq = f.entry.equipment
            a.eq_sum += eq
            fit = res.par_fit.setdefault(s.id, [0, 0.0, 0.0, 0.0, 0.0])
            fit[0] += 1
            fit[1] += eq
            fit[2] += pct
            fit[3] += eq * pct
            fit[4] += eq * eq
            if tt is not None:
                sp = a.splits.setdefault(tt, [0, 0, 0, 0, 0])
                sp[0] += 1
                sp[1] += f.position == 1
                sp[2] += f.position <= 5
                sp[3] += f.position
                sp[4] += f.box["led"] if f.box else 0
            a.finish_sum += f.position
            a.expected_sum += f.expected_position
            a.field_sum += n
            a.points += pts
            a.purse += purse
            a.top10 += f.position <= 10
            b = f.box
            if b is not None:
                a.poles += b["start"] == 1
                a.laps_led += b["led"]
                a.laps += b["laps"]
                a.start_sum += b["start"]
                a.rating_sum += b["rating"]
                a.rated += 1
                a.fast_laps += b["fast_laps"]
            a.dnfs += f.dnf
        if tt is not None:
            laps_run = f.box["laps"] if f.box else est_laps
            for d in f.entry.drivers:
                tl = res.track_laps.setdefault(d.id, {})
                tl[tt] = tl.get(tt, 0) + laps_run
        for did in f.injured:
            d = world.drivers[did]
            severe = world.rng.random() < 0.12
            races = world.rng.randint(8, 30) if severe else world.rng.randint(1, 5)
            races = max(1, round(races / staff_mod.medical(world, d)[1] * (1.15 - d.durability / 330)))
            d.injury_races = max(d.injury_races, races)
            d.injury_history += 1
            res.injuries.append((did, races))
            if severe:
                d.log(world.year, f"seriously injured in a crash in the {s.name}")
                if s.tier >= 5 or d.is_player:
                    world.post("injury", f"{d.name} seriously injured in a {s.name} crash ({races} races out)",
                               driver_id=d.id, series_id=s.id, importance=2)


    for e in dnq:
        d = e.drivers[0]
        if d.series_id != s.id:
            continue
        a = acc.get(d.id)
        if a is None:
            a = acc[d.id] = _Acc(series_id=s.id, team_id=d.team_id)
        a.dnq += 1
        a.points += (system.dnq + system.show_up if system else 0.0) + heat_pts.get(d.id, 0.0)
        a.purse += purses.dnq()


def _serve_suspension(world: "World", d: Driver, track, series_id: str, week: int) -> None:
    """A suspended driver sat out a race that ran: one race of the suspension is served."""
    d.suspension = max(0, d.suspension - 1)
    if d.is_player:
        world.post("player", f"You sat out {track.name}: suspended by the series", driver_id=d.id,
                   series_id=series_id, week=week, importance=2)


def _substitute_pool(world: "World") -> list[Driver]:
    pool = []
    for d in world.drivers.values():
        if d.status in (SIDELINED, PART_TIME) and d.max_tier >= 2 and d.injury_races <= 0:
            pool.append(d)
        elif d.status == ACTIVE and d.tier <= 4 and d.max_tier >= 2 and d.injury_races <= 0:
            pool.append(d)
    return pool


def _pick_substitute(world: "World", pool: list[Driver], s: "Series", track, team,
                     busy: set[int] = frozenset()) -> Optional[Driver]:
    """Owners call someone they know: proven veterans, their development drivers, or hot prospects."""
    tpl = s.template
    rng = world.rng
    best, best_score = None, -1e9
    sample = rng.sample(pool, min(60, len(pool))) if pool else []
    for d in sample:
        if d.id in busy or d.injury_races > 0 or d.suspension > 0 or d.status == RETIRED or d.is_player:
            continue
        age = d.age(world.year)
        if age < tpl.min_age or not tpl.age_allows_track(age, track):
            continue
        if d.tier >= tpl.tier or d.max_tier < tpl.tier - 3:
            continue
        conn = d.connections.get(f"team:{team.id}", 0) + (
            d.connections.get(f"mfr:{team.manufacturer_id}", 0) if team.manufacturer_id else 0)
        score = (d.demonstrated + d.reputation * 0.3 + conn * 30
                 + d.proficiency.get(tpl.discipline, 0) * 20 + rng.gauss(0, 5))
        if score > best_score:
            best, best_score = d, score
    if best is not None:
        key = f"team:{team.id}"
        best.connections[key] = max(best.connections.get(key, 0.0), 0.5)
    return best


def _crown_jewel(world: "World", runner: "SeasonRunner", cj) -> Optional[dict]:
    rng = world.rng
    res, acc, entered = runner.res, runner.acc, runner.entered_jewels
    track = world.tracks.get(cj.track_id)
    candidates = []
    forced = []
    for d in world.drivers.values():
        if d.status not in (ACTIVE, PART_TIME) or d.injury_races > 0 or d.suspension > 0:
            continue
        if d.is_player:
            # The player chooses which crown jewels to enter (UI); the AI never enters for them.
            if (cj.key in world.player_jewels and jewel_eligible(world, d, cj)
                    and entered.get(d.id, 0) < MAX_JEWELS_PER_SEASON):
                forced.append(d)
            continue
        if entered.get(d.id, 0) >= MAX_JEWELS_PER_SEASON:  # a crowded calendar: pick your big races
            continue
        if not jewel_eligible(world, d, cj):
            continue
        dist = math.hypot(d.lat - (track.facts.lat or 0), (d.lon - (track.facts.lon or 0)) * 0.8) * 69
        appeal = (d.reputation + d.demonstrated) / 2 + d.tier * 4 - dist / 60
        # Travel + entry cost deters under-funded racers far from the venue.
        if d.available_funding() < 3000 + dist * 4 and d.tier <= 3:
            continue
        candidates.append((appeal + rng.gauss(0, 10), d))
    candidates.sort(key=lambda x: -x[0])
    field_drivers = forced + [d for _, d in candidates[: cj.entrants - len(forced)]]
    if len(field_drivers) < 6:
        return None
    for d in field_drivers:
        entered[d.id] = entered.get(d.id, 0) + 1
        if d.is_player:
            charge(d, jewel_entry_cost(d, track))
    entries = [Entry([d], _jewel_equipment(world, res, d, cj, rng)) for d in field_drivers]
    rr = engine.run(entries, track, max(cj.max_tier - 1, 2), 0.45, rng,
                    detail=any(d.is_player for d in field_drivers), free_pass=world.year >= 2003,
                    discipline=cj.discipline)
    finishes = rr.finishes
    morale_mod.incidents(world, rr.incidents)
    for att, tgt in rr.paybacks:
        morale_mod.payback(world, att, tgt, max(cj.max_tier - 1, 2), cj.name, track.name, runner.week)
    order = [f.entry.drivers[0].id for f in finishes]
    res.crown_jewel_results.append((cj.key, order))
    winner = world.drivers[order[0]]
    winner.crown_jewels.append(f"{world.year} {cj.name}")
    winner.savings += cj.purse_win * 0.5
    winner.log(world.year, f"won the {cj.name} at {track.name}")
    world.post("jewel", f"{winner.name} wins the {cj.name} at {track.name}", driver_id=winner.id,
               week=runner.week, importance=2)
    for pos, did in enumerate(order[:10], start=1):
        pay = purse_for(pos, len(order), cj.purse_win) * 0.5
        a = acc.get(did)
        if a is not None:
            a.purse += pay
        d = world.drivers[did]
        if d.is_player and d.car is not None and d.car.account is not None and pay:
            d.car.account += pay
            d.car.winnings += pay
            garage.log(d.car, runner.week, f"{cj.name} purse, P{pos}", pay)
    return runner._log(None, track, finishes, 0, jewel=cj.key, jewel_name=cj.name, race=rr)


def _jewel_equipment(world: "World", res: SeasonResults, d: Driver, cj, rng) -> float:
    """Regulars bring their own car; outsiders rent or borrow one (Cup stars in midgets do too)."""
    own_series = world.pyramid.series.get(d.series_id) if d.series_id else None
    if own_series is not None and own_series.discipline == cj.discipline:
        return res.equipment.get(d.id, 50.0)
    money = d.available_funding()
    return clamp(45 + 10 * math.log10(max(money, 1_000) / 10_000) + rng.gauss(0, 5), 30, 75)


MAX_JEWELS_PER_SEASON = 3


def jewel_block_reasons(world: "World", d: Driver, cj, track=None) -> list[str]:
    """Why ``d`` can't enter this crown jewel (empty = eligible). The player may also
    reach one tier up: a weekly racer's shot at the big show."""
    why = []
    if d.age(world.year) < 14:
        why.append("age 14+")
    if d.status not in (ACTIVE, PART_TIME):
        why.append("no current ride")
    if d.injury_races > 0:
        why.append("injured")
    lo = cj.min_tier - 1 if d.is_player else cj.min_tier
    if not (lo <= d.tier <= cj.max_tier):
        why.append(f"tier {cj.min_tier}-{cj.max_tier}")
    if not (d.primary_discipline == cj.discipline or any(r.discipline == cj.discipline for r in d.history[-5:])):
        why.append(cj.discipline.replace("_", " ") + " experience")
    if d.is_player and track is not None and d.available_funding() < jewel_entry_cost(d, track):
        why.append(f"${jewel_entry_cost(d, track):,.0f} entry + travel")
    return why


def jewel_eligible(world: "World", d: Driver, cj) -> bool:
    return not jewel_block_reasons(world, d, cj, world.tracks.get(cj.track_id) if d.is_player else None)


def charge(d: Driver, amount: float) -> None:
    """One-off cost: the open racing account first (player's own car), then savings, the rest out of
    this season's racing money."""
    car = d.car
    if car is not None and car.account is not None and car.account > 0:
        take = min(car.account, amount)
        car.account -= take
        amount -= take
    from_savings = min(d.savings, amount)
    d.savings -= from_savings
    d.season_spend += amount - from_savings


def jewel_entry_cost(d: Driver, track) -> float:
    dist = math.hypot(d.lat - (track.facts.lat or 0), (d.lon - (track.facts.lon or 0)) * 0.8) * 69
    return 2500 + dist * 4


def positions_above_replacement(fit: Optional[list], rows: list[tuple[int, _Acc]]) -> dict[int, float]:
    """PAR, a racing WAR: how much better a driver finished than a replacement-level driver would have
    in the same cars.

    Per series and season: finishing percentile (1 = win, 0 = last) is regressed on the car's equipment
    across every start, which says what each car should do. A driver's edge is their average finish
    against that line. Replacement level is the 20th percentile of the regulars' edges - the kind of
    driver a team can always find. PAR = (edge - replacement) x starts, scaled to a 30-race season
    and halved: one PAR is about two last-to-first swings (some 80 positions in a 40-car field).
    Like baseball's WAR, a solid regular is worth 2-4 a season and a great season 6-9, whether the
    series runs 10 races or 80.
    """
    if not fit or fit[0] < 10 or fit[0] != sum(a.starts for _, a in rows):
        return {}      # (a mid-season save from before PAR existed: this season's data is incomplete)
    n, sx, sy, sxy, sxx = fit
    var = sxx - sx * sx / n
    b = (sxy - sx * sy / n) / var if var > 1e-6 else 0.0
    a0 = (sy - b * sx) / n
    edge = {}
    for did, a in rows:
        if a.starts:
            edge[did] = a.fin_pct_sum / a.starts - (a0 + b * a.eq_sum / a.starts)
    most = max((a.starts for _, a in rows), default=0)
    regular = sorted(edge[did] for did, a in rows if did in edge and a.starts >= max(2, most / 3))
    if len(regular) < 5:
        return {}
    repl = regular[len(regular) // 5]
    # Scaled to a 30-race season so an 80-race sprint-car tour and a 10-race sports-car season compare.
    events = max(a.starts for _, a in rows)
    scale = min(2.0, max(0.4, 30 / max(events, 1))) / 2
    return {did: round((e - repl) * a.starts * scale, 1) for did, a in rows if (e := edge.get(did)) is not None}


def _finalise_records(world: "World", res: SeasonResults, acc: dict[int, _Acc], summary,
                      runner: Optional["SeasonRunner"] = None) -> None:
    by_series: dict[str, list[tuple[int, _Acc]]] = defaultdict(list)
    for did, a in acc.items():
        by_series[a.series_id].append((did, a))
    for sid, rows in by_series.items():
        s = world.series(sid)
        events = len(s.schedule)
        # Same order as the live standings (playoff formats included).
        rows.sort(key=runner.rank_key(sid) if runner else (lambda r: (-r[1].points, -r[1].wins)))
        purse = runner.purse(s) if runner else Purse(s.template, world.year)
        n = len(rows)
        par = positions_above_replacement(res.par_fit.get(sid), rows)
        for pos, (did, a) in enumerate(rows, start=1):
            d = world.drivers[did]
            fund = purse.points_fund(pos) if a.starts else 0.0
            a.purse += fund
            champion = pos == 1 and a.starts >= 0.6 * events
            if d.is_player and d.car is not None and d.car.account is not None:
                # The player's purses went into the racing account race by race.
                d.car.account += fund
                d.car.winnings += fund
                if fund:
                    garage.log(d.car, SEASON_WEEKS, f"Points fund, P{pos} in the championship", fund)
            rec = SeasonRecord(
                year=world.year, series_id=sid, tier=s.tier, discipline=s.discipline,
                team_id=a.team_id, starts=a.starts, wins=a.wins, top5=a.top5,
                avg_finish=a.finish_sum / a.starts if a.starts else float(s.template.field_size),
                expected_finish=a.expected_sum / a.starts if a.starts else float(s.template.field_size),
                championship_pos=pos, field_size=n, champion=champion, series_name=s.name,
                points=round(a.points, 1), top10=max(a.top10, a.top5), winnings=round(a.purse), dnq=a.dnq,
                poles=a.poles, laps_led=a.laps_led, laps=a.laps, dnfs=a.dnfs,
                avg_start=round(a.start_sum / a.rated, 1) if a.rated else None,
                rating=round(a.rating_sum / a.rated, 1) if a.rated else None,
            )
            st = max(a.starts, 1)  # a season of DNQs: no feature starts at all
            rec.note = f"{a.fin_pct_sum / st:.3f}|{a.exp_pct_sum / st:.3f}"
            rec.par = par.get(did)
            if s.tier >= 3 or d.is_player:
                rec.splits = {k: list(v) for k, v in a.splits.items()}
            d.history.append(rec)
            d.career_starts += a.starts
            d.career_wins += a.wins
            # Purse: self-run racers reinvest winnings; hired drivers keep a share (~35%).
            if not (d.is_player and d.car is not None and d.car.account is not None):
                d.savings += a.purse * (0.35 if s.template.team_based else 0.15)
            res.records[did] = rec
            if champion:
                title = f"{world.year} {s.name}"
                d.titles.append(title)
                res.champions[sid] = did
                summary.champions[sid] = did
                if s.tier >= 3:
                    d.log(world.year, f"won the {s.name} championship")
    # Crown-jewel wins attach to the season record
    for key, order in res.crown_jewel_results:
        rec = res.records.get(order[0])
        if rec is not None:
            rec.crown_jewel_wins.append(key)
    # Substitute performance -> breakout flag
    for did, sid, pct in res.substitute_runs:
        if pct < 0:
            continue
        d = world.drivers[did]
        if pct >= 1 - SUBSTITUTE_BREAKOUT_FINISH_PCT:
            if d.breakout < 2:
                d.log(world.year, f"impressed as a substitute in the {world.series(sid).name}")
            d.breakout = 2
            d.connections[f"series:{sid}"] = 1.0
