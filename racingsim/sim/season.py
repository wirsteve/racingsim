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
from .race import Entry, Finish, points_for, run_race

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
    points: int = 0
    purse: float = 0.0
    team_id: Optional[int] = None


@dataclass
class SeasonResults:
    records: dict[int, SeasonRecord] = field(default_factory=dict)
    champions: dict[str, int] = field(default_factory=dict)
    crown_jewel_results: list[tuple[str, list[int]]] = field(default_factory=list)
    substitute_runs: list[tuple[int, str, float]] = field(default_factory=list)  # (driver, series, finish pct)
    injuries: list[tuple[int, int]] = field(default_factory=list)                 # (driver, races)
    equipment: dict[int, float] = field(default_factory=dict)


def purse_for(position: int, field_size: int, purse_win: float) -> float:
    if purse_win <= 0:
        return 0.0
    return purse_win * max(0.04, 1.0 / (1.0 + 0.45 * (position - 1)))


def self_run_equipment(world: "World", d: Driver, series: "Series") -> tuple[float, float]:
    """Return (equipment rating, attendance share) for a driver running their own car."""
    from ..career.market import season_cost_for
    cost = season_cost_for(world, d, series)
    funds = d.available_funding()
    ratio = funds / cost if cost > 0 else 1.0
    attendance = 1.0 if ratio >= 0.8 else clamp(ratio / 0.8, 0.25, 1.0)
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

        self.sub_pool = _substitute_pool(world)
        self.calendar: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for sid in sorted(self.by_series):
            n = len(world.series(sid).schedule)
            for i in range(n):
                self.calendar[1 + (i * SEASON_WEEKS) // max(n, 1)].append((sid, i))
        self.jewels: dict[int, list] = defaultdict(list)
        for i, cj in enumerate(world.pyramid.crown_jewels):
            self.jewels[cj.week or (3 + i * 2) % SEASON_WEEKS + 1].append(cj)

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
            _finalise_records(self.world, self.res, self.acc, self.summary)
            for d in self.world.drivers.values():
                if d.injury_races > 0:  # the winter break heals too
                    d.injury_races = max(0, d.injury_races - OFFSEASON_HEAL)
                d.season_spend = 0.0
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
        rows.sort(key=lambda r: (-r[1].points, -r[1].wins))
        return rows

    # ------------------------------------------------------------------ events
    def _run_event(self, sid: str, event_idx: int) -> Optional[dict]:
        world, res, rng = self.world, self.res, self.world.rng
        s = world.series(sid)
        tpl = s.template
        track_id = s.schedule[event_idx]
        track = world.tracks.get(track_id)
        drivers = self.by_series[sid]
        entries: list[Entry] = []
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
                        if (d.injury_races > 0 or not tpl.age_allows_track(d.age(world.year), track)
                                or rng.random() > self.attendance.get(d.id, 1.0)):
                            sub = _pick_substitute(world, self.sub_pool, s, track, team, self.busy)
                            if sub is not None:
                                res.substitute_runs.append((sub.id, sid, -1.0))
                                self.busy.add(sub.id)
                                car_drivers.append(sub)
                            continue
                        car_drivers.append(d)
                    if car_drivers:
                        # The car is the team's, whoever drives it.
                        entries.append(Entry(car_drivers, car_eq, team_id=team.id, car_key=f"{team.id}:{car}"))
        else:
            pool = [d for d in drivers if d.injury_races <= 0
                    and (d.is_player or rng.random() < self.attendance.get(d.id, 1.0))]
            cap = int(tpl.field_size * 1.5)
            if len(pool) > cap:
                keep = [d for d in pool if d.is_player]
                pool = keep + rng.sample([d for d in pool if not d.is_player], cap - len(keep))
            entries = [Entry([d], res.equipment[d.id]) for d in pool]
        if len(entries) < 3:
            return None
        finishes = run_race(entries, track, tpl.discipline, tpl.tier, tpl.car_weight, rng)
        _tally(world, res, self.acc, finishes, s)
        return self._log(s, track, finishes, event_idx)

    def _log(self, s: "Series", track, finishes: list[Finish], event_idx: int,
             jewel: Optional[str] = None, jewel_name: Optional[str] = None) -> Optional[dict]:
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
                 [d.id for d in f.entry.drivers[1:]]]
                for f in finishes]
        # Weekly local divisions keep just the winner (full results only where someone looks).
        self.race_log[jewel or s.id].append(info)
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


