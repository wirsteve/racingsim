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
    "stint_sd": 2.6,
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
    pit_mult: float = 1.0       # pit crew speed (multiplies stop time)
    pit_sd: float = 1.0         # pit crew consistency (multiplies stop variance and disasters)
    strategy: float = 50.0      # crew chief's strategy rating
    cc_aggr: float = 50.0       # crew chief's appetite for gambles (stay out, two tires)
    injury: float = 1.0         # medical: injury chance multiplier


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
    incidents: list = field(default_factory=list)  # [(instigator id, [collected ids], big one?)]
    paybacks: list = field(default_factory=list)   # [(retaliator id, target id)]
    weather: Optional[dict] = None                 # sim/weather.py: hot, wet, rain-shortened, delay
    scheduled: int = 0                             # laps scheduled (a rain-shortened race runs fewer)
    replay: Optional[dict] = None                  # lap-by-lap frames for the race viewer (detail mode only)


def race_laps(track: "Track", tier: int) -> int:
    tt = S.track_type_of(track)
    miles = CAL["distance_mi"][max(0, min(7, tier))][tt]
    length = track.facts.length_mi or 0.5
    return int(clamp(round(miles / length), CAL["min_laps"], CAL["max_laps"]))


def _lap_seconds(track: "Track", tier: int, tt: str) -> float:
    mph = CAL["mph"][tt] * (0.78 + 0.0314 * max(0, min(7, tier)))
    return (track.facts.length_mi or 0.5) / mph * 3600


# --------------------------------------------------------------------------- setup
def _car(e: Entry, tt: str, cw: float, rng: random.Random, discipline: Optional[str] = None) -> Car:
    ds = e.drivers
    lead = ds[0]
    for d in ds:
        S.ensure(d)

    def avg(fn):
        return sum(fn(d) for d in ds) / len(ds)
    drv = avg(lambda d: S.base(d, discipline) * S.track_factor(d, tt) + S.track_bonus(d, tt)
              + 0.5 * S.offset(d, "speed") + 0.15 * S.offset(d, "consistency"))
    crew = e.crew or {}
    drv += (avg(lambda d: getattr(d, "morale", 60.0)) - 60) * 0.02   # confidence: about +/-1 point
    perf = (1 - cw) * drv + cw * (e.equipment + crew.get("power", 0.0))
    # This weekend's setup: feedback and the crew chief/technical director narrow the miss;
    # a crew chief who likes the car the way the driver does finds speed (chemistry).
    setup = rng.gauss(0, CAL["setup_sd"] * clamp(1.15 - S.offset(lead, "feedback") / 25, 0.6, 1.5)
                      * crew.get("setup_sd", 1.0))
    perf += setup + crew.get("setup_mean", 0.0)
    qual = perf + (1 - cw) * 0.6 * S.offset(lead, "qualifying")
    aggression = lead.aggression
    risk = clamp((0.55 + (aggression - 50) / 120 - S.offset(lead, "consistency") / 40
                  - S.offset(lead, "car_control") / 50 + (S.trait(lead, "temper") - 50) / 250), 0.25, 2.2)
    if crew:   # the spotter keeps the driver out of trouble
        risk = clamp(risk * (1.2 - crew.get("awareness", 50) / 250), 0.2, 2.4)
    return Car(entry=e, start=0, perf=perf, qual=qual,
               adjust=clamp(1.1 - S.offset(lead, "feedback") / 30, 0.6, 1.4) * crew.get("adjust", 1.0),
               pit_mult=crew.get("pit_s", 1.0), pit_sd=crew.get("pit_sd", 1.0),
               strategy=crew.get("strategy", 50.0), cc_aggr=crew.get("aggression", 50.0),
               injury=crew.get("injury", 1.0),
               tire_mgmt=clamp(0.5 + S.offset(lead, "tire_management") / 30, 0, 1),
               craft=S.offset(lead, "racecraft"), defend=S.offset(lead, "defending"),
               restart=S.offset(lead, "restarts") + crew.get("restarts", 0.0), risk=risk, composure=S.offset(lead, "composure"),
               fitness=S.offset(lead, "fitness"), fuel_save=S.offset(lead, "fuel_saving"))


