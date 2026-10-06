"""Statistical race model.

This is deliberately a *management-sim* race model, not a physics sim: each race
resolves into a finishing order from driver ability, equipment, track character
and luck. The track's internal game ratings shape how much each factor matters:

* equipment share rises with horsepower/aero importance and with the tier
  (the higher the level, the more the car decides the result);
* luck rises with drafting effect and caution probability (superspeedways and
  dirt bullrings are lotteries; flat short tracks reward the best driver);
* racecraft matters more where passing is hard; consistency/aggression and the
  track's crash severity drive incidents and injuries.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..tracks import Track
from ..world.entities import Driver
from ..util import clamp


@dataclass
class Entry:
    drivers: list[Driver]
    equipment: float               # 0-100
    team_id: Optional[int] = None
    car_key: str = ""
    mech: Optional[float] = None   # this car's mechanical-failure chance (own cars: engine freshness/health)
    crew: Optional[dict] = None    # race-day effects of the car's people (world/staff.crew_effects)


@dataclass
class Finish:
    entry: Entry
    position: int
    pace: float
    dnf: bool = False
    crashed: bool = False
    injured: list[int] = field(default_factory=list)
    expected_position: int = 0
    box: Optional[dict] = None     # lap-by-lap engine box score (start, laps, led, status, ...)


def _driver_pace(d: Driver, discipline: str, track: Track) -> float:
    s = track.sim
    base = d.effective_ability(discipline)
    # Racecraft pays off where passing is hard; consistency where tires/fuel must be managed.
    craft = (d.racecraft - 50) * 0.10 * (s.passing_difficulty / 100)
    manage = (d.consistency - 50) * 0.05 * ((s.tire_degradation + s.fuel_sensitivity) / 200)
    return base + craft + manage


def _factors(track: Track, tier: int, car_weight: float) -> tuple[float, float]:
    s = track.sim
    # Equipment matters more on power/aero tracks; at superspeedways the draft equalises cars.
    cw = car_weight * (0.75 + 0.5 * (s.horsepower_importance + s.aero_importance) / 200)
    cw *= 1.0 - 0.35 * (s.drafting_effect / 100)
    cw = clamp(cw, 0.1, 0.8)
    # Luck: drafting packs, cautions and lower-tier variance (less prep, more mechanical gremlins).
    luck = 5.0 + 9.0 * (s.drafting_effect / 100) + 4.0 * (s.caution_probability / 100) + 1.2 * max(0, 4 - tier)
    return cw, luck


def _paces(entries: list[Entry], track: Track, discipline: str, cw: float) -> list[float]:
    paces = []
    for e in entries:
        dpace = sum(_driver_pace(d, discipline, track) for d in e.drivers) / len(e.drivers)
        paces.append((1 - cw) * dpace + cw * e.equipment)
    return paces


def heats(entries: list[Entry], track: Track, discipline: str, tier: int, car_weight: float,
          rng: random.Random, per_heat: int = 9) -> tuple[list[Entry], list[list[Entry]]]:
    """Heat races: cars are drawn into heats; returns (overall order by heat performance, heats in finishing order).

    Short heats with inverted starts are mostly luck plus pace, so the noise is larger than in a feature."""
    cw, luck = _factors(track, tier, car_weight)
    paces = _paces(entries, track, discipline, cw)
    score = {id(e): p + rng.gauss(0, luck * 1.3) for e, p in zip(entries, paces)}
    drawn = list(entries)
    rng.shuffle(drawn)
    n = max(1, -(-len(drawn) // per_heat))
    groups = [sorted(drawn[i::n], key=lambda e: -score[id(e)]) for i in range(n)]
    overall = sorted(entries, key=lambda e: -score[id(e)])
    return overall, groups


def run_race(entries: list[Entry], track: Track, discipline: str, tier: int,
             car_weight: float, rng: random.Random, injury_scale: float = 1.0,
             realism: Optional[dict] = None) -> list[Finish]:
    if not entries:
        return []
    real = realism or {}
    s = track.sim
    cw, luck = _factors(track, tier, car_weight)
    luck *= real.get("luck", 1.0)
    injury_scale *= real.get("injuries", 1.0)
    paces = _paces(entries, track, discipline, cw)

    # Expected finishing order from equipment alone (what a scout would "expect").
    equip_order = sorted(range(len(entries)), key=lambda i: -entries[i].equipment)
    expected = {i: rank + 1 for rank, i in enumerate(equip_order)}

    results: list[tuple[float, int, bool, bool]] = []
    for i, e in enumerate(entries):
        score = paces[i] + rng.gauss(0, luck)
        lead = e.drivers[0]
        # Incidents: aggressive/inconsistent drivers crash more; crash-prone venues amplify it.
        crash_p = (0.012 + 0.05 * (s.caution_probability / 100) * (0.6 + (lead.aggression - lead.consistency + 100) / 200)) \
            * real.get("crashes", 1.0)
        mech_p = (e.mech if e.mech is not None else ((0.01 + 0.04 * (s.mechanical_stress / 100) * (1 - e.equipment / 130))
                                                     * (e.crew or {}).get("mech", 1.0))) * real.get("failures", 1.0)
        crashed = rng.random() < crash_p
        mech = (not crashed) and rng.random() < mech_p
        dnf = crashed or mech
        if dnf:
            score -= 1000 - rng.random() * 100  # DNFs classified by laps completed (random)
        results.append((score, i, dnf, crashed))
    results.sort(key=lambda x: -x[0])

    finishes = []
    for pos, (score, i, dnf, crashed) in enumerate(results, start=1):
        injured = []
        if crashed:
            sev = s.crash_severity / 100
            for d in entries[i].drivers:
                if rng.random() < 0.04 * sev * injury_scale:
                    injured.append(d.id)
        finishes.append(Finish(entry=entries[i], position=pos, pace=paces[i], dnf=dnf,
                               crashed=crashed, injured=injured, expected_position=expected[i]))
    return finishes


def points_for(position: int, field_size: int) -> int:
    """Simple, tier-agnostic points: rewards wins and consistency."""
    base = max(field_size - position + 1, 1)
    bonus = 5 if position == 1 else 2 if position <= 3 else 0
    return base + bonus
