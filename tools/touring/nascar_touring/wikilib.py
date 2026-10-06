"""Cached, polite Wikipedia / Wikidata access (stdlib + requests)."""
import hashlib, json, os, time, requests

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
os.makedirs(CACHE, exist_ok=True)
UA = "racingsim-personal/1.0 (personal non-commercial project)"
WP_API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
S = requests.Session()
S.headers["User-Agent"] = UA
_last = {"t": 0.0}
MIN_GAP = 0.6


def _key(url, params):
    s = url + "?" + json.dumps(params, sort_keys=True)
    return os.path.join(CACHE, hashlib.sha1(s.encode()).hexdigest() + ".json")


def get_json(url, params, gap=MIN_GAP, refresh=False):
    path = _key(url, params)
    if not refresh and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    delay = 5
    for attempt in range(8):
        wait = gap - (time.time() - _last["t"])
        if wait > 0:
            time.sleep(wait)
        _last["t"] = time.time()
        try:
            r = S.get(url, params=params, timeout=60)
        except requests.RequestException as e:
            print("  net err", e); time.sleep(delay); delay *= 2; continue
        if r.status_code in (429, 503):
            ra = r.headers.get("Retry-After")
            w = int(ra) if ra and ra.isdigit() else delay
            print(f"  HTTP {r.status_code}, backing off {w}s"); time.sleep(w); delay = min(delay * 2, 120); continue
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
            time.sleep(delay); delay *= 2; continue
        with open(path, "w") as f:
            json.dump(data, f)
        return data
    raise RuntimeError("failed " + url)


def wp(params, **kw):
    p = {"format": "json", "formatversion": "2", "maxlag": "5"}
    p.update(params)
    return get_json(WP_API, p, **kw)


def category_members(cat, ns=None):
    out, cont = [], {}
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": "500"}
        if ns is not None:
            p["cmnamespace"] = str(ns)
        p.update(cont)
        d = wp(p)
        out += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" in d:
            cont = {"cmcontinue": d["continue"]["cmcontinue"]}
        else:
            return out


def _page_path(t):
    return os.path.join(PAGE_DIR, hashlib.sha1(t.encode()).hexdigest() + ".json")


def pages(titles):
    """Return {requested_title: {"title", "revid", "text"} or None} following redirects. Per-title cache."""
    res = {}
    titles = [t for t in dict.fromkeys(titles) if t]
    todo = []
    for t in titles:
        p = _page_path(t)
        if os.path.exists(p):
            with open(p) as f:
                res[t] = json.load(f)
        else:
            todo.append(t)
    for i in range(0, len(todo), 20):
        chunk = todo[i:i + 20]
        d = wp({"action": "query", "prop": "revisions", "rvprop": "ids|content", "rvslots": "main",
                "titles": "|".join(chunk), "redirects": "1"})
        q = d.get("query", {})
        mp = {t: t for t in chunk}
        for n in q.get("normalized", []):
            for k, v in mp.items():
                if v == n["from"]:
                    mp[k] = n["to"]
        for rd in q.get("redirects", []):
            for k, v in mp.items():
                if v == rd["from"]:
                    mp[k] = rd["to"]
        bytitle = {}
        for pg in q.get("pages", []):
            if pg.get("missing") or "revisions" not in pg:
                bytitle[pg["title"]] = None
            else:
                rv = pg["revisions"][0]
                bytitle[pg["title"]] = {"title": pg["title"], "revid": rv["revid"],
                                        "text": rv["slots"]["main"]["content"]}
        for k, v in mp.items():
            res[k] = bytitle.get(v)
            with open(_page_path(k), "w") as f:
                json.dump(res[k], f)
    return res


def page(title):
    return pages([title])[title]


RESOLVE_MAP = os.path.join(CACHE, "resolve_map.json")
PAGE_DIR = os.path.join(CACHE, "pages")
os.makedirs(PAGE_DIR, exist_ok=True)


