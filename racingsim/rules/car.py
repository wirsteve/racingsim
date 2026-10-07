"""The racer's car: chassis, engine, shocks and tires, built to the class rules.

How a car turns into speed (the ``equipment`` number the race model uses):

* **chassis** - builder quality, tiring with age (chassis flex, fatigue), and
  crash damage that is not repaired;
* **engine** - the package the rules allow (built / crate / sealed crate / spec /
  claimer) and how fresh it is: past its rebuild interval it loses power and
  starts to fail;
* **tires** - how many new tires are bolted on each night, against the class
  tire rule; worn tires fall off hardest where the track eats tires;
* **shocks** - package level; matters most on short, flat, handling tracks;
* **setup** - the driver's feedback.

The track decides the mix: horsepower tracks reward the engine, abrasive tracks
reward tires, flat short tracks reward chassis and shocks. Class ``spread`` sets
how far money can separate cars under the rules: a spec Legend or a claimer
stock car cannot be bought into the lead the way a super late model can.

AI racers buy and maintain their cars from their season budget with the same
options and prices the player sees; their in-season wear is modelled in steady
state (cheap), the player's race by race with a money ledger.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..util import clamp
from .classes import CarClass, Option

if TYPE_CHECKING:
    from ..tracks import Track

REF_RAW = 66.0      # raw component score of a typical, competitive local car -> equipment ~50
SCALE = 1.45        # raw -> equipment gain before the class spread is applied


@dataclass
class Car:
    cls: str
    chassis: str
    chassis_q: float
    chassis_age: float              # seasons since new
    engine: str
    engine_q: float
    shocks: str
    shocks_q: float
    condition: float = 100.0        # chassis/body: 100 = straight, unrepaired damage lowers it
    engine_runs: int = 0            # races since the last freshen
    engine_health: float = 100.0    # 0 = blown
    tire_wear: float = 0.15         # 0 = sticker tires, 1 = corded
    new_tires: int = 2              # new tires bought each night (player choice; AI by budget)
    auto_rebuild: bool = True       # freshen the engine at the interval automatically
    auto_repair: bool = True        # fix crash damage straight away if the money is there
    reserve: float = 0.0            # AI: money left this season for repairs
    account: Optional[float] = None  # player: this season's racing account (None = closed)
    winnings: float = 0.0           # player: purses and claims banked this season
    drawn: float = 0.0              # player: savings put into this season's account
    year: int = 0                   # season the ledger is currently writing
    races: int = 0
    ledger: list = field(default_factory=list)  # player: [week, text, amount]
    tag: str = ""                   # player: the car's name in the fleet ("Car 2")
    season_seen: int = 0            # player: the season the car last started (chassis age counts from it)
    interval_mult: float = 1.0      # player: the engine room stretches the freshen interval (rules/shop.py)

    # ------------------------------------------------------------------ components
    def chassis_score(self, cls: CarClass) -> float:
        tired = max(0.0, self.chassis_age - 1) / max(cls.chassis_life, 1.0)
        return self.chassis_q * max(0.55, 1 - 0.32 * tired) * (0.45 + 0.55 * self.condition / 100)

    def engine_score(self, cls: CarClass) -> float:
        opt = cls.engine(self.engine)
        interval = opt.rebuild_races * self.interval_mult if opt and opt.rebuild_races else 0
        fresh = 1.0
        if interval and self.engine_runs > interval:
            fresh = 1 - 0.18 * min(1.0, (self.engine_runs - interval) / interval)
        return self.engine_q * fresh * (0.6 + 0.4 * self.engine_health / 100)

    def tire_score(self) -> float:
        return 100 * (1 - 0.65 * self.tire_wear)

    def overdue(self, cls: CarClass) -> float:
        """0 = fresh engine, 1 = a full interval past due."""
        opt = cls.engine(self.engine)
        if not opt or not opt.rebuild_races:
            return 0.0
        interval = opt.rebuild_races * self.interval_mult
        return clamp((self.engine_runs - interval) / interval, 0, 2)


def weights(track: Optional["Track"]) -> tuple[float, float, float, float]:
    """(chassis, engine, tires, shocks) weights at this track."""
    if track is None:
        hp, td, pd = 50, 50, 50
    else:
        s = track.sim
        hp, td, pd = s.horsepower_importance, s.tire_degradation, s.passing_difficulty
    return (0.32 * (0.85 + 0.3 * pd / 100), 0.30 * (0.55 + 0.9 * hp / 100),
            0.22 * (0.5 + 1.0 * td / 100), 0.12 * (0.7 + 0.6 * (100 - hp) / 100))


def rating(car: Car, cls: CarClass, track: Optional["Track"], feedback: float, tire_wear: Optional[float] = None,
           bonus: float = 0.0) -> float:
    """``bonus``: raw points from the racer's shop (rules/shop.py rating_bonus)."""
    wc, we, wt, ws = weights(track)
    tw = car.tire_wear if tire_wear is None else tire_wear
    raw = (wc * car.chassis_score(cls) + we * car.engine_score(cls) + wt * 100 * (1 - 0.65 * tw)
           + ws * car.shocks_q) / (wc + we + wt + ws)
    raw += (feedback - 50) * 0.10 + bonus   # setup: a driver who can tell the crew what the car is doing
    return clamp(50 + (raw - REF_RAW) * SCALE * cls.spread, 5, 97)


