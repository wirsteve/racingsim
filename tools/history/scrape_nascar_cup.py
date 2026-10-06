#!/usr/bin/env python3
"""
Scrape NASCAR Cup Series season data (1995-2026) from English Wikipedia and
driver bios from Wikidata.

Outputs (relative to this script's directory):
  nascar_cup/{year}.json   one file per season (teams, standings, schedule)
  drivers_cup.json         wiki title -> bio (birth date/place, state, country, qid)

Raw responses are cached under cache_cup/ so re-runs are cheap.  Delete cache_cup/ to
force a fresh download.

Usage:
  python3 scrape_nascar_cup.py                 # all seasons + bios
  python3 scrape_nascar_cup.py 1996 2005       # only the given seasons (+ bios)
  python3 scrape_nascar_cup.py --no-bios       # skip Wikidata
  python3 scrape_nascar_cup.py --refresh       # re-download season wikitext

Data sources: en.wikipedia.org (MediaWiki API, falling back to index.php?action=raw
when the API is rate limited) and wikidata.org (wbgetentities API, falling back to
Special:EntityData).  No other sites are contacted.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time

import requests

try:
    import mwparserfromhell  # noqa: F401  (optional; not required)
except Exception:  # pragma: no cover
    mwparserfromhell = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "nascar_cup")
CACHE = os.path.join(HERE, "cache_cup")
DRIVERS_FILE = os.path.join(HERE, "drivers_cup.json")
YEARS = list(range(1995, 2027))
UA = "racingsim-personal/1.0 (personal non-commercial project; python-requests)"
WP_API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
SLEEP = 0.2

SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA


# ---------------------------------------------------------------------------
# HTTP with polite pacing, 429 backoff and on-disk cache
# ---------------------------------------------------------------------------
_last_req = [0.0]
_api_blocked_until = {}


def _pace():
    wait = SLEEP - (time.time() - _last_req[0])
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()


def http_get(url, params=None, tries=6, allow_redirects=True):
    """GET with pacing and retry on 429/5xx. Returns a Response or None."""
    delay = 1.5
    for _ in range(tries):
        _pace()
        try:
            r = SESSION.get(url, params=params, timeout=60, allow_redirects=allow_redirects)
        except requests.RequestException:
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ra = r.headers.get("retry-after")
            try:
                w = max(float(ra), delay) if ra else delay
            except ValueError:
                w = delay
            time.sleep(min(w, 30))
            delay *= 2
            continue
        return r
    return None


def cache_path(kind, key):
    d = os.path.join(CACHE, kind)
    os.makedirs(d, exist_ok=True)
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)[:80]
    return os.path.join(d, f"{safe}_{h}.json")


def cached(kind, key, fn):
    p = cache_path(kind, key)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    val = fn()
    if val is not None:
        with open(p, "w") as f:
            json.dump(val, f)
    return val


def api_json(api, params, tries=4):
    """Call a MediaWiki API; returns parsed JSON or None if unavailable."""
    if _api_blocked_until.get(api, 0) > time.time():
        return None
    p = dict(params)
    p.setdefault("format", "json")
    p.setdefault("formatversion", 2)
    r = http_get(api, p, tries=tries)
    if r is None or r.status_code != 200:
        # back off from the API for a minute; callers use fallbacks
        _api_blocked_until[api] = time.time() + 60
        return None
    try:
        return r.json()
    except ValueError:
        _api_blocked_until[api] = time.time() + 60
        return None


# ---------------------------------------------------------------------------
# Wikipedia page fetching
# ---------------------------------------------------------------------------
def season_title_guess(y):
    if y <= 2003:
        return f"{y} NASCAR Winston Cup Series"
    if y <= 2007:
        return f"{y} NASCAR Nextel Cup Series"
    if y <= 2016:
        return f"{y} NASCAR Sprint Cup Series"
    if y <= 2019:
        return f"{y} Monster Energy NASCAR Cup Series"
    return f"{y} NASCAR Cup Series"


def fetch_wikitext(title, refresh=False):
    """Return (resolved_title, wikitext) following redirects."""
    key = title

    def do():
        t = title
        for _ in range(4):
            d = api_json(WP_API, dict(action="parse", page=t, prop="wikitext", redirects=1))
            if d and "parse" in d:
                return {"title": d["parse"]["title"], "wikitext": d["parse"]["wikitext"]}
            if d and "error" in d and d["error"].get("code") == "missingtitle":
                return None
            # fallback: index.php?action=raw (handle redirects manually)
            r = http_get("https://en.wikipedia.org/w/index.php", dict(title=t, action="raw"), tries=8)
            if r is None:
                return None
            if r.status_code == 404:
                return None
            txt = r.text
            m = re.match(r"\s*#REDIRECT\s*\[\[([^\]|#]+)", txt, re.I)
            if m:
                t = m.group(1).strip()
                continue
            return {"title": t, "wikitext": txt}
        return None

    p = cache_path("wikitext", key)
    if refresh and os.path.exists(p):
        os.remove(p)
    return cached("wikitext", key, do)


def search_title(query):
    d = api_json(WP_API, dict(action="query", list="search", srsearch=query, srlimit=5))
    if not d:
        return None
    for hit in d.get("query", {}).get("search", []):
        return hit["title"]
    return None


def get_season_page(y, refresh=False):
    t = season_title_guess(y)
    res = fetch_wikitext(t, refresh)
    if res is None:
        alt = search_title(f"{y} NASCAR Cup Series season")
        if alt:
            res = fetch_wikitext(alt, refresh)
    return res


# ---------------------------------------------------------------------------
# Wikitext helpers
# ---------------------------------------------------------------------------
def norm_title(t):
    if t is None:
        return None
    t = t.strip().replace("_", " ")
    t = re.sub(r"\s+", " ", t)
    t = t.split("#")[0].strip()
    if not t:
        return None
    t = t[0].upper() + t[1:]
    return t.replace(" ", "_")


def strip_comments_refs(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>/]*/>", "", s, flags=re.I)
    s = re.sub(r"<ref[^>]*>.*?</ref\s*>", "", s, flags=re.S | re.I)
    return s


def find_matching(s, i, open_, close):
    """s[i:] starts with open_; return index just after the matching close."""
    depth = 0
    n = len(s)
    j = i
    while j < n:
        if s.startswith(open_, j):
            depth += 1
            j += len(open_)
        elif s.startswith(close, j):
            depth -= 1
            j += len(close)
            if depth == 0:
                return j
        else:
            j += 1
    return n


def split_top(s, sep="|"):
    """Split on sep not inside [[ ]] or {{ }}."""
    parts, cur, depth_l, depth_t = [], [], 0, 0
    i, n = 0, len(s)
    while i < n:
        if s.startswith("{{", i):
            depth_t += 1
            cur.append("{{")
            i += 2
        elif s.startswith("}}", i) and depth_t:
            depth_t -= 1
            cur.append("}}")
            i += 2
        elif s.startswith("[[", i):
            depth_l += 1
            cur.append("[[")
            i += 2
        elif s.startswith("]]", i) and depth_l:
            depth_l -= 1
            cur.append("]]")
            i += 2
        elif s.startswith(sep, i) and not depth_l and not depth_t:
            parts.append("".join(cur))
            cur = []
            i += len(sep)
        else:
            cur.append(s[i])
            i += 1
    parts.append("".join(cur))
    return parts


MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}

DROP_TEMPLATES = {
    "color box", "colorbox", "flagicon", "flag icon", "efn", "refn", "ref", "r", "sfn", "cite web",
    "cite news", "citation", "nbsp", "-", "·", "dot", "·", "clarify", "citation needed",
    "cn", "dagger", "double-dagger", "ref label", "note label", "abbr link", "anchor",
    "efn-ua", "efn-lr", "notetag", "#tag:ref", "nascar driver results legend", "legend",
    "small caps", "ns", "spaced ndash", "snd", "ndash", "mdash", "hidden", "dts-",
    "nascar cup series", "dagger", "tooltip2", "see also", "main", "further", "zwsp",
    "ref?", "sup ref", "update after", "as of", "background color", "bgcolor",
}
KEEP_FIRST = {"tooltip", "abbr", "nowrap", "nobr", "small", "big", "center", "sup", "sub",
              "nowrap begin", "lang", "smaller", "larger", "plainlist", "flatlist", "ubl",
              "unbulleted list", "hlist", "bold", "italic", "strong", "em", "sronly",
              "noitalic", "font", "huge", "resize", "large"}


def expand_templates(s):
    """Replace templates by a plain-wikitext approximation (links kept)."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        j = s.find("{{", i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        k = find_matching(s, j, "{{", "}}")
        inner = s[j + 2:k - 2]
        out.append(expand_one(inner))
        i = k
    return "".join(out)


def expand_one(inner):
    parts = split_top(inner, "|")
    name = parts[0].strip().lower().replace("_", " ")
    args = parts[1:]
    pos = [a for a in args if not re.match(r"^\s*[A-Za-z_][\w -]*\s*=", a)]
    named = {}
    for a in args:
        m = re.match(r"^\s*([A-Za-z_][\w -]*)\s*=(.*)$", a, re.S)
        if m:
            named[m.group(1).strip().lower()] = m.group(2)
    if name.startswith("#") and name not in ("#tag:ref",):
        return ""
    if name in ("sortname", "sort name"):
        first = expand_templates(pos[0]).strip() if pos else ""
        last = expand_templates(pos[1]).strip() if len(pos) > 1 else ""
        disp = (first + " " + last).strip()
        target = pos[2].strip() if len(pos) > 2 and pos[2].strip() else disp
        if named.get("nolink", "").strip():
            return disp
        return f"[[{target}|{disp}]]"
    if name in ("sort", "sortkey", "nts", "ntsh"):
        if name in ("nts", "ntsh"):
            return expand_templates(pos[0]) if pos else ""
        if len(pos) > 1:
            return expand_templates(pos[1])
        return ""
    if name in ("flagathlete", "flag athlete"):
        return expand_templates(pos[0]) if pos else ""
    if name in ("color", "colour", "font color", "fgcolor"):
        return expand_templates(pos[-1]) if pos else ""
    if name in ("n/a", "na", "dash", "n.a.", "—", "no", "nd"):
        return expand_templates(pos[0]) if pos else ""
    if name in ("start date", "start date and age", "dts", "date", "birth date", "birth date and age",
                "bda", "dob", "birth-date and age", "birth year and age", "birth based on age as of date"):
        nums = [p.strip() for p in pos if p.strip()]
        try:
            y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            return " ".join(nums)
    if name in DROP_TEMPLATES or name.startswith("cite") or name.startswith("efn") \
            or name.startswith("color box") or name.startswith("flag") or name.endswith("note") \
            or name.startswith("ref"):
        return ""
    if name in KEEP_FIRST:
        return expand_templates(pos[0]) if pos else ""
    if name in ("nowrap", "nobr"):
        return expand_templates(pos[0]) if pos else ""
    if name in ("ill", "interlanguage link", "interlanguage link multi"):
        return f"[[{pos[0].strip()}]]" if pos else ""
    if name in ("plainlist", "unbulleted list"):
        return "<br/>".join(expand_templates(p) for p in pos)
    if name in ("hs", "hidden sort", "sort key"):
        return ""
    # unknown template: drop it
    return ""


LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|((?:[^\[\]]|\[\[[^\]]*\]\])*))?\]\]")


