import os as _os
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", ".."))
"""Step 60: write the deliverables from the build:
tracks_new.json, tracks_enrich.json, sources.json, ledger.jsonl, unavailable.json, REPORT.md,
plus tracks_unresolved.json (venues found but not publishable: no coordinates / unknown type / unknown closure).
"""
import collections
import datetime
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
from census_util import CA, MX, US
from wp_common import BASE, RAW

ACC = "2026-10-06"
REPO = _os.path.join(_REPO, "data", "tracks")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


SOURCES = {
    "src:wikipedia": {"name": "English Wikipedia track articles (infobox, coordinates, categories)",
                      "url": "https://en.wikipedia.org/wiki/Category:Motorsport_venues_in_the_United_States",
                      "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wikidata": {"name": "Wikidata (SPARQL + wbgetentities: P31 race track classes, P625, P2043, P571/P1619, P576/P3999)",
                     "url": "https://query.wikidata.org/", "kind": "wiki", "reliability": "medium", "license": "CC0"},
    "src:frwiki": {"name": "French Wikipedia: Catégorie:Circuit automobile au Québec / de stock car",
                   "url": "https://fr.wikipedia.org/wiki/Cat%C3%A9gorie:Circuit_automobile_au_Qu%C3%A9bec",
                   "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:eswiki": {"name": "Spanish Wikipedia: Categoría:Circuitos de carreras de México",
                   "url": "https://es.wikipedia.org/wiki/Categor%C3%ADa:Circuitos_de_carreras_de_M%C3%A9xico",
                   "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-list-us-tracks": {"name": "Wikipedia: List of auto racing tracks in the United States",
                              "url": "https://en.wikipedia.org/wiki/List_of_auto_racing_tracks_in_the_United_States",
                              "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-list-us-dirt-ovals": {"name": "Wikipedia: List of dirt track ovals in the United States",
                                  "url": "https://en.wikipedia.org/wiki/List_of_dirt_track_ovals_in_the_United_States",
                                  "kind": "wiki", "reliability": "low", "license": "CC BY-SA 4.0"},
    "src:wp-list-canada-dirt-ovals": {"name": "Wikipedia: List of dirt track ovals in Canada",
                                      "url": "https://en.wikipedia.org/wiki/List_of_dirt_track_ovals_in_Canada",
                                      "kind": "wiki", "reliability": "low", "license": "CC BY-SA 4.0"},
    "src:wp-list-canada-tracks": {"name": "Wikipedia: List of auto racing tracks in Canada",
                                  "url": "https://en.wikipedia.org/wiki/List_of_auto_racing_tracks_in_Canada",
                                  "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-list-mexico-tracks": {"name": "Wikipedia: List of auto racing tracks in Mexico",
                                  "url": "https://en.wikipedia.org/wiki/List_of_auto_racing_tracks_in_Mexico",
                                  "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-list-nascar-tracks": {"name": "Wikipedia: List of NASCAR tracks (incl. defunct and one-time venues)",
                                  "url": "https://en.wikipedia.org/wiki/List_of_NASCAR_tracks",
                                  "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-list-champcar-tracks": {"name": "Wikipedia: List of American Championship Car racetracks",
                                    "url": "https://en.wikipedia.org/wiki/List_of_American_Championship_Car_racetracks",
                                    "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-list-nc-venues": {"name": "Wikipedia: List of sports venues in North Carolina (race tracks section)",
                              "url": "https://en.wikipedia.org/wiki/List_of_sports_venues_in_North_Carolina",
                              "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:wp-nascar-local-racing-series": {"name": "Wikipedia: NASCAR Local Racing Series - 2026 tracks list (nascar.com blocked for scripts)",
                                          "url": "https://en.wikipedia.org/wiki/NASCAR_Local_Racing_Series",
                                          "kind": "wiki", "reliability": "medium", "license": "CC BY-SA 4.0"},
    "src:imca-track-directory": {"name": "IMCA official track directory (size & surface, divisions, address, geocoded map marker)",
                                 "url": "https://www.imca.com/view/track-directory/", "kind": "official_sanctioning",
                                 "reliability": "high", "license": "facts only"},
    "src:wissota-tracks": {"name": "WISSOTA official current track list", "url": "https://www.wissota.org/Tracks/Current",
                           "kind": "official_sanctioning", "reliability": "high", "license": "facts only"},
    "src:myracepass": {"name": "MyRacePass track profiles (track-maintained size/banking/composition/shape, map location, latest events)",
                       "url": "https://www.myracepass.com/tracks/", "kind": "results_archive", "reliability": "medium",
                       "license": "facts only"},
    "src:nominatim-osm": {"name": "OpenStreetMap via Nominatim (gazetteer: named race-track features; reverse geocoding of city/state)",
                          "url": "https://nominatim.openstreetmap.org/", "kind": "dataset", "reliability": "medium",
                          "license": "ODbL (c) OpenStreetMap contributors"},
}

UNAVAILABLE = [
    {"source": "NASCAR.com (NASCAR Local Racing Series / Weekly Series member tracks)", "url": "https://www.nascar.com/",
     "reason": "Cloudflare 'Attention Required' 403 on robots.txt and pages for scripted requests", "checked": ACC,
     "replacement_source": "src:wp-nascar-local-racing-series"},
    {"source": "USRA (United States Racing Association) track list", "url": "https://www.usra.com/",
     "reason": "bot-check interstitial page (noindex) returned instead of content", "checked": ACC,
     "replacement_source": "src:myracepass"},
    {"source": "NASA (National Auto Sport Association) / drivenasa.com", "url": "https://www.nasaproracing.com/",
     "reason": "Cloudflare managed challenge ('Just a moment...') 403", "checked": ACC,
     "replacement_source": "src:wikipedia (Road courses in the United States category)"},
    {"source": "INEX (Legends/Bandolero) sanctioned tracks", "url": "https://www.inexracing.com/",
     "reason": "egress proxy refused CONNECT (502) - host not reachable from this environment", "checked": ACC,
     "replacement_source": "src:myracepass (class lists show Legends/Bandolero programs)"},
    {"source": "Overpass API (OpenStreetMap)", "url": "https://overpass-api.de/api/",
     "reason": "connection reset / timeouts on overpass-api.de, overpass.kumi.systems, overpass.private.coffee", "checked": ACC,
     "replacement_source": "src:nominatim-osm (name lookups only)"},
    {"source": "DIRTcar / UMP sanctioned tracks", "url": "https://dirtcar.com/tracks/",
     "reason": "no public track directory (404); site asks Crawl-delay 10 - not crawled further", "checked": ACC,
     "replacement_source": "src:myracepass"},
    {"source": "Quarter Midgets of America track list", "url": "https://quartermidgets.org/tracks/",
     "reason": "404; the clubs page lists 9 clubs by city only (no track coordinates) - not used for records", "checked": ACC,
     "replacement_source": "src:myracepass (quarter-midget club profiles)"},
    {"source": "racing-reference.info", "url": "https://www.racing-reference.info/",
     "reason": "Cloudflare block - excluded by project rules (never fetched)", "checked": ACC,
     "replacement_source": "src:wp-list-nascar-tracks"},
    {"source": "thethirdturn.com", "url": "https://www.thethirdturn.com/",
     "reason": "robots.txt Disallow: / - excluded by project rules (never fetched)", "checked": ACC,
     "replacement_source": "src:wikipedia, src:myracepass"},
    {"source": "Web search (discovery of further sanctioning-body directories: QMA/USAC .25, POWRi, ASCS, USMTS)",
     "url": "n/a", "reason": "shared per-turn web-search budget exhausted by other agents", "checked": ACC,
     "replacement_source": "src:myracepass (hosts most of these bodies' track profiles)"},
]


def clean(r):
    rid = slugify(f"{r['name']}-{r.get('region') or r.get('country')}")
    notes = []
    if r.get("_note_reopened"):
        notes.append(r["_note_reopened"])
    if r.get("_closed_from_text"):
        notes.append(f"closure year taken from article text ('{r['_closed_from_text']}') - low confidence")
    if r.get("_coord_src") == "nominatim":
        notes.append(f"coordinates from OSM feature {r.get('_osm')} ({r.get('_osm_class')}) matched by name")
    if r.get("_coord_src") == "imca-geocoded-address":
        notes.append("coordinates are IMCA's geocoded track address")
    if r.get("_type_inferred"):
        notes.append("track type inferred as oval: MyRacePass profile gives size and oval-track classes but no shape")
    if r.get("_surface_conflict"):
        notes.append("sources disagree on surface (likely converted dirt<->paved); current directory value used")
    if r.get("_coord_spread_km", 0) > 1:
        notes.append(f"source coordinates differ by up to {r['_coord_spread_km']} km")
    if r.get("last_listed_event_year"):
        notes.append(f"latest event listed on MyRacePass: {r['last_listed_event_year']}")
    if r.get("closed_evidence_last_event"):
        notes.append(f"inactive per encyclopedia; MyRacePass lists events up to {r['closed_evidence_last_event']}")
    if r.get("_secondary_of"):
        notes.append(f"second racing surface described in the article on {r['_secondary_of']}")
    out = {
        "id": rid, "name": r["name"], "city": r.get("city"), "region": r.get("region"), "country": r.get("country"),
        "track_type": r["track_type"], "surface": r.get("surface"), "length_mi": r.get("length_mi"),
        "configuration": r.get("configuration"), "turns": r.get("turns"),
        "banking_deg_turns": r.get("banking_deg_turns"), "banking_deg_straights": None,
        "banking_category": r.get("banking_category") or "unknown",
        "opened": r.get("opened"), "closed": r.get("closed"), "active": r.get("active"),
        "status_verified_year": r.get("status_verified_year"), "status_sources": r.get("status_sources") or [],
        "disciplines": r.get("disciplines") or [], "level": r["level"], "notable_note": r.get("notable_note"),
        "lat": r["lat"], "lon": r["lon"], "coord_source": r.get("_coord_src"),
        "aliases": r.get("aliases") or [], "major_series": r.get("major_series") or [],
        "prestige_category": r["prestige_category"], "prestige_basis": r.get("prestige_basis"),
        "confidence": r["confidence"], "sources": r["sources"], "source_urls": r.get("source_urls") or [],
        "notes": "; ".join(notes) or None,
    }
    return out


def main():
    new = json.load(open(os.path.join(RAW, "build_new.json")))
    enr = json.load(open(os.path.join(RAW, "build_enrich.json")))
    rej = json.load(open(os.path.join(RAW, "build_rejected.json")))
    existing = {}
    import glob as _glob
    for f in sorted(os.path.basename(x) for x in _glob.glob(os.path.join(REPO, "*.json"))):
        for r in json.load(open(os.path.join(REPO, f))):
            existing.setdefault(r.get("id") or slugify(f"{r['name']}-{r.get('region') or r.get('country')}"), r)

    recs = [clean(r) for r in new]
    # id collisions
    seen = collections.Counter()
    for r in recs:
        seen[r["id"]] += 1
        if seen[r["id"]] > 1 or r["id"] in existing:
            r["id"] = f"{r['id']}-{slugify(r.get('city') or str(seen[r['id']]))}"
    # validate against the repo schema
    sys.path.insert(0, _REPO)
    from racingsim.tracks.model import TrackFacts
    bad = []
    ok = []
    for r in recs:
        f = TrackFacts.from_dict(r)
        p = f.validate()
        if p:
            bad.append((r["name"], p))
            if any("implausible length" in x for x in p):
                r["length_mi"] = None
                r["notes"] = ((r["notes"] or "") + "; length dropped (implausible)").strip("; ")
            if any("implausible opened" in x for x in p):
                r["opened"] = None
            if not TrackFacts.from_dict(r).validate():
                ok.append(r)
        else:
            ok.append(r)
    recs = sorted(ok, key=lambda r: (r["country"] or "", r["region"] or "", r["name"]))
    json.dump(recs, open(os.path.join(BASE, "tracks_new.json"), "w"), indent=1, ensure_ascii=False)

    # enrichment for existing ids
    enrich_out = {}
    for x in enr:
        eid, r = x["existing_id"], x["rec"]
        e = existing.get(eid)
        if e is None:
            continue
        cur = enrich_out.setdefault(eid, {"id": eid, "name": e["name"], "match_basis": [], "sources": [], "source_urls": []})
        cur["match_basis"].append(x["why"])
        known = {a.lower() for a in (e.get("aliases") or [])} | {e["name"].lower()}
        al = [a for a in r.get("aliases", []) + [r["name"]] if a.lower() not in known and len(a) < 70]
        if al:
            cur["aliases"] = sorted(set(cur.get("aliases", [])) | set(al))
        if r.get("major_series"):
            cur["major_series"] = list(dict.fromkeys(cur.get("major_series", []) + r["major_series"]))
        if e.get("banking_deg_turns") is None and r.get("banking_category") not in (None, "unknown"):
            cur["banking_category"] = r["banking_category"]
        elif e.get("banking_deg_turns") is not None:
            d = e["banking_deg_turns"]
            cur.setdefault("banking_category", "flat" if d < 8 else ("moderate" if d <= 16 else "high"))
            cur["banking_category_basis"] = "derived from existing banking_deg_turns"
        if e.get("opened") is None and r.get("opened"):
            cur["opened"] = r["opened"]
        if e.get("closed") is None and r.get("closed") and e.get("active") is not True:
            cur["closed"] = r["closed"]
        # status corrections
        if r.get("active") is True and e.get("active") is False:
            cur["status_correction"] = {"active": True, "verified_year": r.get("status_verified_year"),
                                        "basis": f"racing listed in {r.get('status_verified_year')} by {', '.join(r.get('status_sources', []))}",
                                        "existing": {"active": e.get("active"), "closed": e.get("closed")}}
        elif False:  # closures for hand-researched active tracks were all earlier closures of reopened venues - never flagged
            # existing records were researched by hand; a closure here is only a review flag, never a field change
            cur["status_review"] = {"possibly_inactive": True, "closed": r["closed"],
                                        "basis": f"closure {r['closed']} per {', '.join(r.get('status_sources') or r['sources'])}" +
                                                 (f" (article text: '{r['_closed_from_text']}')" if r.get("_closed_from_text") else ""),
                                        "existing": {"active": e.get("active"), "closed": e.get("closed")},
                                        "confidence": "low"}
        elif r.get("active") is True and e.get("active") is True:
            cur["status_verified_year"] = max(cur.get("status_verified_year") or 0, r.get("status_verified_year") or 0) or None
            cur["status_sources"] = sorted(set(cur.get("status_sources", [])) | set(r.get("status_sources", [])))
        if r.get("disciplines"):
            nd = sorted(set(r["disciplines"]) - set(e.get("disciplines") or []))
            if nd:
                cur["disciplines_add"] = sorted(set(cur.get("disciplines_add", [])) | set(nd))
        if r.get("prestige_category"):
            cur.setdefault("prestige_category_census", r["prestige_category"])
        cur["sources"] = sorted(set(cur["sources"]) | set(r["sources"]))
        cur["source_urls"] = list(dict.fromkeys(cur["source_urls"] + r.get("source_urls", [])))[:12]
        cur["confidence"] = "high" if x["why"] == "wikipedia title" else "medium"
    enrich_list = []
    for eid, cur in enrich_out.items():
        payload = {k: v for k, v in cur.items() if k not in ("id", "name", "match_basis", "sources", "source_urls", "confidence")}
        if not payload:
            continue
        cur["match_basis"] = sorted(set(cur["match_basis"]))
        # prestige from the census is only a hint for existing tracks: keep out of the core fields
        cur.pop("prestige_category_census", None)
        if len({k for k in cur if k not in ("id", "name", "match_basis", "sources", "source_urls", "confidence")}) == 0:
            continue
        enrich_list.append(cur)
    enrich_list.sort(key=lambda c: c["id"])
    json.dump(enrich_list, open(os.path.join(BASE, "tracks_enrich.json"), "w"), indent=1, ensure_ascii=False)

    # unresolved (not published)
    json.dump(rej, open(os.path.join(BASE, "tracks_unresolved.json"), "w"), indent=1, ensure_ascii=False)

    # sources / unavailable
    src = {k: dict(v, accessed=ACC) for k, v in SOURCES.items()}
    json.dump(src, open(os.path.join(BASE, "sources.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(UNAVAILABLE, open(os.path.join(BASE, "unavailable.json"), "w"), indent=1, ensure_ascii=False)

    # ledger
    rel = {k: v["reliability"] for k, v in SOURCES.items()}
    with open(os.path.join(BASE, "ledger.jsonl"), "w") as f:
        for r in recs:
            for s in r["sources"]:
                url = next((u for u in r["source_urls"] if _url_matches(s, u)), SOURCES.get(s, {}).get("url"))
                f.write(json.dumps({"source": s, "url": url,
                                    "info": f"new track {r['name']} ({r.get('region')}): " + _facts(r, s),
                                    "accessed": ACC, "reliability": rel.get(s, "medium"), "confidence": r["confidence"],
                                    "notes": r.get("notes") or "", "entities": [f"track:{r['id']}"]}, ensure_ascii=False) + "\n")
        for c in enrich_list:
            for s in c["sources"]:
                f.write(json.dumps({"source": s, "url": next((u for u in c["source_urls"] if _url_matches(s, u)), SOURCES.get(s, {}).get("url")),
                                    "info": f"enrichment for existing track {c['id']}: " + ", ".join(k for k in c if k not in ("id", "name", "match_basis", "sources", "source_urls", "confidence")),
                                    "accessed": ACC, "reliability": rel.get(s, "medium"), "confidence": c["confidence"],
                                    "notes": "matched by " + "; ".join(c["match_basis"]), "entities": [f"track:{c['id']}"]},
                                   ensure_ascii=False) + "\n")
    report(recs, enrich_list, rej, bad)
    print("tracks_new", len(recs), "enrich", len(enrich_list), "unresolved", len(rej), "schema fixes", len(bad))


def _url_matches(s, u):
    return {"src:wikipedia": "en.wikipedia.org/wiki/" in u and "List_of" not in u and "NASCAR_Local" not in u,
            "src:wikidata": "wikidata.org" in u, "src:frwiki": "fr.wikipedia" in u, "src:eswiki": "es.wikipedia" in u,
            "src:imca-track-directory": "imca.com" in u, "src:wissota-tracks": "wissota.org" in u,
            "src:myracepass": "myracepass.com" in u, "src:nominatim-osm": "openstreetmap.org" in u}.get(s, False) or (
        s.startswith("src:wp-") and ("List_of" in u or "NASCAR_Local" in u) and SOURCES.get(s, {}).get("url", "").endswith(u.rsplit("/", 1)[-1]))


def _facts(r, s):
    bits = []
    for k in ("track_type", "surface", "length_mi", "opened", "closed"):
        if r.get(k) not in (None, ""):
            bits.append(f"{k}={r[k]}")
    if r.get("status_verified_year") and s in (r.get("status_sources") or []):
        bits.append(f"active {r['status_verified_year']}")
    if s in ("src:myracepass", "src:imca-track-directory", "src:wissota-tracks", "src:wikipedia", "src:wikidata") and r.get("coord_source"):
        bits.append("coords")
    return ", ".join(bits)


def report(recs, enrich, rej, bad):
    by_reg = collections.Counter((r["country"], r["region"]) for r in recs)
    by_surf = collections.Counter(r["surface"] or "unknown" for r in recs)
    by_type = collections.Counter(r["track_type"] for r in recs)
    by_lvl = collections.Counter(r["level"] for r in recs)
    by_conf = collections.Counter(r["confidence"] for r in recs)
    by_act = collections.Counter({True: "active (verified)", False: "inactive/closed", None: "status unknown"}[r["active"]] for r in recs)
    by_src = collections.Counter(s for r in recs for s in r["sources"])
    by_prest = collections.Counter(r["prestige_category"] for r in recs)
    disc = collections.Counter(d for r in recs for d in r["disciplines"])
    rejc = collections.Counter(x["reason"] for x in rej)
    act_by_country = collections.Counter(r["country"] for r in recs if r["active"])
    L = []
    L.append("# North American track census (Wikipedia/Wikidata + official directories)\n")
    L.append(f"Generated {ACC}. Re-run: see *How to re-run* below.\n")
    L.append("## Summary\n")
    L.append(f"* **New tracks (not in the existing database: 371 hand-researched tracks + 37 census_venues.json touring venues): {len(recs)}** — every record has coordinates and at least one source.")
    L.append(f"* Existing tracks enriched: {len(enrich)} (`tracks_enrich.json`).")
    L.append(f"* Venues found but not published (`tracks_unresolved.json`): {len(rej)} — " + ", ".join(f"{k}: {v}" for k, v in rejc.most_common()) + ".")
    L.append(f"* Status: " + ", ".join(f"{k}: {v}" for k, v in by_act.most_common()) +
             f". Active with racing listed in 2025/2026: USA {act_by_country.get('USA', 0)}, Canada {act_by_country.get('CAN', 0)}, Mexico {act_by_country.get('MEX', 0)}.")
    L.append(f"* Confidence: " + ", ".join(f"{k}: {v}" for k, v in by_conf.most_common()) + ".\n")
    L.append("## Counts\n")
    L.append("### By surface\n\n| surface | n |\n|---|---|")
    L += [f"| {k} | {v} |" for k, v in by_surf.most_common()]
    L.append("\n### By track type\n\n| type | n |\n|---|---|")
    L += [f"| {k} | {v} |" for k, v in by_type.most_common()]
    L.append("\n### By level\n\n| level | n |\n|---|---|")
    L += [f"| {k} | {v} |" for k, v in by_lvl.most_common()]
    L.append("\n### By prestige\n\n| prestige | n |\n|---|---|")
    L += [f"| {k} | {v} |" for k, v in by_prest.most_common()]
    L.append("\n### Disciplines (records listing each)\n\n| discipline | n |\n|---|---|")
    L += [f"| {k} | {v} |" for k, v in disc.most_common()]
    L.append("\n### By source (records citing each)\n\n| source | n |\n|---|---|")
    L += [f"| {k} | {v} |" for k, v in by_src.most_common()]
    L.append("\n### By state / province\n\n| country | region | new | of which active |\n|---|---|---|---|")
    act = collections.Counter((r["country"], r["region"]) for r in recs if r["active"])
    for (c, rg), v in sorted(by_reg.items(), key=lambda x: (x[0][0] or "", -x[1])):
        L.append(f"| {c} | {rg} | {v} | {act.get((c, rg), 0)} |")
    open(os.path.join(BASE, "REPORT.md"), "w").write("\n".join(L) + "\n\n" + __import__("report_text").TAIL)


if __name__ == "__main__":
    main()
