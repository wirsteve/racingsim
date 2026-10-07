"""Race Shop page payload: the hauler, the shop's facilities, the fleet, spare engines, the used market
and (owner mode) the team's facilities."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from ..rules import car as C
from ..rules import garage as G
from ..rules import shop as SH

if TYPE_CHECKING:
    from ..game.session import Game


def _effect(name: str, lv: dict) -> str:
    if name == "space":
        return f"{lv['cars']} cars, {lv['engines']} spare engine{'s' if lv['engines'] != 1 else ''}"
    if name == "fab":
        build = "no builds (turnkey cars only)" if lv.get("build") is None else \
            f"builds {lv['build']:+d} chassis quality in {lv['build_weeks']} weeks"
        return (f"crash repairs {round(lv['repair'] * 100)}% of the bill; {build}; "
                f"used cars measured to ±{lv['inspect']}%" + ("; chassis age 25% slower" if lv.get("aging") else ""))
    if name == "engine":
        parts = [f"freshens {round(lv['freshen'] * 100)}% of the bill"]
        if lv["interval"] > 1:
            parts.append(f"{round((lv['interval'] - 1) * 100)}% longer between freshens")
        if lv["power"]:
            parts.append(f"+{lv['power']:g} engine on open (unsealed) engines")
        return "; ".join(parts)
    if name == "setup":
        parts = [f"+{lv['setup']:g} setup"] if lv["setup"] else ["no setup tools"]
        if lv["shocks"]:
            parts.append(f"+{lv['shocks']} shock quality")
        if lv["feedback"] > 1:
            parts.append(f"driver feedback counts {lv['feedback']:g}x")
        return "; ".join(parts)
    return ""


def _hauler(h: dict, cur: bool) -> dict:
    return {**h, "current": cur,
            "effect": f"{h['cars']} car{'s' if h['cars'] > 1 else ''}; towing {round(h['travel'] * 100)}% of normal; "
                      f"failures {round(h['mech'] * 100)}%; sponsors +{round(h['sponsor'] * 100)}%"}


def car_row(w, d, cls, car, track, primary: bool, idx: int = -1) -> dict:
    ch, en, sh = cls.chassis_opt(car.chassis), cls.engine(car.engine), cls.shock(car.shocks)
    interval = round(en.rebuild_races * car.interval_mult) if en and en.rebuild_races else 0
    return {"idx": idx, "tag": car.tag or ("Primary" if primary else "Car"), "primary": primary,
            "chassis": ch.label if ch else car.chassis, "age": round(car.chassis_age, 1),
            "quality": round(car.chassis_q), "condition": round(car.condition),
            "engine": en.label if en else car.engine, "engine_q": round(car.engine_q), "runs": car.engine_runs,
            "interval": interval, "health": round(car.engine_health), "sealed": bool(en and en.sealed),
            "shocks": sh.label if sh else car.shocks,
            "rating": round(C.rating(car, cls, track, d.feedback, tire_wear=C.steady_wear(cls, car.new_tires, track),
                                     bonus=SH.rating_bonus(w, d, cls, track, car=car))),
            "resale": round(C.resale(car, cls) * (1 if primary or idx < 0 else SH.PRIVATE_SALE))}


def shop(game: "Game") -> dict:
    w = game.world
    d = w.player
    if d is None:
        return {"available": False, "why": "No driver."}
    op = SH.get(w)
    cls = G.target_class(w, d)
    spec = SH.data()
    cars, engines = SH.capacity(w)
    out = {
        "available": True, "year": w.year, "in_season": SH.in_season(w), "week": SH.week(w),
        "money": {"savings": round(d.savings), "available": round(d.available_funding()),
                  "account": None if d.car is None or d.car.account is None else round(d.car.account)},
        "hauler": {"key": op.hauler, "age": op.hauler_age, "trade": round(SH.hauler_trade(op)),
                   "options": [_hauler(h, h["key"] == op.hauler) for h in SH.haulers()]},
        "facilities": [], "upkeep": round(SH.upkeep(op)),
        "capacity": {"cars": cars, "engines": engines, "kept": SH.cars_kept(w, d), "spares": len(op.engines)},
    }
    for name in SH.FACILITIES:
        f = spec["facilities"][name]
        lv = SH.level(op, name)
        out["facilities"].append({
            "key": name, "label": f["label"], "level": lv,
            "levels": [{"label": x["label"], "usd": x["usd"], "upkeep": x["upkeep"], "about": x["about"],
                        "effect": _effect(name, x)} for x in f["levels"]]})
    if d.series_id:
        s = w.series(d.series_id)
        out["series"] = {"id": s.id, "name": s.name, "tier": s.tier}
        if not s.template.team_based:
            out["typical_upkeep"] = round(SH.upkeep(SH.typical(s.template.season_cost)))
    out["team"] = team_info(w, d)
    if cls is None:
        out["why"] = ("Your team owns the cars - you just drive them." if d.team_id is not None else
                      "Your class has no researched car rules yet." if d.series_id else "You have no ride.")
        return out
    s = w.series(d.series_id)
    track = G.home_track(w, s)
    SH.sync(w, d, cls)
    out["class"] = {"key": cls.key, "label": cls.label, "has_shocks": bool(cls.shocks)}
    fl = []
    if d.car is not None and d.car.cls == cls.key:
        fl.append(car_row(w, d, cls, d.car, track, True))
    fl += [car_row(w, d, cls, c, track, False, i) for i, c in enumerate(op.backups) if c.cls == cls.key]
    out["fleet"] = fl
    out["projects"] = [{"tag": p["car"].tag, "ready_week": p["ready_week"], "year": p["year"],
                        "chassis": (cls.chassis_opt(p["car"].chassis) or C.Option("", p["car"].chassis, 0, 0)).label,
                        "quality": round(p["car"].chassis_q)} for p in op.projects]
    spares = []
    for i, e in enumerate(op.engines):
        opt = cls.engine(e["key"])
        if opt is None:
            continue
        spares.append({"idx": i, "label": opt.label, "q": round(e["q"]), "runs": e["runs"],
                       "health": round(e["health"]), "sealed": opt.sealed,
                       "freshen": round(SH.freshen_cost(w, opt, e["health"])),
                       "value": round(SH.engine_value(opt, e))})
    out["engines"] = spares
    fb = SH.fac(op, "fab")
    kit = spec["build"].get("kit_share", 0.8)
    out["build"] = {
        "allowed": fb.get("build") is not None, "weeks": fb.get("build_weeks", 0), "bonus": fb.get("build"),
        "chassis": [{"key": o.key, "label": o.label, "usd": round(o.usd * kit), "quality": round(o.quality)}
                    for o in sorted(cls.chassis, key=lambda o: o.usd)],
        "engines": [{"key": o.key, "label": o.label, "usd": o.usd, "quality": round(o.quality)}
                    for o in sorted(cls.engines_in(w.year), key=lambda o: o.usd)]
                   + [{"key": f"spare:{e['idx']}", "label": f"Spare {e['label']} (on the stand)", "usd": 0,
                       "quality": e["q"]} for e in spares],
        "shocks": [{"key": o.key, "label": o.label, "usd": o.usd, "quality": round(o.quality)}
                   for o in sorted(cls.shocks, key=lambda o: o.usd)] or [{"key": "stock", "label": "Stock", "usd": 0,
                                                                         "quality": 50}],
    }
    out["new_engines"] = [{"key": o.key, "label": o.label, "usd": o.usd, "quality": round(o.quality),
                           "sealed": o.sealed, "rebuild_races": o.rebuild_races, "rebuild_usd": o.rebuild_usd}
                          for o in sorted(cls.engines_in(w.year), key=lambda o: o.usd)]
    listings = []
    for item in SH.market(w, d, cls):
        car = item["car"]
        seen = SH.shown(w, item)
        look = copy.copy(car)
        look.condition, look.engine_health = seen["condition"], seen["engine_health"]
        row = car_row(w, d, cls, look, track, False)
        row.update({"id": item["id"], "price": round(item["price"]), "seller": item["seller"],
                    "spread": seen["spread"]})
        listings.append(row)
    out["market"] = listings
    return out


def team_info(w, d):
    from ..game.owner import owned
    t = owned(w)
    if t is None:
        return None
    spec = SH.data()["team"]
    base = SH.team_cost_base(w, t)
    rows = []
    for k in SH.TEAM_FACILITIES:
        f = spec[k]
        lv = SH.team_level(t, k)
        if k == "rnd":
            effect = f"+{f['equipment'] * lv:g} equipment a season"
        elif k == "engineering":
            effect = f"+{f['setup'] * lv:g} setup on race day"
        elif k == "pit":
            effect = f"stops {round(f['pit'] * lv * 100)}% faster"
        else:
            effect = f"sponsors +{round(f['sponsor'] * lv * 100)}%, failures -{round(f['mech'] * lv * 100)}%"
        rows.append({"key": k, "label": f["label"], "about": f["about"], "level": lv,
                     "next": round(f["price"][lv] * base) if lv < 3 else None,
                     "upkeep": round(f["upkeep"] * base), "effect": effect})
    return {"id": t.id, "name": t.name, "cash": round(t.cash), "cars": t.cars, "facilities": rows,
            "upkeep": round(SH.team_upkeep(w, t)), "value": round(SH.team_value(w, t)),
            "equipment": round(t.equipment, 1)}
