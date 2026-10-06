"""Seed a world with real people for its start year.

* National series with data for the start year get that season's real teams
  (name, manufacturer, car count) and real full-time drivers. Ratings are derived
  from their actual results around that season, using the same results-to-level
  scale the scouting model uses, so the paddock "perceives" them correctly.
* Real drivers whose national careers began *after* the start year enter the world
  as prospects at their real age (or later, when they reach racing age), with a
  ceiling based on what they went on to achieve. Whether they make it again is up
  to the simulation.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from ..constants import TIER_SPREAD, TIER_STRENGTH
from ..util import clamp
from ..world.entities import ACTIVE, DISCIPLINES, Driver, SeasonRecord, Team
from .db import SOURCES, TEMPLATE_DISCIPLINE, HistoryDB

if TYPE_CHECKING:
    from ..world.series import Series
    from ..world.world import World

ISO3_HOME = {"USA": None, "CAN": "ON"}
FOREIGN_HUB = {"open_wheel": "IN", "stock_car": "NC"}


def row_level(row: dict) -> float:
    """Results -> 0-100 level (mirrors scouting.season_level)."""
    tier = row["tier"]
    n = max(row.get("n") or 1, 2)
    pos = row.get("pos") or n
    pct = clamp(1 - (pos - 1) / (n - 1), 0, 1)
    starts = row.get("starts")
    if starts is not None and row.get("field") and starts < 3:
        pct *= 0.6  # a handful of starts says little
    return TIER_STRENGTH[tier] + (pct - 0.5) * 2.4 * TIER_SPREAD[tier] + min(row.get("wins") or 0, 8) * 0.4


def _split_name(name: str) -> tuple[str, str]:
    parts = name.replace(", Jr", " Jr").replace("Jr.", "Jr").replace(",", " ").split()
    if len(parts) == 1:
        return parts[0], ""
    if parts[-1] in ("Jr", "Sr", "II", "III", "IV") and len(parts) > 2:
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    return parts[0], " ".join(parts[1:])


def _home(world: "World", bio: dict, discipline: str):
    state = (bio.get("state") or "").upper()
    country = bio.get("country") or "USA"
    if state in world.geo.regions:
        return world.geo.get(state), country
    if country == "CAN":
        return world.geo.get("ON"), country
    hub = FOREIGN_HUB.get(discipline, "NC")
    return world.geo.get(hub), country


def make_real_driver(world: "World", hist: HistoryDB, wiki: Optional[str], name: str, discipline: str,
                     year: int, *, team_equipment: float = 60.0, default_age: int = 28) -> Driver:
    rng = world.rng
    bio = hist.bio(wiki)
    rows = hist.careers().get(wiki or "", [])
    by = hist.birth_year(wiki)
    if by is None:
        first = rows[0]["year"] if rows else year
        by = first - 23 if rows else year - default_age
    age = year - by
    region, country = _home(world, bio, discipline)
    near = [r for r in rows if abs(r["year"] - year) <= 1]
    past = [r for r in rows if r["year"] < year]
    future = [r for r in rows if r["year"] >= year]
    if near:
        levels = [row_level(r) for r in near]
        ability = sum(levels) / len(levels) - (team_equipment - 60) * 0.08
    else:
        ability = TIER_STRENGTH[3] + (age - 16) * 1.5 if age < 22 else TIER_STRENGTH[4]
    ability = clamp(ability, 10, 96)
    peak = max([row_level(r) for r in future] or [ability])
    if future:
        best = max(future, key=row_level)
        peak_age = clamp(best["year"] - by, 24, 38)
    else:
        peak_age = clamp(rng.gauss(29, 2.5), 24, 34)
    potential = clamp(max(ability + (1 if age < peak_age else 0), peak + rng.uniform(0, 2)), ability, 98)
    first, last = _split_name(name)
    starts_all = sum((r.get("starts") or 0) for r in rows) or 1
    top10_rate = sum((r.get("top10") or r.get("top5") or 0) for r in rows) / starts_all
    wins_all = sum(r.get("wins") or 0 for r in rows)
    titles_all = sum(1 for r in rows if r.get("pos") == 1)
    d = Driver(
        id=world.next_id("driver"), first_name=first, last_name=last, birth_year=by,
        home_region=region.code, country=country,
        lat=region.lat + rng.uniform(-0.6, 0.6), lon=region.lon + rng.uniform(-0.7, 0.7),
        ability=ability, potential=potential, peak_age=peak_age,
        consistency=clamp(45 + top10_rate * 40 + rng.gauss(0, 6), 5, 95),
        racecraft=clamp(50 + min(wins_all, 40) * 0.6 + rng.gauss(0, 8), 5, 95),
        aggression=clamp(rng.gauss(52, 14), 5, 95), feedback=clamp(rng.gauss(55, 12), 5, 95),
        adaptability=clamp(rng.gauss(50, 14), 5, 95),
        marketability=clamp(42 + titles_all * 6 + min(wins_all, 30) * 0.5 + rng.gauss(0, 8), 5, 99),
        professionalism=clamp(rng.gauss(62, 10), 5, 95), determination=clamp(rng.gauss(62, 12), 5, 95),
        primary_discipline=discipline,
        family_budget=max(20_000.0, rng.lognormvariate(math.log(40_000), 1.0)),
        first_season=min([r["year"] for r in rows] or [year]) - 6,
        first_license_age=max(5, min(age, 12)),
    )
    for disc in DISCIPLINES:
        d.proficiency[disc] = round(0.9 * world.transfer(discipline, disc) * 0.8, 3)
    d.proficiency[discipline] = 0.92
    d.real = True
    d.wiki = wiki
    d.demonstrated = sum(row_level(r) for r in near) / len(near) if near else ability
    for r in past:
        series_id = r["template"] if r["template"] in world.pyramid.series else r["template"]
        pct = clamp(1 - ((r.get("pos") or r["n"]) - 1) / max(1, r["n"] - 1), 0, 1)
        rec = SeasonRecord(year=r["year"], series_id=series_id, tier=r["tier"], discipline=TEMPLATE_DISCIPLINE[r["template"]],
                           team_id=None, starts=r.get("starts") or 0, wins=r.get("wins") or 0, top5=r.get("top5") or 0,
                           avg_finish=0.0, expected_finish=0.0, championship_pos=r.get("pos") or r["field"],
                           field_size=r["field"], champion=r.get("pos") == 1, series_name=r.get("series_name") or "",
                           team_name=r.get("team") or "")
        rec.note = f"{pct:.3f}|{pct:.3f}"
        d.history.append(rec)
        d.career_starts += rec.starts
        d.career_wins += rec.wins
        if rec.champion:
            d.titles.append(f"{r['year']} {rec.series_name}")
    d.max_tier = max([r["tier"] for r in past] or [0])
    d.reputation = clamp(10 + d.max_tier * 8 + titles_all * 3 + (d.demonstrated - 50) * 0.4)
    d.exposure = clamp(20 + d.max_tier * 9)
    return d


def seed_national(world: "World", hist: HistoryDB) -> set[str]:
    """Create the start year's real teams and drivers. Returns the series ids seeded."""
    from ..career.market import seat_gap, seat_role
    from ..world.names import team_name
    year = world.year
    seeded: set[str] = set()
    created: dict[str, Driver] = {}
    order = sorted(SOURCES, key=lambda k: -_tier(world, k))
    for key in order:
        series = world.pyramid.series.get(key)
        season = hist.season(key, year)
        if series is None or series.dormant or not season or not season.get("teams"):
            continue
        tpl = series.template
        standings = {r.get("wiki") or r.get("name"): r for r in season.get("standings") or []}
        n = max(len(standings), 2)
        n_races = len(season.get("schedule") or []) or tpl.events
        entries = []
        for t in season["teams"]:
            cars = [c for c in t.get("cars", []) if c.get("drivers")]
            flagged = [c for c in cars if c.get("full_time")]
            if any(c.get("full_time") is not None for c in cars):
                cars = flagged
            else:  # no flags: regulars = drivers who started at least half the races
                cars = [c for c in cars if (standings.get(c["drivers"][0].get("wiki") or c["drivers"][0]["name"], {})
                                            .get("starts") or 0) >= 0.5 * n_races]
            if cars:
                entries.append((t, cars))
        if not entries:
            continue

        def pct_of(dr: dict) -> float:
            r = standings.get(dr.get("wiki") or dr["name"])
            if not r or not r.get("pos"):
                return 0.25
            return clamp(1 - (r["pos"] - 1) / (n - 1), 0, 1)

        for t, cars in entries:
            q = sum(pct_of(c["drivers"][0]) for c in cars) / len(cars)
            equipment = clamp(32 + 62 * q + world.rng.gauss(0, 3), 15, 97)
            floor = tpl.team_funding_floor if tpl.team_funding_floor is not None else 0.3
            ratio = clamp(floor + (1.25 - floor) * q, 0.05, 1.35) if tpl.pro else clamp(0.1 + 0.5 * q, 0, 0.8)
            mfr = _manufacturer(world, t.get("manufacturer"))
            team = Team(id=world.next_id("team"), name=t.get("team") or team_name(world.rng), series_id=series.id,
                        home_region="NC" if tpl.discipline == "stock_car" else "IN",
                        owner_type="pro" if q > 0.6 else "privateer", equipment=equipment,
                        sponsor_funding=tpl.season_cost / tpl.drivers_per_car * ratio, cars=len(cars),
                        drivers_per_car=tpl.drivers_per_car, manufacturer_id=mfr,
                        reputation=clamp(20 + 70 * q))
            sel = dict(tpl.selection) if tpl.selection else {"performance": 0.45, "potential": 0.15, "money": 0.3,
                                                              "marketability": 0.1}
            tot = sum(sel.values())
            team.w_performance, team.w_potential = sel["performance"] / tot, sel.get("potential", 0.15) / tot
            team.w_money, team.w_marketability = sel["money"] / tot, sel.get("marketability", 0.1) / tot
            team.roster = [None] * team.seats
            world.teams[team.id] = team
            for car_i, c in enumerate(cars):
                dr = c["drivers"][0]
                key_d = dr.get("wiki") or dr["name"]
                if key_d in created:
                    continue  # already seated in a higher series this season
                d = make_real_driver(world, hist, dr.get("wiki"), dr["name"], tpl.discipline, year,
                                     team_equipment=equipment)
                created[key_d] = d
                slot = car_i * tpl.drivers_per_car
                world.drivers[d.id] = d
                world._seat(d, series, team, slot=slot, funded=True)
                gap = seat_gap(team, tpl, seat_role(tpl, slot))
                d.seat_funded = gap <= 0
                if gap > 0:
                    d.family_budget = max(d.family_budget, gap * 1.05)  # the backing they really had
                if tpl.pro and d.seat_funded:
                    d.salary = tpl.salary_top * clamp((equipment - 25) / 70, 0.05, 1.0)
                d.contract_years = world.rng.randint(1, 3)
                d.max_tier = max(d.max_tier, tpl.tier)
        seeded.add(series.id)
    world.real_drivers = {d.wiki: d.id for d in created.values() if getattr(d, "wiki", None)}
    return seeded


