#!/usr/bin/env python3
"""NASCAR-sanctioned regional touring series (1995-2006 era) + USAR Pro Cup builder.

Reuses the asphalt scraper's helpers (scraper_lib.py = unchanged copy of ../asphalt/scraper.py) and the
copied Wikipedia/Wikidata cache. Extra sources (all fetched once into dl_* folders, robots.txt checked):
  * Ultimate Racing History year race lists (dl_urh/)   -> race date / track / city / state / winner
  * RacingCalendar.net season calendars (dl_rc/)          -> full season calendars (date / circuit / event name)
  * Crittenden Automotive Library Pro Cup pages (dl_other/) -> Pro Cup schedule / pole / winner 1997-2012
Usage: python3 -I build.py   (run from any directory)
"""
import datetime as dt
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wikilib as W
import wikiparse as P
import scraper_lib as S
from config import SERIES, CURRENT_YEAR

OUT = HERE
ACCESSED = "2026-10-06"
URH_URL = "http://www.ultimateracinghistory.com/racelist.php?year={y}"
RC_URL = "https://racingcalendar.net/championship/nascar-elite-division-{s}-series/{y}"
CAL_URL = "https://www.carsandracingstuff.com/library/{p}.php"
CAL_PAGES = {"hootersprocupseries": "h/hootersprocupseries", "usaracingprocupseries": "u/usaracingprocupseries",
             "revoilprocupseries": "r/revoilprocupseries"}

URH_SERIES = {
    "nascar_southeast": ["NASCAR All Pro Series", "NASCAR Southeast Series", "NASCAR Southeast/Midwest Series"],
    "nascar_southwest": ["NASCAR Southwest Series", "NASCAR Southwest/Midwest Series"],
    "nascar_northwest": ["NASCAR Northwest Series"],
    "nascar_midwest": ["NASCAR Midwest Series", "NASCAR Southwest/Midwest Series", "NASCAR Southeast/Midwest Series"],
    "artgo": ["ARTGO Stock Car"],
    "pro_cup": ["USAR Pro Cup", "USAR Pro Cup Northern", "USAR Pro Cup Southern"],
    "nascar_sportsman": ["NASCAR Sportsman"],
    "nascar_dash": ["NASCAR Dash Series"],
    "nascar_autozone_elite": ["NASCAR Elite Division", "NASCAR AutoZone Elite"],
}
RC_KEY = {"nascar_southeast": "southeast", "nascar_southwest": "southwest", "nascar_northwest": "northwest",
          "nascar_midwest": "midwest", "artgo": "midwest"}
SPAN = {"nascar_southeast": (1995, 2006), "nascar_southwest": (1995, 2006), "nascar_northwest": (1995, 2006),
        "nascar_midwest": (1998, 2006), "artgo": (1995, 1997), "pro_cup": (1997, 2014), "nascar_dash": (1995, 2011),
        "nascar_sportsman": (1995, 1996), "nascar_autozone_elite": (2003, 2006)}
# 1996 in NASCAR top-ten standings sub-headings
STAND_1996 = {"nascar_southeast": "Slim Jim All Pro Series", "nascar_northwest": "Reb-Co Northwest Tour",
              "nascar_southwest": "Featherlite Southwest Tour", "nascar_dash": "Goody's Dash Series"}
DASH_NAMES = [(1992, 2003, "NASCAR Goody's Dash Series"), (2004, 2004, "IPOWER Dash Series"),
              (2005, 2007, "ISCARS Dash Touring"), (2008, 2011, "ISCARS Dash Touring (ASA-sanctioned)")]
PROCUP_NAMES = [(1997, 2008, "USAR Hooters Pro Cup Series"), (2009, 2011, "USARacing Pro Cup Series"),
                (2012, 2012, "CARS Rev-Oil Pro Cup Series"), (2013, 2014, "CARS X-1R Pro Cup Series")]
ELITE_NAMES = [(2003, 2003, "NASCAR Elite Division"), (2004, 2006, "NASCAR AutoZone Elite Division")]

MONTHS = S.MONTHS


def log(*a):
    print(*a, flush=True)


def name_for(tbl, y):
    for a, b, n in tbl:
        if a <= y <= b:
            return n
    return None


# ------------------------------------------------------------------ source loaders

def load_urh():
    d = json.load(open(os.path.join(OUT, "dl_urh", "parsed.json")))
    return {int(y): rs for y, rs in d.items()}


