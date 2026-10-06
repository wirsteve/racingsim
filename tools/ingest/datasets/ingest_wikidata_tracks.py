"""Wikidata racetracks in the USA and Canada -> tracks_wikidata.json.

License: Wikidata structured data is CC0 1.0 (public domain dedication).
Access: query.wikidata.org SPARQL endpoint, User-Agent per RULES.md, 1-2 queries total, cached.

Items selected: instance of (a subclass of) motorsport racing track (Q2338524), street circuit (Q926439),
dragstrip (Q357121), kart circuit (Q1232319), or anything with a Racing-Reference track ID (P6807);
country (P17) USA or Canada.  Horse/dog/harness venues are excluded.

Each item is matched to ../../touring/existing_tracks.json (coords within 2 km using the repo's
data/tracks lat/lon, preferring name-confirmed candidates; else exact name/alias in the same state).

Usage: python3 ingest_wikidata_tracks.py [--refresh]
"""
import collections
import json
import os
import re
import sys

from common import CACHE, HERE, ACCESSED, http_get, dump_json, existing_tracks_with_coords, match_existing, haversine_km

ENDPOINT = "https://query.wikidata.org/sparql"
QUERY = """
SELECT ?item ?itemLabel ?article ?coord ?iso ?admLabel
       (GROUP_CONCAT(DISTINCT ?clsLabel; separator="|") AS ?classes)
       (SAMPLE(?lenAmt) AS ?len) (SAMPLE(?lenUnit) AS ?unit)
       (SAMPLE(?inc) AS ?inception) (SAMPLE(?open) AS ?opened) (SAMPLE(?close) AS ?closed)
       (SAMPLE(?osmway) AS ?osm_way) (SAMPLE(?osmrel) AS ?osm_rel) (SAMPLE(?rr) AS ?rr_id)
       (SAMPLE(?web) AS ?website) (SAMPLE(?slope) AS ?banking) (SAMPLE(?ctry) AS ?country)
WHERE {
  VALUES ?ctry { wd:Q30 wd:Q16 }
  { ?item wdt:P31/wdt:P279* ?root . VALUES ?root { wd:Q2338524 wd:Q926439 wd:Q357121 wd:Q1232319 } }
  UNION { ?item wdt:P6807 [] }
  ?item wdt:P17 ?ctry .
  FILTER NOT EXISTS { ?item wdt:P31/wdt:P279* ?bad . VALUES ?bad { wd:Q11822917 wd:Q53585538 wd:Q778020 } }
  ?item wdt:P31 ?cls .
  OPTIONAL { ?item wdt:P625 ?coord }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?item wdt:P131 ?adm }
  OPTIONAL { ?item wdt:P131+ ?a2 . ?a2 wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "US-") || STRSTARTS(?iso, "CA-")) }
  OPTIONAL { ?item p:P2043/psv:P2043 [ wikibase:quantityAmount ?lenAmt ; wikibase:quantityUnit ?lenUnit ] }
  OPTIONAL { ?item wdt:P571 ?inc } OPTIONAL { ?item wdt:P1619 ?open } OPTIONAL { ?item wdt:P3999 ?close }
  OPTIONAL { ?item wdt:P10689 ?osmway } OPTIONAL { ?item wdt:P402 ?osmrel } OPTIONAL { ?item wdt:P6807 ?rr }
  OPTIONAL { ?item wdt:P856 ?web } OPTIONAL { ?item wdt:P4184 ?slope }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en".
    ?item rdfs:label ?itemLabel . ?cls rdfs:label ?clsLabel . ?adm rdfs:label ?admLabel . }
}
GROUP BY ?item ?itemLabel ?article ?coord ?iso ?admLabel
"""
UNIT_TO_MI = {"Q253276": 1.0, "Q828224": 0.621371, "Q11573": 0.000621371, "Q174789": 0.000621371 * 1e-3, "Q3710": 0.000189394}


def year(v):
    m = re.match(r"(-?\d{4})", v or "")
    return int(m.group(1)) if m else None


