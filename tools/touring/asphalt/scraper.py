#!/usr/bin/env python3
"""Asphalt short-track touring-series history scraper (Wikipedia + Wikidata only).

Re-runnable: every HTTP response is cached under ./cache (delete a file to refresh it).
Usage: python3 scraper.py            # build everything
"""
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wikilib as W
import wikiparse as P
from config import SERIES, EVENTS, YEARS, CURRENT_YEAR, US_STATES, CA_PROVINCES, REGION_NAMES, ABBR_TO_COUNTRY

OUT = W.BASE
MONTHS = {m.lower(): i + 1 for i, m in enumerate(P.MONTHS)}
MONTHS.update({m[:3].lower(): i + 1 for i, m in enumerate(P.MONTHS)})
MONTHS["sept"] = 9

# ---------------------------------------------------------------- helpers

def log(*a):
    print(*a, flush=True)


def norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("&", "and")
    s = re.sub(r"[’'`.]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_name(s):
    s = (s or "").split("\n")[0]
    s = re.sub(r"\((?:R|i|I|r|\d+|R\s*\d*)\)", "", s)
    s = re.sub(r"[†‡*#^§¶]+", "", s)
    s = re.sub(r"\[\w\]", "", s)
    return re.sub(r"\s+", " ", s).strip(" ,;-–")


def person(s):
    s = clean_name(s)
    s = re.sub(r"\s*\([^)]*\)", "", s)
    s = re.sub(r"\s+\d+(?:\s+\d+)*$", "", s)  # trailing counts like "Name 8 3"
    s = s.strip(" ,;-–")
    if re.fullmatch(r"(references?|sources?|notes?|key)", s, re.I):
        return ""
    return s


def list_name(txt, pairs):
    """Driver name from a '* YEAR Name ...' list item."""
    if pairs and norm(txt).startswith(norm(pairs[0][1])) and norm(pairs[0][1]):
        return person(pairs[0][1])
    t = re.split(r"\s+[-–—]\s+|\(|,|;", txt)[0]
    t = re.sub(r"\s+(ASA|ARCA|NASCAR|ARTGO|Wisconsin Late|USAR|CRA|PASS)\b.*$", "", t)
    return person(t)


def parse_int(s):
    if s is None:
        return None
    m = re.search(r"-?\d[\d,]*", s.replace("−", "-"))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_date(s, year):
    if not s:
        return None
    s = s.replace(" ", " ")
    m = re.search(r"((?:19|20)\d\d)-(\d\d)-(\d\d)", s)
    if m:
        return m.group(0)
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})", s)
    if m and m.group(1).lower() in MONTHS:
        y = year
        my = re.search(r"\b((?:19|20)\d\d)\b", s)
        if my:
            y = int(my.group(1))
        try:
            return dt.date(y, MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})", s)
    if m and m.group(2).lower() in MONTHS:
        try:
            return dt.date(year, MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def split_location(loc):
    """'Daytona Beach, Florida' -> ('Daytona Beach', 'FL')."""
    if not loc:
        return None, None
    loc = loc.split("\n")[0].strip()
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    state = None
    if parts:
        last = parts[-1]
        if last in REGION_NAMES:
            state = REGION_NAMES[last]; parts = parts[:-1]
        elif re.fullmatch(r"[A-Z]{2}", last) and last in ABBR_TO_COUNTRY:
            state = last; parts = parts[:-1]
        elif last in ("Canada", "USA", "United States", "U.S."):
            parts = parts[:-1]
            if parts and parts[-1] in REGION_NAMES:
                state = REGION_NAMES[parts[-1]]; parts = parts[:-1]
    city = ", ".join(parts) if parts else None
    return city, state


def cells_text(row):
    return [P.cell_text(c["raw"]) for c in row]


def is_header_row(row):
    real = [c for c in row if not c.get("spanned")]
    if not real:
        real = row
    h = sum(1 for c in real if c["header"])
    return h > len(real) / 2


def table_struct(tt):
    grid, cap = P.parse_table(tt)
    hdr_rows, data = [], []
    for r in grid:
        if not data and is_header_row(r):
            hdr_rows.append(r)
        else:
            if is_header_row(r) and data:
                # repeated header inside table (e.g. CARS champions table) -> skip
                txts = [P.cell_text(c["raw"])[0].lower() for c in r]
                if any(t in ("year", "pos", "pos.", "driver") for t in txts):
                    continue
            data.append(r)
    HW = {"pos", "pos.", "driver", "finish", "fin", "start", "car #", "points", "total", "wins", "track", "date",
          "race", "year", "no.", "team", "starts", "laps", "rank", "manufacturer"}
    while data:
        txts = [P.cell_text(c["raw"])[0].lower().strip() for c in data[0]]
        if sum(1 for t in txts if t in HW) >= 2 and not any(re.fullmatch(r"\d+", t) for t in txts[:1]):
            hdr_rows.append(data.pop(0))
        else:
            break
    ncol = max([len(r) for r in grid] or [0])
    heads = []
    for i in range(ncol):
        parts = []
        for r in hdr_rows:
            if i < len(r):
                t = P.cell_text(r[i]["raw"])[0].replace("\n", " ")
                if t and t not in parts:
                    parts.append(t)
        heads.append(parts)
    return heads, data, cap


def hlast(h):
    return (h[-1] if h else "").lower().strip()


def hall(h):
    return " | ".join(h).lower()


def find_col(heads, pred, start=0):
    for i, h in enumerate(heads):
        if i >= start and pred(hlast(h), hall(h)):
            return i
    return None


def cell(row, i):
    if i is None or i >= len(row):
        return "", [], []
    return P.cell_text(row[i]["raw"])


# column predicates
def is_pos(l, a):
    return l in ("pos", "pos.", "position", "rank", "place", "rk", "pos.no.") or l.startswith("pos")


def is_finish(l, a):
    return l in ("fin", "finish", "fin.", "pos (fin)")


def is_driver(l, a):
    return ("driver" in l and "winning" not in l and "winner" not in l and "pole" not in l and "laps" not in l) or l in ("name", "drivers", "driver(s)", "race driver", "race drivers")


def is_winner(l, a):
    return ("winner" in l or "winning driver" in l) and "pole" not in l and "team" not in l and "rookie" not in l


def is_points(l, a):
    return l in ("points", "pts", "pts.", "total", "point", "pts", "total points") or l.startswith("points")


def is_track(l, a):
    return l in ("track", "racetrack", "tracks", "venue", "circuit", "track name", "speedway", "race track", "location/track")


def is_date(l, a):
    return l.startswith("date")


def is_race(l, a):
    return l in ("race", "race title", "race name", "event", "event name", "name", "race title(s)", "races", "title", "race name/title")


def is_city(l, a):
    return l in ("location", "city", "town", "city/state", "locale", "city, state")


def is_state(l, a):
    return l in ("state", "province", "state/province")


def is_round(l, a):
    return l in ("no.", "no", "rnd", "rd", "rd.", "round", "#", "race", "race no.", "race #", "rnd.")


def is_team(l, a):
    return l in ("team", "teams", "car owner", "owner", "team owner", "owner(s)", "team(s)", "owners", "entrant") or l.startswith("team")


def is_make(l, a):
    return l in ("manufacturer", "make", "manufacturers", "car", "mfr.", "manuf.", "chassis/make", "engine", "maker", "make/model") or l.startswith("manufacturer")


def is_number(l, a):
    return l in ("no.", "no", "#", "car #", "number", "car no.", "car number", "num")


def is_rounds(l, a):
    return l in ("races", "rounds", "round(s)", "race(s)", "races entered", "rnds", "rnd(s)", "rounds entered", "schedule")


STAT_COLS = {
    "wins": lambda l, a: l in ("wins",),
    "starts": lambda l, a: l in ("starts", "races started"),
    "top5": lambda l, a: l.replace(" ", "").replace("-", "") in ("top5", "top5s", "t5", "t5s"),
    "top10": lambda l, a: l.replace(" ", "").replace("-", "") in ("top10", "top10s", "t10", "t10s"),
}
NONRESULT_COLS = ("att", "poles", "pole", "diff", "behind", "laps", "led", "earnings", "money", "no.", "car #", "#", "make", "team", "owner", "hometown", "bonus", "pen", "penalty", "car", "dnf", "avg")


# ---------------------------------------------------------------- link registry (resolved in bulk)
LINKS = set()


def reg(t):
    if t:
        LINKS.add(t)
    return t


def first_link(pairs, text=None):
    """Return the link target best matching visible text."""
    if not pairs:
        return None
    if text:
        for tgt, txt in pairs:
            if norm(txt) and norm(txt) in norm(text):
                return tgt
    return pairs[0][0]


# ---------------------------------------------------------------- season article parsing

def classify(heads):
    has = lambda pred: find_col(heads, pred) is not None
    if has(is_finish) and has(is_driver) and not has(is_pos):
        return "raceresult"
    if has(is_pos) and has(is_driver):
        return "standings"
    if has(is_track) and not has(is_pos):
        return "schedule"
    if (has(is_race) or has(is_round)) and has(is_winner):
        return "results"
    if (has(is_team) or has(is_make)) and has(is_driver) and (has(is_number)):
        return "teams"
    return None


def parse_schedule_rows(heads, data, year, division=None):
    ci = dict(
        round=find_col(heads, lambda l, a: is_round(l, a) and l != "race" ),
        date=find_col(heads, is_date),
        race=find_col(heads, is_race),
        track=find_col(heads, is_track),
        city=find_col(heads, is_city),
        state=find_col(heads, is_state),
    )
    if ci["race"] is not None and ci["race"] == ci["round"]:
        ci["round"] = None
    win_cols = [i for i, h in enumerate(heads) if is_winner(hlast(h), hall(h))]
    if division and win_cols:
        dc = [i for i in win_cols if re.search(division["winner"], " ".join(heads[i]), re.I)]
        win_cols = dc
        if not dc:
            return None
    else:
        # prefer overall race winner column ("Race winner" / "Winning driver")
        win_cols = win_cols[:1]
    wc = win_cols[0] if win_cols else None
    rows = []
    for r in data:
        if all(c.get("spanned") for c in r):
            continue
        rt = " ".join(P.cell_text(c["raw"])[0] for c in r if not c.get("spanned")).lower()
        if re.search(r"cancel+ed|not held|\bcancelled\b", rt):
            continue
        tr_text, _, tr_pairs = cell(r, ci["track"])
        if ci["track"] is not None and not tr_text:
            continue
        if tr_text and (not re.match(r"[\w\"'(]", tr_text) or re.match(r"(source|note|reference|sources|notes|references)\b", tr_text, re.I)):
            continue
        if ci["track"] is not None and len({id(c) for c in r}) <= 2 and len(r) > 3:
            continue  # note row spanning the table
        lines = tr_text.split("\n") if tr_text else []
        track = lines[0] if lines else None
        track_wiki = None
        if tr_pairs:
            track_wiki = first_link(tr_pairs, track)
            # strip ", City, State" embedded in track cell
        mparen = re.match(r"^(.*?)\s*\(([^()]+,[^()]+)\)\s*$", track or "")
        if mparen and ci["city"] is None:
            track = mparen.group(1)
            lines = [track, mparen.group(2)]
        if track and len(track) > 70 or re.search(r"\b(postponed|due to|was moved|rescheduled)\b", track or "", re.I):
            continue
        if track and "," in track and ci["city"] is None:
            seg = [s.strip() for s in track.split(",")]
            track_txt = seg[0]
            loc = ", ".join(seg[1:])
        else:
            track_txt = track
            loc = None
        city = state = None
        if ci["city"] is not None:
            ct, _, cpairs = cell(r, ci["city"])
            city, state = split_location(ct)
            for tgt, lbl in cpairs:
                mm = re.match(r"^(.+?),\s*(.+)$", tgt)
                if mm and mm.group(2) in REGION_NAMES:
                    state = REGION_NAMES[mm.group(2)]
                    if not city:
                        city = mm.group(1)
                    break
        elif loc:
            city, state = split_location(loc)
            for tgt, lbl in tr_pairs[1:]:
                mm = re.match(r"^(.+?),\s*(.+)$", tgt)
                if mm and mm.group(2) in REGION_NAMES:
                    state = REGION_NAMES[mm.group(2)]
                    break
        elif len(lines) > 1:
            city, state = split_location(", ".join(lines[1:]))
        if ci["state"] is not None:
            st, _, _ = cell(r, ci["state"])
            st = st.strip()
            state = REGION_NAMES.get(st, st if re.fullmatch(r"[A-Z]{2}", st) else state)
        rd_txt = cell(r, ci["round"])[0] if ci["round"] is not None else ""
        rnd = parse_int(rd_txt) if re.fullmatch(r"\s*\d+\s*\D{0,3}", rd_txt or "") else None
        date_txt = cell(r, ci["date"])[0] if ci["date"] is not None else ""
        race_txt, _, race_pairs = cell(r, ci["race"])
        winner = winner_wiki = None
        if wc is not None:
            wt, _, wpairs = cell(r, wc)
            wname = person(wt) if wt.strip().lower() not in ("n/a", "na") else wt.strip()
            if wname and wname.lower() not in ("n/a", "na", "tba", "tbd", "—", "-", "–", "none", "not held"):
                winner = wname
                winner_wiki = reg(first_link(wpairs, wname))
            elif division and wname.lower() in ("n/a", "na", "—", "-", "–", "not held"):
                continue  # this division did not race here
        if ci["round"] is None:
            rnd = len(rows) + 1
        rows.append(OrderedDict(
            round=rnd, date=parse_date(date_txt, year), race=clean_name(race_txt) or None,
            track=clean_name(track_txt) or None, track_wiki=reg(track_wiki), city=city, state=state,
            winner=winner, winner_wiki=winner_wiki))
    return rows


def parse_results_rows(heads, data):
    rc = find_col(heads, lambda l, a: is_round(l, a) and l != "race")
    nm = find_col(heads, is_race)
    wc = find_col(heads, is_winner)
    out = []
    for r in data:
        rd = cell(r, rc)[0]
        race = clean_name(cell(r, nm)[0]) if nm is not None else None
        wt, _, wp = cell(r, wc)
        wname = person(wt)
        if not race and not wname:
            continue
        out.append(dict(round=parse_int(rd) if re.fullmatch(r"\s*\d+\s*\D{0,3}", rd or "") else None, race=race,
                        winner=wname if wname and wname.lower() not in ("n/a", "tba", "—", "-") else None,
                        winner_wiki=reg(first_link(wp, wname)) if wname else None))
    return out


def merge_results(sched, results):
    if not results:
        return sched
    byrnd = {r["round"]: r for r in results if r["round"] is not None}
    used = set()
    for i, s in enumerate(sched):
        if s["winner"]:
            continue
        m = None
        if s["round"] is not None and s["round"] in byrnd:
            m = byrnd[s["round"]]
        else:
            for j, r in enumerate(results):
                if j in used:
                    continue
                if s["race"] and r["race"] and norm(s["race"]) == norm(r["race"]):
                    m = r; used.add(j); break
            if m is None and len(results) == len(sched):
                m = results[i]
        if m:
            s["winner"], s["winner_wiki"] = m["winner"], m["winner_wiki"]
    return sched


def parse_standings(heads, data):
    pc = find_col(heads, is_pos)
    dc = find_col(heads, is_driver)
    ptc = None
    for i in range(len(heads) - 1, -1, -1):
        if is_points(hlast(heads[i]), hall(heads[i])) or (heads[i] and "points" in hall(heads[i]) and i > (dc or 0) and hlast(heads[i]) in ("points", "pts", "total")):
            ptc = i; break
    if ptc is None:
        ptc = find_col(heads, lambda l, a: "pts" in l or "points" in l, start=(dc or 0) + 1)
    stat_idx = {k: find_col(heads, f) for k, f in STAT_COLS.items()}
    end = ptc if ptc is not None and ptc > (dc or 0) else len(heads)
    result_cols = []
    for i in range((dc or 0) + 1, end):
        l = hlast(heads[i])
        if i in stat_idx.values() or l in NONRESULT_COLS or is_points(l, "") or is_number(l, ""):
            continue
        if re.search(r"behind|diff|gap|bonus|pen", l):
            continue
        result_cols.append(i)
    has_explicit = any(v is not None for v in stat_idx.values())
    if has_explicit:
        result_cols = []
    out = []
    for r in data:
        dtxt, _, dpairs = cell(r, dc)
        name = person(dtxt)
        if not name or name.lower() in ("driver", "pos", "pos.") or ":" in name or len(name) > 45 or re.search(r"reference|source|^key$|^notes?$", name, re.I):
            continue
        ptxt = cell(r, pc)[0]
        pos = parse_int(ptxt) if re.match(r"^\s*\d+", ptxt or "") else None
        pts = parse_int(cell(r, ptc)[0]) if ptc is not None else None
        rec = OrderedDict(pos=pos, name=name, wiki=reg(first_link(dpairs, name)), points=pts,
                          wins=None, starts=None, top5=None, top10=None)
        if has_explicit:
            for k, i in stat_idx.items():
                if i is not None:
                    rec[k] = parse_int(cell(r, i)[0])
        elif result_cols:
            fins = []
            seen_ids = set()
            for i in result_cols:
                if i >= len(r):
                    continue
                c = r[i]
                if c.get("spanned") and id(c) in seen_ids:
                    continue
                seen_ids.add(id(c))
                t = P.cell_text(c["raw"])[0].strip()
                m = re.match(r"^(\d{1,2})(?!\d)", t)
                if m:
                    fins.append(int(m.group(1)))
            rec["starts"] = len(fins)
            rec["wins"] = sum(1 for f in fins if f == 1)
            rec["top5"] = sum(1 for f in fins if f <= 5)
            rec["top10"] = sum(1 for f in fins if f <= 10)
        out.append(rec)
    # a points table must have at least a few rows with numeric positions
    if sum(1 for o in out if o["pos"] is not None) < 2:
        return []
    return out


def parse_teams(heads, data, full_time):
    tc = find_col(heads, is_team)
    mc = find_col(heads, is_make)
    nc = find_col(heads, is_number)
    dc = find_col(heads, is_driver)
    rc = find_col(heads, is_rounds)
    teams = OrderedDict()
    for r in data:
        r = [dict(c, raw=re.sub(r"<small>.*?</small>", "", c["raw"], flags=re.S | re.I)) for c in r]
        team = clean_name(cell(r, tc)[0]) if tc is not None else None
        make = clean_name(cell(r, mc)[0]) if mc is not None else None
        num = cell(r, nc)[0].split("\n")[0].strip() if nc is not None else None
        dtxt, _, dpairs = cell(r, dc)
        if not dtxt:
            continue
        drivers = []
        for ln in dtxt.split("\n"):
            nm = clean_name(re.sub(r"\(.*?\)", "", ln))
            if not nm or nm.lower() in ("tba", "tbd", "various", "multiple"):
                continue
            wk = None
            for tgt, txt in dpairs:
                if norm(txt) and norm(txt) == norm(nm):
                    wk = tgt; break
            drivers.append(OrderedDict(name=nm, wiki=reg(wk)))
        if not drivers:
            continue
        ft = full_time
        if ft is None and rc is not None:
            rt = cell(r, rc)[0].lower()
            if rt.strip() in ("all", "full", "full-time", "full time"):
                ft = True
            elif rt.strip():
                ft = False
        key = (team or "", make or "")
        t = teams.setdefault(key, OrderedDict(team=team, manufacturer=make, cars=[]))
        car = next((c for c in t["cars"] if c["number"] == num), None)
        if car is None:
            car = OrderedDict(number=num, full_time=ft, drivers=[])
            t["cars"].append(car)
        for d in drivers:
            if all(norm(x["name"]) != norm(d["name"]) for x in car["drivers"]):
                car["drivers"].append(d)
    return list(teams.values())


def parse_season_page(pg, year, division=None):
    text = P.clean_source(pg["text"])
    hs = P.headings(text)
    sched_tables, results_tables, stand_tables, team_tables, race_tables = [], [], [], [], []
    for off, tt in P.find_tables(text):
        try:
            heads, data, cap = table_struct(tt)
        except Exception as e:  # pragma: no cover
            log("   table parse error", e); continue
        if not heads:
            continue
        kind = classify(heads)
        hp = P.heading_before(hs, off)
        hpl = " / ".join(hp).lower()
        if kind == "standings":
            if re.search(r"owner|manufacturer|rookie|team|car owner|crew", hpl.split(" / ")[-1] if hp else ""):
                continue
            stand_tables.append((hpl, heads, data))
        elif kind == "schedule":
            if re.search(r"track|venue", hpl) and not re.search(r"schedule|calendar|result", hpl):
                continue
            sched_tables.append((hpl, heads, data))
        elif kind == "results":
            results_tables.append((hpl, heads, data))
        elif kind == "teams":
            team_tables.append((hpl, heads, data))
        elif kind == "raceresult":
            fc, dc = find_col(heads, is_finish), find_col(heads, is_driver)
            for r in data:
                if parse_int(cell(r, fc)[0]) == 1 and re.fullmatch(r"\s*1\s*", cell(r, fc)[0]):
                    wt, _, wp = cell(r, dc)
                    race_tables.append(dict(race=hp[-1] if hp else None, winner=person(wt),
                                            winner_wiki=reg(first_link(wp, person(wt))), round=None))
                    break
    # schedule
    schedule = []
    for hpl, heads, data in sched_tables:
        rows = parse_schedule_rows(heads, data, year, division)
        if rows:
            schedule = rows; break
    if schedule and not all(s["winner"] for s in schedule):
        for hpl, heads, data in results_tables:
            res = parse_results_rows(heads, data)
            if division:
                continue
            if res:
                schedule = merge_results(schedule, res); break
    if schedule and not all(s["winner"] for s in schedule) and race_tables and not division:
        schedule = merge_results(schedule, race_tables)
    # standings
    standings = []
    cands = stand_tables
    if division:
        cands = [t for t in stand_tables if re.search(division["standings"], t[0], re.I)]
    pref = [t for t in cands if "driver" in t[0]] or cands
    for hpl, heads, data in pref:
        standings = parse_standings(heads, data)
        if standings:
            break
    # teams
    teams = []
    if not division:
        for hpl, heads, data in team_tables:
            ft = None
            if re.search(r"complete|full[- ]time|full schedule", hpl):
                ft = True
            elif re.search(r"limited|part[- ]time|partial", hpl):
                ft = False
            for t in parse_teams(heads, data, ft):
                ex = next((x for x in teams if x["team"] == t["team"] and x["manufacturer"] == t["manufacturer"]), None)
                if ex:
                    ex["cars"].extend(t["cars"])
                else:
                    teams.append(t)
    return schedule, standings, teams


# ---------------------------------------------------------------- champion lists / event winners

def table_by_heading(page_title, heading_sub, year_hint=None):
    pg = W.page(page_title)
    if not pg:
        return []
    text = P.clean_source(pg["text"])
    hs = P.headings(text)
    out = []
    for off, tt in P.find_tables(text):
        hp = P.heading_before(hs, off)
        if hp and heading_sub.lower() in " / ".join(hp).lower():
            out.append((hp, tt, pg))
    return out


def year_table_values(page_title, heading_sub, col_pat):
    """{year: (name, wiki)} from a table whose first column is a year."""
    res = {}
    for hp, tt, pg in table_by_heading(page_title, heading_sub):
        heads, data, _ = table_struct(tt)
        ci = None
        for i, h in enumerate(heads):
            if i > 0 and re.search(col_pat, hall(h).replace("\n", " "), re.I):
                ci = i; break
        if ci is None:
            continue
        for r in data:
            yt = cell(r, 0)[0]
            m = re.match(r"^\s*((?:19|20)\d\d)", yt)
            if not m:
                continue
            t, _, pairs = cell(r, ci)
            nm = person(t)
            if not nm or nm.lower() in ("none", "n/a", "—", "-", "tba", "tbd", "none named"):
                continue
            res.setdefault(int(m.group(1)), (nm, reg(first_link(pairs, nm)), r, heads))
        if res:
            break
    return res, (pg if res else None)


def year_list_values(page_title, heading_sub):
    pg = W.page(page_title)
    res = {}
    if not pg:
        return res, None
    text = P.clean_source(pg["text"])
    for hp, y, txt, pairs in P.year_lists(text):
        if hp and heading_sub.lower() in hp[-1].lower():
            nm = list_name(txt, pairs)
            if not nm or nm.lower().startswith("none"):
                continue
            res.setdefault(y, (nm, reg(first_link(pairs, nm)), None, None))
    return res, pg


def champions_for(cfg):
    champs, srcs = {}, []
    for kind, page, heading, col, y0, y1 in cfg.get("champ", []):
        if kind == "table":
            vals, pg = year_table_values(page, heading, col)
        else:
            vals, pg = year_list_values(page, heading)
        used = False
        for y, v in vals.items():
            if y0 <= y <= y1 and YEARS[0] <= y <= YEARS[1] and y not in champs:
                champs[y] = v; used = True
        if used and pg:
            srcs.append(W.oldid_url(pg["title"], pg["revid"]))
    return champs, srcs


# ---------------------------------------------------------------- discovery of season articles

def discover_titles():
    cands = set()
    disc = os.path.join(OUT, "discovery_search.json")
    if not os.path.exists(disc):
        qs = ['"Whelen Modified Tour"', '"Southern Modified Tour"', '"Busch North"', '"Busch East"', '"K&N Pro Series East"',
              '"Camping World East"', '"Pinty\'s Series"', '"Canadian Tire Series"', '"NASCAR Canada"', 'CASCAR', '"CARS Tour"',
              '"Pro Cup"', '"American Speed Association"', '"ASA"', 'ARTGO', '"Midwest Tour"', '"Pro All Stars"',
              '"Southern Super Series"', '"Champion Racing Association"', '"Modified Tour"', '"ARCA"']
        found = {}
        for q in qs:
            titles, off = [], 0
            while True:
                d = W.wp({"action": "query", "list": "search", "srsearch": "intitle:" + q, "srnamespace": "0",
                          "srlimit": "500", "sroffset": str(off), "srwhat": "text"})
                titles += [x["title"] for x in d["query"]["search"]]
                if "continue" in d:
                    off = d["continue"]["sroffset"]
                else:
                    break
            found[q] = titles
        json.dump(found, open(disc, "w"), indent=1)
    for v in json.load(open(disc)).values():
        cands.update(v)
    for cat in ["Category:ARCA Menards Series seasons", "Category:ARCA Racing Series seasons",
                "Category:ARCA Menards Series East", "Category:ARCA Menards Series West", "Category:ASA Midwest Tour seasons"]:
        try:
            cands.update(W.category_members(cat, ns=0))
        except Exception as e:
            log("category fail", cat, e)
    # pattern candidates for years not caught by search
    pats = ["{y} NASCAR Busch North Series", "{y} NASCAR Busch Grand National North Series", "{y} NASCAR Busch East Series",
            "{y} NASCAR Camping World East Series", "{y} NASCAR K&N Pro Series East", "{y} NASCAR K&N Pro Series West",
            "{y} ARCA Bondo/Mar-Hyde Series", "{y} ARCA Re/Max Series", "{y} ARCA Racing Series", "{y} ARCA Menards Series",
            "{y} NASCAR Featherlite Modified Tour", "{y} NASCAR Whelen Modified Tour", "{y} NASCAR Winston West Series",
            "{y} NASCAR West Series", "{y} NASCAR Canadian Tire Series", "{y} NASCAR Pinty's Series", "{y} NASCAR Canada Series",
            "{y} ASA Midwest Tour season", "{y} ARCA Midwest Tour season", "{y} CARS Tour", "{y} SMART Modified Tour",
            "{y} NASCAR Whelen Southern Modified Tour", "{y} ASA STARS National Tour", "{y} ARCA Menards Series East",
            "{y} ARCA Menards Series West"]
    pc = [p.format(y=y) for p in pats for y in range(YEARS[0], YEARS[1] + 1)]
    res = W.resolve(pc)
    for k, v in res.items():
        if v and not v["disambig"]:
            cands.add(v["title"])
    return cands


# ---------------------------------------------------------------- main build

def build_series():
    titles = discover_titles()
    seasons = {}  # (key, year) -> dict
    series_meta = {}
    for key, cfg in SERIES.items():
        log("==", key)
        champs, champ_srcs = champions_for(cfg)
        main_pg = W.page(cfg["main"])
        found = {}
        if cfg.get("season_re"):
            for t in titles:
                m = re.match(cfg["season_re"], t)
                if m and YEARS[0] <= int(m.group(1)) <= YEARS[1]:
                    found.setdefault(int(m.group(1)), t)
        pages = W.pages(list(found.values())) if found else {}
        years = set(found) | set(champs)
        mains = {}
        for page, hfmt, y in cfg.get("main_schedules", []):
            mains[y] = (page, hfmt.format(y=y))
            years.add(y)
        ms = cfg.get("main_seasons")
        if ms:
            for y in range(ms[2], ms[3] + 1):
                years.add(y)
        for y in sorted(years):
            sched, stand, teams, srcs, official = [], [], [], [], None
            t = found.get(y)
            if t and pages.get(t):
                pg = pages[t]
                sched, stand, teams = parse_season_page(pg, y, cfg.get("division"))
                srcs.append(W.oldid_url(pg["title"], pg["revid"]))
                official = re.sub(r"^\d{4}\s+", "", pg["title"]).replace(" season", "")
            if not sched and y in mains:
                page, heading = mains[y]
                for hp, tt, mpg in table_by_heading(page, heading):
                    heads, data, _ = table_struct(tt)
                    sched = parse_schedule_rows(heads, data, y) or []
                    if sched:
                        srcs.append(W.oldid_url(mpg["title"], mpg["revid"]))
                        break
            if ms and ms[2] <= y <= ms[3] and not sched:
                for hp, tt, mpg in table_by_heading(ms[0], ms[1].format(y=y)):
                    if hp[-1].lower() != ms[1].format(y=y).lower():
                        continue
                    heads, data, _ = table_struct(tt)
                    k = classify(heads)
                    if k == "schedule":
                        sched = parse_schedule_rows(heads, data, y) or []
                        if sched:
                            srcs.append(W.oldid_url(mpg["title"], mpg["revid"]))
                for hp, tt, mpg in table_by_heading(ms[0], "points standings"):
                    if str(y) in hp[-1] and len(hp) >= 2 and hp[-2].lower() == ms[1].format(y=y).lower():
                        heads, data, _ = table_struct(tt)
                        stand = parse_standings(heads, data)
            champ = None
            if y in champs:
                nm, wk, _, _ = champs[y]
                champ = OrderedDict(name=nm, wiki=wk)
                for s in champ_srcs:
                    if s not in srcs:
                        srcs.append(s)
            elif stand and y < CURRENT_YEAR and stand[0]["pos"] == 1:
                champ = OrderedDict(name=stand[0]["name"], wiki=stand[0]["wiki"])
            if not (sched or stand or teams or champ):
                continue
            level = "full" if (sched and stand) else ("schedule" if sched else ("champion_only" if not stand else "full"))
            if stand and not sched:
                level = "schedule" if False else "full"
            seasons[(key, y)] = OrderedDict(
                series=key, year=y, official_name=official, data_level=level, champion=champ,
                teams=teams, standings=stand, schedule=sched, sources=srcs)
        names_by_year = []
        for y in sorted(y for (k, y) in seasons if k == key):
            nm = seasons[(key, y)]["official_name"] or None
            if not nm:
                continue
            if names_by_year and names_by_year[-1]["name"] == nm and names_by_year[-1]["to"] == y - 1:
                names_by_year[-1]["to"] = y
            else:
                names_by_year.append(OrderedDict([("from", y), ("to", y), ("name", nm)]))
        ys = sorted(y for (k, y) in seasons if k == key)
        srcs = []
        if main_pg:
            srcs.append(W.oldid_url(main_pg["title"], main_pg["revid"]))
        for s in champ_srcs:
            if s not in srcs:
                srcs.append(s)
        series_meta[key] = OrderedDict(
            name=cfg["name"], names_by_year=names_by_year, discipline=cfg["discipline"],
            years=[ys[0], ys[-1]] if ys else None, footprint=[], level=cfg["level"], sources=srcs)
    return seasons, series_meta


def build_events(seasons, series_meta):
    for key, cfg in EVENTS.items():
        log("== event", key)
        kind, page, heading, wcol, dcol, lcol = cfg["src"]
        rows = {}
        pg = None
        if kind == "table":
            for hp, tt, p in table_by_heading(page, heading):
                heads, data, _ = table_struct(tt)
                wi = find_col(heads, lambda l, a: re.search(wcol, l) is not None, start=1)
                di = find_col(heads, lambda l, a: re.search(dcol, l) is not None) if dcol else None
                li = find_col(heads, lambda l, a: re.search(lcol, l) is not None) if lcol else None
                if wi is None:
                    continue
                for r in data:
                    m = re.match(r"^\s*((?:19|20)\d\d)", cell(r, 0)[0])
                    if not m:
                        continue
                    y = int(m.group(1))
                    wt, _, wp = cell(r, wi)
                    nm = person(wt)
                    if not nm or re.search(r"not held|cancel|none", nm, re.I):
                        continue
                    loc = cell(r, li) if li is not None else None
                    rows.setdefault(y, dict(winner=nm, wiki=reg(first_link(wp, nm)),
                                            date=parse_date(cell(r, di)[0], y) if di is not None else None,
                                            track=clean_name(loc[0]) if loc else None,
                                            track_wiki=reg(first_link(loc[2], loc[0]) if loc[2] else clean_name(loc[0])) if loc and loc[0] else None))
                if rows:
                    pg = p; break
        else:
            pg = W.page(page)
            text = P.clean_source(pg["text"])
            for hp, y, txt, pairs in P.year_lists(text):
                if hp and heading.lower() in hp[-1].lower():
                    nm = list_name(txt, pairs)
                    if nm and not re.search(r"not held|cancel|none", txt, re.I):
                        rows.setdefault(y, dict(winner=nm, wiki=reg(first_link(pairs, nm)), date=None, track=None, track_wiki=None))
        trk_res = W.resolve([cfg["track"]]) if cfg.get("track") else {}
        ys = []
        for y in sorted(rows):
            if not (YEARS[0] <= y <= YEARS[1]):
                continue
            r = rows[y]
            track = r["track"] or cfg["track"]
            twk = r["track_wiki"] or (reg(cfg["track"]) if cfg.get("track") else None)
            sched = [OrderedDict(round=1, date=r["date"], race=cfg["name"], track=track, track_wiki=twk,
                                 city=None, state=None, winner=r["winner"], winner_wiki=r["wiki"])]
            seasons[(key, y)] = OrderedDict(
                series=key, year=y, official_name=cfg["name"], data_level="schedule",
                champion=OrderedDict(name=r["winner"], wiki=r["wiki"]), teams=[], standings=[], schedule=sched,
                sources=[W.oldid_url(pg["title"], pg["revid"])])
            ys.append(y)
        series_meta[key] = OrderedDict(
            name=cfg["name"], names_by_year=[], discipline=cfg["discipline"], years=[ys[0], ys[-1]] if ys else None,
            footprint=[], level="national", type="crown_jewel_event",
            sources=[W.oldid_url(pg["title"], pg["revid"])] if pg else [])


# ---------------------------------------------------------------- link resolution

def resolve_links():
    log("resolving", len(LINKS), "links")
    return W.resolve(sorted(LINKS))


def fix_wiki(res, t):
    if not t:
        return None
    v = res.get(t)
    if not v or v.get("disambig"):
        return None
    return v["title"]


# ---------------------------------------------------------------- venues
TRACK_CITY_FIX = {}


def infobox(text, names=("racetrack", "infobox speedway", "motorsport venue", "infobox racetrack", "venue", "stadium", "sports venue")):
    m = re.search(r"\{\{\s*(?:Infobox[ _]([^|\n]*)|Motorsport[ _]venue|Racetrack|Infobox)\s*[|\n]", text, re.I)
    if not m:
        return {}
    start = m.start()
    depth, i = 0, start
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1; i += 2; continue
        if text.startswith("}}", i):
            depth -= 1; i += 2
            if depth == 0:
                break
            continue
        i += 1
    body = text[start + 2:i - 2]
    parts = P.split_top(body, "|")
    d = {"_type": parts[0].strip()}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k.strip().lower()] = v.strip()
    return d