def load_rc():
    d = json.load(open(os.path.join(OUT, "dl_rc", "parsed.json")))
    out = {}
    for k, (title, rows) in d.items():
        s, y = k.rsplit("_", 1)
        out[(s, int(y))] = (title, rows)
    return out


def load_cal():
    d = json.load(open(os.path.join(OUT, "dl_other", "cal_parsed.json")))
    return {int(y): v for y, v in d.items()}


def urh_date(s):
    try:
        return dt.datetime.strptime(s.strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def rc_date(s, y):
    m = re.match(r"(\d{1,2})\s*([A-Za-z]{3})", s or "")
    if not m:
        return None
    try:
        return dt.date(y, MONTHS[m.group(2).lower()], int(m.group(1)))
    except (KeyError, ValueError):
        return None


def cal_date(s, y):
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2})", s or "")
    if not m or m.group(1).lower() not in MONTHS:
        return None
    try:
        return dt.date(y, MONTHS[m.group(1).lower()], int(m.group(2)))
    except ValueError:
        return None


def core(n):
    return S.core(n)


def same_track(a, b):
    ca, cb = set(core(a).split()), set(core(b).split())
    return bool(ca & cb) or S.norm(a) == S.norm(b)


# ------------------------------------------------------------------ row helpers

# RacingCalendar.net circuit names that are current-day names, duplicates or evident data-entry errors.
# canonical name, city, state (facts: well-known track locations); see COVERAGE.md caveats.
TRACK_FIX = {
    "Larry King Law's Langley Speedway": ("Langley Speedway", "Hampton", "VA"),
    "Lonesome Pine Raceway": ("Lonesome Pine Speedway", "Coeburn", "VA"),
    "Suntana Speedway": ("Suntana Raceway", "Springville", "UT"),
    "Suntana Raceway": ("Suntana Raceway", "Springville", "UT"),
    "Wenatchee Valley Raceway": ("Wenatchee Valley Super Oval", "East Wenatchee", "WA"),
    "Wenatchee Valley Super Oval": ("Wenatchee Valley Super Oval", "East Wenatchee", "WA"),
    "Suika Circuit": ("Sandia Motor Speedway", "Albuquerque", "NM"),   # RC lists the 'Sandia 125' at Suika (Japan)
    "Rocky Mountain Raceway": ("Rocky Mountain Raceway", "West Valley City", "UT"),
    "Redwood Acres Raceway": ("Redwood Acres Raceway", "Eureka", "CA"),
    "Los Angeles Street Race Course": ("Los Angeles Street Race Course", "Los Angeles", "CA"),
    "Shenandoah Speedway": ("Shenandoah Speedway", "Shenandoah", "VA"),
    "Darana Motorsports Park Millington": ("Memphis Motorsports Park", "Millington", "TN"),
    "Coastal Plains Raceway": ("Coastal Plains Raceway", "Jacksonville", "NC"),
}
FIXED = []
EXISTING = {}
for _t in json.load(open(os.path.join(os.path.dirname(OUT), "existing_tracks.json"))):
    for _n in [_t["name"]] + _t.get("aliases", []):
        EXISTING.setdefault(S.norm(_n), _t)


def mkrow(date, race, track, city, state, winner):
    if track in TRACK_FIX:
        nt, c, st = TRACK_FIX[track]
        if nt != track:
            FIXED.append((track, nt, date.isoformat() if date else None))
        track, city, state = nt, city or c, state or st
    if state and not re.fullmatch(r"[A-Z]{2}", state):
        state = S.REGION_NAMES.get(state)
    m = re.match(r"^(.*?)\s*\(([A-Z]{2})\)$", track or "")
    if m:
        track, state = m.group(1), state or m.group(2)
    if not state and track:
        ex = EXISTING.get(S.norm(track))
        if ex:
            city, state = city or ex.get("city"), ex.get("region")
    return OrderedDict(round=None, date=date.isoformat() if date else None, race=race or None, track=track,
                       track_wiki=S.reg(track), city=city, state=state, winner=winner or None, winner_wiki=None)


TRACK_LOC = {}   # norm(track name) -> (city, state) learned from URH rows


def learn_locations(urh):
    for y, rs in urh.items():
        for r in rs:
            if r["state"] and re.fullmatch(r"[A-Z]{2}", r["state"]):
                TRACK_LOC.setdefault(S.norm(r["track"]), (r["city"], r["state"]))


