"""Fill profile gaps of series that were never researched individually.

    python tools/knowledge/fill_gaps.py

For each series missing annual cost, typical age, field size, season events or a car class, copy the value
from the best-researched series that plays the same game rung (``game_template``): same ladder level,
same kind of car. Inherited facts are marked ``confidence: low`` with a note naming where they came from,
and keep that series' sources, so they are easy to find and replace with real research.
"""

from __future__ import annotations

import json
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge"
FIELDS = ("annual_cost_usd", "typical_age", "field_size", "season_events", "race_length")
RANK = {"high": 3, "medium": 2, "low": 1}


def is_fact(v) -> bool:
    return isinstance(v, dict) and bool({"min", "max", "value", "category"} & set(v))


def main() -> int:
    path = KDIR / "series.json"
    series = json.loads(path.read_text(encoding="utf-8"))
    by_tpl: dict[str, list[dict]] = {}
    for s in series:
        if s.get("game_template") and not s.get("inherited_from"):
            by_tpl.setdefault(s["game_template"], []).append(s)
    filled = 0
    for s in series:
        tpl = s.get("game_template")
        donors = [d for d in by_tpl.get(tpl, []) if d is not s]
        if not donors:
            continue
        for f in FIELDS + ("car_class",):
            if s.get(f):
                continue
            cands = [d for d in donors if (is_fact(d.get(f)) if f != "car_class" else d.get(f))]
            if not cands:
                continue
            donor = max(cands, key=lambda d: (RANK.get(d.get("confidence"), 0), len(d.get("sources") or [])))
            if f == "car_class":
                s[f] = donor[f]
            else:
                v = dict(donor[f])
                v["confidence"] = "low"
                v["notes"] = f"inherited from {donor['id']} (same ladder rung); not researched individually"
                s[f] = v
            s.setdefault("inherited_from", {})[f] = donor["id"]
            filled += 1
    path.write_text(json.dumps(series, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"filled {filled} profile gaps by inheritance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
