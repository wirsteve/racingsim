#!/usr/bin/env python3
"""Validate the generated dirt database: JSON parses, schema keys, wins vs schedule winners, champion vs standings."""
import collections, glob, json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_KEYS = ["series", "year", "official_name", "data_level", "champion", "teams", "standings", "schedule", "sources"]
SCHED_KEYS = ["round", "date", "race", "track", "city", "state", "winner", "winner_wiki"]
STAND_KEYS = ["pos", "name", "wiki", "points", "wins", "starts", "top5", "top10"]
VENUE_NEW_KEYS = ["name", "city", "region", "country", "track_type", "surface", "length_mi", "banking_deg_turns", "opened", "closed",
                  "active", "disciplines", "level", "lat", "lon", "sources", "aliases"]
problems, notes = [], []


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        problems.append(f"PARSE ERROR {p}: {e}")
        return None


files = sorted(glob.glob(os.path.join(BASE, "**", "*.json"), recursive=True))
files = [f for f in files if "/cache/" not in f]
series = load(os.path.join(BASE, "series.json")) or {}
drivers = load(os.path.join(BASE, "drivers.json")) or {}
venues = load(os.path.join(BASE, "venues.json")) or {}
races = 0
for f in files:
    d = load(f)
    if d is None:
        continue
    rel = os.path.relpath(f, BASE)
    parts = rel.split(os.sep)
    if len(parts) == 2 and parts[0] in series:
        if list(d.keys()) != SEASON_KEYS:
            problems.append(f"{rel}: keys {list(d.keys())}")
        for r in d["schedule"]:
            races += 1
            if list(r.keys()) != SCHED_KEYS:
                problems.append(f"{rel}: schedule keys {list(r.keys())}"); break
        for r in d["standings"]:
            if list(r.keys()) != STAND_KEYS:
                problems.append(f"{rel}: standings keys {list(r.keys())}"); break
        for w in [d["champion"]] if d["champion"] else []:
            if w.get("wiki") and w["wiki"] not in drivers:
                problems.append(f"{rel}: champion wiki {w['wiki']} missing from drivers.json")
        # wins vs schedule winners
        wins = collections.Counter(r["winner"] for r in d["schedule"] if r["winner"])
        complete = d["schedule"] and all(r["winner"] for r in d["schedule"])
        for s in d["standings"]:
            if s["wins"] is not None and wins:
                if wins.get(s["name"], 0) != s["wins"]:
                    (problems if complete else notes).append(
                        f"{rel}: {s['name']} standings wins={s['wins']} vs schedule winners={wins.get(s['name'], 0)}"
                        + ("" if complete else " (schedule has races without winner)"))
        if d["standings"] and d["champion"] and d["standings"][0]["name"] != d["champion"]["name"]:
            notes.append(f"{rel}: champion {d['champion']['name']} != standings P1 {d['standings'][0]['name']}")
for v in venues.get("new", []):
    if list(v.keys()) != VENUE_NEW_KEYS:
        problems.append(f"venue keys {v.get('name')}: {list(v.keys())}")
print(f"{len(files)} JSON files parsed; {races} schedule rows; {len(drivers)} drivers; venues existing={len(venues.get('existing', []))} new={len(venues.get('new', []))}")
print("PROBLEMS:", len(problems))
for p in problems:
    print("  ", p)
print("NOTES:", len(notes))
for n in notes:
    print("  ", n)
sys.exit(1 if any(p.startswith("PARSE") for p in problems) else 0)
