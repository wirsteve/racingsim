import os as _os
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", ".."))
"""Step 50: cluster candidates into venues, match against the existing track database,
resolve each field by source priority, and write tracks_new.json / tracks_enrich.json.

    python3 -I scripts/50_build.py [--geocode]

--geocode enables Nominatim lookups (cached in raw/nominatim_cache.json) for list-only
venues without coordinates and reverse geocoding of missing city/state.
"""
import collections
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from census_util import (US, CA, MX, banking_category, core_tokens, disciplines_from_classes, haversine_km,
                         name_sim, norm_name, region_from_text, surface_from_text)
from wp_common import BASE, RAW, load

REPO = _os.path.join(_REPO, "data", "tracks")
GEOCODE = "--geocode" in sys.argv
CUR = 2026

# ----------------------------------------------------------------------------- existing
def slugify(text):
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


existing = []
import glob as _glob
for f in sorted(os.path.basename(x) for x in _glob.glob(os.path.join(REPO, "*.json"))):
    for r in json.load(open(os.path.join(REPO, f))):
        r = dict(r)
        r["id"] = r.get("id") or slugify(f"{r['name']}-{r.get('region') or r.get('country')}")
        r["_wp"] = set()
        for s in r.get("sources", []):
            if "wikipedia.org/wiki/" in s:
                r["_wp"].add(urllib.parse.unquote(s.split("/wiki/")[1]).replace("_", " ").split("#")[0])
            elif "wikipedia.org/w/index.php" in s:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(s.split(" ")[0]).query)
                if q.get("title"):
                    r["_wp"].add(q["title"][0].replace("_", " "))
        existing.append(r)
ex_by_id = {}
for r in existing:
    ex_by_id.setdefault(r["id"], r)
existing = list(ex_by_id.values())

# ----------------------------------------------------------------------------- candidates
cands = load("cands.json")
pages = load("wp_pages.json")
resolve = {}
for req, pg in pages.items():
    if pg.get("title"):
        resolve[req] = pg["title"]
        resolve[pg["title"]] = pg["title"]


def canon_title(t):
    if not t:
        return None
    t = t[0].upper() + t[1:]
    return resolve.get(t, t)


GEO_ASSIGN_P = os.path.join(RAW, "geo_assign.json")
_ga = json.load(open(GEO_ASSIGN_P)) if os.path.exists(GEO_ASSIGN_P) else {}
for c in cands:
    k = f"{c['src']}|{c['name']}|{c.get('region')}"
    if c.get("lat") is None and k in _ga:
        g = _ga[k]
        c.update(lat=g["lat"], lon=g["lon"], coord_src="nominatim", osm=g.get("osm"), osm_class=g.get("osm_class"))
wp_alias = {c["wp_title"]: c.get("aliases", []) for c in cands if c.get("src") == "src:wikipedia" and c.get("wp_title")}
wp_nick = {}
for c in cands:
    c["wp_title"] = canon_title(c.get("wp_title"))
    if c.get("link"):
        tgt = canon_title(c["link"])
        lk = c["link"][0].upper() + c["link"][1:]
        # a redirect may point at a different venue's article (e.g. a former track merged into a
        # successor's page): only trust it when the row's own name resembles the target title
        tgt_base = re.sub(r"\s*\(.*?\)$", "", tgt)
        def _jac(x, y):
            a, b = core_tokens(x), core_tokens(y)
            return len(a & b) / len(a | b) if (a | b) else (1.0 if norm_name(x) == norm_name(y) else 0.0)
        surf_words = lambda t: set(re.findall(r"\b(dirt|bullring|kart|karts|drag|dragway|road course|figure)\b", t.lower()))
        if surf_words(c["name"]) != surf_words(tgt_base) or norm_name(c["name"]) != norm_name(tgt_base) and _jac(c["name"], tgt_base) <= 0.5 and not any(_jac(a, c["name"]) > 0.5 for a in
                                                         wp_alias.get(tgt, []) + wp_nick.get(tgt, [])):
            c["link_redirect_ignored"] = tgt
            tgt = None
        c["link"] = tgt
    if c.get("lat") is not None and not (14 <= c["lat"] <= 72 and -170 <= c["lon"] <= -50):
        c["outside_na"] = True

# ----------------------------------------------------------------------------- union-find
parent = {c["cid"]: c["cid"] for c in cands}


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


# cannot-link constraint: two different Wikipedia articles, or two different IMCA directory
# entries, describe two different venues (a redirect resolves to the same title, so it still links)
cl_keys = {c["cid"]: ({c["wp_title"]} if c.get("src") == "src:wikipedia" and c.get("wp_title") else
                      ({c["secondary_of"] + "#second-surface"} if c.get("secondary_of") else set()),
                      {c["url"]} if c.get("src") == "src:imca-track-directory" else set()) for c in cands}
refused = []


def union(a, b, force=False):
    ra, rb = find(a), find(b)
    if ra == rb:
        return
    wa, ia = cl_keys[ra]
    wb, ib = cl_keys[rb]
    if not force and ((wa and wb and not (wa & wb)) or (ia and ib and not (ia & ib))):
        refused.append((a, b))
        return
    parent[rb] = ra
    cl_keys[ra] = (wa | wb, ia | ib)


by = collections.defaultdict(list)
for c in cands:
    if c.get("wp_title"):
        by[("wp", c["wp_title"])].append(c["cid"])
    if c.get("link"):
        by[("wp", c["link"])].append(c["cid"])
    if c.get("qid"):
        by[("q", c["qid"])].append(c["cid"])
    if c.get("mrp_id"):
        by[("m", c["mrp_id"])].append(c["cid"])
for k, ids in by.items():
    for x in ids[1:]:
        union(ids[0], x)

SURF_CLASS = lambda s: None if not s else ("dirt" if s in ("dirt", "clay") else "paved")
TYPE_CLASS = lambda t: None if not t else ("oval" if t in ("oval", "figure_eight") else ("road" if t in ("road_course", "roval", "street_circuit") else t))


