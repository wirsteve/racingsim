"""Running a car through a season: pre-season prep, race nights, wrecks, rebuilds.

The season runner calls into here for every racer who runs their own car in a
class with researched rules. AI racers are handled in steady state (one rating
per season, refreshed after wrecks and engine failures); the player's car is
run race by race with a money ledger, so tires, freshen-ups, entry fees, wrecks
and purses all land in their racing account as they happen.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from ..util import clamp
from . import car as C
from . import shop as SH
from .classes import CarClass, class_for_template

if TYPE_CHECKING:
    from ..world.entities import Driver
    from ..world.series import Series
    from ..world.world import World


def class_of(series: "Series") -> Optional[CarClass]:
    if series is None or series.template.team_based:
        return None
    return class_for_template(series.template.key)


def home_track(world: "World", series: "Series"):
    if series.scope == "track" and series.schedule:
        return world.tracks.get(series.schedule[0])
    return None


# ---------------------------------------------------------------------- pre-season
def prepare(world: "World", d: "Driver", series: "Series", cls: CarClass, funds: float, cost: float) -> float:
    """Ready the car for the season; returns the season equipment rating (AI) / opening rating (player)."""
    ratio = funds / cost if cost > 0 else 1.0
    rng = world.rng
    if d.is_player:
        open_account(world, d, series, cls)
        return player_rating(world, d, cls, home_track(world, series))
    old = d.car if d.car is not None and d.car.cls == cls.key else None
    d.car = C.ai_car(cls, world.year, ratio, rng, old)
    d.car.reserve = max(0.0, funds - cost) * 0.8 + cost * 0.05
    return ai_rating(world, d, series, cls)


def ai_rating(world: "World", d: "Driver", series: "Series", cls: CarClass) -> float:
    track = home_track(world, series)
    wear = C.steady_wear(cls, d.car.new_tires, track)
    return C.rating(d.car, cls, track, d.feedback, tire_wear=wear)


def open_account(world: "World", d: "Driver", series: "Series", cls: CarClass) -> None:
    """The player's racing account for the season: what the family, sponsors and savings put in."""
    if d.car is None or d.car.cls != cls.key:
        starter_car(world, d, cls)
    car = d.car
    car.year = world.year
    if car.account is None:
        draw = max(0.0, d.savings) * 0.25          # the share of savings available_funding counts
        car.account = d.available_funding()
        d.savings -= draw                           # ... really leaves the bank
        car.drawn = draw
        car.winnings = 0.0
        log(car, 0, f"{world.year} season budget ({series.name})", car.account)
        bonus = SH.sponsor_bonus(world, d)
        if bonus >= 1:
            car.account += bonus
            log(car, 0, f"Sponsors like the {SH.hauler(SH.get(world))['label'].lower()}", bonus)
    car.races = 0

    def pay(amount: float, text: str) -> None:
        if not spend(d, amount):
            from ..sim.season import charge
            charge(d, amount)
        log(d.car, 0, text, -amount)
    SH.season_start(world, d, cls, series.template, pay)
    SH.sync(world, d, cls)


def starter_car(world: "World", d: "Driver", cls: CarClass) -> None:
    """No car for this class: sell the old one and buy the best sensible package the money allows."""
    from ..sim.season import charge
    if d.car is not None:
        old_cls = all_class(d.car.cls)
        if old_cls is not None:
            value = C.resale(d.car, old_cls)
            d.savings += value
            d.log(world.year, f"sold the {old_cls.label.lower()} for ${value:,.0f}")
    SH.clear_other_classes(world, d, cls)
    money = d.available_funding() + d.savings * 0.5
    # Keep about half the money for running the season.
    budget = money * 0.5
    ch = C.by_budget(cls.chassis, budget * 0.55)
    en = C.by_budget(cls.engines_in(world.year), budget * 0.35)
    sh = C.by_budget(cls.shocks, budget * 0.10) if cls.shocks else C.Option("stock", "Stock", 0, 50)
    d.car = C.build(cls, ch, en, sh, cls.tires.typical_new)
    d.car.year = world.year
    price = ch.usd + en.usd + sh.usd
    charge(d, price)
    log(d.car, 0, f"Bought {ch.label.lower()}, {en.label}, {sh.label.lower()} shocks", -price)