def venue_location(raw):
    """(city, state) from an infobox location value: prefer a linked 'City, State' target."""
    if not raw:
        return None, None
    txt, _, pairs = P.cell_text(raw)
    for tgt, label in pairs:
        m = re.match(r"^(.+?),\s*(.+)$", tgt)
        if m and m.group(2) in REGION_NAMES:
            return m.group(1), REGION_NAMES[m.group(2)]
    segs = [x.strip() for x in re.split(r"\n", txt) if x.strip()]
    for sgm in segs:
        sgm = re.sub(r",?\s*(United States|USA|U\.S\.|Canada)\.?\s*$", "", sgm)
        c, st = split_location(sgm)
        if st:
            if c and re.match(r"^\d", c):
                c = c.split(",")[-1].strip() if "," in c else None
            return c, st
    return None, None


def num(s):
    if not s:
        return None
    t = P.cell_text(s)[0]
    m = re.search(r"(\d*\.\d+|\d+)", t.replace(",", ""))
    return float(m.group(1)) if m else None


def year_of(s):
    if not s:
        return None
    t = P.cell_text(s)[0]
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", t)
    return int(m.group(1)) if m else None


def wd_claim(ent, pid):
    out = []
    for c in ent.get("claims", {}).get(pid, []):
        dv = c.get("mainsnak", {}).get("datavalue")
        if dv:
            out.append(dv["value"])
    return out