def compatible(a, b, sim):
    sa, sb = SURF_CLASS(a.get("surface")), SURF_CLASS(b.get("surface"))
    ta, tb = TYPE_CLASS(a.get("track_type")), TYPE_CLASS(b.get("track_type"))
    if ta and tb and ta != tb and norm_name(a["name"]) != norm_name(b["name"]):
        return False
    if sa and sb and sa != sb and sim < 0.95:
        return False
    # drag strips only merge with drag strips (or the same name)
    if (a.get("kind") == "drag") != (b.get("kind") == "drag") and norm_name(a["name"]) != norm_name(b["name"]):
        return False
    # two ovals of clearly different length at one complex are separate racing surfaces
    la, lb = a.get("length_mi"), b.get("length_mi")
    if la and lb and max(la, lb) / min(la, lb) > 1.6 and norm_name(a["name"]) != norm_name(b["name"]):
        return False
    return True


geo = [c for c in cands if c.get("lat") is not None and not c.get("outside_na")]
# grid bucket
grid = collections.defaultdict(list)
for c in geo:
    grid[(round(c["lat"] * 20), round(c["lon"] * 20))].append(c)
for c in geo:
    gx, gy = round(c["lat"] * 20), round(c["lon"] * 20)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for o in grid[(gx + dx, gy + dy)]:
                if o["cid"] <= c["cid"]:
                    continue
                d = haversine_km((c["lat"], c["lon"]), (o["lat"], o["lon"]))
                if d > 2.0:
                    continue
                sim = name_sim(c["name"], o["name"])
                if any(name_sim(a, o["name"]) > sim for a in c.get("aliases", [])):
                    sim = max(name_sim(a, o["name"]) for a in c.get("aliases", []))
                if (c["kind"] == "drag") != (o["kind"] == "drag") and sim < 0.6:
                    continue
                diff_src = c.get("src") != o.get("src") or c.get("src") == "src:myracepass"
                if (sim >= 0.6 or (d <= 0.6 and diff_src)) and compatible(c, o, sim):
                    if sim < 0.3:
                        # different names on the same spot: only merge if surfaces & types agree explicitly
                        same_surf = SURF_CLASS(c.get("surface")) and SURF_CLASS(c.get("surface")) == SURF_CLASS(o.get("surface"))
                        same_type = c.get("track_type") and c.get("track_type") == o.get("track_type")
                        if not (same_surf or (same_type and (not c.get("surface") or not o.get("surface")))):
                            continue
                    union(c["cid"], o["cid"])

# same name, same state, coordinates disagree (>2 km): one source has bad coordinates
_byname = collections.defaultdict(list)
for c in geo:
    _byname[norm_name(c["name"])].append(c)
for k, xs in _byname.items():
    for i, a in enumerate(xs):
        for o in xs[i + 1:]:
            d = haversine_km((a["lat"], a["lon"]), (o["lat"], o["lon"]))
            same_reg = a.get("region") and a.get("region") == o.get("region")
            lim = 80 if same_reg else (30 if not (a.get("region") and o.get("region")) else 0)
            if 2.0 < d < lim and compatible(a, o, 1.0) and find(a["cid"]) != find(o["cid"]):
                union(a["cid"], o["cid"])

# Wikipedia coordinates shared by two differently named articles are suspect (copied coordinates)
_wpc = collections.defaultdict(set)
for c in cands:
    if c.get("src") == "src:wikipedia" and c.get("lat") is not None and c.get("wp_title"):
        _wpc[(round(c["lat"], 3), round(c["lon"], 3))].add(c["wp_title"])
SUSPECT = {k for k, v in _wpc.items() if len(v) > 1}

# candidates without coordinates: attach by name + region
clusters = collections.defaultdict(list)
for c in cands:
    clusters[find(c["cid"])].append(c)


def cl_has_coord(cl):
    return any(x.get("lat") is not None for x in cl)


name_index = collections.defaultdict(set)
for root, cl in clusters.items():
    for x in cl:
        for n in [x["name"]] + x.get("aliases", []):
            name_index[(norm_name(n), x.get("region"))].add(root)
for c in cands:
    root = find(c["cid"])
    if cl_has_coord(clusters[root]):
        continue
    hits = set()
    for n in [c["name"]] + c.get("aliases", []):
        hits |= {r for r in name_index.get((norm_name(n), c.get("region")), set()) if r != root and cl_has_coord(clusters[r])}
    if len(hits) == 1:
        union(next(iter(hits)), c["cid"])
clusters = collections.defaultdict(list)
for c in cands:
    clusters[find(c["cid"])].append(c)

# second pass for still-uncoordinated: fuzzy name within same region
for root, cl in list(clusters.items()):
    if cl_has_coord(cl):
        continue
    c = cl[0]
    best = []
    for r2, cl2 in clusters.items():
        if r2 == root or not cl_has_coord(cl2):
            continue
        if not any(x.get("region") == c.get("region") and c.get("region") for x in cl2):
            continue
        import difflib
        s = max(max((difflib.SequenceMatcher(None, norm_name(a["name"]), norm_name(b["name"])).ratio()
                 if core_tokens(a["name"]) == core_tokens(b["name"]) else 0),
                (0.9 if core_tokens(a["name"]) and core_tokens(a["name"]) == core_tokens(b["name"]) and a.get("city")
                 and norm_name(a["city"]) == norm_name(b.get("city") or "") else 0)) for a in cl for b in cl2)
        if s >= 0.85:
            best.append((s, r2))
    best.sort(reverse=True)
    if best and (len(best) == 1 or best[0][0] > best[1][0]):
        union(best[0][1], root)
clusters = collections.defaultdict(list)
for c in cands:
    clusters[find(c["cid"])].append(c)
print("clusters:", len(clusters))