def all_class(key: str) -> Optional[CarClass]:
    from .classes import all_classes
    return all_classes().get(key)


def player_rating(world: "World", d: "Driver", cls: CarClass, track) -> float:
    return C.rating(d.car, cls, track, d.feedback, bonus=SH.rating_bonus(world, d, cls, track))


def log(car: "C.Car", week: int, text: str, amount: float) -> None:
    car.ledger.append([week, text, round(amount), car.year])
    if len(car.ledger) > 400:
        del car.ledger[:100]


def spend(d: "Driver", amount: float) -> bool:
    """Take money from the racing account, then savings. False if there isn't enough."""
    car = d.car
    have = (car.account or 0.0) + d.savings
    if amount > have + 1e-6:
        return False
    take = min(amount, max(car.account or 0.0, 0.0))
    car.account = (car.account or 0.0) - take
    d.savings -= amount - take
    return True


# ---------------------------------------------------------------------- race night (player)
def can_race(d: "Driver", cls: CarClass, travel: float = 0.0) -> bool:
    """``travel``: tonight's tow money (already scaled by the hauler, see travel_per_night)."""
    car = d.car
    return (car is not None and car.engine_health > 0
            and (car.account or 0.0) + d.savings >= cls.per_race_fixed() + travel)


def before_race(world: "World", d: "Driver", cls: CarClass, track, week: int, travel: float,
                overhead: float = 0.0) -> float:
    """Pay to race tonight, bolt on new tires; returns the car's rating at this track.

    ``overhead`` is the programme's crew, hauler, practice and spares cost per night; it is
    skipped first when money is short (you can always show up with fewer spares)."""
    from ..world import settings as ST
    note = SH.practice(world, d, cls, track, week, ST.get(world, "crashes"))
    if note:
        world.post("player", note, driver_id=d.id, week=week, importance=2)
    car = d.car
    n = min(car.new_tires, C.max_new(cls))
    have = (car.account or 0) + d.savings
    base = cls.per_race_fixed() + travel
    while n > 0 and have < base + n * cls.tires.usd:
        n -= 1
    over = clamp(have - base - n * cls.tires.usd, 0, overhead)
    cost = base + n * cls.tires.usd
    if not spend(d, cost + over):     # can_race() guarantees the base; never race for free
        over = 0.0
        if not spend(d, cost):
            cost = 0.0
            n = 0
    C.fit_tires(car, n)
    log(car, week, f"{track.name}: entry, pit passes, fuel{', travel' if travel else ''}"
        + (f", {n} new tire{'s' if n > 1 else ''}" if n else ", no new tires"), -cost)
    if over:
        log(car, week, "Crew, practice tires, spares & food", -over)
    return player_rating(world, d, cls, track)


def after_race(world: "World", d: "Driver", cls: CarClass, track, week: int, finish, purse: float) -> list[str]:
    """Wear, damage, rebuilds and the purse. Returns notes for the race report."""
    rng = world.rng
    car = d.car
    notes = []
    car.races += 1
    car.engine_runs += 1
    car.tire_wear = clamp(car.tire_wear + C.wear_per_race(cls, track), 0, 1)
    if purse:
        car.account = (car.account or 0.0) + purse
        car.winnings += purse
        log(car, week, f"Purse, P{finish.position}", purse)
    if finish.crashed:
        dmg = C.crash_damage(rng, track.sim.crash_severity)
        car.condition = clamp(car.condition - dmg * 100, 0, 100)
        cost = C.repair_cost(cls, dmg) * SH.repair_mult(world)
        notes.append(f"Wrecked: about ${cost:,.0f} of damage")
        if car.auto_repair:
            msg = repair(world, d, cls, week)
            if "don't have" in msg:
                notes.append(msg)
    elif finish.dnf:
        hit = rng.uniform(25, 110)
        car.engine_health = clamp(car.engine_health - hit, 0, 100)
        notes.append("Engine let go" if car.engine_health <= 0 else "Mechanical failure: engine damaged")
        if car.auto_rebuild:
            msg = rebuild(world, d, cls, week)
            if "don't have" in msg:
                notes.append(msg)
    opt = cls.engine(car.engine)
    if (car.auto_rebuild and opt and opt.rebuild_races and car.engine_runs >= opt.rebuild_races * car.interval_mult
            and car.engine_health > 0):
        msg = rebuild(world, d, cls, week)
        if "don't have" in msg:
            notes.append(msg)
    return notes