def merge_rc_urh(rc_rows, urh_rows, y):
    """RC calendar (complete list, no winners) + URH results (winners). Returns (rows, n_matched)."""
    out, used = [], set()
    urh_d = [(urh_date(r["date"]), r) for r in urh_rows]
    pre = {}  # rc index -> urh index
    for pass_no, window in ((1, 3), (2, 45)):
        for i, rr in enumerate(rc_rows):
            if i in pre:
                continue
            d = rc_date(rr["date"], y)
            cands = []
            for j, (ud, ur) in enumerate(urh_d):
                if j in pre.values() or not ud or not d:
                    continue
                gap = abs((ud - d).days)
                if gap <= window and same_track(rr["circuit"], ur["track"]):
                    cands.append((gap, j))
            if pass_no == 1 and not cands:
                cands = [(0, j) for j, (ud, ur) in enumerate(urh_d)
                         if j not in pre.values() and ud and d and ud == d]
                if len(cands) != 1:
                    cands = []
            if pass_no == 2 and len(cands) != 1:
                continue
            if cands:
                pre[i] = min(cands)[1]
    for i, j in pre.items():
        RC_PERIOD[rc_rows[i]["circuit_slug"]].append((y, urh_d[j][1]["track"], urh_d[j][1]["city"], urh_d[j][1]["state"]))
    for i, rr in enumerate(rc_rows):
        d = rc_date(rr["date"], y)
        best = (0, pre[i]) if i in pre else None
        if best is not None:
            j = best[1]
            used.add(j)
            ud, ur = urh_d[j]
            out.append(mkrow(ud, ur["race"] or rr["event"], ur["track"], ur["city"], ur["state"],
                             "; ".join(ur["winners"]) if ur["winners"] else None))
        else:
            out.append(("rc", d, rr))
    for j, (ud, ur) in enumerate(urh_d):
        if j not in used:
            out.append(mkrow(ud, ur["race"], ur["track"], ur["city"], ur["state"], "; ".join(ur["winners"]) or None))
    PENDING.append((out, y))
    return out, len(used)


def resolve_pending():
    """RC-only rows: use the period track name URH used for the same RC circuit in the nearest year (<=6 y)."""
    for out, y in PENDING:
        for k, x in enumerate(out):
            if isinstance(x, tuple):
                _, d, rr = x
                name, city, state = rr["circuit"], None, None
                near = sorted(RC_PERIOD.get(rr["circuit_slug"], []), key=lambda t: abs(t[0] - y))
                if near and abs(near[0][0] - y) <= 6:
                    name, city, state = near[0][1], near[0][2], near[0][3]
                if not state:
                    city, state = TRACK_LOC.get(S.norm(name), TRACK_LOC.get(S.norm(rr["circuit"]), (city, state)))
                out[k] = mkrow(d, rr["event"], name, city, state, None)
        out.sort(key=lambda r: r["date"] or "9999")
        for i, r in enumerate(out):
            r["round"] = i + 1


RC_PERIOD = defaultdict(list)
PENDING = []


def urh_only(urh_rows):
    out = []
    for ur in sorted(urh_rows, key=lambda r: urh_date(r["date"]) or dt.date(9999, 1, 1)):
        out.append(mkrow(urh_date(ur["date"]), ur["race"], ur["track"], ur["city"], ur["state"],
                         "; ".join(ur["winners"]) or None))
    for i, r in enumerate(out):
        r["round"] = i + 1
    return out


PLAYOFF_RE = re.compile(r"memorial|four champions|hooters 300|championship", re.I)


