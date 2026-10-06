"""Cached fetch layer: Wikipedia API, Wikidata API/SPARQL only (plus robots-checked official sites)."""
import hashlib, json, os, time, urllib.parse, urllib.robotparser
import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "cache")
os.makedirs(CACHE, exist_ok=True)
UA = "racingsim-personal/1.0 (personal non-commercial project)"
S = requests.Session()
S.headers["User-Agent"] = UA
BLOCKED = ("thethirdturn.com", "racing-reference.info", "web.archive.org", "archive.org", "archive.ph", "archive.today")
_last = {}
STATS = {"fetched": 0, "backoff": 0}

def _cache_path(key):
    h = hashlib.sha1(key.encode()).hexdigest()
    return os.path.join(CACHE, h[:2], h + ".json")

def _get(url, params=None, min_gap=0.35, host="wiki"):
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    if any(b in full for b in BLOCKED):
        raise RuntimeError("blocked source: " + full)
    p = _cache_path(full)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    delay = 2.0
    import random
    for attempt in range(40):
        gap = time.time() - _last.get(host, 0)
        if gap < min_gap:
            time.sleep(min_gap - gap)
        _last[host] = time.time()
        try:
            r = S.get(url, params=params, timeout=60)
        except requests.RequestException as e:
            time.sleep(delay); delay = min(delay * 1.6, 60); continue
        if r.status_code in (429, 503, 502, 504):
            ra = r.headers.get("Retry-After")
            wait = max(float(ra) if ra and ra.replace('.', '').isdigit() else 0, delay) + random.random()
            STATS["backoff"] += 1
            time.sleep(wait); delay = min(delay * 1.6, 60); continue
        STATS["fetched"] += 1
        if r.status_code == 404:
            out = {"__status": 404}
        else:
            r.raise_for_status()
            try:
                out = r.json()
            except ValueError:
                out = {"__text": r.text}
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(out, f)
        return out
    raise RuntimeError("failed after retries: " + full)

API = "https://en.wikipedia.org/w/api.php"

def page(title):
    """Return dict(title, wikitext, oldid, url) or None. Follows redirects."""
    d = _get(API, {"action": "query", "prop": "revisions", "rvprop": "content|ids", "rvslots": "main",
                   "titles": title, "redirects": 1, "format": "json", "formatversion": 2})
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "revisions" not in pages[0]:
        return None
    pg = pages[0]; rev = pg["revisions"][0]
    t = pg["title"]
    return {"title": t, "wikitext": rev["slots"]["main"]["content"], "oldid": rev["revid"],
            "url": "https://en.wikipedia.org/w/index.php?title=%s&oldid=%d" % (urllib.parse.quote(t.replace(" ", "_")), rev["revid"])}

def resolve(titles):
    """Batch-resolve titles -> canonical title (redirect-followed) or None if missing. Max 50 per call."""
    out = {}
    titles = [t for t in dict.fromkeys(titles) if t]
    for i in range(0, len(titles), 50):
        chunk = titles[i:i+50]
        d = _get(API, {"action": "query", "titles": "|".join(chunk), "redirects": 1, "format": "json", "formatversion": 2,
                       "prop": "pageprops", "ppprop": "wikibase_item|disambiguation"})
        q = d.get("query", {})
        m = {}
        for n in q.get("normalized", []): m[n["from"]] = n["to"]
        rd = {}
        for n in q.get("redirects", []): rd[n["from"]] = n["to"]
        info = {}
        for pg in q.get("pages", []):
            info[pg["title"]] = None if pg.get("missing") or pg.get("invalid") else {
                "qid": pg.get("pageprops", {}).get("wikibase_item"), "disambig": "disambiguation" in pg.get("pageprops", {})}
        for t in chunk:
            x = m.get(t, t); x = rd.get(x, x); x = m.get(x, x)
            inf = info.get(x)
            out[t] = (x, inf) if inf else (None, None)
    return out

def search(q, limit=20):
    d = _get(API, {"action": "query", "list": "search", "srsearch": q, "srlimit": limit, "format": "json", "formatversion": 2})
    return [x["title"] for x in d.get("query", {}).get("search", [])]

def prefix(p, limit=100):
    d = _get(API, {"action": "query", "list": "allpages", "apprefix": p, "aplimit": limit, "format": "json", "formatversion": 2})
    return [x["title"] for x in d.get("query", {}).get("allpages", [])]

def category(cat, limit=500):
    d = _get(API, {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": limit, "format": "json", "formatversion": 2})
    return [x["title"] for x in d.get("query", {}).get("categorymembers", [])]

def wd_entities(qids, props="claims|labels|sitelinks"):
    out = {}
    qids = [q for q in dict.fromkeys(qids) if q]
    for i in range(0, len(qids), 50):
        d = _get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(qids[i:i+50]),
                 "props": props, "languages": "en", "sitefilter": "enwiki", "format": "json"}, host="wd")
        out.update(d.get("entities", {}))
    return out

_robots = {}
def official_get(url):
    """Fetch an official site page only if robots.txt permits; >=2s between requests."""
    pu = urllib.parse.urlparse(url)
    root = "%s://%s" % (pu.scheme, pu.netloc)
    if root not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(root + "/robots.txt", timeout=30)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            if r.status_code in (401, 403): rp.disallow_all = True
        except requests.RequestException:
            rp.disallow_all = True
        _robots[root] = rp
        time.sleep(2)
    if not _robots[root].can_fetch(UA, url):
        raise RuntimeError("robots disallow " + url)
    cd = _robots[root].crawl_delay(UA) or 0
    ROBOTS_LOG[root] = "allowed (crawl-delay %s)" % cd if cd else "allowed"
    return _get(url, min_gap=max(2.0, float(cd)), host=pu.netloc)

ROBOTS_LOG = {}


def _ensure(p):
    os.makedirs(os.path.dirname(p), exist_ok=True); return p

def _page_params(title):
    return {"action": "query", "prop": "revisions", "rvprop": "content|ids", "rvslots": "main",
            "titles": title, "redirects": 1, "format": "json", "formatversion": 2}

def _page_key(title):
    return API + "?" + urllib.parse.urlencode(_page_params(title))

def pages(titles):
    """Bulk page(): up to 20 titles per request; seeds the per-title cache used by page()."""
    res, todo = {}, []
    for t in dict.fromkeys(t for t in titles if t):
        if os.path.exists(_cache_path(_page_key(t))):
            res[t] = page(t)
        else:
            todo.append(t)
    for i in range(0, len(todo), 20):
        chunk = todo[i:i+20]
        d = _get(API, {"action": "query", "prop": "revisions", "rvprop": "content|ids", "rvslots": "main",
                       "titles": "|".join(chunk), "redirects": 1, "format": "json", "formatversion": 2})
        q = d.get("query", {})
        m = {n["from"]: n["to"] for n in q.get("normalized", [])}
        rd = {n["from"]: n["to"] for n in q.get("redirects", [])}
        byt = {pg["title"]: pg for pg in q.get("pages", [])}
        for t in chunk:
            x = m.get(t, t); x = rd.get(x, x); x = m.get(x, x)
            pg = byt.get(x)
            ok = pg and not pg.get("missing") and pg.get("revisions") and "slots" in pg["revisions"][0] \
                and "content" in pg["revisions"][0]["slots"].get("main", {})
            if ok or (pg and (pg.get("missing") or pg.get("invalid"))):
                with open(_ensure(_cache_path(_page_key(t))), "w") as f:
                    json.dump({"query": {"pages": [pg]}}, f)
                res[t] = page(t)
            else:
                res[t] = page(t)
    return res