# ----------------------------------------------------------------------------- field resolution
P_NAME = ["src:wikipedia", "src:wikidata", "src:imca-track-directory", "src:wissota-tracks", "src:myracepass",
          "src:wp-list-us-tracks", "src:wp-list-canada-tracks", "src:wp-list-mexico-tracks", "src:wp-list-us-dirt-ovals",
          "src:wp-list-canada-dirt-ovals", "src:wp-list-nascar-tracks", "src:wp-list-champcar-tracks",
          "src:wp-nascar-local-racing-series", "src:frwiki", "src:eswiki", "src:wp-list-nc-venues", "src:nominatim"]
P_COORD = ["wikipedia", "wikidata", "wikipedia-list", "myracepass-map", "imca-geocoded-address", "frwiki", "eswiki", "nominatim"]
P_LOC = ["src:wikipedia", "src:imca-track-directory", "src:wissota-tracks", "src:myracepass", "src:wp-list-us-tracks",
         "src:wp-list-canada-tracks", "src:wp-list-mexico-tracks", "src:wp-nascar-local-racing-series",
         "src:wp-list-us-dirt-ovals", "src:wp-list-canada-dirt-ovals", "src:wp-list-nascar-tracks", "src:wikidata"]
P_TYPE = ["src:wikipedia", "src:wp-list-us-tracks", "src:wp-list-canada-tracks", "src:wp-list-mexico-tracks",
          "src:myracepass", "src:wissota-tracks", "src:imca-track-directory", "src:wp-list-us-dirt-ovals",
          "src:wp-list-canada-dirt-ovals", "src:wp-nascar-local-racing-series", "src:wp-list-nascar-tracks", "src:wikidata"]
P_SURF_CURRENT = ["src:imca-track-directory", "src:wissota-tracks", "src:myracepass", "src:wp-nascar-local-racing-series"]
P_LEN = ["src:wikipedia", "src:wp-list-us-tracks", "src:wp-list-canada-tracks", "src:wp-list-mexico-tracks",
         "src:imca-track-directory", "src:wissota-tracks", "src:myracepass", "src:wp-nascar-local-racing-series",
         "src:wikidata", "src:wp-list-nascar-tracks"]


def pick(cl, key, order, by="src"):
    rank = {s: i for i, s in enumerate(order)}
    xs = [x for x in cl if x.get(key) not in (None, "", [])]
    if not xs:
        return None, None
    xs.sort(key=lambda x: rank.get(x.get(by), 99))
    return xs[0][key], xs[0]


SERIES_JUNK = re.compile(r"warped tour|site of the first|^nascar$|world rally|formula d$|drag racing|\bnhra\b|ihra|"
                        r"international hot rod|superbike|motocross|^\d{4} ", re.I)
SERIES_CANON = [
    (r"^NASCAR (Cup|Grand National|Winston Cup|Sprint Cup|Monster Energy)|^Grand National Series$|^Winston Cup$|NASCAR Grand National", "NASCAR Cup Series"),
    (r"K&N Pro Series West|Winston West|NASCAR Southwest|AutoZone Elite Division, Southwest|West Series races", "ARCA Menards Series West"),
    (r"NASCAR Canada Series|Canadian Tire Series|Pinty", "NASCAR Canada Series (Pinty's)"),
    (r"Championship Auto Racing Teams|^CART\b", "American championship car racing (AAA/USAC/CART/Champ Car)"),
    (r"Atlantic Championship", "Atlantic Championship"),
    (r"American Speed Association|^ASA\b", "American Speed Association"),
    (r"^NASCAR (Xfinity|Busch|Nationwide|O'Reilly Auto Parts)( Grand National)? Series", "NASCAR Xfinity Series"),
    (r"^NASCAR (Craftsman |Camping World |Gander (Outdoors |RV & Outdoors )?)?Truck", "NASCAR Craftsman Truck Series"),
    (r"^ARCA Menards Series East|^NASCAR (K&N Pro Series East|Busch East|Busch North)", "ARCA Menards Series East"),
    (r"^ARCA Menards Series West|^NASCAR (K&N Pro Series West|Winston West|Southwest)", "ARCA Menards Series West"),
    (r"^ARCA (Menards|Racing|Re/Max|Bondo)", "ARCA Menards Series"),
    (r"IndyCar|Indy Racing League|^IRL", "IndyCar Series"),
    (r"Champ Car|CART|American Championship car racing|AAA Championship|USAC Championship Car", "American championship car racing (AAA/USAC/CART/Champ Car)"),
    (r"NASCAR (Mexico|Corona|Toyota|PEAK Mexico)", "NASCAR Mexico Series"),
    (r"Whelen Modified|NASCAR Modified Tour|Featherlite Modified", "NASCAR Whelen Modified Tour"),
    (r"World of Outlaws", "World of Outlaws"),
    (r"Lucas Oil Late Model", "Lucas Oil Late Model Dirt Series"),
    (r"IMSA|WeatherTech|American Le Mans|Grand-Am|Rolex Sports Car", "IMSA SportsCar Championship (and predecessors)"),
    (r"Formula One|United States Grand Prix|Canadian Grand Prix|Mexican Grand Prix|Mexico City Grand Prix", "Formula One"),
    (r"Trans.?Am", "Trans-Am Series"),
    (r"SCCA", "SCCA club racing"),
    (r"CARS Tour", "CARS Tour"),
    (r"Pro All Stars|^PASS", "Pro All Stars Series"),
    (r"American Canadian Tour|^ACT\b", "American Canadian Tour"),
    (r"CASCAR", "CASCAR"),
]


def canon_series(s):
    s = s.strip()
    for pat, name in SERIES_CANON:
        if re.search(pat, s, re.I):
            return name
    return s


NATIONAL = {"NASCAR Cup Series", "NASCAR Xfinity Series", "NASCAR Craftsman Truck Series", "ARCA Menards Series",
            "IndyCar Series", "American championship car racing (AAA/USAC/CART/Champ Car)", "NASCAR Canada Series (Pinty's)",
            "NASCAR Mexico Series", "World of Outlaws", "Lucas Oil Late Model Dirt Series",
            "IMSA SportsCar Championship (and predecessors)", "Trans-Am Series", "CASCAR", "Atlantic Championship",
            "American Speed Association", "USAC National Midget Series", "Can-Am", "USF2000 Championship",
            "Barber Pro Series", "GT World Challenge America"}