def _stop_time(stop_s: float, rng: random.Random, c: Optional["Car"] = None) -> float:
    """A pit stop: usually close to the crew's norm, occasionally a disaster (loose wheel, jack)."""
    mult, sd = (c.pit_mult, c.pit_sd) if c is not None else (1.0, 1.0)
    t = stop_s * mult + abs(rng.gauss(0, CAL["pit_sd"] * sd))
    if rng.random() < CAL["loose_wheel"] * sd:
        t += rng.uniform(10, 25)
    return t


def _order(cars: list[Car]) -> list[Car]:
    """Running order: laps completed first, then race time."""
    return sorted(cars, key=lambda c: (-c.laps, c.time))


def _sync_laps(running: list[Car], completed: int, lap_s: float) -> None:
    """Laps completed follow from the time gap to the leader: a full lap of time behind is a lap down."""
    if not running:
        return
    lead_t = min(c.time for c in running)
    for c in running:
        c.laps = completed - max(0, int((c.time - lead_t) // lap_s))


def _frame(cars: list[Car], order: list[Car], lap: int, green: bool, caution_left: int, pits_seen: list) -> list:
    """One replay frame: running order with each car's gap to the leader (tenths of a second, laps down
    included) and a code - 0 running, 1 pitted this step, 2 out (crash), 3 out (failure)."""
    idx = {id(c): i for i, c in enumerate(cars)}
    lead_t = order[0].time if order else 0.0
    rows = []
    for c in order:
        i = idx[id(c)]
        code = 1 if c.pits > pits_seen[i] else 0
        pits_seen[i] = c.pits
        rows.append([i, int(round((c.time - lead_t) * 10)), code])
    for i, c in enumerate(cars):
        if not c.running:
            rows.append([i, -1, 2 if c.crashed else 3])
    flag = "G" if green and caution_left <= 0 else "Y"
    return [lap, flag, rows]


# --------------------------------------------------------------------------- the race
def run(entries: list[Entry], track: "Track", tier: int, car_weight: float, rng: random.Random,
        detail: bool = False, stages: int = 0, free_pass: bool = True, injury_scale: float = 1.0,
        laps: Optional[int] = None, name_of=None, discipline: Optional[str] = None,
        realism: Optional[dict] = None, weather: Optional[dict] = None) -> RaceResult:
    """One race. ``realism`` holds the world's settings multipliers (crashes, failures, injuries, luck);
    ``weather`` comes from sim/weather.py."""
    real = realism or {}
    crash_x, fail_x, luck_x = real.get("crashes", 1.0), real.get("failures", 1.0), real.get("luck", 1.0)
    injury_scale *= real.get("injuries", 1.0)
    wx = (weather or {}).get("kind")
    tt = S.track_type_of(track)
    s = track.sim
    n_laps = laps or race_laps(track, tier)
    lap_s = _lap_seconds(track, tier, tt)
    cw = clamp(car_weight * (0.75 + 0.5 * (s.horsepower_importance + s.aero_importance) / 200)
               * (1.0 - 0.35 * (s.drafting_effect / 100)), 0.1, 0.8)
    cars = [_car(e, tt, cw, rng, discipline) for e in entries]
    if len(cars) < 2:
        return RaceResult([], n_laps)
    log: list = []
    say = (lambda lap, text: log.append([lap, text])) if detail else (lambda lap, text: None)
    who = name_of or (lambda c: c.entry.drivers[0].name)
    if wx == "wet":
        # Rain on a road course: car control is everything, and the mistakes multiply.
        for c in cars:
            cc = S.offset(c.entry.drivers[0], "car_control")
            c.perf += 0.3 * cc
            c.risk = clamp(c.risk * clamp(1.45 - cc / 30, 0.9, 1.9), 0.2, 3.0)
        say(0, "Rain: the race starts on a wet track")
    elif wx == "hot":
        say(0, "A hot, slick track: tires will go away and drivers will feel it")
    elif wx == "delay":
        say(0, "A rain delay before the start; the track is dry for the race")

    # ---- qualifying (or heat-based lineup noise for short local races)
    q_noise = lap_s * CAL["noise"] * CAL["qual_noise"] * (1.6 if tier <= 2 else 1.0) * luck_x
    for c in cars:
        base_mech = c.entry.mech if c.entry.mech is not None else 0.03 * (c.entry.crew or {}).get("mech", 1.0)
        base_mech = min(0.95, base_mech * fail_x)
        c.mech_lap = 1 - (1 - base_mech) ** (1 / n_laps)
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
    crash_share = 0.72 * crash_x / (0.72 * crash_x + 0.28)       # share of cautions that are crashes
    caution_hazard = exp_cautions / n_laps * (0.28 + 0.72 * crash_x) * (1.5 if wx == "wet" else 1.0)
    falloff = CAL["falloff"] * (0.4 + 1.2 * s.tire_degradation / 100) * lap_s * (1.25 if wx == "hot" else 1.0)
    noise = (CAL["noise"] * lap_s * (1 + CAL["draft_noise"] * (s.drafting_effect / 100) ** 2) * luck_x
             * (1.5 if wx == "wet" else 1.0))
    pass_threshold = lap_s * 0.0013 * (0.3 + 1.4 * s.passing_difficulty / 100)
    draft_chaos = s.drafting_effect / 100
    # Races you watch run a lap at a time; the rest of the world in ~16 steps (same model, coarser).
    step = 1 if detail else max(1, n_laps // 24)
    stage_ends = []
    if stages:
        stage_ends = [e for e in (round(n_laps * f) for f in ((0.25, 0.5) if stages == 2 else (0.33, 0.66))[:stages])
                      if 0 < e < n_laps]
    for c in cars:
        c.fuel_laps = fuel_laps * (1 + c.fuel_save / 200)
        c.stint = rng.gauss(0, CAL["stint_sd"] * c.adjust)

    scheduled = n_laps
    if wx == "rain_short":
        # The rain comes: the race goes the distance it can, and it's official.
        n_laps = max(1, round(n_laps * weather.get("share", 0.75)))
    # Replay frames (races you watch): one per step - [lap, flag, [[car, gap tenths, code], ...] in order].
    frames: list = [] if detail else None
    pits_seen = [0] * len(cars)
    lap = 0
    caution_left = 0
    cautions = caution_laps = lead_changes = 0
    leader_ids: set = set()
    last_leader: Optional[Car] = None
    stage_results: list = []
    new_caution = False
    incidents: list = []
    paybacks: list = []
    # Grudges: a driver with a temper and a hot rivalry may settle it today.
    by_driver = {c.entry.drivers[0].id: c for c in cars}
    planned: list = []
    for c in cars:
        d = c.entry.drivers[0]
        for target_id, heat in (getattr(d, "rivals", None) or {}).items():
            tgt = by_driver.get(target_id)
            if tgt is None or heat < 35:
                continue
            # Only a short fuse acts on it, and even then rarely: most grudges are settled by racing hard.
            fuse = max(0.0, S.trait(d, "temper") - 45) / 55
            if rng.random() < heat / 100 * fuse * 0.2:
                planned.append([rng.randint(int(n_laps * 0.2), max(int(n_laps * 0.2) + 1, int(n_laps * 0.95))), c, tgt])

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
        if green and stage_ends and lap < stage_ends[0]:
            k = min(k, stage_ends[0] - lap)
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
                tired = (max(0.0, -c.fitness) * 0.002 * lap_s * (lap / n_laps)
                         * (2.0 if wx == "hot" else 1.0 if n_laps > 150 else 0.0))
                pace = (lap_s * (1 - (c.perf + c.stint - 50) * CAL["spread_per_point"] - c.damage * 0.01)
                        + wear + tired)
                jitter = noise * (1.4 - (c.perf - 30) / 100) * math.sqrt(k)
                if late:
                    jitter *= (1.15 - clamp(c.composure / 40, -0.3, 0.3))
                seg = pace * k + rng.gauss(0, jitter)
                c.time += seg
                c.tire_age += k
                c.fuel_laps -= k
                c._seg = seg / k  # noqa: SLF001 - per-lap pace this step (fastest-lap credit)
            _sync_laps(running, lap + k, lap_s)
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
            # keep the times in the order the passing produced (a car held up stays behind, but
            # ahead of anyone it got by in the same step)
            for i in range(1, len(new)):
                a, b = new[i - 1], new[i]
                if a.laps == b.laps and b.time <= a.time:
                    b.time = a.time + 0.02
            # fastest lap of the step
            fastest = min(running, key=lambda x: x._seg)  # noqa: SLF001
            fastest.fast_laps += k
            # incidents: chance this step brings out a caution
            if rng.random() < 1 - (1 - caution_hazard) ** k:
                big = tt == "superspeedway" and rng.random() < CAL["big_one_share"]
                cause = rng.random()
                if cause < crash_share or big:
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
                    if len(involved) > 1:
                        incidents.append((involved[0].entry.drivers[0].id,
                                          [x.entry.drivers[0].id for x in involved[1:]], big))
                else:
                    say(lap + k, "Caution: " + rng.choice(["debris on the track", "a spin", "fluid on the track",
                                                             "a car stopped on track"]))
                cautions += 1
                caution_left = max(2, int(CAL["caution_laps"][tt] * rng.uniform(0.7, 1.4)))
                new_caution = True
            # payback: a planned retaliation happens if both are still out there under green
            for p in [p for p in planned if lap < p[0] <= lap + k]:
                planned.remove(p)
                _, att, tgt = p
                if att.running and tgt.running and caution_left <= 0:
                    paybacks.append((att.entry.drivers[0].id, tgt.entry.drivers[0].id))
                    if rng.random() < 0.6:
                        tgt.running, tgt.status, tgt.crashed, tgt.out_lap = False, "crash", True, tgt.laps
                    else:
                        tgt.damage += 3
                    att.damage += rng.uniform(0, 1.5)
                    say(lap + k, f"PAYBACK: {who(att)} turns {who(tgt)} into the wall")
                    cautions += 1
                    caution_left = max(2, int(CAL["caution_laps"][tt] * rng.uniform(0.7, 1.2)))
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
                        # A sharp strategist times the stop (traffic, the cycle) and loses less on pit road.
                        c.time += pit_loss * (1.05 - c.strategy / 1000) + _stop_time(stop_s, rng, c)
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
                stay: set = set(map(id, order))
                if stops_needed:
                    pitters, stayers = [], []
                    to_go = n_laps - lap
                    two_tires = set()
                    for i, c in enumerate(order):
                        need = c.damage >= 0.3 or c.tire_age > tire_life * 0.45 or c.fuel_laps < min(to_go, fuel_laps * 0.7)
                        # Crew chief's call: aggressive ones gamble on track position more often; good
                        # strategists judge better whether the tires will really make it to the end.
                        judged = (c.tire_age + to_go) / tire_life + rng.gauss(0, (100 - c.strategy) / 250)
                        viable = c.fuel_laps >= to_go and judged < 0.95
                        gamble = i < 10 and viable and rng.random() < 0.12 + c.cc_aggr / 220
                        (pitters if need and not gamble else stayers).append(c)
                        if (need and not gamble and c.damage == 0 and 5 <= i and to_go < tire_life * 0.7
                                and rng.random() < c.cc_aggr / 160):
                            two_tires.add(c)
                    for c in pitters:
                        c.pits += 1
                        two = c in two_tires
                        c.tire_age = c.tire_age // 2 if two else 0
                        c.fuel_laps = fuel_laps * (1 + c.fuel_save / 200)
                        c.damage = c.damage * 0.4 if c.damage * 0.4 >= 0.3 else 0.0   # fixed what they could
                        c._stop = _stop_time(stop_s * (0.62 if two else 1.0), rng, c) + order.index(c) * 0.4  # noqa: SLF001
                        c.stint = rng.gauss(0, CAL["stint_sd"] * c.adjust)
                    stay = set(map(id, stayers))
                    rank = {id(c): i for i, c in enumerate(order)}
                    # Off pit road in the order the stops finish; cars that stayed out line up ahead
                    # of them, each lap's cars together (lapped cars stay lapped).
                    order.sort(key=lambda c: (-c.laps, id(c) not in stay,
                                              rank[id(c)] if id(c) in stay else c._stop))  # noqa: SLF001
                    if pitters and stayers and order[0] is not leader:
                        say(lap, f"{who(order[0])} stays out and inherits the lead")
                    fast2 = [c for c in pitters if c in two_tires][:1]
                    if fast2:
                        say(lap, f"{who(fast2[0])} takes two tires to gain track position")
                # The field bunches up behind the pace car: each lap's cars in a tight line.
                gap = min(0.3, lap_s * 0.5 / len(order))
                base, slot = leader.time, {}
                for c in order:
                    down = max(0, leader.laps - c.laps)
                    i = slot.get(down, 0)
                    slot[down] = i + 1
                    c.time = base + down * lap_s + i * gap
            k = max(1, min(caution_left, n_laps - lap))   # the whole yellow in one step
            for c in running:
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
                        if a.laps != b.laps:
                            break
                        fresh = 0.12 if b.tire_age < a.tire_age - 10 else 0.0   # newer tires launch better
                        if rng.random() < clamp(CAL["restart_swap"] + (b.restart - a.restart) / 40 + fresh
                                                + draft_chaos * 0.15, 0.02, 0.7):
                            a.time, b.time = b.time, a.time
                            order[i], order[i + 1] = b, a
                say(lap + k + 1, f"Green flag: {who(_order(running)[0])} leads the restart")
        lap += k
        _sync_laps([c for c in cars if c.running], lap, lap_s)
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
        if frames is not None:
            frames.append(_frame(cars, order, lap, green, caution_left, pits_seen))
        if stage_ends and lap >= stage_ends[0]:
            # Scored at the stage lap - under yellow too (then there's no extra caution).
            stage_ends.pop(0)
            top = [c for c in order[:10]]
            stage_results.append([c.entry.drivers[0].id for c in top])
            for i, c in enumerate(top, start=1):
                c.stage_pos.append(i)
            if top:
                say(lap, f"Stage {len(stage_results)} to {who(top[0])}")
            if caution_left <= 0:
                caution_left = 2   # stage-end caution
                new_caution = True
                cautions += 1

    # ---- classification
    final = sorted(cars, key=lambda c: (-c.laps, c.time if c.running else 1e9, -c.out_lap))
    margin = ((final[1].time - final[0].time) if len(final) > 1 and final[0].running and final[1].running
              and final[1].laps == final[0].laps else 0.0)
    if final:
        if n_laps < scheduled:
            say(n_laps, f"Rain! The race is called after {n_laps} of {scheduled} laps")
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
                if rng.random() < 0.05 * sev * injury_scale * (1.4 - dur / 100) * c.injury:
                    injured.append(d.id)
        finishes.append(Finish(entry=c.entry, position=pos, pace=c.perf, dnf=not c.running,
                               crashed=c.crashed, injured=injured, expected_position=0, box=box))
    # expected finish from equipment alone (scouts' baseline)
    by_eq = sorted(range(len(finishes)), key=lambda i: -finishes[i].entry.equipment)
    for rank, i in enumerate(by_eq, start=1):
        finishes[i].expected_position = rank
    replay = None
    if frames is not None:
        idx = {id(c): i for i, c in enumerate(cars)}
        replay = {"lap_s": round(lap_s, 3), "laps": n_laps, "scheduled": scheduled, "track_type": tt,
                  "cars": [{"id": c.entry.drivers[0].id, "ids": [d.id for d in c.entry.drivers],
                            "name": who(c), "start": c.start,
                            "team": c.entry.team_id, "car_key": c.entry.car_key} for c in cars],
                  "finish": [idx[id(c)] for c in final], "frames": frames}
    return RaceResult(finishes=finishes, laps=n_laps, cautions=cautions, caution_laps=caution_laps,
                      lead_changes=lead_changes, leaders=len(leader_ids), margin=round(margin, 3),
                      log=log, stages=stage_results, incidents=incidents, paybacks=paybacks, weather=weather, scheduled=scheduled,
                      replay=replay)


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