def links(s):
    """List of (target, display) for wikilinks in s (after template expansion)."""
    res = []
    for m in LINK_RE.finditer(s):
        tgt = m.group(1).strip()
        if re.match(r"^(file|image|category|media|wikt|wiktionary|w|commons):", tgt, re.I):
            continue
        if tgt.startswith(":"):
            tgt = tgt[1:]
        disp = m.group(2)
        disp = clean_text(disp) if disp is not None else tgt
        res.append((tgt, disp))
    return res


def clean_text(s):
    """Wikitext -> plain text."""
    if s is None:
        return ""
    s = strip_comments_refs(s)
    s = expand_templates(s)
    s = re.sub(r"\[\[(?:File|Image):[^\]]*(?:\[\[[^\]]*\]\][^\]]*)*\]\]", "", s, flags=re.I)
    s = LINK_RE.sub(lambda m: (m.group(2) if m.group(2) is not None else m.group(1)), s)
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    s = s.replace("&nbsp;", " ").replace("&ndash;", "–").replace("&mdash;", "—").replace("&amp;", "&")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Sections & tables
# ---------------------------------------------------------------------------
HEAD_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.M)


def sections(text):
    """List of dicts {level, title, start, end} (end = start of next heading of same/higher level)."""
    heads = [(len(m.group(1)), clean_text(m.group(2)), m.start(), m.end()) for m in HEAD_RE.finditer(text)]
    res = []
    for idx, (lvl, title, st, en) in enumerate(heads):
        end = len(text)
        for lvl2, _, st2, _ in heads[idx + 1:]:
            if lvl2 <= lvl:
                end = st2
                break
        res.append({"level": lvl, "title": title, "start": st, "body": en, "end": end})
    return res


def heading_path(secs, pos):
    """Headings (outermost first) enclosing position pos."""
    path = [s for s in secs if s["start"] <= pos < s["end"]]
    path.sort(key=lambda s: s["level"])
    return [s["title"] for s in path]


ATTR_RE = re.compile(r'^\s*(?:[\w-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s|]+)\s*)+$')


ATTR_TOKENS_RE = re.compile(
    r"""^\s*(?:(?:[\w-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'|]+)|nowrap|\{\{\s*(?:n/a|na|yes|no|sort\|[^{}]*)\s*\}\})\s*)+$""",
    re.I)


def split_attrs(cell):
    """'attrs | content' -> (attrs, content)."""
    # MediaWiki semantics: text before the first top-level single "|" is always the
    # attribute string (invalid attributes are silently dropped by the renderer).
    parts = split_top(cell, "|")
    if len(parts) >= 2:
        return parts[0], "|".join(parts[1:])
    # attributes followed by an attribute-emitting template, e.g. 'rowspan="3" {{n/a}}'
    m = re.match(r'^(\s*(?:[\w-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\'|{]+)\s*)+)(\{\{\s*(?:n/a|na|yes|no|dunno|tba|tbd|n\.a\.)[^{}]*\}\}.*)$', cell, re.I | re.S)
    if m:
        return m.group(1), m.group(2)
    return "", cell


def attr_int(attrs, name):
    m = re.search(name + r'\s*=\s*["\']?\s*(\d+)', attrs, re.I)
    return int(m.group(1)) if m else 1


def find_tables(text):
    """Find top-level tables. Returns list of (start, end, raw)."""
    res = []
    i = 0
    lines = text.split("\n")
    offs = []
    o = 0
    for ln in lines:
        offs.append(o)
        o += len(ln) + 1
    depth = 0
    start = None
    for li, ln in enumerate(lines):
        st = ln.lstrip()
        if st.startswith("{|"):
            if depth == 0:
                start = li
            depth += 1
        elif st.startswith("|}"):
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    raw = "\n".join(lines[start:li + 1])
                    res.append((offs[start], offs[li] + len(ln), raw))
                    start = None
    return res


