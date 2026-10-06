"""Extraction of facts (champions, season tables, event winners, infoboxes) from wikitext."""
import collections, re
import parse
from parse import clean, links, tables, parse_date, split_city_state, state_code

NONPERSON = re.compile(r"(?i)^(not awarded|none|n/a|tba|tbd|cancel|no race|rain|vacant|postpone|—|–|-|event cancelled|not held|unknown)")


BADNAME = re.compile(r"(?i)\bnot held\b|^see\b|cancel|rained? ?out|postpon|\bno race\b|\bTBA\b|\bTBD\b|^\d{4}|\bwinner\b|\bevent\b")


def person_from_cell(raw):
    """Return (name, wiki) from a wikitext fragment containing a driver."""
    raw = parse.strip_refs(raw)
    txt = clean(raw)
    lk = links(parse.expand_templates(raw))
    txt = re.sub(r"\s*\((?:[^()]*)\)", "", txt)          # "(2)", "(Harris Chassis)"
    txt = re.sub(r"\s*\[\d+\]", "", txt)
    txt = re.sub(r"[†‡*#^]+", "", txt).strip(" ,;:")
    txt = re.sub(r"\s*\$[\d,]+.*$", "", txt)
    if not txt or NONPERSON.match(txt) or BADNAME.search(txt) or not re.search(r"[A-Za-z]{2}", txt):
        return None, None
    name = txt
    wiki = None
    for tgt, disp in lk:
        d = re.sub(r"\s*\(.*?\)", "", disp).strip()
        if d and (d in name or name in d or d.split()[-1:] == name.split()[-1:]):
            wiki = re.sub(r"\s+", " ", tgt.split("#")[0]).strip()
            wiki = wiki[:1].upper() + wiki[1:]
            break
    return name, wiki


