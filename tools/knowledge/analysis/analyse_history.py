#!/usr/bin/env python3
"""Career-economics evidence computed from the racingsim historical season files.

Read-only over /home/user/racingsim/data/history (or a path given as argv[1]).
Writes computed_evidence.json next to this script (or argv[2]).

Pure standard library (no numpy).  Cite results as src:racingsim-history-analysis.

Definitions used throughout
---------------------------
* driver key  = Wikipedia title from the standings row, else "name:<lowercased name>".
* season length = max(starts) among that season's standings rows.
* full-time (FT) = starts >= 0.70 * season length (season length >= 4).
* championship rank = position among *eligible* drivers (NASCAR "eligible" flag; from
  2011 Cup regulars are not eligible for Xfinity/Truck points).
* ladders (game tiers in brackets):
    open wheel: usf2000 [3] -> pro_mazda [4] -> indy_lights [5] -> top [7] (irl_indycar + cart_champcar)
    stock car : nascar_trucks [5] -> nascar_xfinity [6] -> nascar_cup [7]
* "advance" = FT in a higher rung of the same ladder (skipping allowed) within k seasons.
* age = season year - birth year (approx. age on 1 July).
* 2026 seasons are partial (data captured Oct 2026); FT status in 2026 is relative to
  races run so far.  Cohorts whose k-year window would run past 2026 are dropped.
"""
import json, glob, os, re, sys, math, statistics, collections
from datetime import date

HIST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "history")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "computed_evidence.json")
LAST_YEAR = 2026
FT_SHARE = 0.70

SERIES = {
    "usf2000":        {"ladder": "open_wheel", "rung": 1, "tier": 3, "label": "USF2000"},
    "pro_mazda":      {"ladder": "open_wheel", "rung": 2, "tier": 4, "label": "Star Mazda / Pro Mazda / Indy Pro 2000 / USF Pro 2000"},
    "indy_lights":    {"ladder": "open_wheel", "rung": 3, "tier": 5, "label": "Indy Lights / Infiniti Pro / Indy NXT"},
    "irl_indycar":    {"ladder": "open_wheel", "rung": 4, "tier": 7, "label": "IRL / IndyCar"},
    "cart_champcar":  {"ladder": "open_wheel", "rung": 4, "tier": 7, "label": "CART / Champ Car"},
    "nascar_trucks":  {"ladder": "stock_car", "rung": 1, "tier": 5, "label": "NASCAR Truck Series"},
    "nascar_xfinity": {"ladder": "stock_car", "rung": 2, "tier": 6, "label": "NASCAR Busch/Nationwide/Xfinity/O'Reilly Series"},
    "nascar_cup":     {"ladder": "stock_car", "rung": 3, "tier": 7, "label": "NASCAR Cup Series"},
}
LOWER_SERIES = ["usf2000", "pro_mazda", "indy_lights", "nascar_trucks", "nascar_xfinity"]

# Organisations that fielded Cup cars or are formal Cup-team satellites / development arms.
# Used only for the "connected team" proxy (manual list, low-medium confidence).
CUP_AFFILIATES = [
    "hendrick", "jr motorsports", "joe gibbs", "gibbs", "roush", "childress", "kevin harvick", "harvick",
    "penske", "keselowski", "kyle busch", "stewart haas", "stewarthaas", "ganassi", "dale earnhardt",
    "evernham", "michael waltrip", "red bull", "bill davis", "petty", "germain", "front row", "spire",
    "gms racing", "trackhouse", "23xi", "legacy motor", "richard petty", "wood brothers", "robert yates",
    "yates", "ricky rudd", "rcr", "dei", "jtg", "furniture row", "hscott", "turner scott", "turner motorsports",
    "team menard", "pettyfamily", "rfk", "chip ganassi", "kaulig", "halmar", "hattori", "dgr", "david gilliland",
]