def parse_table(raw):
    """Parse a wikitable into rows of cells (dicts: header, attrs, text(raw), rowspan, colspan).
    Nested tables are kept inside the cell text."""
    raw = strip_comments_refs(raw)
    lines = raw.split("\n")
    rows = []
    cur = None
    caption = None
    depth = 0
    cell_target = None  # cell dict currently receiving continuation lines
    for ln in lines[1:]:
        st = ln.strip()
        if depth > 0:
            if cell_target is not None:
                cell_target["text"] += "\n" + ln
            if st.startswith("{|"):
                depth += 1
            elif st.startswith("|}"):
                depth -= 1
            continue
        if st.startswith("{|"):
            depth = 1
            if cell_target is not None:
                cell_target["text"] += "\n" + ln
            continue
        if st.startswith("|}"):
            break
        if st.startswith("|+"):
            caption = st[2:]
            continue
        if st.startswith("|-"):
            cur = []
            rows.append(cur)
            cell_target = None
            continue
        if st.startswith("!") or st.startswith("|"):
            if cur is None:
                cur = []
                rows.append(cur)
            is_h = st.startswith("!")
            body = st[1:]
            if is_h:
                pieces = []
                for p in split_top(body, "!!"):
                    pieces.extend(split_top(p, "||"))
            else:
                pieces = split_top(body, "||")
            for p in pieces:
                attrs, content = split_attrs(p)
                cell = {"header": is_h, "attrs": attrs, "text": content.strip(),
                        "rowspan": attr_int(attrs, "rowspan"), "colspan": attr_int(attrs, "colspan")}
                cur.append(cell)
                cell_target = cell
            continue
        # continuation line
        if cell_target is not None:
            cell_target["text"] += "\n" + ln
    rows = [r for r in rows if r]
    return {"rows": rows, "caption": caption}


def grid(table):
    """Expand rowspan/colspan into a rectangular grid of cell refs.
    Returns list of rows; each row is a list of (cell, is_origin) or None."""
    out = []
    pending = {}  # col -> (cell, remaining)
    for row in table["rows"]:
        g = []
        col = 0
        cells = list(row)
        ci = 0

        def fill_pending():
            nonlocal col
            while col in pending:
                cell, rem = pending[col]
                g.append((cell, False))
                if rem - 1 <= 0:
                    del pending[col]
                else:
                    pending[col] = (cell, rem - 1)
                col += 1

        while ci < len(cells):
            fill_pending()
            c = cells[ci]
            ci += 1
            cs = max(1, min(c["colspan"], 60))
            rs = max(1, min(c["rowspan"], 200))
            for k in range(cs):
                g.append((c, k == 0))
                if rs > 1:
                    pending[col] = (c, rs - 1)
                col += 1
        fill_pending()
        # trailing pending columns beyond
        maxc = max(pending.keys(), default=-1)
        while col <= maxc:
            if col in pending:
                cell, rem = pending[col]
                g.append((cell, False))
                if rem - 1 <= 0:
                    del pending[col]
                else:
                    pending[col] = (cell, rem - 1)
            else:
                g.append(None)
            col += 1
        out.append(g)
    return out


def header_rows(gr):
    """Indices of leading rows that are entirely header cells."""
    idx = []
    for i, r in enumerate(gr):
        cells = [c for c in r if c]
        if cells and all(c[0]["header"] for c in cells) and i == len(idx):
            idx.append(i)
        else:
            break
    return idx


def col_names(gr, hdr_idx):
    """Column names, combining multi-row headers (last non-empty wins)."""
    ncol = max((len(r) for r in gr), default=0)
    names = [""] * ncol
    for i in hdr_idx:
        for c, cell in enumerate(gr[i]):
            if cell:
                t = clean_text(cell[0]["text"])
                if t:
                    names[c] = t if not names[c] else (names[c] if cell[0].get("colspan", 1) > 1 else t)
    return names


def get_tables(text):
    secs = sections(text)
    res = []
    for st, en, raw in find_tables(text):
        t = parse_table(raw)
        t["start"] = st
        t["path"] = heading_path(secs, st)
        t["grid"] = grid(t)
        t["hdr"] = header_rows(t["grid"])
        t["cols"] = col_names(t["grid"], t["hdr"])
        res.append(t)
    return res


def cell_at(row, c):
    if c is None or c >= len(row) or row[c] is None:
        return None
    return row[c][0]


def find_col(cols, *pats, exclude=()):
    for p in pats:
        for i, name in enumerate(cols):
            n = name.lower()
            if re.search(p, n) and not any(re.search(e, n) for e in exclude):
                return i
    return None


# ---------------------------------------------------------------------------
# US states / tracks
# ---------------------------------------------------------------------------
STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC", "Washington, D.C.": "DC",
    # Canada
    "Ontario": "ON", "Quebec": "QC", "British Columbia": "BC", "Alberta": "AB", "Manitoba": "MB",
    "Saskatchewan": "SK", "Nova Scotia": "NS", "New Brunswick": "NB", "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE",
}
STATE_ABBR = set(STATES.values())

# keyword in track name -> (city, state); used when the page doesn't give a parseable location
TRACKS = [
    ("daytona", "Daytona Beach", "FL"), ("rockingham", "Rockingham", "NC"),
    ("north carolina motor speedway", "Rockingham", "NC"), ("north carolina speedway", "Rockingham", "NC"),
    ("richmond", "Richmond", "VA"), ("atlanta", "Hampton", "GA"), ("darlington", "Darlington", "SC"),
    ("bristol", "Bristol", "TN"), ("north wilkesboro", "North Wilkesboro", "NC"),
    ("martinsville", "Ridgeway", "VA"), ("talladega", "Lincoln", "AL"), ("sears point", "Sonoma", "CA"),
    ("infineon", "Sonoma", "CA"), ("sonoma", "Sonoma", "CA"), ("charlotte motor speedway", "Concord", "NC"),
    ("lowe's motor speedway", "Concord", "NC"), ("lowe’s motor speedway", "Concord", "NC"),
    ("charlotte", "Concord", "NC"), ("dover", "Dover", "DE"), ("pocono", "Long Pond", "PA"),
    ("michigan", "Brooklyn", "MI"), ("new hampshire", "Loudon", "NH"), ("indianapolis", "Speedway", "IN"),
    ("brickyard", "Speedway", "IN"), ("watkins glen", "Watkins Glen", "NY"), ("phoenix", "Avondale", "AZ"),
    ("ism raceway", "Avondale", "AZ"), ("texas motor speedway", "Fort Worth", "TX"),
    ("california speedway", "Fontana", "CA"), ("auto club speedway", "Fontana", "CA"),
    ("las vegas", "Las Vegas", "NV"), ("homestead", "Homestead", "FL"), ("miami", "Homestead", "FL"),
    ("chicagoland", "Joliet", "IL"), ("kansas", "Kansas City", "KS"), ("kentucky", "Sparta", "KY"),
    ("circuit of the americas", "Austin", "TX"), ("nashville superspeedway", "Lebanon", "TN"),
    ("road america", "Elkhart Lake", "WI"), ("gateway", "Madison", "IL"),
    ("world wide technology", "Madison", "IL"), ("los angeles memorial coliseum", "Los Angeles", "CA"),
    ("coliseum", "Los Angeles", "CA"), ("chicago street", "Chicago", "IL"), ("iowa", "Newton", "IA"),
    ("autódromo hermanos rodríguez", "Mexico City", None), ("hermanos rodr", "Mexico City", None),
    ("bowman gray", "Winston-Salem", "NC"), ("naval base coronado", "San Diego", "CA"),
    ("coronado", "San Diego", "CA"), ("suzuka", "Suzuka", None), ("motegi", "Motegi", None),
    ("ontario", "Ontario", "CA"), ("riverside", "Riverside", "CA"), ("north wilkes", "North Wilkesboro", "NC"),
    ("st. louis", "Madison", "IL"), ("fontana", "Fontana", "CA"),
]


def track_lookup(name):
    n = (name or "").lower()
    for kw, city, st in TRACKS:
        if kw in n:
            return city, st
    return None, None


