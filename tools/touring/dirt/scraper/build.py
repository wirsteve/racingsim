#!/usr/bin/env python3
"""Build the dirt / sprint / midget touring-series database from Wikipedia + Wikidata.

Re-runnable: every HTTP response is cached under ../cache (delete it to refresh).
Usage:  python3 build.py            (writes ../series.json, ../<series>/<year>.json, ../events/, ../drivers.json, ../venues.json, ../COVERAGE.md)
"""
import collections, json, os, re, sys
import wiki, parse, extract, official
from config import SERIES, EVENTS, YEAR_MIN, YEAR_MAX, DISC_TO_VENUE

OUT = wiki.BASE
EXISTING = os.path.join(os.path.dirname(OUT), "existing_tracks.json")
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s); print(s, flush=True)


def wurl(p):
    return p["url"] if p else None


# ======================================================================== champions / events
def winners_from(src, p):
    kind = src[0]
    if kind == "official":
        return official.champions(src[1])
    if kind == "table":
        rows = extract.year_winner_tables(p["wikitext"], src[2], src[3])
    else:
        nth = src[3] if len(src) > 3 else 0
        sec = None
        # nth occurrence of the heading
        txt = p["wikitext"]
        for _ in range(nth + 1):
            sec = extract.list_section(txt, src[2])
            if sec is None:
                break
            idx = txt.find(sec)
            txt = txt[idx + len(sec):]
        rows = extract.list_winners(sec) if sec else []
    return rows