PLACE_TYPES = {"Q515", "Q1093829", "Q15127012", "Q3957", "Q532", "Q5119", "Q1549591", "Q486972", "Q17343829",
               "Q498162", "Q15284", "Q3184121", "Q1907114", "Q2039348", "Q852446", "Q1115575", "Q17201685",
               "Q3327873", "Q13218391", "Q13212489", "Q47168", "Q1289426", "Q22865", "Q14762300", "Q2989398",
               "Q1500350", "Q1520223", "Q3518810", "Q107390", "Q35657", "Q11828004", "Q13221722", "Q752392",
               "Q1059478", "Q4835091", "Q3266850", "Q1637706", "Q15063611"}
GENERIC = {"speedway", "raceway", "motor", "motorsports", "motorsport", "international", "park", "circuit", "the",
           "race", "track", "of", "at", "superspeedway", "speedbowl", "motorplex", "and", "complex", "stadium", "street"}
ROAD_RE = re.compile(r"road course|roval|\binfield\b|\(rc\)", re.I)


def is_place_title(t):
    if not t:
        return False
    m = re.match(r"^.+,\s*(.+)$", t)
    return bool(m and m.group(1) in REGION_NAMES)


def core(n):
    return " ".join(w for w in norm(re.sub(r"\(.*?\)", " ", n or "")).split() if w not in GENERIC)