def procup_rows(cal_year, y, urh_rows, crosscheck):
    out = []
    urh_d = [(urh_date(r["date"]), r) for r in urh_rows]
    for r in cal_year["races"]:
        d = cal_date(r["date"], y)
        race = r["race"]
        if r["division"]:
            race = f"{race} ({'Southern' if r['division'].endswith('South') else 'Northern'} Division)"
        elif y >= 2001 and y <= 2008:
            race = f"{race} ({'Four Champions Championship Series' if PLAYOFF_RE.search(r['race'] or '') else 'combined divisions'})"
        city, state = TRACK_LOC.get(S.norm(r["track"]), (None, None))
        # URH cross-check (1997-2002)
        m = None
        for ud, ur in urh_d:
            if ud and d and abs((ud - d).days) <= 2 and same_track(ur["track"], r["track"]):
                m = ur; break
        if m is None:
            same = [ur for ud, ur in urh_d if ud and d and ud == d]
            if len(same) == 1:
                m = same[0]
        if m:
            city, state = city or m["city"], state or m["state"]
            if m["winners"] and S.norm(m["winners"][0]) != S.norm(r["winner"] or ""):
                crosscheck.append(f"pro_cup {y} {d}: Crittenden winner '{r['winner']}' vs URH '{m['winners'][0]}' at {r['track']}")
        elif urh_rows:
            crosscheck.append(f"pro_cup {y} {d}: race at {r['track']} not in URH list")
        out.append(mkrow(d, race, r["track"], city, state, r["winner"]))
    out.sort(key=lambda r: r["date"] or "9999")
    for i, r in enumerate(out):
        r["round"] = i + 1
    return out


# ------------------------------------------------------------------ champions

def champions():
    ch = defaultdict(dict)   # key -> year -> (name, wiki, src_url)

    def put(key, vals, pg, y0=1995, y1=2026):
        if not pg:
            return
        u = W.oldid_url(pg["title"], pg["revid"])
        for y, v in vals.items():
            if y0 <= y <= y1 and y not in ch[key]:
                ch[key][y] = (v[0], v[1], u)
    v, pg = S.year_table_values("NASCAR AutoZone Elite Division, Southeast Series", "List of champions (NASCAR All Pro", "champion")
    put("nascar_southeast", v, pg)
    v, pg = S.year_table_values("NASCAR AutoZone Elite Division, Northwest Series", "List of champions", "champion")
    put("nascar_northwest", v, pg)
    for h in ("NASCAR AutoZone Elite Division, Southwest Series", "NASCAR Featherlite Southwest Tour"):
        v, pg = S.year_list_values("NASCAR AutoZone Elite Division, Southwest Series", h)
        put("nascar_southwest", v, pg)
    v, pg = S.year_list_values("ARTGO", "Past NASCAR/Midwest Champions")
    put("nascar_midwest", v, pg, 1998, 2006)
    v, pg = S.year_list_values("ARTGO", "Past ARTGO Champions")
    put("artgo", v, pg, 1995, 1997)
    v, pg = S.year_list_values("CARS Tour", "ProCup Champions (2001")
    put("pro_cup", v, pg, 2001, 2014)
    v, pg = S.year_list_values("CARS Tour", "ProCup Series Champions (1997")
    put("pro_cup", v, pg, 1997, 2000)
    v, pg = S.year_list_values("ISCARS Dash Touring Series", "List of champions")
    put("nascar_dash", v, pg, 1995, 2011)
    return ch


# ------------------------------------------------------------------ driver wiki resolution for non-Wikipedia names

def resolve_people(names, known):
    """name -> Wikipedia title of the racing driver, verified by page text. known: norm(name)->title from WP links."""
    out = {}
    todo = []
    for n in names:
        k = S.norm(n)
        if k in known:
            out[n] = known[k]
        else:
            todo.append(n)
    cands = {}
    for n in todo:
        base = [n]
        sp = re.sub(r"\b([A-Z])\.(?=[A-Z])", r"\1. ", n)
        if sp != n:
            base.append(sp)
        c = []
        for b in base:
            c += [f"{b} (racing driver)", f"{b} (NASCAR driver)", f"{b} (driver)", f"{b} (racer)", b]
        cands[n] = c
    allc = sorted({c for v in cands.values() for c in v})
    res = W.resolve(allc)
    pages_needed = sorted({res[c]["title"] for c in allc if res.get(c) and not res[c]["disambig"]})
    pgs = W.pages(pages_needed) if pages_needed else {}
    for n in todo:
        for c in cands[n]:
            v = res.get(c)
            if not v or v["disambig"]:
                continue
            pg = pgs.get(v["title"])
            if not pg:
                continue
            lead = pg["text"][:6000]
            if re.search(r"racing driver|race car driver|stock car|NASCAR|late model|racecar driver", lead, re.I):
                out[n] = v["title"]
                break
    return out


# ------------------------------------------------------------------ main build

