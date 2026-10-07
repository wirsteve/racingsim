"""The player's race shop: the hauler, the shop, a fleet of cars and spare engines.

A racer who runs their own car owns more than the car. What they own decides what the car costs
to run and how fast it can be (data/rules/shop.json, prices in 2025 dollars):

* **the hauler**: from an open trailer behind the family pickup to a semi transporter. Bigger
  rigs cost more to tow and insure but carry spares (fewer small failures end a night), carry a
  backup car (a car wrecked in practice or the heat isn't the end of the night) and look good to
  sponsors;
* **the shop**: space (how many cars and spare engines you can keep), fabrication (cheaper crash
  repairs; build your own cars from a bare chassis), an engine room (cheaper, longer-lasting
  freshens; a dyno finds power in an open engine) and setup tools (scales, a shock dyno, data and
  simulation: setup speed, and more out of the driver's feedback);
* **the fleet**: the primary car (``Driver.car``), backups, cars being built, spare engines, and
  a used-car market that turns over every few weeks.

The researched season budgets the race night overhead comes from already include a typical
operation for the level (a local racer's open trailer, a touring racer's race trailer and shop);
the overhead is reduced by that typical upkeep and the player's own upkeep is charged instead,
so a bigger operation than the level needs costs more and a leaner one costs less.

Owner mode teams have their own facilities (``team_*`` functions): R&D, engineering, pit crew
training and transporters, priced as shares of the series' season cost.
"""

from __future__ import annotations

import copy
import random
import zlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Optional

from ..util import clamp, load_json
from . import car as C
from .classes import CarClass
from .fail import Fail

if TYPE_CHECKING:
    from ..world.entities import Driver, Team
    from ..world.world import World

FACILITIES = ("space", "fab", "engine", "setup")
TEAM_FACILITIES = ("rnd", "engineering", "pit", "transport")
SELL_BACK = 0.4          # share of a facility upgrade's price that comes back when it is sold off
HAULER_RESALE = 0.6      # of the price, less ~10% a season
PRACTICE_WRECK = 0.035   # chance a night's practice or heat race bends the car (average track, EST)
SELLERS = ("a racer moving up a class", "a racer getting out of the sport", "a builder's demo car",
           "an estate sale", "a racer's backup car", "a team clearing out the shop", "a weekend warrior")


@lru_cache(maxsize=1)
def data() -> dict:
    try:
        return load_json("rules/shop.json")
    except FileNotFoundError:
        return {"haulers": [], "facilities": {}, "team": {}, "build": {}, "market": {}}


def haulers() -> list[dict]:
    return data()["haulers"]


def hauler_opt(key: str) -> Optional[dict]:
    return next((h for h in haulers() if h["key"] == key), None)


@dataclass
class Operation:
    hauler: str = "open"
    hauler_age: int = 0
    levels: dict = field(default_factory=dict)      # facility -> level (0 = the basic one)
    backups: list = field(default_factory=list)     # Car: the rest of the fleet (the primary is Driver.car)
    engines: list = field(default_factory=list)     # spare engines: {"key", "q", "runs", "health"}
    projects: list = field(default_factory=list)    # builds: {"car", "ready_week", "year"}
    market: dict = field(default_factory=dict)      # {"stamp", "items"}
    seq: int = 0                                    # numbers used-car listings
    season: int = 0                                 # the last season the shop's upkeep was paid
    peak: float = 0.0                               # the highest upkeep level paid for this season
    capital: float = 0.0                            # the player's own savings put into the shop (come back in full)
    cars_named: int = 0                             # numbers the fleet's cars ("Car 3")


def get(world: "World") -> Operation:
    op = world.__dict__.get("shop")
    if op is None:
        op = world.__dict__["shop"] = Operation()
    return op


def level(op: Operation, fac: str) -> int:
    n = len(data()["facilities"].get(fac, {}).get("levels", [None]))
    return int(clamp(op.levels.get(fac, 0), 0, n - 1))


def fac(op: Operation, name: str) -> dict:
    return data()["facilities"][name]["levels"][level(op, name)]


def hauler(op: Operation) -> dict:
    return hauler_opt(op.hauler) or haulers()[0]