def parse_location(text):
    """Parse 'City, State' (link target or text) -> (city, state_abbr)."""
    if not text:
        return None, None
    t = clean_text(text)
    t = re.sub(r"\s*\(.*?\)", "", t).strip()
    parts = [p.strip() for p in t.split(",") if p.strip()]
    if len(parts) >= 2:
        st = parts[-1]
        if st in STATES:
            return parts[0], STATES[st]
        if st.rstrip(".") in STATE_ABBR:
            return parts[0], st.rstrip(".")
        return parts[0], None
    if len(parts) == 1:
        if parts[0] in STATES:
            return None, STATES[parts[0]]
        return parts[0], None
    return None, None


# ---------------------------------------------------------------------------
# Season parsing
# ---------------------------------------------------------------------------
def parse_date(txt, year):
    t = clean_text(txt)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    m = re.search(r"([A-Z][a-z]+)\.?\s+(\d{1,2})", t)
    if m and m.group(1).lower() in MONTHS:
        return f"{year:04d}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]+)", t)
    if m and m.group(2).lower() in MONTHS:
        return f"{year:04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    # abbreviated months: "Feb 18"
    m = re.search(r"([A-Z][a-z]{2})\.?\s+(\d{1,2})", t)
    if m:
        for full, num in MONTHS.items():
            if full.startswith(m.group(1).lower()):
                return f"{year:04d}-{num:02d}-{int(m.group(2)):02d}"
    return None


def round_number(cell):
    if cell is None:
        return None
    t = clean_text(cell["text"])
    m = re.match(r"^\s*(\d{1,2})\s*$", t)
    return int(m.group(1)) if m else None


NAME_FIX_RE = re.compile(r"\s*\((?:R|i|R\)|\w)\)\s*$")


TOOLTIP_RE = re.compile(r"\{\{\s*tooltip\s*\|\s*(\d+)\s*\|\s*([^{}|]*)", re.I)


def person_from_cell(text, with_rounds=False):
    """Extract list of {name, wiki[, races, rounds]} from a driver cell."""
    raw = strip_comments_refs(text)
    raw_chunks = re.split(r"<br\s*/?>|\n", raw, flags=re.I)
    res = []
    for rch in raw_chunks:
        if not rch.strip():
            continue
        races = rounds = None
        m = TOOLTIP_RE.search(rch)
        if m:
            races, rounds = int(m.group(1)), m.group(2).strip()
        ch = expand_templates(re.sub(r"<small>.*?</small>", "", rch, flags=re.S | re.I))
        lk = [(t, d) for t, d in links(ch) if not is_nonperson_link(t)]
        found = []
        if lk:
            for tgt, disp in lk:
                nm = re.sub(r"\s*\(R\)\s*$", "", disp).strip()
                found.append({"name": nm, "wiki": norm_title(tgt)})
        else:
            nm = clean_text(ch)
            nm = re.sub(r"\(\s*R\s*\)|\(\s*i\s*\)", "", nm)
            nm = re.sub(r"\s+\d[\d,\s–\-]*$", "", nm).strip()  # trailing round numbers
            nm = nm.strip(" ,;*†‡")
            if nm and not re.match(r"^(tba|tbd|tbc|various|none|–|—|-|n/a|\d+.*)$", nm, re.I) and len(nm) < 60:
                found.append({"name": nm, "wiki": None})
        if with_rounds and len(found) == 1 and races is not None:
            found[0]["races"] = races
            found[0]["rounds"] = rounds
        res.extend(found)
    # dedupe preserving order (merge stints)
    seen, out = {}, []
    for p in res:
        k = p["wiki"] or p["name"]
        if k not in seen:
            seen[k] = p
            out.append(p)
        elif "races" in p:
            q = seen[k]
            q["races"] = q.get("races", 0) + p["races"]
            q["rounds"] = ", ".join(x for x in (q.get("rounds"), p["rounds"]) if x)
    return out


NONPERSON = re.compile(r"(rookie|nascar|^list of|\bchevrolet\b|^ford\b|\bford motor|\btoyota\b|\bdodge\b|"
                       r"\bpontiac\b|motorsports?\b|racing$|speedway|raceway|\bteam\b|cup series|xfinity|"
                       r"truck series|busch series|#|united states|ownership|^\d{4} )", re.I)


def is_nonperson_link(t):
    return bool(NONPERSON.search(t)) and not re.search(r"\(racing driver\)|\(driver\)", t, re.I)


def manuf_name(text):
    t = clean_text(text)
    t = re.sub(r"\s*\d+$", "", t)
    for m in ("Chevrolet", "Ford", "Pontiac", "Dodge", "Toyota", "Oldsmobile", "Buick", "Mercury"):
        if m.lower() in t.lower():
            return m
    return t or None


def car_numbers(text):
    t = re.sub(r"<small>.*?</small>", "", strip_comments_refs(text), flags=re.S | re.I)
    t = clean_text(strip_sup(t))
    return re.findall(r"(?<![\d])(\d{1,3})(?![\d])", t)


def pick_team_chunk(text):
    """A team cell may list several teams (with round counts) separated by <br>; keep the main one."""
    t = strip_comments_refs(text)
    chunks = [c for c in split_top(re.sub(r"<br\s*/?>", "\x00", t, flags=re.I), "\x00") if clean_text(c).strip()]
    chunks = [c.replace("\x00", " ") for c in chunks]
    if len(chunks) <= 1:
        return re.sub(r"<small>.*?</small>", "", t.replace("\x00", " "), flags=re.S | re.I)
    best, best_n = chunks[0], -1
    for c in chunks:
        m = re.search(r"\{\{\s*tooltip\s*\|\s*(\d+)", c, re.I)
        n = int(m.group(1)) if m else -1
        if n > best_n:
            best, best_n = c, n
    if best_n < 0:
        best = chunks[0]
    return re.sub(r"<small>.*?</small>", "", best, flags=re.S | re.I)


def section_fulltime(path):
    """Decide full-time status from heading path. Returns True/False/None."""
    path = [re.sub(r"[–—]", "-", x) for x in path]
    p = " / ".join(path).lower()
    last = path[-1].lower() if path else ""
    if re.search(r"limited|part[- ]time|part time|partial|one[- ]off", last):
        return False
    if re.search(r"complete|full[- ]time|full schedule|full season|chartered", last) and "non-chartered" not in last and "non chartered" not in last:
        return True
    if re.search(r"non-?\s?chartered|open teams|open entries", last):
        return None  # decide per row / subheading
    if re.search(r"limited|part[- ]time", p):
        return False
    if re.search(r"complete|full[- ]time|full schedule", p):
        return True
    return None