def year_of(s):
    m = re.search(r"\b(19[3-9]\d|20[0-3]\d)\b", s or "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- list-format winners/champions
LIST_ITEM = re.compile(r"^[*#]\s*(?:'''|\[\[[^|\]]*\|)?\s*'*(19\d\d|20\d\d)(?:\]\])?'*\s*(?:\(([^)]*)\))?\s*(?:[-–—:,]|&ndash;|&mdash;|\{\{(?:ndash|snd|mdash)\}\})?\s*(.*)$")


def list_section(wikitext, heading_re, stop_at_next=True):
    """Return the raw text of the first section whose heading matches heading_re."""
    lines = wikitext.split("\n")
    out, inside, lvl = [], False, 0
    for ln in lines:
        m = re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", ln.strip())
        if m:
            if inside and len(m.group(1)) <= lvl:
                break
            if not inside and re.search(heading_re, clean(m.group(2)), re.I):
                inside, lvl = True, len(m.group(1))
                continue
        if inside:
            out.append(ln)
    return "\n".join(out) if inside else None


def list_winners(section_text, split_on_comma=True):
    """Parse '* 1995 – Name, City, ST' style lines -> [{year,name,wiki,note,place}]"""
    res = []
    for ln in section_text.split("\n"):
        ln = parse.COMMENT_RE.sub("", ln).strip()
        if ln.startswith("**"):
            continue
        if res and re.match(r"^[^*#;:].*:\s*$", ln):
            break  # a new sub-list label such as "Sport Modifieds:"
        m = LIST_ITEM.match(ln)
        if not m:
            continue
        year = int(m.group(1)); note = m.group(2); rest = m.group(3)
        rest = parse.strip_refs(rest)
        # cut off hometown after first comma or ';' (outside links)
        seg = rest
        depth = 0; cut = None
        for i, ch in enumerate(rest):
            if rest[i:i+2] in ("[[", "{{") or ch == "(": depth += 1
            elif rest[i:i+2] in ("]]", "}}") or ch == ")": depth -= 1
            elif depth == 0 and (ch == ";" or (split_on_comma and ch == ",")):
                # keep ", Jr." / ", Sr."
                if re.match(r",\s*(Jr|Sr|II|III)\b", rest[i:]):
                    continue
                cut = i; break
        place = None
        if cut is not None:
            seg, place = rest[:cut], clean(rest[cut+1:])
        name, wiki = person_from_cell(seg)
        if not name:
            continue
        # strip trailing " at <track>" or chassis notes
        name = re.sub(r"\s+at\s+.*$", "", name).strip()
        res.append({"year": year, "name": name, "wiki": wiki, "note": note, "place": place})
    return res


# ---------------------------------------------------------------- table helpers
def split_header(rows):
    """-> (labels, data_rows). Header = leading rows made entirely of header cells (divider rows skipped)."""
    hdr, i = [], 0
    while i < len(rows) and rows[i] and all(c.header for c in rows[i]):
        texts = [c.text for c in rows[i]]
        if len(set(texts)) == 1 and len(rows[i]) > 2 and hdr:
            i += 1; continue  # full-width divider
        hdr.append(rows[i]); i += 1
    if not hdr and rows:
        hdr, i = [rows[0]], 1
    n = max(len(r) for r in hdr) if hdr else 0
    labels = []
    for k in range(n):
        parts = []
        for r in hdr:
            if k < len(r):
                t = r[k].text
                if t and t not in parts:
                    parts.append(t)
        labels.append(" ".join(parts).strip().lower())
    return labels, rows[i:]


def find_col(labels, *pats, exclude=None):
    for p in pats:
        for i, l in enumerate(labels):
            if exclude and re.search(exclude, l):
                continue
            if re.fullmatch(p, l):
                return i
    return None


def year_winner_tables(wikitext, heading_re=None, driver_pat=r".*(driver|winner|champion|name).*"):
    """Tables whose rows are year -> person; supports side-by-side column groups (Year,Driver,Year,Driver)."""
    out = []
    for heading, caption, rows in tables(wikitext):
        hp = " / ".join(heading) + ((" / " + caption) if caption else "")
        if heading_re and not (re.search(heading_re, hp, re.I) or re.search(heading_re, " / ".join(heading), re.I)):
            continue
        labels, data = split_header(rows)
        ycols = [i for i, l in enumerate(labels) if re.fullmatch(r"(season|years?)", l)]
        if not ycols:
            ycols = [i for i, l in enumerate(labels) if re.fullmatch(r"(date)", l)]
        if not ycols:
            continue
        groups = []
        for gi, yc in enumerate(ycols):
            end = ycols[gi + 1] if gi + 1 < len(ycols) else len(labels)
            dc = None
            for j in range(yc + 1, end):
                if re.fullmatch(driver_pat, labels[j]):
                    dc = j; break
            extra = {labels[j]: j for j in range(yc + 1, end) if j != dc}
            groups.append((yc, dc, extra))
        for r in data:
            for yc, dc, extra in groups:
                if dc is None or yc >= len(r) or dc >= len(r):
                    continue
                y = year_of(r[yc].text)
                if not y:
                    continue
                name, wiki = person_from_cell(r[dc].raw)
                if not name:
                    continue
                ex = {k: r[j].text for k, j in extra.items() if j < len(r)}
                out.append({"year": y, "name": name, "wiki": wiki, "extra": ex, "heading": heading, "datecell": r[yc].text})
    return out


# ---------------------------------------------------------------- season articles
ROLE_PATTERNS = {
    "round": [r"no\.?", r"#", r"rd\.?", r"rnd\.?", r"round", r"race no\.?", r"race #"],
    "date": [r".*date.*"],
    "race": [r"race title", r"race name", r"event", r"race", r"event name", r"name", r"race / event"],
    "track": [r"track", r"venue", r"circuit", r"race / track", r"race/track", r"track / location", r"track/location", r"speedway", r"track \(location\)"],
    "location": [r"location", r"city", r"city, state", r"location \(city, state\)"],
    "state": [r"state", r"st\.?"],
    "winner": [r"winning driver", r"winner", r"race winner", r"feature winner", r"a-?main winner", r"winning driver\(s\)", r"driver", r"a-feature winner"],
}


def roles(labels):
    r = {}
    taken = set()
    for role in ["round", "date", "winner", "track", "location", "state", "race"]:
        for p in ROLE_PATTERNS[role]:
            hit = None
            for i, l in enumerate(labels):
                if i in taken:
                    continue
                if re.fullmatch(p, l):
                    hit = i; break
            if hit is not None:
                r[role] = hit; taken.add(hit); break
    return r


def parse_track_cell(raw, text, has_race_col):
    """'Race - Track, City, State' -> dict(race, track, city, state, track_wiki)."""
    out = {"race": None, "track": None, "city": None, "state": None, "track_wiki": None}
    t = re.sub(r",\s*(Canada|United States|USA|U\.S\.A?\.?)\s*$", "", text or "")
    if re.fullmatch(r"(?i)\s*(tba|tbd|tbc|unknown)\s*", t):
        t = ""
    lk = links(parse.expand_templates(parse.strip_refs(raw)))
    if not has_race_col:
        m = re.match(r"^(.*?)\s+[-–—]\s+(.*)$", t)
        if m and "," in m.group(2):
            out["race"], t = m.group(1).strip(), m.group(2).strip()
        else:
            m = re.match(r"^(.*?)\s+(?:at|@)\s+(.*)$", t)
            if m and "," in m.group(2):
                out["race"], t = m.group(1).strip(), m.group(2).strip()
    parts = [p.strip() for p in t.split(",") if p.strip()]
    if len(parts) >= 3 and state_code(parts[-1]):
        out["state"] = state_code(parts[-1]); out["city"] = parts[-2]; out["track"] = ", ".join(parts[:-2])
    elif len(parts) == 2 and state_code(parts[-1]):
        # "Track, ST" or "City, ST"
        out["state"] = state_code(parts[-1]); out["track"] = parts[0]
    elif len(parts) == 2:
        out["track"], out["city"] = parts[0], parts[1]
    else:
        out["track"] = t or None
    if out["track"]:
        for tgt, disp in lk:
            if disp and (disp in out["track"] or out["track"] in disp) and not re.search(r",\s*[A-Z]", tgt):
                out["track_wiki"] = tgt.split("#")[0]; break
    return out


FINISH_RE = re.compile(r"^(\d{1,2})(?:\*|†|‡|\^|P|F|L|W)*$")


def parse_season(wikitext, year):
    """Return dict(schedule, entries, standings) parsed from a season article."""
    schedule, results, entries, standings = [], {}, [], []
    for heading, caption, rows in tables(wikitext):
        if not rows:
            continue
        labels, data = split_header(rows)
        hl = " / ".join(heading).lower() + " " + caption.lower()
        r = roles(labels)
        pos = find_col(labels, r"pos\.?", r"position", r"rank", r"place", r"pl\.?")
        pts = find_col(labels, r"points", r"pts\.?", r"total points", r"points total", r"total", r"pts\. total")
        drv = find_col(labels, r"driver", r"driver\(s\)", r"drivers", r"race driver", r"name")
        if pos is not None and drv is not None and (pts is not None or "standing" in hl):
            standings.extend(_standings(labels, data, pos, drv, pts))
            continue
        if "date" in r and ("track" in r or "race" in r or "location" in r):
            schedule.extend(_schedule(labels, data, r, year, hl))
            continue
        team_c = find_col(labels, r"team", r"owner", r"entrant", r"car owner", r"team/entrant", r"car owner / entrant", r"team / entrant", r"owner/team", r"team/owner", r"car owner/entrant")
        if "round" in r and "winner" in r and "date" not in r and (labels[r["winner"]] != "driver" or team_c is None) \
                and not re.search(r"team|driver|entr", hl):
            for row in data:
                if r["round"] < len(row) and r["winner"] < len(row):
                    lab = row[r["round"]].text.strip()
                    if "≠" in lab:
                        continue
                    nm, wk = person_from_cell(row[r["winner"]].raw)
                    results.setdefault(lab, []).append((nm, wk))
            continue
        num = find_col(labels, r"no\.?", r"car no\.?", r"#", r"number", r"car", r"car #")
        team = find_col(labels, r"team", r"owner", r"entrant", r"car owner", r"team/entrant", r"car owner / entrant", r"team / entrant", r"owner/team", r"team/owner", r"car owner/entrant")
        if drv is not None and (num is not None or team is not None):
            entries.extend(_entries(labels, data, num, drv, team, hl))
    # dedupe schedule (rowspans) and merge results by round
    seen, sched = set(), []
    for s in schedule:
        key = (s["round"], s["date"], s["race"], s["track"])
        if key in seen:
            continue
        seen.add(key); sched.append(s)
    used = collections.Counter()
    for s in sched:
        lab = s.get("_rlabel") or ""
        lst = results.get(lab)
        if lst and not s["winner"]:
            i = used[lab] if not lab.isdigit() else 0
            if i < len(lst):
                s["winner"], s["winner_wiki"] = lst[i]
            used[lab] += 1
    for i, s in enumerate(sched):
        s["round"] = i + 1
    # unique driver standings (keep first occurrence)
    st, seen = [], set()
    for s in standings:
        if s["name"] in seen:
            continue
        seen.add(s["name"]); st.append(s)
    return {"schedule": sched, "entries": entries, "standings": st}


def _int(s):
    m = re.match(r"^\s*(\d+)", s or "")
    return int(m.group(1)) if m else None


CANCEL = re.compile(r"(?i)cancel|rained out|rain ?out|postpone|not held|abandoned|weather")


def _schedule(labels, data, r, year, hl):
    out = []
    n = 0
    for row in data:
        if not row or all(c.header for c in row) and len(set(c.text for c in row)) == 1:
            continue
        g = lambda k: row[r[k]] if k in r and r[k] < len(row) else None
        datec, trackc, racec, locc, winc, rndc, stc = g("date"), g("track"), g("race"), g("location"), g("winner"), g("round"), g("state")
        dtext = datec.text if datec else ""
        if not dtext or not re.search(r"\d", dtext):
            continue
        rowtxt = " ".join(c.text for c in row)
        win_text = winc.text if winc else ""
        if CANCEL.search(win_text) or (CANCEL.search(rowtxt) and not win_text):
            continue
        n += 1
        rlabel = rndc.text.strip() if rndc else ""
        if "≠" in rlabel:
            n -= 1
            continue
        rnd = _int(rlabel) if rndc else None
        info = {"race": None, "track": None, "city": None, "state": None, "track_wiki": None}
        if trackc:
            info = parse_track_cell(trackc.raw, trackc.text, racec is not None)
        if racec and racec is not trackc:
            info["race"] = racec.text or info["race"]
        if locc:
            c, s = split_city_state(locc.text)
            info["city"] = info["city"] or c
            info["state"] = info["state"] or s
            if not trackc:
                info["track"] = None
        if stc and not info["state"]:
            info["state"] = state_code(stc.text)
        wn, ww = person_from_cell(winc.raw) if winc else (None, None)
        out.append({"round": rnd if rnd else n, "date": parse_date(dtext, year), "race": info["race"] or None,
                    "track": info["track"], "city": info["city"], "state": info["state"],
                    "winner": wn, "winner_wiki": ww, "_track_wiki": info["track_wiki"], "_rlabel": rlabel})
    return out


def _entries(labels, data, num, drv, team, hl):
    out = []
    chas = find_col(labels, r"chassis", r"chassis manufacturer", r"car")
    if chas == num:
        chas = None
    rnds = find_col(labels, r"rounds?", r"round\(s\)", r"races", r"rounds?\s*\(.*\)")
    ft = True if re.search(r"full[- ]time", hl) else (False if re.search(r"part[- ]time|limited", hl) else None)
    for row in data:
        if drv >= len(row):
            continue
        if all(c.header for c in row) and len(set(c.text for c in row)) == 1:
            continue
        number = row[num].text if num is not None and num < len(row) else None
        # multiple drivers in one cell separated by <br>
        raw = row[drv].raw
        drivers = []
        for piece in re.split(r"<br\s*/?>|\n\*|\n", raw):
            nm, wk = person_from_cell(piece)
            if nm:
                drivers.append({"name": nm, "wiki": wk})
        if not drivers:
            continue
        rtext = row[rnds].text if rnds is not None and rnds < len(row) else None
        fulltime = ft
        if rtext and fulltime is None:
            fulltime = True if re.fullmatch(r"(?i)all", rtext.strip()) else False
        out.append({"number": (number or None), "team": (row[team].text if team is not None and team < len(row) else None) or None,
                    "chassis": (row[chas].text if chas is not None and chas < len(row) else None) or None,
                    "full_time": fulltime, "drivers": drivers})
    return out


def _standings(labels, data, pos, drv, pts):
    out = []
    wins = find_col(labels, r"wins", r"w")
    starts = find_col(labels, r"starts", r"races", r"st\.?")
    t5 = find_col(labels, r"top ?5s?", r"t5", r"top-5s?", r"top fives?")
    t10 = find_col(labels, r"top ?10s?", r"t10", r"top-10s?", r"top tens?")
    known = {pos, drv, pts, wins, starts, t5, t10}
    race_cols = [i for i in range(len(labels)) if i not in known and i > drv and (pts is None or i < pts)]
    for row in data:
        if pos >= len(row) or drv >= len(row):
            continue
        p = _int(row[pos].text)
        if not p:
            continue
        nm, wk = person_from_cell(row[drv].raw)
        if not nm:
            continue
        g = lambda c: _int(row[c].text.replace(",", "")) if c is not None and c < len(row) else None
        rec = {"pos": p, "name": nm, "wiki": wk, "points": g(pts), "wins": g(wins), "starts": g(starts), "top5": g(t5), "top10": g(t10)}
        if len(race_cols) >= 3 and rec["wins"] is None:
            fins = []
            st = 0
            for c in race_cols:
                if c >= len(row):
                    continue
                v = row[c].text.strip()
                m = FINISH_RE.match(v)
                if m:
                    fins.append(int(m.group(1))); st += 1
                elif re.fullmatch(r"(?i)(dnf|ret|dq|dsq|nc|wd)", v):
                    st += 1
            if st:
                rec["wins"] = sum(1 for f in fins if f == 1)
                rec["top5"] = sum(1 for f in fins if f <= 5)
                rec["top10"] = sum(1 for f in fins if f <= 10)
                rec["starts"] = st
                rec["_derived"] = True
        out.append(rec)
    return out


# ---------------------------------------------------------------- infobox
def infobox(wikitext, kind=r"infobox (race ?track|motorsport venue|racetrack|venue|speedway|stadium)"):
    m = re.search(r"\{\{\s*(" + kind + r")\b", wikitext, re.I)
    if not m:
        m = re.search(r"\{\{\s*(infobox[^|}]*|motorsport venue|race ?track)\s*\|", wikitext, re.I)
        if not m:
            return {}
    i = m.start(); depth = 0; j = i
    while j < len(wikitext):
        if wikitext.startswith("{{", j): depth += 1; j += 2; continue
        if wikitext.startswith("}}", j):
            depth -= 1; j += 2
            if depth == 0: break
            continue
        j += 1
    body = wikitext[i+2:j-2]
    parts = parse._split_top(body)
    out = {"_type": parts[0].strip()}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


def coord_from(raw):
    if not raw:
        return None
    m = re.search(r"\{\{\s*coord\s*\|([^}]*)\}\}", raw, re.I)
    if not m:
        return None
    a = [x.strip() for x in m.group(1).split("|") if "=" not in x and not x.strip().startswith(("region", "type", "display", "format"))]
    try:
        if len(a) >= 2 and all(re.fullmatch(r"-?[\d.]+", x) for x in a[:2]) and (len(a) == 2 or not re.fullmatch(r"[\d.]+", a[2])):
            lat, lon = float(a[0]), float(a[1])
            if len(a) >= 4 and a[1] in "NS":
                pass
            return round(lat, 5), round(lon, 5)
        # d m s N d m s W  or d m N d m W  or d N d W
        def dms(seq):
            vals, hemi = [], None
            for x in seq:
                if x in ("N", "S", "E", "W"):
                    hemi = x; break
                vals.append(float(x))
            v = sum(val / (60 ** k) for k, val in enumerate(vals))
            return (-v if hemi in ("S", "W") else v), len(vals) + 1
        lat, n1 = dms(a)
        lon, _ = dms(a[n1:])
        return round(lat, 5), round(lon, 5)
    except (ValueError, IndexError):
        return None