INTERNATIONAL = {"Formula One", "Formula E", "World Touring Car Championship", "FIA World Endurance Championship"}
REGIONAL_PAT = re.compile(r"ARCA Menards Series (East|West)|Whelen Modified|CARS Tour|Pro All Stars|American Canadian Tour|"
                          r"CASCAR|ARCA Midwest|Super DIRTcar|USAC|ASCS|POWRi|USMTS|CRA\b|Champion Racing|"
                          r"SMART Modified|Southern Super|Tour|Series|Championship|Cup", re.I)
LOCAL_PAT = re.compile(r"NASCAR Local Racing Series|IMCA Speedway Motors Weekly|WISSOTA|weekly", re.I)


def nascar_list_series(x):
    """NASCAR list rows: section tells which national series, seasons_raw the years."""
    sec = (x.get("list_section") or "")
    yrs = x.get("seasons_raw") or ""
    m = re.findall(r"(19\d\d|20\d\d)", yrs)
    span = f" ({m[0]}" + (f"–{m[-1]}" if len(m) > 1 and m[-1] != m[0] else "") + ")" if m else ""
    which = "NASCAR national series"
    if "Truck" in yrs:
        which = "NASCAR Craftsman Truck Series"
    elif "Xfinity" in yrs or "Busch" in yrs:
        which = "NASCAR Xfinity Series"
    elif "Grand National" in yrs or "Cup" in yrs or "championship" in sec.lower() or "Defunct" in sec:
        which = "NASCAR Cup Series"
    return which + span


