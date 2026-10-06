"""Champion lists from official series websites (robots.txt checked by wiki.official_get, >=2 s / crawl-delay between requests).
Only short factual year->champion lists are extracted; no prose is stored."""
import html, re
import wiki

PAGES = {
    "usmts": "https://www.usmts.com/past-champions/",
    "stss": "https://www.shorttracksuperseries.com/champions/",
    "mars": "https://www.marsracingseries.com/champions/",
    "ascs": "https://ascsracing.com/about/series-champions/",
}


def lines(url):
    d = wiki.official_get(url)
    t = d.get("__text", "")
    t = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", t)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    return [re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()]


def _name(s):
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)
    s = re.split(r",\s*(?!Jr|Sr|II|III)", s)[0]
    return re.sub(r"\s+", " ", s).strip(" -–")


def year_dash(ls, header_re):
    """'2024 - Name, City, ST' (or '(City, ST)') lines following a header line."""
    out, inside = [], False
    for l in ls:
        if re.search(header_re, l, re.I) and not re.search(r"rookie", l, re.I):
            if out:
                break
            inside = True; continue
        if inside:
            m = re.match(r"^(\d{4})\s*[-–:]\s*(.+)$", l)
            if m:
                note = re.findall(r"\(([^)]*)\)", m.group(2))
                out.append({"year": int(m.group(1)), "name": _name(m.group(2)), "wiki": None, "note": note[-1] if note else None})
            elif out:
                break
    return out


def year_blocks(ls, start_re=None):
    """'2023' line followed by 'Name (Division)' / 'Series Champion: Name' lines."""
    out, year, started = [], None, start_re is None
    for l in ls:
        if not started:
            if re.search(start_re, l, re.I):
                started = True
            continue
        if re.fullmatch(r"(19|20)\d\d", l):
            year = int(l); continue
        if year is None:
            continue
        m = re.match(r"^Series Champion:\s*(.+)$", l)
        if m:
            out.append({"year": year, "name": _name(m.group(1)), "wiki": None, "note": "Series Champion"}); continue
        m = re.match(r"^([A-Z][^()]{2,40}?)\s*\(([^)]*)\)\s*$", l)
        if m:
            out.append({"year": year, "name": m.group(1).strip(), "wiki": None, "note": m.group(2)}); continue
        if re.match(r"^(Rookie|Upcoming|Driver Registration|Schedule)", l):
            if l.startswith("Rookie"):
                continue
            year = None
            if out:
                break
    return out


def champions(key):
    if key == "usmts":
        return year_dash(lines(PAGES["usmts"]), r"^Past Champions$")
    if key in ("mars_late_model", "mars_modified"):
        hdr = r"^MARS Late Model.*Past Champions" if key == "mars_late_model" else r"^MARS Modified.*Past Champions"
        rows = year_dash(lines(PAGES["mars"]), hdr)
        # years with split (East/West) titles have no single champion
        cnt = {}
        for r in rows:
            cnt[r["year"]] = cnt.get(r["year"], 0) + 1
        return [r for r in rows if cnt[r["year"]] == 1]
    if key == "ascs":
        return year_blocks(lines(PAGES["ascs"]), r"Past\s+Series Champions")
    if key.startswith("stss"):
        rows = year_blocks(lines(PAGES["stss"]), r"Champions")
        want = {"stss": ("overall", "elite", "one series"), "stss_north": ("north",), "stss_south": ("south",)}[key]
        out = []
        for r in rows:
            n = (r["note"] or "").lower()
            if any(n == w or n.startswith(w) for w in want) and "sportsman" not in n:
                if not any(o["year"] == r["year"] for o in out):
                    out.append(r)
        return out
    raise KeyError(key)


# ---------------------------------------------------------------- MyRacePass-hosted series schedules (date / track / event name only)
MRP = {
    "lolmds": "https://www.lucasdirt.com",
    "usmts": "https://www.usmts.com",
    "stss": "https://www.shorttracksuperseries.com",
    "mars_late_model": "https://www.marsracingseries.com",
    "high_limit": "https://www.highlimitracing.com",
}
CARD = re.compile(r'<div class="mrp-rowCard">(.*?)<div class="mrp-rowCardAction">(.*?)</div>', re.S)


def mrp_years(key):
    d = wiki.official_get(MRP[key] + "/schedules/")
    return sorted({int(y) for y in re.findall(r'href="/schedules/(\d{4})"', d.get("__text", ""))})


def mrp_schedule(key, year):
    url = MRP[key] + "/schedules/%d" % year
    d = wiki.official_get(url)
    t = d.get("__text", "")
    out = []
    for m in CARD.finditer(t):
        body, action = m.group(1), m.group(2)
        dm = re.search(r'<p class="text-muted text-uppercase">([^<]+)</p>', body)
        tm = re.search(r"<h3>(?:<a[^>]*>)?([^<]+)", body)
        em = re.search(r'</h3>\s*<p class="text-muted">([^<]*)</p>', body)
        st = re.sub(r"<[^>]+>", " ", action)
        st = re.sub(r"\s+", " ", html.unescape(st)).strip()
        out.append({"date": html.unescape(dm.group(1)).strip() if dm else None,
                    "track": html.unescape(tm.group(1)).strip() if tm else None,
                    "race": html.unescape(em.group(1)).strip() if em else None,
                    "status": st})
    return url, out