def norm_team(name):
    s = (name or "").lower()
    s = re.sub(r"[–—\-/&.,']", " ", s)
    s = re.sub(r"\b(racing|motorsports|motorsport|inc|llc|enterprises|team|autosport|racing development)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def dkey(row):
    w = row.get("wiki")
    return w if w else "name:" + (row.get("name") or "").strip().lower()


# ---------------------------------------------------------------- loading
def load():
    births = {}
    for f in glob.glob(os.path.join(HIST, "drivers*.json")):
        for k, v in json.load(open(f)).items():
            bd = (v or {}).get("birth_date")
            if bd and re.match(r"^\d{4}", bd) and k not in births:
                births[k] = int(bd[:4])
    seasons = {}   # (series, year) -> dict
    for s in SERIES:
        for f in sorted(glob.glob(os.path.join(HIST, s, "*.json"))):
            d = json.load(open(f))
            y = int(d.get("year") or os.path.basename(f)[:4])
            rows = d.get("standings") or []
            champion_only = d.get("data_level") == "champion_only" or all(r.get("starts") is None for r in rows)
            maxst = max([r.get("starts") or 0 for r in rows] or [0])
            elig = [r for r in rows if r.get("eligible", True) and r.get("pos") is not None]
            elig.sort(key=lambda r: r["pos"])
            drivers = {}
            for r in rows:
                k = dkey(r)
                st = r.get("starts") or 0
                drivers[k] = {"starts": st, "wins": r.get("wins") or 0, "top5": r.get("top5"), "top10": r.get("top10"),
                              "ft": (not champion_only) and maxst >= 4 and st >= FT_SHARE * maxst,
                              "rank": None, "results": r.get("results"), "name": r.get("name"), "nat": r.get("nat")}
            for i, r in enumerate(elig):
                drivers[dkey(r)]["rank"] = i + 1
            n_elig_ft = sum(1 for r in elig if drivers[dkey(r)]["ft"])
            # team map
            teamof = {}
            for t in d.get("teams") or []:
                tn = norm_team(t.get("team"))
                for c in t.get("cars") or []:
                    drs = c.get("drivers") or []
                    for dr in drs:
                        k = dr.get("wiki") or "name:" + (dr.get("name") or "").strip().lower()
                        score = dr.get("races") if isinstance(dr.get("races"), int) else (40 if c.get("full_time") and len(drs) == 1 else (20 if c.get("full_time") else 1))
                        if k not in teamof or score > teamof[k][1]:
                            teamof[k] = (tn, score, t.get("manufacturer"), t.get("team"))
            winners = [(r.get("winner_wiki") or ("name:" + (r.get("winner") or "").lower()), r.get("date")) for r in d.get("schedule") or [] if r.get("winner")]
            seasons[(s, y)] = {"drivers": drivers, "champion_only": champion_only, "maxstarts": maxst,
                               "n_elig_ft": n_elig_ft, "teamof": teamof, "winners": winners,
                               "champion": dkey(elig[0]) if elig else None, "n_rounds": len(d.get("schedule") or [])}
    return births, seasons


births, seasons = load()
years_of = collections.defaultdict(list)
for (s, y) in seasons:
    years_of[s].append(y)
for s in years_of:
    years_of[s].sort()


def full_data(s, y):
    v = seasons.get((s, y))
    return bool(v) and not v["champion_only"] and v["maxstarts"] >= 4


def ft_in(s, y, k):
    v = seasons.get((s, y))
    return bool(v) and k in v["drivers"] and v["drivers"][k]["ft"]


def starts_in(s, y, k):
    v = seasons.get((s, y))
    return (v["drivers"][k]["starts"] if v and k in v["drivers"] else 0) or 0


def higher(s):
    L, r = SERIES[s]["ladder"], SERIES[s]["rung"]
    return [t for t in SERIES if SERIES[t]["ladder"] == L and SERIES[t]["rung"] > r]


def lower(s):
    L, r = SERIES[s]["ladder"], SERIES[s]["rung"]
    return [t for t in SERIES if SERIES[t]["ladder"] == L and SERIES[t]["rung"] < r]


def same_rung(s):
    L, r = SERIES[s]["ladder"], SERIES[s]["rung"]
    return [t for t in SERIES if SERIES[t]["ladder"] == L and SERIES[t]["rung"] == r]


def age(k, y):
    b = births.get(k)
    return (y - b) if b else None


def q(vals, p, nd=1):
    v = sorted(vals)
    if not v:
        return None
    i = (len(v) - 1) * p
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return round(v[lo] + (v[hi] - v[lo]) * (i - lo), nd)


def dist(vals):
    vals = [x for x in vals if x is not None]
    if not vals:
        return {"n": 0}
    nd = 3 if all(0 <= x <= 1 for x in vals) else 1   # shares keep 3 decimals, ages/counts 1
    return {"n": len(vals), "mean": round(statistics.mean(vals), nd), "p10": q(vals, .1, nd), "p25": q(vals, .25, nd),
            "median": q(vals, .5, nd), "p75": q(vals, .75, nd), "p90": q(vals, .9, nd), "min": min(vals), "max": max(vals)}


def rate(num, den):
    return {"rate": round(num / den, 3) if den else None, "n": den, "k": num,
            "ci95": wilson(num, den)}


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def decade(y):
    return "1995-1999" if y < 2000 else ("2000-2009" if y < 2010 else ("2010-2019" if y < 2020 else "2020-2026"))


def era(y):
    return "1995-2004" if y < 2005 else ("2005-2014" if y < 2015 else "2015-2026")


def age_bucket(a):
    if a is None:
        return "unknown"
    return "<=19" if a <= 19 else ("20-22" if a <= 22 else ("23-25" if a <= 25 else ("26-29" if a <= 29 else ("30-34" if a <= 34 else "35+"))))


def pos_bucket(rank, ft):
    if rank == 1:
        return "champion"
    if not ft or rank is None:
        return None
    return "P2-3" if rank <= 3 else ("P4-5" if rank <= 5 else ("P6-10" if rank <= 10 else "P11+"))


evidence = {"meta": {"source_id": "src:racingsim-history-analysis", "script": "analyse_history.py",
                     "generated": str(date.today()), "data_root": HIST, "definitions": __doc__.strip(),
                     "coverage": {s: {"years": [years_of[s][0], years_of[s][-1]] if years_of[s] else None,
                                      "full_data_years": [y for y in years_of[s] if full_data(s, y)],
                                      "n_seasons": len(years_of[s])} for s in SERIES}}}

# ---------------------------------------------------------------- 1. promotion (lower -> higher)
promo_rows = []
for s in LOWER_SERIES:
    up = higher(s)
    for y in years_of[s]:
        v = seasons[(s, y)]
        for k, dr in v["drivers"].items():
            b = pos_bucket(dr["rank"], dr["ft"])
            if b is None and not (v["champion_only"] and k == v["champion"]):
                continue
            if v["champion_only"]:
                b = "champion"
            already = any(ft_in(t, yy, k) for t in up for yy in (y - 1, y))
            prior_higher = any(ft_in(t, yy, k) for t in up for yy in range(1995, y - 1))
            out = {}
            nxt = [t for t in up if SERIES[t]["rung"] == SERIES[s]["rung"] + 1]
            for kk in (1, 2, 3):
                # outcome only measurable if the next rung has full standings for every window year
                if y + kk > LAST_YEAR or not all(any(full_data(t, yy) for t in nxt) for yy in range(y + 1, y + kk + 1)):
                    out[kk] = None
                    continue
                out[kk] = {"ft_up": any(ft_in(t, yy, k) for t in up for yy in range(y + 1, y + kk + 1)),
                           "ft_next": any(ft_in(t, yy, k) for t in up if SERIES[t]["rung"] == SERIES[s]["rung"] + 1 for yy in range(y + 1, y + kk + 1)),
                           "any_up": any(starts_in(t, yy, k) > 0 for t in up for yy in range(y + 1, y + kk + 1))}
            # where are they 1 yr later (for non-promoted)
            promo_rows.append({"series": s, "year": y, "key": k, "bucket": b, "age": age(k, y), "already_up": already,
                               "prior_higher": prior_higher, "out": out, "ft": dr["ft"],
                               "team": v["teamof"].get(k, (None,))[0], "manu": (v["teamof"].get(k, (None, None, None))[2]),
                               "nat": dr.get("nat"), "stays_ft_next": ft_in(s, y + 1, k) if y + 1 <= LAST_YEAR else None})


def promo_table(rows, kk=3, field="ft_up"):
    rows = [r for r in rows if r["out"].get(kk) is not None and not r["already_up"]]
    return rate(sum(1 for r in rows if r["out"][kk][field]), len(rows))


promotion = {}
for s in LOWER_SERIES:
    R = [r for r in promo_rows if r["series"] == s]
    res = {"label": SERIES[s]["label"], "next_rungs": higher(s)}
    for b in ["champion", "P2-3", "P4-5", "P6-10", "P11+"]:
        Rb = [r for r in R if r["bucket"] == b]
        res[b] = {f"within_{kk}y": {"ft_higher": promo_table(Rb, kk, "ft_up"), "ft_next_rung": promo_table(Rb, kk, "ft_next"),
                                    "any_start_higher": promo_table(Rb, kk, "any_up")} for kk in (1, 2, 3)}
        res[b]["excluded_already_ft_higher"] = sum(1 for r in Rb if r["already_up"])
    allft = [r for r in R if r["ft"]]
    res["all_full_time"] = {f"within_{kk}y": promo_table(allft, kk, "ft_up") for kk in (1, 2, 3)}
    res["by_era_within3y_ft_higher"] = {}
    for e in ["1995-2004", "2005-2014", "2015-2026"]:
        res["by_era_within3y_ft_higher"][e] = {
            "champion": promo_table([r for r in R if r["bucket"] == "champion" and era(r["year"]) == e]),
            "top5": promo_table([r for r in R if r["bucket"] in ("champion", "P2-3", "P4-5") and era(r["year"]) == e]),
            "all_full_time": promo_table([r for r in allft if era(r["year"]) == e])}
    res["by_age_within3y_ft_higher"] = {}
    for ab in ["<=19", "20-22", "23-25", "26-29", "30-34", "35+", "unknown"]:
        res["by_age_within3y_ft_higher"][ab] = {
            "top5": promo_table([r for r in R if r["bucket"] in ("champion", "P2-3", "P4-5") and age_bucket(r["age"]) == ab]),
            "P6+": promo_table([r for r in R if r["bucket"] in ("P6-10", "P11+") and age_bucket(r["age"]) == ab])}
    res["champions_list"] = [{"year": r["year"], "driver": r["key"], "age": r["age"], "already_ft_higher": r["already_up"],
                              "ft_higher_within3y": (r["out"][3] or {}).get("ft_up") if r["out"].get(3) else None,
                              "ft_higher_within1y": (r["out"][1] or {}).get("ft_up") if r["out"].get(1) else None}
                             for r in sorted(R, key=lambda r: r["year"]) if r["bucket"] == "champion"]
    promotion[s] = res
evidence["promotion_by_finish"] = promotion

# connected (Cup-affiliated) teams vs independents: NASCAR lower series, full-time drivers, not already Cup
def is_affiliated(team):
    t = team or ""
    return any(a in t for a in CUP_AFFILIATES)

conn = {}
for s in ["nascar_trucks", "nascar_xfinity"]:
    R = [r for r in promo_rows if r["series"] == s and r["ft"] and r["year"] >= 1997]
    out = {}
    for grp in ["top5", "P6-10", "P11+"]:
        sel = (lambda r: r["bucket"] in ("champion", "P2-3", "P4-5")) if grp == "top5" else (lambda r, g=grp: r["bucket"] == g)
        out[grp] = {"cup_affiliated_team": promo_table([r for r in R if sel(r) and is_affiliated(r["team"])]),
                    "independent_team": promo_table([r for r in R if sel(r) and r["team"] and not is_affiliated(r["team"])])}
    out["by_manufacturer_all_ft_within3y"] = {m: promo_table([r for r in R if (r["manu"] or "?") == m])
                                              for m in sorted(set((r["manu"] or "?") for r in R)) if sum(1 for r in R if (r["manu"] or "?") == m) >= 15}
    conn[s] = out
evidence["connected_team_effect"] = {"note": "Cup-affiliated = team name matches a manual list of Cup organisations/satellites (see CUP_AFFILIATES in script). Outcome: full-time at a higher NASCAR national series within 3 seasons; drivers already full-time higher are excluded.",
                                     **conn}

# nationality (open wheel)
natres = {}
for s in ["usf2000", "pro_mazda", "indy_lights"]:
    R = [r for r in promo_rows if r["series"] == s and r["ft"]]
    natres[s] = {"USA": promo_table([r for r in R if r["nat"] == "USA"]),
                 "non_USA": promo_table([r for r in R if r["nat"] and r["nat"] != "USA"]),
                 "share_non_usa_by_decade": {dcd: rate(sum(1 for r in R if decade(r["year"]) == dcd and r["nat"] and r["nat"] != "USA"),
                                                       sum(1 for r in R if decade(r["year"]) == dcd and r["nat"])) for dcd in ["1995-1999", "2000-2009", "2010-2019", "2020-2026"]}}
evidence["open_wheel_nationality"] = natres

# ---------------------------------------------------------------- 2. ages
first_year = {s: years_of[s][0] for s in SERIES}
careers = collections.defaultdict(dict)  # s -> k -> {years:[...], ft_years:[...]}
for (s, y), v in seasons.items():
    if v["champion_only"]:
        continue
    for k, dr in v["drivers"].items():
        if dr["starts"] > 0:
            c = careers[s].setdefault(k, {"years": [], "ft": []})
            c["years"].append(y)
            if dr["ft"]:
                c["ft"].append(y)
for s in careers:
    for c in careers[s].values():
        c["years"].sort(); c["ft"].sort()

ages = {}
for s in SERIES:
    fy = min(y for y in years_of[s] if full_data(s, y)) if any(full_data(s, y) for y in years_of[s]) else None
    if fy is None:
        continue
    deb, ftd, last, lastft = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for k, c in careers[s].items():
        y0 = c["years"][0]
        if y0 > fy:
            deb[decade(y0)].append(age(k, y0)); deb["all"].append(age(k, y0))
        if c["ft"] and c["ft"][0] > fy:
            f0 = c["ft"][0]
            ftd[decade(f0)].append(age(k, f0)); ftd["all"].append(age(k, f0))
        yl = c["years"][-1]
        if yl <= LAST_YEAR - 3:
            last[decade(yl)].append(age(k, yl)); last["all"].append(age(k, yl))
        if c["ft"] and c["ft"][-1] <= LAST_YEAR - 3 and not any(ft_in(t, yy, k) for t in SERIES if t != s for yy in range(c["ft"][-1] + 1, LAST_YEAR + 1)):
            lastft[decade(c["ft"][-1])].append(age(k, c["ft"][-1])); lastft["all"].append(age(k, c["ft"][-1]))
    ages[s] = {"label": SERIES[s]["label"], "tier": SERIES[s]["tier"],
               "age_at_first_start": {d: dist(v) for d, v in sorted(deb.items())},
               "age_at_first_full_time_season": {d: dist(v) for d, v in sorted(ftd.items())},
               "age_at_last_start_in_series": {d: dist(v) for d, v in sorted(last.items())},
               "age_at_last_full_time_season_no_later_ft_anywhere": {d: dist(v) for d, v in sorted(lastft.items())},
               "note": f"debuts in the first full-data year ({fy}) excluded (left-censoring); 'last' requires no start in this series after {LAST_YEAR-3}."}
evidence["ages"] = ages


# Kaplan-Meier for seasons in series
def km(durations):
    # durations: list of (t, event)
    out = []
    S = 1.0
    ts = sorted(set(t for t, e in durations if e))
    for t in ts:
        n_at = sum(1 for tt, e in durations if tt >= t)
        d = sum(1 for tt, e in durations if tt == t and e)
        if n_at:
            S *= (1 - d / n_at)
        out.append((t, round(S, 3)))
    med = next((t for t, sv in out if sv <= 0.5), None)
    return {"survival": {str(t): sv for t, sv in out if t <= 20}, "median": med, "n": len(durations),
            "n_censored": sum(1 for t, e in durations if not e)}


tenure = {}
for s in SERIES:
    fy = min((y for y in years_of[s] if full_data(s, y)), default=None)
    if fy is None:
        continue
    dur_all, dur_ft = [], []
    for k, c in careers[s].items():
        if c["years"][0] <= fy:
            continue
        active = c["years"][-1] >= LAST_YEAR - 1
        dur_all.append((len(c["years"]), not active))
        if c["ft"] and c["ft"][0] > fy:
            dur_ft.append((len(c["ft"]), not (c["ft"][-1] >= LAST_YEAR - 1)))
    tenure[s] = {"seasons_with_starts_KM": km(dur_all), "full_time_seasons_KM": km(dur_ft),
                 "share_one_season_only_with_starts": rate(sum(1 for t, e in dur_all if t == 1 and e), sum(1 for t, e in dur_all if e))}
evidence["tenure_in_series"] = tenure

# ---------------------------------------------------------------- 3. seat turnover
turn = {}
for s in SERIES:
    rows = []
    hi, lo, sr = higher(s), lower(s), [t for t in same_rung(s) if t != s]
    for y in years_of[s]:
        if not (full_data(s, y) and full_data(s, y + 1)):
            continue
        A = {k for k, d in seasons[(s, y)]["drivers"].items() if d["ft"]}
        B = {k for k, d in seasons[(s, y + 1)]["drivers"].items() if d["ft"]}
        if not A or not B:
            continue
        new, gone = B - A, A - B
        cnew = collections.Counter()
        for k in new:
            if any(ft_in(t, y, k) for t in lo):
                cnew["promoted_from_lower_ft"] += 1
            elif starts_in(s, y, k) > 0:
                cnew["part_time_same_series_prev_year"] += 1
            elif any(ft_in(t, y, k) for t in hi):
                cnew["demoted_from_higher_ft"] += 1
            elif any(starts_in(t, y, k) > 0 for t in lo + sr):
                cnew["part_time_lower_or_parallel_prev_year"] += 1
            elif k in careers[s] and careers[s][k]["years"][0] < y:
                cnew["returning_after_gap"] += 1
            else:
                cnew["from_outside_dataset"] += 1
        cgone = collections.Counter()
        for k in gone:
            if any(ft_in(t, y + 1, k) for t in hi):
                cgone["moved_up_ft"] += 1
            elif any(ft_in(t, y + 1, k) for t in sr):
                cgone["moved_parallel_ft"] += 1
            elif starts_in(s, y + 1, k) > 0:
                cgone["part_time_same_series"] += 1
            elif any(ft_in(t, y + 1, k) for t in lo):
                cgone["moved_down_ft"] += 1
            elif any(starts_in(t, y + 1, k) > 0 for t in SERIES):
                cgone["part_time_elsewhere_in_dataset"] += 1
            else:
                later = any(starts_in(t, yy, k) > 0 for t in SERIES for yy in range(y + 2, LAST_YEAR + 1))
                cgone["absent_returned_later" if later else "absent_never_returned_in_dataset"] += 1
        rows.append({"year": y, "n_ft": len(A), "n_ft_next": len(B), "new": len(new), "gone": len(gone), "new_by_origin": dict(cnew), "gone_by_destination": dict(cgone)})
    if not rows:
        continue
    tot_new = collections.Counter(); tot_gone = collections.Counter()
    for r in rows:
        tot_new.update(r["new_by_origin"]); tot_gone.update(r["gone_by_destination"])
    sn, sg = sum(tot_new.values()), sum(tot_gone.values())
    tr = [r["new"] / r["n_ft_next"] for r in rows]
    turn[s] = {"label": SERIES[s]["label"], "tier": SERIES[s]["tier"],
               "ft_seat_turnover_share_per_season": dist([round(x, 3) for x in tr]),
               "by_era_mean_turnover": {e: round(statistics.mean([r["new"] / r["n_ft_next"] for r in rows if era(r["year"]) == e]), 3)
                                        for e in ["1995-2004", "2005-2014", "2015-2026"] if any(era(r["year"]) == e for r in rows)},
               "new_ft_drivers_origin_share": {k: round(v / sn, 3) for k, v in tot_new.most_common()},
               "departed_ft_drivers_destination_share": {k: round(v / sg, 3) for k, v in tot_gone.most_common()},
               "n_new_total": sn, "n_departed_total": sg, "per_year": rows,
               "note": "turnover = share of next season's full-time drivers who were not full-time in this series the season before; 'absent' = no start anywhere in this dataset (other series such as ARCA, sports cars, local racing or retirement are not covered)."}
evidence["seat_turnover"] = turn

# exit risk by finish tercile & age: P(not FT in same-or-higher series next season | FT this season)
exitrisk = {}
for s in SERIES:
    hi = higher(s) + [s] + [t for t in same_rung(s) if t != s]
    cells = collections.defaultdict(lambda: [0, 0])
    for y in years_of[s]:
        if not (full_data(s, y) and full_data(s, y + 1)) or y + 1 > LAST_YEAR - 0:
            continue
        v = seasons[(s, y)]
        fts = [(k, d) for k, d in v["drivers"].items() if d["ft"] and d["rank"]]
        n = len(fts)
        if n < 6:
            continue
        order = sorted(fts, key=lambda kd: kd[1]["rank"])
        for i, (k, d) in enumerate(order):
            terc = "top_third" if i < n / 3 else ("middle_third" if i < 2 * n / 3 else "bottom_third")
            keep = any(ft_in(t, y + 1, k) for t in hi)
            for key in [(terc, age_bucket(age(k, y))), (terc, "all"), ("all", age_bucket(age(k, y))), ("all", "all")]:
                cells[key][1] += 1
                cells[key][0] += (0 if keep else 1)
    tab = collections.defaultdict(dict)
    for (t, a), (lost, n) in cells.items():
        tab[t][a] = rate(lost, n)
    exitrisk[s] = dict(tab)
evidence["ft_seat_loss_risk_by_finish_and_age"] = {"note": "share of full-time drivers (ranked among eligible) NOT full-time in the same or a higher series the next season; terciles of rank among full-timers.", **exitrisk}

# ---------------------------------------------------------------- 4. performance metrics, team effects, aging curves
def ow_percentiles(s, y):
    """mean finishing percentile per driver from per-race results (1 = won every race, 0 = last)."""
    v = seasons[(s, y)]
    res = {k: d["results"] for k, d in v["drivers"].items() if isinstance(d.get("results"), list)}
    if not res:
        return {}
    L = max(len(r) for r in res.values())
    sums = collections.defaultdict(list)
    for i in range(L):
        fin = [(k, r[i]) for k, r in res.items() if i < len(r) and isinstance(r[i], int)]
        n = len(fin)
        if n < 5:
            continue
        for k, p in fin:
            sums[k].append(1 - (min(p, n) - 1) / (n - 1))
    return {k: (statistics.mean(v), len(v)) for k, v in sums.items() if len(v) >= 3}


def season_metric(s, y):
    """driver -> (metric, weight).  NASCAR: top-10 rate per start (fallback top-5);  open wheel: mean finish percentile."""
    v = seasons[(s, y)]
    if SERIES[s]["ladder"] == "open_wheel":
        return ow_percentiles(s, y)
    out = {}
    for k, d in v["drivers"].items():
        if d["starts"] >= 5 and d.get("top10") is not None:
            out[k] = (d["top10"] / d["starts"], d["starts"])
    return out


metrics = {(s, y): season_metric(s, y) for (s, y) in seasons if full_data(s, y)}


def icc_oneway(groups):
    groups = [g for g in groups if len(g) >= 2]
    if len(groups) < 5:
        return None
    N = sum(len(g) for g in groups); a = len(groups)
    grand = sum(sum(g) for g in groups) / N
    ssb = sum(len(g) * (statistics.mean(g) - grand) ** 2 for g in groups)
    ssw = sum(sum((x - statistics.mean(g)) ** 2 for x in g) for g in groups)
    msb, msw = ssb / (a - 1), ssw / (N - a)
    k0 = (N - sum(len(g) ** 2 for g in groups) / N) / (a - 1)
    icc = (msb - msw) / (msb + (k0 - 1) * msw) if (msb + (k0 - 1) * msw) else None
    return {"icc": round(icc, 3) if icc is not None else None, "n_team_seasons": a, "n_driver_seasons": N}


def corr(xs, ys):
    n = len(xs)
    if n < 5:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 3) if sx and sy else None


