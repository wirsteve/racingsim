"""Fold staged rules research (tools/knowledge/staging/rules/*.json) into data/rules/.

Outputs (committed):
  data/rules/research.json     every class-rule, part, points-system, payout, race-format and
                               history record, de-duplicated, with a stable id, its sources and
                               confidence - the evidence the game's rule files are built from
  data/rules/sources.json      source registry for those records (name, url, kind, reliability)
  data/rules/unavailable.json  sources that blocked automated access (not circumvented) and what replaced them

The game files (data/rules/classes.json, points.json, payouts.json) are curated from this
evidence and cite the same source ids. Run again whenever new research is staged:

    python tools/knowledge/rules_import.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGING = ROOT / "tools" / "knowledge" / "staging" / "rules"
OUT = ROOT / "data" / "rules"
KINDS = ("class_rules", "parts", "points_systems", "payouts", "race_formats", "history")


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"skip {path.name}: {exc}", file=sys.stderr)
        return {}


def _rid(kind: str, rec: dict) -> str:
    key = json.dumps({k: rec.get(k) for k in ("class", "body", "region", "year", "item", "part", "event",
                                               "topic", "fact", "level", "format")}, sort_keys=True)
    return f"{kind[:2]}:{hashlib.sha1(key.encode()).hexdigest()[:10]}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    old = _load(OUT / "research.json") if (OUT / "research.json").exists() else {}
    research: dict[str, dict] = {k: {r["id"]: r for r in old.get(k, [])} for k in KINDS}
    sources = _load(OUT / "sources.json") if (OUT / "sources.json").exists() else {}
    unavailable = {(u.get("source"), u.get("url")): u for u in
                   (_load(OUT / "unavailable.json") if (OUT / "unavailable.json").exists() else [])}
    for f in sorted(STAGING.glob("*.json")):
        d = _load(f)
        origin = f.stem
        for sid, s in (d.get("sources") or {}).items():
            sources.setdefault(sid, s)
        for u in d.get("unavailable") or []:
            unavailable.setdefault((u.get("source"), u.get("url")), u)
        for kind in KINDS:
            for rec in d.get(kind) or []:
                if not isinstance(rec, dict):
                    continue
                rec = dict(rec)
                rec.pop("id", None)
                rid = _rid(kind, rec)
                rec["id"] = rid
                rec["origin"] = origin
                research[kind][rid] = rec
    missing = sorted({s for k in KINDS for r in research[k].values() for s in r.get("sources", [])
                      if isinstance(s, str) and s not in sources})
    out = {"_comment": "Researched evidence for data/rules/*.json; see tools/knowledge/rules_import.py.",
           **{k: sorted(research[k].values(), key=lambda r: (str(r.get("class", "")), str(r.get("body", "")),
                                                              str(r.get("year", "")), r["id"]))
              for k in KINDS}}
    (OUT / "research.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "sources.json").write_text(json.dumps(dict(sorted(sources.items())), indent=1, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    (OUT / "unavailable.json").write_text(json.dumps(sorted(unavailable.values(), key=lambda u: str(u.get("source"))),
                                                     indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print({k: len(research[k]) for k in KINDS}, "sources", len(sources), "unavailable", len(unavailable))
    if missing:
        print(f"{len(missing)} cited source ids have no registry entry: {missing[:10]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