def seed_prospects(world: "World", hist: HistoryDB) -> int:
    """Real drivers whose national careers start after the start year."""
    from ..career.market import choose_self_run
    year = world.year
    known = set(getattr(world, "real_drivers", {}))
    pending = []
    count = 0
    for wiki, rows in hist.careers().items():
        if wiki in known or not rows or rows[0]["year"] < year:
            continue
        by = hist.birth_year(wiki)
        if by is None:
            continue
        pending.append((wiki, rows, by))
    world.history_entrants = {}
    for wiki, rows, by in pending:
        age = year - by
        disc = TEMPLATE_DISCIPLINE[rows[0]["template"]]
        if is_import(hist, wiki):
            # Raised abroad: they arrive in North American racing the year before their debut.
            arrival = rows[0]["year"] - 1
            if arrival > year:
                world.history_entrants.setdefault(arrival, []).append(wiki)
                continue
        if age < 8:
            world.history_entrants.setdefault(by + 8, []).append(wiki)
            continue
        if age > 40:
            continue
        if place_prospect(world, hist, wiki, rows, disc):
            count += 1
    return count


def place_prospect(world: "World", hist: HistoryDB, wiki: str, rows: list[dict], disc: str) -> Optional[Driver]:
    from ..career.market import choose_self_run
    year = world.year
    name = hist.bio(wiki).get("name") or wiki.replace("_", " ").split(" (")[0]
    d = make_real_driver(world, hist, wiki, name, disc, year)
    age = d.age(year)
    peak = max(row_level(r) for r in rows)
    if is_import(hist, wiki) and age >= 16:
        return _place_import(world, wiki, d, rows, disc, peak)
    # Before their national career they are developing: ability by age, ceiling = what they became.
    d.ability = clamp(min(d.ability, TIER_STRENGTH[0] + max(0, age - 8) * 2.4 + world.rng.gauss(0, 3)), 15, peak)
    d.potential = clamp(peak + world.rng.uniform(-1.5, 2.5), d.ability, 98)
    d.demonstrated = d.ability
    d.history.clear()
    d.titles.clear()
    d.career_starts = d.career_wins = 0
    d.max_tier = 0
    d.reputation = 5
    d.exposure = 5
    start_disc = "karting" if disc == "open_wheel" and age < 15 else disc
    d.primary_discipline = start_disc
    for x in DISCIPLINES:
        d.proficiency[x] = round(min(0.6, max(0, age - 6) * 0.06) * world.transfer(start_disc, x), 3)
    # Families of drivers who reached national series were, on the whole, able to fund racing.
    d.family_budget = max(d.family_budget, world.rng.lognormvariate(math.log(60_000 if disc == "open_wheel" else 25_000), 0.8))
    world.drivers[d.id] = d
    d.status = ACTIVE
    if not choose_self_run(world, d, entrant=age < 14):
        del world.drivers[d.id]
        return None
    world.real_drivers[wiki] = d.id
    return d