def _usd(world: "World", x: float) -> str:
    """Money in a message, in the season's own dollars (the model runs in 2025 dollars)."""
    from ..history.economy import price_index
    return f"${x * price_index(world.year):,.0f}"


def _buy(world: "World", d: "Driver", amount: float) -> bool:
    """Pay for shop capital: in season the racing account first, then savings; in the off-season savings, then
    next season's racing money. Savings that go into the shop are the player's own capital: selling it
    returns them in full."""
    from .garage import _pay
    if amount <= 0:
        return True
    before = d.savings
    if not _pay(d, amount):
        return False
    get(world).capital += max(0.0, before - d.savings)
    return True


def _proceeds(world: "World", d: "Driver", value: float) -> None:
    """Money from selling shop capital. The player's own capital comes back in full; the rest was the
    family's and sponsors' racing money: in season it goes back into the racing account, in the off-season
    the family keeps half (as close_account does with money left unspent)."""
    op = get(world)
    value = max(0.0, value)
    own = min(value, op.capital)
    op.capital -= own
    car = d.car
    if car is not None and car.account is not None:
        car.account += value
        car.drawn += own
    else:
        d.savings += own + 0.5 * (value - own)


def engine_value(opt, e: dict) -> float:
    """A spare engine on the used market: like an engine in a car (rules/car.py resale)."""
    if opt is None:
        return 0.0
    over = clamp((e["runs"] - opt.rebuild_races) / opt.rebuild_races, 0, 2) if opt.rebuild_races else 0.0
    return opt.usd * 0.55 * (0.3 + 0.7 * e["health"] / 100) * (1 - 0.3 * over / 2)


PRIVATE_SALE = 0.8       # of a car's market value a racer gets selling it themselves (the dealer's margin is the buyer's)


def in_season(world: "World") -> bool:
    return world.season is not None and not world.season.finished


def week(world: "World") -> int:
    return world.season.week if in_season(world) else 0


# ---------------------------------------------------------------------- effects on the car
def repair_mult(world: "World") -> float:
    return fac(get(world), "fab")["repair"]


def _open_engine(opt) -> bool:
    return opt is not None and not opt.sealed


def freshen_mult(world: "World", opt) -> float:
    return fac(get(world), "engine")["freshen"] if _open_engine(opt) else 1.0


def interval_mult(world: "World", opt) -> float:
    return fac(get(world), "engine")["interval"] if _open_engine(opt) else 1.0


def mech_mult(world: "World") -> float:
    return hauler(get(world))["mech"]


def travel_mult(world: "World") -> float:
    return hauler(get(world))["travel"]


def rating_bonus(world: "World", d: "Driver", cls: CarClass, track, car: Optional["C.Car"] = None) -> float:
    """Raw car points the shop adds: setup tools, dyno power in an open engine, shop-built shocks and
    more out of the driver's feedback."""
    op = get(world)
    car = car or d.car
    st, en = fac(op, "setup"), fac(op, "engine")
    wc, we, wt, ws = C.weights(track)
    tot = wc + we + wt + ws
    bonus = st["setup"] + (d.feedback - 50) * 0.10 * (st["feedback"] - 1)
    if car is not None and _open_engine(cls.engine(car.engine)):
        bonus += en["power"] * we / tot
    if cls.shocks:
        bonus += st["shocks"] * ws / tot
    return bonus


def sync(world: "World", d: "Driver", cls: Optional[CarClass]) -> None:
    """Name every car in the fleet and keep the engine room's freshen interval on them."""
    op = get(world)
    for car in fleet(world, d):
        if not car.tag:
            car.tag = _tag(op)
        if cls is not None:
            car.interval_mult = interval_mult(world, cls.engine(car.engine))


def fleet(world: "World", d: "Driver") -> list:
    return ([d.car] if d.car is not None else []) + list(get(world).backups)


def capacity(world: "World") -> tuple[int, int]:
    """(cars, spare engines) the shop has room for."""
    sp = fac(get(world), "space")
    return sp["cars"], sp["engines"]


def cars_kept(world: "World", d: "Driver") -> int:
    op = get(world)
    return len(fleet(world, d)) + len(op.projects)