# ======================================================================== main
def main():
    os.makedirs(OUT, exist_ok=True)
    main_pages = sorted({c["champ"][1] for c in SERIES.values() if c["champ"][0] != "official"} | {e["src"][1] for e in EVENTS.values()})
    tpl_pages = sorted({c["venues_tpl"] for c in SERIES.values() if c.get("venues_tpl")})
    pages = wiki.pages(main_pages + tpl_pages)
    for t in main_pages:
        if not pages.get(t):
            log("WARN missing main page", t)

    # ---- season articles
    titles = json.load(open(os.path.join(OUT, "cache", "season_titles.json")))
    season_titles = collections.defaultdict(dict)
    for key, cfg in SERIES.items():
        if not cfg.get("season_re"):
            continue
        for t in titles:
            m = re.match(cfg["season_re"], t)
            if m:
                season_titles[key][int(m.group(1))] = t
    all_season = [t for d in season_titles.values() for t in d.values()]
    spages = wiki.pages(all_season)

    seasons = collections.defaultdict(dict)   # key -> year -> record
    for key, cfg in SERIES.items():
        champs = {}
        if cfg["champ"][0] == "official":
            p = None
            for r in winners_from(cfg["champ"], None):
                champs.setdefault(r["year"], r)
            cfg["_champ_src"] = official.PAGES[cfg["champ"][1].split("_")[0] if cfg["champ"][1].startswith(("stss", "mars")) else cfg["champ"][1]]
        else:
            p = pages.get(cfg["champ"][1])
            if p:
                for r in winners_from(cfg["champ"], p):
                    champs.setdefault(r["year"], r)
            cfg["_champ_src"] = wurl(p)
        cfg["_champs"] = champs
        mrp_years = [y for y in official.mrp_years(cfg["mrp"]) if YEAR_MIN <= y <= YEAR_MAX] if cfg.get("mrp") else []
        years = set(champs) | set(season_titles.get(key, {})) | set(mrp_years)
        lo = YEAR_MIN
        for y in sorted(years):
            if not (lo <= y <= YEAR_MAX or y in cfg.get("extra_years", ())):
                continue
            rec = {"series": key, "year": y, "official_name": None, "data_level": "champion_only",
                   "champion": None, "teams": [], "standings": [], "schedule": [], "sources": []}
            if y in champs:
                c = champs[y]
                rec["champion"] = {"name": c["name"], "wiki": c["wiki"]}
                rec["sources"].append(cfg["_champ_src"])
            st = season_titles.get(key, {}).get(y)
            sp = spages.get(st) if st else None
            if sp:
                rec["official_name"] = re.sub(r"^\d{4}\s+", "", sp["title"])
                parsed = extract.parse_season(sp["wikitext"], y)
                rec["schedule"] = parsed["schedule"]
                rec["standings"] = parsed["standings"]
                rec["teams"] = group_teams(parsed["entries"])
                rec["sources"].insert(0, sp["url"])
                rec["_name_links"] = name_links(sp["wikitext"])
                if not rec["champion"] and rec["standings"] and rec["standings"][0]["pos"] == 1:
                    rec["champion"] = {"name": rec["standings"][0]["name"], "wiki": rec["standings"][0]["wiki"]}
                if rec["schedule"] and (rec["standings"] or rec["teams"]):
                    rec["data_level"] = "full"
                elif rec["schedule"]:
                    rec["data_level"] = "schedule"
                elif rec["teams"] or rec["standings"]:
                    rec["data_level"] = "full" if rec["standings"] else "champion_only"
            if not rec["schedule"] and y in mrp_years:
                url, rows = official.mrp_schedule(cfg["mrp"], y)
                SRC_URL[0] = url
                rec["schedule"] = mrp_rows(rows, y)
                if rec["schedule"]:
                    rec["sources"].append(url)
                    if rec["data_level"] == "champion_only":
                        rec["data_level"] = "schedule"
            if not rec["champion"] and not rec["schedule"]:
                continue
            seasons[key][y] = rec
        log(f"{key}: champions {len(champs)} (all years), season articles {len(season_titles.get(key, {}))}, files {len(seasons[key])}")

    # ---- events
    events = {}
    for ek, ecfg in EVENTS.items():
        p = pages.get(ecfg["src"][1])
        if not p:
            continue
        rows = winners_from(ecfg["src"], p)
        winners, seen = [], set()
        for r in rows:
            k = (r["year"], r["name"])
            if k in seen:
                continue
            seen.add(k)
            winners.append({"year": r["year"], "name": r["name"], "wiki": r["wiki"]})
        winners.sort(key=lambda w: w["year"])
        events[ek] = {"name": ecfg["name"], "track": ecfg["track"], "city": None, "state": None,
                      "discipline": ecfg["discipline"], "winners": winners, "sources": [p["url"]],
                      "_name_links": name_links(p["wikitext"])}
        log(f"event {ek}: {len(winners)} winners")

    # ---- fill wiki links from same-article links, then global unique-name map
    fill_person_links(seasons, events)
    drivers = build_drivers(seasons, events)
    # drop wiki titles that failed verification
    apply_driver_titles(seasons, events, drivers)

    venues = build_venues(seasons, events, pages, tpl_pages)

    # ---- series.json
    series_out = {}
    for key, cfg in SERIES.items():
        yrs = sorted(set(cfg["_champs"]) | set(seasons[key]))
        names = []
        for y in sorted(seasons[key]):
            on = seasons[key][y]["official_name"]
            if on:
                if names and names[-1]["name"] == on and names[-1]["to"] == y - 1:
                    names[-1]["to"] = y
                else:
                    names.append({"from": y, "to": y, "name": on})
        fp = collections.Counter()
        for rec in seasons[key].values():
            for r in rec["schedule"]:
                if r["state"]:
                    fp[r["state"]] += 1
        for st in cfg.get("_tpl_states", []):
            fp[st] += 0
        srcs = [cfg["_champ_src"]] + [seasons[key][y]["sources"][0] for y in sorted(seasons[key]) if seasons[key][y]["schedule"]]
        if cfg.get("venues_tpl") and pages.get(cfg["venues_tpl"]):
            srcs.append(pages[cfg["venues_tpl"]]["url"])
        series_out[key] = {"name": cfg["name"], "names_by_year": names, "discipline": cfg["discipline"],
                           "years": [yrs[0], yrs[-1]] if yrs else None, "footprint": sorted(fp),
                           "level": cfg["level"], "sources": [s for s in dict.fromkeys(srcs) if s]}
        if cfg.get("caveat"):
            series_out[key]["note"] = cfg["caveat"]
    dump(os.path.join(OUT, "series.json"), series_out)

    # ---- season files
    for key in seasons:
        d = os.path.join(OUT, key)
        os.makedirs(d, exist_ok=True)
        for y, rec in seasons[key].items():
            out = {k: v for k, v in rec.items() if not k.startswith("_")}
            out["schedule"] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rec["schedule"]]
            out["standings"] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rec["standings"]]
            out["sources"] = list(dict.fromkeys(s for s in out["sources"] if s))
            dump(os.path.join(d, f"{y}.json"), out)
    os.makedirs(os.path.join(OUT, "events"), exist_ok=True)
    for ek, ev in events.items():
        dump(os.path.join(OUT, "events", ek + ".json"), {k: v for k, v in ev.items() if not k.startswith("_")})
    dump(os.path.join(OUT, "drivers.json"), {k: v for k, v in sorted(drivers.items()) if v})
    dump(os.path.join(OUT, "venues.json"), venues)
    coverage(seasons, events, series_out, drivers, venues)
    log("HTTP stats", wiki.STATS)


TODAY = "2026-10-06"
SRC_URL = [None]


def mrp_rows(rows, year):
    """Official-site schedule cards -> schedule rows (no winners on these pages)."""
    out = []
    for r in rows:
        nm, st = r["race"] or "", r["status"] or ""
        if re.search(r"(?i)practice|test (day|session)|open practice|banquet|cancel|rain ?out|postpone|weather", nm + " " + st):
            continue
        date = parse.parse_date(r["date"] or "", year)
        if not date:
            continue
        if not st.startswith("Results") and date < TODAY:
            continue  # past event without results: did not run
        trk = r["track"]
        if trk and trk.startswith("ZZZ_"):
            trk = None  # archived venue whose name the site has mangled; unknown
        out.append({"round": len(out) + 1, "date": date, "race": nm or None, "track": trk, "city": None, "state": None,
                    "winner": None, "winner_wiki": None, "_track_wiki": None, "_src": SRC_URL[0]})
    return out


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def group_teams(entries):
    teams = collections.OrderedDict()
    for e in entries:
        tname = e["team"] or "(unknown)"
        t = teams.setdefault(tname, {"team": e["team"], "manufacturer": None, "cars": [], "_chassis": set()})
        if e["chassis"]:
            t["_chassis"].add(e["chassis"])
        car = next((c for c in t["cars"] if c["number"] == e["number"]), None)
        if not car:
            car = {"number": e["number"], "full_time": e["full_time"], "drivers": []}
            t["cars"].append(car)
        for d in e["drivers"]:
            if d["name"] not in [x["name"] for x in car["drivers"]]:
                car["drivers"].append(dict(d))
    out = []
    for t in teams.values():
        if len(t["_chassis"]) == 1:
            t["manufacturer"] = next(iter(t["_chassis"]))
        del t["_chassis"]
        out.append(t)
    return out


