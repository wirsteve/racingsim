"""Team finances: the closed economic loop.

Results bring purses and fans; fans and results bring sponsors and merchandise; money buys
development, and development is next year's speed. Every team-run team keeps books each season
(2025 dollars, like the rest of the model):

Revenue
  * purses and points-fund money (the team keeps about 65%; the driver gets the rest)
  * the team's own sponsors, plus what pay drivers bring to their seat
  * Cup charters (2016 on): guaranteed money per chartered car, part fixed, part by results
  * merchandise from the drivers' fan bases
  * manufacturer support for factory-aligned teams at the national level
  * the owner's own money: most teams lose money and owners cover part of it
Costs
  * running the cars (the series' full-season cost per car, scaled by how hard the team spends)
  * staff salaries (inside the running cost) and driver salaries

The spending level the team can afford sets its development; equipment moves toward what that
spending buys relative to the rest of the series. Owners who run out of money sell the team.

Numbers (docs/research/team_economics.md, all converted to 2025 dollars with the motorsport price
index):
  * Cup: ~$20M per car per season (2024-25 testimony, high confidence); 2024 revenue per car
    $8.2M-$43M, average result -$2.2M per car, 3 of 12 organisations profitable (high).
  * Charters from 2016: ~$9M per car per year 2016-24, ~$12.5M from 2025; last-placed charter
    $4-5M then ~$8.5M (high/medium).
  * Merchandise: team/driver/sponsor keep ~9% of a trackside sale, the driver ~3% (medium).
  * Manufacturer support per team is not disclosed (gap); 8% of the season cost at tier 5+ is
    an estimate (EST, low confidence).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from ..util import clamp
from . import fans as F

if TYPE_CHECKING:
    from .entities import Team
    from .world import World

TEAM_PURSE_SHARE = 0.65
CHARTERS = 36
CHARTER_START = 2016
# (average, last-placed) charter money per car per year, nominal dollars of the era (research 2.2).
CHARTER_PAY = ((2016, 9.0e6, 4.5e6), (2025, 12.5e6, 8.5e6))
MERCH_TEAM_PER_FAN = 2.0     # $ per fan per season to the team side (EST from the 9% share)
MERCH_DRIVER_PER_FAN = 1.35  # $ per fan per season to the driver (3% of ~$45 spent)
MANUFACTURER_SHARE = 0.08    # of the season cost, tier 5+ factory-aligned teams (EST, low)
OWNER_SUBSIDY = {"family": 0.05, "privateer": 0.08, "pro": 0.12, "factory": 0.2}
BOOKS_KEPT = 15
SPEND_MIN, SPEND_MAX = 0.45, 1.6


def _price(year: int) -> float:
    from ..history.economy import price_index
    return max(price_index(year), 0.05)


def charter_pay(year: int, results_pct: float) -> float:
    """Charter money for one car this season, 2025 dollars; results_pct 0 (last) .. 1 (best)."""
    if year < CHARTER_START:
        return 0.0
    avg, low = CHARTER_PAY[0][1:] if year < CHARTER_PAY[1][0] else CHARTER_PAY[1][1:]
    nominal = low + (avg - low) * 2 * clamp(results_pct, 0, 1)
    return nominal / _price(year)


def assign_charters(world: "World") -> None:
    """2016: the established Cup teams get charters (36 cars); the rest run open."""
    cup = [t for t in world.teams.values() if t.series_id == "cup_series"]
    if world.year + 1 < CHARTER_START or not cup or any(t.charters for t in cup):
        return
    left = CHARTERS
    for t in sorted(cup, key=lambda t: (-t.reputation, -t.equipment, t.id)):
        n = min(t.cars, left)
        t.charters = n
        left -= n
        if left <= 0:
            break
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
        for t in teams:
            if t.spend:
                continue
            t.spend = round(clamp(2 ** ((t.equipment - mean) / 28), SPEND_MIN, SPEND_MAX), 3)
            t.cash = round(0.3 * tpl.season_cost * t.cars * t.spend)


def _team_rows(world: "World", results, team: "Team") -> list:
    return [(did, r) for did, r in results.records.items() if r.team_id == team.id and r.series_id == team.series_id]


def close_books(world: "World", results) -> None:
    """Season end: every team's revenue and costs, next year's spending, equipment and sponsors."""
    from ..career.market import seat_gap, seat_role
    from .staff import team_staff
    ensure(world)
    F.ensure(world)
    assign_charters(world)
    rng = world.rng
    year = world.year
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
        for t in sorted(teams, key=lambda x: x.id):
            rows = _team_rows(world, results, t)
            pcts = [1 - (r.avg_finish - 1) / max(1, r.field_size - 1) for _, r in rows if r.starts]
            pct = sum(pcts) / len(pcts) if pcts else 0.3
            drivers = [world.drivers[i] for i in t.roster if i is not None and i in world.drivers]
            purse = TEAM_PURSE_SHARE * sum(r.winnings for _, r in rows)
            own = t.sponsor_funding * t.seats
            brought = 0.0
            for slot, did in enumerate(t.roster):
                d = world.drivers.get(did) if did is not None else None
                if d is not None and not d.seat_funded:
                    gap = seat_gap(t, tpl, seat_role(tpl, slot))
                    brought += max(0.0, gap) * clamp(world.seat_coverage.get(d.id, 1.0), 0, 1)
            charter = t.charters * charter_pay(year, pct) if sid == "cup_series" else 0.0
            merch = MERCH_TEAM_PER_FAN * 1000 * sum(d.fans for d in drivers)
            mfr = MANUFACTURER_SHARE * tpl.season_cost * t.cars if (t.manufacturer_id and tpl.tier >= 5) else 0.0
            running = tpl.season_cost * t.cars * t.spend
            staff_pay = sum(m.salary for m in team_staff(world, t.id))
            salaries = sum(d.salary for d in drivers if d.seat_funded)
            owner = OWNER_SUBSIDY.get(t.owner_type, 0.08) * running
            revenue = {"purse": purse, "sponsors": own, "pay_drivers": brought, "charter": charter,
                       "merchandise": merch, "manufacturer": mfr, "owner": owner}
            costs = {"running": running - min(staff_pay, running * 0.6), "staff": min(staff_pay, running * 0.6),
                     "driver_salaries": salaries}
            net = sum(revenue.values()) - sum(costs.values())
            t.cash = round(t.cash + net)
            ledgers.append((t, pct, drivers, sum(revenue.values()) - owner, salaries))
            t.books.append({"year": year, "revenue": {k: round(v) for k, v in revenue.items()},
                            "costs": {k: round(v) for k, v in costs.items()}, "net": round(net),
                            "cash": t.cash, "spend": t.spend, "result_pct": round(pct, 3)})
            del t.books[:-BOOKS_KEPT]
        # Next year: equipment from what this year's money built, relative to the series.
        levels = sorted(t.spend for t, *_ in ledgers)
        median = levels[len(levels) // 2] if levels else 1.0
        for t, pct, drivers, earned, salaries in ledgers:
            target = mean_eq + 28 * math.log2(max(t.spend, 0.05) / max(median, 0.05))
            t.equipment = round(clamp(t.equipment + 0.35 * (target - t.equipment) + rng.gauss(0, 2), 8, 98), 1)
            _sponsors(world, t, tpl, pct, drivers)
            budget = earned + OWNER_SUBSIDY.get(t.owner_type, 0.08) * tpl.season_cost * t.cars * t.spend
            budget += 0.3 * t.cash if t.cash > 0 else 0.4 * t.cash
            t.spend = round(clamp((budget - salaries) / max(1.0, tpl.season_cost * t.cars), SPEND_MIN, SPEND_MAX), 3)
            if t.cash < -0.6 * tpl.season_cost * t.cars:
                _sold(world, t, tpl)
    # Drivers' own merchandise money.
    for d in world.drivers.values():
        if d.status != "retired" and d.fans >= 1:
            d.savings += MERCH_DRIVER_PER_FAN * 1000 * d.fans


def _sponsors(world: "World", t: "Team", tpl, pct: float, drivers: list) -> None:
    """Sponsors follow results and fans (and drift back toward what the series normally raises)."""
    fans = sum(d.fans for d in drivers)
    reach = F.TIER_FANS[min(tpl.tier, 7)] * max(1, len(drivers))
    factor = (0.85 + 0.3 * pct) * (1 + 0.1 * math.log10(1 + fans / max(reach, 0.01)))
    per_seat = tpl.season_cost / max(1, tpl.drivers_per_car)
    norm = 0.35 * per_seat
    new = t.sponsor_funding * clamp(factor + world.rng.gauss(0, 0.05), 0.85, 1.15)
    t.sponsor_funding = round(clamp(0.85 * new + 0.15 * norm, 0.0, 1.2 * per_seat))


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
    return {"last": last, "history": [{"year": b["year"], "net": b["net"], "cash": b["cash"],
                                       "revenue": sum(b["revenue"].values()), "costs": sum(b["costs"].values())}
                                      for b in t.books],
            "charters": t.charters, "spend": t.spend, "cash": t.cash}
