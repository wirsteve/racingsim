#!/usr/bin/env python3
"""Validate nascar_touring outputs and write COVERAGE.md (adapted from ../asphalt/validate.py)."""
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
        if os.sep + "cache" + os.sep in f or os.sep + "dl_" in f:
            continue
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
    # every schedule track must appear in venues.json
    vnames = set()
    for e in venues["existing"]:
        vnames |= {norm(n) for n in e["names_seen"]}
    for e in venues["new"]:
        vnames |= {norm(n) for n in [e["name"]] + e.get("aliases", [])}
    missing_tracks = sorted({r["track"] for d in seasons.values() for r in d["schedule"] if r["track"] and norm(r["track"]) not in vnames})
    for t in missing_tracks:
        errors.append(f"schedule track not in venues.json: {t}")
    bn = json.load(open(os.path.join(BASE, "build_notes.json")))
    # coverage
    per = defaultdict(dict)
    for (k, y), d in seasons.items():
        per[k][y] = d
    lines = ["# NASCAR regional touring series + USAR Pro Cup coverage (1995–2014)", "",
             "Sources: English Wikipedia/Wikidata (champions, 1996 top-ten standings, Goody's Dash season articles), "
             "Ultimate Racing History year race lists (race dates, tracks, winners), RacingCalendar.net season calendars "
             "(complete calendars without winners), Crittenden Automotive Library (Pro Cup schedules, poles, winners 1997–2012). "
             "No racing-reference.info / thethirdturn.com data.",
             "data_level: **full** = schedule + standings; **schedule** = race list/winners only; **champion_only** = only the champion is known.",
             "", "## Summary by series", "",
             "| series | name | years present | full | schedule | champion_only | races | races with winner | standings rows | gaps (no file, within 1995–2026 span of the series) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
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
        nw = sum(1 for d in ys.values() for r in d["schedule"] if r["winner"])
        tot_w = globals().setdefault("TOTW", [0]); tot_w[0] += nw
        lines.append(f"| {k} | {m['name']} | {span[0] if span else '-'}–{span[1] if span else '-'} ({len(ys)}) | {c.get('full',0)} | {c.get('schedule',0)} | {c.get('champion_only',0)} | {nr} | {nw} | {nd} | {compress(gaps) or '—'} |")
    lines += ["", "## Notes on lineage, sources and gaps", "",
              "- **nascar_southeast** covers both the *Slim Jim All Pro Series* and the *NASCAR Southeast Series*: they are one lineage (Winston All Pro 1991–93, Slim Jim All Pro 1994–2000, Gatorade All-Pro 2001, Hills Bros. All-Pro 2002, Kodak Southeast 2003, AutoZone Elite Division Southeast 2004–06; names per RacingCalendar.net, lineage per Wikipedia). It is therefore one key, not two.",
              "- **nascar_southwest** (Featherlite Southwest Tour → Featherlite Southwest Series 1998 → AutoZone Elite Division Southwest 2004–06), **nascar_northwest** (REB-CO Northwest Tour → Raybestos Brakes Northwest Series 1998 → AutoZone Elite Division Northwest 2004–06), **nascar_midwest** (NASCAR RE/MAX Challenge Series 1998–2002 → International Truck & Engine Midwest Series 2003 → AutoZone Elite Division Midwest 2004–06). All four ended after 2006.",
              "- **nascar_midwest** now has full calendars + winners 1998–2006 (previous folder: champions only). **artgo** 1995–1997 is also re-issued here with calendars + winners (previous folder: champions only); both keys supersede the ../asphalt versions.",
              "- **nascar_autozone_elite** is the 2003–2006 umbrella: series.json lists its four divisions and each division's champion per year; its season files hold only the year-end Toyota All-Star Showdown Elite Division race at Irwindale (champion null).",
              "- **pro_cup**: 1997–2012 complete schedules with winners (Crittenden Automotive Library; cross-checked against Ultimate Racing History 1997–2002). 2001–2008 races are labelled '(Northern Division)', '(Southern Division)', '(Four Champions Championship Series)' or '(combined divisions)'; the season champion is the Four Champions playoff winner (Wikipedia CARS Tour). Division regular-season champions are not available. 2013–2014: champion only (no accessible schedule source). No Pro Cup points standings were found in any accessible source.",
              "- **nascar_dash** (Goody's Dash Series; item 8 discovery): 1997–2003 full from Wikipedia season articles; 1996 top-ten standings only; 1995 two races (partial) + champion; 2004–2011 (IPOWER Dash / ISCARS Dash Touring, no longer NASCAR-sanctioned) champion only. **nascar_sportsman** (NASCAR Sportsman Division, 1995–1996) partial race lists from URH; no champion source.",
              "- Calendars for SE/SW/NW/MW/ARTGO come from RacingCalendar.net (user-submitted, matched to race results by date ±3 days + track name, second pass ±45 days for rain dates). Winners are known only where Ultimate Racing History lists the race: SE 2003–2006 (+ a few 1995–1998), SW 2001–2006, NW 2002–2006, MW 1998–2006, ARTGO 1995–1997. SE/SW/NW 1995–2000/2001 therefore are calendars without most winners.",
              "- 1996 standings (SE, SW, NW, Dash) are Wikipedia '1996 in NASCAR' top-ten tables only (points, starts, wins, top5, top10). Other seasons of the four NASCAR regional series have no standings in any accessible source.",
              "- Track names: RacingCalendar.net uses present-day circuit names; for calendar-only rows the period name used by URH for the same circuit in the nearest season (≤6 y) is substituted. Manual fixes: " + "; ".join(f"{a} → {b}" for a, b in bn.get("track_fixes", [])) + ". The 'Suika Circuit' → Sandia Motor Speedway fix is a correction of an evident RacingCalendar.net data-entry error (event 'Sandia 125'), confidence low-medium.",
              "- Wins in standings vs schedule winners can only be compared where both exist (Dash 1997–2003).",
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
              f"- total races: {tot_r} (with winner: {globals().get('TOTW', [0])[0]}); total standings rows: {tot_d}",
              f"- every schedule track present in venues.json: {'yes' if not missing_tracks else 'NO (' + str(len(missing_tracks)) + ' missing)'}",
              f"- new venues with coordinates: {sum(1 for v in venues['new'] if v.get('lat') is not None)} / {len(venues['new'])}", ""]
    if bn.get("crosscheck"):
        lines += ["### Source cross-check (Pro Cup: Crittenden vs Ultimate Racing History)", ""] + [f"- {x}" for x in bn["crosscheck"]] + [""]
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