def main():
    refresh = "--refresh" in sys.argv
    dest = os.path.join(CACHE, "wikidata", "racetracks_us_ca.json")
    if refresh and os.path.exists(dest):
        os.remove(dest)
    http_get(ENDPOINT, dest=dest, delay=1.0, params={"query": QUERY, "format": "json"},
             headers={"Accept": "application/sparql-results+json"}, timeout=300)
    with open(dest, encoding="utf-8") as f:
        rows = json.load(f)["results"]["bindings"]
    items = collections.OrderedDict()
    for b in rows:
        g = {k: v["value"] for k, v in b.items()}
        qid = g["item"].rsplit("/", 1)[-1]
        it = items.setdefault(qid, {"qid": qid, "name": g.get("itemLabel"), "isos": collections.Counter(),
                                    "adm": set(), "classes": set(), "g": g})
        if g.get("iso"):
            it["isos"][g["iso"]] += 1
        if g.get("admLabel"):
            it["adm"].add(g["admLabel"])
        it["classes"] |= set(filter(None, (g.get("classes") or "").split("|")))
        for k in ("coord", "article", "len", "unit", "inception", "opened", "closed", "osm_way", "osm_rel", "rr_id", "website", "banking"):
            if g.get(k) and not it["g"].get(k):
                it["g"][k] = g[k]
    existing = existing_tracks_with_coords()
    out = []
    for qid, it in items.items():
        g = it["g"]
        lat = lon = None
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", g.get("coord") or "")
        if m:
            lon, lat = float(m.group(1)), float(m.group(2))
        # prefer the most specific (state/province) code; P131+ can also pick up ancestors of neighbours
        state = None
        if it["isos"]:
            state = it["isos"].most_common(1)[0][0].split("-", 1)[1]
        length_mi = None
        if g.get("len") and g.get("unit"):
            f = UNIT_TO_MI.get(g["unit"].rsplit("/", 1)[-1])
            if f:
                length_mi = round(float(g["len"]) * f, 3)
        rec = {
            "wikidata_id": qid, "name": it["name"],
            "enwiki": g["article"].rsplit("/", 1)[-1] if g.get("article") else None,
            "lat": lat, "lon": lon,
            "country": "USA" if g.get("country", "").endswith("Q30") else "CAN",
            "state": state, "admin_area": sorted(it["adm"])[:3],
            "classes": sorted(it["classes"]),
            "length_mi": length_mi,
            "opened": year(g.get("opened")) or year(g.get("inception")),
            "closed": year(g.get("closed")),
            "banking_deg": float(g["banking"]) if g.get("banking") else None,
            "osm_way_id": g.get("osm_way"), "osm_relation_id": g.get("osm_rel"),
            "racing_reference_track_id": g.get("rr_id"),
            "website": g.get("website"),
            "confidence": "medium", "sources": ["src:wikidata-racetracks"],
        }
        tid, how, dist = match_existing(rec["name"], lat, lon, state, existing)
        rec["existing_track_id"], rec["match_method"], rec["match_distance_km"] = tid, how, dist
        out.append(rec)
    # primary match per existing track
    best = {}
    for i, r in enumerate(out):
        if r["existing_track_id"]:
            key = (r["match_method"] != "coords+name", r["match_distance_km"] or 0)
            if r["existing_track_id"] not in best or key < best[r["existing_track_id"]][0]:
                best[r["existing_track_id"]] = (key, i)
    for i, r in enumerate(out):
        r["match_primary"] = bool(r["existing_track_id"]) and best[r["existing_track_id"]][1] == i
    out.sort(key=lambda r: (r["country"], r["state"] or "", r["name"] or ""))
    hit = {r["existing_track_id"] for r in out if r["existing_track_id"]}
    stats = {"items": len(out), "with_coords": sum(r["lat"] is not None for r in out),
             "with_enwiki": sum(bool(r["enwiki"]) for r in out), "with_length": sum(r["length_mi"] is not None for r in out),
             "with_racing_reference_id": sum(bool(r["racing_reference_track_id"]) for r in out),
             "with_osm_id": sum(bool(r["osm_way_id"] or r["osm_relation_id"]) for r in out),
             "closed_items": sum(r["closed"] is not None for r in out),
             "matched_to_existing": sum(bool(r["existing_track_id"]) for r in out), "existing_tracks_found": len(hit),
             "by_country": dict(collections.Counter(r["country"] for r in out))}
    dump_json({"source": "src:wikidata-racetracks", "license": "CC0 1.0 (Wikidata)", "accessed": ACCESSED,
               "endpoint": ENDPOINT, "stats": stats,
               "existing_tracks_not_found": [t["id"] for t in existing if t["id"] not in hit],
               "tracks": out}, os.path.join(HERE, "tracks_wikidata.json"))
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