def name_links(wikitext):
    """display-name -> link target for every person-ish link in an article."""
    m = {}
    for tgt, disp in parse.links(parse.expand_templates(parse.strip_refs(wikitext))):
        d = re.sub(r"\s*\(.*?\)\s*", "", disp).strip()
        if d and tgt and not tgt.startswith(("#",)):
            m.setdefault(d, tgt.split("#")[0])
    return m


def iter_people(seasons, events):
    for key in seasons:
        for rec in seasons[key].values():
            nl = rec.get("_name_links", {})
            if rec["champion"]:
                yield rec["champion"], nl
            for r in rec["standings"]:
                yield r, nl
            for r in rec["schedule"]:
                yield r, nl  # winner/winner_wiki
            for t in rec["teams"]:
                for c in t["cars"]:
                    for d in c["drivers"]:
                        yield d, nl
    for ev in events.values():
        for w in ev["winners"]:
            yield w, ev.get("_name_links", {})


def _nk(obj):
    return ("winner", "winner_wiki") if "winner" in obj else ("name", "wiki")


def fill_person_links(seasons, events):
    glob = collections.defaultdict(set)
    for obj, nl in iter_people(seasons, events):
        n, w = _nk(obj)
        if obj.get(n) and not obj.get(w) and obj[n] in nl:
            obj[w] = nl[obj[n]]
        if obj.get(n) and obj.get(w):
            glob[obj[n]].add(obj[w])
    for obj, nl in iter_people(seasons, events):
        n, w = _nk(obj)
        if obj.get(n) and not obj.get(w) and len(glob.get(obj[n], ())) == 1:
            obj[w] = next(iter(glob[obj[n]]))


# ======================================================================== drivers (Wikidata)
RACING_OCC = {"Q378622", "Q10349745", "Q15117302", "Q2066131", "Q18574233", "Q1076502", "Q4009406", "Q11338576", "Q19841381"}


def claim_ids(ent, prop):
    out = []
    for c in ent.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
    return out


def claim_time(ent, prop):
    for c in ent.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "time" in v:
            t, prec = v["time"], v.get("precision", 11)
            m = re.match(r"[+-](\d{4})-(\d{2})-(\d{2})", t)
            if not m:
                continue
            if prec >= 11:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            return m.group(1)
    return None


def label(ent):
    return ent.get("labels", {}).get("en", {}).get("value")


def is_racer(ent):
    occ = set(claim_ids(ent, "P106"))
    sports = set(claim_ids(ent, "P641"))
    return bool(occ & RACING_OCC) or bool(sports & {"Q5386", "Q1045436", "Q1196629", "Q2141981", "Q7579869"})


def build_drivers(seasons, events):
    # gather names / titles
    linked, unlinked = set(), set()
    for obj, _ in iter_people(seasons, events):
        n, w = _nk(obj)
        if obj.get(w):
            linked.add(obj[w])
        elif obj.get(n):
            unlinked.add(obj[n])
    log(f"drivers: {len(linked)} linked titles, {len(unlinked)} unlinked names")
    # candidate titles for unlinked names
    cands = {}
    for n in unlinked:
        if not re.fullmatch(r"[A-Za-z.'’\- ]{4,40}", n) or len(n.split()) < 2:
            continue
        cands[n] = [n + " (racing driver)", n + " (American racing driver)", n]
    res = wiki.resolve(sorted(linked) + [c for v in cands.values() for c in v])
    qids = {t: r[1]["qid"] for t, r in res.items() if r[0] and r[1] and r[1]["qid"] and not r[1]["disambig"]}
    ents = wiki.wd_entities(sorted(set(qids.values())), props="claims|labels|descriptions")
    title_ok = {}
    for t in linked:
        q = qids.get(t)
        e = ents.get(q) if q else None
        title_ok[t] = (res[t][0], q) if e and "Q5" in claim_ids(e, "P31") else None
    found_unlinked = {}
    for n, cs in cands.items():
        for c in cs:
            q = qids.get(c)
            e = ents.get(q) if q else None
            if e and "Q5" in claim_ids(e, "P31") and is_racer(e):
                desc = e.get("descriptions", {}).get("en", {}).get("value", "")
                found_unlinked[n] = (res[c][0], q)
                break
    log(f"drivers: verified {sum(1 for v in title_ok.values() if v)} linked, matched {len(found_unlinked)} unlinked by title+Wikidata occupation")
    MAP["title"] = title_ok
    MAP["unlinked"] = found_unlinked
    # bios
    people = {}
    for v in list(title_ok.values()) + list(found_unlinked.values()):
        if v:
            people[v[0]] = v[1]
    pents = {q: ents[q] for q in people.values() if q in ents}
    # birthplace entities + admin chain
    bp = {q: (claim_ids(e, "P19") or [None])[0] for q, e in pents.items()}
    places = wiki.wd_entities(sorted({x for x in bp.values() if x}), props="claims|labels")
    chain = dict(places)
    frontier = set()
    for e in places.values():
        frontier.update(claim_ids(e, "P131")[:1]); frontier.update(claim_ids(e, "P17")[:1])
    for _ in range(4):
        frontier = {x for x in frontier if x not in chain}
        if not frontier:
            break
        new = wiki.wd_entities(sorted(frontier), props="claims|labels")
        chain.update(new)
        frontier = set()
        for e in new.values():
            frontier.update(claim_ids(e, "P131")[:1]); frontier.update(claim_ids(e, "P17")[:1])
    citizen = set()
    for e in pents.values():
        citizen.update(claim_ids(e, "P27")[:1])
    chain.update(wiki.wd_entities(sorted(citizen - set(chain)), props="claims|labels"))
    drivers = {}
    for title, q in people.items():
        e = pents.get(q)
        if not e:
            continue
        place = bp.get(q)
        st, ctry = admin_state(place, chain)
        if not ctry:
            c = (claim_ids(e, "P27") or [None])[0]
            ctry = iso3(chain.get(c)) if c else None
        drivers[title] = {"name": re.sub(r"\s*\(.*?\)$", "", title), "qid": q, "birth_date": claim_time(e, "P569"),
                          "birth_place": label(chain.get(place, {})) if place else None, "state": st, "country": ctry}
    return drivers


