"""Nominatim (OpenStreetMap) gazetteer lookups with a persistent cache.

Usage policy (https://operations.osmfoundation.org/policies/nominatim/): identifying
User-Agent, <=1 request/s (we use >=2 s), results cached, no bulk systematic dumping.
Used only (a) to locate a named track that a directory/list gives without coordinates,
accepting the hit only when the OSM feature is a race-track-type object whose name matches,
and (b) to reverse-geocode city/state for records that have coordinates but no city.
Data (c) OpenStreetMap contributors, ODbL.
"""
import json
import os
import time
import urllib.parse
import urllib.request

from wp_common import RAW, UA

CACHE_P = os.path.join(RAW, "nominatim_cache.json")
_cache = json.load(open(CACHE_P)) if os.path.exists(CACHE_P) else {}
_last = [0.0]


_refusals = [0]


CACHE_ONLY = False


def _get(url):
    if url in _cache:
        return _cache[url]
    if CACHE_ONLY:
        return None
    for attempt in range(2):
        gap = time.time() - _last[0]
        if gap < 3.0:
            time.sleep(3.0 - gap)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            _refusals[0] = 0
            break
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError("nominatim refused (403) - stop")
            if e.code == 429:
                _refusals[0] += 1
                if _refusals[0] >= 3:
                    flush()
                    raise RuntimeError("nominatim rate-limited repeatedly (429) - stop")
                time.sleep(90)
                continue
            data = None
            break
    else:
        return None
    _cache[url] = data
    if len(_cache) % 10 == 0:
        flush()
    return data


def flush():
    json.dump(_cache, open(CACHE_P, "w"))


def search(q, countrycodes="us,ca,mx", limit=5):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": limit, "countrycodes": countrycodes, "addressdetails": 1})
    return _get(url) or []


def reverse(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(
        {"lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": 12, "addressdetails": 1})
    return _get(url)


TRACKISH = {("leisure", "track"), ("highway", "raceway"), ("leisure", "sports_centre"), ("leisure", "stadium"),
            ("landuse", "recreation_ground"), ("leisure", "pitch"), ("amenity", "events_venue"),
            ("leisure", "park"), ("tourism", "attraction"), ("landuse", "grass"), ("sport", "motor"),
            ("leisure", "recreation_ground"), ("amenity", "public_building"), ("place", "locality")}
STRICT_TRACK = {("leisure", "track"), ("highway", "raceway"), ("leisure", "sports_centre"), ("leisure", "stadium")}