def parse_teams(tables, n_rounds, year):
    team_tabs = []
    for t in tables:
        cols = [c.lower() for c in t["cols"]]
        if not t["path"] or not any("team" in h.lower() for h in t["path"][:3]):
            continue
        has_team = find_col(t["cols"], r"^team", r"team") is not None
        has_drv = find_col(t["cols"], r"driver") is not None
        has_no = find_col(t["cols"], r"^no\.?$", r"^#$", r"car number", r"^no") is not None
        if has_team and has_drv and has_no:
            team_tabs.append(t)
    teams = {}
    order = []
    for t in team_tabs:
        ft = section_fulltime(t["path"])
        cols = t["cols"]
        c_man = find_col(cols, r"manufacturer", r"^make", r"^manu", r"^models?$", r"^car$", r"^chassis")
        c_team = find_col(cols, r"^team", r"team", exclude=(r"owner",))
        c_no = find_col(cols, r"^no\.?$", r"^#$", r"^no\b", r"car number", r"number")
        c_drv = find_col(cols, r"driver", exclude=(r"owner",))
        c_own = find_col(cols, r"owner")
        c_rnd = find_col(cols, r"^round", r"^races?$", r"rounds", r"^races?\b", r"^schedule")
        span_idx = {}
        for r in t["grid"][len(t["hdr"]):]:
            team_c, no_c, drv_c = cell_at(r, c_team), cell_at(r, c_no), cell_at(r, c_drv)
            if not team_c or not drv_c or not no_c:
                continue
            # skip rows that are just separators
            if team_c is drv_c:
                continue
            team_raw = pick_team_chunk(team_c["text"])
            team_name = clean_text(strip_sup(team_raw)).replace("\n", " ")
            team_name = re.sub(r"\s+", " ", team_name).strip(" †‡*§#")
            if not team_name or team_name.lower() in ("team",):
                continue
            tl = [x for x in links(expand_templates(team_raw)) if not re.match(r"(chevrolet|ford|toyota|dodge|pontiac)$", x[0], re.I)]
            team_wiki = norm_title(tl[0][0]) if tl else None
            nums = car_numbers(no_c["text"])
            if not nums:
                continue
            number = nums[0]
            man = manuf_name(cell_at(r, c_man)["text"]) if cell_at(r, c_man) else None
            owner = None
            if c_own is not None and cell_at(r, c_own):
                owner = clean_text(cell_at(r, c_own)["text"]).replace("\n", ", ") or None
            drivers = person_from_cell(drv_c["text"], with_rounds=True)
            if not drivers:
                continue
            rc = cell_at(r, c_rnd) if c_rnd is not None else None
            if rc is not None and len(drivers) == 1 and "races" not in drivers[0] and rc is not drv_c:
                m = TOOLTIP_RE.search(rc["text"])
                if m:
                    drivers[0]["races"], drivers[0]["rounds"] = int(m.group(1)), m.group(2).strip()
                else:
                    rt = clean_text(rc["text"])
                    if re.match(r"^\d+$", rt):
                        drivers[0]["races"] = int(rt)
            row_ft = ft
            if row_ft is None:
                # non-chartered without subheading: use races count if present
                row_ft = False
                if c_rnd is not None and cell_at(r, c_rnd):
                    txt = clean_text(cell_at(r, c_rnd)["text"]).lower()
                    if re.search(r"\ball\b|full|complete", txt):
                        row_ft = True
                    else:
                        m = re.match(r"^\s*(\d+)", txt)
                        if m and n_rounds and int(m.group(1)) >= n_rounds:
                            row_ft = True
            key = (team_name, man)
            if key not in teams:
                teams[key] = {"team": team_name, "team_wiki": team_wiki, "owner": owner,
                              "manufacturer": man, "cars": []}
                order.append(key)
            tm = teams[key]
            if owner and not tm["owner"]:
                tm["owner"] = owner
            car = None
            for cc in tm["cars"]:
                if cc["number"] == number and cc["full_time"] == row_ft:
                    car = cc
            if car is None:
                car = {"number": number, "full_time": row_ft, "drivers": []}
                tm["cars"].append(car)
            k = span_idx.get(id(no_c), 0)
            span_idx[id(no_c)] = k + 1
            pairs = [(number, drivers)]
            if len(nums) > 1 and len(nums) == len(drivers) and no_c["rowspan"] == 1:
                pairs = [(n, [d]) for n, d in zip(nums, drivers)]
            elif len(nums) > 1 and no_c["rowspan"] == len(nums) and k < len(nums):
                pairs = [(nums[k], drivers)]
            elif len(nums) > 1:
                car.setdefault("alt_numbers", [])
                for n in nums[1:]:
                    if n not in car["alt_numbers"]:
                        car["alt_numbers"].append(n)
            for num, drs in pairs:
                car2 = None
                for cc in tm["cars"]:
                    if cc["number"] == num and cc["full_time"] == row_ft:
                        car2 = cc
                if car2 is None:
                    car2 = {"number": num, "full_time": row_ft, "drivers": []}
                    tm["cars"].append(car2)
                for d in drs:
                    prev = [x for x in car2["drivers"] if (x["wiki"] or x["name"]) == (d["wiki"] or d["name"])]
                    if not prev:
                        car2["drivers"].append(d)
                    elif "races" in d and d.get("rounds") != prev[0].get("rounds"):
                        prev[0]["races"] = prev[0].get("races", 0) + d["races"]
                        prev[0]["rounds"] = ", ".join(x for x in (prev[0].get("rounds"), d["rounds"]) if x)
            if not car["drivers"]:
                tm["cars"].remove(car)
    return [teams[k] for k in order], team_tabs


def parse_schedule(tables, year):
    cand = []
    for t in tables:
        cols = t["cols"]
        if find_col(cols, r"track") is None or find_col(cols, r"date") is None:
            continue
        if not any(re.search(r"schedule|calendar", h, re.I) for h in t["path"]):
            continue
        cand.append(t)
    if not cand:
        for t in tables:
            cols = t["cols"]
            if find_col(cols, r"track") is not None and find_col(cols, r"date") is not None:
                cand.append(t)
    sched = []
    if not cand:
        return sched
    t = cand[0]
    cols = t["cols"]
    c_no = find_col(cols, r"^no\.?$", r"^no\b", r"^rd", r"round", r"^#$")
    if c_no is None:
        c_no = 0
    c_race = find_col(cols, r"race", exclude=(r"time",))
    c_track = find_col(cols, r"track", r"circuit", r"venue")
    c_loc = find_col(cols, r"location", r"city")
    c_date = find_col(cols, r"date")
    c_win = find_col(cols, r"winner", r"winning driver")
    seen = set()
    for r in t["grid"][len(t["hdr"]):]:
        rn = round_number(cell_at(r, c_no))
        if rn is None or rn in seen:
            continue
        seen.add(rn)
        race_c, track_c, date_c = cell_at(r, c_race), cell_at(r, c_track), cell_at(r, c_date)
        race = clean_text(race_c["text"]).replace("\n", " ") if race_c else None
        track, city, state = None, None, None
        if track_c:
            exp = expand_templates(strip_comments_refs(track_c["text"]))
            lk = links(exp)
            if lk:
                track = lk[0][1]
                if len(lk) > 1:
                    city, state = parse_location(lk[1][0])
                    if city and lk[1][1] and "," not in lk[1][1]:
                        city = lk[1][1]
                    if state is None:
                        city2, state = parse_location(lk[1][1])
            else:
                parts = clean_text(exp).split(",")
                track = parts[0].strip()
                if len(parts) > 1:
                    city, state = parse_location(",".join(parts[1:]))
            track = re.sub(r"\s+", " ", track or "").strip() or None
        if c_loc is not None and cell_at(r, c_loc) and (city is None or state is None):
            exp = expand_templates(strip_comments_refs(cell_at(r, c_loc)["text"]))
            lk = links(exp)
            if lk:
                c1, s1 = parse_location(lk[0][0])
                if s1 is None:
                    c1, s1 = parse_location(lk[0][1])
                if len(lk) > 1 and s1 is None:
                    _, s1 = parse_location(lk[1][0])
                    c1 = lk[0][1]
            else:
                c1, s1 = parse_location(exp)
            city = city or c1
            state = state or s1
        tc, ts = track_lookup(track)
        if city is None:
            city = tc
        if state is None:
            state = ts
        date = parse_date(date_c["text"], year) if date_c else None
        winner, winner_wiki = None, None
        if c_win is not None and cell_at(r, c_win):
            ppl = person_from_cell(cell_at(r, c_win)["text"])
            if ppl:
                winner, winner_wiki = ppl[0]["name"], ppl[0]["wiki"]
        country = "USA"
        if city in ("Mexico City",) or (track and re.search(r"Hermanos|Mexico", track)):
            country, state = "MEX", None
        elif city in ("Suzuka", "Motegi"):
            country = "JPN"
        elif state in ("ON", "QC", "BC", "AB"):
            country = "CAN"
        sched.append({"round": rn, "date": date, "race": race, "track": track, "city": city,
                      "state": state, "country": country, "winner": winner, "winner_wiki": winner_wiki})
    sched.sort(key=lambda x: x["round"])
    return sched