MAP = {}
STATE_TYPES = {"Q35657", "Q11828004", "Q9357527", "Q1352230", "Q107390"}


def iso3(ent):
    if not ent:
        return None
    for c in ent.get("claims", {}).get("P298", []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, str):
            return v
    return None


def admin_state(place, chain):
    st, ctry = None, None
    cur, seen = place, set()
    while cur and cur in chain and cur not in seen:
        seen.add(cur)
        e = chain[cur]
        if not ctry:
            c = (claim_ids(e, "P17") or [None])[0]
            if c and c in chain:
                ctry = iso3(chain[c])
        if not st and set(claim_ids(e, "P31")) & STATE_TYPES:
            st = parse.state_code(label(e) or "")
        if "Q35657" in claim_ids(e, "P31") and not st:
            st = parse.state_code(label(e) or "")
        nxt = claim_ids(e, "P131")
        cur = nxt[0] if nxt else None
    if st and not ctry:
        ctry = "CAN" if st in parse.CA_PROV.values() else "USA"
    return st, ctry


def apply_driver_titles(seasons, events, drivers):
    tok, unl = MAP.get("title", {}), MAP.get("unlinked", {})
    for obj, _ in iter_people(seasons, events):
        n, w = _nk(obj)
        if obj.get(w):
            v = tok.get(obj[w])
            obj[w] = v[0] if v else None
        elif obj.get(n) and obj[n] in unl:
            obj[w] = unl[obj[n]][0]


