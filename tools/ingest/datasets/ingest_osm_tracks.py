"""OpenStreetMap motorsport venues in the USA and Canada -> tracks_osm.json.

Data: (c) OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright). Any derived
database we ship must keep the attribution and stay ODbL (share-alike for the derived DB).

Access: the QLever SPARQL endpoint over the full OSM planet (osm2rdf, University of Freiburg,
https://qlever.dev/api/osm-planet). The main Overpass instance (overpass-api.de) has robots.txt
`Disallow: /api/`, and the public mirrors we tried (kumi.systems, private.coffee) timed out on
state-sized queries on 2026-10-06, so QLever is used: 2 queries total (USA, Canada), cached.

What is pulled: every OSM object inside the country relation that is highway=raceway, or has a
sport tag matching motor/karting/speedway/stock_car/dirt_track/drag_racing (horse/dog/rc/motocross-only excluded).
Objects are clustered into venues (same name within 3 km; unnamed raceway ways join the nearest
named venue within 1.5 km), then matched to ../../touring/existing_tracks.json (coords within 2 km
using the repo's data/tracks lat/lon, else exact name/alias in the same state).

Usage: python3 ingest_osm_tracks.py [--refresh]
"""
import collections
import json
import os
import re
import sys

from common import CACHE, HERE, ACCESSED, http_get, norm, haversine_km, dump_json, existing_tracks_with_coords, match_existing

ENDPOINT = "https://qlever.dev/api/osm-planet"
COUNTRIES = {"USA": 148838, "CAN": 1428125}
SPORT_RE = "motor|karting|speedway|stock_car|dirt_track|drag_racing|racing"
QUERY = """
PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX ogc: <http://www.opengis.net/rdf#>
PREFIX osmrel: <https://www.openstreetmap.org/relation/>
PREFIX osm2rdf: <https://osm2rdf.cs.uni-freiburg.de/rdf#>
SELECT ?osm (SAMPLE(?name_) AS ?name) (SAMPLE(?sport_) AS ?sport) (SAMPLE(?surface_) AS ?surface)
       (SAMPLE(?leisure_) AS ?leisure) (SAMPLE(?highway_) AS ?highway) (SAMPLE(?lentag_) AS ?length_tag)
       (SAMPLE(?wd_) AS ?wikidata) (SAMPLE(?web_) AS ?website) (SAMPLE(?glen_) AS ?geom_length_m)
       (SAMPLE(?area_) AS ?area) (SAMPLE(?c_) AS ?centroid) (SAMPLE(?iso_) AS ?iso)
WHERE {
  { ?osm osmkey:highway "raceway" } UNION { ?osm osmkey:sport ?s0 . FILTER(REGEX(?s0, "%SPORT%")) }
  ?osm ogc:sfIntersects osmrel:%REL% .
  ?osm geo:hasGeometry/geo:asWKT ?wkt . BIND(geof:centroid(?wkt) AS ?c_)
  OPTIONAL { ?osm osmkey:name ?name_ } OPTIONAL { ?osm osmkey:sport ?sport_ } OPTIONAL { ?osm osmkey:surface ?surface_ }
  OPTIONAL { ?osm osmkey:leisure ?leisure_ } OPTIONAL { ?osm osmkey:highway ?highway_ } OPTIONAL { ?osm osmkey:length ?lentag_ }
  OPTIONAL { ?osm osmkey:wikidata ?wd_ } OPTIONAL { ?osm osmkey:website ?web_ } OPTIONAL { ?osm osm2rdf:length ?glen_ }
  OPTIONAL { ?osm osm2rdf:area ?area_ }
  OPTIONAL { ?osm ogc:sfIntersects ?st . ?st osmkey:admin_level 4 ; osmkey:ISO3166-2 ?iso_ }
}
GROUP BY ?osm
"""
# Second pass: named facilities (no motorsport tags) whose name says speedway/raceway/... and whose
# main tag is a sports/recreation area (filters out the thousands of "Speedway" fuel stations).
NAME_RE = "speedway|raceway|motorsports? park|race ?track|dragway|drag strip|motorplex|kartway|motor park"
QUERY_NAMES = QUERY.replace(
    '{ ?osm osmkey:highway "raceway" } UNION { ?osm osmkey:sport ?s0 . FILTER(REGEX(?s0, "%SPORT%")) }',
    '?osm osmkey:name ?n0 . FILTER(REGEX(?n0, "%NAME%", "i")) '
    '{ ?osm osmkey:leisure ?l0 . FILTER(?l0 IN ("sports_centre", "stadium", "track", "pitch", "racetrack")) } '
    'UNION { ?osm osmkey:landuse "recreation_ground" } '
    'FILTER NOT EXISTS { ?osm osmkey:sport ?sx . FILTER(REGEX(?sx, "horse|dog|athletics|running|bmx|cycling")) }'
).replace("%NAME%", NAME_RE)