def build_venues(seasons, res):
    existing = json.load(open(os.path.join(os.path.dirname(OUT), "existing_tracks.json")))
    ex_index, ex_core = defaultdict(list), defaultdict(list)
    for t in existing:
        for n in [t["name"]] + t.get("aliases", []):
            ex_index[norm(n)].append(t)
            if core(n):
                ex_core[core(n)].append(t)
    # canonical wiki titles of all linked tracks + their wikidata entities (to drop links to towns)
    canon = sorted({fix_wiki(res, r.get("track_wiki")) for s in seasons.values() for r in s["schedule"]} - {None})
    qids = {t: (res.get(t) or {}).get("qid") for t in canon}
    missing = [t for t in canon if not qids.get(t)]
    if missing:
        r2 = W.resolve(missing)
        for t in missing:
            qids[t] = (r2.get(t) or {}).get("qid")
    ents = W.wd_entities([q for q in qids.values() if q])
    place = set()
    for t in canon:
        e = ents.get(qids.get(t)) if qids.get(t) else None
        p31 = {v["id"] for v in wd_claim(e, "P31")} if e else set()
        if is_place_title(t) or (p31 & PLACE_TYPES):
            place.add(t)
    venues = OrderedDict()
    for (k, y), s in seasons.items():
        for r in s["schedule"]:
            if not r.get("track"):
                continue
            wk = fix_wiki(res, r.get("track_wiki"))
            if wk in place:
                wk = None
            road = bool(ROAD_RE.search(r["track"] or ""))
            key = ("w", wk, road) if wk else ("n", norm(re.sub(r"\(.*?\)", "", r["track"])), r.get("state"))
            v = venues.setdefault(key, dict(names=[], wiki=wk, road=road, states=set(), cities=set(), raw_links=set(), series=set()))
            if r["track"] not in v["names"]:
                v["names"].append(r["track"])
            if r.get("state"):
                v["states"].add(r["state"])
            if r.get("city"):
                v["cities"].add(r["city"])
            if r.get("track_wiki") and fix_wiki(res, r["track_wiki"]) not in place:
                v["raw_links"].add(r["track_wiki"])
            v["series"].add(s["series"])
    # merge state-less name-only venues into a same-named venue that has a state
    for key, v in list(venues.items()):
        if key[0] == "n" and key[2] is None:
            other = [k2 for k2 in venues if k2[0] == "n" and k2[1] == key[1] and k2[2] is not None]
            if len(other) == 1:
                tgt = venues[other[0]]
                tgt["names"] += [n for n in v["names"] if n not in tgt["names"]]
                tgt["cities"] |= v["cities"]; tgt["series"] |= v["series"]
                del venues[key]
    # merge name-only venues into linked venues with the same normalized name
    wiki_by_name = {}
    for key, v in venues.items():
        if key[0] == "w":
            for n in v["names"] + [v["wiki"]] + list(v["raw_links"]):
                wiki_by_name.setdefault((norm(n), v["road"]), key)
    for key, v in list(venues.items()):
        if key[0] == "n":
            road = bool(ROAD_RE.search(v["names"][0]))
            tk = wiki_by_name.get((norm(v["names"][0]), road)) or wiki_by_name.get((key[1], road))
            if tk:
                tgt = venues[tk]
                for n in v["names"]:
                    if n not in tgt["names"]:
                        tgt["names"].append(n)
                tgt["states"] |= v["states"]; tgt["cities"] |= v["cities"]; tgt["series"] |= v["series"]
                del venues[key]
    wtitles = [v["wiki"] for v in venues.values() if v["wiki"]]
    vpages = W.pages(wtitles)
    out_ex, out_new = [], []
    for key, v in venues.items():
        pg = vpages.get(v["wiki"]) if v["wiki"] else None
        ib = infobox(pg["text"]) if pg else {}
        fn = ib.get("former_names") or ib.get("former names") or ""
        former = [clean_name(re.sub(r"\(.*?\)", "", x)) for x in re.split(r"\n|;|,\s+(?=[A-Z])", re.sub(r"\(.*?\)", "", P.cell_text(fn)[0])) if x.strip()] if fn else []
        former = [a for a in former if a]
        probe = list(v["names"]) if v["road"] else ([v["wiki"]] if v["wiki"] else []) + list(v["raw_links"]) + v["names"]
        if not v["road"]:
            probe += former
        cands = []
        for n in probe:
            if not n:
                continue
            for cand in ex_index.get(norm(n), []) + ex_index.get(norm(re.sub(r"\(.*?\)", " ", n)), []):
                if cand not in cands:
                    cands.append(cand)
        if not cands and v["states"]:
            for n in probe:
                for cand in ex_core.get(core(n), []):
                    if cand.get("region") in v["states"] and cand not in cands:
                        cands.append(cand)
        if v["road"]:
            cands = [c for c in cands if ROAD_RE.search(c["name"]) or any(ROAD_RE.search(a) for a in c.get("aliases", []))] or []
        if len(cands) > 1 and v["states"]:
            c2 = [c for c in cands if c.get("region") in v["states"]]
            cands = c2 or cands
        if cands:
            out_ex.append(OrderedDict(existing_id=cands[0]["id"], names_seen=sorted(set(v["names"]))))
            continue
        ent = ents.get(qids.get(v["wiki"])) if v["wiki"] and qids.get(v["wiki"]) else None
        if v["wiki"] and not ent:
            q = (W.resolve([v["wiki"]]).get(v["wiki"]) or {}).get("qid")
            ent = W.wd_entities([q]).get(q) if q else None
        lat = lon = None
        if ent:
            co = wd_claim(ent, "P625")
            if co:
                lat, lon = round(co[0]["latitude"], 6), round(co[0]["longitude"], 6)
        if lat is None and ib.get("coordinates"):
            mm = re.search(r"\{\{\s*coord\s*\|([^}]*)\}\}", ib["coordinates"], re.I)
            if mm:
                lat, lon = parse_coord(mm.group(1))
        state = sorted(v["states"])[0] if v["states"] else None
        city = sorted(v["cities"])[0] if v["cities"] else None
        if ib.get("location") and (not state or not city):
            c2, s2 = venue_location(ib["location"])
            state = state or s2
            city = city or c2
        country = ABBR_TO_COUNTRY.get(state) if state else None
        if ent and not country:
            c = wd_claim(ent, "P17")
            if c:
                country = {"Q30": "USA", "Q16": "CAN", "Q96": "MEX"}.get(c[0]["id"])
        stxt = (P.cell_text(ib.get("surface", "") or ib.get("layout1_surface", "") or "")[0] or "").lower()
        surface = None
        if stxt:
            if "asphalt" in stxt or "paved" in stxt or "tarmac" in stxt or "pavement" in stxt:
                surface = "asphalt"
            elif "concrete" in stxt:
                surface = "concrete"
            elif "dirt" in stxt or "clay" in stxt:
                surface = "dirt"
        lraw = ib.get("length_mi") or ib.get("length mi")
        length = num(lraw)
        if length is None and ib.get("length"):
            lt = P.cell_text(ib["length"])[0]
            length = num(ib["length"])
            if length and "km" in lt and "mi" not in lt:
                length = round(length / 1.609344, 3)
        if length is not None and length > 5:  # obviously not miles
            length = None
        bank = P.cell_text(ib.get("banking", ""))[0] or None
        opened = year_of(ib.get("opened") or ib.get("broke_ground"))
        closed = year_of(ib.get("closed"))
        if ent and not opened:
            oc = wd_claim(ent, "P1619")
            if oc and oc[0].get("time"):
                opened = int(oc[0]["time"][1:5])
        if ent and not closed:
            cc = wd_claim(ent, "P3999")
            if cc and cc[0].get("time"):
                closed = int(cc[0]["time"][1:5])
        typ = (P.cell_text((ib.get("layout", "") or "") + " " + (ib.get("type", "") or "") + " " + (ib.get("layout1", "") or ""))[0] or "").lower()
        allnames = " ".join(v["names"]).lower()
        tt = None
        if "street" in allnames or "street" in typ:
            tt = "street_circuit"
        elif v["road"] or "road course" in typ or "road" in typ:
            tt = "road_course"
        elif "figure" in typ:
            tt = "figure_eight"
        elif "oval" in typ or "oval" in stxt or ib.get("banking"):
            tt = "oval"
        aliases = list(former)
        for n in v["names"]:
            if n not in aliases and (not v["wiki"] or norm(n) != norm(v["wiki"])):
                aliases.append(n)
        name = v["wiki"] or v["names"][0]
        name = re.sub(r"\s*\((?:race ?track|racetrack|speedway|racing|motorsport|[A-Z][a-z]+(?: [A-Z][a-z]+)?)\)$", "", name)
        if v["road"] and not ROAD_RE.search(name):
            name = name + " Road Course"
        aliases = [a for a in aliases if a != name]
        disc = set()
        for sk in v["series"]:
            d = (SERIES.get(sk) or EVENTS.get(sk) or {}).get("discipline")
            disc.add({"asphalt_late_model": "late_model"}.get(d, d))
        srcs = []
        if pg:
            srcs.append(W.oldid_url(pg["title"], pg["revid"]))
        if ent:
            srcs.append("https://www.wikidata.org/wiki/" + ent["id"])
        if not srcs:
            srcs = sorted({src for s in seasons.values() for r in s["schedule"] if r.get("track") in v["names"] for src in s["sources"][:1]})[:3]
        active = False if closed else None
        status = (P.cell_text(ib.get("status", "") or "")[0] or "").lower()
        if re.search(r"closed|defunct|demolished|abandoned", status):
            active = False
        elif re.search(r"\b(open|active|operational)\b", status):
            active = True
        out_new.append(OrderedDict(
            name=name, city=city, region=state, country=country, track_type=tt, surface=surface,
            length_mi=length, banking_deg_turns=bank, opened=opened, closed=closed, active=active,
            disciplines=sorted(x for x in disc if x), level=None, lat=lat, lon=lon, sources=srcs,
            aliases=aliases))
    # dedupe existing records by id
    merged = OrderedDict()
    for r in out_ex:
        m = merged.setdefault(r["existing_id"], OrderedDict(existing_id=r["existing_id"], names_seen=[]))
        m["names_seen"] = sorted(set(m["names_seen"]) | set(r["names_seen"]))
    return {"existing": list(merged.values()), "new": out_new}, venues