# ======================================================================== venues
def norm(s):
    s = (s or "").lower().replace("&", "and")
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_venues(seasons, events, pages, tpl_pages):
    existing = json.load(open(EXISTING))
    ex_by = {}
    for t in existing:
        for n in [t["name"]] + (t.get("aliases") or []):
            ex_by.setdefault(norm(n), []).append(t)
    # occurrences
    occ = []
    for key, yrs in seasons.items():
        disc = SERIES[key]["discipline"]
        for y, rec in yrs.items():
            for r in rec["schedule"]:
                if r["track"] or r["city"]:
                    occ.append(dict(name=r["track"], city=r["city"], state=r["state"], link=r.get("_track_wiki"),
                                    disc=disc, level=SERIES[key]["level"], src=r.get("_src") or rec["sources"][0], obj=r))
    for ek, ev in events.items():
        if ev["track"]:
            occ.append(dict(name=ev["track"], city=None, state=None, link=ev["track"], disc=ev["discipline"],
                            level="national", src=ev["sources"][0], obj=ev))
    # venue templates: nickname -> article title  (used to give a link to unlinked names)
    tpl_links = {}
    for t in tpl_pages:
        p = pages.get(t)
        if p:
            for tgt, disp in parse.links(p["wikitext"]):
                tpl_links.setdefault(norm(tgt), tgt)
    known = set(ex_by) | {norm(o["name"]) for o in occ if o["name"] and o["state"]}
    name_states = collections.defaultdict(set)
    for o in occ:
        if o["name"] and o["state"]:
            name_states[norm(o["name"])].add(o["state"])
    for t in existing:
        for n in [t["name"]] + (t.get("aliases") or []):
            name_states[norm(n)].add(t["region"])
    for o in occ:
        if not o["link"] and o["name"] and not SUBTRACK.match(o["name"]) and norm(o["name"]) not in tpl_links:
            if not o["state"] and norm(o["name"]) in known:
                continue  # stateless name already known elsewhere: resolve by merging, not by title guess
            o["_guess"] = o["name"]
    links = sorted({o["link"] for o in occ if o["link"]} | set(tpl_links.values()) | {o["_guess"] for o in occ if o.get("_guess")})
    res = wiki.resolve(links)
    # track article texts
    arts = wiki.pages(sorted({r[0] for r in res.values() if r[0] and not r[1]["disambig"]}))
    qids = {t: res[t][1]["qid"] for t in links if res.get(t) and res[t][0] and res[t][1]["qid"]}
    ents = wiki.wd_entities(sorted(set(qids.values())), props="claims|labels|sitelinks")

    def canon(link):
        r = res.get(link)
        if not r or not r[0] or r[1]["disambig"]:
            return None
        a = arts.get(r[0])
        if not a or not is_track_article(a["wikitext"]):
            return None
        return r[0]

    canon_qid = {}
    for l in links:
        c = canon(l)
        if c and res[l][1].get("qid"):
            canon_qid[c] = res[l][1]["qid"]
    def too_old(c, o):
        f = venue_facts(arts[c], None)
        d = (o["obj"].get("date") or "")[:4] if isinstance(o["obj"], dict) else ""
        return bool(f.get("closed") and d.isdigit() and int(d) > f["closed"] + 1 and not o.get("link"))

    groups = collections.OrderedDict()
    for o in occ:
        sub = bool(o["name"] and SUBTRACK.match(o["name"]))
        c = canon(o["link"]) if o["link"] and not sub else None
        if c:
            f = venue_facts(arts[c], None, quick=True)
            if o["state"] and f.get("region") and f["region"] != o["state"]:
                c = None   # article is about a same-named track in another state
            elif not o["state"] and f.get("region") and o["name"] and name_states.get(norm(o["name"])) \
                    and f["region"] not in name_states[norm(o["name"])]:
                c = None   # stateless row; the same name is elsewhere tied to a different state
        if not c and o["name"] and not sub:
            c2 = tpl_links.get(norm(o["name"]))
            c = canon(c2) if c2 else None
        if not c and o.get("_guess"):
            c = canon(o["_guess"])
            if c and not o["state"] and c != o["_guess"]:
                c = None   # stateless name that only matches via a redirect: too ambiguous
            if c and too_old(c, o):
                c = None   # article's track closed before this race: a different, same-named venue
            if c:
                f = venue_facts(arts[c], None, quick=True)
                if o["state"] and f.get("region") and f["region"] != o["state"]:
                    c = None   # same name, different state: not the same venue
        key = ("wiki", c) if c else ("name", norm(o["name"] or o["city"]), o["state"])
        g = groups.setdefault(key, {"wiki": c, "occ": []})
        g["occ"].append(o)
    # merge name-only groups into wiki groups with same normalized seen-name + state
    by_seen = {}
    for k, g in groups.items():
        if g["wiki"]:
            for o in g["occ"]:
                if o["name"]:
                    by_seen[(norm(o["name"]), o["state"])] = k
    for k in list(groups):
        if k[0] == "name" and (k[1], k[2]) in by_seen:
            groups[by_seen[(k[1], k[2])]]["occ"].extend(groups.pop(k)["occ"])
    # name-only groups: merge by core name within a state; stateless ones into a unique same-name group
    by_core = collections.defaultdict(list)
    for k, g in groups.items():
        for o in g["occ"]:
            if o["name"] and o["state"]:
                by_core[(core(o["name"]), o["state"])].append(k)
    for k in list(groups):
        if k not in groups or k[0] != "name":
            continue
        g = groups[k]
        tgt = None
        if k[2]:
            cands = [x for x in dict.fromkeys(by_core.get((core(g["occ"][0]["name"] or ""), k[2]), [])) if x != k and x in groups]
            if cands:
                tgt = next((x for x in cands if x[0] == "wiki"), cands[0])
        else:
            nm0 = g["occ"][0]["name"] or ""
            exact = {x for x, gg in groups.items() if x != k and any(norm(o["name"] or "") == norm(nm0) and o["state"] for o in gg["occ"])}
            cands = exact or {x for (cn, stt), xs in by_core.items() for x in xs if cn == core(nm0) and x in groups and x != k}
            if len(cands) == 1:
                tgt = cands.pop()
        if tgt:
            groups[tgt]["occ"].extend(groups.pop(k)["occ"])

    existing_out, new_out = {}, []
    for k, g in groups.items():
        names_seen = sorted({o["name"] for o in g["occ"] if o["name"]})
        states = collections.Counter(o["state"] for o in g["occ"] if o["state"])
        st = states.most_common(1)[0][0] if states else None
        cities = collections.Counter(o["city"] for o in g["occ"] if o["city"])
        a = arts.get(g["wiki"]) if g["wiki"] else None
        info = venue_facts(a, ents.get(canon_qid.get(g["wiki"]))) if a else {}
        st = st or info.get("region")
        # match existing
        match = None
        for n in ([g["wiki"]] if g["wiki"] else []) + names_seen + info.get("aliases", []):
            if SUBTRACK.match(n or "") and n != g["wiki"]:
                continue
            for t in ex_by.get(norm(n), []):
                if not st or t["region"] == st:
                    match = t; break
            if match:
                break
        if not match and st:
            for n in names_seen + info.get("aliases", []) + ([g["wiki"]] if g["wiki"] else []):
                if SUBTRACK.match(n or ""):
                    continue
                cn = core(n)
                if not cn:
                    continue
                hits = [t for t in existing if t["region"] == st and any(core(x) == cn for x in [t["name"]] + (t.get("aliases") or []))]
                if len(hits) == 1:
                    match = hits[0]; break
        if match:
            e = existing_out.setdefault(match["id"], {"existing_id": match["id"], "names_seen": []})
            e["names_seen"] = sorted(set(e["names_seen"]) | set(names_seen))
            for o in g["occ"]:
                o["obj"]["_venue"] = match["id"]
                backfill(o["obj"], match["city"], match["region"])
            continue
        yrs = [int(o["obj"]["date"][:4]) for o in g["occ"] if isinstance(o["obj"], dict) and (o["obj"].get("date") or "")[:4].isdigit()]
        if info.get("closed") and yrs and max(yrs) > info["closed"] + 1:
            info["closed"], info["active"] = None, None   # infobox 'closed' contradicted by later races (likely an earlier layout)
        disc = sorted({DISC_TO_VENUE[o["disc"]] for o in g["occ"]})
        lvl = "national" if any(o["level"] == "national" for o in g["occ"]) else "regional"
        name = info.get("name") or (collections.Counter(o["name"] for o in g["occ"] if o["name"]).most_common(1) or [(None,)])[0][0]
        region = info.get("region") or st
        rec = {"name": name, "city": info.get("city") or (cities.most_common(1)[0][0] if cities else None),
               "region": region, "country": country_of(region), "track_type": info.get("track_type"),
               "surface": info.get("surface"), "length_mi": info.get("length_mi"), "banking_deg_turns": info.get("banking"),
               "opened": info.get("opened"), "closed": info.get("closed"), "active": info.get("active"),
               "disciplines": disc, "level": lvl, "lat": info.get("lat"), "lon": info.get("lon"),
               "sources": list(dict.fromkeys(([a["url"]] if a else []) + ([f"https://www.wikidata.org/wiki/{info['qid']}"] if info.get("qid") else []) +
                                             sorted({o["src"] for o in g["occ"]})[:3])),
               "aliases": sorted(set(info.get("aliases", [])) | {n for n in names_seen if n != name})}
        new_out.append(rec)
        for o in g["occ"]:
            o["obj"]["_venue"] = name
            backfill(o["obj"], rec["city"], rec["region"])
    # backfill event city/state from venue facts
    for ek, ev in events.items():
        if ev["track"]:
            v = next((x for x in new_out if x["name"] == ev.get("_venue")), None)
            if v:
                ev["city"], ev["state"] = v["city"], v["region"]
            elif ev.get("_venue"):
                t = next(t for t in existing if t["id"] == ev["_venue"])
                ev["city"], ev["state"] = t["city"], t["region"]
    # footprint states from venue templates
    for key, cfg in SERIES.items():
        p = pages.get(cfg.get("venues_tpl") or "")
        if not p:
            continue
        sts = set()
        for tgt, disp in parse.links(p["wikitext"]):
            c = canon(tgt)
            a = arts.get(c) if c else None
            if a:
                f = venue_facts(a, None, quick=True)
                if f.get("region"):
                    sts.add(f["region"])
        cfg["_tpl_states"] = sorted(sts)
    new_out.sort(key=lambda r: ((r["region"] or "ZZ"), r["name"] or ""))
    log(f"venues: {len(existing_out)} existing matched, {len(new_out)} new")
    return {"existing": sorted(existing_out.values(), key=lambda x: x["existing_id"]), "new": new_out}