def build_record(cl):
    srcs = sorted({x["src"] for x in cl})
    name, nx = pick(cl, "name", P_NAME)
    rec = {"name": name}
    # coordinates: group the options that agree (<3 km); prefer the group backed by more
    # independent coordinate sources, then by source priority; never a coordinate copied between articles
    cs = [x for x in cl if x.get("lat") is not None and not x.get("outside_na")]
    rank = {s: i for i, s in enumerate(P_COORD)}
    suspect = lambda x: x.get("coord_src") == "wikipedia" and (round(x["lat"], 3), round(x["lon"], 3)) in SUSPECT
    groups = []
    for x in sorted(cs, key=lambda x: (suspect(x), rank.get(x.get("coord_src"), 99))):
        for g in groups:
            if haversine_km((g[0]["lat"], g[0]["lon"]), (x["lat"], x["lon"])) < 3:
                g.append(x)
                break
        else:
            groups.append([x])
    groups.sort(key=lambda g: (-len({y.get("coord_src") for y in g if y.get("coord_src") != "wikipedia-list"} | ({"list"} if any(y.get("coord_src") == "wikipedia-list" for y in g) else set())),
                               suspect(g[0]), rank.get(g[0].get("coord_src"), 99)))
    if cs:
        best = groups[0][0]
        rec["lat"], rec["lon"] = round(best["lat"], 5), round(best["lon"], 5)
        rec["_coord_src"] = best["coord_src"]
        if best.get("coord_src") == "nominatim":
            rec["_osm"], rec["_osm_class"] = best.get("osm"), best.get("osm_class")
            rec["_osm_assigned"] = True
        rec["_coord_spread_km"] = round(max([haversine_km((best["lat"], best["lon"]), (g[0]["lat"], g[0]["lon"])) for g in groups[1:]] or [0]), 2)
        rec["_coord_options"] = [{"src": g[0]["coord_src"], "lat": g[0]["lat"], "lon": g[0]["lon"], "n": len(g)} for g in groups]
        rec["_coord_tie"] = len(groups) > 1 and len({y.get("coord_src") for y in groups[0]}) == len({y.get("coord_src") for y in groups[1]})
    else:
        rec["lat"] = rec["lon"] = None
    city, _ = pick([x for x in cl if not (x.get("city") and re.search(r"[\d°@\"]|https?:", x["city"]))], "city", P_LOC)
    region, _ = pick(cl, "region", P_LOC)
    country, _ = pick(cl, "country", P_LOC)
    if region and not country:
        country = "USA" if region in US.values() else ("CAN" if region in CA.values() else ("MEX" if region in MX.values() else None))
    rec.update(city=city, region=region, country=country)
    tt, tx = pick(cl, "track_type", P_TYPE)
    rec["track_type"] = tt
    rec["_type_inferred"] = bool(tx and tx.get("type_inferred"))
    # surface: current official directory beats encyclopedia (tracks get paved / return to dirt)
    cur = [x for x in cl if x["src"] in P_SURF_CURRENT and x.get("surface")]
    rank = {s: i for i, s in enumerate(P_SURF_CURRENT)}
    cur.sort(key=lambda x: rank.get(x["src"], 99))
    surf_all = {x["src"]: x["surface"] for x in cl if x.get("surface")}
    if cur:
        rec["surface"] = cur[0]["surface"]
    else:
        rec["surface"], _ = pick(cl, "surface", P_TYPE)
    rec["_surface_conflict"] = len({SURF_CLASS(s) for s in surf_all.values()}) > 1
    ln, lx = pick(cl, "length_mi", P_LEN)
    if ln is not None and not (0.05 <= ln <= 15):
        ln = None
    rec["length_mi"] = round(ln, 3) if ln else None
    cfg, _ = pick(cl, "config", ["src:wikipedia"])
    rec["configuration"] = cfg
    trn, _ = pick(cl, "turns", ["src:wikipedia"])
    rec["turns"] = trn
    bd, _ = pick(cl, "banking_deg", ["src:wikipedia"])
    rec["banking_deg_turns"] = bd
    bc = banking_category(deg=bd) if bd is not None else None
    if bc is None:
        bc, _ = pick(cl, "banking_cat", ["src:myracepass", "src:wissota-tracks", "src:imca-track-directory"])
    if bc is None:
        braw, _ = pick(cl, "banking_raw", ["src:wp-list-canada-tracks", "src:wp-list-nascar-tracks"])
        if braw:
            m = re.findall(r"(\d+(?:\.\d+)?)\s*°", braw)
            if m:
                rec["banking_deg_turns"] = max(float(v) for v in m)
                bc = banking_category(deg=rec["banking_deg_turns"])
            else:
                bc = banking_category(text=braw)
    rec["banking_category"] = bc or "unknown"
    op, _ = pick(cl, "opened", ["src:wikipedia", "src:wikidata", "src:wp-list-us-tracks", "src:wp-list-canada-tracks",
                                "src:wp-list-mexico-tracks"])
    clo, _ = pick(cl, "closed", ["src:wikipedia", "src:wikidata", "src:wp-list-us-tracks", "src:wp-list-canada-tracks",
                                 "src:wp-list-mexico-tracks"])
    rec["opened"], rec["closed"] = op, clo
    ctx = next((x for x in cl if x.get("closed") == clo and x.get("closed_src")), None)
    if clo and ctx and ctx.get("closed_src") == "wikipedia-text":
        rec["_closed_from_text"] = ctx.get("closed_snippet")
    # status
    act_true = [x for x in cl if x.get("active") is True and x.get("active_year")]
    act_false = [x for x in cl if x.get("active") is False]
    mrp_last = max([x.get("last_event_year") or 0 for x in cl if x["src"] == "src:myracepass"] or [0])
    if act_true:
        y = max(x["active_year"] for x in act_true)
        rec["active"] = True
        rec["status_verified_year"] = y
        rec["status_sources"] = sorted({x.get("active_src") or x["src"] for x in act_true})
        if clo and clo < y:
            rec["_note_reopened"] = f"encyclopedia lists closure {clo}, but racing listed in {y}"
            rec["closed"] = None
    elif act_false or clo:
        rec["active"] = False
        rec["status_verified_year"] = None
        rec["status_sources"] = sorted({x["src"] for x in act_false})
        if mrp_last and (not clo or mrp_last > clo):
            rec["closed_evidence_last_event"] = mrp_last
    else:
        rec["active"] = None
        rec["status_verified_year"] = None
        rec["status_sources"] = []
        if mrp_last:
            rec["last_listed_event_year"] = mrp_last
    # aliases
    al = []
    for x in cl:
        if x.get("kind") == "drag" or x.get("secondary_of"):
            continue  # a drag strip's or second surface's name is not an alias of the circuit
        raw = []
        for n in [x["name"]] + x.get("aliases", []):
            # "A, B" / "A B C" run-togethers from plain lists: split on commas between venue names
            parts = [q.strip() for q in re.split(r",\s+(?=[A-Z])", n)] if "," in n else [n]
            raw += parts
        for n in raw:
            n = re.sub(r"\s+", " ", n).strip()
            words = n.lower().split()
            if len(words) != len(set(words)) and len(words) > 4:
                continue  # garbled concatenation
            if n and norm_name(n) != norm_name(name) and norm_name(n) not in {norm_name(a) for a in al} and len(n) < 60:
                if not re.search(r"\(.*(layout|oval|dirt|asphalt|clay).*\)|(dirt|paved) oval$|karts?$|dragway|drag strip", n, re.I):
                    al.append(n)
    rec["aliases"] = al[:8]
    # series
    ser = []
    for x in cl:
        if x["src"] == "src:wp-list-nascar-tracks":
            ser.append(nascar_list_series(x))
        elif x["src"] == "src:wp-list-champcar-tracks":
            yrs = re.findall(r"(19\d\d|20\d\d)", x.get("seasons_raw") or "")
            ser.append("American championship car racing (AAA/USAC/CART/Champ Car)" +
                       (f" ({yrs[0]}–{yrs[-1]})" if len(yrs) > 1 else (f" ({yrs[0]})" if yrs else "")))
        else:
            ser += [canon_series(s) for s in x.get("major_series", []) if not SERIES_JUNK.search(s)]
    seen, ms = set(), []
    for s in ser:
        k = s.lower()
        base = re.sub(r"\s*\(.*\)$", "", k)
        if k in seen:
            continue
        # drop bare series when a dated version exists and vice versa keep dated
        seen.add(k)
        ms.append(s)
    # remove undated duplicates if dated version present
    dated = {re.sub(r"\s*\(.*\)$", "", s).lower() for s in ms if s.endswith(")")}
    ms = [s for s in ms if s.endswith(")") or s.lower() not in dated]
    ms = [s for s in ms if not re.match(r"^(NASCAR national series)$", s)]
    rec["major_series"] = ms[:15]
    # disciplines
    classes = [c for x in cl for c in x.get("classes", [])]
    disc = set(disciplines_from_classes(classes, rec["surface"], tt))
    blob = " ".join(ms).lower() + " " + " ".join(c for x in cl for c in x.get("wp_categories", []) or []).lower()
    if re.search(r"nascar|arca|stock car|pinty|cascar", blob):
        disc.add("stock_car")
    if re.search(r"late model|cars tour|pro all stars|american canadian tour|lucas oil late", blob):
        disc.add("dirt_late_model" if SURF_CLASS(rec["surface"]) == "dirt" else "late_model")
    if re.search(r"modified", blob):
        disc.add("modified")
    if re.search(r"world of outlaws|sprint car|ascs", blob):
        disc.add("sprint_car")
    if re.search(r"indycar|championship car|champ car|cart|formula|open.wheel", blob):
        disc.add("open_wheel")
    if re.search(r"imsa|sports ?car|le mans|grand-am|trans-am|gt ", blob):
        disc.add("sports_car")
    if re.search(r"scca|nasa |club racing", blob):
        disc.add("club_road")
    if re.search(r"karting venues|kart", blob) or tt == "kart_circuit":
        disc.add("karting")
    nm = " ".join({x["name"] for x in cl}).lower()
    if re.search(r"\bkart", nm):
        disc.add("karting")
    if re.search(r"quarter midget|\bqma\b|\bqmc\b|\bqmrc\b|quarter-midget", nm):
        disc.add("quarter_midget")
    if re.search(r"quarter midget", blob):
        disc.add("quarter_midget")
    if re.search(r"legends", blob):
        disc.add("legends")
    if re.search(r"motorcycle|ama |motogp|superbike", blob):
        disc.add("motorcycle")
    if SURF_CLASS(rec["surface"]) == "dirt" and "late_model" in disc:
        disc.discard("late_model")
        disc.add("dirt_late_model")
    if SURF_CLASS(rec["surface"]) == "paved" and "dirt_late_model" in disc:
        disc.discard("dirt_late_model")
        disc.add("late_model")
    rec["disciplines"] = sorted(disc)
    # level: an operating venue is classed by what it hosts now (undated series, or dated spans
    # reaching 2000+); a one-off national race decades ago only raises prestige. Closed venues are
    # classed by the role they had.
    def _end(sv):
        yy = [int(y) for y in re.findall(r"(19\d\d|20\d\d)", sv)]
        return max(yy) if yy else None
    if rec.get("active") is False:
        lvl_ms = ms
    else:
        lvl_ms = [sv for sv in ms if _end(sv) is None or _end(sv) >= 2000]
    base_ms = {re.sub(r"\s*\(.*\)$", "", s) for s in lvl_ms}
    if base_ms & INTERNATIONAL:
        lvl = "international"
    elif base_ms & NATIONAL:
        lvl = "national"
    elif any(REGIONAL_PAT.search(s) and not LOCAL_PAT.search(s) for s in base_ms):
        lvl = "regional"
    else:
        lvl = "local"
    rec["level"] = lvl
    # prestige
    cur_nat = [s for s in ms if re.sub(r"\s*\(.*\)$", "", s) in NATIONAL and not s.endswith(")")]
    hist_nat = [s for s in ms if re.sub(r"\s*\(.*\)$", "", s) in NATIONAL and s.endswith(")")]
    spans = []
    for s in hist_nat:
        yy = [int(y) for y in re.findall(r"(19\d\d|20\d\d)", s)]
        if yy:
            spans.append(max(yy) - min(yy) + 1)
    if lvl == "international":
        pc, basis = "high", "hosts/hosted an international championship (Formula One)"
    elif cur_nat or (spans and max(spans) >= 5):
        pc, basis = "high", "hosts/hosted national-championship racing" + (f" over {max(spans)} seasons" if spans else "")
    elif lvl == "national" or lvl == "regional":
        pc, basis = "medium", ("hosted national-series racing briefly" if lvl == "national" else "hosts regional touring-series racing")
    else:
        pc, basis = "low", "local weekly venue; no national/regional series found in sources"
    rec["prestige_category"] = pc
    rec["prestige_basis"] = basis
    # notable note (short, factual, our own words)
    bits = []
    if rec.get("status_sources"):
        if "src:imca-track-directory" in rec["status_sources"]:
            bits.append("IMCA-sanctioned weekly track (2026 directory)")
        if "src:wissota-tracks" in rec["status_sources"]:
            bits.append("WISSOTA member track (2026)")
        if "src:wp-nascar-local-racing-series" in rec["status_sources"]:
            bits.append("NASCAR Local Racing Series member track (2026)")
    if hist_nat:
        bits.append("hosted " + ", ".join(hist_nat[:3]))
    rec["notable_note"] = "; ".join(bits) or None
    # provenance
    urls = []
    for x in cl:
        if x.get("url") and x["url"] not in urls:
            urls.append(x["url"])
    rec["sources"] = srcs
    rec["source_urls"] = urls[:12]
    rec["_kinds"] = sorted({x["kind"] for x in cl})
    rec["_wp_titles"] = sorted({x["wp_title"] for x in cl if x.get("wp_title")} | {x["link"] for x in cl if x.get("link")})
    rec["_qids"] = sorted({x["qid"] for x in cl if x.get("qid")})
    rec["_mrp"] = [{"id": x["mrp_id"], "claimed": x.get("mrp_claimed"), "last": x.get("last_event_year"),
                    "size": x.get("size_raw"), "shape": x.get("shape_raw"), "comp": x.get("comp_raw")}
                   for x in cl if x["src"] == "src:myracepass"]
    rec["_secondary_of"] = next((x.get("secondary_of") for x in cl if x.get("secondary_of")), None)
    rec["_members"] = [{"src": x["src"], "name": x["name"], "region": x.get("region")} for x in cl]
    if rec.get("_coord_src") == "nominatim":
        rec["sources"] = sorted(set(rec["sources"]) | {"src:nominatim-osm"})
        if rec.get("_osm") and rec["_osm"] not in rec["source_urls"]:
            rec["source_urls"].append(rec["_osm"])
    rec["_suspect_only"] = bool(cs) and all(suspect(x) for x in cs)
    return rec