def is_import(hist: HistoryDB, wiki: str) -> bool:
    return (hist.bio(wiki).get("country") or "USA") not in ("USA", "CAN")


def _place_import(world: "World", wiki: str, d: Driver, rows: list[dict], disc: str, peak: float) -> Optional[Driver]:
    """A driver who made their name abroad (F1 feeders, Supercars, ...) arrives with a reputation."""
    from ..career.market import choose_self_run
    debut = row_level(rows[0])
    d.ability = clamp(debut - 2 + world.rng.gauss(0, 2), 15, peak)
    d.potential = clamp(peak + world.rng.uniform(-1.5, 2.0), d.ability, 98)
    d.demonstrated = d.ability
    d.history.clear()
    d.titles.clear()
    d.career_starts = d.career_wins = 0
    d.max_tier = max(0, rows[0]["tier"] - 2)
    d.reputation = clamp(15 + d.max_tier * 7)
    d.exposure = clamp(20 + d.max_tier * 8)
    d.family_budget = max(d.family_budget, world.rng.lognormvariate(math.log(150_000), 0.6))
    d.events.append(f"{world.year}: arrived from overseas racing")
    world.drivers[d.id] = d
    d.status = ACTIVE
    if not choose_self_run(world, d, entrant=False):
        del world.drivers[d.id]
        return None
    world.real_drivers[wiki] = d.id
    return d


def history_entrants(world: "World", next_year: int) -> int:
    """Real drivers reaching racing age this off-season join the world."""
    hist = getattr(world, "history", None)
    entrants = getattr(world, "history_entrants", {}).pop(next_year, [])
    if hist is None or not entrants:
        return 0
    careers = hist.careers()
    n = 0
    for wiki in entrants:
        rows = careers.get(wiki)
        if rows and wiki not in world.real_drivers:
            if place_prospect(world, hist, wiki, rows, TEMPLATE_DISCIPLINE[rows[0]["template"]]):
                n += 1
    return n


def _tier(world: "World", key: str) -> int:
    t = world.pyramid.templates.get(key)
    return t.tier if t else 0


def _manufacturer(world: "World", name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    n = name.lower()
    for m in world.manufacturers.values():
        if m.name.lower() in n:
            return m.id
    return None
