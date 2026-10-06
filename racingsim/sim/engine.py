"""Lap-by-lap race engine (the racing equivalent of OOTP's pitch-by-pitch simulation).

A race is run in short segments of laps (1 lap at a time for races you watch, a few laps per
step for the rest of a big field). Every step:

* each car turns laps at a pace built from the driver's skills (speed, track-type skill,
  consistency), the car (equipment), tire wear (falloff grows with the age of the tires and
  shrinks with tire management) and fuel load;
* faster cars try to pass the car ahead - success depends on the speed difference, the
  attacker's racecraft vs the defender's defending and how hard the track is to pass on
  (superspeedway drafts make passing easy and chaotic; Martinsville makes it hard);
* incidents happen: spins and crashes (aggression, consistency, car control, composure late
  in the race, a tight pack), multi-car "big ones" on superspeedways, mechanical failures
  (engine health and freshness from the car model);
* cautions bunch the field; cars pit for tires and fuel; the free pass gives the first car a
  lap down its lap back (2003+); restarts reshuffle the front (restart skill);
* green-flag pit cycles when the fuel window closes or the tires are gone;
* stage ends, lap leaders, fastest laps, passes and running position are recorded.

The output is a full box score per car (start, finish, laps, laps led, status, pit stops,
average running position, fastest laps, passes, driver rating) and a play-by-play log.
All tuning numbers live in ``CAL`` and come from docs/research/race_engine_calibration.md.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..util import clamp
from ..world import skills as S
from .race import Entry, Finish

if TYPE_CHECKING:
    from ..tracks import Track

# --------------------------------------------------------------------------- calibration
CAL = {
    # Race distance (miles) by (tier, track type); laps = miles / track length, then clamped.
    "distance_mi": {
        7: {"short": 265, "intermediate": 400, "superspeedway": 500, "road": 220, "dirt": 150},
        6: {"short": 135, "intermediate": 300, "superspeedway": 300, "road": 160, "dirt": 100},
        5: {"short": 105, "intermediate": 200, "superspeedway": 250, "road": 120, "dirt": 75},
        4: {"short": 75, "intermediate": 150, "superspeedway": 200, "road": 90, "dirt": 50},
        3: {"short": 55, "intermediate": 100, "superspeedway": 150, "road": 60, "dirt": 25},
        2: {"short": 25, "intermediate": 50, "superspeedway": 75, "road": 40, "dirt": 15},
        1: {"short": 12, "intermediate": 25, "superspeedway": 40, "road": 30, "dirt": 8},
        0: {"short": 6, "intermediate": 10, "superspeedway": 15, "road": 20, "dirt": 5},
    },
    "min_laps": 12, "max_laps": 600,
    # Average race speed (mph) at the top tier by track type; lower tiers slower.
    "mph": {"short": 95, "intermediate": 175, "superspeedway": 190, "road": 95, "dirt": 75},
    # Pace: share of lap time one performance point is worth.
    "spread_per_point": 0.0005,
    # Tire falloff per lap of tire age, as a share of lap time, at tire_degradation 50.
    "falloff": 0.00045,
    # Cautions per race-mile... expressed as expected cautions per race by track type (top tier).
    "cautions": {"short": 8.5, "intermediate": 6.5, "superspeedway": 7.0, "road": 4.0, "dirt": 4.0},
    "caution_laps": {"short": 7, "intermediate": 5, "superspeedway": 5, "road": 3, "dirt": 3},
    "big_one_share": 0.35,   # superspeedway cautions that are multi-car pileups
    # Pit stops
    "pit_loss_s": {"short": 18, "intermediate": 30, "superspeedway": 35, "road": 35, "dirt": 25},
    "stop_s": 13.0,          # 4 tires + fuel at the top level (lower tiers slower)
    "fuel_window_mi": 95,    # miles per tank (top tier)
    "tire_life_laps": {"short": 120, "intermediate": 45, "superspeedway": 60, "road": 25, "dirt": 40},
    "noise": 0.0018,         # lap-to-lap variation (share of lap time) for an average consistency
    # Race-weekend setup: each car hits or misses the setup by this many performance points (sd);
    # a driver with good feedback narrows it. Real elite drivers' finishes vary by ~9-10 positions.
    "setup_sd": 3.0,
    "qual_noise": 2.6,       # one-lap qualifying luck (track evolution, draw, a bobble) vs race noise
    "draft_noise": 2.2,      # extra pack-racing randomness at full drafting effect
    "stint_sd": 2.2,
    "restart_swap": 0.28,    # chance two cars side by side on a restart trade places         # each run the car gets better or worse (adjustments, track evolution), points
    "pit_sd": 1.6,           # seconds of pit-stop variation (fumbles, loose wheels in the tail)
    "loose_wheel": 0.012,    # chance a stop goes badly wrong (extra 10-25 s)
}


@dataclass(eq=False)   # identity comparison: cars are looked up in lists every step
class Car:
    entry: Entry
    start: int
    perf: float                 # race pace in performance points (skills + car), track-adjusted
    qual: float                 # qualifying pace
    tire_mgmt: float            # 0-1 (1 = best)
    craft: float                # passing skill (points)
    defend: float
    restart: float
    risk: float                 # incident propensity multiplier
    composure: float
    fitness: float
    fuel_save: float
    time: float = 0.0
    laps: int = 0
    tire_age: int = 0
    fuel_laps: float = 0.0
    damage: float = 0.0
    running: bool = True
    status: str = "running"
    led: int = 0
    pos_sum: float = 0.0
    pos_laps: int = 0
    top15_laps: int = 0
    fast_laps: int = 0
    passes: int = 0
    passed: int = 0
    quality_passes: int = 0
    pits: int = 0
    stage_pos: list = field(default_factory=list)
    crashed: bool = False
    out_lap: int = 0
    mech_lap: float = 1.0       # per-lap mechanical hazard
    stint: float = 0.0          # this run's pace change from adjustments (points)
    adjust: float = 1.0         # how well this crew/driver adjusts (feedback): scales stint swings


@dataclass
class RaceResult:
    finishes: list[Finish]
    laps: int
    cautions: int = 0
    caution_laps: int = 0
    lead_changes: int = 0
    leaders: int = 0
    margin: float = 0.0
    log: list = field(default_factory=list)       # [lap, text]
    stages: list = field(default_factory=list)    # [[driver ids top 10], ...]


def race_laps(track: "Track", tier: int) -> int:
    tt = S.track_type_of(track)
    miles = CAL["distance_mi"][max(0, min(7, tier))][tt]
    length = track.facts.length_mi or 0.5
    return int(clamp(round(miles / length), CAL["min_laps"], CAL["max_laps"]))


def _lap_seconds(track: "Track", tier: int, tt: str) -> float:
    mph = CAL["mph"][tt] * (0.78 + 0.0314 * max(0, min(7, tier)))
    return (track.facts.length_mi or 0.5) / mph * 3600


# --------------------------------------------------------------------------- setup
def _car(e: Entry, tt: str, cw: float, rng: random.Random) -> Car:
    ds = e.drivers
    lead = ds[0]
    S.ensure(lead)

    def avg(fn):
        return sum(fn(d) for d in ds) / len(ds)
    drv = avg(lambda d: d.ability * S.track_factor(d, tt) + S.track_bonus(d, tt)
              + 0.5 * S.offset(d, "speed") + 0.15 * S.offset(d, "consistency"))
    perf = (1 - cw) * drv + cw * e.equipment
    # This weekend's setup: feedback (and the crew) narrow the miss.
    setup = rng.gauss(0, CAL["setup_sd"] * clamp(1.15 - S.offset(lead, "feedback") / 25, 0.6, 1.5))
    perf += setup
    qual = perf + (1 - cw) * 0.6 * S.offset(lead, "qualifying")
    aggression = lead.aggression
    risk = clamp((0.55 + (aggression - 50) / 120 - S.offset(lead, "consistency") / 40
                  - S.offset(lead, "car_control") / 50 + (S.trait(lead, "temper") - 50) / 250), 0.25, 2.2)
    return Car(entry=e, start=0, perf=perf, qual=qual,
               adjust=clamp(1.1 - S.offset(lead, "feedback") / 30, 0.6, 1.4),
               tire_mgmt=clamp(0.5 + S.offset(lead, "tire_management") / 30, 0, 1),
               craft=S.offset(lead, "racecraft"), defend=S.offset(lead, "defending"),
               restart=S.offset(lead, "restarts"), risk=risk, composure=S.offset(lead, "composure"),
               fitness=S.offset(lead, "fitness"), fuel_save=S.offset(lead, "fuel_saving"))


def _stop_time(stop_s: float, rng: random.Random) -> float:
    """A pit stop: usually close to the crew's norm, occasionally a disaster (loose wheel, jack)."""
    t = stop_s + abs(rng.gauss(0, CAL["pit_sd"]))
    if rng.random() < CAL["loose_wheel"]:
        t += rng.uniform(10, 25)
    return t