def slope(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx, 3) if vx else None


team_eff = {}
for s in SERIES:
    groups, by_era = [], collections.defaultdict(list)
    tsmean = {}  # (y, team) -> {driver: metric}
    for y in years_of[s]:
        m = metrics.get((s, y))
        if not m:
            continue
        v = seasons[(s, y)]
        g = collections.defaultdict(dict)
        for k, (val, w) in m.items():
            if v["drivers"][k]["ft"] and k in v["teamof"]:
                g[v["teamof"][k][0]][k] = val
        for t, dd in g.items():
            tsmean[(y, t)] = dd
            if len(dd) >= 2:
                groups.append(list(dd.values())); by_era[era(y)].append(list(dd.values()))
    # switchers: delta driver metric vs delta leave-one-out teammate metric
    dx, dy, sx_, sy_ = [], [], [], []
    for y in years_of[s]:
        if (s, y + 1) not in metrics or (s, y) not in metrics:
            continue
        v0, v1 = seasons[(s, y)], seasons[(s, y + 1)]
        for k in metrics[(s, y)]:
            if k not in metrics[(s, y + 1)] or not (v0["drivers"][k]["ft"] and v1["drivers"].get(k, {}).get("ft")):
                continue
            t0, t1 = v0["teamof"].get(k, (None,))[0], v1["teamof"].get(k, (None,))[0]
            if not t0 or not t1:
                continue
            o0 = [x for kk, x in tsmean.get((y, t0), {}).items() if kk != k]
            o1 = [x for kk, x in tsmean.get((y + 1, t1), {}).items() if kk != k]
            if not o0 or not o1:
                continue
            d_drv = metrics[(s, y + 1)][k][0] - metrics[(s, y)][k][0]
            d_team = statistics.mean(o1) - statistics.mean(o0)
            if t0 != t1:
                dx.append(d_team); dy.append(d_drv)
            else:
                sx_.append(d_team); sy_.append(d_drv)
    # level correlation: driver metric vs leave-one-out teammate mean (same season)
    lx, ly = [], []
    for (y, t), dd in tsmean.items():
        if len(dd) >= 2:
            for k, val in dd.items():
                lx.append(statistics.mean([x for kk, x in dd.items() if kk != k])); ly.append(val)
    team_eff[s] = {"metric": "mean finishing percentile per race" if SERIES[s]["ladder"] == "open_wheel" else "top-10 finishes per start",
                   "icc_within_team_season": icc_oneway(groups),
                   "icc_by_era": {e: icc_oneway(gs) for e, gs in sorted(by_era.items())},
                   "corr_driver_vs_teammates_same_season": {"r": corr(lx, ly), "n": len(lx)},
                   "team_switchers": {"n": len(dx), "slope_driver_change_on_team_change": slope(dx, dy) if len(dx) >= 10 else None,
                                      "r": corr(dx, dy)},
                   "team_stayers": {"n": len(sx_), "slope": slope(sx_, sy_) if len(sx_) >= 10 else None, "r": corr(sx_, sy_)}}


