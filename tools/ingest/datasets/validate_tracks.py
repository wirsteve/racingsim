"""Spot-validate tracks_osm.json and tracks_wikidata.json against the repo's data/tracks/*.json
(coordinates, length, surface) for the venues matched to existing_tracks.json. Writes validation_tracks.json."""
import collections
import os

from common import HERE, REPO, norm, load_json, dump_json, haversine_km, EXISTING_TRACKS


def repo_tracks():
    by_key = {}
    tdir = os.path.join(REPO, "data", "tracks")
    for fn in os.listdir(tdir):
        if fn.endswith(".json"):
            for t in load_json(os.path.join(tdir, fn)):
                by_key[(norm(t["name"]), (t.get("region") or "").upper())] = t
    out = {}
    for e in load_json(EXISTING_TRACKS):
        t = by_key.get((norm(e["name"]), (e.get("region") or "").upper()))
        if t:
            out[e["id"]] = t
    return out


def surf(s):
    s = (s or "").lower()
    if any(k in s for k in ("asphalt", "paved", "concrete", "tarmac")):
        return "paved"
    if any(k in s for k in ("dirt", "clay", "ground", "unpaved", "compacted", "gravel")):
        return "dirt"
    return None


def main():
    repo = repo_tracks()
    res = {}
    for fname, lenkey in (("tracks_osm.json", "length_longest_raceway_way_mi"), ("tracks_wikidata.json", "length_mi")):
        d = load_json(os.path.join(HERE, fname))
        c = collections.Counter()
        dists, len_examples, surf_mism = [], [], []
        for t in d["tracks"]:
            if not t.get("match_primary"):
                continue
            r = repo.get(t["existing_track_id"])
            if not r:
                continue
            c["matched_with_repo_facts"] += 1
            c["match_" + t["match_method"]] += 1
            if t.get("lat") is not None and r.get("lat") is not None:
                dk = haversine_km(t["lat"], t["lon"], r["lat"], r["lon"])
                dists.append(dk)
            L, RL = t.get(lenkey), r.get("length_mi")
            if L and RL:
                c["length_compared"] += 1
                rel = abs(L - RL) / RL
                c["length_within_10pct"] += rel <= 0.10
                c["length_within_25pct"] += rel <= 0.25
                if len(len_examples) < 15:
                    len_examples.append({"track": r["name"], "dataset": L, "repo": RL})
            s1, s2 = surf(t.get("surface")), surf(r.get("surface"))
            if s1 and s2:
                c["surface_compared"] += 1
                c["surface_agree"] += s1 == s2
                if s1 != s2:
                    surf_mism.append({"track": r["name"], "dataset": t.get("surface"), "repo": r.get("surface")})
        dists.sort()
        res[fname] = {
            "counts": dict(c),
            "coord_distance_km": {"median": round(dists[len(dists) // 2], 3) if dists else None,
                                  "p90": round(dists[int(len(dists) * 0.9)], 3) if dists else None,
                                  "share_within_1km": round(sum(x <= 1 for x in dists) / len(dists), 3) if dists else None},
            "length_within_10pct_rate": round(c["length_within_10pct"] / c["length_compared"], 3) if c["length_compared"] else None,
            "length_within_25pct_rate": round(c["length_within_25pct"] / c["length_compared"], 3) if c["length_compared"] else None,
            "surface_agreement_rate": round(c["surface_agree"] / c["surface_compared"], 3) if c["surface_compared"] else None,
            "length_examples": len_examples, "surface_mismatches": surf_mism[:20],
        }
    # how many North-American existing tracks are covered by either dataset
    ex = load_json(EXISTING_TRACKS)
    na = [e for e in ex if len(e.get("region") or "") == 2]
    osm_hit = {t["existing_track_id"] for t in load_json(os.path.join(HERE, "tracks_osm.json"))["tracks"] if t["existing_track_id"]}
    wd_hit = {t["existing_track_id"] for t in load_json(os.path.join(HERE, "tracks_wikidata.json"))["tracks"] if t["existing_track_id"]}
    open_na = [e for e in na if not (repo.get(e["id"]) or {}).get("closed") and "street" not in e["id"]]
    res["coverage_of_existing_north_american_tracks"] = {
        "na_existing": len(na), "osm_found": len([e for e in na if e["id"] in osm_hit]),
        "wikidata_found": len([e for e in na if e["id"] in wd_hit]),
        "either_found": len([e for e in na if e["id"] in osm_hit | wd_hit]),
        "active_permanent_na": len(open_na),
        "active_permanent_osm_found": len([e for e in open_na if e["id"] in osm_hit]),
        "active_permanent_either_found": len([e for e in open_na if e["id"] in osm_hit | wd_hit]),
        "active_permanent_missing": [e["id"] for e in open_na if e["id"] not in osm_hit | wd_hit],
    }
    dump_json(res, os.path.join(HERE, "validation_tracks.json"))
    for k, v in res.items():
        print(k, {a: b for a, b in v.items() if a not in ("length_examples", "surface_mismatches", "active_permanent_missing")})


if __name__ == "__main__":
    main()