SUBTRACK = re.compile(r"(?i)^(the )?dirt (track|oval) at\b")
GENERIC = {"speedway", "raceway", "motor", "motorsports", "motorsport", "park", "international", "race", "track", "racetrack",
           "the", "at", "of", "and", "oval", "complex", "motorplex", "speedpark", "dirt", "mile"}


def core(name):
    return " ".join(w for w in norm(name).split() if w not in GENERIC)


def backfill(obj, city, region):
    """Fill a schedule row's missing city/state from its matched venue record (never overwrite what the source gave)."""
    if "round" not in obj:
        return
    if not obj.get("state") and region:
        obj["state"] = region
        if not obj.get("city") and city:
            obj["city"] = city


def is_track_article(wt):
    head = wt[:6000].lower()
    return bool(re.search(r"infobox (race ?track|motorsport venue|racetrack|speedway)", head) or
                re.search(r"\b(speedway|raceway|race track|racetrack|motor ?plex|dirt track|oval)\b", head[:3000]))


def country_of(region):
    if not region:
        return None
    if region in parse.CA_PROV.values():
        return "CAN"
    if region in parse.US_STATES.values():
        return "USA"
    return None


NUM = re.compile(r"(\d*\.\d+|\d+)")


def _num(raw):
    t = parse.clean(raw or "")
    m = re.search(r"(\d+)\s*/\s*(\d+)", t)
    if m and int(m.group(2)):
        return round(int(m.group(1)) / int(m.group(2)), 3)
    m = NUM.search(t)
    return float(m.group(1)) if m else None