def parse_results(tables):
    """Race results table -> {round: (name, wiki)}"""
    res = {}
    for t in tables:
        cols = t["cols"]
        c_win = find_col(cols, r"winning driver", r"^winner", r"race winner", r"winner")
        if c_win is None:
            continue
        if find_col(cols, r"pole") is None and find_col(cols, r"race") is None:
            continue
        c_no = find_col(cols, r"^no\.?$", r"^no\b", r"race number", r"^rd", r"round", r"^#$")
        if c_no is None:
            c_no = 0
        for r in t["grid"][len(t["hdr"]):]:
            rn = round_number(cell_at(r, c_no))
            if rn is None or rn in res:
                continue
            wc = cell_at(r, c_win)
            if not wc:
                continue
            ppl = person_from_cell(wc["text"])
            if ppl:
                res[rn] = (ppl[0]["name"], ppl[0]["wiki"])
        if res:
            break
    return res


FINISH_RE = re.compile(r"^\s*(\d{1,2})(?!\d)")


SUP_RE = re.compile(r"<sup[^>]*>.*?</sup\s*>|\{\{\s*(?:sup|su|efn|ref|abbr)\s*\|[^{}]*\}\}", re.S | re.I)


def strip_sup(text):
    return SUP_RE.sub("", text or "")


def parse_finish(text):
    """Return ('fin', n) / ('dnq', code) / (None, None) for a results cell."""
    t = clean_text(strip_sup(text))
    t = t.replace("*", "").strip()
    if not t:
        return None, None
    m = FINISH_RE.match(t)
    if m:
        return "fin", int(m.group(1))
    code = re.sub(r"[^A-Za-z]", "", t).upper()
    if code:
        return "dnq", code
    return None, None


def parse_standings(tables, text, year):
    cand = []
    for t in tables:
        cols = [c.lower() for c in t["cols"]]
        c_drv = find_col(t["cols"], r"^driver")
        c_pts = find_col(t["cols"], r"^pts\.?$", r"^points$", r"^pts", r"points")
        c_pos = find_col(t["cols"], r"^pos", r"^rank", r"^\#$")
        if c_drv is None or c_pts is None or c_pos is None:
            continue
        p = " / ".join(t["path"]).lower()
        if "owner" in p or "manufacturer" in p or "rookie" in p:
            continue
        score = 0
        if "driver" in p:
            score += 2
        if "standing" in p or "championship" in p or "points" in p:
            score += 1
        cand.append((score, -len(cand), t, c_pos, c_drv, c_pts))
    if not cand:
        return [], None
    cand.sort(key=lambda x: (x[0], len(x[2]["grid"])), reverse=True)
    _, _, t, c_pos, c_drv, c_pts = cand[0]
    # race columns: between driver and points columns (non-empty header)
    hdr_last = t["grid"][t["hdr"][-1]] if t["hdr"] else []
    race_cols = []
    for c in range(c_drv + 1, c_pts):
        name = t["cols"][c].strip()
        if not name:
            continue
        if re.search(r"^(pts\.?|points|stage.*|bonus.*|wins?|top ?\d+|starts|poles?|laps.*|led|avg.*|behind|diff.*|car|no\.?|team|make|playoff.*)$", name, re.I) and name != "CAR":
            continue
        hc = None
        for hi in t["hdr"]:
            cc = cell_at(t["grid"][hi], c)
            if cc and clean_text(cc["text"]).strip():
                hc = cc
        raw_h = hc["text"] if hc else ""
        if re.match(r"^D\d$", name) or re.search(r"duel|125s?\b|clash|shootout|all-star|open\b", raw_h, re.I):
            continue  # non-championship qualifying races
        race_cols.append(c)
    stand = []
    for r in t["grid"][len(t["hdr"]):]:
        pc, dc, ptc = cell_at(r, c_pos), cell_at(r, c_drv), cell_at(r, c_pts)
        if not dc or not ptc or not pc:
            continue
        if pc is dc:
            continue
        ppl = person_from_cell(dc["text"])
        if not ppl:
            continue
        pos_t = clean_text(pc["text"])
        m = re.match(r"^\s*(\d+)", pos_t)
        pos = int(m.group(1)) if m else None
        pts_t = clean_text(strip_sup(ptc["text"])).replace(",", "")
        m2 = re.search(r"-?\d+", pts_t)
        pts = int(m2.group(0)) if m2 else None
        wins = top5 = top10 = starts = 0
        finishes = []
        for c in race_cols:
            cc = cell_at(r, c)
            if cc is None or cc is pc or cc is dc:
                finishes.append(None)
                continue
            kind, val = parse_finish(cc["text"])
            if kind == "fin":
                starts += 1
                wins += val == 1
                top5 += val <= 5
                top10 += val <= 10
                finishes.append(val)
            elif kind == "dnq":
                finishes.append(val)
            else:
                finishes.append(None)
        if pos is None and pts is None and starts == 0:
            continue
        stand.append({"pos": pos, "name": ppl[0]["name"], "wiki": ppl[0]["wiki"], "points": pts,
                      "wins": wins, "top5": top5, "top10": top10, "starts": starts,
                      "_finishes": finishes})
    return stand, {"race_cols": len(race_cols), "path": t["path"]}


def official_name(title, year):
    return re.sub(r"^\d{4}\s+", "", title)


def build_season(year, refresh=False):
    page = get_season_page(year, refresh)
    if page is None:
        raise RuntimeError(f"no page for {year}")
    title, text = page["title"], page["wikitext"]
    tables = get_tables(text)

    schedule = parse_schedule(tables, year)
    n_rounds = len(schedule)
    teams, team_tabs = parse_teams(tables, n_rounds, year)
    standings, sinfo = parse_standings(tables, text, year)

    # name -> wiki map from every link on the page
    name2wiki = {}
    for tgt, disp in links(expand_templates(strip_comments_refs(text))):
        if disp and disp not in name2wiki:
            name2wiki[disp] = norm_title(tgt)
    for s in standings:
        if s["wiki"]:
            name2wiki[s["name"]] = s["wiki"]

    results = parse_results(tables)
    # winners from standings finishes (column j = round j+1)
    fin_winner = {}
    if sinfo and sinfo["race_cols"]:
        for s in standings:
            for j, f in enumerate(s["_finishes"]):
                if f == 1:
                    fin_winner.setdefault(j + 1, (s["name"], s["wiki"]))
    for race in schedule:
        rn = race["round"]
        if not race["winner"]:
            if rn in results:
                race["winner"], race["winner_wiki"] = results[rn]
            elif n_rounds and sinfo and sinfo["race_cols"] == n_rounds and rn in fin_winner:
                race["winner"], race["winner_wiki"] = fin_winner[rn]
        if race["winner"] and not race["winner_wiki"]:
            race["winner_wiki"] = name2wiki.get(race["winner"])
    for s in standings:
        if not s["wiki"]:
            s["wiki"] = name2wiki.get(s["name"])
        s.pop("_finishes", None)
    for tm in teams:
        for car in tm["cars"]:
            for d in car["drivers"]:
                if not d["wiki"]:
                    d["wiki"] = name2wiki.get(d["name"])
    # If season has standings race columns, also trust them for number of starts
    meta = {"standings_race_columns": sinfo["race_cols"] if sinfo else 0,
            "team_tables": [" / ".join(t["path"]) for t in team_tabs]}
    return {
        "series": "cup_series",
        "year": year,
        "official_name": official_name(title, year),
        "teams": teams,
        "standings": standings,
        "schedule": schedule,
        "sources": ["https://en.wikipedia.org/wiki/" + title.replace(" ", "_")],
        "_meta": meta,
    }