# two-way fixed effects (driver + team-season) on driver-season metric, alternating projections
def twfe(s, min_starts=5):
    obs = []
    for y in years_of[s]:
        m = metrics.get((s, y))
        if not m:
            continue
        v = seasons[(s, y)]
        for k, (val, w) in m.items():
            if k in v["teamof"] and w >= (3 if SERIES[s]["ladder"] == "open_wheel" else min_starts):
                obs.append((k, (y, v["teamof"][k][0]), val, w))
    # keep drivers with >= 3 driver-seasons and team-seasons with >= 2 retained drivers
    # (reduces limited-mobility over-fitting; iterate until stable)
    for _ in range(10):
        nd = collections.Counter(o[0] for o in obs)
        obs = [o for o in obs if nd[o[0]] >= 3]
        nt = collections.Counter(o[1] for o in obs)
        obs = [o for o in obs if nt[o[1]] >= 2]
    if len(obs) < 80:
        return {"skipped": "too few repeat drivers / multi-car team-seasons after filtering", "n_obs": len(obs)}
    mu = sum(o[2] * o[3] for o in obs) / sum(o[3] for o in obs)
    a = collections.defaultdict(float); b = collections.defaultdict(float)
    for _ in range(200):
        num, den = collections.defaultdict(float), collections.defaultdict(float)
        for k, t, val, w in obs:
            num[k] += w * (val - mu - b[t]); den[k] += w
        a = {k: num[k] / den[k] for k in num}
        num, den = collections.defaultdict(float), collections.defaultdict(float)
        for k, t, val, w in obs:
            num[t] += w * (val - mu - a[k]); den[t] += w
        b = {t: num[t] / den[t] for t in num}
    W = sum(o[3] for o in obs)
    def wvar(xs):
        m_ = sum(x * w for x, w in xs) / W
        return sum(w * (x - m_) ** 2 for x, w in xs) / W
    va = wvar([(a[k], w) for k, t, val, w in obs]); vb = wvar([(b[t], w) for k, t, val, w in obs])
    vy = wvar([(val, w) for k, t, val, w in obs])
    ma = sum(a[k] * w for k, t, v_, w in obs) / W; mb = sum(b[t] * w for k, t, v_, w in obs) / W
    cab = sum(w * (a[k] - ma) * (b[t] - mb) for k, t, v_, w in obs) / W
    vres = wvar([(val - mu - a[k] - b[t], w) for k, t, val, w in obs])
    expl = va + vb + 2 * cab
    return {"n_obs_driver_seasons": len(obs), "n_drivers": len(a), "n_team_seasons": len(b),
            "share_total_var_driver": round(va / vy, 3), "share_total_var_team_season": round(vb / vy, 3),
            "share_total_var_2cov": round(2 * cab / vy, 3), "share_total_var_residual": round(vres / vy, 3),
            "team_share_of_driver_plus_team_var": round(vb / (va + vb), 3) if va + vb else None,
            "note": "driver-season level, drivers with >=3 seasons and team-seasons with >=2 such drivers only. Limited-mobility bias still inflates both FE variances (negative 2cov, small residual); read team_share_of_driver_plus_team_var as a rough indicator only (low confidence)."}