def parse_coord(s):
    parts = [p.strip() for p in s.split("|")]
    nums, dirs = [], []
    for p in parts:
        if re.fullmatch(r"-?\d+(\.\d+)?", p):
            nums.append(float(p))
        elif p in ("N", "S", "E", "W"):
            dirs.append((len(nums), p))
        elif "=" in p:
            break
    if not dirs and len(nums) >= 2:
        return round(nums[0], 6), round(nums[1], 6)
    if len(dirs) == 2:
        i1 = dirs[0][0]
        lat_parts, lon_parts = nums[:i1], nums[i1:dirs[1][0]]
        def dms(x):
            return x[0] + (x[1] / 60 if len(x) > 1 else 0) + (x[2] / 3600 if len(x) > 2 else 0)
        try:
            lat, lon = dms(lat_parts), dms(lon_parts)
        except IndexError:
            return None, None
        if dirs[0][1] == "S":
            lat = -lat
        if dirs[1][1] == "W":
            lon = -lon
        return round(lat, 6), round(lon, 6)
    return None, None


# ---------------------------------------------------------------- drivers (Wikidata)
ISO3 = {"Q30": "USA", "Q16": "CAN", "Q96": "MEX", "Q145": "GBR", "Q408": "AUS", "Q664": "NZL", "Q142": "FRA",
        "Q183": "DEU", "Q38": "ITA", "Q29": "ESP", "Q155": "BRA", "Q414": "ARG", "Q39": "CHE", "Q55": "NLD",
        "Q31": "BEL", "Q33": "FIN", "Q34": "SWE", "Q20": "NOR", "Q35": "DNK", "Q17": "JPN", "Q148": "CHN",
        "Q298": "CHL", "Q739": "COL", "Q717": "VEN", "Q258": "ZAF", "Q27": "IRL", "Q40": "AUT", "Q36": "POL",
        "Q213": "CZE", "Q45": "PRT", "Q159": "RUS", "Q212": "UKR", "Q43": "TUR", "Q801": "ISR", "Q419": "PER",
        "Q77": "URY", "Q750": "BOL", "Q736": "ECU", "Q733": "PRY", "Q800": "CRI", "Q804": "PAN", "Q241": "CUB",
        "Q786": "DOM", "Q1183": "PRI", "Q766": "JAM", "Q28": "HUN", "Q218": "ROU", "Q224": "HRV", "Q215": "SVN",
        "Q41": "GRC", "Q884": "KOR", "Q865": "TWN", "Q334": "SGP", "Q833": "MYS", "Q252": "IDN", "Q928": "PHL",
        "Q668": "IND", "Q869": "THA", "Q881": "VNM", "Q21": "GBR", "Q22": "GBR", "Q25": "GBR", "Q26": "GBR"}