def build():
    W.seed_page_cache()
    W.seed_resolve_map()
    urh, rc, cal = load_urh(), load_rc(), load_cal()
    learn_locations(urh)
    ch = champions()
    seasons, meta, notes, crosscheck = {}, {}, defaultdict(dict), []
    wp_dash = {}
    for y in range(1997, 2004):
        pg = W.page(f"{y} NASCAR Goody's Dash Series")
        if pg:
            wp_dash[y] = pg
    st96 = {}
    for key, sub in STAND_1996.items():
        for hp, tt, pg in S.table_by_heading("1996 in NASCAR", sub):
            heads, data, _ = S.table_struct(tt)
            st = S.parse_standings(heads, data)
            if st:
                st96[key] = (st, W.oldid_url(pg["title"], pg["revid"]))
                break
    for key in SERIES:
        y0, y1 = SPAN[key]
        for y in range(y0, y1 + 1):
            sched, stand, srcs, official = [], [], [], None
            uyr = [r for r in urh.get(y, []) if r["series"] in URH_SERIES.get(key, [])]
            src_kind = None
            if key in RC_KEY and (RC_KEY[key], y) in rc and rc[(RC_KEY[key], y)][1]:
                title, rows = rc[(RC_KEY[key], y)]
                if True:
                    if (key == "artgo") == title.startswith("ARTGO"):
                        sched, nm = merge_rc_urh(rows, uyr, y)
                        official = title
                        srcs.append(RC_URL.format(s=RC_KEY[key], y=y))
                        if uyr:
                            srcs.append(URH_URL.format(y=y))
                        src_kind = "rc+urh" if uyr else "rc"
                        notes[key][y] = dict(rc=len(rows), urh=len(uyr), matched=nm)
            elif key == "pro_cup" and y in cal:
                sched = procup_rows(cal[y], y, uyr, crosscheck)
                srcs.append(CAL_URL.format(p=CAL_PAGES[cal[y]["page"]]))
                if uyr:
                    srcs.append(URH_URL.format(y=y))
                src_kind = "cal+urh" if uyr else "cal"
                notes[key][y] = dict(cal=len(cal[y]["races"]), urh=len(uyr))
            elif key == "nascar_dash" and y in wp_dash:
                pg = wp_dash[y]
                sched, stand, _ = S.parse_season_page(pg, y)
                srcs.append(W.oldid_url(pg["title"], pg["revid"]))
                official = re.sub(r"^\d{4}\s+", "", pg["title"])
                src_kind = "wikipedia season article"
            elif uyr:
                sched = urh_only(uyr)
                srcs.append(URH_URL.format(y=y))
                src_kind = "urh (partial)"
                notes[key][y] = dict(urh=len(uyr))
            if y == 1996 and key in st96 and not stand:
                stand = st96[key][0]
                srcs.append(st96[key][1])
            if key == "pro_cup":
                official = name_for(PROCUP_NAMES, y)
            elif key == "nascar_dash" and not official:
                official = name_for(DASH_NAMES, y)
            elif key == "nascar_autozone_elite":
                official = name_for(ELITE_NAMES, y)
                for r in sched:
                    r["race"] = (r["race"] or "") + " (Elite Division race)"
            elif key == "nascar_sportsman":
                official = "NASCAR Sportsman Division"
            champ = None
            if y in ch.get(key, {}):
                nm, wk, u = ch[key][y]
                champ = OrderedDict(name=nm, wiki=wk)
                if u not in srcs:
                    srcs.append(u)
            elif stand and y < CURRENT_YEAR and stand[0]["pos"] == 1 and key != "nascar_autozone_elite":
                champ = OrderedDict(name=stand[0]["name"], wiki=stand[0]["wiki"])
            if not (sched or stand or champ):
                continue
            seasons[(key, y)] = OrderedDict(series=key, year=y, official_name=official, data_level=None,
                                            champion=champ, teams=[], standings=stand, schedule=sched, sources=srcs)
            notes[key].setdefault(y, {})["src"] = src_kind
        ys = sorted(y for (k, y) in seasons if k == key)
        nby = []
        for y in ys:
            nm = seasons[(key, y)]["official_name"]
            if not nm:
                continue
            if nby and nby[-1]["name"] == nm and nby[-1]["to"] == y - 1:
                nby[-1]["to"] = y
            else:
                nby.append(OrderedDict([("from", y), ("to", y), ("name", nm)]))
        main_pg = W.page(SERIES[key]["main"])
        msrc = [W.oldid_url(main_pg["title"], main_pg["revid"])] if main_pg else []
        for (k, y), d in sorted(seasons.items()):
            if k != key:
                continue
            for u in d["sources"]:
                if "racingcalendar.net/championship" in u:
                    u = u.rsplit("/", 1)[0]
                elif "ultimateracinghistory" in u:
                    u = "http://www.ultimateracinghistory.com/byyear.php"
                elif "wikipedia.org" in u and re.search(r"title=\d{4}", u):
                    continue  # season / year articles are cited per season
                if u not in msrc:
                    msrc.append(u)
        meta[key] = OrderedDict(name=SERIES[key]["name"], names_by_year=nby, discipline=SERIES[key]["discipline"],
                                years=[ys[0], ys[-1]] if ys else None, footprint=[], level=SERIES[key]["level"],
                                sources=msrc)
    resolve_pending()
    # umbrella description
    meta["nascar_autozone_elite"]["type"] = "umbrella"
    meta["nascar_autozone_elite"]["divisions"] = ["nascar_southeast", "nascar_southwest", "nascar_northwest", "nascar_midwest"]
    meta["nascar_autozone_elite"]["division_champions"] = OrderedDict(
        (str(y), OrderedDict((k, ((seasons.get((k, y)) or {}).get("champion") or {}).get("name"))
                             for k in meta["nascar_autozone_elite"]["divisions"])) for y in range(2003, 2007))
    meta["nascar_autozone_elite"]["notes"] = ("Umbrella name for NASCAR's four regional late-model tours; season files hold "
                                              "only the year-end Toyota All-Star Showdown Elite Division race at Irwindale.")
    meta["pro_cup"]["notes"] = ("2001-2008: separate Northern and Southern Division regular seasons (race names suffixed "
                                "'(Northern Division)' / '(Southern Division)') followed by the Four Champions "
                                "Championship Series that decided the overall champion; divisions merged 2009.")
    meta["nascar_southeast"]["notes"] = ("Slim Jim All Pro Series and NASCAR Southeast Series are the same lineage "
                                         "(All Pro 1991-2002, Kodak Southeast 2003, AutoZone Elite Division Southeast 2004-2006).")
    # resolve winner links for non-Wikipedia names
    known = {}
    for s in seasons.values():
        for r in s["standings"]:
            if r["wiki"]:
                known.setdefault(S.norm(r["name"]), r["wiki"])
        if s["champion"] and s["champion"]["wiki"]:
            known.setdefault(S.norm(s["champion"]["name"]), s["champion"]["wiki"])
        for r in s["schedule"]:
            if r["winner_wiki"]:
                known.setdefault(S.norm(r["winner"]), r["winner_wiki"])
    names = sorted({w for s in seasons.values() for r in s["schedule"] if r["winner"] and not r["winner_wiki"]
                    for w in [r["winner"]]})
    log("resolving people:", len(names))
    ppl = resolve_people(names, known)
    for s in seasons.values():
        for r in s["schedule"]:
            if r["winner"] and not r["winner_wiki"]:
                r["winner_wiki"] = S.reg(ppl.get(r["winner"]))
        for r in s["standings"]:
            S.reg(r["wiki"])
        if s["champion"]:
            S.reg(s["champion"]["wiki"])
    return seasons, meta, notes, crosscheck