# ---------------------------------------------------------------------- tires
def wear_per_race(cls: CarClass, track: Optional["Track"]) -> float:
    """Wear a tire picks up in one night (1.0 = used up)."""
    td = track.sim.tire_degradation if track is not None else 50
    return (0.6 + 0.8 * td / 100) / max(cls.tires.life_races, 1.0)


def steady_wear(cls: CarClass, new_per_race: float, track: Optional["Track"]) -> float:
    """Average wear of the set for a racer who buys ``new_per_race`` tires every night."""
    w = wear_per_race(cls, track)
    if new_per_race <= 0:
        return 0.9
    # Each tire lives 4/n nights; average age over its life is half that.
    return clamp(w * (4 / new_per_race) / 2, 0.02, 0.9)


def max_new(cls: CarClass) -> int:
    return 4 if cls.tires.max_new is None else int(cls.tires.max_new)


def fit_tires(car: Car, n: int) -> None:
    """Bolt on ``n`` new tires, replacing the most worn corners."""
    n = max(0, min(4, n))
    car.tire_wear = car.tire_wear * (4 - n) / 4


# ---------------------------------------------------------------------- buying
def option_cost(opt: Option) -> float:
    return opt.usd


def build(cls: CarClass, chassis: Option, engine: Option, shocks: Option, new_tires: int) -> Car:
    return Car(cls=cls.key, chassis=chassis.key, chassis_q=chassis.quality, chassis_age=chassis.age,
               engine=engine.key, engine_q=engine.quality, shocks=shocks.key, shocks_q=shocks.quality,
               new_tires=min(new_tires, max_new(cls)), tire_wear=0.2)


def resale(car: Car, cls: CarClass) -> float:
    """What the car fetches on the used market (chassis + engine + shocks)."""
    ch = cls.chassis_opt(car.chassis)
    en = cls.engine(car.engine)
    sh = cls.shock(car.shocks)
    v = 0.0
    if ch:
        age = max(car.chassis_age - ch.age, 0)
        v += ch.usd * max(0.15, 0.6 * 0.82 ** age) * (0.4 + 0.6 * car.condition / 100)
    if en:
        v += en.usd * 0.55 * (0.3 + 0.7 * car.engine_health / 100) * (1 - 0.3 * car.overdue(cls) / 2)
    if sh:
        v += sh.usd * 0.4
    return v


def by_budget(options: list[Option], money: float) -> Option:
    """Best (highest quality) option affordable with ``money``; the cheapest if none is."""
    opts = sorted(options, key=lambda o: o.usd)
    best = opts[0]
    for o in opts:
        if o.usd <= money and o.quality >= best.quality:
            best = o
    return best