# ---------------------------------------------------------------------- money
def upkeep(op: Operation) -> float:
    """A season of insurance, registration and tires on the rig, shop rent and utilities."""
    return hauler(op)["upkeep"] + sum(fac(op, f)["upkeep"] for f in FACILITIES)


def typical(season_cost: float) -> Operation:
    """The operation a typical racer at this budget runs (what the researched season budgets include)."""
    if season_cost < 15_000:
        return Operation(hauler="open")
    if season_cost < 60_000:
        return Operation(hauler="enclosed", levels={"fab": 1, "setup": 1})
    if season_cost < 200_000:
        return Operation(hauler="race_trailer", levels={"space": 1, "fab": 1, "engine": 1, "setup": 1})
    return Operation(hauler="stacker", levels={"space": 2, "fab": 2, "engine": 1, "setup": 2})


def overhead(world: "World", template, base: float) -> float:
    """Tonight's crew, practice and spares cost with the typical operation's upkeep taken out (the
    player pays their own at the start of the season)."""
    if get(world).season != world.year:      # nothing paid for this season (an old save loaded mid-season)
        return base
    events = max(1, template.events)
    return max(0.4 * base, base - upkeep(typical(template.season_cost)) / events)


def season_upkeep(world: "World", template, base: float) -> float:
    """What the player pays at the start of the season for their own rig and shop, over the typical
    operation the season budget already includes: whatever of the typical upkeep came out of the race
    nights' overhead, plus anything bigger than typical. (Where the class's own costs already eat the
    whole researched budget the typical part can't be taken out of the overhead: then it is netted
    off here instead.)"""
    events = max(1, template.events)
    t = upkeep(typical(template.season_cost))
    removed = max(0.4 * base, base - t / events)
    removed = (base - removed) * events
    return max(0.0, upkeep(get(world)) - (t - removed))


def season_start(world: "World", d: "Driver", cls: Optional[CarClass], template, pay) -> None:
    """Once a season, at the first look at the account: the cars and the rig age a year, the
    upkeep is paid and builds finished over the winter roll out. (``cls`` None: the player isn't racing
    their own car this season, and the shop's upkeep is paid in full.)"""
    op = get(world)
    if op.season == world.year:
        return
    first = op.season == 0
    op.season = world.year
    aging = fac(op, "fab").get("aging", 1.0)
    for car in fleet(world, d):
        if car.season_seen and car.season_seen < world.year:
            car.chassis_age += (world.year - car.season_seen) * aging
        car.season_seen = world.year
    if not first:
        op.hauler_age += 1
    tick(world, d)
    op.peak = upkeep(op)
    cost = season_upkeep(world, template, C.overhead_per_night(cls, template)) if cls is not None else upkeep(op)
    if cost >= 1:
        pay(cost, f"Shop & hauler for the season: {hauler(op)['label'].lower()}, {fac(op, 'space')['label'].lower()} "
                  "(rent, insurance, tags, upkeep)")


def sponsor_bonus(world: "World", d: "Driver") -> float:
    """Extra sponsor money a better-looking rig brings in."""
    return hauler(get(world))["sponsor"] * d.sponsor_money()


# ---------------------------------------------------------------------- race night
def practice(world: "World", d: "Driver", cls: CarClass, track, wk: int, scale: float = 1.0) -> Optional[str]:
    """Practice and heats can bend a car before the feature. With a backup in the hauler you roll it out;
    without one the crew bolts the damaged car back together. Returns a note, or None."""
    rng = world.rng
    sev = track.sim.crash_severity if track is not None else 50
    if d.car is None or rng.random() >= PRACTICE_WRECK * scale * (0.6 + 0.8 * sev / 100):
        return None
    from .garage import log
    dmg = C.crash_damage(rng, sev) * 0.7
    d.car.condition = clamp(d.car.condition - dmg * 100, 0, 100)
    op = get(world)
    spare = _best_backup(world, d, cls)
    if spare is not None and C.rating(spare, cls, track, d.feedback) <= C.rating(d.car, cls, track, d.feedback):
        spare = None                             # the bent primary is still the better car
    if spare is not None and hauler(op)["cars"] >= 2:
        idx = op.backups.index(spare)
        make_primary(world, d, idx)
        log(d.car, wk, f"{track.name}: wrecked in practice, rolled out the backup car", 0)
        return "Wrecked in practice: you rolled out the backup car from the hauler."
    log(d.car, wk, f"{track.name}: wrecked in practice, patched up for the feature", 0)
    return ("Wrecked in practice: the crew patched the car up for the feature"
            + (" (a stacker or semi could have brought the backup car)." if spare is not None else "."))


