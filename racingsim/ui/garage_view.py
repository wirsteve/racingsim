"""Garage page payload: the player's car, the class rules it's built to, and the money."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from ..history.economy import price_index
from ..rules import car as C
from ..rules import garage as G
from ..rules.classes import CarClass
from ..util import load_json

if TYPE_CHECKING:
    from ..game.session import Game


@lru_cache(maxsize=1)
def rule_sources() -> dict:
    try:
        return load_json("rules/sources.json")
    except FileNotFoundError:
        return {}


def sources(ids: list[str]) -> list[dict]:
    src = rule_sources()
    out = []
    for i in ids or []:
        s = src.get(i, {})
        out.append({"id": i, "name": s.get("name", i), "url": s.get("url"), "reliability": s.get("reliability")})
    return out


def _opt(o: C.Option, year: int) -> dict:
    return {"key": o.key, "label": o.label, "usd": o.usd, "quality": round(o.quality), "age": o.age,
            "rebuild_usd": o.rebuild_usd, "rebuild_races": o.rebuild_races, "claim_usd": o.claim_usd,
            "sealed": o.sealed, "weight_break_lb": o.weight_break_lb, "legal": o.available(year),
            "years": list(o.years) if o.years != (1900, 2100) else None, "note": o.note}


def class_info(cls: CarClass, year: int) -> dict:
    t = cls.tires
    return {
        "key": cls.key, "label": cls.label, "discipline": cls.discipline, "spread": cls.spread,
        "min_weight_lb": cls.min_weight_lb, "rules": cls.rules, "claims": cls.claims,
        "history": [h for h in cls.history if h.get("year", 0) <= year] or cls.history[:3],
        "tires": {"usd": t.usd, "typical_new": t.typical_new, "max_new": t.max_new, "life_races": t.life_races,
                  "spec": t.spec, "rule": t.rule},
        "per_race": {"entry": cls.entry_usd, "fuel": cls.fuel_usd, "misc": cls.misc_usd},
        "chassis_life": cls.chassis_life, "repair_frac": cls.repair_frac,
        "chassis": [_opt(o, year) for o in sorted(cls.chassis, key=lambda o: o.usd)],
        "engines": [_opt(o, year) for o in sorted(cls.engines, key=lambda o: o.usd)],
        "shocks": [_opt(o, year) for o in sorted(cls.shocks, key=lambda o: o.usd)],
        "facts": cls.facts, "confidence": cls.confidence, "notes": cls.notes,
        "sources": sources(cls.sources),
    }


def car_info(world, d, cls: CarClass, track) -> dict:
    car = d.car
    ch = cls.chassis_opt(car.chassis)
    en = cls.engine(car.engine)
    sh = cls.shock(car.shocks)
    remaining = 0
    if world.season is not None and d.series_id:
        s = world.series(d.series_id)
        remaining = max(0, len(s.schedule) - car.races) if car.account is not None else len(s.schedule)
    wc, we, wt, ws = C.weights(track)
    tot = wc + we + wt + ws
    return {
        "chassis": {"label": ch.label if ch else car.chassis, "quality": round(car.chassis_q),
                    "age": car.chassis_age, "condition": round(car.condition), "score": round(car.chassis_score(cls)),
                    "weight": round(wc / tot, 2), "repair_usd": round(C.repair_cost(cls, (100 - car.condition) / 100))},
        "engine": {"label": en.label if en else car.engine, "quality": round(car.engine_q), "runs": car.engine_runs,
                   "interval": en.rebuild_races if en else 0, "health": round(car.engine_health),
                   "rebuild_usd": en.rebuild_usd if en else 0, "score": round(car.engine_score(cls)),
                   "sealed": en.sealed if en else False, "claim_usd": en.claim_usd if en else 0,
                   "weight": round(we / tot, 2)},
        "shocks": {"label": sh.label if sh else car.shocks, "quality": round(car.shocks_q), "weight": round(ws / tot, 2)},
        "tires": {"wear": round(car.tire_wear, 2), "score": round(car.tire_score()), "new_per_night": car.new_tires,
                  "max_new": C.max_new(cls), "weight": round(wt / tot, 2),
                  "wear_per_race": round(C.wear_per_race(cls, track), 3)},
        "rating": round(C.rating(car, cls, track, d.feedback)),
        "rating_fresh_tires": round(C.rating(car, cls, track, d.feedback, tire_wear=C.steady_wear(cls, car.new_tires, track))),
        "resale": round(C.resale(car, cls)),
        "night_cost": round(C.night_cost(cls, car)), "engine_wear_per_race": round(C.engine_wear_cost(cls, car)),
        "overhead_per_night": round(C.overhead_per_night(cls, world.series(d.series_id).template)) if d.series_id else 0,
        "season_running": round(C.season_running(cls, car, remaining)), "remaining_races": remaining,
        "auto_rebuild": car.auto_rebuild, "auto_repair": car.auto_repair,
        "account": None if car.account is None else round(car.account),
        # Ledger rows in the dollars of their season: [week, text, nominal amount, year].
        "ledger": [[r[0], r[1], round(r[2] * price_index(r[3] if len(r) > 3 and r[3] else world.year)),
                    r[3] if len(r) > 3 else world.year] for r in car.ledger[-80:]],
    }


def garage(game: "Game") -> dict:
    w = game.world
    d = w.player
    if d is None:
        return {"available": False, "why": "No driver."}
    cls = G.target_class(w, d)
    if cls is None:
        why = ("Your team prepares the car - you just drive it." if d.team_id is not None else
               "Your current class has no researched rules yet." if d.series_id else "You have no ride.")
        return {"available": False, "why": why}
    s = w.series(d.series_id)
    track = G.home_track(w, s)
    out = {"available": True, "class": class_info(cls, w.year), "series": {"id": s.id, "name": s.name},
           "track": track.name if track else None, "year": w.year,
           "money": {"savings": round(d.savings), "available": round(d.available_funding())},
           "in_season": d.car is not None and d.car.account is not None}
    if d.car is not None and d.car.cls == cls.key:
        out["car"] = car_info(w, d, cls, track)
    elif d.car is not None:
        old = G.all_class(d.car.cls)
        out["old_car"] = {"class": old.label if old else d.car.cls, "resale": round(C.resale(d.car, old)) if old else 0}
    # Ready-made packages for a new car in this class.
    legal = cls.engines_in(w.year)
    chs = sorted(cls.chassis, key=lambda o: o.usd)
    ens = sorted(legal, key=lambda o: o.usd)
    shs = sorted(cls.shocks, key=lambda o: o.usd) or [C.Option("stock", "Stock", 0, 50)]
    pk = []
    for label, i in (("Budget", 0.0), ("Competitive", 0.5), ("Front-runner", 1.0)):
        ch = chs[min(len(chs) - 1, int(i * (len(chs) - 1) + 0.5))]
        en = ens[min(len(ens) - 1, int(i * (len(ens) - 1) + 0.5))]
        sh = shs[min(len(shs) - 1, int(i * (len(shs) - 1) + 0.5))]
        tmp = C.build(cls, ch, en, sh, cls.tires.typical_new)
        pk.append({"label": label, "key": f"{ch.key}|{en.key}|{sh.key}", "usd": ch.usd + en.usd + sh.usd,
                   "parts": [ch.label, en.label, sh.label],
                   "rating": round(C.rating(tmp, cls, track, d.feedback,
                                            tire_wear=C.steady_wear(cls, cls.tires.typical_new, track)))})
    seen = set()
    out["packages"] = [p for p in pk if not (p["key"] in seen or seen.add(p["key"]))]
    return out