def build_drivers(seasons, res):
    titles = set()
    for s in seasons.values():
        if s["champion"] and s["champion"]["wiki"]:
            titles.add(s["champion"]["wiki"])
        for r in s["standings"]:
            if r["wiki"]:
                titles.add(r["wiki"])
        for r in s["schedule"]:
            if r["winner_wiki"]:
                titles.add(r["winner_wiki"])
        for t in s["teams"]:
            for c in t["cars"]:
                for d in c["drivers"]:
                    if d["wiki"]:
                        titles.add(d["wiki"])
    titles = sorted(titles)
    log("drivers:", len(titles))
    qmap = {t: (res.get(t) or {}).get("qid") for t in titles}
    missing = [t for t in titles if not qmap[t]]
    if missing:
        r2 = W.resolve(missing)
        for t in missing:
            qmap[t] = (r2.get(t) or {}).get("qid")
    ents = W.wd_entities([q for q in qmap.values() if q], props="claims|labels")
    # birthplaces
    bp = {}
    for t, q in qmap.items():
        e = ents.get(q) if q else None
        if e:
            v = wd_claim(e, "P19")
            if v:
                bp[t] = v[0]["id"]
    places = W.wd_entities(sorted(set(bp.values())), props="claims|labels")
    # walk P131 up to 4 levels for state/province
    chain_ents = dict(places)
    frontier = set()
    for p in places.values():
        for v in wd_claim(p, "P131"):
            frontier.add(v["id"])
    for _ in range(4):
        frontier -= set(chain_ents)
        if not frontier:
            break
        new = W.wd_entities(sorted(frontier), props="claims|labels")
        chain_ents.update(new)
        frontier = set()
        for p in new.values():
            for v in wd_claim(p, "P131"):
                frontier.add(v["id"])
    countries = set()
    for p in chain_ents.values():
        for v in wd_claim(p, "P17"):
            countries.add(v["id"])
    for e in ents.values():
        for v in wd_claim(e, "P27"):
            countries.add(v["id"])
    cents = W.wd_entities(sorted(countries - set(ISO3)), props="claims|labels")

    def label(e):
        return (e.get("labels", {}).get("en") or {}).get("value") if e else None

    def iso3(qid):
        if qid in ISO3:
            return ISO3[qid]
        e = cents.get(qid)
        v = wd_claim(e, "P298") if e else []
        return v[0] if v else None

    def region_of(pq):
        seen, cur = set(), [pq]
        for _ in range(6):
            nxt = []
            for q in cur:
                if q in seen:
                    continue
                seen.add(q)
                e = chain_ents.get(q)
                lb = label(e)
                if lb in REGION_NAMES and q != pq or (lb in REGION_NAMES and q == pq and False):
                    return REGION_NAMES[lb]
                if lb in REGION_NAMES:
                    return REGION_NAMES[lb]
                if e:
                    nxt += [v["id"] for v in wd_claim(e, "P131")]
            cur = nxt
        return None

    # Wikipedia infobox fallback for drivers whose Wikidata item lacks birthplace/birth date
    need = []
    for t in titles:
        e = ents.get(qmap.get(t)) if qmap.get(t) else None
        if t not in bp or not (e and wd_claim(e, "P569")):
            need.append(t)
    log("infobox fallback for", len(need), "drivers")
    wp_bio = {}
    bpages = W.pages(need)
    for t in need:
        pg = bpages.get(t)
        if not pg:
            continue
        ib = infobox(pg["text"])
        raw = ib.get("birth_place") or ib.get("birthplace") or ""
        txt = P.cell_text(raw)[0].replace("\n", ", ") if raw else ""
        ctry = None
        if re.search(r"(United States|U\.S\.|USA|\bUS\b)\s*$", txt):
            ctry = "USA"
        elif re.search(r"Canada\s*$", txt):
            ctry = "CAN"
        elif re.search(r"Mexico\s*$", txt):
            ctry = "MEX"
        txt2 = re.sub(r",?\s*(United States|U\.S\.|USA|US|Canada|Mexico)\.?\s*$", "", txt).strip(" ,")
        c, st = split_location(txt2)
        bd = None
        mb = re.search(r"\{\{\s*(?:birth[ _]date(?:[ _]and[ _]age)?|bda|dob)\s*\|([^}]*)\}\}", ib.get("birth_date") or ib.get("birth date") or "", re.I)
        if mb:
            nums = [x.strip() for x in mb.group(1).split("|") if re.fullmatch(r"\s*\d+\s*", x)]
            if len(nums) >= 3:
                try:
                    bd = dt.date(int(nums[0]), int(nums[1]), int(nums[2])).isoformat()
                except ValueError:
                    bd = None
            elif nums:
                bd = nums[0]
        if not bd and (ib.get("birth_date") or ""):
            yy = re.search(r"\b(19\d\d|20[0-2]\d)\b", P.cell_text(ib["birth_date"])[0] or "")
            bd = yy.group(1) if yy else None
        wp_bio[t] = (txt2 or None, st, ctry or (ABBR_TO_COUNTRY.get(st) if st else None), bd)
    out = OrderedDict()
    for t in titles:
        q = qmap.get(t)
        e = ents.get(q) if q else None
        bd = None
        if e:
            v = wd_claim(e, "P569")
            if v:
                tm, prec = v[0]["time"], v[0].get("precision", 11)
                yy = tm[1:5]
                bd = tm[1:11] if prec >= 11 else yy
        place = state = country = None
        if t in bp:
            pe = chain_ents.get(bp[t])
            place = label(pe)
            state = region_of(bp[t])
            c = wd_claim(pe, "P17") if pe else []
            if c:
                country = iso3(c[0]["id"])
        if not country and e:
            c = wd_claim(e, "P27")
            if c:
                country = iso3(c[0]["id"])
        if (not place or not bd or not state) and t in wp_bio:
            ib_place, ib_state, ib_country, ib_bd = wp_bio[t]
            if not place and ib_place:
                place = ib_place
            if not state and ib_state and (not place or t not in bp):
                state = ib_state
            if not country and ib_country:
                country = ib_country
            if not bd and ib_bd:
                bd = ib_bd
        if state and not country:
            country = ABBR_TO_COUNTRY.get(state)
        if state and country not in ("USA", "CAN"):
            state = None
        if state and country and ABBR_TO_COUNTRY.get(state) != country:
            state = None
        name = label(e) or re.sub(r"\s*\(.*\)$", "", t)
        out[t] = OrderedDict(name=name, qid=q, birth_date=bd, birth_place=place, state=state, country=country)
    return out