# ---------------------------------------------------------------------------
# Title canonicalisation (redirects) and Wikidata bios
# ---------------------------------------------------------------------------
def resolve_titles(titles):
    """title -> (canonical_title, qid). Uses API in batches; fallback Special:ItemByTitle."""
    out = {}
    todo = []
    for t in titles:
        c = cached("titles", t, lambda: None)
        if c is not None:
            out[t] = tuple(c)
        else:
            todo.append(t)
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        d = api_json(WP_API, dict(action="query", titles="|".join(x.replace("_", " ") for x in batch),
                                  prop="pageprops", ppprop="wikibase_item", redirects=1))
        if d and "query" in d:
            q = d["query"]
            mapping = {}
            for n in q.get("normalized", []):
                mapping[n["from"]] = n["to"]
            redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
            pages = {p["title"]: p for p in q.get("pages", [])}
            for t in batch:
                s = t.replace("_", " ")
                s = mapping.get(s, s)
                s = redir.get(s, s)
                p = pages.get(s)
                if p is None or p.get("missing"):
                    val = [norm_title(s), None]
                else:
                    val = [norm_title(p["title"]), p.get("pageprops", {}).get("wikibase_item")]
                out[t] = tuple(val)
                with open(cache_path("titles", t), "w") as f:
                    json.dump(val, f)
        else:
            for t in batch:
                r = http_get("https://www.wikidata.org/wiki/Special:ItemByTitle/enwiki/" + t, tries=6,
                             allow_redirects=False)
                qid = None
                if r is not None and r.status_code in (301, 302, 303):
                    m = re.search(r"(Q\d+)", r.headers.get("location", ""))
                    qid = m.group(1) if m else None
                val = [t, qid]
                out[t] = tuple(val)
                if r is not None:
                    with open(cache_path("titles", t), "w") as f:
                        json.dump(val, f)
    return out


def _slim(ent):
    claims = {}
    for pid in ("P569", "P19", "P131", "P17", "P31", "P300", "P298", "P27"):
        vals = []
        for c in ent.get("claims", {}).get(pid, []):
            if c.get("rank") == "deprecated":
                continue
            dv = c.get("mainsnak", {}).get("datavalue")
            if not dv:
                continue
            v = dv.get("value")
            if isinstance(v, dict) and "id" in v:
                vals.append({"id": v["id"], "rank": c.get("rank")})
            elif isinstance(v, dict) and "time" in v:
                vals.append({"time": v["time"], "precision": v.get("precision"), "rank": c.get("rank")})
            else:
                vals.append({"value": v, "rank": c.get("rank")})
        if vals:
            # preferred first
            vals.sort(key=lambda x: 0 if x.get("rank") == "preferred" else 1)
            claims[pid] = vals
    label = ent.get("labels", {}).get("en", {}).get("value")
    return {"id": ent.get("id"), "label": label, "claims": claims}


def get_entities(qids):
    out = {}
    todo = []
    for q in qids:
        p = cache_path("wd", q)
        if os.path.exists(p):
            with open(p) as f:
                out[q] = json.load(f)
        else:
            todo.append(q)
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        d = api_json(WD_API, dict(action="wbgetentities", ids="|".join(batch), props="claims|labels",
                                  languages="en", formatversion=1))
        ents = {}
        if d and "entities" in d:
            ents = d["entities"]
        else:
            for q in batch:
                r = http_get(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json", tries=8)
                if r is not None and r.status_code == 200:
                    try:
                        ents.update(r.json().get("entities", {}))
                    except ValueError:
                        pass
        for k, ent in ents.items():
            s = _slim(ent)
            q = s["id"] or k
            out[q] = s
            if k != q:
                out[k] = s
            for key in {k, q}:
                with open(cache_path("wd", key), "w") as f:
                    json.dump(s, f)
    return out


def first_id(ent, pid):
    for v in (ent or {}).get("claims", {}).get(pid, []):
        if "id" in v:
            return v["id"]
    return None


def first_val(ent, pid):
    for v in (ent or {}).get("claims", {}).get(pid, []):
        if "value" in v:
            return v["value"]
    return None


def fmt_date(v):
    if not v:
        return None
    m = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})", v["time"])
    if not m:
        return None
    prec = v.get("precision") or 11
    if prec >= 11:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if prec == 10:
        return f"{m.group(1)}-{m.group(2)}"
    return m.group(1)


def build_bios(titles):
    titles = sorted(set(t for t in titles if t))
    print(f"[bios] resolving {len(titles)} titles", flush=True)
    res = resolve_titles(titles)
    qids = sorted(set(q for _, q in res.values() if q))
    print(f"[bios] fetching {len(qids)} person entities", flush=True)
    people = get_entities(qids)
    # places and their P131 chains
    place_ids = set()
    for q in qids:
        pid = first_id(people.get(q), "P19")
        if pid:
            place_ids.add(pid)
    places = {}
    frontier = set(place_ids)
    for depth in range(7):
        need = [p for p in frontier if p not in places]
        if not need:
            break
        print(f"[bios] fetching {len(need)} place entities (level {depth})", flush=True)
        got = get_entities(need)
        places.update(got)
        nxt = set()
        for p in need:
            e = got.get(p)
            if not e:
                continue
            v = first_val(e, "P300")
            if v and re.match(r"^(US|CA)-", v):
                continue  # reached a state/province
            up = first_id(e, "P131")
            if up:
                nxt.add(up)
            c = first_id(e, "P17")
            if c:
                nxt.add(c)
        frontier = nxt
    # countries
    countries = set()
    for e in list(places.values()):
        c = first_id(e, "P17")
        if c:
            countries.add(c)
    for q in qids:
        c = first_id(people.get(q), "P27")
        if c:
            countries.add(c)
    places.update(get_entities([c for c in countries if c not in places]))

    def resolve_place(pid):
        state, state_label, country = None, None, None
        seen = set()
        cur = pid
        for _ in range(8):
            if not cur or cur in seen:
                break
            seen.add(cur)
            e = places.get(cur)
            if not e:
                break
            v = first_val(e, "P300")
            if v and re.match(r"^(US|CA)-[A-Z]{2}$", v):
                state = v[3:]
                state_label = e.get("label")
                country = "USA" if v.startswith("US") else "CAN"
                break
            if country is None:
                c = first_id(e, "P17")
                if c and places.get(c):
                    country = first_val(places[c], "P298")
            cur = first_id(e, "P131")
        if country is None:
            e = places.get(pid)
            c = first_id(e, "P17")
            if c and places.get(c):
                country = first_val(places[c], "P298")
        return state, state_label, country

    def infobox_fallback(title):
        """Birth date/place from the article's infobox (Wikipedia) when Wikidata lacks them."""
        page = fetch_wikitext(title.replace("_", " "))
        if not page:
            return None, None, None, None
        txt = strip_comments_refs(page["wikitext"])
        out_bd = out_bp = out_st = out_c = None
        m = re.search(r"\|\s*birth_date\s*=\s*(.*)", txt)
        if m:
            v = expand_templates(split_top(m.group(1), "|")[0])
            mm = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
            if mm:
                out_bd = mm.group(0)
            else:
                d2 = parse_date(v, 0)
                y = re.search(r"\b(1[89]\d\d|20[0-2]\d)\b", clean_text(v))
                if d2 and y:
                    out_bd = f"{y.group(1)}{d2[4:]}"
                elif y:
                    out_bd = y.group(1)
        m = re.search(r"\|\s*birth_place\s*=\s*(.*)", txt)
        bp_raw = split_top(m.group(1), "|")[0] if m else ""
        if re.search(r"[A-Za-z]", clean_text(bp_raw)):
            raw = expand_templates(bp_raw)
            out_bp = re.sub(r",?\s*(U\.S\.A?\.?|United States|USA|US)\s*$", "", clean_text(raw)).strip(" ,")
            for tgt, disp in links(raw):
                c1, s1 = parse_location(tgt)
                if s1:
                    out_st = s1
                    break
            if not out_st:
                _, out_st = parse_location(out_bp)
            if out_st:
                out_c = "CAN" if out_st in ("ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE") else "USA"
            elif re.search(r"U\.S\.|United States", clean_text(raw)):
                out_c = "USA"
        return out_bd, out_bp, out_st, out_c

    bios = {}
    for t in titles:
        canon, qid = res.get(t, (t, None))
        ent = people.get(qid) if qid else None
        name = (ent or {}).get("label") or t.replace("_", " ")
        name = re.sub(r"\s*\(.*?\)\s*$", "", name)
        bd = fmt_date((ent or {}).get("claims", {}).get("P569", [None])[0]) if ent else None
        bp, state, country = None, None, None
        pid = first_id(ent, "P19") if ent else None
        if pid:
            state, state_label, country = resolve_place(pid)
            pl = places.get(pid, {}).get("label")
            if pl:
                bp = pl
                if state_label and state_label != pl:
                    bp = f"{pl}, {state_label}"
                elif not state_label:
                    c = first_id(places.get(pid), "P17")
                    cl = places.get(c, {}).get("label") if c else None
                    if cl and cl != pl:
                        bp = f"{pl}, {cl}"
        if country is None and ent:
            c = first_id(ent, "P27")
            if c and places.get(c):
                country = first_val(places[c], "P298")
        if not bd or not bp or (country in (None, "USA", "CAN") and not state):
            fbd, fbp, fst, fc = infobox_fallback(canon or t)
            bd = bd or fbd
            if not bp and fbp:
                bp = fbp
            if not state and fst and (country in (None, "USA", "CAN")):
                state = fst
                country = country or fc
            country = country or fc
        bios[t] = {"name": name, "birth_date": bd, "birth_place": bp, "state": state,
                   "country": country, "qid": qid}
    return bios, res


