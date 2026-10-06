"""Step 40: normalise every source into one candidate schema.

Candidate keys: cid, src (source id), url, name, aliases, city, region, country, lat, lon, coord_src,
track_type, surface, length_mi, banking_deg, banking_cat, turns, opened, closed, active (True/False/None),
active_year, major_series, disciplines, classes, wp_title, qid, mrp_id, link, config, notes, kind ('venue'|
'drag'|'other'|'attrib' - attribution-only rows that must attach to another candidate).
Output: raw/cands.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from census_util import (ALL_NAMES, banking_category, disciplines_from_classes, parse_size_mi,
                         region_from_text, surface_from_text)
from wp_common import RAW, load, save
from wikitext_util import years

CUR = 2026
cands = []


def add(**kw):
    kw.setdefault("aliases", [])
    kw.setdefault("major_series", [])
    kw.setdefault("disciplines", [])
    kw.setdefault("classes", [])
    kw.setdefault("kind", "venue")
    kw["cid"] = f"c{len(cands)}"
    cands.append(kw)
    return kw


def wp_url(t):
    return "https://en.wikipedia.org/wiki/" + t.replace(" ", "_")


SURF_PAVED = ("asphalt", "concrete", "asphalt_concrete")


def wp_track_type(rec, lay):
    cats = " ".join(rec.get("categories", [])).lower()
    wc = set(rec.get("wd_classes", []))
    if lay and lay.get("kind") in ("oval", "road_course", "figure_eight", "kart_circuit", "roval"):
        return lay["kind"]
    if "street circuit" in wc or "street circuits" in cats or re.search(r"street circuit|grand prix circuit|street course", rec["name"].lower()):
        return "street_circuit"
    if "kart circuit" in wc or "karting venues" in cats:
        return "kart_circuit"
    if "figure 8" in cats or "figure-eight" in cats:
        return "figure_eight"
    if re.search(r"road courses in|road racing venues", cats) and not re.search(r"oval|speedway venues", cats):
        return "road_course"
    if re.search(r"dirt oval|paved oval|oval", cats):
        return "oval"
    if re.search(r"speedway|raceway|motor speedway|bowl|stadium", rec["name"].lower()):
        if lay and lay.get("turns") and lay["turns"] > 6:
            return "road_course"
        if re.search(r"speedway|bowl|stadium", rec["name"].lower()):
            return "oval"
    if lay and lay.get("turns"):
        return "oval" if lay["turns"] <= 4 else "road_course"
    return None


def is_drag_or_other(rec):
    cats = " ".join(rec.get("categories", [])).lower()
    wc = set(rec.get("wd_classes", []))
    n = rec["name"].lower()
    if re.search(r"dragway|dragstrip|drag strip|drag racing", n) or ("dragstrip" in wc and len(wc) == 1):
        return "drag"
    if ("drag racing venues" in cats or "dragstrips" in cats) and not re.search(
            r"road courses|oval|nascar|speedway venues|motorsport venues in", cats):
        return "drag"
    if re.search(r"horse racing|harness racing|racecourse|thoroughbred", cats + " " + " ".join(wc)) and not re.search(
            r"motorsport|auto racing|nascar|dirt oval|speedway venues", cats):
        return "other"
    if re.search(r"motocross|supercross|off-road racing venues", cats) and not re.search(r"oval|road courses|nascar", cats):
        return "other"
    return None


def from_wp():
    for r in load("cand_wp.json"):
        if r["source"] == "wd":
            add(src="src:wikidata", url=f"https://www.wikidata.org/wiki/{r['qid']}", name=r["name"],
                aliases=r.get("aliases", []), country=r.get("country"), lat=r["coord"][0], lon=r["coord"][1],
                coord_src="wikidata", qid=r["qid"], length_mi=r.get("length_mi") if r.get("length_mi") == r.get("length_mi") else None,
                opened=r.get("opened"), closed=r.get("closed"),
                track_type={"street circuit": "street_circuit", "kart circuit": "kart_circuit"}.get(
                    next((c for c in r["wd_classes"] if c in ("street circuit", "kart circuit")), None)),
                kind="drag" if r["wd_classes"] == ["dragstrip"] else "venue", wd_classes=r["wd_classes"])
            continue
        kind = is_drag_or_other(r) or "venue"
        lays = [l for l in r.get("layouts", []) if l.get("kind") not in ("drag", "other")]
        if r.get("layouts") and not lays:
            kind = "drag" if any(l.get("kind") == "drag" for l in r["layouts"]) else kind
        prim = lays[0] if lays else None
        # oval-named venues with several layouts: the oval is the primary racing surface
        ovals = [l for l in lays if l.get("kind") == "oval"]
        if ovals and prim is not ovals[0] and re.search(r"[óo]valo|oval|speedway|motor speedway", r["name"] + " " + r["wp_title"], re.I):
            prim = ovals[0]
            lays = [prim] + [l for l in lays if l is not prim]
        coord = r.get("coord") or [None, None]
        base = dict(src="src:wikipedia", url=wp_url(r["wp_title"]), name=r["name"], aliases=r.get("aliases", []),
                    city=r.get("city"), region=r.get("region"), country=r.get("country"), lat=coord[0], lon=coord[1],
                    coord_src="wikipedia" if r.get("coord") else None, opened=r.get("opened"), closed=r.get("closed"),
                    closed_src=r.get("closed_src"), closed_snippet=r.get("closed_snippet"),
                    major_series=r.get("major_series", []), wp_title=r["wp_title"], qid=r.get("qid"), kind=kind,
                    wp_categories=r.get("categories", []), defunct_category=r.get("defunct_category"),
                    wd_classes=r.get("wd_classes", []))
        if r.get("closed") or r.get("defunct_category"):
            base["active"] = False
        tt = wp_track_type(r, prim)
        cfg = "; ".join(f"{l.get('layout') or 'layout'}: {l.get('length_mi') or '?'} mi {l.get('surface') or ''}".strip()
                        for l in lays[:4]) or None
        bdeg = _bank_deg(prim.get("banking_raw")) if prim else None
        add(**base, track_type=tt, surface=prim.get("surface") if prim else None,
            length_mi=prim.get("length_mi") if prim else None, turns=prim.get("turns") if prim else None,
            banking_deg=bdeg, banking_raw=prim.get("banking_raw") if prim else None, config=cfg)
        # a genuinely different racing surface at the same facility (dirt vs paved)
        if prim and prim.get("surface"):
            pc = "dirt" if prim["surface"] in ("dirt", "clay") else "paved"
            for l in lays[1:]:
                ln = l.get("layout") or ""
                # only a surface that exists alongside the primary one (not an earlier/temporary version)
                sequential = bool(re.search(r"original|temporary|former|old\b", ln, re.I)) or (
                    bool(re.search(r"\d{4}", ln)) and "present" not in ln.lower())
                if l.get("surface") and ("dirt" if l["surface"] in ("dirt", "clay") else "paved") != pc \
                        and l.get("kind") in ("oval", None, "figure_eight") and not sequential:
                    b2 = dict(base)
                    b2["name"] = f"{r['name']} {'dirt' if l['surface'] in ('dirt', 'clay') else 'paved'} oval"
                    b2["wp_title"] = None
                    b2["secondary_of"] = r["wp_title"]
                    add(**b2, track_type="oval", surface=l["surface"], length_mi=l.get("length_mi"),
                        turns=l.get("turns"), banking_deg=_bank_deg(l.get("banking_raw")))
                    break


def _bank_deg(txt):
    if not txt:
        return None
    m = re.findall(r"(\d+(?:\.\d+)?)\s*°", txt)
    if not m:
        m = re.findall(r"(\d+(?:\.\d+)?)\s*(?:degrees|deg)", txt, re.I)
    vals = [float(x) for x in m if 0 <= float(x) <= 45]
    return max(vals) if vals else None


def from_fr_es():
    for k, p in load("wp_fr_es_pages.json").items():
        if not p.get("coord"):
            continue
        add(src="src:frwiki" if p["lang"] == "fr" else "src:eswiki",
            url=f"https://{p['lang']}.wikipedia.org/wiki/" + p["title"].replace(" ", "_"), name=p["title"],
            lat=p["coord"][0], lon=p["coord"][1], coord_src=p["lang"] + "wiki", qid=p.get("qid"),
            country="CAN" if p["lang"] == "fr" else "MEX", kind="venue_weak")


LIST_SRC = {"List_of_auto_racing_tracks_in_the_United_States": "src:wp-list-us-tracks",
            "List_of_dirt_track_ovals_in_the_United_States": "src:wp-list-us-dirt-ovals",
            "List_of_dirt_track_ovals_in_Canada": "src:wp-list-canada-dirt-ovals",
            "List_of_auto_racing_tracks_in_Canada": "src:wp-list-canada-tracks",
            "List_of_auto_racing_tracks_in_Mexico": "src:wp-list-mexico-tracks",
            "List_of_NASCAR_tracks": "src:wp-list-nascar-tracks",
            "List_of_American_Championship_Car_racetracks": "src:wp-list-champcar-tracks",
            "List_of_sports_venues_in_North_Carolina": "src:wp-list-nc-venues"}


def from_lists():
    for r in load("wp_list_entries.json"):
        lst = r["list"]
        sec = (r.get("section") or "").lower()
        if lst == "List_of_sports_venues_in_North_Carolina" and "race tracks" not in sec:
            continue
        if re.search(r"drag", sec):
            kind = "drag"
        else:
            kind = "venue"
        name = re.sub(r"\s*\(.*?\)\s*$", "", r["name"]).strip(" *")
        name = re.split(r";", name)[0].strip()
        if not name or len(name) < 3 or re.match(r"^[\d.]+ ?mi", name):
            continue
        reg, country = region_from_text(r.get("region") or "")
        if not reg:
            reg, country = region_from_text(r.get("city") or "")
        if not country:
            country = {"USA": "USA", "Canada": "CAN", "Mexico": "MEX"}.get(r.get("country"))
        city = r.get("city")
        if city:
            city = re.split(r",|\(", city)[0].strip() or None
            if city and region_from_text(city)[0] and city in ALL_NAMES:
                city = None
        tt, surf = None, surface_from_text(r.get("surface"))
        shape = (r.get("shape") or "") + " " + sec
        if "figure" in sec:
            tt = "figure_eight"
        elif "road" in sec:
            tt = "road_course"
        elif "street" in sec or "temporary" in sec:
            tt = "street_circuit"
        elif re.search(r"oval|superspeedway|intermediate|mile tracks|short tracks|dirt", sec) or "oval" in shape.lower():
            tt = "oval"
        if not surf:
            surf = surface_from_text(shape)
        if "dirt" in sec and not surf:
            surf = "dirt"
        if "paved" in sec and not surf:
            surf = "asphalt"
        length = r.get("length_mi") or parse_size_mi(r.get("shape") or "")
        opened = closed = None
        oy = years(r.get("opened_raw") or "")
        if oy:
            opened = oy[0]
            if len(oy) > 1:
                closed = oy[-1]
        cy = years(r.get("closed_raw") or "")
        if cy:
            closed = cy[-1]
        active = None
        if r.get("defunct_shading") or "defunct" in sec or closed:
            active = False
        series = [s for s in (r.get("series_links") or r.get("series") or []) if s and len(s) > 2]
        coord = r.get("coord")
        link = (r.get("link") or "").split("#")[0] or None
        if link:
            link = link[0].upper() + link[1:]
        add(src=LIST_SRC[lst], url=wp_url(lst), name=name, city=city, region=reg, country=country,
            lat=coord[0] if coord else None, lon=coord[1] if coord else None,
            coord_src="wikipedia-list" if coord else None, track_type=tt, surface=surf, length_mi=length,
            opened=opened, closed=closed, active=active,
            major_series=series if ("nascar" not in lst.lower() and "championship" not in lst.lower()) else [],
            link=link, kind=kind, list_section=r.get("section"), seasons_raw=r.get("seasons_raw"),
            banking_raw=r.get("banking_raw"))


def from_imca():
    p = os.path.join(RAW, "dir", "imca_tracks.json")
    if not os.path.exists(p):
        return
    for r in json.load(open(p)):
        reg, country = region_from_text(r.get("state_name") or "")
        if not reg and r.get("address_lines"):
            reg, country = region_from_text(", ".join(r["address_lines"]))
        ss = r.get("size_surface") or ""
        divs = [d.strip() for d in re.split(r",", r.get("divisions") or "") if d.strip()]
        add(src="src:imca-track-directory", url=r["url"], name=r["name"], city=r.get("city"), region=reg,
            country=country, lat=r.get("lat"), lon=r.get("lon"), coord_src="imca-geocoded-address" if r.get("lat") else None,
            track_type="figure_eight" if "figure" in ss.lower() else "oval", surface=surface_from_text(ss),
            length_mi=parse_size_mi(ss), banking_cat=banking_category(text=ss) if "bank" in ss.lower() or "flat" in ss.lower() else None,
            active=True, active_year=CUR, active_src="src:imca-track-directory",
            major_series=["IMCA Speedway Motors Weekly Racing"], classes=["IMCA " + d for d in divs],
            website=r.get("website"), size_raw=ss)


def from_wissota():
    p = os.path.join(RAW, "dir", "wissota_tracks.json")
    for r in json.load(open(p)):
        d = r.get("description") or ""
        add(src="src:wissota-tracks", url="https://www.wissota.org/Tracks/Current", name=r["name"], city=r["city"],
            region=r["region"], country="CAN" if r["region"] in ("ON", "MB", "SK", "AB", "BC") else "USA",
            mrp_id=r["mrp_id"], track_type="oval" if "oval" in d.lower() else None, surface=surface_from_text(d),
            length_mi=parse_size_mi(d), banking_cat=banking_category(text=d), active=True, active_year=CUR,
            active_src="src:wissota-tracks", major_series=["WISSOTA"], classes=["WISSOTA"], kind="attrib_or_venue",
            size_raw=d, website=r.get("website"))


def from_nascar_local():
    for r in json.load(open(os.path.join(RAW, "dir", "nascar_local_2026.json"))):
        link = r["link"] if not r.get("frwiki") else None
        add(src="src:wp-nascar-local-racing-series", url=wp_url("NASCAR_Local_Racing_Series"), name=r["name"],
            city=r["city"], region=r["region"], country=r["country"], link=link, surface=surface_from_text(r["desc"]),
            length_mi=parse_size_mi(r["desc"]), track_type="oval", active=True, active_year=CUR,
            active_src="src:wp-nascar-local-racing-series", major_series=["NASCAR Local Racing Series"], kind="attrib")


MRP_SHAPE = {"oval": "oval", '"d" oval': "oval", "d oval": "oval", "tri-oval": "oval", "trioval": "oval",
             "figure 8": "figure_eight", "figure eight": "figure_eight", "road course": "road_course",
             "egg": "oval", "triangle": "oval", "square": "oval", "paperclip": "oval", "kidney": "oval",
             "kart": "kart_circuit", "road": "road_course", "flat track": "oval", "rectangle": "oval"}


def from_mrp():
    p = os.path.join(RAW, "dir", "mrp_tracks.jsonl")
    if not os.path.exists(p):
        return
    for line in open(p):
        r = json.loads(line)
        if r.get("error") or r["name"].upper().startswith("ZZZ"):
            continue  # "ZZZ_" profiles are MyRacePass's archived/duplicate placeholders
        na = lambda v: None if (v is None or v.strip().upper() in ("N/A", "", "NA")) else v.strip()
        size, bank, comp, shape = na(r.get("size")), na(r.get("banking")), na(r.get("composition")), na(r.get("shape"))
        ev = r.get("event_years") or []
        tt = None
        if shape:
            sl = shape.lower()
            tt = next((v for k, v in MRP_SHAPE.items() if k in sl), None)
            if tt is None and "drag" in sl:
                tt = "drag"
        place = r.get("page_place") or r.get("place")
        reg, country = region_from_text(place)
        city = place.split(",")[0].strip() if place and "," in place else None
        active, ay = None, None
        if ev and max(ev) >= 2025:
            active, ay = True, min(max(ev), CUR)  # events listed for next season also count as current
        surf = surface_from_text(comp)
        if comp and comp.lower() in ("gumbo",):
            surf = "dirt"
        inferred = False
        szm = parse_size_mi(size or "")
        if tt is None and not (shape and "drag" in shape.lower()) and szm and szm <= 1.0 and r.get("classes") \
                and not re.search(r"drag|pull|derby|mud", " ".join(r.get("classes", [])), re.I):
            tt, inferred = "oval", True  # short track running oval-track classes; profile leaves shape blank
        add(src="src:myracepass", url=r["url"], name=r["name"], city=city, region=reg, country=country, type_inferred=inferred,
            lat=r.get("lat"), lon=r.get("lon"), coord_src="myracepass-map" if r.get("lat") else None,
            mrp_id=r["id"], track_type=tt if tt != "drag" else None, surface=surf, length_mi=parse_size_mi(size or ""),
            banking_cat=banking_category(text=bank), active=active, active_year=ay,
            active_src="src:myracepass" if active else None, classes=r.get("classes", []),
            kind="drag" if tt == "drag" else "mrp", size_raw=size, banking_raw=bank, shape_raw=shape,
            comp_raw=comp, last_event_year=min(max(ev), CUR) if ev else None, mrp_claimed=r.get("claimed"))


if __name__ == "__main__":
    from_wp()
    from_fr_es()
    from_lists()
    from_imca()
    from_wissota()
    from_nascar_local()
    from_mrp()
    save("cands.json", cands)
    import collections
    print(len(cands), collections.Counter(c["src"] for c in cands))