def _best_backup(world: "World", d: "Driver", cls: CarClass):
    ok = [c for c in get(world).backups if c.cls == cls.key and c.engine_health > 0 and c.condition >= 60]
    return max(ok, key=lambda c: C.rating(c, cls, None, d.feedback), default=None)


def ready_car(world: "World", d: "Driver", cls: CarClass) -> Optional[str]:
    """Before a race night: a car that can't race (blown engine, wrecked) is swapped for the best backup."""
    car = d.car
    if car is None or (car.cls == cls.key and car.engine_health > 0 and car.condition >= 40):
        return None
    spare = _best_backup(world, d, cls)
    if spare is None:
        return None
    make_primary(world, d, get(world).backups.index(spare))
    return f"Your primary car can't race: {d.car.tag or 'the backup'} takes its place."


def tick(world: "World", d: "Driver") -> list[str]:
    """Builds that are finished join the fleet."""
    op = get(world)
    done, notes = [], []
    for p in op.projects:
        if not in_season(world) or p["year"] < world.year or week(world) >= p["ready_week"]:
            done.append(p)
    for p in done:
        op.projects.remove(p)
        car = p["car"]
        _stamp(world, car)
        if d.car is None or d.car.cls != car.cls:
            _swap_in(world, d, car)
        else:
            op.backups.append(car)
        notes.append(f"{car.tag} is finished and ready to race.")
        from .garage import all_class
        sync(world, d, all_class(car.cls))
        world.post("player", f"Your new build ({car.tag}) is finished", driver_id=d.id, importance=1)
    return notes


# ---------------------------------------------------------------------- fleet moves
def _stamp(world: "World", car: "C.Car") -> None:
    """The season a car joins the fleet (bought in the off-season it counts from next season)."""
    if not car.season_seen:
        car.season_seen = world.year if in_season(world) else world.year + 1


def _tag(op: Operation) -> str:
    op.cars_named += 1
    return f"Car {op.cars_named}"


BOOKS = ("account", "ledger", "winnings", "drawn", "races", "auto_rebuild", "auto_repair", "reserve", "year",
         "new_tires")


def _move_books(src: "C.Car", dst: "C.Car") -> None:
    for attr in BOOKS:
        setattr(dst, attr, getattr(src, attr))
    src.account, src.ledger, src.winnings, src.drawn, src.races = None, [], 0.0, 0.0, 0


def _swap_in(world: "World", d: "Driver", car: "C.Car") -> None:
    """``car`` becomes the primary; the old primary goes into the fleet (or is sold if it's for another class)."""
    from .garage import all_class
    old = d.car
    d.car = car
    if old is None:
        return
    _move_books(old, car)
    if old.cls == car.cls:
        get(world).backups.append(old)
        return
    oc = all_class(old.cls)
    _proceeds(world, d, PRIVATE_SALE * C.resale(old, oc) if oc else 0.0)


def clear_other_classes(world: "World", d: "Driver", cls: CarClass) -> None:
    """Moving to a new class: backups, builds and spare engines that don't fit it are sold."""
    from .garage import all_class
    op = get(world)
    value = 0.0
    for car in list(op.backups) + [p["car"] for p in op.projects]:
        if car.cls != cls.key:
            oc = all_class(car.cls)
            value += C.resale(car, oc) if oc else 0.0
    op.backups = [c for c in op.backups if c.cls == cls.key]
    op.projects = [p for p in op.projects if p["car"].cls == cls.key]
    keep = []
    for e in op.engines:
        if cls.engine(e["key"]) is not None:
            keep.append(e)
            continue
        oc = next((c for c in (all_class(k) for k in _classes()) if c and c.engine(e["key"])), None)
        value += engine_value(oc.engine(e["key"]) if oc else None, e)
    op.engines = keep
    op.market = {}
    if value >= 1:
        d.savings += value
        d.log(world.year, f"sold the old class's spare cars and engines for {_usd(world, value)}")


