"""Long memory: awards, milestones, the almanac, records books, winners by track and the Hall of Fame.

Everything here is derived from what the simulation already keeps (season records, results, the
news wire) and stored compactly in ``world.annals``:

* ``almanac[year]``: champions, award winners, the PAR leaders, crown-jewel winners, milestones and
  Hall of Fame inductees for that season.
* ``track_winners[track id]``: [year, event, driver id] for every touring, national and crown-jewel
  race run there.
* ``hof``: Hall of Fame inductees in order, with the case for each.

Awards follow the real ones: champion (already a title), Rookie of the Year, Most Popular Driver
(national series: popularity is sticky - Dale Earnhardt Jr. won it 15 years running), a value
award for the PAR leader, and one Driver of the Year at the top level.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from .entities import RETIRED

if TYPE_CHECKING:
    from .entities import Driver, SeasonRecord
    from .world import World

AWARD_TIER = 4          # regional touring series and up hand out season awards
POPULAR_TIER = 5        # national series vote a Most Popular Driver
HOF_WAIT = 3            # seasons after the last one before a driver is on the ballot
HOF_YEARS = 15          # seasons on the ballot
HOF_BAR = 160.0         # career value needed for induction
HOF_MAX = 3             # inductees per year at most
TIER_WEIGHT = {7: 1.0, 6: 0.45, 5: 0.25, 4: 0.12, 3: 0.05}
START_MILESTONES = (100, 250, 500, 750)
REF_EVENTS = 36         # a Cup-length season: wins in longer schedules are scaled to it
REF_FIELD = 30          # titles in small fields count for less
WIN_MILESTONES = (10, 25, 50, 100, 200)


def store(world: "World") -> dict:
    a = world.__dict__.setdefault("annals", {})
    a.setdefault("almanac", {})
    a.setdefault("track_winners", {})
    a.setdefault("hof", [])
    return a


# ---------------------------------------------------------------------------------- during the season
TRACK_WINNERS_KEPT = 200


def note_race(world: "World", track_id: str, event: str, winner_id: int) -> None:
    rows = store(world)["track_winners"].setdefault(track_id, [])
    rows.append([world.year, event, winner_id])
    if len(rows) > TRACK_WINNERS_KEPT:
        del rows[: len(rows) - TRACK_WINNERS_KEPT]


def series_wins_before(d: "Driver", series_id: str) -> int:
    return sum(r.wins for r in d.history if r.series_id == series_id)


def past_unknown(d: "Driver", year: int) -> bool:
    """A driver generated with a career already behind them (no records before this world began):
    we can't tell whether this is really their first season or first win in a series."""
    return not d.is_player and not any(r.year < year for r in d.history) and d.years_at_tier > 1


def first_win(world: "World", d: "Driver", series, wins_this_season: int, track_name: str, week: int) -> None:
    """News when a driver wins for the first time in a touring or national series."""
    if wins_this_season != 1 or (series.tier < AWARD_TIER and not d.is_player):
        return
    if series_wins_before(d, series.id) or past_unknown(d, world.year):
        return
    text = f"{d.name} scores a first {series.name} win at {track_name}"
    d.log(world.year, f"first {series.name} win, at {track_name}")
    if series.tier >= 5 or d.is_player:
        world.post("milestone", text, driver_id=d.id, series_id=series.id, week=week, importance=2)
    _milestones(world).append([text, d.id, series.tier])


def _milestones(world: "World") -> list:
    return store(world).setdefault("pending_milestones", [])


