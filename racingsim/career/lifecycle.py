"""Aging, development, attrition, comebacks and new entrants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..constants import GRASSROOTS_RETURN_PROB, QUIT_HAZARD_BY_TIER, TIER_STRENGTH
from ..util import clamp, weighted_choice
from ..world.entities import ACTIVE, PART_TIME, RETIRED, SIDELINED, Driver

if TYPE_CHECKING:
    from ..sim.season import SeasonResults
    from ..world.world import World, YearSummary


def develop(world: "World", results: "SeasonResults") -> None:
    rng = world.rng
    for d in world.drivers.values():
        if d.status == RETIRED:
            continue
        age = d.age(world.year)
        rec = results.records.get(d.id)
        starts = rec.starts if rec else 0
        seat_time = min(1.0, starts / 18)
        if age <= d.peak_age:
            rate = 0.20 if age < 15 else 0.15 if age < 19 else 0.11 if age < 24 else 0.07
            coaching = 1 + 0.035 * d.tier  # better teams, engineers, coaches higher up
            drive = 0.75 + d.determination / 250 + d.professionalism / 500
            growth = (d.potential - d.ability) * rate * (0.35 + 0.65 * seat_time) * coaching * drive
            d.ability = clamp(d.ability + growth + rng.gauss(0, 1.0), 1, d.potential + 1)
            # Rare late breakthroughs (research C 5.5 "late window")
            if 24 <= age <= 33 and rng.random() < 0.015:
                bump = rng.uniform(3, 8)
                d.potential = clamp(d.potential + bump, 0, 99)
        else:
            decline = 0.12 * (age - d.peak_age) + rng.gauss(0, 0.5)
            d.ability = clamp(d.ability - max(0.0, decline), 1, 99)
            d.potential = min(d.potential, d.ability + 1)
        if rec is not None:
            disc = rec.discipline
            prof = d.proficiency.get(disc, 0.0)
            learn = starts / (starts + 25) * (0.5 + d.adaptability / 100)
            d.proficiency[disc] = round(min(1.0, prof + (1 - prof) * learn), 3)
        # Off-track: marketability rises with success and youth, fades with obscurity.
        if rec is not None and (rec.champion or rec.wins >= 3):
            d.marketability = clamp(d.marketability + rng.uniform(0.5, 2.5))
        elif d.status == SIDELINED:
            d.marketability = clamp(d.marketability - 1.0)
        if d.breakout > 0:
            d.breakout -= 1
        # Team/manufacturer relationships decay unless refreshed by working together.
        for key in list(d.connections):
            if d.team_id is not None and key == f"team:{d.team_id}":
                d.connections[key] = min(1.0, d.connections[key] + 0.15)
            else:
                d.connections[key] *= 0.85
                if d.connections[key] < 0.05:
                    del d.connections[key]
        if d.team_id is not None:
            d.connections.setdefault(f"team:{d.team_id}", 0.3)
            team = world.teams.get(d.team_id)
            if team and team.manufacturer_id:
                key = f"mfr:{team.manufacturer_id}"
                d.connections[key] = min(1.0, d.connections.get(key, 0) + 0.2)


def retirements(world: "World", results: "SeasonResults", summary: "YearSummary") -> list[Driver]:
    """Drivers quit (money, age, results, injury) or step back to grassroots racing."""
    rng = world.rng
    retired = []
    for d in list(world.drivers.values()):
        if d.status == RETIRED:
            continue
        age = d.age(world.year)
        tier = d.tier if d.series_id else max(0, d.max_tier - 1)
        h = QUIT_HAZARD_BY_TIER[min(tier, 7)]
        rec = results.records.get(d.id)
        if age < 16:
            h = 0.11  # families step away from youth racing
        if d.status == SIDELINED:
            h += 0.18 * d.seasons_sidelined + 0.1
        if rec is not None and rec.field_size > 3:
            fin = 1 - (rec.avg_finish - 1) / max(1, rec.field_size - 1)
            if fin < 0.3:
                h += 0.04
        if age > 38:
            h += 0.025 * (age - 38) * (1.6 if tier >= 5 else 1.0)
        if age > 60:
            h += 0.15
        if d.injury_races > 10:
            h += 0.2
        h *= 1.5 - d.determination / 100
        if rng.random() >= clamp(h, 0, 0.95):
            continue
        # Veterans who lose national rides often go back to short tracks (research A 11, C 5.7).
        if d.max_tier >= 5 and age <= 58 and d.tier >= 4 and rng.random() < GRASSROOTS_RETURN_PROB:
            if _return_to_grassroots(world, d):
                continue
        retire(world, d, summary)
        retired.append(d)
    return retired


def retire(world: "World", d: Driver, summary: "YearSummary") -> None:
    if d.team_id is not None:
        team = world.teams.get(d.team_id)
        if team:
            team.roster = [None if x == d.id else x for x in team.roster]
    if d.program_mfr is not None:
        m = world.manufacturers.get(d.program_mfr)
        if m and d.id in m.prospects:
            m.prospects.remove(d.id)
    d.status = RETIRED
    d.series_id = None
    d.team_id = None
    d.sponsors.clear()
    summary.retirements += 1
    if d.max_tier >= 4:
        d.log(world.year, f"retired from driving at {d.age(world.year)}")


def _return_to_grassroots(world: "World", d: Driver) -> bool:
    """Former pro self-funds a local headline division near home, using savings."""
    from .market import release_seat
    release_seat(world, d)
    options = [s for s in world.pyramid.series.values()
               if s.scope == "track" and s.tier == 2 and s.discipline in (d.primary_discipline, "dirt_oval", "stock_car")]
    if not options:
        return False
    from ..util import haversine_mi
    options.sort(key=lambda s: haversine_mi(d.lat, d.lon, s.anchor_lat, s.anchor_lon))
    s = options[0]
    d.series_id = s.id
    d.tier = s.tier
    d.home_track_id = s.region_key
    d.status = ACTIVE
    d.family_budget = max(d.family_budget, s.template.season_cost * 0.8)
    d.log(world.year, f"stepped back to weekly racing in the {s.name}")
    return True


def new_entrants(world: "World", summary: "YearSummary", count: int) -> list[Driver]:
    """Each year a new cohort arrives: mostly kids, plus teen and adult late starters."""
    from ..world.factory import make_driver
    from .market import choose_self_run
    rng = world.rng
    created = []
    for _ in range(count):
        roll = rng.random()
        if roll < 0.55:
            age = int(clamp(rng.gauss(8, 2), 5, 13))
            youth = True
        elif roll < 0.85:
            age = int(clamp(rng.gauss(17, 3), 13, 30))
            youth = False
        else:
            age = int(clamp(rng.gauss(33, 8), 22, 60))  # late starters: club racing, local divisions
            youth = False
        region = world.geo.random_home(rng)
        discipline = world.geo.favoured_discipline(rng, region, youth=age < 14)
        if age >= 22 and rng.random() < 0.45:
            discipline = "club_road"
        ability = clamp(rng.gauss(TIER_STRENGTH[0] + (age - 8) * 0.6 if age < 18 else 34, 7), 5, 70)
        d = make_driver(world, discipline=discipline, age=age, region=region, ability=ability,
                        years_racing=0.3)
        d.first_season = world.year + 1
        d.first_license_age = age
        d.reputation = 1.0
        d.demonstrated = clamp(ability + rng.gauss(0, 6), 5, 80)
        world.drivers[d.id] = d
        if choose_self_run(world, d, entrant=True):
            created.append(d)
        else:
            del world.drivers[d.id]
    summary.new_entrants += len(created)
    return created