for s in SERIES:
    team_eff[s]["two_way_fixed_effects"] = twfe(s)

# win concentration by organisation
conc = {}
for s in SERIES:
    rows = []
    for y in years_of[s]:
        v = seasons[(s, y)]
        if not v["winners"] or v["champion_only"]:
            continue
        c = collections.Counter()
        for wk, _ in v["winners"]:
            c[v["teamof"].get(wk, ("?",))[0]] += 1
        tot = sum(c.values())
        top = [n for t, n in c.most_common() if t != "?"]
        nft_teams = len(set(v["teamof"][k][0] for k, d in v["drivers"].items() if d["ft"] and k in v["teamof"]))
        rows.append({"year": y, "races": tot, "top1_share": round(top[0] / tot, 3) if top else None,
                     "top3_share": round(sum(top[:3]) / tot, 3) if top else None, "n_winning_orgs": len(top), "n_orgs_with_ft_cars": nft_teams,
                     "unmatched_share": round(c.get("?", 0) / tot, 3)})
    if rows:
        conc[s] = {"top3_org_win_share": dist([r["top3_share"] for r in rows if r["top3_share"] is not None]),
                   "top1_org_win_share": dist([r["top1_share"] for r in rows if r["top1_share"] is not None]),
                   "winning_orgs_per_season": dist([r["n_winning_orgs"] for r in rows]),
                   "orgs_with_ft_cars_per_season": dist([r["n_orgs_with_ft_cars"] for r in rows]),
                   "per_year": rows}