# ---------------------------------------------------------------------------------- season end
def season_end(world: "World", results) -> None:
    """Awards, milestones and the almanac page for the season just finished."""
    year = world.year
    alm = {"champions": [], "awards": [], "par": [], "jewels": [], "milestones": [], "hof": []}
    alm["milestones"] = list(store(world).pop("pending_milestones", []))
    prev = store(world)["almanac"].get(year - 1, {})
    popular_before = {a[4]: a[2] for a in prev.get("awards", []) if len(a) > 4 and a[0] == "Most Popular Driver"}
    by_series: dict[str, list[tuple[int, "SeasonRecord"]]] = defaultdict(list)
    for did, rec in results.records.items():
        by_series[rec.series_id].append((did, rec))
    for sid, did in sorted(results.champions.items()):
        s = world.series(sid)
        if s.tier >= 3:
            alm["champions"].append([s.name, s.tier, did])
    alm["champions"].sort(key=lambda x: (-x[1], x[0]))
    jewel_names = {cj.key: cj.name for cj in world.pyramid.crown_jewels}
    for key, order in results.crown_jewel_results:
        if order:
            alm["jewels"].append([jewel_names.get(key, key), order[0]])

    rng = world.rng
    top_tier = max((world.series(sid).tier for sid in by_series), default=0)
    doty: Optional[tuple[float, int, str]] = None
    for sid in sorted(by_series):
        s = world.series(sid)
        if s.tier < AWARD_TIER:
            continue
        rows = by_series[sid]
        events = max(1, len(s.schedule))
        full = [(did, r) for did, r in rows if r.starts >= 0.5 * events]
        if not full:
            continue
        rookies = [(did, r) for did, r in full
                   if not any(h.series_id == sid and h.year < year for h in world.drivers[did].history)
                   and not past_unknown(world.drivers[did], year)]
        if rookies:
            did, _ = min(rookies, key=lambda x: (x[1].championship_pos, x[0]))
            _award(world, alm, did, s, "Rookie of the Year")
        valued = [(did, r) for did, r in full if r.par is not None]
        if valued:
            did, r = max(valued, key=lambda x: (x[1].par, -x[0]))
            _award(world, alm, did, s, "Most Valuable Driver", f"{r.par:+.1f} PAR")
            if s.tier == top_tier:
                for d_id, rr in valued:
                    score = rr.par + (3 if rr.champion else 0)
                    if doty is None or score > doty[0]:
                        doty = (score, d_id, s.name)
        if s.tier >= POPULAR_TIER:
            holder = popular_before.get(sid)   # by series id: popularity survives a sponsor rename

            def pop(x):
                d = world.drivers[x[0]]
                return (d.marketability * 0.5 + d.reputation * 0.3 + x[1].wins * 1.5
                        + (8 if x[0] == holder else 0) + rng.gauss(0, 4))
            did, _ = max(full, key=pop)
            _award(world, alm, did, s, "Most Popular Driver")
        for did, r in rows:
            if r.starts:
                _season_milestones(world, alm, world.drivers[did], s, r)
    if doty is not None:
        d = world.drivers[doty[1]]
        d.awards.append(f"{year} Driver of the Year")
        alm["awards"].insert(0, ["Driver of the Year", doty[2], doty[1], "", None])
        world.post("award", f"{d.name} is the {year} Driver of the Year", driver_id=d.id, importance=2)
    # The value leaderboard: national level and up.
    best = [(r.par, did, world.series(r.series_id).name) for did, r in results.records.items()
            if r.par is not None and r.tier >= 5]
    best.sort(key=lambda x: (-x[0], x[1]))
    alm["par"] = [[round(p, 1), did, name] for p, did, name in best[:15]]
    alm["milestones"].sort(key=lambda m: -(m[2] if len(m) > 2 else 0))   # the biggest stages first
    store(world)["almanac"][year] = alm


def _award(world: "World", alm: dict, did: int, s, label: str, note: str = "") -> None:
    d = world.drivers[did]
    d.awards.append(f"{world.year} {s.name} {label}")
    alm["awards"].append([label, s.name, did, note, s.id])
    if s.tier >= 5 or d.is_player:
        world.post("award", f"{d.name}: {s.name} {label}" + (f" ({note})" if note else ""), driver_id=did,
                   series_id=s.id, importance=2 if d.is_player or s.tier >= 6 else 1)


def _season_milestones(world: "World", alm: dict, d: "Driver", s, rec: "SeasonRecord") -> None:
    """Starts and wins in a series crossing round numbers this season (the record is already filed)."""
    starts = sum(h.starts for h in d.history if h.series_id == s.id)
    wins = sum(h.wins for h in d.history if h.series_id == s.id)
    for mark in START_MILESTONES:
        if starts - rec.starts < mark <= starts:
            _milestone(world, alm, d, s, f"{d.name} made a {mark}th {s.name} start")
    for mark in WIN_MILESTONES:
        if wins - rec.wins < mark <= wins:
            _milestone(world, alm, d, s, f"{d.name} reached {mark} {s.name} wins")


def _milestone(world: "World", alm: dict, d: "Driver", s, text: str) -> None:
    alm["milestones"].append([text, d.id, s.tier])
    if s.tier >= 5 or d.is_player:
        world.post("milestone", text, driver_id=d.id, series_id=s.id, importance=1)


# ---------------------------------------------------------------------------------- Hall of Fame
def career_value(d: "Driver") -> tuple[float, dict]:
    """A Hall of Fame case: wins, titles, top fives and PAR, weighted by the level they came at."""
    score = 0.0
    tally = {"wins": 0, "titles": 0, "top5": 0, "par": 0.0, "top_wins": 0, "top_titles": 0, "seasons": 0}
    top = max((r.tier for r in d.history), default=0)
    for r in d.history:
        w = TIER_WEIGHT.get(r.tier, 0.0)
        if not w:
            continue
        par = max(0.0, r.par or 0.0)
        # A win in an 80-race sprint-car season or a title in a ten-car class counts for less than
        # in a 36-race, 40-car season.
        per_race = min(1.0, REF_EVENTS / max(r.starts, 1))
        field = min(1.0, (r.field_size or 0) / REF_FIELD)
        score += w * ((r.wins * 4 + r.top5 * 0.6) * per_race + (40 if r.champion else 0) * field + par * 1.5)
        tally["wins"] += r.wins
        tally["titles"] += r.champion
        tally["top5"] += r.top5
        tally["par"] += r.par or 0.0
        tally["seasons"] += 1
        if r.tier == top:
            tally["top_wins"] += r.wins
            tally["top_titles"] += r.champion
    score += 8 * len(d.crown_jewels)
    tally["top_tier"] = top
    return round(score, 1), tally