PAVED = {"asphalt", "paved", "concrete", "concrete:plates", "paving_stones", "chipseal", "tarmac"}
DIRT = {"dirt", "clay", "ground", "unpaved", "earth", "compacted", "gravel", "sand", "fine_gravel", "mud", "soil"}
EXCLUDE_SPORTS = {"horse_racing", "dog_racing", "rc_car", "motocross", "equestrian", "bmx", "cycling", "running", "athletics"}


def fetch(country, rel, refresh, by_name=False):
    dest = os.path.join(CACHE, "osm", f"qlever_{country}{'_names' if by_name else ''}.json")
    if refresh and os.path.exists(dest):
        os.remove(dest)
    q = (QUERY_NAMES if by_name else QUERY).replace("%SPORT%", SPORT_RE).replace("%REL%", str(rel))
    http_get(ENDPOINT, dest=dest, delay=5.0, method="POST", data={"query": q},
             headers={"Accept": "application/sparql-results+json"}, timeout=600)
    with open(dest, encoding="utf-8") as f:
        rows = json.load(f)["results"]["bindings"]
    out = []
    for b in rows:
        g = {k: v["value"] for k, v in b.items()}
        m = re.match(r"POINT\(([-\d.eE]+) ([-\d.eE]+)\)", g.get("centroid", ""))
        if not m:
            continue
        g["lon"], g["lat"] = float(m.group(1)), float(m.group(2))
        g["country"] = country
        g["found_by"] = "name" if by_name else "tags"
        g["osm_type"], g["osm_id"] = g["osm"].rsplit("/", 2)[-2:]
        out.append(g)
    return out


def keep(f):
    sports = set(re.split(r"[;,]\s*", f.get("sport") or ""))
    sports.discard("")
    if f.get("leisure") in ("bleachers", "grandstand"):
        return False
    if sports and sports <= EXCLUDE_SPORTS:
        return False
    if not sports and f.get("highway") != "raceway" and f.get("found_by") != "name":
        return False
    return True


def surface_cat(s):
    if not s:
        return None
    s = s.lower()
    if s in PAVED:
        return "paved"
    if s in DIRT:
        return "dirt"
    return "other"


