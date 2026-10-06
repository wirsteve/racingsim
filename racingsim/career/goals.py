"""Owner goals and job security.

Every team driver starts the season with a goal set from the car they were given: the owner
ranks the cars in the series by equipment and expects the driver to finish about where the car
ranks (a little slack for the bad luck everyone has). Top cars are expected to contend for the
title; mid-pack cars to win races or make a points position; back-markers to beat the cars
around them.

At season end the owner judges the result. Beating the goal builds **job security** (0-100);
missing it badly burns it. Drivers on the hot seat can be fired mid-contract (market.py), and
the verdict moves morale. Paid seats - drivers who bring the money - are judged more gently:
the cheque speaks for them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..util import clamp

if TYPE_CHECKING:
    from ..world.entities import Driver
    from ..world.world import World

NEUTRAL = 60.0
HOT_SEAT = 25.0


def security(d: "Driver") -> float:
    return float(getattr(d, "job_security", NEUTRAL))


def security_word(x: float) -> str:
    return ("untouchable" if x >= 85 else "secure" if x >= 65 else "stable" if x >= 45
            else "under pressure" if x >= HOT_SEAT else "on the hot seat")


def set_goals(world: "World") -> None:
    """Pre-season: every team driver gets a target from where their car ranks in the series."""
    by_series: dict[str, list] = {}
    for t in world.teams.values():
        by_series.setdefault(t.series_id, []).append(t)
    for sid, teams in by_series.items():
        s = world.series(sid)
        if s.dormant or not s.template.team_based:
            continue
        cars = []
        for t in teams:
            for car in range(t.cars):
                cars.append((t.equipment, t.id, car, t))
        cars.sort(key=lambda x: (-x[0], x[1], x[2]))
        field = len(cars)
        for rank, (_, _, car, t) in enumerate(cars, start=1):
            for slot in range(car * t.drivers_per_car, (car + 1) * t.drivers_per_car):
                did = t.roster[slot] if slot < len(t.roster) else None
                d = world.drivers.get(did) if did is not None else None
                if d is None:
                    continue
                # Points positions count drivers: with two or three drivers sharing a car, a car's rank
                # covers that many places in the standings.
                per = max(1, t.drivers_per_car)
                target = int(clamp(round((rank * 1.15 + 1) * per), 1, field * per))
                if rank <= 2:
                    target, label = 3 * per, f"Contend for the championship (top {3 * per})"
                elif rank <= 6:
                    label = f"Win races and finish top {target} in points"
                else:
                    label = f"Finish top {target} in points"
                d.goal = {"year": world.year, "series_id": sid, "team_id": t.id, "target": target, "label": label}


def review(world: "World", results) -> None:
    """Season end: the owner's verdict on every goal set this year."""
    for d in world.drivers.values():
        g = d.goal
        if not g or g.get("year") != world.year or "result" in g:
            continue
        rec = results.records.get(d.id)
        if rec is None or rec.series_id != g["series_id"] or rec.starts == 0:
            g["result"] = "did not race"
            continue
        events = (getattr(results, "events_held", {}).get(rec.series_id)
                  or len(world.series(rec.series_id).schedule) or rec.starts)
        if rec.starts < 0.6 * events:
            g.update(result="part season", pos=rec.championship_pos)   # injured or replaced: not judged
            continue
        target, pos = g["target"], rec.championship_pos
        margin = (target - pos) / max(target, 3)            # + = beat the goal
        delta = clamp(margin * 30, -35, 20) + min(rec.wins, 4) * 2.5 + (10 if rec.champion else 0)
        if d.seat_funded is False and delta < 0:
            delta *= 0.4                                     # a paid seat: the money talks
        d.job_security = round(clamp(security(d) + delta + (NEUTRAL - security(d)) * 0.1, 1, 99), 1)
        d.morale = round(clamp(getattr(d, "morale", 60.0) + clamp(margin * 10, -8, 8), 1, 99), 1)
        verdict = ("exceeded" if pos <= target - max(2, target // 4) or rec.champion else
                   "met" if pos <= target else
                   "missed" if pos <= target * 1.5 + 2 else "well short")
        g.update(result=verdict, pos=pos)
        if d.is_player:
            team = world.teams.get(g["team_id"])
            who = team.name if team else "The team"
            text = {"exceeded": f"{who} are thrilled: P{pos} in points beat the goal (top {target})",
                    "met": f"{who} are satisfied: P{pos} met the goal (top {target})",
                    "missed": f"{who} expected more: P{pos} missed the goal (top {target})",
                    "well short": f"{who} are unhappy: P{pos} was well short of the goal (top {target})"}[verdict]
            world.post("player", text + f". Job security: {security_word(d.job_security)}.", driver_id=d.id,
                       importance=2)


def fire_chance(d: "Driver") -> float:
    """Chance a driver on the hot seat is let go this winter (team-paid seats only)."""
    sec = security(d)
    if not d.seat_funded or sec >= HOT_SEAT:
        return 0.0
    return clamp(0.25 + (HOT_SEAT - sec) / 40, 0.0, 0.85)


def view(d: "Driver") -> dict:
    g = dict(d.goal) if d.goal else None
    return {"goal": g, "security": round(security(d)), "word": security_word(security(d))}