# ---------------------------------------------------------------- output

def finalize(seasons, series_meta, res):
    # canonicalize wiki links
    for s in seasons.values():
        if s["champion"]:
            s["champion"]["wiki"] = fix_wiki(res, s["champion"]["wiki"])
        for r in s["standings"]:
            r["wiki"] = fix_wiki(res, r["wiki"])
        for t in s["teams"]:
            for c in t["cars"]:
                for d in c["drivers"]:
                    d["wiki"] = fix_wiki(res, d["wiki"])
        for r in s["schedule"]:
            r["winner_wiki"] = fix_wiki(res, r["winner_wiki"])
        # data_level
        if s["schedule"] and s["standings"]:
            s["data_level"] = "full"
        elif s["schedule"]:
            s["data_level"] = "schedule"
        elif s["standings"]:
            s["data_level"] = "full" if s["teams"] else "schedule"
        else:
            s["data_level"] = "champion_only"


def write_outputs(seasons, series_meta, venues, drivers):
    for (k, y), s in seasons.items():
        d = os.path.join(OUT, k)
        os.makedirs(d, exist_ok=True)
        sched = []
        for r in s["schedule"]:
            sched.append(OrderedDict(round=r["round"], date=r["date"], race=r["race"], track=r["track"],
                                     city=r["city"], state=r["state"], winner=r["winner"], winner_wiki=r["winner_wiki"]))
        o = OrderedDict(series=s["series"], year=y, official_name=s["official_name"], data_level=s["data_level"],
                        champion=s["champion"], teams=s["teams"], standings=s["standings"], schedule=sched,
                        sources=s["sources"])
        with open(os.path.join(d, f"{y}.json"), "w") as f:
            json.dump(o, f, indent=1, ensure_ascii=False)
    # footprint
    for k, m in series_meta.items():
        fp = set()
        for (kk, y), s in seasons.items():
            if kk == k:
                fp |= {r["state"] for r in s["schedule"] if r.get("state")}
        m["footprint"] = sorted(fp)
    with open(os.path.join(OUT, "series.json"), "w") as f:
        json.dump(series_meta, f, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT, "venues.json"), "w") as f:
        json.dump(venues, f, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT, "drivers.json"), "w") as f:
        json.dump(drivers, f, indent=1, ensure_ascii=False)