def write_sources(seasons):
    srcs = OrderedDict()
    srcs["src:wikipedia"] = dict(name="English Wikipedia (series, season and year articles)", url="https://en.wikipedia.org",
                                 kind="wiki", reliability="medium", license="CC BY-SA 4.0", accessed=ACCESSED)
    srcs["src:wikidata"] = dict(name="Wikidata", url="https://www.wikidata.org", kind="wiki", reliability="medium",
                                license="CC0", accessed=ACCESSED)
    srcs["src:urh"] = dict(name="Ultimate Racing History (race-by-race year lists)", url="http://www.ultimateracinghistory.com/byyear.php",
                           kind="historical_db", reliability="medium", license=None, accessed=ACCESSED)
    srcs["src:racingcalendar"] = dict(name="RacingCalendar.net championship calendars (user-submitted)",
                                      url="https://racingcalendar.net/championships", kind="historical_db",
                                      reliability="medium", license=None, accessed=ACCESSED)
    srcs["src:crittenden"] = dict(name="The Crittenden Automotive Library - Pro Cup series pages",
                                  url="https://www.carsandracingstuff.com/library/h/hootersprocupseries.php",
                                  kind="secondary", reliability="medium", license=None, accessed=ACCESSED)
    srcs["src:speedwaydigest"] = dict(name="Speedway Digest news (2013 CARS X-1R Pro Cup naming)",
                                      url="https://speedwaydigest.com/index.php/news/racing-news/10051-clay-rogers-makes-his-return-to-the-x-1r-pro-cup-series-worth-10-000/",
                                      kind="news", reliability="medium", license=None, accessed=ACCESSED)
    json.dump(srcs, open(os.path.join(OUT, "sources.json"), "w"), indent=1)
    led = []
    def L(src, url, info, rel, conf, ents, notes=""):
        led.append(OrderedDict(source=src, url=url, info=info, accessed=ACCESSED, reliability=rel, confidence=conf,
                               notes=notes, entities=ents))
    for (k, y), s in sorted(seasons.items()):
        for u in s["sources"]:
            src = ("src:wikipedia" if "wikipedia.org" in u else "src:urh" if "ultimateracinghistory" in u else
                   "src:racingcalendar" if "racingcalendar" in u else "src:crittenden" if "carsandracingstuff" in u else "src:other")
            what = {"src:wikipedia": "champion / standings / season article", "src:urh": "race dates, tracks, winners",
                    "src:racingcalendar": "season calendar (dates, circuits, event names, official season name)",
                    "src:crittenden": "Pro Cup schedule with pole sitters and winners"}.get(src, "")
            L(src, u, f"{k} {y}: {what}", "medium", "medium" if src != "src:wikipedia" else "high", [f"series:{k}"])
    L("src:speedwaydigest", srcs["src:speedwaydigest"]["url"], "2013 series name 'CARS X-1R Pro Cup Series'", "medium", "medium",
      ["series:pro_cup"], "Wikipedia CARS Tour article says Rev-Oil title sponsorship through 2013; news says X-1R from 2013.")
    with open(os.path.join(OUT, "ledger.jsonl"), "w") as f:
        for r in led:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    unav = [
        dict(source="racing-reference.info", url="https://www.racing-reference.info/", reason="Cloudflare block / project rule: never fetched",
             checked=ACCESSED, replacement_source="src:urh, src:racingcalendar, src:crittenden, src:wikipedia"),
        dict(source="thethirdturn.com", url="https://thethirdturn.com/", reason="robots.txt Disallow: / ; project rule: never fetched",
             checked=ACCESSED, replacement_source="src:urh, src:racingcalendar, src:crittenden, src:wikipedia"),
        dict(source="stockcarracing.fandom.com (Stock Car Racing Wiki)", url="https://stockcarracing.fandom.com/",
             reason="Cloudflare challenge page on robots.txt; also mirrors Third Turn-style 'Central' pages - not used",
             checked=ACCESSED, replacement_source="src:urh, src:racingcalendar"),
        dict(source="jayski.com", url="https://www.jayski.com/", reason="Cloudflare challenge page", checked=ACCESSED,
             replacement_source="src:urh"),
        dict(source="web.archive.org (defunct usarprocup.com / nascar regional sites)", url="https://web.archive.org/",
             reason="HTTP 429 / connection reset through proxy; not retried", checked=ACCESSED,
             replacement_source="src:crittenden"),
    ]
    json.dump(unav, open(os.path.join(OUT, "unavailable.json"), "w"), indent=1)


def main():
    seasons, meta, notes, crosscheck = build()
    res = S.resolve_links()
    S.finalize(seasons, meta, res)
    S.fill_venue_locations(seasons, res)
    venues, _ = S.build_venues(seasons, res)
    drivers = S.build_drivers(seasons, res)
    S.write_outputs(seasons, meta, venues, drivers)
    json.dump(dict(notes={k: {str(y): v for y, v in d.items()} for k, d in notes.items()}, crosscheck=crosscheck,
                   track_fixes=sorted({(a, b) for a, b, _ in FIXED})),
              open(os.path.join(OUT, "build_notes.json"), "w"), indent=1)
    write_sources(seasons)
    log("seasons:", len(seasons), "venues existing/new:", len(venues["existing"]), len(venues["new"]), "drivers:", len(drivers))
    log("crosscheck issues:", len(crosscheck))


if __name__ == "__main__":
    main()
