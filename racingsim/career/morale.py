"""Personality in action: morale, rivalries and paybacks, team chemistry, contract leanings.

* **Morale** (0-100, 60 = content) moves a little after every race (wins, results against what
  the car should do, crashes) and is re-set each winter from the season as a whole: results
  against expectation, titles, a ride or no ride, contract security, team chemistry and whether
  an ambitious driver is stuck in a slow car. Confident drivers are a touch faster (race engine),
  develop a little faster, and re-sign more readily.
* **Rivalries**: being wrecked by someone builds heat toward them (more for hot-tempered
  drivers; less in a superspeedway big one, where nobody is really to blame). Heat cools with
  time. A driver with a temper and a hot rivalry may pay it back on track (race engine), and
  the sanctioning body answers: points, a fine, and at the national level a suspension.
* **Team chemistry** (multi-car teams): a leader lifts the shop; two alpha drivers with tempers
  or the same hunger to be number one pull it apart. It moves the cars' setups a little.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..util import clamp
from ..world import skills as S

if TYPE_CHECKING:
    from ..world.entities import Driver, Team
    from ..world.world import World

NEUTRAL = 60.0
HEAT_MIN = 5.0          # rivalries below this are forgotten
PAYBACK_POINTS = {7: 25, 6: 25, 5: 25, 4: 15, 3: 10}
PAYBACK_FINE = {7: 50_000, 6: 25_000, 5: 15_000, 4: 3_000, 3: 1_000}


def morale(d: "Driver") -> float:
    return float(getattr(d, "morale", NEUTRAL))


def word(m: float) -> str:
    return ("ecstatic" if m >= 85 else "happy" if m >= 70 else "content" if m >= 50
            else "frustrated" if m >= 35 else "miserable")


# ---------------------------------------------------------------------------------- race by race
def after_race(d: "Driver", position: int, field: int, expected: int, dnf: bool, crashed: bool) -> None:
    """Small nudge after every race; the season-end update does most of the work."""
    if field <= 1:
        return
    beat = (expected - position) / field            # + = better than the car should do
    delta = beat * 3.0
    # Winning and running up front feel good - relative to the field (one winner per race, so the
    # average driver's morale doesn't creep up week after week in small local fields).
    delta += (2.0 if position == 1 else 0.5 if position <= 5 else 0.0) - (2.0 + 0.5 * min(4, field - 1)) / field
    if crashed:
        delta -= 1.5
    elif dnf:
        delta -= 0.8
    # A short fuse swings harder both ways.
    delta *= 0.7 + S.trait(d, "temper") / 165
    d.morale = round(clamp(morale(d) + delta + (NEUTRAL - morale(d)) * 0.03, 1, 99), 1)
    if d.rivals:   # grudges cool a little every race weekend
        for k in list(d.rivals):
            d.rivals[k] = round(d.rivals[k] * 0.97, 1)
            if d.rivals[k] < HEAT_MIN:
                del d.rivals[k]


def add_heat(victim: "Driver", instigator_id: int, amount: float) -> None:
    if victim.id == instigator_id:
        return
    cur = victim.rivals.get(instigator_id, 0.0)
    victim.rivals[instigator_id] = round(min(100.0, cur + amount), 1)


def incidents(world: "World", incidents: list) -> None:
    """Heat from crashes: whoever got collected blames whoever started it."""
    for instigator, victims, big in incidents:
        for vid in victims[:2]:          # the cars right there blame the car that started it
            v = world.drivers.get(vid)
            if v is None:
                continue
            base = 6.0 if big else 22.0
            add_heat(v, instigator, base * S.trait(v, "temper") / 50)


def payback(world: "World", attacker_id: int, target_id: int, tier: int, series_name: str,
            track_name: str, week: int, acc: Optional[dict] = None) -> list[str]:
    """The sanctioning body's answer to an intentional wreck. Returns news lines."""
    a, t = world.drivers.get(attacker_id), world.drivers.get(target_id)
    if a is None or t is None:
        return []
    from ..sim.season import charge   # late import: season imports this module
    heat = a.rivals.get(target_id, 0.0)
    pts = PAYBACK_POINTS.get(tier, 0)
    fine = PAYBACK_FINE.get(tier, 0)
    if acc is not None and pts and attacker_id in acc:
        acc[attacker_id].points -= pts
    if fine:
        charge(a, fine)
    suspended = tier >= 5 and heat >= 75 and world.rng.random() < 0.35
    if suspended:
        a.suspension = max(a.suspension, 1)
    # Settled - for now. The target has a new grudge of their own.
    a.rivals[target_id] = round(heat * 0.25, 1)
    add_heat(t, attacker_id, 30 * S.trait(t, "temper") / 50)
    a.morale = round(clamp(morale(a) + 2, 1, 99), 1)     # it felt good
    t.morale = round(clamp(morale(t) - 4, 1, 99), 1)
    pen = ([f"docked {pts} points"] if pts else []) + ([f"fined ${fine:,.0f}"] if fine else [])
    text = f"{a.name} wrecks {t.name} in retaliation at {track_name} ({series_name})"
    if pen:
        text += ": " + " and ".join(pen)
    if suspended:
        text += "; suspended one race"
    a.log(world.year, f"retaliated against {t.name} at {track_name}" + ("; suspended one race" if suspended else ""))
    world.post("incident", text, driver_id=a.id, week=week, importance=2 if tier >= 5 or a.is_player or t.is_player else 1)
    return [text]