def _classes():
    from .classes import all_classes
    return all_classes()


def make_primary(world: "World", d: "Driver", idx: int) -> str:
    op = get(world)
    if not 0 <= idx < len(op.backups):
        return Fail("No such car.")
    car = op.backups.pop(idx)
    old = d.car
    if old is not None:
        _move_books(old, car)
        op.backups.insert(idx, old)
    d.car = car
    return f"{car.tag or 'That car'} is your primary car now."


# ---------------------------------------------------------------------- used market
def market(world: "World", d: "Driver", cls: CarClass) -> list[dict]:
    op = get(world)
    m = data()["market"]
    period = week(world) // max(1, m.get("refresh_weeks", 4)) if in_season(world) else -1
    stamp = [cls.key, world.year, period]
    if op.market.get("stamp") != stamp:
        rng = random.Random(zlib.crc32(f"{world.config.seed}|{cls.key}|{world.year}|{period}".encode()))
        op.market = {"stamp": stamp, "items": [_listing(world, op, cls, rng) for _ in range(m.get("listings", 6))]}
    return op.market["items"]


def _listing(world: "World", op: Operation, cls: CarClass, rng: random.Random) -> dict:
    ch = rng.choice(cls.chassis)
    en = rng.choice(cls.engines_in(world.year))
    sh = rng.choice(cls.shocks) if cls.shocks else C.Option("stock", "Stock", 0, 50)
    car = C.build(cls, ch, en, sh, cls.tires.typical_new)
    car.chassis_age = ch.age + rng.randint(1, 6)
    car.condition = round(rng.uniform(55, 98))
    car.engine_runs = rng.randint(0, int((en.rebuild_races or 10) * 1.3))
    car.engine_health = round(rng.uniform(55, 100))
    car.tire_wear = round(rng.uniform(0.3, 0.8), 2)
    lo, hi = data()["market"].get("markup", [0.8, 1.3])
    price = round(C.resale(car, cls) * rng.uniform(lo, hi), -2)
    op.seq += 1
    return {"id": op.seq, "car": car, "price": max(100.0, price), "seller": rng.choice(SELLERS),
            "noise": [rng.gauss(0, 1), rng.gauss(0, 1)]}


def shown(world: "World", item: dict) -> dict:
    """What you can tell about a used car: with a chassis jig you can measure it, otherwise it's the seller's word."""
    sd = fac(get(world), "fab")["inspect"]
    car = item["car"]
    return {"condition": int(clamp(round(car.condition + item["noise"][0] * sd), 20, 100)),
            "engine_health": int(clamp(round(car.engine_health + item["noise"][1] * sd * 1.5), 10, 100)),
            "spread": sd}