evidence["team_strength"] = {"per_series": team_eff, "win_concentration_by_org": conc}

# Cup-affiliated share of wins in Trucks / Xfinity
aff = {}
for s in ["nascar_trucks", "nascar_xfinity"]:
    rows = []
    for y in years_of[s]:
        v = seasons[(s, y)]
        if not v["winners"]:
            continue
        n = len(v["winners"]); a_ = 0; cupdrv = 0
        for wk, _ in v["winners"]:
            if is_affiliated(v["teamof"].get(wk, ("",))[0]):
                a_ += 1
            if ft_in("nascar_cup", y, wk):
                cupdrv += 1
        nft = [k for k, d in v["drivers"].items() if d["ft"]]
        rows.append({"year": y, "wins_by_cup_affiliated_teams": round(a_ / n, 3), "wins_by_cup_ft_drivers": round(cupdrv / n, 3),
                     "share_ft_drivers_at_affiliated_teams": round(sum(1 for k in nft if is_affiliated(v["teamof"].get(k, ("",))[0])) / len(nft), 3) if nft else None})
    aff[s] = {"by_era": {e: {"wins_by_cup_affiliated_teams": round(statistics.mean([r["wins_by_cup_affiliated_teams"] for r in rows if era(r["year"]) == e]), 3),
                             "wins_by_cup_ft_drivers": round(statistics.mean([r["wins_by_cup_ft_drivers"] for r in rows if era(r["year"]) == e]), 3),
                             "share_ft_drivers_at_affiliated_teams": round(statistics.mean([r["share_ft_drivers_at_affiliated_teams"] for r in rows if era(r["year"]) == e and r["share_ft_drivers_at_affiliated_teams"] is not None]), 3)}
                         for e in ["1995-2004", "2005-2014", "2015-2026"]}, "per_year": rows}
evidence["cup_affiliated_dominance_lower_series"] = aff

# aging curves (delta method) + wins by age
aging = {}
for s in ["nascar_cup", "nascar_xfinity", "nascar_trucks", "irl_indycar", "cart_champcar", "indy_lights"]:
    deltas = collections.defaultdict(list)
    for y in years_of[s]:
        m0, m1 = metrics.get((s, y)), metrics.get((s, y + 1))
        if not m0 or not m1:
            continue
        for k in m0:
            if k in m1 and seasons[(s, y)]["drivers"][k]["ft"] and seasons[(s, y + 1)]["drivers"][k]["ft"]:
                a_ = age(k, y)
                if a_ is None:
                    continue
                w = 2 / (1 / m0[k][1] + 1 / m1[k][1])
                deltas[a_].append((m1[k][0] - m0[k][0], w))
    curve, cum = {}, 0.0
    for a_ in range(18, 50):
        dl = deltas.get(a_, [])
        if len(dl) < 8:
            continue
        md = sum(d * w for d, w in dl) / sum(w for d, w in dl)
        cum += md
        curve[str(a_ + 1)] = {"mean_delta_from_prev_age": round(md, 4), "cumulative": round(cum, 4), "n_pairs": len(dl)}
    peak = max(curve.items(), key=lambda kv: kv[1]["cumulative"])[0] if curve else None
    # wins by age at race
    wa = []
    for y in years_of[s]:
        for wk, dt in seasons[(s, y)]["winners"]:
            a_ = age(wk, y)
            if a_ is not None:
                wa.append(a_)
    # wins per FT driver-season by age bucket
    per = collections.defaultdict(lambda: [0, 0])
    for y in years_of[s]:
        v = seasons[(s, y)]
        if v["champion_only"]:
            continue
        for k, d in v["drivers"].items():
            if d["ft"]:
                ab = age_bucket(age(k, y))
                per[ab][0] += d["wins"]; per[ab][1] += 1
    aging[s] = {"delta_method_curve": curve, "peak_age_delta_method": peak,
                "age_at_race_wins": dist(wa),
                "wins_per_ft_driver_season_by_age": {ab: {"wins_per_season": round(w / n, 3), "n_driver_seasons": n} for ab, (w, n) in sorted(per.items())},
                "metric": team_eff[s]["metric"],
                "note": "delta method: mean change in metric between consecutive full-time seasons, indexed by age; survivor bias makes late-age declines look smaller than they are."}
