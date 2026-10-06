"""Ingest nascaR.data (Kyle Grealis, GPL-3; data curated with permission from DriverAverages.com).

Source files (public Cloudflare R2, documented in the package vignette "ingesting-nascar-data"):
  https://nascar.kylegrealis.com/{cup,nxs,truck}_series.parquet   (the .csv URLs listed in the docs 404 as of 2026-10-06)

Output: results/nascardata_<series>/<year>.json in the knowledge-layer race-by-race format.
Date/city/state are not in nascaR.data; they are joined from the repo's history schedules
(data/history/nascar_*/<year>.json, Wikipedia-derived) when the round/track/winner line up.

Also writes validation_nascar_data.json comparing winners and season stats with the repo history.

Usage: python3 ingest_nascar_data.py [--refresh]
"""
import collections
import os
import re
import sys

import pandas as pd

from common import CACHE, HERE, HISTORY, ACCESSED, EXISTING_TRACKS, http_get, norm, pnorm, track_key, load_json, dump_json

BASE = "https://nascar.kylegrealis.com/{}_series.parquet"
US_STATE_NAMES = {"Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
                  "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
                  "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
                  "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
                  "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
                  "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "Ontario", "Quebec",
                  "British Columbia", "Alberta", "Manitoba", "Saskatchewan", "Nova Scotia", "New Brunswick"}
SERIES = {
    # nascaR.data key: (output source_key, repo history dir, our series id)
    "cup": ("nascardata_cup", "nascar_cup", "cup_series"),
    "nxs": ("nascardata_nxs", "nascar_xfinity", "stock_national"),
    "truck": ("nascardata_truck", "nascar_trucks", "truck_series"),
}


