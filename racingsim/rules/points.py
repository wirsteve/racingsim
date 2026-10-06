"""Points systems and championship formats (data/rules/points.json).

A *system* scores one race: points by finishing position (a published table,
or a per-position step formula for weekly tracks), plus the bonuses the real
rulebooks give - led a lap / led the most laps (NASCAR 1975-2016), stage
points (NASCAR 2017+), a win bonus, heat-race points and show-up points at
weekly tracks, consolation points for cars that did not make the feature.

A *format* decides the champion: straight points, or a Chase / playoff where
the top drivers are reset with seeding bonuses before the final races and
(in elimination formats) cut down round by round to a winner-take-all finale.

Assignments map series templates and years to a system and a format, so a 1996
career scores with the Latford table and a 2018 career with stages and playoffs.
Our race model does not simulate individual laps, so "led a lap", "most laps
led" and stage finishes are drawn from the cars' race pace (fast cars lead).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from ..util import load_json


@dataclass
class System:
    key: str
    label: str
    table: list[float] = field(default_factory=list)   # points for P1, P2, ...
    step: Optional[dict] = None     # {"first": 50, "step": 2, "min": 10} when no published table
    from_last: float = 0.0          # points per position counted from last (Hickory / NASCAR weekly style)
    from_last_cap: int = 0          # ... counting at most this many cars (0 = whole field)
    beyond: float = 0.0             # points for positions past the table
    win_bonus: float = 0.0
    led_lap: float = 0.0
    most_led: float = 0.0
    stage: list[float] = field(default_factory=list)   # stage points for top 10 at each stage end
    stages: int = 0
    heat: list[float] = field(default_factory=list)    # heat-race points by heat finish
    show_up: float = 0.0            # every car that signs in
    dnq: float = 0.0                # cars that miss the feature
    note: str = ""
    sources: list[str] = field(default_factory=list)
    confidence: str = "low"

    def finish_points(self, pos: int, field_size: int = 0) -> float:
        if self.from_last:
            cars = min(field_size, self.from_last_cap) if self.from_last_cap else field_size
            return max(self.from_last, self.from_last * (cars - pos + 1))
        if self.table:
            return self.table[pos - 1] if pos <= len(self.table) else self.beyond
        if self.step:
            return max(self.step.get("min", 1), self.step["first"] - self.step.get("step", 2) * (pos - 1))
        return 0.0


@dataclass
class Format:
    key: str
    label: str
    kind: str = "points"            # points | chase | elimination
    drivers: int = 0                # playoff field
    races: int = 0                  # races in the Chase / playoffs
    base: float = 0.0               # reset base (e.g. 5000, 2000)
    seed_steps: list[float] = field(default_factory=list)   # reset bonus by regular-season rank (Chase 2004-06 style)
    per_win: float = 0.0            # reset bonus per win
    win_in: bool = False            # a regular-season win clinches a spot
    rounds: list[int] = field(default_factory=list)          # elimination: drivers left after each round
    round_races: list[int] = field(default_factory=list)
    finale: bool = False            # the last round is decided by finishing order
    note: str = ""
    sources: list[str] = field(default_factory=list)
    confidence: str = "low"


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return load_json("rules/points.json")
    except FileNotFoundError:
        return {}


def _mk(cls, key, raw):
    known = set(cls.__dataclass_fields__)
    return cls(key=key, **{k: v for k, v in raw.items() if k in known and k != "key"})


@lru_cache(maxsize=1)
def systems() -> dict[str, System]:
    return {k: _mk(System, k, v) for k, v in _data().get("systems", {}).items()}


@lru_cache(maxsize=1)
def formats() -> dict[str, Format]:
    return {k: _mk(Format, k, v) for k, v in _data().get("formats", {}).items()}


DEFAULT = System("default", "Generic points", step={"first": 50, "step": 2, "min": 10}, win_bonus=0)


@lru_cache(maxsize=8192)
def assignment(template_key: str, year: int, scope: str = "", state: str = "") -> tuple[str, Optional[str]]:
    """(system key, format key) for this series and season.

    Rules are matched in file order: the first entry naming the template (and, if it lists
    ``states``, the series' home state - weekly dirt tracks score by their sanctioning body,
    IMCA in Iowa, DIRTcar UMP in Illinois, WISSOTA in Minnesota) wins; ``scopes`` entries are
    the fallback for templates without their own rule."""
    best = None
    for a in _data().get("assign", []):
        lo, hi = a.get("from", 0), a.get("to", 9999)
        if not lo <= year <= hi:
            continue
        states = a.get("states")
        if states and state not in states:
            continue
        if template_key in a.get("templates", []):
            return a["system"], a.get("format")
        if scope and scope in a.get("scopes", []) and best is None:
            best = (a["system"], a.get("format"))
    return best or ("default", None)


def system_for(template_key: str, year: int, scope: str = "", state: str = "") -> System:
    return systems().get(assignment(template_key, year, scope, state)[0], DEFAULT)


def format_for(template_key: str, year: int, scope: str = "", state: str = "") -> Optional[Format]:
    key = assignment(template_key, year, scope, state)[1]
    return formats().get(key) if key else None


def score_race(system: System, order: list[tuple[int, float]], rng: random.Random) -> dict[int, float]:
    """Points for one race. ``order`` is [(key, race pace)] in finishing order.

    Lap-leading and stage results are drawn from pace: the winner always led a lap;
    a handful of other fast cars led too; the most laps usually go to the winner.
    """
    n = len(order)
    pts = {k: system.finish_points(i, n) for i, (k, _) in enumerate(order, start=1)}
    if not order:
        return pts
    pts[order[0][0]] += system.win_bonus
    pts = {k: v + system.show_up for k, v in pts.items()}
    if system.led_lap or system.most_led:
        top = order[: min(12, len(order))]
        leaders = {order[0][0]}
        for k, pace in sorted(top[1:], key=lambda x: -(x[1] + rng.gauss(0, 4)))[: rng.randint(0, 5)]:
            leaders.add(k)
        for k in leaders:
            pts[k] += system.led_lap
        most = order[0][0] if rng.random() < 0.5 or len(leaders) == 1 else rng.choice(sorted(leaders))
        pts[most] += system.most_led
    if system.stage and system.stages:
        for _ in range(system.stages):
            ranked = sorted(order, key=lambda x: -(x[1] + rng.gauss(0, 3)))
            for i, (k, _) in enumerate(ranked[: len(system.stage)]):
                pts[k] += system.stage[i]
    return pts


def heat_points(system: System, keys_by_heat_finish: list[int]) -> dict[int, float]:
    return {k: system.heat[i] for i, k in enumerate(keys_by_heat_finish) if i < len(system.heat)}


def score_box(system: System, finishes) -> dict[int, float]:
    """Points from a lap-by-lap race: real laps led, most laps led and stage finishes."""
    n = len(finishes)
    pts: dict[int, float] = {}
    for f in finishes:
        b = f.box or {}
        p = system.finish_points(f.position, n) + system.show_up
        if f.position == 1:
            p += system.win_bonus
        if b.get("led"):
            p += system.led_lap
        if b.get("most_led"):
            p += system.most_led
        if system.stage:
            for sp in b.get("stage_pos", []):
                if sp <= len(system.stage):
                    p += system.stage[sp - 1]
        pts[f.entry.drivers[0].id] = p
    return pts