# ---------------------------------------------------------------------- actions
def shop_action(world: "World", d: "Driver", action: str, key: Optional[str] = None) -> str:
    from . import garage as G
    op = get(world)
    if action.startswith("team_"):
        return team_action(world, d, action, key)
    if action == "hauler":
        h = hauler_opt(key or "")
        if h is None:
            return Fail("Unknown hauler.")
        if h["key"] == op.hauler:
            return Fail("That's the rig you have.")
        cur = hauler(op)
        trade = hauler_trade(op)
        if trade >= h["usd"]:
            _proceeds(world, d, trade - h["usd"])
        elif not _buy(world, d, h["usd"] - trade):
            return Fail(f"The {h['label'].lower()} costs {_usd(world, h['usd'])} (your {cur['label'].lower()} fetches {_usd(world, trade)}).")
        before = upkeep(op)
        op.hauler, op.hauler_age = h["key"], 0 if in_season(world) else -1   # off-season: new for next season
        _ledger(world, d, f"Hauler: {h['label']} (sold the {cur['label'].lower()} for {_usd(world, trade)})", -(h["usd"] - trade))
        _prorate(world, d, before)
        return f"Your rig is now the {h['label'].lower()}."
    if action in ("upgrade", "downgrade"):
        if key not in FACILITIES:
            return Fail("Unknown facility.")
        levels = data()["facilities"][key]["levels"]
        lv = level(op, key)
        if action == "upgrade":
            if lv + 1 >= len(levels):
                return Fail(f"Your {data()['facilities'][key]['label'].lower()} is as good as it gets.")
            nxt = levels[lv + 1]
            if not _buy(world, d, nxt["usd"]):
                return Fail(f"{nxt['label']} costs {_usd(world, nxt['usd'])} - more than you have.")
            before = upkeep(op)
            op.levels[key] = lv + 1
            _ledger(world, d, f"Shop: {nxt['label']}", -nxt["usd"])
            _prorate(world, d, before)
            sync(world, d, G.target_class(world, d))
            return f"New in the shop: {nxt['label'].lower()}."
        if lv == 0:
            return Fail("Nothing to sell off.")
        if key == "space" and cars_kept(world, d) > levels[lv - 1]["cars"]:
            return Fail(f"The {levels[lv - 1]['label'].lower()} only holds {levels[lv - 1]['cars']} cars: sell some first.")
        if key == "space" and len(op.engines) > levels[lv - 1]["engines"]:
            return Fail("Sell some spare engines first.")
        back = SELL_BACK * levels[lv]["usd"]
        _proceeds(world, d, back)
        op.levels[key] = lv - 1
        _ledger(world, d, f"Sold off: {levels[lv]['label']}", back)
        sync(world, d, G.target_class(world, d))
        return f"Sold off the {levels[lv]['label'].lower()} for {_usd(world, back)}."
    cls = G.target_class(world, d)
    if cls is None:
        return Fail("You don't run your own car in a class with a garage.")
    cars, engines = capacity(world)
    if action == "buy_used":
        item = next((x for x in market(world, d, cls) if str(x["id"]) == str(key)), None)
        if item is None:
            return Fail("That car has been sold.")
        replace = d.car is None or d.car.cls != cls.key
        if not replace and cars_kept(world, d) >= cars:
            return Fail(f"No room in the shop: your {fac(op, 'space')['label'].lower()} holds {cars} cars.")
        if not _buy(world, d, item["price"]):
            return Fail(f"The seller wants {_usd(world, item['price'])} - more than you have.")
        car = item["car"]
        car.tag = _tag(op)
        _stamp(world, car)
        op.market["items"].remove(item)
        if replace:
            _swap_in(world, d, car)
        else:
            op.backups.append(car)
        sync(world, d, cls)
        _ledger(world, d, f"Bought a used car ({car.tag}) from {item['seller']}", -item["price"])
        return f"Bought {car.tag}" + (" - it's your race car now." if replace else " - it's in the shop as a backup.")
    if action == "build":
        fb = fac(op, "fab")
        if fb.get("build") is None:
            return Fail("You need at least a welder and a tube bender to build a car.")
        parts = (key or "").split("|")
        if len(parts) != 3:
            return Fail("Pick a chassis, an engine and shocks.")
        ch = cls.chassis_opt(parts[0])
        sh = cls.shock(parts[2]) if cls.shocks else C.Option("stock", "Stock", 0, 50)
        spare = None
        if parts[1].startswith("spare:"):
            i = int(parts[1][6:]) if parts[1][6:].isdigit() else -1
            spare = op.engines[i] if 0 <= i < len(op.engines) else None
            en = cls.engine(spare["key"]) if spare else None
        else:
            en = cls.engine(parts[1])
        if ch is None or en is None or sh is None:
            return Fail("Pick a chassis, an engine and shocks.")
        if spare is None and not en.available(world.year):
            return Fail(f"{en.label} isn't legal in {world.year}.")
        if cars_kept(world, d) >= cars and d.car is not None and d.car.cls == cls.key:
            return Fail(f"No room in the shop for another car: your {fac(op, 'space')['label'].lower()} holds {cars}.")
        kit = data()["build"].get("kit_share", 0.8) * ch.usd
        price = kit + (0 if spare else en.usd) + sh.usd
        if not _buy(world, d, price):
            return Fail(f"The build needs {_usd(world, price)} in parts - more than you have.")
        car = C.build(cls, ch, en, sh, d.car.new_tires if d.car else cls.tires.typical_new)
        car.chassis_q = clamp(ch.quality + fb["build"], 0, 100)
        if spare is not None:
            op.engines.remove(spare)
            car.engine_q, car.engine_runs, car.engine_health = spare["q"], spare["runs"], spare["health"]
        car.tag = _tag(op)
        wk = week(world)
        op.projects.append({"car": car, "ready_week": wk + fb["build_weeks"], "year": world.year})
        _ledger(world, d, f"Build: {ch.label} kit for {car.tag}" + ("" if spare else f", {en.label}"), -price)
        when = f"in about {fb['build_weeks']} weeks" if in_season(world) else "over the winter"
        notes = tick(world, d)
        sync(world, d, cls)
        return f"{car.tag} goes on the jig: ready {when}." + (" " + " ".join(notes) if notes else "")
    if action == "primary":
        i = _int(key)
        if 0 <= i < len(op.backups) and op.backups[i].cls != cls.key:
            return Fail(f"That car isn't a {cls.label.lower()}.")
        msg = make_primary(world, d, i)
        sync(world, d, cls)
        return msg
    if action == "sell_car":
        i = _int(key)
        if not 0 <= i < len(op.backups):
            return Fail("No such car.")
        car = op.backups.pop(i)
        oc = G.all_class(car.cls)
        value = PRIVATE_SALE * C.resale(car, oc) if oc else 0.0
        _proceeds(world, d, value)
        _ledger(world, d, f"Sold {car.tag or 'a backup car'}", value)
        return f"Sold {car.tag or 'the car'} for {_usd(world, value)}."
    if action == "buy_engine":
        en = cls.engine(key or "")
        if en is None or not en.available(world.year):
            return Fail("That engine isn't legal this season.")
        if len(op.engines) >= engines:
            return Fail(f"No room for another spare engine (your shop keeps {engines}).")
        if not _buy(world, d, en.usd):
            return Fail(f"A {en.label} costs {_usd(world, en.usd)} - more than you have.")
        op.engines.append({"key": en.key, "q": en.quality, "runs": 0, "health": 100.0})
        _ledger(world, d, f"Spare engine: {en.label}", -en.usd)
        return f"A fresh {en.label} goes on the engine stand."
    if action in ("swap_engine", "sell_engine", "freshen_engine"):
        i = _int(key)
        if not 0 <= i < len(op.engines):
            return Fail("No such engine.")
        e = op.engines[i]
        opt = cls.engine(e["key"])
        if action == "sell_engine":
            value = engine_value(opt, e)
            op.engines.pop(i)
            _proceeds(world, d, value)
            _ledger(world, d, f"Sold a spare {opt.label if opt else 'engine'}", value)
            return f"Sold the spare engine for {_usd(world, value)}."
        if action == "freshen_engine":
            if opt is None:
                return Fail("Unknown engine.")
            cost = freshen_cost(world, opt, e["health"])
            if not _buy(world, d, cost):
                return Fail(f"A freshen costs {_usd(world, cost)} - more than you have.")
            e["runs"], e["health"] = 0, 100.0
            _ledger(world, d, f"Spare engine freshened ({opt.label})", -cost)
            return f"The spare {opt.label} is fresh ({_usd(world, cost)})."
        car = d.car
        if car is None or car.cls != cls.key:
            return Fail("You need a car to put it in.")
        old = {"key": car.engine, "q": car.engine_q, "runs": car.engine_runs, "health": car.engine_health}
        car.engine, car.engine_q, car.engine_runs, car.engine_health = e["key"], e["q"], e["runs"], e["health"]
        op.engines[i] = old
        sync(world, d, cls)
        _ledger(world, d, f"Engine swap: {opt.label if opt else e['key']} in, old engine on the stand", 0)
        return f"The {opt.label if opt else 'spare'} is in the car; the old engine is on the stand."
    return Fail("Unknown shop action.")