def hall_of_fame(world: "World") -> list[str]:
    """The annual ballot: retired drivers a few seasons removed, the strongest cases first."""
    a = store(world)
    year = world.year
    inducted = {h["id"] for h in a["hof"]}
    ballot = []
    for d in world.drivers.values():
        if d.status != RETIRED or d.id in inducted or d.max_tier < 5 or not d.history:
            continue
        last = max(r.year for r in d.history)
        if not (year - HOF_WAIT - HOF_YEARS <= last <= year - HOF_WAIT):
            continue
        score, tally = career_value(d)
        if score >= HOF_BAR:
            ballot.append((score, d.id, tally, last))
    ballot.sort(key=lambda x: (-x[0], x[1]))
    news = []
    for score, did, tally, last in ballot[:HOF_MAX]:
        d = world.drivers[did]
        first = min(r.year for r in d.history)
        case = (f"{tally['wins']} win{'s' if tally['wins'] != 1 else ''} and {tally['titles']} "
                f"title{'s' if tally['titles'] != 1 else ''} in touring and national racing"
                + (f", {len(d.crown_jewels)} crown jewels" if d.crown_jewels else ""))
        a["hof"].append({"id": did, "year": year, "score": score, "career": f"{first}-{last}", "case": case})
        d.awards.append(f"Hall of Fame (class of {year})")
        d.log(year, "inducted into the Hall of Fame")
        text = f"{d.name} is inducted into the Hall of Fame ({case})"
        world.post("award", text, driver_id=did, importance=2)
        news.append(text)
        alm = a["almanac"].get(year)   # announced in the winter after this season
        if alm is not None:
            alm["hof"].append(did)
    return news


# ---------------------------------------------------------------------------------- records books
CAREER = (("wins", "Wins"), ("titles", "Championships"), ("starts", "Starts"), ("top5", "Top fives"),
          ("poles", "Poles"), ("laps_led", "Laps led"), ("par", "PAR"))
SEASON = (("wins", "Wins"), ("poles", "Poles"), ("top5", "Top fives"), ("laps_led", "Laps led"),
          ("par", "PAR"), ("rating", "Driver rating"))


def records(world: "World", series_id: str, limit: int = 10) -> dict:
    """Career leaders and single-season bests in one series (cached until the next season is filed)."""
    finished = bool(world.season is not None and world.season.finished)
    key = ("records", series_id, world.year, finished)
    hit = world.cache.get(key)
    if hit is not None:
        return hit
    career: dict[int, dict] = {}
    season: dict[str, list] = {k: [] for k, _ in SEASON}
    for d in world.drivers.values():
        for r in d.history:
            if r.series_id != series_id:
                continue
            c = career.setdefault(d.id, {k: 0 for k, _ in CAREER})
            c["wins"] += r.wins
            c["titles"] += r.champion
            c["starts"] += r.starts
            c["top5"] += r.top5
            c["poles"] += r.poles
            c["laps_led"] += r.laps_led
            c["par"] += r.par or 0.0
            for k, _ in SEASON:
                v = getattr(r, k)
                if v is None or (k == "rating" and r.starts < 10):
                    continue
                season[k].append((v, d.id, r.year))
    out = {"career": {}, "season": {}}
    for k, label in CAREER:
        rows = sorted(((c[k], did) for did, c in career.items() if c[k] > 0), key=lambda x: (-x[0], x[1]))[:limit]
        out["career"][k] = {"label": label, "rows": [[round(v, 1) if k == "par" else v, did] for v, did in rows]}
    for k, label in SEASON:
        rows = sorted(season[k], key=lambda x: (-x[0], x[2], x[1]))[:limit]
        out["season"][k] = {"label": label, "rows": [[round(v, 1) if isinstance(v, float) else v, did, y]
                                                      for v, did, y in rows if v]}
    world.cache[key] = out
    return out


def career_splits(d: "Driver") -> dict:
    """Career by track type across touring and national racing (tier 3+)."""
    out: dict[str, list] = {}
    for r in d.history:
        if r.tier < 3:
            continue
        for tt, v in (getattr(r, "splits", None) or {}).items():
            acc = out.setdefault(tt, [0, 0, 0, 0, 0])
            for i in range(5):
                acc[i] += v[i]
    return out
