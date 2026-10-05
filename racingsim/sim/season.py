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


def run_season(world: "World", summary: "YearSummary") -> SeasonResults:
    rng = world.rng
    res = SeasonResults()
    acc: dict[int, _Acc] = {}
    attendance: dict[int, float] = {}

    by_series: dict[str, list[Driver]] = defaultdict(list)
    for d in world.drivers.values():
        if d.status in (ACTIVE, PART_TIME) and d.series_id in world.pyramid.series:
            by_series[d.series_id].append(d)

    # Pre-season: equipment for every entrant.
    for sid, drivers in by_series.items():
        s = world.series(sid)
        for d in drivers:
            if s.template.team_based and d.team_id in world.teams:
                team = world.teams[d.team_id]
                covered = world_seat_coverage(world, d)
                res.equipment[d.id] = clamp(team.equipment - (1 - covered) * 25 + rng.gauss(0, 2), 5, 99)
                attendance[d.id] = 1.0 if covered >= 0.6 else clamp(covered / 0.6, 0.3, 1.0)
            else:
                eq, att = self_run_equipment(world, d, s)
                res.equipment[d.id] = eq
                attendance[d.id] = att * (0.6 if d.status == PART_TIME else 1.0)

    sub_pool = _substitute_pool(world)

    for sid, drivers in by_series.items():
        s = world.series(sid)
        tpl = s.template
        for event_idx, track_id in enumerate(s.schedule):
            track = world.tracks.get(track_id)
            entries: list[Entry] = []
            if tpl.team_based:
                for team in world.teams_in(sid):
                    for car in range(team.cars):
                        car_drivers = []
                        for slot in range(car * team.drivers_per_car, (car + 1) * team.drivers_per_car):
                            did = team.roster[slot] if slot < len(team.roster) else None
                            d = world.drivers.get(did) if did else None
                            if d is None or d.status == RETIRED:
                                continue
                            if (d.injury_races > 0 or not tpl.age_allows_track(d.age(world.year), track)
                                    or rng.random() > attendance.get(d.id, 1.0)):
                                sub = _pick_substitute(world, sub_pool, s, track, team)
                                if sub is not None:
                                    res.substitute_runs.append((sub.id, sid, -1.0))
                                    res.equipment.setdefault(sub.id, team.equipment)
                                    car_drivers.append(sub)
                                continue
                            car_drivers.append(d)
                        if car_drivers:
                            entries.append(Entry(car_drivers, res.equipment.get(car_drivers[0].id, team.equipment),
                                                 team_id=team.id, car_key=f"{team.id}:{car}"))
            else:
                pool = [d for d in drivers if d.injury_races <= 0
                        and rng.random() < attendance.get(d.id, 1.0)]
                cap = int(tpl.field_size * 1.5)
                if len(pool) > cap:
                    pool = rng.sample(pool, cap)
                entries = [Entry([d], res.equipment[d.id]) for d in pool]
            if len(entries) < 3:
                continue
            finishes = run_race(entries, track, tpl.discipline, tpl.tier, tpl.car_weight, rng)
            _tally(world, res, acc, finishes, s)
            _tick_injuries(entries)

    _crown_jewels(world, res, acc)
    _finalise_records(world, res, acc, summary)
    return res


def world_seat_coverage(world: "World", d: Driver) -> float:
    """Share of the required seat funding actually delivered (set by the market)."""
    return world.seat_coverage.get(d.id, 1.0)


def _tick_injuries(entries: list[Entry]) -> None:
    for e in entries:
        for d in e.drivers:
            if d.injury_races > 0:
                d.injury_races -= 1


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
                d.log(world.year, f"seriously injured in a crash at {world.tracks.get(s.schedule[0]).name if s.scope == 'track' else s.name}")


def _substitute_pool(world: "World") -> list[Driver]:
    pool = []
    for d in world.drivers.values():
        if d.status in (SIDELINED, PART_TIME) and d.max_tier >= 2 and d.injury_races <= 0:
            pool.append(d)
        elif d.status == ACTIVE and d.tier <= 4 and d.max_tier >= 2 and d.injury_races <= 0:
            pool.append(d)
    return pool


def _pick_substitute(world: "World", pool: list[Driver], s: "Series", track, team) -> Optional[Driver]:
    """Owners call someone they know: proven veterans, their development drivers, or hot prospects."""
    tpl = s.template
    rng = world.rng
    best, best_score = None, -1e9
    sample = rng.sample(pool, min(60, len(pool))) if pool else []
    for d in sample:
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


def _crown_jewels(world: "World", res: SeasonResults, acc: dict[int, _Acc]) -> None:
    rng = world.rng
    entered: dict[int, int] = {}
    for cj in world.pyramid.crown_jewels:
        track = world.tracks.get(cj.track_id)
        candidates = []
        for d in world.drivers.values():
            if d.status not in (ACTIVE, PART_TIME) or d.injury_races > 0:
                continue
            if entered.get(d.id, 0) >= 3:  # a crowded calendar: pick your big races
                continue
            if not (cj.min_tier <= d.tier <= cj.max_tier):
                continue
            if d.primary_discipline != cj.discipline and not any(
                    r.discipline == cj.discipline for r in d.history[-5:]):
                continue
            if d.age(world.year) < 14:
                continue
            dist = math.hypot(d.lat - (track.facts.lat or 0), (d.lon - (track.facts.lon or 0)) * 0.8) * 69
            appeal = (d.reputation + d.demonstrated) / 2 + d.tier * 4 - dist / 60
            # Travel + entry cost deters under-funded racers far from the venue.
            if d.available_funding() < 3000 + dist * 4 and d.tier <= 3:
                continue
            candidates.append((appeal + rng.gauss(0, 10), d))
        candidates.sort(key=lambda x: -x[0])
        field_drivers = [d for _, d in candidates[: cj.entrants]]
        if len(field_drivers) < 6:
            continue
        for d in field_drivers:
            entered[d.id] = entered.get(d.id, 0) + 1
        entries = [Entry([d], res.equipment.get(d.id, 50.0)) for d in field_drivers]
        finishes = run_race(entries, track, cj.discipline, max(cj.max_tier - 1, 2), 0.45, rng)
        order = [f.entry.drivers[0].id for f in finishes]
        res.crown_jewel_results.append((cj.key, order))
        winner = world.drivers[order[0]]
        winner.crown_jewels.append(f"{world.year} {cj.name}")
        winner.savings += cj.purse_win * 0.5
        winner.log(world.year, f"won the {cj.name} at {track.name}")
        for pos, did in enumerate(order[:10], start=1):
            a = acc.get(did)
            if a is not None:
                a.purse += purse_for(pos, len(order), cj.purse_win) * 0.5


def _finalise_records(world: "World", res: SeasonResults, acc: dict[int, _Acc], summary) -> None:
    by_series: dict[str, list[tuple[int, _Acc]]] = defaultdict(list)
    for did, a in acc.items():
        by_series[a.series_id].append((did, a))
    for sid, rows in by_series.items():
        s = world.series(sid)
        events = len(s.schedule)
        rows.sort(key=lambda r: -r[1].points)
        n = len(rows)
        for pos, (did, a) in enumerate(rows, start=1):
            d = world.drivers[did]
            champion = pos == 1 and a.starts >= 0.6 * events
            rec = SeasonRecord(
                year=world.year, series_id=sid, tier=s.tier, discipline=s.discipline,
                team_id=a.team_id, starts=a.starts, wins=a.wins, top5=a.top5,
                avg_finish=a.finish_sum / a.starts, expected_finish=a.expected_sum / a.starts,
                championship_pos=pos, field_size=n, champion=champion,
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