def _prorate(world: "World", d: "Driver", before: float) -> None:
    """A bigger rig or shop bought mid-season: the rest of this season's extra upkeep is paid now (over the
    most already paid for this season, so selling off and buying back doesn't pay twice)."""
    from ..sim.season import SEASON_WEEKS, charge
    from .garage import spend
    op = get(world)
    paid = max(before, op.peak) if op.season == world.year else before
    extra = (upkeep(op) - paid) * max(0, SEASON_WEEKS - week(world)) / SEASON_WEEKS
    if not in_season(world) or extra < 1 or d.car is None:
        return
    op.peak = upkeep(op)
    if not spend(d, extra):
        charge(d, extra)
    _ledger(world, d, "Upkeep for the rest of the season", -extra)


def _int(key) -> int:
    try:
        return int(key)
    except (TypeError, ValueError):
        return -1


def freshen_cost(world: "World", opt, health: float) -> float:
    cost = opt.rebuild_usd * (1 + (100 - health) / 70) * freshen_mult(world, opt)
    if health <= 0:
        cost = max(cost, opt.usd * 0.6)
    return cost


def hauler_trade(op: Operation) -> float:
    return hauler(op)["usd"] * HAULER_RESALE * 0.9 ** max(0, op.hauler_age)


def _ledger(world: "World", d: "Driver", text: str, amount: float) -> None:
    from .garage import log
    if d.car is not None:
        if d.car.account is None:
            d.car.year = world.year
        log(d.car, week(world), text, amount)