# ---------------------------------------------------------------------------------- team chemistry
def chemistry(world: "World", team: "Team") -> float:
    """-1 (a toxic shop) .. +1 (everyone pulling together); 0 for one-car teams."""
    ds = [world.drivers[i] for i in team.roster if i is not None and i in world.drivers]
    if len(ds) < 2:
        return 0.0
    lead = max(S.trait(d, "leadership") for d in ds)
    chem = (lead - 50) / 60
    for i, x in enumerate(ds):
        for y in ds[i + 1:]:
            # Two hot heads, or two drivers who both need to be the team's number one.
            chem -= max(0.0, (S.trait(x, "temper") + S.trait(y, "temper")) / 2 - 60) / 50
            chem -= max(0.0, min(S.trait(x, "ambition"), S.trait(y, "ambition")) - 65) / 45
    chem += (sum(morale(d) for d in ds) / len(ds) - NEUTRAL) / 80
    return round(clamp(chem, -1.0, 1.0), 2)


# ---------------------------------------------------------------------------------- the off-season
def season_update(world: "World", results) -> None:
    """Re-set morale from the season as a whole; old grudges cool."""
    for d in world.drivers.values():
        if d.status == "retired":
            continue
        m = morale(d)
        m += (NEUTRAL - m) * 0.35                      # a winter at home
        rec = results.records.get(d.id)
        amb = S.trait(d, "ambition")
        if rec is None or rec.starts == 0:
            if d.status == "sidelined" or d.series_id is None:
                m -= 6 + (amb - 50) / 10
        else:
            field = max(rec.field_size, 2)
            beat = (rec.expected_finish - rec.avg_finish) / field
            m += clamp(beat * 40, -12, 12)
            m += (min(rec.wins, 5) - min(rec.starts / field, 5)) * 1.5    # wins beyond a fair share
            if rec.champion:
                m += 10
            if d.team_id is not None and d.team_id in world.teams:
                team = world.teams[d.team_id]
                # Ambitious drivers stuck in slow cars stew; the rest are glad of the ride.
                if team.equipment < 50:
                    m -= max(0.0, amb - 50) / 8 * (50 - team.equipment) / 25
                m += chemistry(world, team) * 4
        if d.team_id is not None:
            m += 2 if d.contract_years >= 2 else -2 if d.contract_years <= 0 else 0
        if d.suspension:
            d.suspension = 0
        d.morale = round(clamp(m, 1, 99), 1)
        if d.rivals:
            d.rivals = {k: round(v * 0.7, 1) for k, v in d.rivals.items()
                        if v * 0.7 >= HEAT_MIN and k in world.drivers and world.drivers[k].status != "retired"}


# ---------------------------------------------------------------------------------- contracts
def resign_chance(d: "Driver") -> float:
    """A star's chance of re-signing before the deal runs out (was a flat 85%)."""
    return clamp(0.45 + morale(d) / 250 + S.trait(d, "loyalty") / 400, 0.3, 0.97)


def switch_margin(d: "Driver") -> float:
    """Equipment edge another team at the same level needs to lure this driver away."""
    return (5 + (S.trait(d, "loyalty") - 50) / 6 - (S.trait(d, "ambition") - 50) / 10
            - (NEUTRAL - morale(d)) / 8)


def rivals_view(world: "World", d: "Driver", limit: int = 5) -> list[dict]:
    out = []
    for rid, heat in sorted((d.rivals or {}).items(), key=lambda x: -x[1])[:limit]:
        r = world.drivers.get(rid)
        if r is None:
            continue
        out.append({"id": rid, "name": r.name, "heat": round(heat),
                    "word": "bitter" if heat >= 75 else "heated" if heat >= 40 else "simmering"})
    return out