def confidence(rec):
    s = set(rec["sources"])
    indep = 0
    indep += 1 if s & {"src:wikipedia", "src:wikidata", "src:frwiki", "src:eswiki"} else 0
    indep += 1 if s & {"src:imca-track-directory", "src:wissota-tracks"} else 0
    indep += 1 if "src:myracepass" in s else 0
    indep += 1 if any(x.startswith("src:wp-list") or x == "src:wp-nascar-local-racing-series" for x in s) and not (s & {"src:wikipedia"}) else 0
    strong_coord = rec.get("_coord_src") in ("wikipedia", "wikidata", "wikipedia-list", "myracepass-map", "imca-geocoded-address") or (
        rec.get("_coord_src") == "nominatim" and rec.get("_osm_class") in ("highway/raceway", "leisure/track", "leisure/sports_centre", "leisure/stadium"))
    if rec.get("_surface_conflict") or rec.get("_coord_spread_km", 0) > 3:
        return "low" if indep < 2 else "medium"
    if rec.get("_closed_from_text") or rec.get("_type_inferred"):
        return "medium" if strong_coord and indep >= 2 else "low"
    if indep >= 2 and strong_coord:
        return "high"
    if strong_coord:
        return "medium"
    return "low"


# ----------------------------------------------------------------------------- existing match
ex_names = []
for e in existing:
    names = [e["name"]] + list(e.get("aliases") or [])
    ex_names.append((e, {norm_name(n) for n in names}))