# ---------------------------------------------------------------------- owner mode: the team's facilities
def team_level(t: "Team", key: str) -> int:
    return int(clamp((getattr(t, "facilities", None) or {}).get(key, 0), 0, 3))


def team_cost_base(world: "World", t: "Team") -> float:
    return world.series(t.series_id).template.season_cost * max(1, t.cars)


def team_upkeep(world: "World", t: "Team") -> float:
    spec = data()["team"]
    return sum(spec[k]["upkeep"] * team_level(t, k) for k in TEAM_FACILITIES) * team_cost_base(world, t)


def team_value(world: "World", t: "Team") -> float:
    """What the facilities would fetch if the team is sold."""
    spec = data()["team"]
    base = team_cost_base(world, t)
    return SELL_BACK * sum(sum(spec[k]["price"][:team_level(t, k)]) for k in TEAM_FACILITIES) * base


def team_equipment(t: "Team") -> float:
    return data()["team"]["rnd"]["equipment"] * team_level(t, "rnd")


def team_sponsor(t: "Team") -> float:
    return 1 + data()["team"]["transport"]["sponsor"] * team_level(t, "transport")


def team_crew(t: "Team", eff: dict) -> None:
    """Race-day effects of the team's facilities on a crew-effects dict (staff.effects)."""
    spec = data()["team"]
    eff["setup_mean"] += spec["engineering"]["setup"] * team_level(t, "engineering")
    eff["pit_s"] *= 1 - spec["pit"]["pit"] * team_level(t, "pit")
    eff["pit_sd"] *= 1 - 1.5 * spec["pit"]["pit"] * team_level(t, "pit")
    eff["mech"] *= 1 - spec["transport"]["mech"] * team_level(t, "transport")


def team_action(world: "World", d: "Driver", action: str, key: Optional[str]) -> str:
    from ..game.owner import owned
    t = owned(world)
    if t is None:
        return Fail("You don't own a team.")
    if action != "team_upgrade" or key not in TEAM_FACILITIES:
        return Fail("Unknown team action.")
    spec = data()["team"][key]
    lv = team_level(t, key)
    if lv >= 3:
        return Fail(f"{t.name}'s {spec['label'].lower()} is as good as it gets.")
    price = spec["price"][lv] * team_cost_base(world, t)
    have = max(0.0, t.cash) + max(0.0, d.savings)
    if price > have:
        return Fail(f"That costs {_usd(world, price)}: the team has {_usd(world, max(0.0, t.cash))} and you have {_usd(world, d.savings)}.")
    from_team = min(max(0.0, t.cash), price)
    t.cash -= from_team
    d.savings -= price - from_team
    if not isinstance(getattr(t, "facilities", None), dict):
        t.facilities = {}
    t.facilities[key] = lv + 1
    world.post("player", f"{t.name} invests {_usd(world, price)} in {spec['label'].lower()} (level {lv + 1})",
               driver_id=d.id, importance=1)
    return f"{t.name}: {spec['label'].lower()} up to level {lv + 1} ({_usd(world, price)})."