def _load_map():
    if os.path.exists(RESOLVE_MAP):
        with open(RESOLVE_MAP) as f:
            return json.load(f)
    return {}


def _save_map(m):
    tmp = RESOLVE_MAP + ".tmp"
    with open(tmp, "w") as f:
        json.dump(m, f)
    os.replace(tmp, RESOLVE_MAP)


def _ingest(m, q):
    info = {}
    for pg in q.get("pages", []):
        if pg.get("missing") or pg.get("invalid"):
            info[pg["title"]] = None
        else:
            pp = pg.get("pageprops", {})
            info[pg["title"]] = {"title": pg["title"], "qid": pp.get("wikibase_item"),
                                 "disambig": "disambiguation" in pp}
    for t, v in info.items():
        m[t] = v
    red = {r["from"]: r["to"] for r in q.get("redirects", [])}
    for f, t in red.items():
        if t in info:
            m[f] = info[t]
    for n in q.get("normalized", []):
        to = n["to"]
        to = red.get(to, to)
        if to in info:
            m[n["from"]] = info[to]


def seed_resolve_map():
    """Rebuild title map from cached pageprops responses (makes resolve() independent of batch layout)."""
    m = _load_map()
    for fn in os.listdir(CACHE):
        if not fn.endswith(".json") or fn == "resolve_map.json":
            continue
        try:
            with open(os.path.join(CACHE, fn)) as f:
                d = json.load(f)
        except Exception:
            continue
        q = d.get("query") if isinstance(d, dict) else None
        if q and q.get("pages") and all("revisions" not in p for p in q["pages"]) and any("pageprops" in p or p.get("missing") for p in q["pages"]):
            _ingest(m, q)
    _save_map(m)
    return m


def resolve(titles):
    """Map titles -> {"title","qid","disambig"} (after redirects) or None if missing. Per-title cache."""
    m = _load_map()
    titles = [t for t in dict.fromkeys(titles) if t]
    todo = [t for t in titles if t not in m]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        d = wp({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item|disambiguation",
                "titles": "|".join(chunk), "redirects": "1"})
        q = d.get("query", {})
        _ingest(m, q)
        for t in chunk:
            m.setdefault(t, None)
        _save_map(m)
    return {t: m.get(t) for t in titles}


def oldid_url(title, revid):
    from urllib.parse import quote
    return f"https://en.wikipedia.org/w/index.php?title={quote(title.replace(' ', '_'))}&oldid={revid}"


def wd_entities(qids, props="claims|labels|sitelinks"):
    out = {}
    qids = [q for q in dict.fromkeys(qids) if q]
    for i in range(0, len(qids), 50):
        d = get_json(WD_API, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": props,
                              "languages": "en", "sitefilter": "enwiki", "format": "json"})
        out.update(d.get("entities", {}))
    return out


def seed_page_cache():
    n = 0
    for fn in os.listdir(CACHE):
        if not fn.endswith(".json") or fn == "resolve_map.json":
            continue
        try:
            with open(os.path.join(CACHE, fn)) as f:
                d = json.load(f)
        except Exception:
            continue
        q = d.get("query") if isinstance(d, dict) else None
        if not q or not q.get("pages") or not any("revisions" in p for p in q["pages"]):
            continue
        info = {}
        for pg in q["pages"]:
            if pg.get("missing") or "revisions" not in pg:
                info[pg["title"]] = None
            else:
                rv = pg["revisions"][0]
                info[pg["title"]] = {"title": pg["title"], "revid": rv["revid"], "text": rv["slots"]["main"]["content"]}
        keys = dict((t, t) for t in info)
        red = {r["from"]: r["to"] for r in q.get("redirects", [])}
        for f_, t in red.items():
            keys[f_] = t
        for nn in q.get("normalized", []):
            keys[nn["from"]] = red.get(nn["to"], nn["to"])
        for k, t in keys.items():
            if t in info:
                p = _page_path(k)
                if not os.path.exists(p):
                    with open(p, "w") as f:
                        json.dump(info[t], f)
                    n += 1
    return n