def fnum(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def sval(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return None if s in ("", "-", "NA", "nan") else s


def load(series, refresh=False):
    dest = os.path.join(CACHE, "nascar_data", f"{series}_series.parquet")
    if refresh and os.path.exists(dest):
        os.remove(dest)
    http_get(BASE.format(series), dest=dest, delay=2.0)
    df = pd.read_parquet(dest)
    df["Car"] = df["Car"].astype("string")
    return df


def repo_history(hdir):
    out = {}
    d = os.path.join(HISTORY, hdir)
    for fn in os.listdir(d):
        if fn.endswith(".json"):
            h = load_json(os.path.join(d, fn))
            out[int(h["year"])] = h
    return out


def build_track_places(hist):
    """exact normalized track name -> (city, state) from repo schedules, then unambiguous fallbacks."""
    places = {}
    for h in hist.values():
        for r in h.get("schedule", []):
            if r.get("track") and r.get("city"):
                places.setdefault(norm(r["track"]), (r.get("city"), r.get("state")))
    # fallbacks for venues absent from 1995+ schedules (1950s-80s tracks): existing_tracks.json, then Wikidata
    # racetrack items (run ingest_wikidata_tracks.py first). Used only when the name key is unambiguous
    # (e.g. several "Tri-City Speedway"s exist), and a Wikidata P131 that is a county/state gives state only.
    cands = collections.defaultdict(set)
    for t in load_json(EXISTING_TRACKS):
        if len(t.get("region") or "") == 2:
            for nm in [t["name"]] + list(t.get("aliases") or []):
                cands[norm(nm)].add((t.get("city"), t.get("region")))
    wd = os.path.join(HERE, "tracks_wikidata.json")
    if os.path.exists(wd):
        for t in load_json(wd)["tracks"]:
            if t.get("state"):
                city = (t.get("admin_area") or [None])[0]
                if city and (re.search(r"County|Parish|Township|Province|State", city) or len(city.split()) > 3
                             or city in US_STATE_NAMES):
                    city = None
                cands[norm(t["name"])].add((city, t["state"]))
    for k, v in cands.items():
        states = {st for _, st in v}
        if k and k not in places and len(states) == 1:
            cities = {c for c, _ in v if c}
            places[k] = (cities.pop() if len(cities) == 1 else None, states.pop())
    return places


# Period/sponsor names -> canonical venue (facts mirrored from racingsim/history/db.py ALIASES plus a few extras).
CANON = {
    "sears point": "sonoma", "infineon": "sonoma", "sonoma": "sonoma",
    "lowe s motor speedway": "charlotte", "lowes motor speedway": "charlotte", "charlotte motor speedway": "charlotte",
    "north carolina motor speedway": "rockingham", "north carolina speedway": "rockingham", "rockingham": "rockingham",
    "phoenix": "phoenix", "ism raceway": "phoenix",
    "dover": "dover", "new hampshire": "new hampshire", "richmond": "richmond",
    "gateway": "gateway", "world wide technology": "gateway",
    "auto club speedway": "fontana", "california speedway": "fontana",
    "echopark": "atlanta ms", "atlanta motor speedway": "atlanta ms",
    "homestead": "homestead", "miami dade": "homestead",
    "o reilly raceway park": "irp", "lucas oil raceway": "irp", "indianapolis raceway park": "irp",
    "lucas oil indianapolis raceway park": "irp",
    "rambi": "myrtle beach", "myrtle beach": "myrtle beach",
    "coronado": "coronado", "san diego": "coronado", "qualcomm circuit": "coronado",
    "nashville speedway usa": "nashville fairgrounds", "fairgrounds speedway": "nashville fairgrounds",
    "pikes peak": "ppir", "memphis": "memphis", "mosport": "mosport", "canadian tire motorsport park": "mosport",
    "michigan": "michigan", "bristol": "bristol", "watkins glen": "watkins glen", "pocono": "pocono",
    "milwaukee": "milwaukee", "wisconsin state fair": "milwaukee",
}


def canon(name):
    n = norm(name)
    for k in sorted(CANON, key=len, reverse=True):
        if k in n:
            return CANON[k]
    return None


def same_track(a, b):
    ca, cb = canon(a), canon(b)
    if ca or cb:
        if ca == cb:
            return True
        if ca and cb:
            return False
    ka, kb = set(track_key(a).split()), set(track_key(b).split())
    return bool(ka & kb) or norm(a) == norm(b)


def same_person(a, b):
    """Name variants such as 'Gio Ruggiero' / 'Giovanni Ruggiero': same surname and same first initial."""
    suf = {"jr", "sr", "ii", "iii", "iv"}
    x, y = pnorm(a).split(), pnorm(b).split()
    if (set(x) & suf) and (set(y) & suf) and (set(x) & suf) != (set(y) & suf):
        return False  # Sr. vs Jr. are different people
    x, y = [w for w in x if w not in suf], [w for w in y if w not in suf]
    return bool(x and y) and x[-1] == y[-1] and x[0][0] == y[0][0]


def align(races, schedule):
    """Map nascaR.data race number -> repo schedule entry (or None)."""
    sched = [r for r in schedule if not r.get("cancelled")]
    mapping = {}
    used = set()
    # pass 1: same index with same track
    for rnd, info in races.items():
        i = rnd - 1
        if 0 <= i < len(sched) and same_track(info["track"], sched[i].get("track", "")):
            mapping[rnd] = sched[i]
            used.add(i)
    # pass 2: nearest unused schedule entry with same track and same winner, else same track within +-3
    for rnd, info in races.items():
        if rnd in mapping:
            continue
        cands = [j for j, s in enumerate(sched) if j not in used and same_track(info["track"], s.get("track", ""))]
        win = [j for j in cands if pnorm(sched[j].get("winner")) == pnorm(info["winner"])]
        pick = (win or [j for j in cands if abs(j - (rnd - 1)) <= 3] or [None])[0]
        if pick is not None:
            mapping[rnd] = sched[pick]
            used.add(pick)
    return mapping


def main():
    refresh = "--refresh" in sys.argv
    validation = {"source": "src:nascar-data", "accessed": ACCESSED, "series": {}}
    for key, (skey, hdir, sid) in SERIES.items():
        df = load(key, refresh)
        hist = repo_history(hdir)
        places = build_track_places(hist)
        v = collections.Counter()
        mism = []
        stat_checks = collections.Counter()
        for year, ydf in df.groupby("Season"):
            year = int(year)
            races = {}
            for rnd, rdf in ydf.groupby("Race"):
                rdf = rdf.sort_values("Finish")
                w = rdf[rdf["Finish"] == 1]
                races[int(rnd)] = {"df": rdf, "track": str(rdf["Track"].iloc[0]),
                                   "winner": str(w["Driver"].iloc[0]) if len(w) else None}
            h = hist.get(year)
            mapping = align(races, h["schedule"]) if h else {}
            out_races = []
            for rnd in sorted(races):
                info = races[rnd]
                rdf = info["df"]
                s = mapping.get(rnd)
                place = places.get(norm(info["track"]), (None, None))
                results = []
                for row in rdf.itertuples(index=False):
                    results.append({
                        "pos": fnum(row.Finish), "start": fnum(row.Start), "driver": sval(row.Driver),
                        "car_number": sval(row.Car), "team": sval(row.Team), "manufacturer": sval(row.Make),
                        "laps": fnum(row.Laps), "status": sval(row.Status), "points": fnum(row.Pts),
                        "led": fnum(row.Led),
                    })
                out_races.append({
                    "round": rnd,
                    "date": s.get("date") if s else None,
                    "race": s.get("race") if s else sval(rdf["Name"].iloc[0]),
                    "race_name_source": sval(rdf["Name"].iloc[0]),
                    "track": info["track"],
                    "track_length_mi": fnum(rdf["Length"].iloc[0]),
                    "surface": sval(rdf["Surface"].iloc[0]),
                    "city": s.get("city") if s else place[0],
                    "state": s.get("state") if s else place[1],
                    "repo_schedule_match": bool(s),
                    "results": results,
                })
                # validation: winner agreement
                if h:
                    v["races_with_repo_year"] += 1
                    if s:
                        v["aligned"] += 1
                        if s.get("winner"):
                            v["winner_compared"] += 1
                            if pnorm(s["winner"]) == pnorm(info["winner"]):
                                v["winner_agree"] += 1
                            elif same_person(s["winner"], info["winner"]):
                                v["winner_agree"] += 1
                                v["winner_agree_name_variant"] += 1
                            else:
                                mism.append({"year": year, "round": rnd, "track": info["track"],
                                             "nascar_data": info["winner"], "repo": s["winner"]})
            if h:
                v["repo_schedule_entries"] += len([r for r in h["schedule"] if not r.get("cancelled") and r.get("winner")])
                # season stat checks against repo standings (wins/starts/top5/top10 for top 10 of standings)
                agg = collections.defaultdict(lambda: collections.Counter())
                for row in ydf.itertuples(index=False):
                    a = agg[pnorm(row.Driver)]
                    a["starts"] += 1
                    a["wins"] += int(row.Finish == 1)
                    a["top5"] += int(row.Finish <= 5)
                    a["top10"] += int(row.Finish <= 10)
                for st in h.get("standings", [])[:10]:
                    a = agg.get(pnorm(st.get("name")))
                    if a is None:
                        stat_checks["driver_missing"] += 1
                        continue
                    for f in ("wins", "starts", "top5", "top10"):
                        if st.get(f) is not None:
                            stat_checks[f + "_compared"] += 1
                            stat_checks[f + "_agree"] += int(a[f] == st[f])
                            if a[f] != st[f]:
                                stat_checks[f + "_abs_diff_sum"] += abs(a[f] - st[f])
            dump_json({"series": sid, "source_key": skey, "source": "src:nascar-data", "year": year,
                       "license": "GPL-3 (nascaR.data); underlying data curated with permission from DriverAverages.com",
                       "notes": "date/city/state/race joined from repo history schedule when repo_schedule_match is true; points are as recorded by the source (incl. stage points era)",
                       "races": out_races},
                      os.path.join(HERE, "results", skey, f"{year}.json"), indent=None)
        rate = lambda a, b: round(v[a] / v[b], 4) if v[b] else None
        validation["series"][key] = {
            "rows": int(len(df)), "seasons": [int(df.Season.min()), int(df.Season.max())],
            "races": int(df.groupby(["Season", "Race"]).ngroups),
            "overlap_races": v["races_with_repo_year"], "aligned_to_repo_schedule": v["aligned"],
            "repo_schedule_entries_with_winner": v["repo_schedule_entries"],
            "winner_compared": v["winner_compared"], "winner_agree": v["winner_agree"],
            "winner_agree_name_variant": v["winner_agree_name_variant"],
            "winner_agreement_rate": rate("winner_agree", "winner_compared"),
            "alignment_rate": rate("aligned", "races_with_repo_year"),
            "season_stat_checks_top10_drivers": dict(stat_checks),
            "winner_mismatches": mism[:60], "winner_mismatch_count": len(mism),
        }
        print(key, {k: validation["series"][key][k] for k in ("races", "aligned_to_repo_schedule", "winner_compared", "winner_agreement_rate")})
    dump_json(validation, os.path.join(HERE, "validation_nascar_data.json"))


if __name__ == "__main__":
    main()
