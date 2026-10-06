"""Fan bases: who people come to see.

A driver's fan base (thousands of fans) grows with results where people are watching - a win
in a televised national series reaches far more people than a win at a Saturday-night bullring
- and with charisma (marketability). Fans drift away when a driver stops winning, steps down a
level or retires. Fans sell souvenirs and attract sponsors; the most popular driver award
follows them.

Scale anchors (docs/research/team_economics.md section 8): Cup season TV audiences averaged about
6.0M viewers in 2010, 5.1M in 2015, 2.9M in 2021 and 2.5M in 2025; Xfinity about 1.0M and the
Truck Series about 0.5M in 2025; IndyCar 1.2-1.4M. The tier weights below put a Cup star's
following in the low millions and a weekly-track champion's in the low thousands. These are
game-scale estimates, not counts of real people.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from ..util import clamp

if TYPE_CHECKING:
    from .entities import Driver
    from .world import World

# Thousands of fans a typical driver at each level reaches in a season of racing.
TIER_FANS = {0: 0.05, 1: 0.4, 2: 1.5, 3: 6.0, 4: 20.0, 5: 60.0, 6: 120.0, 7: 400.0}
# Cup TV audience relative to 2025 (2.48M): 2010-2025 from research section 8 (6.0M, 5.1M, 3.1M, 2.9M,
# 2.5M); 2005 from section 10 (~1.33x 2010); 1995-2000 estimated from Daytona 500 audiences (EST).
# Applied to stock-car national series only: other disciplines' audiences follow other curves.
AUDIENCE = {1995: 2.0, 2000: 2.3, 2005: 3.2, 2010: 2.4, 2015: 2.05, 2019: 1.25, 2021: 1.18, 2025: 1.0}
SEED_SCALE = 0.22      # starting followings at about the level seasons of results sustain
RETAIN = 0.85          # share of last year's fans who stay (a following settles near 6-7 seasons of gains)
RETAIN_RETIRED = 0.7


def audience(year: int) -> float:
    ys = sorted(AUDIENCE)
    if year <= ys[0]:
        return AUDIENCE[ys[0]]
    if year >= ys[-1]:
        return AUDIENCE[ys[-1]]
    for a, b in zip(ys, ys[1:]):
        if a <= year <= b:
            return AUDIENCE[a] + (AUDIENCE[b] - AUDIENCE[a]) * (year - a) / (b - a)
    return 1.0


def initial(d: "Driver", rng: random.Random) -> float:
    """A starting following for drivers who arrive with a career behind them."""
    tier = min(7, max(d.max_tier, d.tier if d.series_id else 0))
    wins = d.career_wins + 3 * len(d.titles)
    base = TIER_FANS[tier] * (0.4 + d.marketability / 80) * (0.5 + d.reputation / 100) * (1 + wins / 40)
    return round(base * SEED_SCALE * math.exp(rng.gauss(0, 0.35)), 2)


def ensure(world: "World") -> None:
    """Old saves and new worlds: give every driver a following once."""
    if world.__dict__.get("fans_seeded"):
        return
    rng = random.Random(world.config.seed * 17 + 3)
    for d in sorted(world.drivers.values(), key=lambda x: x.id):
        if not d.fans:
            d.fans = initial(d, rng)
    world.fans_seeded = True


def season_update(world: "World", results) -> None:
    """Fans after a season: results where people watch, charisma, and time."""
    ensure(world)
    view = audience(world.year) ** 0.5
    for d in world.drivers.values():
        rec = results.records.get(d.id)
        if d.status == "retired":
            d.fans = round(d.fans * RETAIN_RETIRED, 2)
            continue
        gain = 0.0
        if rec is not None and rec.starts:
            reach = TIER_FANS[min(rec.tier, 7)] * (view if rec.tier >= 5 and rec.discipline == "stock_car" else 1.0)
            show = (0.15 + 0.05 * rec.top5 + 0.25 * rec.wins + (2.0 if rec.champion else 0.0)
                    + 0.5 * len(rec.crown_jewel_wins))
            gain = 0.2 * reach * show * (0.5 + d.marketability / 100)
        d.fans = round(clamp(d.fans * RETAIN + gain, 0.0, 20_000.0), 2)


def label(k: float) -> str:
    """Thousands of fans -> '1.2M', '35k', '800'."""
    if k >= 1000:
        return f"{k / 1000:.1f}M"
    if k >= 1:
        return f"{k:.0f}k"
    return f"{k * 1000:.0f}"


def rank(world: "World", d: "Driver") -> int:
    return 1 + sum(1 for x in world.drivers.values() if x.fans > d.fans and x.status != "retired")