def match_existing(rec):
    wp = set(rec["_wp_titles"])
    hits = [e for e, _ in ex_names if wp & e["_wp"]]
    if rec.get("_secondary_of"):
        hits = [e for e in hits if SURF_CLASS(e.get("surface")) == SURF_CLASS(rec.get("surface"))]
    if hits:
        # one article can back several existing records (oval + road course): pick the same kind
        hits.sort(key=lambda e: (TYPE_CLASS(e.get("track_type")) != TYPE_CLASS(rec.get("track_type")),
                                 SURF_CLASS(e.get("surface")) != SURF_CLASS(rec.get("surface"))))
        return hits[0], "wikipedia title"
    if rec.get("_secondary_of"):
        return None, None
    names = {norm_name(rec["name"])} | {norm_name(a) for a in rec["aliases"]}
    best = None
    for e, en in ex_names:
        near = None
        if rec.get("lat") is not None and e.get("lat") is not None:
            near = haversine_km((rec["lat"], rec["lon"]), (e["lat"], e["lon"]))
        same_state = bool(rec.get("region")) and e.get("region") == rec.get("region")
        if names & en and (same_state or (near is not None and near < 3)):
            if SURF_CLASS(e.get("surface")) and SURF_CLASS(rec.get("surface")) and SURF_CLASS(e["surface"]) != SURF_CLASS(rec["surface"]) and near is not None and near > 0.5:
                pass
            return e, "name+state"
        if near is not None and near < 2.0:
            sim = max(name_sim(n, rec["name"]) for n in [e["name"]] + list(e.get("aliases") or []))
            if sim >= 0.6 and compatible({"name": e["name"], "surface": e.get("surface"), "track_type": e.get("track_type")},
                                         {"name": rec["name"], "surface": rec.get("surface"), "track_type": rec.get("track_type")}, sim):
                if best is None or near < best[2]:
                    best = (e, f"within {near:.2f} km, name sim {sim:.2f}", near)
            elif near < 0.25 and TYPE_CLASS(e.get("track_type")) == TYPE_CLASS(rec.get("track_type")) and \
                    (not e.get("surface") or not rec.get("surface") or SURF_CLASS(e["surface"]) == SURF_CLASS(rec["surface"])):
                if best is None or near < best[2]:
                    best = (e, f"same site within {near:.2f} km", near)
            elif near < 0.4 and SURF_CLASS(e.get("surface")) == SURF_CLASS(rec.get("surface")) and \
                    TYPE_CLASS(e.get("track_type")) == TYPE_CLASS(rec.get("track_type")) and rec.get("surface"):
                if best is None or near < best[2]:
                    best = (e, f"same site within {near:.2f} km (renamed?)", near)
    if best:
        return best[0], best[1]
    return None, None


# ----------------------------------------------------------------------------- geocoding (optional)
def geocode_missing(recs):
    import geocode as G
    G.CACHE_ONLY = "--no-search" in sys.argv  # use earlier lookups without new requests
    n = 0
    for r in recs:
        if r.get("lat") is None and r.get("region") and r["track_type"] in ("oval", "figure_eight", "road_course", None) \
                and not (set(r["sources"]) & {"src:myracepass", "src:wissota-tracks"}):
            state = next((k for k, v in {**US, **CA, **MX}.items() if v == r["region"]), r["region"])
            try:
                hits = G.search(f"{r['name']}, {state}")
            except RuntimeError as e:
                print(e)
                break
            n += 1
            for h in hits:
                cls = (h.get("category"), h.get("type"))
                hn = h.get("name") or ""
                hs = (h.get("address") or {}).get("state")
                if cls not in G.TRACKISH or not hn or name_sim(hn, r["name"]) < 0.8:
                    continue
                if hs and region_from_text(hs)[0] != r["region"]:
                    continue
                r["lat"], r["lon"] = round(float(h["lat"]), 5), round(float(h["lon"]), 5)
                r["_coord_src"] = "nominatim"
                r["_osm"] = f"https://www.openstreetmap.org/{h.get('osm_type')}/{h.get('osm_id')}"
                r["_osm_class"] = "/".join(cls)
                r["sources"] = sorted(set(r["sources"]) | {"src:nominatim-osm"})
                r["source_urls"].append(r["_osm"])
                if not r.get("city"):
                    a = h.get("address") or {}
                    r["city"] = a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or a.get("county")
                break
    for r in recs:
        # coordinate conflicts between equally-backed sources: keep the option nearest the stated town
        if r.get("_coord_tie") and r.get("_coord_spread_km", 0) > 5 and r.get("city") and r.get("region"):
            state = next((k for k, v in {**US, **CA, **MX}.items() if v == r["region"]), r["region"])
            try:
                hits = G.search(f"{r['city']}, {state}", limit=1)
            except RuntimeError as e:
                print(e)
                break
            if hits:
                tc = (float(hits[0]["lat"]), float(hits[0]["lon"]))
                opt = min(r["_coord_options"], key=lambda o: haversine_km(tc, (o["lat"], o["lon"])))
                r["lat"], r["lon"], r["_coord_src"] = round(opt["lat"], 5), round(opt["lon"], 5), opt["src"]
                r["_coord_resolved_by_town"] = f"{r['city']}, {state}"
    for r in recs:
        if r.get("lat") is not None and (not r.get("city") or not r.get("region")):
            try:
                h = G.reverse(r["lat"], r["lon"])
            except RuntimeError as e:
                print(e)
                break
            a = (h or {}).get("address") or {}
            if not r.get("region"):
                reg, cty = region_from_text(a.get("state") or "")
                if reg:
                    r["region"], r["country"] = reg, cty
            if not r.get("city"):
                r["city"] = a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or a.get("municipality")
                if r["city"]:
                    r["_city_src"] = "nominatim-reverse"
            if not r.get("country"):
                r["country"] = {"us": "USA", "ca": "CAN", "mx": "MEX"}.get(a.get("country_code"))
    G.flush()
    print("geocode searches:", n)