def repair(world: "World", d: "Driver", cls: CarClass, week: int) -> str:
    car = d.car
    dmg = (100 - car.condition) / 100
    if dmg <= 0.005:
        return "The car is straight."
    cost = C.repair_cost(cls, dmg) * SH.repair_mult(world)
    if not spend(d, cost):
        return f"Repairs need ${cost:,.0f} - you don't have it."
    car.condition = 100.0
    log(car, week, "Crash repairs", -cost)
    return f"Repaired for ${cost:,.0f}."


def rebuild(world: "World", d: "Driver", cls: CarClass, week: int) -> str:
    car = d.car
    opt = cls.engine(car.engine)
    if opt is None:
        return "Unknown engine."
    blown = car.engine_health <= 0
    cost = SH.freshen_cost(world, opt, car.engine_health)
    if not spend(d, cost):
        return f"A {'rebuild' if not blown else 'replacement short block'} costs ${cost:,.0f} - you don't have it."
    car.engine_runs, car.engine_health = 0, 100.0
    log(car, week, ("Engine rebuilt after failure" if blown else "Engine freshened") + f" ({opt.label})", -cost)
    return f"Engine {'rebuilt' if blown else 'freshened'} for ${cost:,.0f}."


def close_account(world: "World", d: "Driver") -> None:
    """Season over: winnings left in the account are the driver's; of the family's money left
    unspent, half goes into the driver's racing savings (the family keeps the rest)."""
    car = d.car
    if car is None or car.account is None:
        return
    left = car.account
    own = car.winnings + car.drawn     # winnings and the savings put in come back in full
    keep = min(max(left, 0.0), own) + 0.5 * max(0.0, left - own)
    d.savings = max(0.0, d.savings + (keep if left >= 0 else left))
    log(car, 99, "Season closed: banked", keep if left >= 0 else left)
    car.account = None
    car.winnings = 0.0
    car.drawn = 0.0


# ---------------------------------------------------------------------- AI wrecks
def ai_wreck(world: "World", d: "Driver", series: "Series", cls: CarClass, crashed: bool) -> Optional[float]:
    """AI racer's car after a wreck or failure: fix it from the season reserve if possible.
    Returns the new equipment rating, or None if unchanged."""
    rng = world.rng
    car = d.car
    if crashed:
        dmg = C.crash_damage(rng, 50)
        cost = C.repair_cost(cls, dmg)
        if car.reserve >= cost:
            car.reserve -= cost
            return None
        car.condition = clamp(car.condition - dmg * 100 * (1 - car.reserve / max(cost, 1)), 0, 100)
        car.reserve = 0.0
    else:
        hit = rng.uniform(25, 110)
        opt = cls.engine(car.engine)
        cost = (opt.rebuild_usd if opt else 2000) * (1 + hit / 70)
        if car.reserve >= cost:
            car.reserve -= cost
            return None
        car.engine_health = clamp(car.engine_health - hit, 5, 100)
        car.reserve = 0.0
    return ai_rating(world, d, series, cls)


def travel_per_night(world: "World", d: "Driver", series: "Series") -> float:
    """Tow money the player spends per night (the market's season travel estimate spread over the events)."""
    from ..career.market import season_cost_for
    events = max(1, series.template.events if series.scope == "track" else len(series.schedule))
    total = season_cost_for(world, d, series) - series.template.season_cost
    return max(0.0, total) / events * SH.travel_mult(world)


