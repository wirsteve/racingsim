"""Team finances: the closed economic loop.

Results bring purses and fans; fans and results bring sponsors and merchandise; money buys
development, and development is next year's speed. Every team-run team keeps books each season
(2025 dollars, like the rest of the model):

Revenue
  * the money the organisation raises itself (``Team.sponsor_funding`` per seat, the figure the
    driver market already uses), itemised as Cup charter money (2016 on: guaranteed per chartered
    car, part fixed, part by results), the owner's own money (most teams lose money and owners
    cover part of it) and sponsors (the rest)
  * what pay drivers bring to their seat
  * purses and points-fund money (the team keeps about 65%; the driver gets the rest)
  * merchandise from the drivers' fan bases
  * manufacturer support for factory-aligned teams at the national level
Costs
  * running the cars (the series' full-season cost per car, scaled by how hard the team spends)
  * staff salaries (inside the running cost) and driver salaries

The spending level the team can afford sets its development; equipment moves toward what that
spending buys relative to the rest of the series. Owners who run out of money sell the team.

Numbers (docs/research/team_economics.md, all converted to 2025 dollars with the motorsport price
index):
  * Cup: ~$20M per car per season (2024-25 testimony, high confidence); 2024 revenue per car
    $8.2M-$43M, average result -$2.2M per car, 3 of 12 organisations profitable (high).
  * Charters from 2016: ~$9M per car per year 2016-24, ~$12.5M from 2025 (high); the last-placed
    charter's $4-5M, then ~$8.5M, comes from search summaries only (medium-low).
  * Merchandise: team/driver/sponsor keep ~9% of a trackside sale, the driver ~3% (medium). The
    research has no per-fan spending figure: $45 a fan a season, so ~$1.35 each to the driver and
    the team, is an estimate (EST, low).
  * Manufacturer support per team is not disclosed (gap); 8% of the season cost at tier 5+ is
    an estimate (EST, low confidence).
  * How much of a loss owners cover (5-20% of the season cost by owner type) is not sourced: it is
    set so the average team loses money, as the 2024 figures show (EST, low).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from ..util import clamp
from ..rules import shop
from . import fans as F

if TYPE_CHECKING:
    from .entities import Team
    from .world import World

TEAM_PURSE_SHARE = 0.65
CHARTERS = 36
CHARTER_START = 2016
# (average, last-placed) charter money per car per year (research 2.2: ~$9M / $4-5M nominal 2016-24,
# ~$12.5M / ~$8.5M from 2025). Given here in 2025 dollars with general inflation (~1.25x for the 2016-24
# deal, EST): TV money didn't grow with the motorsport cost index the rest of the model uses for eras.
CHARTER_PAY = ((2016, 11.25e6, 5.6e6), (2025, 12.5e6, 8.5e6))
CHARTER_INSIDE = 0.5        # share of charter money already counted in what the team raises (the rest is new)
MERCH_TEAM_PER_FAN = 1.35   # $ per fan per season to the team (3% of an EST ~$45 a fan)
MERCH_DRIVER_PER_FAN = 1.35  # $ per fan per season to the driver (3% of an EST ~$45 a fan)
MANUFACTURER_SHARE = 0.08    # of the season cost, tier 5+ factory-aligned teams (EST, low)
OWNER_SUBSIDY = {"family": 0.05, "privateer": 0.08, "pro": 0.12, "factory": 0.2}   # EST, low
BOOKS_KEPT = 15
SPEND_MIN, SPEND_MAX = 0.4, 2.0
SPEND_EFFECT = 9.0           # equipment points per doubling of spend over the series average, per year
OPTIMISM = (0.93, 1.15)      # owners plan next year's budget a little above or below what came in


def charter_pay(year: int, results_pct: float) -> float:
    """Charter money for one car this season, 2025 dollars; results_pct 0 (last) .. 1 (best)."""
    if year < CHARTER_START:
        return 0.0
    avg, low = CHARTER_PAY[0][1:] if year < CHARTER_PAY[1][0] else CHARTER_PAY[1][1:]
    return low + (avg - low) * 2 * clamp(results_pct, 0, 1)


def assign_charters(world: "World", announce: bool = True) -> None:
    """2016: the established Cup teams get charters (36 cars); the rest run open. Worlds that start
    later (or saves from before finances) get them quietly."""
    cup = [t for t in world.teams.values() if t.series_id == "cup_series"]
    if world.year + 1 < CHARTER_START or not cup or any(t.charters for t in cup):
        return
    announce = announce and world.year + 1 == CHARTER_START
    left = CHARTERS
    for t in sorted(cup, key=lambda t: (-t.reputation, -t.equipment, t.id)):
        n = min(t.cars, left)
        t.charters = n
        left -= n
        if left <= 0:
            break
    if not announce:
        return
    world.post("finance", f"NASCAR introduces charters: {CHARTERS} Cup cars are guaranteed a starting spot "
                          f"and a share of the TV money", importance=2)


def ensure(world: "World") -> None:
    """Opening books for teams that have none (new worlds, old saves, new teams)."""
    by_series: dict[str, list] = {}
    for t in world.teams.values():
        by_series.setdefault(t.series_id, []).append(t)
    for sid, teams in by_series.items():
        mean = sum(t.equipment for t in teams) / len(teams)
        tpl = world.series(sid).template
        anchors = world.__dict__.setdefault("equipment_anchor", {})
        anchors.setdefault(sid, mean)
        for t in teams:
            if not t.funding_anchor:
                t.funding_anchor = t.sponsor_funding
            if t.spend:
                continue
            t.spend = round(clamp(2 ** ((t.equipment - mean) / 36), SPEND_MIN, SPEND_MAX), 3)
            t.cash = round(0.3 * tpl.season_cost * t.cars * t.spend)
    if world.year >= CHARTER_START:
        assign_charters(world, announce=False)


def close_books(world: "World", results) -> None:
    """Season end: every team's revenue and costs, next year's spending, equipment and sponsors."""
    from ..career.market import seat_gap, seat_role
    from .staff import team_staff
    ensure(world)
    F.ensure(world)
    assign_charters(world)
    from ..history.economy import price_index
    rng = world.rng
    year = world.year
    rows_by_team: dict[int, list] = {}
    for did, r in results.records.items():
        if r.team_id is not None:
            rows_by_team.setdefault(r.team_id, []).append((did, r))
    by_series: dict[str, list] = {}
    for t in world.teams.values():
        by_series.setdefault(t.series_id, []).append(t)
    for sid, teams in sorted(by_series.items()):
        s = world.series(sid)
        tpl = s.template
        if s.dormant:
            continue
        mean_eq = sum(t.equipment for t in teams) / len(teams)
        ledgers = []
        result_pct = _result_ranks(teams, rows_by_team)
        for t in sorted(teams, key=lambda x: x.id):
            rows = rows_by_team.get(t.id, [])
            pct = result_pct.get(t.id, 0.25)
            drivers = [world.drivers[i] for i in t.roster if i is not None and i in world.drivers]
            purse = TEAM_PURSE_SHARE * sum(r.winnings for _, r in rows)
            raised = t.sponsor_funding * t.seats      # charters + owner money + sponsors, as the market sees it
            brought = 0.0
            for slot, did in enumerate(t.roster):
                d = world.drivers.get(did) if did is not None else None
                if d is not None and not d.seat_funded:
                    gap = seat_gap(t, tpl, seat_role(tpl, slot))
                    brought += max(0.0, gap) * clamp(world.seat_coverage.get(d.id, 1.0), 0, 1)
            charter = t.charters * charter_pay(year, pct) if sid == "cup_series" else 0.0
            # The player's own team: the owner's money is the player's savings (game/owner.py settle).
            owner = 0.0 if t.player_owned else OWNER_SUBSIDY.get(t.owner_type, 0.08) * tpl.season_cost * t.cars
            # Charters (2016) came with the TV money that used to reach teams through purses and
            # deals; half is treated as part of what the team was already raising, half as new money.
            sponsors = max(0.05 * raised, raised - CHARTER_INSIDE * charter - owner)
            merch = MERCH_TEAM_PER_FAN * 1000 * sum(d.fans for d in drivers)
            mfr = MANUFACTURER_SHARE * tpl.season_cost * t.cars if (t.manufacturer_id and tpl.tier >= 5) else 0.0
            running = tpl.season_cost * t.cars * t.spend
            staff_pay = sum(m.salary for m in team_staff(world, t.id))
            salaries = sum(d.salary for d in drivers if d.seat_funded)
            facilities = shop.team_upkeep(world, t)
            revenue = {"sponsors": sponsors, "charter": charter, "owner": owner, "pay_drivers": brought,
                       "purse": purse, "merchandise": merch, "manufacturer": mfr}
            costs = {"running": running - min(staff_pay, running * 0.6), "staff": min(staff_pay, running * 0.6),
                     "driver_salaries": salaries}
            if facilities:
                costs["facilities"] = facilities
            net = sum(revenue.values()) - sum(costs.values())
            t.cash = round(t.cash + net)
            ledgers.append((t, pct, drivers, sum(revenue.values()), salaries))
            t.books.append({"year": year, "revenue": {k: round(v) for k, v in revenue.items()},
                            "costs": {k: round(v) for k, v in costs.items()}, "net": round(net),
                            "cash": t.cash, "spend": t.spend, "result_pct": round(pct, 3),
                            "idx": price_index(year)})
            del t.books[:-BOOKS_KEPT]
        # Next year: equipment from what this year's money built, relative to the series. An organisation
        # keeps most of its know-how; spending more or less than the series average moves it from there.
        mean_spend = sum(t.spend for t, *_ in ledgers) / len(ledgers) if ledgers else 1.0
        fans_by_team = {t.id: sum(d.fans for d in drivers) for t, _, drivers, *_ in ledgers}
        fan_median = sorted(fans_by_team.values())[len(fans_by_team) // 2] if fans_by_team else 1.0
        moved = []
        for t, pct, drivers, earned, salaries in ledgers:
            x = clamp(math.log2(max(t.spend, 0.05) / max(mean_spend, 0.05)), -1.5, 1.5)
            target = mean_eq + 0.75 * (t.equipment - mean_eq) + SPEND_EFFECT * x + shop.team_equipment(t)
            moved.append((t, t.equipment + 0.35 * (target - t.equipment) + rng.gauss(0, 2)))
        if moved:   # the series as a whole keeps its level (drifting slowly back to where it started)
            anchor = world.__dict__.get("equipment_anchor", {}).get(sid, mean_eq)
            shift = (mean_eq + 0.1 * (anchor - mean_eq)) - sum(e for _, e in moved) / len(moved)
            for t, e in moved:
                t.equipment = round(clamp(e + shift, 8, 98), 1)
        for t, pct, drivers, earned, salaries in ledgers:
            _sponsors(world, t, tpl, pct, fans_by_team[t.id], fan_median)
            if t.player_owned:
                from ..game import owner as owner_mode
                owner_mode.settle(world, t, tpl)
            budget = earned + (0.3 * t.cash if t.cash > 0 else 0.4 * t.cash)
            if t.player_owned:
                budget *= {"lean": 0.8, "normal": 1.0, "push": 1.25}.get(t.budget_mode, 1.0)
            else:
                budget *= rng.uniform(*OPTIMISM)
            t.spend = round(clamp((budget - salaries) / max(1.0, tpl.season_cost * t.cars), SPEND_MIN, SPEND_MAX), 3)
            if t.cash < -0.5 * tpl.season_cost * t.cars and not t.player_owned:
                _sold(world, t, tpl)
    # Drivers' own merchandise money.
    for d in world.drivers.values():
        if d.status != "retired" and d.fans >= 1:
            d.savings += MERCH_DRIVER_PER_FAN * 1000 * d.fans


def _result_ranks(teams: list, rows_by_team: dict) -> dict[int, float]:
    """Each team's results as a rank within its series: 1 = best average finish, 0 = worst.
    (Ranks average 0.5 whatever the field size or drivers per car.)"""
    avg = []
    for t in teams:
        rows = [r for _, r in rows_by_team.get(t.id, []) if r.starts and r.series_id == t.series_id]
        if rows:
            avg.append((sum(r.avg_finish * r.starts for r in rows) / sum(r.starts for r in rows), t.id))
    avg.sort()
    n = len(avg)
    return {tid: (1 - i / (n - 1)) if n > 1 else 0.5 for i, (_, tid) in enumerate(avg)}


def _sponsors(world: "World", t: "Team", tpl, pct: float, fans: float, fan_median: float) -> None:
    """Sponsors follow results and fans against the rest of the series (an average team holds steady),
    and drift back toward what this team has always been able to raise."""
    rel = clamp(math.log10(max(fans, 0.01) / max(fan_median, 0.01)), -1.5, 1.5)
    factor = (0.85 + 0.3 * pct) * (1 + 0.04 * rel) * shop.team_sponsor(t)
    per_seat = tpl.season_cost / max(1, tpl.drivers_per_car)
    new = t.sponsor_funding * clamp(factor + world.rng.gauss(0, 0.04), 0.85, 1.15)
    anchor = t.funding_anchor or t.sponsor_funding
    t.sponsor_funding = round(clamp(0.85 * new + 0.15 * anchor, 0.0, max(1.35 * per_seat, 1.3 * anchor)))


def _sold(world: "World", t: "Team", tpl) -> None:
    """Out of money: the owner sells. New money comes in; the shop loses people and momentum."""
    t.cash = round(0.25 * tpl.season_cost * t.cars)
    t.equipment = round(clamp(t.equipment - 6, 8, 98), 1)
    t.reputation = clamp(t.reputation - 8, 0, 100)
    t.spend = round(clamp(t.spend * 0.9, SPEND_MIN, SPEND_MAX), 3)
    t.books[-1]["sold"] = True
    if tpl.tier >= 4:
        world.post("finance", f"{t.name} changes hands after running out of money", importance=2 if tpl.tier >= 6 else 1)


def team_view(world: "World", t: "Team") -> Optional[dict]:
    if not t.books:
        return None
    last = t.books[-1]
    return {"last": last, "history": [{"year": b["year"], "net": b["net"], "cash": b["cash"], "idx": b.get("idx"),
                                       "revenue": sum(b["revenue"].values()), "costs": sum(b["costs"].values())}
                                      for b in t.books],
            "charters": t.charters, "spend": t.spend, "cash": t.cash}