def fill_venue_locations(seasons, res, venue_pages_cache={}):
    """Fill missing city/state in schedule rows from the venue's own Wikipedia infobox location."""
    need = sorted({fix_wiki(res, r["track_wiki"]) for s in seasons.values() for r in s["schedule"]
                   if r.get("track_wiki") and (not r.get("state") or not r.get("city"))} - {None})
    pgs = W.pages(need) if need else {}
    locs = {}
    for t in need:
        pg = pgs.get(t)
        if not pg:
            continue
        ib = infobox(pg["text"])
        city, state = venue_location(ib.get("location") or ib.get("city") or "")
        if not state:
            lead = P.clean_source(pg["text"])
            lead = re.sub(r"\{\{[^{}]*\}\}", "", lead)[:2500]
            for mm in re.finditer(r"\[\[([^\]|]+?),\s*([^\]|]+)(?:\|[^\]]*)?\]\]", lead):
                if mm.group(2) in REGION_NAMES:
                    city, state = mm.group(1), REGION_NAMES[mm.group(2)]
                    break
        if city and "," in city:
            city = city.split(",")[-1].strip()
        if state:
            locs[t] = (city, state)
    for s in seasons.values():
        for r in s["schedule"]:
            t = fix_wiki(res, r.get("track_wiki"))
            if t in locs:
                c, st = locs[t]
                if not r.get("state"):
                    r["state"] = st
                if not r.get("city") and c:
                    r["city"] = c


def main():
    W.seed_page_cache()
    W.seed_resolve_map()
    seasons, meta = build_series()
    build_events(seasons, meta)
    res = resolve_links()
    finalize(seasons, meta, res)
    fill_venue_locations(seasons, res)
    venues, _ = build_venues(seasons, res)
    drivers = build_drivers(seasons, res)
    write_outputs(seasons, meta, venues, drivers)
    log("seasons:", len(seasons), "venues existing/new:", len(venues["existing"]), len(venues["new"]), "drivers:", len(drivers))


if __name__ == "__main__":
    main()