def claim_check(world: "World", d: "Driver", cls: CarClass, finish, week: int) -> Optional[str]:
    """Claim rules: a rival can buy a top finisher's engine for the claim price after the feature."""
    car = d.car
    opt = cls.engine(car.engine)
    if opt is None or not opt.claim_usd or finish.position > 5 or finish.dnf:
        return None
    # An engine worth far more than the claim price is a target.
    worth = opt.usd * (0.4 + 0.6 * car.engine_health / 100)
    if worth <= opt.claim_usd * 1.1:
        return None
    if world.rng.random() >= 0.08 * math.log2(worth / opt.claim_usd + 1):
        return None
    car.account = (car.account or 0.0) + opt.claim_usd
    car.winnings += opt.claim_usd
    log(car, week, f"Engine claimed after the feature ({opt.label})", opt.claim_usd)
    spare = min(cls.engines_in(world.year), key=lambda e: e.usd)
    car.engine, car.engine_q, car.engine_runs, car.engine_health = spare.key, spare.quality * 0.92, 0, 85.0
    return (f"Your engine was claimed for ${opt.claim_usd:,.0f}. You bolt in a tired spare "
            f"{spare.label.lower()} - buy a fresh engine in the garage.")


# ---------------------------------------------------------------------- player garage actions
def target_class(world: "World", d: "Driver") -> Optional[CarClass]:
    """The class the player races (or will race next season, in the off-season)."""
    if not d.series_id or d.team_id is not None:
        return None
    s = world.pyramid.series.get(d.series_id)
    return class_of(s) if s is not None else None


def _pay(d: "Driver", amount: float) -> bool:
    """In season: racing account then savings. Off-season: savings, then next season's racing money."""
    from ..sim.season import charge
    if amount <= 0:
        return True
    if d.car is not None and d.car.account is not None:
        return spend(d, amount)
    if d.savings * 0.75 + d.available_funding() < amount:   # available_funding already counts 25% of savings
        return False
    charge(d, amount)
    return True


def _settle(d: "Driver", price: float, trade: float) -> bool:
    """Pay ``price`` less the trade-in; a trade-in worth more than the price comes back as money."""
    if trade > price:
        _refund(d, trade - price)
        return True
    return _pay(d, price - trade)


def _refund(d: "Driver", amount: float) -> None:
    if amount <= 0:
        return
    if d.car is not None and d.car.account is not None:
        d.car.account += amount
    else:
        d.savings += amount