evidence["aging_curves"] = aging

# ---------------------------------------------------------------- 5. ladder flow: where do lower-series full-timers end up (career level reached)
reach = {}
for s in LOWER_SERIES:
    hi = higher(s)
    top = [t for t in SERIES if SERIES[t]["ladder"] == SERIES[s]["ladder"] and SERIES[t]["tier"] == 7]
    fy = min((y for y in years_of[s] if full_data(s, y)), default=None)
    drivers = [(k, c) for k, c in careers[s].items() if c["ft"] and c["ft"][0] > fy and c["ft"][0] <= LAST_YEAR - 5]
    n = len(drivers)
    got_hi = sum(1 for k, c in drivers if any(ft_in(t, yy, k) for t in hi for yy in range(c["ft"][0], LAST_YEAR + 1)))
    got_top = sum(1 for k, c in drivers if any(ft_in(t, yy, k) for t in top for yy in range(c["ft"][0], LAST_YEAR + 1)))
    any_top = sum(1 for k, c in drivers if any(starts_in(t, yy, k) > 0 for t in top for yy in range(c["ft"][0], LAST_YEAR + 1)))
    # top-level full-time for >= 3 seasons (an established premier career)
    est = 0
    for k, c in drivers:
        yrs = set(yy for t in top for yy in range(c["ft"][0], LAST_YEAR + 1) if ft_in(t, yy, k))
        est += len(yrs) >= 3
    reach[s] = {"cohort": f"drivers whose first full-time season in this series was {fy+1}-{LAST_YEAR-5}", "n": n,
                "ever_ft_higher_rung": rate(got_hi, n), "ever_ft_premier": rate(got_top, n),
                "ever_any_premier_start": rate(any_top, n), "ft_premier_3plus_seasons": rate(est, n)}
evidence["career_reach_from_lower_series"] = reach

# Cup: how did Cup full-time rookies arrive (prior seasons in Xfinity/Trucks, best finish)
arr = []
for k, c in careers["nascar_cup"].items():
    if not c["ft"] or c["ft"][0] <= 1996:
        continue
    y0 = c["ft"][0]
    prev_x = [yy for yy in range(1995, y0) if starts_in("nascar_xfinity", yy, k) > 0]
    prev_xft = [yy for yy in range(1995, y0) if ft_in("nascar_xfinity", yy, k)]
    prev_t = [yy for yy in range(1995, y0) if ft_in("nascar_trucks", yy, k)]
    best = min([seasons[("nascar_xfinity", yy)]["drivers"][k]["rank"] or 99 for yy in prev_xft] or [None] if prev_xft else [None]) if prev_xft else None
    xwins = sum(seasons[("nascar_xfinity", yy)]["drivers"][k]["wins"] for yy in prev_x)
    arr.append({"age": age(k, y0), "xfinity_ft_seasons": len(prev_xft), "truck_ft_seasons": len(prev_t), "best_xfinity_rank": best, "xfinity_wins_before": xwins, "year": y0})
evidence["cup_rookie_background"] = {
    "n": len(arr),
    "xfinity_ft_seasons_before_cup": dist([a["xfinity_ft_seasons"] for a in arr]),
    "truck_ft_seasons_before_cup": dist([a["truck_ft_seasons"] for a in arr]),
    "share_with_zero_xfinity_ft_seasons": rate(sum(1 for a in arr if a["xfinity_ft_seasons"] == 0), len(arr)),
    "share_with_zero_xfinity_wins_before": rate(sum(1 for a in arr if a["xfinity_wins_before"] == 0), len(arr)),
    "share_best_xfinity_rank_top5": rate(sum(1 for a in arr if a["best_xfinity_rank"] and a["best_xfinity_rank"] <= 5), sum(1 for a in arr if a["best_xfinity_rank"])),
    "by_era": {e: {"n": sum(1 for a in arr if era(a["year"]) == e),
                   "age": dist([a["age"] for a in arr if era(a["year"]) == e]),
                   "xfinity_ft_seasons": dist([a["xfinity_ft_seasons"] for a in arr if era(a["year"]) == e]),
                   "zero_xfinity_wins": rate(sum(1 for a in arr if era(a["year"]) == e and a["xfinity_wins_before"] == 0), sum(1 for a in arr if era(a["year"]) == e))}
               for e in ["1995-2004", "2005-2014", "2015-2026"]},
    "note": "first full-time Cup season 1997-2026; prior seasons only counted from 1995 (left-censored for 1997-2000 rookies)."}

# owner-driver / family-team proxy: driver's surname appears in the team name
def surname(name):
    parts = re.sub(r"\b(jr|sr|ii|iii|iv)\.?$", "", (name or "").lower().replace(",", "")).split()
    return parts[-1] if parts else ""

owner = {}
for s in SERIES:
    rows = collections.defaultdict(lambda: [0, 0])
    prom = {"owner_driver": [0, 0], "other": [0, 0]}
    for y in years_of[s]:
        v = seasons[(s, y)]
        if v["champion_only"] or not v["teamof"]:
            continue
        for k, d in v["drivers"].items():
            if not d["ft"] or k not in v["teamof"]:
                continue
            sn = surname(d["name"])
            team_raw = (v["teamof"][k][3] or "").lower()
            is_own = len(sn) >= 3 and sn in team_raw
            rows[era(y)][1] += 1; rows[era(y)][0] += is_own
            if s in LOWER_SERIES and y + 3 <= LAST_YEAR:
                hi = higher(s)
                up = any(ft_in(t, yy, k) for t in hi for yy in range(y + 1, y + 4))
                already = any(ft_in(t, yy, k) for t in hi for yy in (y - 1, y))
                if not already:
                    g = "owner_driver" if is_own else "other"
                    prom[g][1] += 1; prom[g][0] += up
    owner[s] = {"share_ft_drivers_in_team_bearing_their_surname": {e: rate(a, b) for e, (a, b) in sorted(rows.items())}}
    if s in LOWER_SERIES:
        owner[s]["promotion_within3y"] = {g: rate(a, b) for g, (a, b) in prom.items()}
evidence["owner_driver_proxy"] = {"note": "Driver surname appears in team name (owner-drivers and family-owned teams, e.g. 'Norm Benning Racing', 'Jeremy Clements Racing', 'Rahal Letterman', 'Andretti'); a lower bound for self/family funding since most family money flows through other teams. Celebrity owners (e.g. a Cup star's own truck team) inflate it slightly.", **owner}

