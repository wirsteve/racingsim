"""Records books, the almanac and the Hall of Fame for the UI."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from ..world import annals

if TYPE_CHECKING:
    from ..world.world import World


def _who(world: "World", did: int) -> dict:
    d = world.drivers.get(did)
    return {"id": did, "name": d.name if d else "?", "me": bool(d and d.is_player), "real": bool(d and d.real)}


def records_index(world: "World") -> list[dict]:
    """Series with a records book: touring level and up, newest name, best level first."""
    key = ("records_index", world.year, bool(world.season is not None and world.season.finished))
    hit = world.cache.get(key)
    if hit is not None:
        return hit
    seen: dict[str, dict] = {}
    for d in world.drivers.values():
        for r in d.history:
            if r.tier < 3:
                continue
            cur = seen.get(r.series_id)
            if cur is None or r.year > cur["year"]:
                s = world.pyramid.series.get(r.series_id)
                name = s.name if s is not None else (r.series_name or r.series_id)
                seen[r.series_id] = {"id": r.series_id, "name": re.sub(r"^\d{4} ", "", name),   # "2007 IndyCar Series"
                                     "tier": r.tier, "year": r.year}
    out = sorted(seen.values(), key=lambda x: (-x["tier"], x["name"]))
    names = [x["name"] for x in out]
    for x in out:   # two touring series can share a name: tell them apart
        if names.count(x["name"]) > 1:
            x["name"] = f'{x["name"]} ({x["id"]})'
    world.cache[key] = out
    return out


def records(world: "World", series_id: Optional[str]) -> dict:
    index = records_index(world)
    if not index:
        return {"series": [], "current": None, "career": {}, "season": {}}
    ids = {x["id"] for x in index}
    if series_id not in ids:
        mine = world.player.series_id if world.player is not None else None
        series_id = mine if mine in ids else "cup_series" if "cup_series" in ids else index[0]["id"]
    book = annals.records(world, series_id)
    career = {k: {"label": v["label"], "rows": [{"value": val, **_who(world, did)} for val, did in v["rows"]]}
              for k, v in book["career"].items()}
    season = {k: {"label": v["label"], "rows": [{"value": val, "year": y, **_who(world, did)} for val, did, y in v["rows"]]}
              for k, v in book["season"].items()}
    return {"series": index, "current": series_id, "career": career, "season": season}


def almanac(world: "World", year: Optional[int]) -> dict:
    book = annals.store(world)["almanac"]
    years = sorted(book, reverse=True)
    if not years:
        return {"years": [], "year": None}
    if year not in book:
        year = years[0]
    a = book[year]
    return {
        "years": years, "year": year,
        "champions": [{"series": s, "tier": t, **_who(world, did)} for s, t, did in a["champions"]],
        "awards": [{"award": x[0], "series": x[1], "note": x[3], **_who(world, x[2])} for x in a["awards"]],
        "par": [{"par": p, "series": s, **_who(world, did)} for p, did, s in a["par"]],
        "jewels": [{"event": e, **_who(world, did)} for e, did in a["jewels"]],
        "milestones": [{"text": m[0], **_who(world, m[1])} for m in a["milestones"]][:60],
        "hof": [_who(world, did) for did in a.get("hof", [])],
    }


def hall_of_fame(world: "World") -> dict:
    rows = []
    for h in reversed(annals.store(world)["hof"]):
        rows.append({**_who(world, h["id"]), "year": h["year"], "career": h["career"], "case": h["case"],
                     "score": h["score"]})
    return {"inductees": rows, "bar": annals.HOF_BAR, "wait": annals.HOF_WAIT}