def ai_car(cls: CarClass, year: int, ratio: float, rng: random.Random, old: Optional[Car]) -> Car:
    """Season-start car for an AI racer whose money covers ``ratio`` of a typical programme.

    Racers keep their car across seasons: it ages, gets freshened, and is replaced
    when it is worn out or the budget allows a step up. Money buys the parts the
    class rules allow - a richer racer gets a newer chassis from a better builder,
    the stronger engine package, better shocks and more new tires each night.
    """
    engines = cls.engines_in(year)
    ch_opts = sorted(cls.chassis, key=lambda o: o.usd)
    sh_opts = sorted(cls.shocks, key=lambda o: o.usd) or [Option("stock", "Stock", 0, 50)]
    level = clamp((ratio - 0.4) / 1.6 + rng.gauss(0, 0.12), 0, 1)  # 0.4x -> 0, 2.0x -> 1

    def pick(opts: list[Option]) -> Option:
        opts = sorted(opts, key=lambda o: o.usd)
        return opts[min(len(opts) - 1, int(level * len(opts)))]

    tires = int(round(clamp(cls.tires.typical_new * (0.4 + 0.75 * ratio) + rng.gauss(0, 0.5), 0, max_new(cls))))
    if old is not None and old.cls == cls.key:
        car = old
        car.chassis_age += 1
        ch = cls.chassis_opt(car.chassis)
        worn_out = car.chassis_age >= cls.chassis_life * rng.uniform(0.8, 1.3) or car.condition < 55
        step_up = level > 0.7 and car.chassis_age >= 2 and rng.random() < 0.45
        if worn_out or step_up or ch is None:
            new = pick(ch_opts)
            car.chassis, car.chassis_q, car.chassis_age, car.condition = new.key, new.quality, new.age, 100.0
        car.condition = max(car.condition, 92.0)  # winter rebuild straightens the old one
        en = cls.engine(car.engine)
        if en is None or not en.available(year) or (level > 0.65 and rng.random() < 0.3):
            en = pick(engines)
            car.engine, car.engine_q = en.key, en.quality
        car.engine_runs, car.engine_health = 0, 100.0  # winter freshen
        if level > 0.6 and rng.random() < 0.3:
            sh = pick(sh_opts)
            car.shocks, car.shocks_q = sh.key, sh.quality
        car.new_tires = min(tires, max_new(cls))
        return car
    return build(cls, pick(ch_opts), pick(engines), pick(sh_opts), tires)


# ---------------------------------------------------------------------- running costs
def night_cost(cls: CarClass, car: Car) -> float:
    """Entry + pit passes, fuel, consumables and the new tires for one race night."""
    return cls.per_race_fixed() + car.new_tires * cls.tires.usd


def engine_wear_cost(cls: CarClass, car: Car) -> float:
    opt = cls.engine(car.engine)
    if not opt or not opt.rebuild_races:
        return 0.0
    return opt.rebuild_usd / opt.rebuild_races


def season_running(cls: CarClass, car: Car, events: int) -> float:
    return events * (night_cost(cls, car) + engine_wear_cost(cls, car))


def typical_build(cls: CarClass, year: int = 2024) -> Car:
    """The middle option of every part: what a typical competitive racer in the class runs."""
    def mid(opts):
        opts = sorted(opts, key=lambda o: o.usd)
        return opts[len(opts) // 2] if opts else Option("stock", "Stock", 0, 50)
    return build(cls, mid(cls.chassis), mid(cls.engines_in(year)), mid(cls.shocks), cls.tires.typical_new)


def capital_per_season(cls: CarClass, car: Car) -> float:
    """Depreciation of the car: chassis over its life, engine and shocks over ~3 seasons."""
    ch, en, sh = cls.chassis_opt(car.chassis), cls.engine(car.engine), cls.shock(car.shocks)
    return ((ch.usd * 0.6 / max(cls.chassis_life, 1)) if ch else 0) + (en.usd / 3 if en else 0) + (sh.usd / 3 if sh else 0)


_OVERHEAD: dict = {}


def overhead_per_night(cls: CarClass, template) -> float:
    """Crew, hauler, practice tires, test days and spares: what a researched season budget for this
    series costs beyond the car's parts and race nights (typical programme), spread per event."""
    key = (cls.key, template.key)
    if key not in _OVERHEAD:
        car = typical_build(cls)
        model = capital_per_season(cls, car) + season_running(cls, car, template.events)
        _OVERHEAD[key] = max(0.0, template.season_cost - model) / max(template.events, 1)
    return _OVERHEAD[key]


def mech_risk(cls: CarClass, car: Car, stress: float) -> float:
    """Chance of a mechanical DNF tonight."""
    base = 0.008 + 0.03 * stress / 100
    return clamp(base * (1 + 2.2 * car.overdue(cls)) * (1 + (100 - car.engine_health) / 60)
                 * (1.25 - car.engine_q / 200), 0.003, 0.5)


def crash_damage(rng: random.Random, severity: float) -> float:
    """Share of the chassis knocked out of shape (0-1) in a crash."""
    return clamp(rng.betavariate(1.4, 4.0) * (0.6 + 0.9 * severity / 100), 0.02, 1.0)


TYPICAL_DAMAGE = 0.27  # mean of crash_damage() at an average track


def new_chassis_price(cls: CarClass) -> float:
    return max((c.usd for c in cls.chassis), default=10_000.0)


def repair_cost(cls: CarClass, damage: float) -> float:
    """Parts and labour to straighten the car; a typical wreck costs ``repair_frac`` of a new chassis,
    a destroyed one costs about a new chassis."""
    new = new_chassis_price(cls)
    return min(new, damage * new * cls.repair_frac / TYPICAL_DAMAGE)