def _order(cars: list[Car]) -> list[Car]:
    """Running order: laps completed first, then race time."""
    return sorted(cars, key=lambda c: (-c.laps, c.time))


# --------------------------------------------------------------------------- the race
def run(entries: list[Entry], track: "Track", tier: int, car_weight: float, rng: random.Random,
        detail: bool = False, stages: int = 0, free_pass: bool = True, injury_scale: float = 1.0,
        laps: Optional[int] = None, name_of=None) -> RaceResult:
    tt = S.track_type_of(track)
    s = track.sim
    n_laps = laps or race_laps(track, tier)
    lap_s = _lap_seconds(track, tier, tt)
    cw = clamp(car_weight * (0.75 + 0.5 * (s.horsepower_importance + s.aero_importance) / 200)
               * (1.0 - 0.35 * (s.drafting_effect / 100)), 0.1, 0.8)
    cars = [_car(e, tt, cw, rng) for e in entries]
    if len(cars) < 2:
        return RaceResult([], n_laps)
    log: list = []
    say = (lambda lap, text: log.append([lap, text])) if detail else (lambda lap, text: None)
    who = name_of or (lambda c: c.entry.drivers[0].name)

    # ---- qualifying (or heat-based lineup noise for short local races)
    q_noise = lap_s * CAL["noise"] * CAL["qual_noise"] * (1.6 if tier <= 2 else 1.0)
    for c in cars:
        c.mech_lap = 1 - (1 - (c.entry.mech if c.entry.mech is not None else 0.03)) ** (1 / n_laps)
        c.time = -(c.qual - 50) * CAL["spread_per_point"] * lap_s + rng.gauss(0, q_noise)
    grid = sorted(cars, key=lambda c: c.time)
    for i, c in enumerate(grid, start=1):
        c.start = i
        c.time = (i - 1) * 0.25   # rolling start: two-wide rows, a few lengths apart
    say(0, f"{who(grid[0])} on the pole" + (f", {who(grid[1])} alongside" if len(grid) > 1 else ""))

    # ---- race parameters
    tier_f = max(0, min(7, tier))
    fuel_laps = max(8, CAL["fuel_window_mi"] * (0.8 + 0.03 * tier_f) / (track.facts.length_mi or 0.5))
    tire_life = CAL["tire_life_laps"][tt] * (0.6 + 0.8 * (100 - s.tire_degradation) / 100)
    pit_loss = CAL["pit_loss_s"][tt]
    stop_s = CAL["stop_s"] * (1.0 + 0.12 * (7 - tier_f))
    stops_needed = n_laps > fuel_laps * 0.95 or n_laps > tire_life * 1.4
    exp_cautions = CAL["cautions"][tt] * (1 + 0.06 * (7 - tier_f)) * min(1.6, (n_laps / max(race_laps(track, 7), 1)) ** 0.5)
    caution_hazard = exp_cautions / n_laps
    falloff = CAL["falloff"] * (0.4 + 1.2 * s.tire_degradation / 100) * lap_s
    noise = CAL["noise"] * lap_s * (1 + CAL["draft_noise"] * (s.drafting_effect / 100) ** 2)
    pass_threshold = lap_s * 0.0013 * (0.3 + 1.4 * s.passing_difficulty / 100)
    draft_chaos = s.drafting_effect / 100
    # Races you watch run a lap at a time; the rest of the world in ~16 steps (same model, coarser).
    step = 1 if detail else max(1, n_laps // 24)
    stage_ends = []
    if stages:
        stage_ends = [round(n_laps * f) for f in ((0.25, 0.5) if stages == 2 else (0.33, 0.66))[:stages]]
    for c in cars:
        c.fuel_laps = fuel_laps * (1 + c.fuel_save / 200)
        c.stint = rng.gauss(0, CAL["stint_sd"] * c.adjust)

    lap = 0
    caution_left = 0
    cautions = caution_laps = lead_changes = 0
    leader_ids: set = set()
    last_leader: Optional[Car] = None
    stage_results: list = []
    new_caution = False

    def incident(lap_now: int, big: bool) -> list[Car]:
        """Choose who is involved in a crash (weighted by risk, close racing mid-pack)."""
        order = [c for c in _order(cars) if c.running]
        if not order:
            return []
        weights = [c.risk * (1.0 + 0.6 * (5 < i < len(order) * 0.8)) for i, c in enumerate(order)]
        first = rng.choices(order, weights=weights)[0]
        involved = [first]
        idx = order.index(first)
        n_more = (rng.randint(4, 14) if big else rng.choices([0, 1, 2, 3], weights=[45, 30, 15, 10])[0])
        for j in range(1, n_more + 1):
            k = idx + j if rng.random() < 0.7 else idx - j
            if 0 <= k < len(order) and order[k] not in involved:
                involved.append(order[k])
        return involved

    while lap < n_laps:
        k = min(step, n_laps - lap)
        if caution_left <= 0 and n_laps - lap <= max(10, n_laps // 8):
            k = 1 if detail else min(k, 3)   # the run to the flag is fine-grained
        green = caution_left <= 0
        running = [c for c in cars if c.running]
        if not running:
            break
        late = lap >= n_laps * 0.85
        if green:
            # -------- green-flag laps
            before = _order(running)       # running order going into this step
            for c in running:
                ok_tires = c.tire_age
                wear = falloff * (1.25 - 0.5 * c.tire_mgmt) * (ok_tires + k / 2)
                if c.tire_age > tire_life:
                    wear += falloff * 4 * (c.tire_age - tire_life)
                tired = max(0.0, -c.fitness) * 0.002 * lap_s * (lap / n_laps) * (n_laps > 150)
                pace = (lap_s * (1 - (c.perf + c.stint - 50) * CAL["spread_per_point"] - c.damage * 0.01)
                        + wear + tired)
                jitter = noise * (1.4 - (c.perf - 30) / 100) * math.sqrt(k)
                if late:
                    jitter *= (1.15 - clamp(c.composure / 40, -0.3, 0.3))
                seg = pace * k + rng.gauss(0, jitter)
                c.time += seg
                c.laps += k
                c.tire_age += k
                c.fuel_laps -= k
                c._seg = seg / k  # noqa: SLF001 - per-lap pace this step (fastest-lap credit)
            # passing: resolve from the front, a car can only gain spots by beating the car ahead
            new: list[Car] = []
            for c in before:
                # c tries to move up past cars that ended the step behind it in time
                pos = len(new)
                while pos > 0 and new[pos - 1].laps == c.laps and c.time < new[pos - 1].time:
                    ahead = new[pos - 1]
                    adv = ahead.time - c.time
                    skill = (c.craft - ahead.defend) / 25
                    p = clamp(0.5 + adv / pass_threshold * 0.25 + skill * 0.25 + draft_chaos * 0.3, 0.03, 0.97)
                    if rng.random() < p:
                        pos -= 1
                        c.passes += 1
                        ahead.passed += 1
                        if pos < 15:
                            c.quality_passes += 1
                    else:
                        c.time = ahead.time + 0.05 + rng.random() * 0.1   # stuck behind
                        break
                new.insert(pos, c)
            # fastest lap of the step
            fastest = min(running, key=lambda x: x._seg)  # noqa: SLF001
            fastest.fast_laps += k
            # incidents: chance this step brings out a caution
            if rng.random() < 1 - (1 - caution_hazard) ** k:
                big = tt == "superspeedway" and rng.random() < CAL["big_one_share"]
                cause = rng.random()
                if cause < 0.72 or big:
                    involved = incident(lap + k, big)
                    sev = track.sim.crash_severity / 100
                    for c in involved:
                        dmg = rng.betavariate(1.3, 3.0) * (1.4 if big else 1.0)
                        if dmg > 0.55 or rng.random() < 0.25 * sev:
                            c.running, c.status, c.crashed, c.out_lap = False, "crash", True, c.laps
                        else:
                            c.damage += dmg * 4
                    names = ", ".join(who(c) for c in involved[:5]) + (f" and {len(involved) - 5} more" if len(involved) > 5 else "")
                    say(lap + k, ("BIG ONE: " if big else "Caution: ") + f"crash involving {names}")
                else:
                    say(lap + k, "Caution: " + rng.choice(["debris on the track", "a spin", "fluid on the track",
                                                             "a car stopped on track"]))
                cautions += 1
                caution_left = max(2, int(CAL["caution_laps"][tt] * rng.uniform(0.7, 1.4)))
                new_caution = True
            # mechanical failures
            for c in running:
                if c.running and rng.random() < 1 - (1 - c.mech_lap) ** k:
                    c.running, c.status, c.out_lap = False, rng.choice(["engine", "transmission", "rear gear",
                                                                       "electrical", "overheating"]), c.laps
                    say(lap + k, f"{who(c)} out with a failure ({c.status})")
            # green-flag stops: out of fuel window or tires gone
            if stops_needed:
                for c in running:
                    if c.running and (c.fuel_laps < k + 1 or c.tire_age > tire_life * 1.35):
                        c.time += pit_loss + _stop_time(stop_s, rng)
                        c.stint = rng.gauss(0, CAL["stint_sd"] * c.adjust)
                        c.tire_age, c.fuel_laps, c.pits = 0, fuel_laps * (1 + c.fuel_save / 200), c.pits + 1
        else:
            # -------- caution laps: field bunched; pit decisions on the first lap under yellow
            order = _order(running)
            leader = order[0]
            if new_caution:
                new_caution = False
                if free_pass:   # the first car a lap down gets its lap back (2003+)
                    down = [c for c in order if c.laps < leader.laps]
                    if down:
                        down[0].laps += 1
                        say(lap, f"Free pass to {who(down[0])}")
                if stops_needed:
                    pitters, stayers = [], []
                    to_go = n_laps - lap
                    for i, c in enumerate(order):
                        need = c.damage > 0 or c.tire_age > tire_life * 0.45 or c.fuel_laps < min(to_go, fuel_laps * 0.7)
                        gamble = (i < 8 and c.fuel_laps >= to_go and c.tire_age < tire_life * 0.8
                                  and rng.random() < 0.35)
                        (pitters if need and not gamble else stayers).append(c)
                    for c in pitters:
                        c.pits += 1
                        c.tire_age, c.fuel_laps, c.damage = 0, fuel_laps * (1 + c.fuel_save / 200), c.damage * 0.4
                        c._stop = _stop_time(stop_s, rng) + order.index(c) * 0.4  # noqa: SLF001
                        c.stint = rng.gauss(0, CAL["stint_sd"] * c.adjust)
                    pitters.sort(key=lambda c: c._stop)  # noqa: SLF001
                    lead_lap = [c for c in pitters if c.laps == leader.laps]
                    order = stayers + lead_lap + [c for c in pitters if c not in lead_lap]
                    if pitters and stayers and order[0] is not leader:
                        say(lap, f"{who(order[0])} stays out and inherits the lead")
                for i, c in enumerate(order):
                    c.time = leader.time + i * 0.3
            k = max(1, min(caution_left, n_laps - lap))   # the whole yellow in one step
            for c in running:
                c.laps += k
                c.time += lap_s * 1.6 * k
                c.fuel_laps -= 0.5 * k
            caution_left -= k
            caution_laps += k
            if caution_left <= 0:
                # restart: the front rows reshuffle on restart skill
                order = _order(running)
                late_restart = lap >= n_laps * 0.8
                for _ in range(2 if late_restart else 1):   # late restarts are wilder
                    for i in range(min(12, len(order)) - 1):
                        a, b = order[i], order[i + 1]
                        fresh = 0.12 if b.tire_age < a.tire_age - 10 else 0.0   # newer tires launch better
                        if rng.random() < clamp(CAL["restart_swap"] + (b.restart - a.restart) / 40 + fresh
                                                + draft_chaos * 0.15, 0.02, 0.7):
                            a.time, b.time = b.time, a.time
                            order[i], order[i + 1] = b, a
                say(lap + 1, f"Green flag: {who(_order(running)[0])} leads the restart")
        lap += k
        # -------- bookkeeping per step
        order = _order([c for c in cars if c.running])
        if order:
            leader = order[0]
            if last_leader is not None and leader is not last_leader and green:
                lead_changes += 1
                say(lap, f"{who(leader)} takes the lead")
            last_leader = leader
            leader_ids.add(id(leader))
            leader.led += k
            for i, c in enumerate(order, start=1):
                c.pos_sum += i * k
                c.pos_laps += k
                if i <= 15:
                    c.top15_laps += k
        if stage_ends and lap >= stage_ends[0] and caution_left <= 0:
            stage_ends.pop(0)
            top = [c for c in order[:10]]
            stage_results.append([c.entry.drivers[0].id for c in top])
            for i, c in enumerate(top, start=1):
                c.stage_pos.append(i)
            if top:
                say(lap, f"Stage {len(stage_results)} to {who(top[0])}")
            caution_left = max(caution_left, 2)   # stage-end caution
            new_caution = True
            cautions += 1

    # ---- classification
    final = sorted(cars, key=lambda c: (-c.laps, c.time if c.running else 1e9, -c.out_lap))
    margin = (final[1].time - final[0].time) if len(final) > 1 and final[1].laps == final[0].laps else 0.0
    if final:
        say(n_laps, f"{who(final[0])} wins" + (f" by {margin:.3f}s" if margin else ""))
    most_led = max(cars, key=lambda c: c.led)
    finishes = []
    n = len(final)
    for pos, c in enumerate(final, start=1):
        arp = c.pos_sum / c.pos_laps if c.pos_laps else n
        box = {"start": c.start, "laps": c.laps, "led": c.led, "status": c.status, "pits": c.pits,
               "arp": round(arp, 1), "fast_laps": c.fast_laps, "passes": c.passes, "passed": c.passed,
               "quality_passes": c.quality_passes, "top15_laps": c.top15_laps, "stage_pos": c.stage_pos,
               "most_led": c is most_led and c.led > 0}
        box["rating"] = driver_rating(pos, n, box, n_laps)
        injured = []
        if c.crashed:
            sev = track.sim.crash_severity / 100
            for d in c.entry.drivers:
                dur = (d.durability if hasattr(d, "durability") else 50)
                if rng.random() < 0.05 * sev * injury_scale * (1.4 - dur / 100):
                    injured.append(d.id)
        finishes.append(Finish(entry=c.entry, position=pos, pace=c.perf, dnf=not c.running,
                               crashed=c.crashed, injured=injured, expected_position=0, box=box))
    # expected finish from equipment alone (scouts' baseline)
    by_eq = sorted(range(len(finishes)), key=lambda i: -finishes[i].entry.equipment)
    for rank, i in enumerate(by_eq, start=1):
        finishes[i].expected_position = rank
    return RaceResult(finishes=finishes, laps=n_laps, cautions=cautions, caution_laps=caution_laps,
                      lead_changes=lead_changes, leaders=len(leader_ids), margin=round(margin, 3),
                      log=log, stages=stage_results)


def driver_rating(pos: int, n: int, box: dict, laps: int) -> float:
    """NASCAR-style driver rating (0-150).

    NASCAR never published the weights; this is the linear model fitted on 19,599 Cup
    driver-races 2013-2026 (docs/research/race_engine_calibration.md section 1.2, R^2 0.84),
    with positions rescaled to a 40-car field and a small average-running-position term for
    the residual (speed). Mean by finish reproduces ~128 for a win, ~87 for 10th, ~48 for 30th.
    """
    scale = 39 / max(n - 1, 1)
    fin = 1 + (pos - 1) * scale
    start = 1 + (box["start"] - 1) * scale
    arp = 1 + (box["arp"] - 1) * scale
    led_share = box["led"] / max(laps, 1)
    r = (103.7 - 1.10 * fin + 3.0 * (pos == 1) + 7.0 * (fin <= 15) + 84.9 * led_share - 0.84 * start
         - 5.9 * bool(box.get("most_led")) + 0.4 * (box["status"] == "running")
         + 0.35 * (fin - arp))
    return round(clamp(r, 20.0, 150.0), 1)