def venue_facts(a, ent, quick=False):
    wt = a["wikitext"]
    ib = extract.infobox(wt)
    out = {"name": a["title"].split(" (")[0] if not quick else None}
    loc = ib.get("location", "") + " " + ib.get("city", "") + " " + ib.get("state", "")
    city, st = None, None
    for tgt, disp in parse.links(parse.expand_templates(loc)):
        mm = re.match(r"^(.*?),\s*([A-Za-z .]+)$", tgt)
        if mm and parse.state_code(mm.group(2)):
            city, st = mm.group(1), parse.state_code(mm.group(2))
    if not st:
        txt = parse.clean(loc)
        parts = [x.strip() for x in re.split(r",|\n", txt) if x.strip()]
        for i in range(len(parts) - 1, -1, -1):
            sc = parse.state_code(parts[i].replace("United States", "").strip())
            if sc:
                st = sc
                if i > 0:
                    city = re.sub(r"^(near|outside)\s+", "", parts[i - 1], flags=re.I)
                break
    if not st:
        lead = re.sub(r"\{\{[^{}]*\}\}", "", wt[:6000])
        mm = re.search(r"(?:located|situated|based)\s+(?:in|near|just outside(?: of)?|outside(?: of)?)\s+(?:the\s+\w+\s+of\s+)?\[\[([^|\]]+?),\s*([A-Za-z .]+?)(?:\|[^\]]*)?\]\]", lead)
        if mm and parse.state_code(mm.group(2)):
            city, st = mm.group(1), parse.state_code(mm.group(2))
    out["city"], out["region"] = city, st
    if quick:
        return out
    surf = parse.clean(ib.get("surface", "")).lower()
    out["surface"] = "clay" if "clay" in surf else "dirt" if "dirt" in surf else "asphalt" if re.search(r"asphalt|paved|concrete", surf) else None
    if out["surface"] is None and re.search(r"\b(dirt|clay)\s+(oval|track)", wt[:4000], re.I):
        out["surface"] = "clay" if re.search(r"\bclay\s+(oval|track)", wt[:4000], re.I) else "dirt"
    ln = ib.get("length_mi") or ib.get("length") or ""
    out["length_mi"] = _num(ln)
    if out["length_mi"] is not None and out["length_mi"] >= 3:
        out["length_mi"] = None
    if out["length_mi"] is None and ib.get("length_km"):
        km = _num(ib["length_km"])
        out["length_mi"] = round(km / 1.609344, 3) if km and km < 5 else None
    bk = parse.clean(ib.get("banking", ""))
    m = NUM.search(bk)
    out["banking"] = float(m.group(1)) if m else None
    op = parse.clean(ib.get("opened", "") or ib.get("built", ""))
    m = re.search(r"\b(1[89]\d\d|20[0-2]\d)\b", op)
    out["opened"] = int(m.group(1)) if m else None
    cl = parse.clean(ib.get("closed", ""))
    m = re.search(r"\b(1[89]\d\d|20[0-2]\d)\b", cl)
    out["closed"] = int(m.group(1)) if m else None
    out["active"] = False if out["closed"] else None
    lay = (parse.clean(ib.get("layout", "") + " " + ib.get("shape", ""))).lower()
    out["track_type"] = "figure_eight" if "figure" in lay else "road_course" if "road" in lay else \
        "oval" if ("oval" in lay or re.search(r"\boval\b", wt[:5000], re.I)) else None
    fn = ib.get("former_names") or ib.get("former names") or ib.get("former_name") or ""
    al = [x for x in re.split(r",\s*|\n|;", parse.clean(re.sub(r"\(\s*\d{4}[^)]*\)", "", fn))) if x.strip()]
    out["aliases"] = [re.sub(r"\s*\d{4}.*$", "", x).strip() for x in al if len(x) > 3]
    c = extract.coord_from(ib.get("coordinates", "") or ib.get("coord", "")) or extract.coord_from(wt)
    if ent:
        for cl_ in ent.get("claims", {}).get("P625", []):
            v = cl_.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, dict) and "latitude" in v:
                c = (round(v["latitude"], 5), round(v["longitude"], 5)); break
        out["qid"] = ent.get("id")
        if out["closed"] is None:
            t = claim_time(ent, "P3999") or claim_time(ent, "P576")
            if t:
                out["closed"] = int(t[:4]); out["active"] = False
        if out["opened"] is None:
            t = claim_time(ent, "P1619") or claim_time(ent, "P571")
            if t:
                out["opened"] = int(t[:4])
    out["lat"], out["lon"] = (c if c else (None, None))
    return out