def run_season(world: "World", summary: "YearSummary") -> SeasonResults:
    runner = SeasonRunner(world, summary)
    world.season = runner
    return runner.run_to_end()


def world_seat_coverage(world: "World", d: Driver) -> float:
    """Share of the required seat funding actually delivered (set by the market)."""
    return world.seat_coverage.get(d.id, 1.0)


OFFSEASON_HEAL = 10


def _tally(world: "World", res: SeasonResults, acc: dict[int, _Acc], finishes: list[Finish],
           s: "Series") -> None:
    n = len(finishes)
    tpl = s.template
    for f in finishes:
        pct = 1 - (f.position - 1) / max(1, n - 1)
        exp_pct = 1 - (f.expected_position - 1) / max(1, n - 1)
        pts = points_for(f.position, n)
        purse = purse_for(f.position, n, tpl.purse_win)
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
            a.finish_sum += f.position
            a.expected_sum += f.expected_position
            a.field_sum += n
            a.points += pts
            a.purse += purse
        for did in f.injured:
            d = world.drivers[did]
            severe = world.rng.random() < 0.12
            races = world.rng.randint(8, 30) if severe else world.rng.randint(1, 5)
            d.injury_races = max(d.injury_races, races)
            d.injury_history += 1
            res.injuries.append((did, races))
            if severe:
                d.log(world.year, f"seriously injured in a crash in the {s.name}")
                if s.tier >= 5 or d.is_player:
                    world.post("injury", f"{d.name} seriously injured in a {s.name} crash ({races} races out)",
                               driver_id=d.id, series_id=s.id, importance=2)


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
        if d.id in busy or d.injury_races > 0 or d.status == RETIRED or d.is_player:
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
        if d.status not in (ACTIVE, PART_TIME) or d.injury_races > 0:
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
    finishes = run_race(entries, track, cj.discipline, max(cj.max_tier - 1, 2), 0.45, rng)
    order = [f.entry.drivers[0].id for f in finishes]
    res.crown_jewel_results.append((cj.key, order))
    winner = world.drivers[order[0]]
    winner.crown_jewels.append(f"{world.year} {cj.name}")
    winner.savings += cj.purse_win * 0.5
    winner.log(world.year, f"won the {cj.name} at {track.name}")
    world.post("jewel", f"{winner.name} wins the {cj.name} at {track.name}", driver_id=winner.id,
               week=runner.week, importance=2)
    for pos, did in enumerate(order[:10], start=1):
        a = acc.get(did)
        if a is not None:
            a.purse += purse_for(pos, len(order), cj.purse_win) * 0.5
    return runner._log(None, track, finishes, 0, jewel=cj.key, jewel_name=cj.name)


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
    """One-off cost: savings first, the rest out of this season's racing money."""
    from_savings = min(d.savings, amount)
    d.savings -= from_savings
    d.season_spend += amount - from_savings


def jewel_entry_cost(d: Driver, track) -> float:
    dist = math.hypot(d.lat - (track.facts.lat or 0), (d.lon - (track.facts.lon or 0)) * 0.8) * 69
    return 2500 + dist * 4


def _finalise_records(world: "World", res: SeasonResults, acc: dict[int, _Acc], summary) -> None:
    by_series: dict[str, list[tuple[int, _Acc]]] = defaultdict(list)
    for did, a in acc.items():
        by_series[a.series_id].append((did, a))
    for sid, rows in by_series.items():
        s = world.series(sid)
        events = len(s.schedule)
        rows.sort(key=lambda r: (-r[1].points, -r[1].wins))  # same order as the live standings
        n = len(rows)
        for pos, (did, a) in enumerate(rows, start=1):
            d = world.drivers[did]
            champion = pos == 1 and a.starts >= 0.6 * events
            rec = SeasonRecord(
                year=world.year, series_id=sid, tier=s.tier, discipline=s.discipline,
                team_id=a.team_id, starts=a.starts, wins=a.wins, top5=a.top5,
                avg_finish=a.finish_sum / a.starts, expected_finish=a.expected_sum / a.starts,
                championship_pos=pos, field_size=n, champion=champion, series_name=s.name,
            )
            rec.note = f"{a.fin_pct_sum / a.starts:.3f}|{a.exp_pct_sum / a.starts:.3f}"
            d.history.append(rec)
            d.career_starts += a.starts
            d.career_wins += a.wins
            # Purse: self-run racers reinvest winnings; hired drivers keep a share (~35%).
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
