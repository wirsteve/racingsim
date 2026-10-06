"""Fill missing coordinates (and obvious facts) of staged new venues from open track datasets.

    python tools/knowledge/geocode_venues.py STAGED_TRACKS_JSON WIKIDATA_JSON [OSM_JSON]

Order: Wikidata racetrack items (CC0), then OpenStreetMap venues (ODbL; coordinates only,
credited in data/CREDITS.md). Matching needs the same state/province and a name match
(normalised name, or all distinctive tokens shared). Venues still without coordinates
stay out of the track database (logged).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

GENERIC = {"speedway", "raceway", "motor", "motorsports", "park", "the", "track", "race", "international",
           "fairgrounds", "county", "oval", "of", "at", "and", "motorplex", "complex", "center", "dirt", "short"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def toks(s: str) -> set[str]:
    return {t for t in norm(s).split() if t not in GENERIC and len(t) > 1}


def best_match(v: dict, pool: list[dict]):
    names = [v["name"]] + list(v.get("aliases") or [])
    vt = set().union(*[toks(n) for n in names])
    vn = {norm(n) for n in names}
    for c in pool:
        if (c.get("state") or c.get("region") or "").upper() != (v.get("region") or "").upper():
            continue
        cn = {norm(c.get("name", ""))} | {norm(n) for n in c.get("other_names") or []}
        ct = set().union(*[toks(n) for n in cn]) if cn else set()
        if vn & cn or (vt and vt <= ct) or (ct and ct <= vt and len(ct) >= 1 and vt & ct):
            if c.get("lat") is not None:
                return c
    return None


def main(staged: str, wikidata: str, osm: str | None = None) -> int:
    venues = json.loads(Path(staged).read_text(encoding="utf-8"))
    wd = json.loads(Path(wikidata).read_text(encoding="utf-8"))["tracks"]
    om = json.loads(Path(osm).read_text(encoding="utf-8"))["tracks"] if osm else []
    om = [c for c in om if not c.get("unnamed") and "drag" not in (c.get("kinds") or []) and "karting" not in (c.get("kinds") or [])]
    found = {"wikidata": 0, "osm": 0, "missing": 0}
    for v in venues:
        if v.get("lat") is not None:
            continue
        c = best_match(v, wd)
        if c is not None:
            v["lat"], v["lon"] = c["lat"], c["lon"]
            for k_src, k_dst in (("length_mi", "length_mi"), ("opened", "opened"), ("closed", "closed")):
                if v.get(k_dst) is None and c.get(k_src) is not None:
                    v[k_dst] = c[k_src]
            v.setdefault("sources", []).append(f"https://www.wikidata.org/wiki/{c['wikidata_id']}")
            found["wikidata"] += 1
            continue
        c = best_match(v, om)
        if c is not None:
            v["lat"], v["lon"] = c["lat"], c["lon"]
            if v.get("surface") is None and c.get("surface_category") in ("asphalt", "dirt", "concrete"):
                v["surface"] = c["surface_category"]
            v.setdefault("sources", []).append(f"https://www.openstreetmap.org/{c['osm_id']} (ODbL)")
            found["osm"] += 1
            continue
        found["missing"] += 1
    for v in venues:
        v["track_type"] = v.get("track_type") or "oval"
        v["level"] = v.get("level") or "regional"
    Path(staged).write_text(json.dumps(venues, indent=1, ensure_ascii=False), encoding="utf-8")
    print(found, "missing:", [v["name"] + " (" + (v.get("region") or "") + ")" for v in venues if v.get("lat") is None])
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
