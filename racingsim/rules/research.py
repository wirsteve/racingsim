"""Read-only access to the rules evidence (data/rules/research.json) for the Encyclopedia."""

from __future__ import annotations

from functools import lru_cache

from ..util import load_json
from .classes import all_classes
from .payouts import tables
from .points import _data as points_data
from .points import formats, systems


@lru_cache(maxsize=1)
def evidence() -> dict:
    try:
        return load_json("rules/research.json")
    except FileNotFoundError:
        return {}


@lru_cache(maxsize=1)
def source_registry() -> dict:
    try:
        return load_json("rules/sources.json")
    except FileNotFoundError:
        return {}


def _src(ids) -> list[dict]:
    reg = source_registry()
    out = []
    for i in ids or []:
        if not isinstance(i, str):
            continue
        s = reg.get(i, {})
        out.append({"id": i, "name": s.get("name", i), "url": s.get("url"), "year": s.get("year"),
                    "reliability": s.get("reliability")})
    return out


def _with_sources(rec: dict) -> dict:
    r = dict(rec)
    r["sources"] = _src(rec.get("sources"))
    return r


def overview() -> dict:
    ev = evidence()
    by_class: dict[str, int] = {}
    for kind in ("class_rules", "parts", "payouts", "points_systems", "race_formats"):
        for r in ev.get(kind, []):
            k = r.get("class") or "general"
            by_class[k] = by_class.get(k, 0) + 1
    classes = [{"key": c.key, "label": c.label, "discipline": c.discipline, "confidence": c.confidence,
                "templates": c.templates, "records": sum(by_class.get(k, 0) for k in c.evidence_keys())}
               for c in all_classes().values()]
    pts = [{"key": s.key, "label": s.label, "note": s.note, "confidence": s.confidence,
            "table": s.table[:12], "step": s.step, "win_bonus": s.win_bonus, "led_lap": s.led_lap,
            "most_led": s.most_led, "stage": s.stage, "stages": s.stages, "heat": s.heat, "show_up": s.show_up,
            "sources": _src(s.sources)} for s in systems().values()]
    fmts = [{"key": f.key, "label": f.label, "kind": f.kind, "drivers": f.drivers, "races": f.races,
             "note": f.note, "confidence": f.confidence, "sources": _src(f.sources)} for f in formats().values()]
    pays = [{"key": t.key, "label": t.label, "year": t.year, "by_position": t.by_position[:10],
             "to_start": t.to_start, "dnq": t.dnq, "points_fund": t.points_fund[:5], "note": t.note,
             "confidence": t.confidence, "sources": _src(t.sources)} for t in tables().values()]
    return {"classes": classes, "points": pts, "formats": fmts, "payouts": pays,
            "assign": points_data().get("assign", []),
            "counts": {k: len(ev.get(k, [])) for k in ("class_rules", "parts", "points_systems", "payouts",
                                                        "race_formats", "history")},
            "history": [_with_sources(h) for h in ev.get("history", [])],
            "sources": len(source_registry())}


def class_detail(key: str):
    from ..ui.garage_view import class_info
    c = all_classes().get(key)
    ev = evidence()
    keys = set(c.evidence_keys()) if c is not None else {key}
    recs = {kind: [_with_sources(r) for r in ev.get(kind, []) if r.get("class") in keys]
            for kind in ("class_rules", "parts", "payouts", "points_systems", "race_formats", "history")}
    if c is None and not any(recs.values()):
        return None
    out = {"key": key, "evidence": recs}
    if c is not None:
        out["class"] = class_info(c, 2026)
    return out
