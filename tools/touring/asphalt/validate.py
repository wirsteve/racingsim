#!/usr/bin/env python3
"""Validate outputs and write COVERAGE.md."""
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
KEYS = ["series", "year", "official_name", "data_level", "champion", "teams", "standings", "schedule", "sources"]
SKEYS = ["round", "date", "race", "track", "city", "state", "winner", "winner_wiki"]
STKEYS = ["pos", "name", "wiki", "points", "wins", "starts", "top5", "top10"]


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def main():
    errors, mismatches, guest_list = [], [], []
    series = json.load(open(os.path.join(BASE, "series.json")))
    venues = json.load(open(os.path.join(BASE, "venues.json")))
    drivers = json.load(open(os.path.join(BASE, "drivers.json")))
    seasons = {}
    for f in sorted(glob.glob(os.path.join(BASE, "*", "[12][0-9][0-9][0-9].json"))):
        try:
            d = json.load(open(f))
        except Exception as e:
            errors.append(f"{f}: parse error {e}"); continue
        if list(d.keys()) != KEYS:
            errors.append(f"{f}: keys {list(d.keys())}")
        for r in d["schedule"]:
            if list(r.keys()) != SKEYS:
                errors.append(f"{f}: schedule keys {list(r.keys())}"); break
        for r in d["standings"]:
            if list(r.keys()) != STKEYS:
                errors.append(f"{f}: standings keys {list(r.keys())}"); break
        if d["series"] not in series:
            errors.append(f"{f}: unknown series {d['series']}")
        seasons[(d["series"], d["year"])] = d
    # wins agreement
    checked = 0
    for (k, y), d in sorted(seasons.items()):
        pts = [r for r in d["schedule"] if r["round"] is not None]
        if not pts or not d["standings"]:
            continue
        if not all(r["winner"] for r in pts):
            continue
        if all(r["wins"] is None for r in d["standings"]):
            continue
        checked += 1
        stand_keys = {}
        for r in d["standings"]:
            stand_keys[r["wiki"] or norm(r["name"])] = r
            stand_keys.setdefault(norm(r["name"]), r)
        sw_all = Counter()
        for r in d["schedule"]:
            if not r["winner"]:
                continue
            kk = r["winner_wiki"] if r["winner_wiki"] and r["winner_wiki"] in stand_keys else norm(r["winner"])
            if kk in stand_keys:
                sw_all[id(stand_keys[kk])] += 1
        sw = Counter()
        guests = Counter()
        for r in pts:
            kk = r["winner_wiki"] if r["winner_wiki"] and r["winner_wiki"] in stand_keys else norm(r["winner"])
            if kk in stand_keys:
                sw[id(stand_keys[kk])] += 1
            else:
                guests[r["winner"]] += 1
        bad = []
        for r in d["standings"]:
            if r["wins"] is None:
                continue
            a = sw.get(id(r), 0)
            if r["wins"] not in (a, sw_all.get(id(r), 0)):
                bad.append((r["name"], a, r["wins"]))
        if guests:
            guest_list.append((k, y, sorted(guests.items())))
        if bad:
            mismatches.append((k, y, sorted(bad)))
    # coverage
    per = defaultdict(dict)
    for (k, y), d in seasons.items():
        per[k][y] = d
    lines = ["# Asphalt touring series coverage (1995–2026)", "",
             "Source: English Wikipedia (season articles, series main articles) + Wikidata. ",
             "data_level: **full** = schedule + standings; **schedule** = race list/winners only; **champion_only** = only the champion is known.",
             "", "## Summary by series", "",
             "| series | name | years present | full | schedule | champion_only | races | standings rows | gaps (no file, within 1995–2026 span of the series) |",
             "|---|---|---|---|---|---|---|---|---|"]
    tot_r = tot_d = 0
    for k, m in series.items():
        ys = per.get(k, {})
        c = Counter(d["data_level"] for d in ys.values())
        nr = sum(len(d["schedule"]) for d in ys.values())
        nd = sum(len(d["standings"]) for d in ys.values())
        tot_r += nr; tot_d += nd
        span = m.get("years") or []
        gaps = []
        if span:
            for y in range(max(1995, span[0]), min(2026, span[1]) + 1):
                if y not in ys:
                    gaps.append(y)
        lines.append(f"| {k} | {m['name']} | {span[0] if span else '-'}–{span[1] if span else '-'} ({len(ys)}) | {c.get('full',0)} | {c.get('schedule',0)} | {c.get('champion_only',0)} | {nr} | {nd} | {compress(gaps) or '—'} |")
    lines += ["", "## Notes on lineage and gaps", "",
              "- Lineages are split into separate series keys where the sanctioning body or class changed: asa (ASA National Tour, to 2004) / asa_late_model* (2003–2010) / asa_stars (2023+); artgo (to 1997) / nascar_midwest (1998–2006) / arca_midwest (ASA Midwest Tour 2007–2014, ARCA Midwest Tour 2015–2022, ASA Midwest Tour again 2023+); pro_cup (USAR Hooters Pro Cup 1997–2014) / cars_lms + cars_slm (CARS Tour 2015+; SLM became Pro Late Model in 2022); whelen_southern_modified (NASCAR, 2005–2016) / smart_modified (SMART 1995–2004 and 2021+; series dormant 2017–2020); cascar (to 2006) / pinty (NASCAR Canada, 2007+).",
              "- Busch North / K&N East 1995–2006 and 2010–2011, ARCA 1995–1997 and Whelen Modified 1995–2004 have no Wikipedia season article: champion only (from the series main article champions table).",
              "- 2007 and 2009 Busch East/Camping World East articles have only partial per-race results, so winners are partially known.",
              "- PASS, CRA, Pro Cup, ASA National Tour, ARTGO, NASCAR Midwest, CASCAR, APC United and OSCAAR exist on Wikipedia only as champions lists (plus one current-season schedule for CRA / Southern Super Series / Midwest Tour, whose winners are partly blank in the article).",
              "- Crown-jewel events (snowball_derby, winchester_400, oxford_250, slinger_nationals, all_american_400, florida_governors_cup, valleystar_300, la_crosse_oktoberfest, myrtle_beach_400, little_500) are stored as one-race 'seasons' with champion = race winner; dates only where the winners table lists them.",
              "- 2026 seasons still in progress at scrape time (2026-10-06): champion is null unless the series main article already lists a 2026 champion.",
              "- standings wins/starts/top5/top10 are computed from the Wikipedia results matrix (numeric finishing cells; DNQ/Wth/DNS not counted as starts) unless the table has explicit columns. Seasons with only a points column have wins/starts/top5/top10 = null.",
              ""]
    lines += ["", "## Per-season detail", "", "| series | year | data_level | races | winners known | standings rows | teams/cars | champion |", "|---|---|---|---|---|---|---|---|"]
    for k in series:
        for y in sorted(per.get(k, {})):
            d = per[k][y]
            nw = sum(1 for r in d["schedule"] if r["winner"])
            ncar = sum(len(t["cars"]) for t in d["teams"])
            ch = d["champion"]["name"] if d["champion"] else "—"
            lines.append(f"| {k} | {y} | {d['data_level']} | {len(d['schedule'])} | {nw} | {len(d['standings'])} | {len(d['teams'])}/{ncar} | {ch} |")
    lines += ["", "## Validation", "",
              f"- files parsed: {len(seasons)} season files, errors: {len(errors)}",
              f"- seasons where standings wins could be compared with schedule winners: {checked}; seasons with a wins-count mismatch: {len(mismatches)}; seasons with winners absent from standings: {len(guest_list)}",
              f"- venues: {len(venues['existing'])} matched to existing_tracks.json, {len(venues['new'])} new",
              f"- drivers with Wikipedia titles (drivers.json): {len(drivers)}",
              f"- total races: {tot_r}; total standings rows: {tot_d}", ""]
    if mismatches:
        lines += ["### Wins mismatches (schedule winner count vs standings wins)", "",
                  "Format: driver: schedule wins / standings wins. Usually caused by non-points races, ",
                  "results-matrix cells that the article marks differently, or name spelling differences.", ""]
        for k, y, bad in mismatches:
            lines.append(f"- {k} {y}: " + "; ".join(f"{n}: {a}/{b}" for n, a, b in bad))
    if guest_list:
        lines += ["", "### Race winners absent from that season's standings table", "",
                  "Typically guest / points-ineligible drivers (e.g. Cup regulars in combination races) or truncated top-10 standings.", ""]
        for k, y, g in guest_list:
            lines.append(f"- {k} {y}: " + "; ".join(f"{n} ({c})" for n, c in g))
    if errors:
        lines += ["", "### Errors", ""] + [f"- {e}" for e in errors]
    open(os.path.join(BASE, "COVERAGE.md"), "w").write("\n".join(lines) + "\n")
    print(f"seasons={len(seasons)} errors={len(errors)} checked={checked} mismatches={len(mismatches)} guest-seasons={len(guest_list)}")
    for k, y, bad in mismatches:
        print("  MISMATCH", k, y, bad[:6])
    for e in errors[:20]:
        print("  ERR", e)


def compress(ys):
    if not ys:
        return ""
    out, s, p = [], ys[0], ys[0]
    for y in ys[1:]:
        if y == p + 1:
            p = y; continue
        out.append(f"{s}–{p}" if s != p else str(s)); s = p = y
    out.append(f"{s}–{p}" if s != p else str(s))
    return ", ".join(out)


if __name__ == "__main__":
    main()