def garage_action(world: "World", d: "Driver", action: str, key: Optional[str] = None,
                  value: Optional[int] = None) -> str:
    cls = target_class(world, d)
    if cls is None:
        return "You don't run your own car in a class with a garage (team seats are the team's business)."
    week = world.season.week if world.season is not None else 0
    car = d.car
    if car is not None and car.account is None:
        car.year = world.year
    if action == "new_car":
        ch, en, sh = (cls.chassis_opt(key or ""), None, None)
        parts = (key or "").split("|")
        if len(parts) == 3:
            ch, en, sh = cls.chassis_opt(parts[0]), cls.engine(parts[1]), cls.shock(parts[2])
        if ch is None or en is None or (cls.shocks and sh is None):
            return "Pick a chassis, an engine and shocks."
        if not en.available(world.year):
            return f"{en.label} isn't legal in {world.year}."
        sh = sh or C.Option("stock", "Stock", 0, 50)
        trade = 0.0
        if car is not None:
            old = all_class(car.cls)
            trade = C.resale(car, old) if old else 0.0
        price = ch.usd + en.usd + sh.usd
        if not _settle(d, price, trade):
            return f"That package costs ${price:,.0f} (trade-in ${trade:,.0f}) - more than you have."
        new = C.build(cls, ch, en, sh, car.new_tires if car is not None else cls.tires.typical_new)
        new.year = world.year
        if car is not None:   # the season's money and history move to the new car (read after paying)
            for attr in ("account", "ledger", "winnings", "drawn", "races", "auto_rebuild", "auto_repair", "reserve"):
                setattr(new, attr, getattr(car, attr))
        d.car = new
        log(new, week, f"New car: {ch.label}, {en.label}, {sh.label} shocks"
            + (f" (trade-in ${trade:,.0f})" if trade else ""), -(price - trade))
        return f"Bought: {ch.label} with a {en.label}." + (f" Old car sold for ${trade:,.0f}." if trade else "")
    if car is None or car.cls != cls.key:
        return f"You need a {cls.label.lower()} first - buy a car package."
    if action == "chassis":
        opt = cls.chassis_opt(key or "")
        if opt is None:
            return "Unknown chassis."
        old = cls.chassis_opt(car.chassis)
        trade = (old.usd * max(0.15, 0.6 * 0.82 ** max(car.chassis_age - old.age, 0)) * (0.4 + 0.6 * car.condition / 100)
                 ) if old else 0.0
        if not _settle(d, opt.usd, trade):
            return f"{opt.label} costs ${opt.usd:,.0f} (old chassis fetches ${trade:,.0f})."
        car.chassis, car.chassis_q, car.chassis_age, car.condition = opt.key, opt.quality, opt.age, 100.0
        log(car, week, f"Chassis: {opt.label} (sold old for ${trade:,.0f})", -(opt.usd - trade))
        return f"New chassis: {opt.label}."
    if action == "engine":
        opt = cls.engine(key or "")
        if opt is None or not opt.available(world.year):
            return "That engine isn't legal this season."
        cur = cls.engine(car.engine)
        trade = (cur.usd * 0.55 * (0.3 + 0.7 * car.engine_health / 100)) if cur else 0.0
        if not _settle(d, opt.usd, trade):
            return f"{opt.label} costs ${opt.usd:,.0f} (yours fetches ${trade:,.0f})."
        car.engine, car.engine_q, car.engine_runs, car.engine_health = opt.key, opt.quality, 0, 100.0
        log(car, week, f"Engine: {opt.label} (sold old for ${trade:,.0f})", -(opt.usd - trade))
        return f"Installed: {opt.label}."
    if action == "shocks":
        opt = cls.shock(key or "")
        if opt is None:
            return "Unknown shock package."
        if not _pay(d, opt.usd):
            return f"{opt.label} shocks cost ${opt.usd:,.0f}."
        car.shocks, car.shocks_q = opt.key, opt.quality
        log(car, week, f"Shocks: {opt.label}", -opt.usd)
        return f"New shocks: {opt.label}."
    if action == "tires":
        n = int(value if value is not None else cls.tires.typical_new)
        n = max(0, min(n, C.max_new(cls)))
        car.new_tires = n
        return f"You'll buy {n} new tire{'s' if n != 1 else ''} each night."
    if action == "rebuild":
        return rebuild(world, d, cls, week)
    if action == "repair":
        return repair(world, d, cls, week)
    if action == "hire":
        from ..world import staff as ST
        s = world.staff.get(int(key)) if key and key.isdigit() else None
        if s is None or s.retired or s.team_id is not None or s.role not in ST.PLAYER_ROLES:
            return "That person isn't available."
        if s.id in world.player_crew.values():
            return f"{s.name} already works for you."
        if s.role in world.player_crew:
            cur = world.staff.get(world.player_crew[s.role])
            return (f"You already have a {ST.ROLES[s.role][0].lower()}"
                    + (f" ({cur.name})" if cur else "") + " - let them go first.")
        tier = world.series(d.series_id).tier
        cost = ST.hire_cost(world, s, tier)
        if not _pay(d, cost):
            return f"{s.name} wants ${cost:,.0f} for the season - more than you have."
        world.player_crew[s.role] = s.id
        if d.car is not None:
            log(d.car, week, f"Hired {s.name} ({ST.ROLES[s.role][0].lower()}) for the season", -cost)
        return f"{s.name} joins your crew as {ST.ROLES[s.role][0].lower()} for the season."
    if action == "release":
        from ..world import staff as ST
        if key not in world.player_crew:
            return "Nobody in that role."
        sid = world.player_crew.pop(key)
        s = world.staff.get(sid)
        return f"{s.name if s else 'They'} is off the crew (no refund)."
    if action in ("auto_rebuild", "auto_repair"):
        setattr(car, action, bool(value))
        return f"{'Automatic engine freshens' if action == 'auto_rebuild' else 'Automatic crash repairs'} " \
               f"{'on' if value else 'off'}."
    return "Unknown garage action."
