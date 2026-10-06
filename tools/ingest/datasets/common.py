"""Shared helpers for the dataset ingestion scripts (stdlib + requests/pandas)."""
import json
import math
import os
import re
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
HISTORY = os.path.join(REPO, "data", "history")
EXISTING_TRACKS = os.path.join(HERE, "cache", "existing_tracks.json")
UA = "racingsim-personal/1.0 (personal non-commercial project)"
ACCESSED = "2026-10-06"


def http_get(url, dest=None, delay=2.0, params=None, headers=None, timeout=180, method="GET", data=None):
    """Polite fetch with a fixed User-Agent; caches to `dest` when given."""
    import requests
    if dest and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    h = {"User-Agent": UA}
    h.update(headers or {})
    for attempt in range(4):
        r = requests.request(method, url, params=params, data=data, headers=h, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(delay * (attempt + 2) * 5)
            continue
        r.raise_for_status()
        break
    else:
        r.raise_for_status()
    time.sleep(delay)
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
    return r


def norm(s):
    """Loose name key: ascii, lowercase, alnum only, drop suffixes."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


TRACK_STOP = {"international", "speedway", "raceway", "motor", "the", "of", "at", "park", "race", "track",
              "course", "circuit", "superspeedway", "motorsports", "motorsport", "complex", "center", "fairgrounds",
              "fairground", "county", "and", "inc", "llc", "s", "road", "oval", "dirt", "drag", "strip", "dragway"}


def track_key(s):
    return " ".join(w for w in norm(s).split() if w not in TRACK_STOP)


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = p2 - p1
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, p, indent=1):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)
        f.write("\n")


def existing_tracks_with_coords():
    """existing_tracks.json (id, name, city, region, aliases) joined to repo lat/lon in data/tracks/*.json."""
    if not os.path.exists(EXISTING_TRACKS):  # derive the list from the repo's track database
        import sys
        sys.path.insert(0, REPO)
        from racingsim.tracks.database import TrackDatabase
        os.makedirs(os.path.dirname(EXISTING_TRACKS), exist_ok=True)
        dump_json([{"id": t.id, "name": t.facts.name, "city": t.facts.city, "region": t.facts.region,
                    "aliases": t.facts.aliases} for t in TrackDatabase.load()], EXISTING_TRACKS)
    ex = load_json(EXISTING_TRACKS)
    coords = {}
    tdir = os.path.join(REPO, "data", "tracks")
    for fn in os.listdir(tdir):
        if not fn.endswith(".json"):
            continue
        for t in load_json(os.path.join(tdir, fn)):
            if t.get("lat") is None:
                continue
            for nm in [t.get("name")] + list(t.get("aliases") or []):
                coords.setdefault((norm(nm), (t.get("region") or "").upper()), (t["lat"], t["lon"]))
                coords.setdefault((norm(nm), ""), (t["lat"], t["lon"]))
    out = []
    for t in ex:
        names = [t["name"]] + list(t.get("aliases") or [])
        ll = None
        for nm in names:
            ll = coords.get((norm(nm), (t.get("region") or "").upper())) or coords.get((norm(nm), ""))
            if ll:
                break
        out.append(dict(t, lat=ll[0] if ll else None, lon=ll[1] if ll else None, _keys={track_key(n) for n in names if track_key(n)},
                        _norms={norm(n) for n in names}))
    return out


def match_existing(name, lat, lon, region, existing, max_km=2.0):
    """Return (existing_id, method, distance_km) or (None, None, None).
    Coordinate match within max_km wins (preferring a candidate whose name/alias also matches, so the
    Daytona oval is not matched to the co-located road-course entry); else exact name/alias in same region;
    else distinctive-word key match in same region."""
    n, k = norm(name), track_key(name)
    if lat is not None:
        near = []
        for t in existing:
            if t["lat"] is None:
                continue
            d = haversine_km(lat, lon, t["lat"], t["lon"])
            if d <= max_km:
                if n and n == norm(t["name"]):
                    rank = 0
                elif n and (n in t["_norms"] or bool(k and k in t["_keys"])):
                    rank = 1
                else:
                    rank = 2
                near.append((rank, d, t["id"]))
        if near:
            near.sort()  # name-confirmed candidates first, then nearest
            rank, d, tid = near[0]
            return (tid, "coords+name" if rank < 2 else "coords", round(d, 2))
    reg = (region or "").upper()
    for t in existing:
        same_reg = not reg or not t.get("region") or t["region"].upper() == reg
        if same_reg and n and n in t["_norms"]:
            return (t["id"], "name", None)
    for t in existing:
        same_reg = reg and t.get("region") and t["region"].upper() == reg
        if same_reg and k and len(k) >= 4 and k in t["_keys"]:
            return (t["id"], "name_key", None)
    return (None, None, None)


def pnorm(s):
    """Person-name key: like norm() but keeps generational suffixes (Dale Earnhardt vs Dale Earnhardt Jr.)."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())