# ---------------------------------------------------------------------------
# Validation / main
# ---------------------------------------------------------------------------
def validate(season):
    issues = []
    ft = sum(1 for tm in season["teams"] for c in tm["cars"] if c["full_time"])
    if not season["standings"]:
        issues.append("no standings")
    if ft < 30:
        issues.append(f"only {ft} full-time cars")
    n = len(season["schedule"])
    if not (29 <= n <= 36):
        issues.append(f"schedule length {n}")
    if season["schedule"]:
        rounds = [r["round"] for r in season["schedule"]]
        if rounds != list(range(1, n + 1)):
            issues.append("non-contiguous rounds")
        today = dt.date.today().isoformat()
        miss_w = sum(1 for r in season["schedule"] if not r["winner"] and (r["date"] or "9999") < today)
        future = sum(1 for r in season["schedule"] if (r["date"] or "") >= today)
        if future:
            issues_note = f"{future} races not yet run"
            season.setdefault("_notes", []).append(issues_note)
        miss_s = sum(1 for r in season["schedule"] if not r["state"] and r["city"] != "Mexico City")
        miss_d = sum(1 for r in season["schedule"] if not r["date"])
        if miss_d:
            issues.append(f"{miss_d} races w/o date")
        if miss_s:
            issues.append(f"{miss_s} races w/o state")
        if miss_w:
            issues.append(f"{miss_w} races w/o winner")
    return ft, issues


def main(argv):
    refresh = "--refresh" in argv
    no_bios = "--no-bios" in argv
    years = [int(a) for a in argv if a.isdigit()]
    years = years or YEARS
    os.makedirs(OUT_DIR, exist_ok=True)
    seasons = {}
    for y in years:
        try:
            s = build_season(y, refresh)
        except Exception as e:  # keep going
            import traceback
            traceback.print_exc()
            print(f"{y}: FAILED {e}")
            continue
        seasons[y] = s

    # canonicalise titles (follow redirects) so drivers merge across seasons
    all_titles = set()
    for s in seasons.values():
        for st in s["standings"]:
            all_titles.add(st["wiki"])
        for tm in s["teams"]:
            for c in tm["cars"]:
                for d in c["drivers"]:
                    all_titles.add(d["wiki"])
        for r in s["schedule"]:
            all_titles.add(r["winner_wiki"])
    all_titles.discard(None)
    bios, res = ({}, {})
    if not no_bios:
        bios, res = build_bios(all_titles)

    def canon(t):
        if t and t in res:
            return norm_title(res[t][0])
        return t

    for y, s in seasons.items():
        for st in s["standings"]:
            st["wiki"] = canon(st["wiki"])
        for tm in s["teams"]:
            for c in tm["cars"]:
                for d in c["drivers"]:
                    d["wiki"] = canon(d["wiki"])
        for r in s["schedule"]:
            r["winner_wiki"] = canon(r["winner_wiki"])
        s.pop("_meta", None)
        with open(os.path.join(OUT_DIR, f"{y}.json"), "w") as f:
            json.dump(s, f, indent=1, ensure_ascii=False)

    if not no_bios:
        # drivers file keyed by canonical title, only for drivers in teams/standings
        need = set()
        for s in seasons.values():
            for st in s["standings"]:
                need.add(st["wiki"])
            for tm in s["teams"]:
                for c in tm["cars"]:
                    for d in c["drivers"]:
                        need.add(d["wiki"])
        need.discard(None)
        drivers = {}
        if os.path.exists(DRIVERS_FILE) and set(years) != set(YEARS):
            with open(DRIVERS_FILE) as f:
                drivers = json.load(f)
        for t, b in bios.items():
            c = canon(t)
            if c in need and (c not in drivers or drivers[c].get("qid") is None):
                drivers[c] = b
        drivers = dict(sorted(drivers.items()))
        with open(DRIVERS_FILE, "w") as f:
            json.dump(drivers, f, indent=1, ensure_ascii=False)

    # coverage table
    print()
    print(f"{'year':<5} {'name':<38} {'teams':>5} {'FTcars':>6} {'PTcars':>6} {'stand':>5} "
          f"{'sched':>5} {'win':>4}  status")
    ok = 0
    for y in years:
        p = os.path.join(OUT_DIR, f"{y}.json")
        if not os.path.exists(p):
            print(f"{y:<5} MISSING")
            continue
        with open(p) as f:
            s = json.load(f)
        ft, issues = validate(s)
        pt = sum(1 for tm in s["teams"] for c in tm["cars"] if not c["full_time"])
        w = sum(1 for r in s["schedule"] if r["winner"])
        st = "OK" if not issues else "PARTIAL: " + "; ".join(issues)
        if s.get("_notes"):
            st += " (" + "; ".join(s["_notes"]) + ")"
        ok += not issues
        print(f"{y:<5} {s['official_name'][:38]:<38} {len(s['teams']):>5} {ft:>6} {pt:>6} "
              f"{len(s['standings']):>5} {len(s['schedule']):>5} {w:>4}  {st}")
    print(f"\n{ok}/{len(years)} seasons fully valid")
    if os.path.exists(DRIVERS_FILE):
        with open(DRIVERS_FILE) as f:
            dr = json.load(f)
        n = len(dr)
        if n:
            def pct(k):
                return 100.0 * sum(1 for v in dr.values() if v.get(k)) / n
            print(f"drivers: {n}  qid {pct('qid'):.1f}%  birth_date {pct('birth_date'):.1f}%  "
                  f"birth_place {pct('birth_place'):.1f}%  country {pct('country'):.1f}%  state {pct('state'):.1f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