def cluster(feats):
    named = [f for f in feats if f.get("name")]
    unnamed = [f for f in feats if not f.get("name")]
    parent = list(range(len(named)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_name = collections.defaultdict(list)
    for i, f in enumerate(named):
        by_name[norm(f["name"])].append(i)
    for idx in by_name.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                fa, fb = named[idx[a]], named[idx[b]]
                if haversine_km(fa["lat"], fa["lon"], fb["lat"], fb["lon"]) <= 3.0:
                    parent[find(idx[a])] = find(idx[b])
    # facility polygons that contain differently-named raceway ways (e.g. "X Speedway" area + "Oval" way): within 0.6 km
    fac = [i for i, f in enumerate(named) if f.get("leisure") in ("sports_centre", "stadium", "track")]
    for i in fac:
        for j, g in enumerate(named):
            if j != i and g.get("highway") == "raceway" and haversine_km(named[i]["lat"], named[i]["lon"], g["lat"], g["lon"]) <= 0.6:
                parent[find(j)] = find(i)
    groups = collections.defaultdict(list)
    for i, f in enumerate(named):
        groups[find(i)].append(f)
    groups = list(groups.values())
    cents = [(sum(x["lat"] for x in g) / len(g), sum(x["lon"] for x in g) / len(g)) for g in groups]
    orphans = []
    for f in unnamed:
        best, bd = None, 1.5
        for gi, (la, lo) in enumerate(cents):
            if abs(la - f["lat"]) > 0.03:
                continue
            d = haversine_km(la, lo, f["lat"], f["lon"])
            if d <= bd:
                best, bd = gi, d
        if best is None:
            orphans.append(f)
        else:
            groups[best].append(f)
    # unnamed raceway ways far from any named venue: cluster within 0.8 km; keep clusters >= 0.15 mi of raceway
    ugroups = []
    for f in orphans:
        for g in ugroups:
            if haversine_km(g[0]["lat"], g[0]["lon"], f["lat"], f["lon"]) <= 0.8:
                g.append(f)
                break
        else:
            ugroups.append([f])
    kept = [g for g in ugroups if sum(float(x.get("geom_length_m") or 0) for x in g) >= 240]
    dropped = len(orphans) - sum(len(g) for g in kept)
    return groups + kept, dropped


def venue(g):
    named = [x for x in g if x.get("name")]
    facility = [x for x in named if x.get("leisure") in ("sports_centre", "stadium", "track", "pitch") or x["osm_type"] == "relation"]
    names = collections.Counter(x["name"] for x in (facility or named))
    name = names.most_common(1)[0][0] if names else None
    ways = [x for x in g if x.get("highway") == "raceway"]
    anchor = max(facility, key=lambda x: float(x.get("area") or 0)) if facility else None
    if anchor:
        lat, lon = anchor["lat"], anchor["lon"]
    else:
        w = [(float(x.get("geom_length_m") or 1), x) for x in g]
        tot = sum(a for a, _ in w)
        lat, lon = sum(a * x["lat"] for a, x in w) / tot, sum(a * x["lon"] for a, x in w) / tot
    surf_len = collections.Counter()
    for x in ways or g:
        if x.get("surface"):
            surf_len[x["surface"].lower()] += float(x.get("geom_length_m") or 1)
    surface = surf_len.most_common(1)[0][0] if surf_len else None
    cats = {surface_cat(s) for s in surf_len}
    cats.discard(None)
    sports = sorted({s for x in g for s in re.split(r"[;,]\s*", x.get("sport") or "") if s})
    lens = sorted((float(x["geom_length_m"]) for x in ways if x.get("geom_length_m")), reverse=True)
    iso = collections.Counter(x["iso"] for x in g if x.get("iso")).most_common(1)
    lentag = next((x["length_tag"] for x in g if x.get("length_tag")), None)
    primary = anchor or max(g, key=lambda x: float(x.get("geom_length_m") or 0))
    kinds = []
    if "karting" in sports:
        kinds.append("karting")
    if "drag_racing" in sports or re.search(r"drag", name or "", re.I):
        kinds.append("drag")
    return {
        "name": name,
        "other_names": sorted(set(x["name"] for x in named) - {name})[:6],
        "found_by": sorted({x.get("found_by", "tags") for x in g}),
        "lat": round(lat, 6), "lon": round(lon, 6),
        "country": g[0]["country"],
        "state": iso[0][0].split("-")[-1] if iso else None,
        "surface": surface,
        "surface_category": ("mixed" if len(cats) > 1 else (cats.pop() if cats else None)),
        "length_tagged": lentag,
        "length_longest_raceway_way_mi": round(lens[0] / 1609.344, 3) if lens else None,
        "raceway_ways": len(ways), "raceway_total_mi": round(sum(lens) / 1609.344, 3) if lens else None,
        "sports": sports, "kinds": kinds,
        "osm_id": f"{primary['osm_type']}/{primary['osm_id']}",
        "osm_ids": sorted({f"{x['osm_type']}/{x['osm_id']}" for x in g})[:25],
        "wikidata": next((x["wikidata"] for x in g if x.get("wikidata")), None),
        "website": next((x["website"] for x in g if x.get("website")), None),
        "confidence": "medium" if (anchor or len(named) > 1) else "low",
        "unnamed": not named,
        "sources": ["src:osm-qlever"],
    }


def main():
    refresh = "--refresh" in sys.argv
    feats = []
    seen = set()
    for c, rel in COUNTRIES.items():
        rows = fetch(c, rel, refresh)
        feats += [f for f in rows if keep(f)]
        seen |= {f["osm"] for f in rows}
        extra = [f for f in fetch(c, rel, refresh, by_name=True) if f["osm"] not in seen]
        for f in extra:
            f.setdefault("sport", None)
        feats += extra
        print(c, "rows", len(rows), "name-only facilities", len(extra))
    groups, orphans = cluster(feats)
    venues = [venue(g) for g in groups]
    existing = existing_tracks_with_coords()
    matched = 0
    for v in venues:
        tid, how, dist = match_existing(v["name"] or "", v["lat"], v["lon"], v["state"], existing)
        v["existing_track_id"], v["match_method"], v["match_distance_km"] = tid, how, dist
        matched += bool(tid)
    # one primary venue per existing track: name-confirmed first, then nearest
    best = {}
    for i, v in enumerate(venues):
        if v["existing_track_id"]:
            key = (v["match_method"] != "coords+name", v["unnamed"], v["match_distance_km"] or 0)
            if v["existing_track_id"] not in best or key < best[v["existing_track_id"]][0]:
                best[v["existing_track_id"]] = (key, i)
    for i, v in enumerate(venues):
        v["match_primary"] = bool(v["existing_track_id"]) and best[v["existing_track_id"]][1] == i
    venues.sort(key=lambda v: (v["country"], v["state"] or "", v["name"] or "~"))
    hit_ids = {v["existing_track_id"] for v in venues if v["existing_track_id"]}
    missing = [t["id"] for t in existing if t["id"] not in hit_ids]
    out = {"source": "src:osm-qlever", "license": "ODbL 1.0 - (c) OpenStreetMap contributors",
           "accessed": ACCESSED, "endpoint": ENDPOINT,
           "notes": "length_longest_raceway_way_mi is the longest single highway=raceway way (OSM ways are often split, so it is a lower bound / rough guide, low confidence); surface is the length-weighted mode of raceway surfaces",
           "stats": {"features_kept": len(feats), "venues": len(venues), "unnamed_small_features_dropped": orphans,
                     "unnamed_venues": sum(v["unnamed"] for v in venues),
                     "venues_matched_to_existing": matched, "existing_tracks": len(existing),
                     "existing_tracks_found": len(hit_ids), "by_country": dict(collections.Counter(v["country"] for v in venues)),
                     "surface_category": dict(collections.Counter(v["surface_category"] for v in venues))},
           "existing_tracks_not_found": missing,
           "tracks": venues}
    dump_json(out, os.path.join(HERE, "tracks_osm.json"))
    print(json.dumps(out["stats"], indent=1))


if __name__ == "__main__":
    main()