def _richness(r):
    return (len(r["sources"]) + (2 if "src:wikipedia" in r["sources"] else 0) +
            sum(1 for k in ("length_mi", "surface", "opened", "banking_deg_turns") if r.get(k) is not None))


def same_site_dedupe(recs):
    """Records on the same spot (<=150 m) of the same kind are one venue under two names
    (typically a rename seen by sources located in different passes)."""
    out = []
    for r in sorted(recs, key=_richness, reverse=True):
        twin = None
        for k in out:
            if haversine_km((k["lat"], k["lon"]), (r["lat"], r["lon"])) <= 0.15 and \
                    TYPE_CLASS(k["track_type"]) == TYPE_CLASS(r["track_type"]) and \
                    (not k.get("surface") or not r.get("surface") or SURF_CLASS(k["surface"]) == SURF_CLASS(r["surface"])) and \
                    not (k.get("_secondary_of") or r.get("_secondary_of")):
                twin = k
                break
        if twin is None:
            out.append(r)
            continue
        if norm_name(r["name"]) not in {norm_name(a) for a in twin["aliases"] + [twin["name"]]}:
            twin["aliases"].append(r["name"])
        for k in ("sources", "status_sources"):
            twin[k] = sorted(set(twin.get(k) or []) | set(r.get(k) or []))
        twin["source_urls"] = list(dict.fromkeys(twin["source_urls"] + r["source_urls"]))
        twin["major_series"] = list(dict.fromkeys(twin["major_series"] + r["major_series"]))
        twin["disciplines"] = sorted(set(twin["disciplines"]) | set(r["disciplines"]))
        for k in ("surface", "length_mi", "opened", "city", "region"):
            if twin.get(k) is None and r.get(k) is not None:
                twin[k] = r[k]
        if r.get("active") is True and twin.get("active") is not True:
            twin["active"], twin["status_verified_year"] = True, r.get("status_verified_year")
            twin["closed"] = None
        twin["_merged_same_site"] = twin.get("_merged_same_site", []) + [r["name"]]
    return out


# ----------------------------------------------------------------------------- main
def main():
    recs = []
    for root, cl in clusters.items():
        if all(x.get("outside_na") for x in cl if x.get("lat") is not None) and any(x.get("lat") is not None for x in cl):
            continue
        rec = build_record(cl)
        if rec["country"] not in (None, "USA", "CAN", "MEX"):
            continue
        recs.append(rec)
    if GEOCODE:
        geocode_missing([r for r in recs if not r["_kinds"] == ["drag"]])
        ga = dict(_ga)
        for r in recs:
            if r.get("_coord_src") == "nominatim" and not r.get("_osm_assigned"):
                for x in r["_members"]:
                    ga[f"{x['src']}|{x['name']}|{x.get('region')}"] = {"lat": r["lat"], "lon": r["lon"], "osm": r.get("_osm"),
                                                                       "osm_class": r.get("_osm_class")}
        json.dump(ga, open(GEO_ASSIGN_P, "w"), indent=0)
    new, enrich, rejected = [], [], collections.Counter()
    rej_rows = []
    for r in recs:
        kinds = set(r["_kinds"])
        if kinds <= {"drag"} or (r["track_type"] is None and "drag" in kinds) or (
                re.search(r"dragway|drag ?strip|drag racing", r["name"], re.I) and r["track_type"] != "oval"):
            rejected["drag strip"] += 1
            continue
        if r["disciplines"] == ["motorcycle"] or re.search(r"motocross|supercross|ama motocross", " ".join(r["major_series"]).lower()):
            rejected["motorcycle-only venue"] += 1
            continue
        if kinds <= {"other"}:
            rejected["not a car circuit (horse/motocross)"] += 1
            continue
        e, why = match_existing(r)
        if e is not None:
            enrich.append((e, why, r))
            continue
        reason = None
        if r["country"] not in ("USA", "CAN", "MEX"):
            reason = "no country"
        elif r.get("lat") is None:
            reason = "no coordinates"
        elif r["track_type"] is None:
            reason = "track type unknown"
        elif kinds <= {"mrp"}:
            m = r["_mrp"][0]
            if not (m.get("size") or m.get("shape")) or not (m.get("claimed") or (m.get("last") or 0) >= 2023):
                reason = "myracepass-only profile without size/shape or recent activity"
        elif r.get("active") is False and not r.get("closed") and not r.get("closed_evidence_last_event"):
            reason = "inactive, closure year unknown"
        elif r.get("_suspect_only"):
            reason = "only coordinates are shared by two different Wikipedia articles (unverifiable)"
        elif kinds <= {"venue_weak"}:
            reason = "fr/es wiki only, type unknown"
        if r["track_type"] == "street_circuit" and (r.get("closed") or r.get("active") is False) is False and not r["major_series"]:
            pass
        if reason:
            rejected[reason] += 1
            rej_rows.append({"name": r["name"], "region": r.get("region"), "reason": reason, "sources": r["sources"],
                             "urls": r["source_urls"][:3]})
            continue
        r["confidence"] = confidence(r)
        new.append(r)
    new = same_site_dedupe(new)
    print("new", len(new), "enrich", len(enrich), "rejected", dict(rejected))
    json.dump(new, open(os.path.join(RAW, "build_new.json"), "w"), indent=1, ensure_ascii=False)
    json.dump([{"existing_id": e["id"], "existing_name": e["name"], "why": w, "rec": r} for e, w, r in enrich],
              open(os.path.join(RAW, "build_enrich.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(rej_rows, open(os.path.join(RAW, "build_rejected.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