# ======================================================================== coverage + validation
def coverage(seasons, events, series_out, drivers, venues):
    L = ["# Dirt / Sprint / Midget touring series coverage", "",
         "Generated by `scraper/build.py` from Wikipedia + Wikidata, plus robots.txt-checked official series sites for champion lists "
         "(USMTS, ASCS, STSS, MARS) and date/track/event-name schedules (LOLMDS, USMTS, STSS, MARS, High Limit — winners not on those pages).", "",
         "Official sites used and robots.txt status: " + "; ".join(f"{k}: {v}" for k, v in sorted(wiki.ROBOTS_LOG.items())), ""]
    mism = []
    tot_races = 0
    L.append("## Series × years\n")
    for key, cfg in SERIES.items():
        s = series_out[key]
        L.append(f"### {key} — {cfg['name']} ({cfg['discipline']}, {cfg['level']})\n")
        L.append(f"Champion list span: {s['years']}.  Footprint: {', '.join(s['footprint']) or 'n/a'}\n")
        L.append("| Year | data_level | champion | races | winners known | standings | drivers (entries) | notes |")
        L.append("|---|---|---|---|---|---|---|---|")
        yrs = seasons[key]
        rng = range(min([YEAR_MIN] + list(cfg.get("extra_years", ()))), YEAR_MAX + 1)
        for y in rng:
            rec = yrs.get(y)
            if not rec:
                if s["years"] and s["years"][0] <= y <= s["years"][1]:
                    L.append(f"| {y} | — | — | 0 | 0 | 0 | 0 | gap: no source |")
                continue
            nr = len(rec["schedule"]); tot_races += nr
            nw = sum(1 for r in rec["schedule"] if r["winner"])
            nd = sum(len(c["drivers"]) for t in rec["teams"] for c in t["cars"])
            notes = []
            if nr and nw < nr:
                notes.append(f"{nr - nw} races without winner")
            # wins validation
            if rec["standings"] and nw:
                cnt = collections.Counter(r["winner"] for r in rec["schedule"] if r["winner"])
                for st in rec["standings"]:
                    if st.get("wins") is not None and not st.get("_derived"):
                        if cnt.get(st["name"], 0) != st["wins"]:
                            mism.append(f"{key} {y}: {st['name']} standings wins {st['wins']} vs schedule {cnt.get(st['name'], 0)}")
            ch = rec["champion"]["name"] if rec["champion"] else "—"
            L.append(f"| {y} | {rec['data_level']} | {ch} | {nr} | {nw} | {len(rec['standings'])} | {nd} | {'; '.join(notes)} |")
        L.append("")
    L.append("## Crown-jewel events\n")
    L.append("| event | discipline | track | winners | 1995–2026 winners | span |")
    L.append("|---|---|---|---|---|---|")
    for ek, ev in events.items():
        ys = [w["year"] for w in ev["winners"]]
        inr = sum(1 for y in ys if YEAR_MIN <= y <= YEAR_MAX)
        L.append(f"| {ek} | {ev['discipline']} | {ev['track'] or '(varies)'} | {len(ys)} | {inr} | {min(ys) if ys else '—'}–{max(ys) if ys else '—'} |")
    L.append("")
    L.append("## Totals\n")
    L.append(f"- Season files: {sum(len(v) for v in seasons.values())}; races with schedule rows: {tot_races}")
    L.append(f"- Drivers with Wikidata bios: {len([d for d in drivers.values() if d])}")
    L.append(f"- Venues: {len(venues['existing'])} matched to existing_tracks.json, {len(venues['new'])} new")
    L.append("")
    L.append("## Validation: standings wins vs schedule winners\n")
    if mism:
        L += ["- " + m for m in mism]
    else:
        L.append("- No season has both an explicit standings `wins` column and a schedule with winners that disagree (see notes).")
    L.append("")
    L.append("## Known gaps (no Wikipedia data found)\n")
    for g in GAPS:
        L.append(f"- {g}")
    L.append("")
    with open(os.path.join(OUT, "COVERAGE.md"), "w") as f:
        f.write("\n".join(L))
    MISMATCH[:] = mism


MISMATCH = []
GAPS = [
    "Southern All Star, NeSmith Chevrolet DLM, Ultimate Super Late Model Series (official site robots.txt disallows all — not used), "
    "Hav-A-Tampa / STARS, UMP/DIRTcar Summernationals, Xtreme DIRTcar, Southern Nationals, Carolina Clash, Schaeffer's Spring Nationals, "
    "Comp Cams Super Dirt Series, DIRTcar Modified Nationals, POWRi pre-2005, Iowa/Midwest regional late-model tours: no English Wikipedia "
    "article or champions list exists and no usable robots-permitted official history page was found.",
    "USAC official site (usacracing.com) robots.txt blocks Claude user agents, so it was not used.",
    "USMTS / ASCS / STSS / MARS have champion lists from the official site only; their schedules (where present) come from the official "
    "MyRacePass schedule pages, which list date, track and event name but not the winner.",
    "Crown jewels without a Wikipedia winners list: Dirt Track World Championship, North-South 100, USA Nationals, Hillbilly Hundred "
    "(article has no list), National 100, Show-Me 100, Silver Dollar Nationals, 4-Crown Nationals, Belleville Midget Nationals, Williams Grove National Open.",
    "Season articles exist only for a handful of years (WoO Sprint 2015–19, WoO LM 2018, LOLMDS 2018–21, USAC 2010s, Super DIRTcar 2018); "
    "all other years are champion_only.",
]

if __name__ == "__main__":
    main()
