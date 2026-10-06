"""Shared helpers for the track census (Wikipedia / Wikidata API access).

Polite access: identifying User-Agent, >=0.3 s between requests, back-off on 429/5xx.
"""
import json
import os
import time
import urllib.parse
import urllib.request

UA = "racingsim-personal/1.0 (personal non-commercial project)"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)

_last = [0.0]


def _get(url, accept="application/json", min_gap=0.35, tries=6):
    for attempt in range(tries):
        gap = time.time() - _last[0]
        if gap < min_gap:
            time.sleep(min_gap - gap)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                wait = int(e.headers.get("Retry-After") or (5 * (attempt + 1)))
                print(f"  HTTP {e.code}, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:  # network hiccup
            print("  error", e, flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("failed " + url)


def wp_api(params, lang="en"):
    p = dict(params)
    p.setdefault("format", "json")
    p.setdefault("formatversion", "2")
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p)
    return json.loads(_get(url))


def wp_api_all(params, cont_key="continue"):
    """Iterate over continued API results."""
    p = dict(params)
    while True:
        d = wp_api(p)
        yield d
        if "continue" not in d:
            break
        p.update(d["continue"])


def sparql(query):
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query})
    return json.loads(_get(url, accept="application/sparql-results+json", min_gap=1.0))


def save(name, obj):
    with open(os.path.join(RAW, name), "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def load(name):
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)
