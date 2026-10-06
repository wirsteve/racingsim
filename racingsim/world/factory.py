"""Procedural creation of drivers, teams, sponsors and manufacturers."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Optional

from ..constants import (
    FAMILY_BUDGET_MEDIAN, FAMILY_BUDGET_SIGMA, INVESTMENT_FAMILY_SHARE, PRODIGY_SHARE,
    REPRESENTATION_RATIO, TIER_SPREAD, TIER_STRENGTH,
)
from ..util import clamp, lognormal_money, weighted_choice
from . import names
from .entities import DISCIPLINES, Driver, Manufacturer, Sponsor, Team

if TYPE_CHECKING:
    from .regions import Region
    from .series import Series
    from .world import World


PRO_FUNDING_FLOOR = {4: 0.2, 5: 0.25, 6: 0.35, 7: 0.75}


def _trait(rng: random.Random, mean: float = 50, sd: float = 15) -> float:
    return clamp(rng.gauss(mean, sd), 1, 99)


def family_budget(rng: random.Random, region: "Region", age: int = 30) -> float:
    """What the household will put into racing per season.

    Kids depend on parents; working adults fund their own hobby racing, and their
    budgets grow through their 20s-40s. Stronger local economies skew money up.
    """
    median = FAMILY_BUDGET_MEDIAN * (0.75 + region.sponsor_market / 160)
    if age >= 22:
        median *= 1.0 + min(age - 22, 20) * 0.04
    return lognormal_money(rng, median, FAMILY_BUDGET_SIGMA)


def start_age_for(rng: random.Random, discipline: str, youth: bool) -> int:
    """First competitive race age (research C 4.1 / 5.1)."""
    if not youth:
        return int(clamp(rng.gauss(24, 8), 16, 55))
    if discipline == "karting":
        return int(clamp(rng.gauss(7, 2), 5, 13))
    if discipline == "dirt_oval":
        return int(clamp(rng.gauss(9, 2.5), 5, 15))
    return int(clamp(rng.gauss(8, 2.5), 5, 14))


def make_driver(world: "World", *, discipline: str, age: int, region: "Region",
                ability: float, years_racing: Optional[float] = None,
                near: Optional[tuple[float, float]] = None, budget_floor: float = 0.0) -> Driver:
    rng = world.rng
    first, last = names.driver_name(rng)
    year = world.year
    # Potential: younger drivers have more headroom; a small share are generational talents.
    headroom_years = max(0.0, 23 - age)
    headroom = headroom_years * rng.uniform(0.4, 3.0) + abs(rng.gauss(0, 4))
    represent = REPRESENTATION_RATIO / max(world.config.population_scale, 0.05)
    if age <= 16 and rng.random() < min(0.1, PRODIGY_SHARE * represent):
        headroom += rng.uniform(8, 18)  # generational talent
    potential = clamp(ability + headroom, ability, 99)
    peak_age = clamp(rng.gauss(29, 2.5), 24, 34)
    if rng.random() < 0.10:
        peak_age = rng.uniform(31, 36)  # late bloomer (research C 5.5)
    if near:
        lat = near[0] + rng.uniform(-0.6, 0.6)
        lon = near[1] + rng.uniform(-0.7, 0.7)
    else:
        lat = region.lat + rng.uniform(-1.2, 1.2)
        lon = region.lon + rng.uniform(-1.5, 1.5)
    if years_racing is None:
        years_racing = max(0.5, age - start_age_for(rng, discipline, youth=age < 16))
    fam = max(family_budget(rng, region, age), budget_floor * rng.uniform(1.0, 1.5))
    if age <= 16 and rng.random() < min(0.15, INVESTMENT_FAMILY_SHARE * represent):
        # A family that treats racing as a career investment (or owns a business that
        # will sponsor it): the Menard/Stroll/Burton archetype at the extreme.
        fam = max(fam, lognormal_money(rng, 180_000, 0.9))
    d = Driver(
        id=world.next_id("driver"),
        first_name=first, last_name=last,
        birth_year=year - age,
        home_region=region.code, country=region.country,
        lat=lat, lon=lon,
        ability=clamp(ability, 5, 97), potential=potential, peak_age=peak_age,
        consistency=_trait(rng), racecraft=_trait(rng), aggression=_trait(rng),
        feedback=_trait(rng), adaptability=_trait(rng), marketability=_trait(rng, 45, 15),
        professionalism=_trait(rng, 55, 15), determination=_trait(rng, 55, 18),
        primary_discipline=discipline,
        family_budget=fam,
        first_season=year - int(years_racing),
        first_license_age=max(5, age - int(years_racing)),
    )
    base = 1 - math.exp(-years_racing / 4.0)
    for disc in DISCIPLINES:
        d.proficiency[disc] = round(base * world.transfer(discipline, disc) * (0.8 if disc != discipline else 1.0), 3)
    d.proficiency[discipline] = round(base, 3)
    d.demonstrated = clamp(ability + rng.gauss(0, 5), 5, 95)
    return d


def ability_for_tier(rng: random.Random, tier: int, bias: float = 0.0) -> float:
    return clamp(rng.gauss(TIER_STRENGTH[tier] + bias, TIER_SPREAD[tier]), 5, 96)


def make_teams_for_series(world: "World", series: "Series") -> list[Team]:
    rng = world.rng
    tpl = series.template
    teams = []
    cars_left = tpl.cars
    sizes = [1, 2, 3, 4]
    size_w = [5, 3, 2, 1] if tpl.tier < 5 else [3, 3, 2, 2]
    rank = 0
    while cars_left > 0:
        n = min(cars_left, weighted_choice(rng, sizes, size_w))
        cars_left -= n
        teams.append(n)
    n_teams = len(teams)
    out = []
    for i, cars in enumerate(teams):
        # Quality by rank: a few strong organisations, a long tail of small teams.
        q = clamp(1 - (i + rng.random()) / n_teams + rng.gauss(0, 0.08), 0, 1)
        q = q ** 1.3
        equipment = clamp(28 + 62 * q + rng.gauss(0, 4), 10, 97)
        if tpl.pro:
            # Share of a seat's cost the organisation raises itself (charter money, team-sold
            # sponsorship, owner money). Research A 14.4: Trucks/O'Reilly drivers bring much of
            # the budget; premier-level teams fund nearly everything; dirt owners fund the car.
            floor = tpl.team_funding_floor if tpl.team_funding_floor is not None else PRO_FUNDING_FLOOR.get(tpl.tier, 0.25)
            funding_ratio = clamp(floor + (1.25 - floor) * q + rng.gauss(0, 0.08), 0.05, 1.35)
        else:
            funding_ratio = clamp((0.05 + 0.6 * q) * (tpl.tier / 7) + rng.gauss(0, 0.05), 0.0, 0.8)
        owner_type = "pro" if q > 0.7 else "privateer" if q > 0.3 else "family"
        region = _team_home(world, series)
        mfr = None
        if world.manufacturers and tpl.discipline in ("stock_car", "dirt_oval", "sports_car", "open_wheel") and tpl.tier >= 3:
            eligible = [m for m in world.manufacturers.values() if m.races(tpl.discipline, world.year)]
            if tpl.discipline == "open_wheel" and tpl.tier < 7:
                eligible = []  # spec junior formulae: no manufacturer affiliation
            if eligible and (q > 0.45 or rng.random() < 0.3):
                mfr = rng.choice(eligible).id
                if q > 0.75:
                    owner_type = "factory" if tpl.discipline == "sports_car" else "pro"
        sel, conn_w = base_selection(tpl)
        # The less a team raises itself, the more it must hire for money (pay drivers).
        sel["money"] = sel.get("money", 0.3) + max(0.0, 1 - funding_ratio) * 0.15
        sel["performance"] = sel.get("performance", 0.45) + max(0.0, funding_ratio - 0.8) * 0.2
        total = sum(sel.values())
        team = Team(
            id=world.next_id("team"),
            name=names.team_name(rng),
            series_id=series.id,
            home_region=region,
            owner_type=owner_type,
            equipment=equipment,
            sponsor_funding=tpl.season_cost / tpl.drivers_per_car * funding_ratio,
            cars=cars,
            drivers_per_car=tpl.drivers_per_car,
            manufacturer_id=mfr,
            w_performance=sel["performance"] / total,
            w_potential=sel.get("potential", 0.15) / total,
            w_money=sel["money"] / total,
            w_marketability=sel.get("marketability", 0.1) / total,
            w_connections=conn_w,
            reputation=clamp(20 + 70 * q),
        )
        out.append(team)
    return out


def _team_home(world: "World", series: "Series") -> str:
    """Pro teams cluster in industry hubs (Charlotte for stock cars, Indianapolis for open wheel)."""
    tpl = series.template
    regions = list(world.geo.regions.values())
    if tpl.scope == "region" and series.region_key:
        regions = world.geo.in_macro(series.region_key) or regions
    weights = [r.racer_weight * (0.3 + r.culture.get(tpl.discipline, 10) / 100)
               * (1 + r.hub(tpl.discipline) / 25 * (tpl.tier / 7)) for r in regions]
    return weighted_choice(world.rng, regions, weights).code


def make_manufacturers(world: "World") -> list[Manufacturer]:
    """Real manufacturers with their participation years (data/manufacturers.json)."""
    from ..util import load_json
    out = []
    for m in load_json("manufacturers.json")["manufacturers"]:
        years = dict(m["years"])
        prog = m.get("program") or {}
        out.append(Manufacturer(
            id=world.next_id("mfr"), name=m["name"], disciplines=list(m["years"]),
            program_budget=prog.get("budget", 0), program_slots=prog.get("slots", 0),
            aggressiveness=prog.get("aggr", 0.5), years=years, program_years=m.get("program_years")))
    return out


def make_sponsors(world: "World", scale: float = 1.0) -> list[Sponsor]:
    rng = world.rng
    out = []
    for region in world.geo.regions.values():
        n_local = max(2, int(region.racer_weight * region.sponsor_market / 4 * scale))
        for _ in range(n_local):
            out.append(Sponsor(
                id=world.next_id("sponsor"), name=names.sponsor_name(rng, "local"), industry="local",
                scope="local", region=region.code,
                budget=lognormal_money(rng, 3_000, 0.8), min_tier=0, max_tier=3,
                loyalty=rng.uniform(0.3, 0.9)))
        n_regional = max(1, int(region.racer_weight * region.sponsor_market / 30 * scale))
        for _ in range(n_regional):
            out.append(Sponsor(
                id=world.next_id("sponsor"), name=names.sponsor_name(rng, "regional"), industry="regional",
                scope="regional", region=region.code,
                budget=lognormal_money(rng, 45_000, 0.8), min_tier=2, max_tier=5,
                loyalty=rng.uniform(0.3, 0.8)))
    for i in range(int(len(names.SPONSOR_NATIONAL) * 2 * max(scale, 0.5))):
        out.append(Sponsor(
            id=world.next_id("sponsor"), name=names.SPONSOR_NATIONAL[i % len(names.SPONSOR_NATIONAL)],
            industry="national", scope="national", region=None,
            budget=lognormal_money(rng, 1_200_000, 0.9), min_tier=4, max_tier=7,
            loyalty=rng.uniform(0.2, 0.7)))
    return out


DEFAULT_SELECTION = {"performance": 0.45, "potential": 0.15, "money": 0.3, "marketability": 0.1}


def base_selection(tpl) -> tuple[dict, float]:
    """What owners in this series weigh: research weights for the tier (knowledge layer), blended
    50/50 with any series-specific rule in data/series.json. Returns (weights, connection weight)."""
    from ..knowledge.weights import selection_weights
    research = selection_weights(tpl.tier)
    conn_w = 0.6 * (research["connections"] if research else 1.0)
    base = {k: research[k] for k in DEFAULT_SELECTION} if research else dict(DEFAULT_SELECTION)
    if tpl.selection:
        base = {k: 0.5 * base.get(k, 0) + 0.5 * tpl.selection.get(k, DEFAULT_SELECTION[k]) for k in DEFAULT_SELECTION}
    return base, conn_w