# share of premier full-time drivers who came through the in-dataset ladder (any earlier start in a lower rung)
ladder_share = {}
for s in ["nascar_cup", "irl_indycar", "cart_champcar"]:
    lo = lower(s)
    per = {}
    for y in years_of[s]:
        if not full_data(s, y):
            continue
        fts = [k for k, d in seasons[(s, y)]["drivers"].items() if d["ft"]]
        if not fts:
            continue
        came = sum(1 for k in fts if any(starts_in(t, yy, k) > 0 for t in lo for yy in range(1995, y)))
        came_ft = sum(1 for k in fts if any(ft_in(t, yy, k) for t in lo for yy in range(1995, y)))
        per[y] = {"n_ft": len(fts), "any_prior_lower_start": round(came / len(fts), 3), "prior_lower_ft_season": round(came_ft / len(fts), 3)}
    ladder_share[s] = {"by_era_mean_any_prior_lower_start": {e: round(statistics.mean([v["any_prior_lower_start"] for y, v in per.items() if era(y) == e]), 3) for e in ["1995-2004", "2005-2014", "2015-2026"] if any(era(y) == e for y in per)},
                       "by_era_mean_prior_lower_ft_season": {e: round(statistics.mean([v["prior_lower_ft_season"] for y, v in per.items() if era(y) == e]), 3) for e in ["1995-2004", "2005-2014", "2015-2026"] if any(era(y) == e for y in per)},
                       "per_year": per}
evidence["premier_field_ladder_share"] = {"note": "lower rungs counted from 1995 only, so early years understate ladder share (left-censoring); NASCAR lower = Trucks+Xfinity; open wheel lower = USF2000/Pro Mazda/Indy Lights (European feeders, Atlantics, ARCA not in data).", **ladder_share}

# annual outcome distribution of full-time drivers (season Y -> Y+1), by series and age bucket
annual = {}
for s in SERIES:
    hi, lo, par = higher(s), lower(s), [t for t in same_rung(s) if t != s]
    cnt = collections.defaultdict(collections.Counter)
    for y in years_of[s]:
        if not (full_data(s, y) and full_data(s, y + 1)):
            continue
        for k, d in seasons[(s, y)]["drivers"].items():
            if not d["ft"]:
                continue
            if any(ft_in(t, y + 1, k) for t in hi):
                o = "advance_ft_higher"
            elif ft_in(s, y + 1, k) or any(ft_in(t, y + 1, k) for t in par):
                o = "stay_ft_same_level"
            elif starts_in(s, y + 1, k) > 0 or any(starts_in(t, y + 1, k) > 0 for t in hi):
                o = "part_time_same_or_higher"
            elif any(ft_in(t, y + 1, k) for t in lo) or any(starts_in(t, y + 1, k) > 0 for t in lo):
                o = "down_to_lower_rung"
            elif any(starts_in(t, y + 1, k) > 0 for t in SERIES):
                o = "other_series_in_dataset"
            else:
                later = any(starts_in(t, yy, k) > 0 for t in SERIES for yy in range(y + 2, LAST_YEAR + 1))
                o = "absent_returned_later" if later else "absent_no_return_in_dataset"
            for key in ("all", age_bucket(age(k, y)), "era:" + era(y)):
                cnt[key][o] += 1
    annual[s] = {key: {"n": sum(c.values()), **{o: round(v / sum(c.values()), 3) for o, v in c.most_common()}} for key, c in cnt.items()}
evidence["annual_outcomes_full_time"] = {"note": "what full-time drivers of season Y do in season Y+1; 'absent' = no start in any series of this dataset (quit, injury, or moved to ARCA/sports cars/short tracks/Europe - not distinguishable). Seasons where Y+1 is 2026 use partial 2026 data.", **annual}

# career outcome classes for lower-series full-time cohorts, and how premier careers end
classes = {}
for s in LOWER_SERIES:
    hi = higher(s)
    fy = min((y for y in years_of[s] if full_data(s, y)), default=None)
    c = collections.Counter()
    for k, cr in careers[s].items():
        if not cr["ft"] or cr["ft"][0] <= fy or cr["ft"][0] > LAST_YEAR - 5:
            continue
        f0 = cr["ft"][0]
        if any(ft_in(t, yy, k) for t in hi for yy in range(f0, LAST_YEAR + 1)):
            c["advanced_ft_higher"] += 1
        elif len(cr["ft"]) >= 4:
            c["journeyman_4plus_ft_seasons_no_advance"] += 1
        else:
            last = cr["years"][-1]
            later_elsewhere = any(starts_in(t, yy, k) > 0 for t in SERIES if t != s for yy in range(last + 1, LAST_YEAR + 1)) or \
                any(starts_in(t, yy, k) > 0 for t in hi for yy in range(f0, LAST_YEAR + 1))
            if cr["years"][-1] >= LAST_YEAR - 1:
                c["still_active_same_series_no_advance"] += 1
            elif later_elsewhere:
                c["sideways_or_part_time_elsewhere_then_gone"] += 1
            else:
                c["left_dataset_within_3_ft_seasons"] += 1
    n = sum(c.values())
    classes[s] = {"n": n, **{k: rate(v, n) for k, v in c.most_common()}}
ends = {}
for s in ["nascar_cup", "irl_indycar", "nascar_xfinity", "nascar_trucks"]:
    lo = lower(s)
    c = collections.Counter(); agesend = collections.defaultdict(list)
    for k, cr in careers[s].items():
        if not cr["ft"]:
            continue
        lf = cr["ft"][-1]
        if lf > LAST_YEAR - 3 or (s == "nascar_cup" and lf <= 1995):
            continue
        if s in ("nascar_xfinity", "nascar_trucks") and any(ft_in(t, yy, k) for t in higher(s) for yy in range(lf + 1, LAST_YEAR + 1)):
            continue  # left because promoted
        if any(ft_in(t, yy, k) for t in lo for yy in range(lf + 1, lf + 3)):
            o = "dropped_to_lower_series_full_time"
        elif any(starts_in(s, yy, k) > 0 for yy in range(lf + 1, lf + 4)):
            o = "part_time_same_series_then_out"
        elif any(starts_in(t, yy, k) > 0 for t in SERIES for yy in range(lf + 1, lf + 4)):
            o = "part_time_other_series_then_out"
        else:
            o = "left_dataset_directly"
        c[o] += 1
        agesend[o].append(age(k, lf))
    n = sum(c.values())
    ends[s] = {"n": n, **{k: {**rate(v, n), "age_at_last_ft": dist(agesend[k])} for k, v in c.most_common()}}
evidence["career_outcome_classes_lower_series"] = {"note": "cohort = first full-time season after first data year and <= 2021", **classes}
evidence["how_full_time_careers_end"] = {"note": "drivers whose last full-time season in the series was <= 2023 (lower series: excluding those who left because they were promoted)", **ends}

json.dump(evidence, open(OUT, "w"), indent=1, ensure_ascii=False)
print("wrote", OUT)
