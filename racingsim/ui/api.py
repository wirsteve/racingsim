"""JSON views of the game for the web UI.

Everything the browser sees goes through here. Hidden "true" ratings are only
shown for the player's own driver; everyone else is shown a *scouting report*
whose accuracy improves with the driver's exposure, as in the career model.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Optional

from ..career.scouting import categorize, estimated_potential
from ..game import career
from ..sim.season import SEASON_WEEKS, jewel_block_reasons, jewel_eligible, jewel_entry_cost
from ..util import clamp
from ..world.entities import DISCIPLINES, RETIRED, Driver

if TYPE_CHECKING:
    from ..game.session import Game
    from ..world.world import World

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DISC_LABEL = {
    "karting": "Karting", "stock_car": "Stock car", "dirt_oval": "Dirt oval", "open_wheel": "Open wheel",
    "sports_car": "Sports car", "touring_car": "Touring car", "club_road": "Club road",
}
TRAITS = ("consistency", "racecraft", "aggression", "feedback", "adaptability", "marketability",
          "professionalism", "determination")


def week_label(week: int, preseason: bool = False) -> str:
    if week <= 0:
        return "Pre-season" if preseason else "Off-season"
    m = min(11, 1 + int((week - 1) * 10.5 / SEASON_WEEKS))
    return f"Week {week} · {MONTHS[m - 1] if m >= 1 else 'Jan'}"


def scale(x: float) -> int:
    """0-100 hidden scale -> 20-80 scouting scale (premier-level average ~64)."""
    return int(round(clamp(20 + (x - 15) * 0.75, 20, 80)))


def money(x: float) -> float:
    return round(float(x), 0)


# ------------------------------------------------------------------------ small cards
def series_brief(world: "World", sid: Optional[str]) -> Optional[dict]:
    if not sid or sid not in world.pyramid.series:
        return None
    s = world.series(sid)
    return {"id": s.id, "name": s.name, "tier": s.tier, "tier_name": world.pyramid.tier_names.get(s.tier),
            "discipline": s.discipline, "discipline_label": DISC_LABEL.get(s.discipline), "scope": s.scope,
            "key": s.template.key}


def team_brief(world: "World", tid: Optional[int]) -> Optional[dict]:
    t = world.teams.get(tid) if tid is not None else None
    if t is None:
        return None
    m = world.manufacturers.get(t.manufacturer_id) if t.manufacturer_id else None
    return {"id": t.id, "name": t.name, "equipment": round(t.equipment), "owner_type": t.owner_type,
            "manufacturer": m.name if m else None, "series_id": t.series_id}


def scouted(world: "World", d: Driver) -> dict:
    """Ratings as the player's scouts see them (exact for the player's own driver)."""
    if d.is_player:
        ovr = d.effective_ability(d.primary_discipline)
        out = {"overall": scale(ovr), "potential": scale(d.potential), "exact": True}
        out.update({k: scale(getattr(d, k)) for k in TRAITS})
        return out
    rng = random.Random(d.id * 92821 + world.year * 31)
    sd = 2 + 12 * (1 - d.exposure / 100)

    def blur(x: float) -> int:
        return int(round(scale(x + rng.gauss(0, sd)) / 5) * 5)

    out = {"overall": blur(d.effective_ability(d.primary_discipline)),
           "potential": blur(max(d.ability, estimated_potential(d, world.year))), "exact": False,
           "confidence": "high" if sd < 5 else "medium" if sd < 9 else "low"}
    out.update({k: blur(getattr(d, k)) for k in TRAITS})
    return out


def driver_row(world: "World", d: Driver) -> dict:
    sr = scouted(world, d)
    last = d.history[-1] if d.history else None
    return {
        "id": d.id, "name": d.name, "age": d.age(world.year), "home": d.home_region, "country": d.country,
        "status": d.status, "tier": d.tier if d.series_id else None, "series": series_brief(world, d.series_id),
        "team": team_brief(world, d.team_id), "discipline": d.primary_discipline,
        "overall": sr["overall"], "potential": sr["potential"], "reputation": round(d.reputation),
        "starts": d.career_starts, "wins": d.career_wins, "titles": len(d.titles),
        "crown_jewels": len(d.crown_jewels), "max_tier": d.max_tier, "is_player": d.is_player,
        "last_pos": last.championship_pos if last else None, "last_field": last.field_size if last else None,
        "funded": d.seat_funded, "program": world.manufacturers[d.program_mfr].name if d.program_mfr else None,
        "real": d.real, "wiki": d.wiki,
    }


def driver_detail(world: "World", did: int) -> dict:
    d = world.drivers[did]
    row = driver_row(world, d)
    region = world.geo.regions.get(d.home_region)
    history = []
    for r in d.history:
        s = world.pyramid.series.get(r.series_id)
        history.append({
            "year": r.year, "age": r.year - d.birth_year, "series": series_brief(world, r.series_id),
            "series_name": r.series_name or (s.name if s else r.series_id), "tier": r.tier, "discipline": r.discipline,
            "team": team_brief(world, r.team_id) or (
                {"id": None, "name": r.team_name} if getattr(r, "team_name", "") else None),
            "starts": r.starts, "wins": r.wins, "top5": r.top5,
            "avg_finish": round(r.avg_finish, 1) if r.avg_finish else None, "pos": r.championship_pos, "field": r.field_size,
            "champion": r.champion, "jewels": r.crown_jewel_wins,
        })
    connections = []
    for key, v in sorted(d.connections.items(), key=lambda kv: -kv[1]):
        kind, _, ident = key.partition(":")
        label = None
        if kind == "team" and int(ident) in world.teams:
            label = world.teams[int(ident)].name
        elif kind == "mfr" and int(ident) in world.manufacturers:
            label = world.manufacturers[int(ident)].name
        if label:
            connections.append({"kind": kind, "name": label, "strength": round(v, 2)})
    finances = None
    if d.is_player:
        finances = {"family_budget": money(d.family_budget), "savings": money(d.savings),
                    "sponsors": [{"name": world.sponsors[x.sponsor_id].name, "amount": money(x.amount),
                                  "years_left": x.years_left} for x in d.sponsors if x.sponsor_id in world.sponsors],
                    "scholarship": money(d.scholarship), "salary": money(d.salary),
                    "available": money(d.available_funding())}
    else:
        finances = {"sponsors": [{"name": world.sponsors[x.sponsor_id].name}
                                 for x in d.sponsors if x.sponsor_id in world.sponsors]}
    row.update({
        "first_name": d.first_name, "last_name": d.last_name, "birth_year": d.birth_year,
        "home_name": region.name if region else d.home_region, "ratings": scouted(world, d),
        "history": history, "events": list(reversed(d.events[-80:])), "connections": connections[:8],
        "finances": finances, "category": categorize(d, world.year).title(),
        "contract_years": d.contract_years if d.team_id else None, "salary": money(d.salary) if d.is_player else None,
        "injury_races": d.injury_races, "exposure": round(d.exposure), "momentum": round(d.momentum),
        "titles_list": d.titles, "jewels_list": d.crown_jewels,
        "proficiency": {DISC_LABEL[k]: round(v * 100) for k, v in d.proficiency.items() if v >= 0.05},
        "veteran": d.grassroots_veteran,
    })
    return row


# ------------------------------------------------------------------------ status / dashboard
def status(game: "Game") -> dict:
    w = game.world
    p = w.player
    runner = game.runner
    from ..history.economy import price_index
    out = {"phase": game.phase, "year": w.year, "week": runner.week if game.phase == "season" else 0,
           "price_index": price_index(w.year), "start_year": w.config.start_year,
           "weeks": SEASON_WEEKS, "label": week_label(runner.week, preseason=True) if game.phase == "season" else "Off-season",
           "message": game.last_message, "player": None}
    if p is not None:
        out["player"] = {"id": p.id, "name": p.name, "age": p.age(w.year), "status": p.status,
                         "series": series_brief(w, p.series_id), "team": team_brief(w, p.team_id),
                         "funding": money(p.available_funding()), "reputation": round(p.reputation),
                         "next_race_week": runner.next_week_for(p) if game.phase == "season" else None}
    return out


def _last_season(world: "World") -> int:
    """The most recently completed season (the off-season sits before the year rolls over)."""
    runner = world.season
    return world.year if runner is not None and runner.finished else world.year - 1


def standings_rows(world: "World", sid: str, limit: Optional[int] = None) -> list[dict]:
    runner = world.season
    rows = []
    if runner is not None and not runner.finished and any(a.series_id == sid for a in runner.acc.values()):
        st = runner.playoffs.get(sid)
        alive = set(st["alive"]) if st else set()
        field_ = set(st["field"]) if st else set()
        leader = None
        for pos, (did, a) in enumerate(runner.standings(sid), start=1):
            d = world.drivers[did]
            pts = round(a.points)
            leader = pts if leader is None else leader
            rows.append({"pos": pos, "driver_id": did, "name": d.name, "is_player": d.is_player,
                         "team": team_brief(world, a.team_id), "points": pts, "behind": leader - pts,
                         "starts": a.starts, "wins": a.wins, "top5": a.top5, "top10": max(a.top10, a.top5), "dnq": a.dnq,
                         "winnings": round(a.purse),
                         "playoff": "alive" if did in alive else "out" if did in field_ else None,
                         "avg_finish": round(a.finish_sum / a.starts, 1) if a.starts else None})
    else:
        recs = [(d, r) for d in world.drivers.values() for r in d.history[-1:]
                if r.series_id == sid and r.year == _last_season(world)]
        recs.sort(key=lambda x: x[1].championship_pos)
        for d, r in recs:
            team = team_brief(world, r.team_id) or (
                {"id": None, "name": r.team_name} if getattr(r, "team_name", "") else None)
            pts = getattr(r, "points", None)
            rows.append({"pos": r.championship_pos, "driver_id": d.id, "name": d.name, "is_player": d.is_player,
                         "team": team, "points": round(pts) if pts is not None else None, "starts": r.starts,
                         "wins": r.wins, "top5": r.top5, "top10": getattr(r, "top10", 0), "dnq": getattr(r, "dnq", 0),
                         "winnings": round(getattr(r, "winnings", 0.0)) or None,
                         "avg_finish": round(r.avg_finish, 1) if r.avg_finish else None,
                         "champion": r.champion, "final": True})
        lead = next((x["points"] for x in rows if x["points"] is not None), None)
        for x in rows:
            x["behind"] = (lead - x["points"]) if lead is not None and x["points"] is not None else None
    return rows[:limit] if limit else rows


def schedule(world: "World", sid: str) -> list[dict]:
    s = world.series(sid)
    runner = world.season
    logs = {e["event"]: e for e in (runner.race_log.get(sid, []) if runner else [])}
    out = []
    n = len(s.schedule)
    for i, tid in enumerate(s.schedule):
        week = 1 + (i * SEASON_WEEKS) // max(n, 1)
        t = world.tracks.get(tid)
        e = logs.get(i)
        item = {"event": i, "week": week, "label": week_label(week), "track_id": tid, "track": t.name,
                "city": t.facts.city, "region": t.facts.region, "done": runner is not None and week <= runner.week}
        if e:
            wd = world.drivers[e["winner"]]
            item["winner"] = {"id": wd.id, "name": wd.name}
            item["has_results"] = "results" in e
            if e.get("player"):
                me = next((r for r in e.get("results", []) if world.drivers[r[0]].is_player
                           or world.player_id in r[4]), None)
                if me:
                    item["player_pos"] = me[2]
        out.append(item)
    return out


def race_result(world: "World", key: str, event: int, year: Optional[int] = None) -> Optional[dict]:
    if year is None or year == world.year:
        logs = world.season.race_log if world.season else {}
    else:
        logs = world.race_logs.get(year, {})
    for e in logs.get(key, []):
        if e["event"] == event and "results" in e:
            rows = []
            for did, tid, pos, dnf, co in e.get("results", []):
                d = world.drivers[did]
                rows.append({"pos": pos, "driver_id": did, "name": d.name, "is_player": d.is_player or
                             world.player_id in co, "team": team_brief(world, tid), "dnf": dnf,
                             "co_drivers": [{"id": c, "name": world.drivers[c].name} for c in co],
                             "tier": d.tier})
            return {"track": e["track"], "track_id": e["track_id"], "week": e["week"], "label": week_label(e["week"]),
                    "series": series_brief(world, e["series_id"]), "jewel": e.get("jewel_name"), "results": rows}
    return None


def dashboard(game: "Game") -> dict:
    w = game.world
    p = w.player
    out = {"status": status(game), "news": news(w, limit=25)}
    if p is None:
        return out
    out["driver"] = driver_detail(w, p.id)
    if p.series_id:
        sched = schedule(w, p.series_id)
        out["upcoming"] = [x for x in sched if not x["done"]][:5]
        out["recent"] = [x for x in sched if x["done"]][-5:]
        st = standings_rows(w, p.series_id)
        me = next((r for r in st if r["is_player"]), None)
        out["standings"] = st[:10]
        out["my_standing"] = me
    out["jewels"] = jewels(game)
    out["advice"] = advice(game)
    out["opportunities"] = opportunities(game)
    return out


def opportunities(game: "Game") -> list[dict]:
    """Combines and shootouts the player can apply to (they run at season's end)."""
    w = game.world
    p = w.player
    out = []
    for so in w.shootouts:
        target = w.pyramid.templates.get(so["target_template"])
        item = {"key": so["key"], "name": so["name"], "award": so["award"], "note": so.get("note", ""),
                "target": target.name.replace("{region} ", "regional ").replace("{track} ", "") if target else None, "winners": so.get("winners", 1),
                "min_age": so["min_age"], "max_age": so["max_age"],
                "applied": so["key"] in w.player_applications}
        if p is not None and p.status != RETIRED:
            age = p.age(w.year)
            key = w.series(p.series_id).template.key if p.series_id else None
            ok_age = so["min_age"] <= age <= so["max_age"]
            ok_series = key in so["from_templates"]
            item["eligible"] = ok_age and ok_series
            item["why_not"] = ", ".join(x for x, ok in (("age " + str(so["min_age"]) + "-" + str(so["max_age"]), ok_age),
                                                     ("race in a feeder class", ok_series)) if not ok)
        out.append(item)
    return out


def advice(game: "Game") -> list[str]:
    """Paddock talk: plain-language hints derived from the same levers the AI uses."""
    from ..constants import NOTICE_THRESHOLD, TIER_STRENGTH
    w = game.world
    p = w.player
    if p is None or p.status == RETIRED:
        return []
    tips = []
    age = p.age(w.year)
    funding = p.available_funding()
    nxt = min(7, p.tier + 1)
    if p.exposure < NOTICE_THRESHOLD[min(7, p.tier + 2)]:
        tips.append("Scouts above your level barely know you exist. Wins, titles and especially crown-jewel "
                    "results raise your exposure; so does racing near an industry hub.")
    if p.demonstrated >= TIER_STRENGTH[nxt] - 1 and p.series_id:
        tips.append(f"Your results say you're ready for the next level ({w.pyramid.tier_names[nxt]}). "
                    "The question is who pays for it.")
    cheapest = min((t.season_cost for t in w.pyramid.templates.values() if t.tier == nxt), default=None)
    if cheapest and funding < cheapest * 0.5:
        tips.append(f"Stepping up costs at least {_fmt_money(cheapest)} a season; you have about {_fmt_money(funding)}. "
                    "Pitch sponsors every off-season - marketability and results make it easier.")
    if p.program_mfr is not None:
        tips.append(f"You're in the {w.manufacturers[p.program_mfr].name} development program: their teams "
                    "look at you first and they help pay for each step. Keep progressing or they'll drop you.")
    elif 14 <= age <= 19 and p.tier >= 1:
        tips.append("Manufacturer development programs sign promising teenagers (usually 15-17). "
                    "They only sign drivers their scouts have seen win.")
    if age >= 24 and p.tier <= 3:
        tips.append("Development ladders favour teenagers. From here the realistic routes up are dominant "
                    "results plus a patron, a combine/shootout win, or money - or a long career as a local hero.")
    if p.injury_races > 0:
        tips.append(f"You're injured for {p.injury_races} more races.")
    if p.breakout:
        tips.append("People are still talking about your standout drive. This off-season is your window.")
    return tips[:4]


def _fmt_money(x: float) -> str:
    return f"${x / 1e6:.1f}M" if x >= 1e6 else f"${x / 1e3:.0f}k"


def jewels(game: "Game") -> list[dict]:
    w = game.world
    p = w.player
    runner = game.runner
    out = []
    for cj in sorted(w.pyramid.crown_jewels, key=lambda c: c.week):
        t = w.tracks.get(cj.track_id)
        res = next((o for k, o in runner.res.crown_jewel_results if k == cj.key), None) if runner else None
        item = {"key": cj.key, "name": cj.name, "week": cj.week, "label": week_label(cj.week), "track": t.name,
                "track_id": t.id, "discipline": DISC_LABEL[cj.discipline], "purse_win": cj.purse_win,
                "min_tier": cj.min_tier, "max_tier": cj.max_tier, "entrants": cj.entrants,
                "done": game.phase != "season" or cj.week <= runner.week,
                "entered": cj.key in w.player_jewels}
        if p is not None and p.status != RETIRED:
            item["eligible"] = jewel_eligible(w, p, cj)
            item["cost"] = round(jewel_entry_cost(p, t))
            if not item["eligible"]:
                why = jewel_block_reasons(w, p, cj, t)
                item["why_not"] = ", ".join(why) or "not eligible"
        hist = getattr(w, "history", None)
        if hist is not None and getattr(cj, "history_source", None):
            # Real winners before the career's start year (afterwards the world writes its own history).
            start = getattr(w.config, "start_year", w.year)
            item["real_winners"] = [{"year": y, "name": n} for y, n in hist.conn.execute(
                "SELECT year, winner FROM race WHERE source = ? AND year < ? AND winner IS NOT NULL "
                "ORDER BY year DESC LIMIT 8", (cj.history_source, start))]
        if res:
            wd = w.drivers[res[0]]
            item["winner"] = {"id": wd.id, "name": wd.name}
            if p is not None and p.id in res:
                item["player_pos"] = res.index(p.id) + 1
        out.append(item)
    return out


def news(world: "World", limit: int = 50, kind: Optional[str] = None, driver_id: Optional[int] = None) -> list[dict]:
    items = [n for n in reversed(world.news)
             if (kind is None or n["kind"] == kind) and (driver_id is None or n["driver_id"] == driver_id)]
    out = []
    for n in items[:limit]:
        x = dict(n)
        x["label"] = week_label(n["week"])
        out.append(x)
    return out


# ------------------------------------------------------------------------ browsers
def drivers_query(world: "World", q: dict) -> dict:
    tier = q.get("tier")
    disc = q.get("discipline")
    region = q.get("region")
    status_f = q.get("status", "active")
    text = (q.get("q") or "").lower().strip()
    series_id = q.get("series")
    min_age, max_age = int(q.get("min_age") or 0), int(q.get("max_age") or 200)
    rows = []
    for d in world.drivers.values():
        if status_f == "active" and (d.status == RETIRED or not d.series_id):
            continue
        if status_f == "free" and (d.status == RETIRED or d.series_id):
            continue
        if status_f == "retired" and d.status != RETIRED:
            continue
        if tier not in (None, "") and (not d.series_id or d.tier != int(tier)):
            continue
        if disc and d.primary_discipline != disc:
            continue
        if region and d.home_region != region:
            continue
        if series_id and d.series_id != series_id:
            continue
        a = d.age(world.year)
        if not (min_age <= a <= max_age):
            continue
        if text and text not in d.name.lower():
            continue
        rows.append(d)
    sort = q.get("sort", "overall")
    keyf = {
        "overall": lambda d: -scouted(world, d)["overall"], "potential": lambda d: -scouted(world, d)["potential"],
        "age": lambda d: d.age(world.year), "reputation": lambda d: -d.reputation, "wins": lambda d: -d.career_wins,
        "tier": lambda d: -(d.tier if d.series_id else -1), "name": lambda d: d.last_name,
        "titles": lambda d: -len(d.titles),
    }.get(sort, lambda d: -d.reputation)
    total = len(rows)
    if sort in ("overall", "potential") and total > 3000:
        rows.sort(key=lambda d: -d.reputation)
        rows = rows[:3000]
    rows.sort(key=keyf)
    offset, limit = max(0, int(q.get("offset") or 0)), max(1, min(int(q.get("limit") or 100), 500))
    return {"total": total, "rows": [driver_row(world, d) for d in rows[offset:offset + limit]]}


def pyramid(world: "World") -> list[dict]:
    by_tier: dict[int, dict] = {}
    counts = Counter()
    for d in world.drivers.values():
        if d.status != RETIRED and d.series_id:
            counts[world.series(d.series_id).template.key] += 1
    instances = Counter(s.template.key for s in world.pyramid.active())
    for tpl in sorted(world.pyramid.templates.values(), key=lambda t: (t.tier, t.discipline, t.key)):
        if instances[tpl.key] == 0:
            continue
        tier = by_tier.setdefault(tpl.tier, {"tier": tpl.tier, "name": world.pyramid.tier_names.get(tpl.tier),
                                             "templates": [], "drivers": 0})
        tier["drivers"] += counts[tpl.key]
        tier["templates"].append({
            "key": tpl.key, "name": tpl.name.replace("{track} ", "").replace("{region} ", ""),
            "discipline": tpl.discipline, "discipline_label": DISC_LABEL[tpl.discipline], "scope": tpl.scope,
            "instances": instances[tpl.key], "drivers": counts[tpl.key], "cost": tpl.season_cost,
            "team_based": tpl.team_based, "min_age": tpl.min_age, "max_age": tpl.max_age,
            "field": tpl.field_size, "events": tpl.events, "prestige": tpl.prestige, "visibility": tpl.visibility,
            "pro": tpl.pro, "seats": tpl.cars * tpl.drivers_per_car if tpl.team_based else None,
            "single_id": next((s.id for s in world.pyramid.active() if s.template.key == tpl.key), None)
            if instances[tpl.key] == 1 else None,
        })
    return [by_tier[t] for t in sorted(by_tier, reverse=True)]


def series_instances(world: "World", key: str) -> list[dict]:
    counts = Counter(d.series_id for d in world.drivers.values() if d.status != RETIRED and d.series_id)
    out = []
    for s in world.pyramid.active():
        if s.template.key != key:
            continue
        region = None
        if s.scope == "track":
            t = world.tracks.get(s.region_key)
            region = t.facts.region
        out.append({"id": s.id, "name": s.name, "drivers": counts[s.id], "region": region or s.region_key,
                    "type": s.template.name.replace("{track} ", "").replace("{region} ", "")})
    out.sort(key=lambda x: (x["region"] or "", x["name"]))
    return out


def series_detail(world: "World", sid: str) -> dict:
    s = world.series(sid)
    tpl = s.template
    teams = []
    for t in world.teams_in(sid):
        roster = [driver_row(world, world.drivers[x]) for x in t.roster if x is not None and x in world.drivers]
        teams.append({**team_brief(world, t.id), "cars": t.cars, "roster": roster,
                      "funding_per_seat": money(t.sponsor_funding)})
    teams.sort(key=lambda t: -t["equipment"])
    champs = []
    runner = world.season
    if runner is not None and runner.finished and runner.res.champions.get(sid) is not None:
        did = runner.res.champions[sid]
        champs.append({"year": world.year, "driver_id": did, "name": world.drivers[did].name})
    for summ in reversed(world.summaries):
        if summ.year == world.year and champs:
            continue
        did = summ.champions.get(sid)
        if did is not None:
            champs.append({"year": summ.year, "driver_id": did, "name": world.drivers[did].name})
    drivers = [] if tpl.team_based else [driver_row(world, d) for d in world.drivers.values()
                                         if d.series_id == sid and d.status != RETIRED]
    return {
        **series_brief(world, sid), "real_schedule": s.real_schedule, "dormant": s.dormant, "template": {
            "cost": tpl.season_cost, "events": tpl.events, "field": tpl.field_size, "min_age": tpl.min_age,
            "max_age": tpl.max_age, "full_age": tpl.full_age, "team_based": tpl.team_based, "pro": tpl.pro,
            "prestige": tpl.prestige, "visibility": tpl.visibility, "purse_win": tpl.purse_win,
            "scholarship": tpl.champion_scholarship, "license_min_tier": tpl.license_min_tier,
            "license_min_starts": tpl.license_min_starts, "pro_am": tpl.pro_am, "note": tpl.note,
            "drivers_per_car": tpl.drivers_per_car},
        "schedule": schedule(world, sid), "standings": standings_rows(world, sid), "teams": teams,
        "drivers": sorted(drivers, key=lambda r: -r["overall"]), "champions": champs[:25],
    }


def team_detail(world: "World", tid: int) -> dict:
    t = world.teams[tid]
    out = team_brief(world, tid)
    out.update({"series": series_brief(world, t.series_id), "home": t.home_region, "cars": t.cars,
                "drivers_per_car": t.drivers_per_car, "funding_per_seat": money(t.sponsor_funding),
                "weights": {"performance": round(t.w_performance, 2), "potential": round(t.w_potential, 2),
                            "money": round(t.w_money, 2), "marketability": round(t.w_marketability, 2)},
                "roster": [driver_row(world, world.drivers[x]) for x in t.roster if x is not None],
                "reputation": round(t.reputation)})
    return out


def tracks_query(world: "World", q: dict) -> list[dict]:
    out = []
    usage = defaultdict(set)
    for s in world.pyramid.active():
        for tid in set(s.schedule):
            usage[tid].add(s.tier)
    for t in world.tracks:
        f = t.facts
        if q.get("region") and f.region != q["region"]:
            continue
        if q.get("country") and f.country != q["country"]:
            continue
        if q.get("surface") == "dirt" and not f.is_dirt:
            continue
        if q.get("surface") == "paved" and f.is_dirt:
            continue
        if q.get("type") and f.track_type != q["type"]:
            continue
        if q.get("level") and f.level != q["level"]:
            continue
        text = (q.get("q") or "").lower()
        if text and text not in t.name.lower() and text not in (f.city or "").lower():
            continue
        out.append({"id": t.id, "name": t.display_name, "city": f.city, "region": f.region, "country": f.country,
                    "type": f.track_type, "surface": f.surface, "length": f.length_mi,
                    "banking": f.banking_deg_turns, "opened": f.opened, "active": f.active, "level": f.level,
                    "size_class": t.profile.size_class, "prestige": t.profile.prestige,
                    "lat": f.lat, "lon": f.lon, "series_tiers": sorted(usage.get(t.id, []))})
    out.sort(key=lambda r: (-r["prestige"], r["name"]))
    return out


def track_detail(world: "World", tid: str) -> dict:
    t = world.tracks.get(tid)
    d = t.to_dict()
    hosted = sorted({(s.tier, s.name, s.id) for s in world.pyramid.active() if tid in s.schedule},
                    reverse=True)
    jewels_here = [cj.name for cj in world.pyramid.crown_jewels if cj.track_id == tid]
    return {"id": t.id, "name": t.display_name, "facts": d["facts"], "profile": d["profile"], "sim": d["sim"],
            "series": [{"tier": a, "name": b, "id": c} for a, b, c in hosted], "jewels": jewels_here}


def offseason(game: "Game") -> dict:
    w = game.world
    menu = game.menu()
    choices = []
    for c in menu["choices"]:
        x = {k: v for k, v in c.items() if not k.startswith("_")}
        if "series_id" in c:
            x["series"] = series_brief(w, c["series_id"])
        if c.get("team_id") is not None:
            x["team"] = team_brief(w, c["team_id"])
        if c.get("manufacturer_id"):
            x["manufacturer"] = w.manufacturers[c["manufacturer_id"]].name
        choices.append(x)
    p = w.player
    summary = None
    if p is not None and p.history and p.history[-1].year == w.year:
        r = p.history[-1]
        summary = {"series": series_brief(w, r.series_id), "pos": r.championship_pos, "field": r.field_size,
                   "wins": r.wins, "top5": r.top5, "starts": r.starts, "avg_finish": round(r.avg_finish, 1),
                   "champion": r.champion}
    return {"choices": choices, "actions": menu["actions"], "season": summary,
            "driver": driver_detail(w, p.id) if p else None, "message": game.last_message,
            "regions": regions(w)}


def regions(world: "World") -> list[dict]:
    return [{"code": r.code, "name": r.name, "country": r.country, "macro": r.macro_region,
             "hubs": r.industry_hubs, "culture": r.culture}
            for r in sorted(world.geo.regions.values(), key=lambda r: (r.country != "USA", r.name))]


def _entry_classes(discipline: str) -> dict:
    """Entry-level classes of a starting discipline with their age windows (for the wizard)."""
    from ..world.series import load_templates
    loaded = load_templates()
    tpls = loaded[0] if isinstance(loaded, tuple) else loaded
    tpls = tpls.values() if isinstance(tpls, dict) else tpls
    entry = [t for t in tpls if t.discipline == discipline and t.tier <= 1 and not t.team_based]
    if not entry:
        return {"min_age": 5, "max_age": 50, "classes": []}
    return {"min_age": min(t.min_age for t in entry), "max_age": min(50, max(t.max_age or 50 for t in entry)),
            "classes": [{"name": t.name.replace("{track} ", "").replace("{region} ", ""), "min_age": t.min_age,
                         "max_age": t.max_age, "cost": t.season_cost} for t in sorted(entry, key=lambda t: t.min_age)]}


def setup_options() -> dict:
    from ..history.economy import price_index
    from ..world.regions import Geography
    geo = Geography.load()
    try:
        from ..history import HistoryDB
        hist = HistoryDB.load_default()
        hist_years = hist.years() if hist else []
    except Exception:  # pragma: no cover - history data optional
        hist_years = []
    return {
        "years": list(range(1995, 2027)), "price_index": {y: price_index(y) for y in range(1995, 2027)},
        "history_years": hist_years,
        "backgrounds": [{"id": k, "label": v[0], "detail": v[1], "budget": v[2]} for k, v in career.BACKGROUNDS.items()],
        "talents": [{"id": k, "label": v[0], "detail": v[1]} for k, v in career.TALENTS.items()],
        "disciplines": [{"id": k, "label": v, **_entry_classes(k)} for k, v in career.START_DISCIPLINES.items()],
        "regions": [{"code": r.code, "name": r.name, "country": r.country, "macro": r.macro_region,
                     "culture": r.culture, "hubs": r.industry_hubs, "description": geo.macro_descriptions.get(r.macro_region)}
                    for r in sorted(geo.regions.values(), key=lambda r: (r.country != "USA", r.name))],
        "all_disciplines": [{"id": k, "label": DISC_LABEL[k]} for k in DISCIPLINES],
    }
