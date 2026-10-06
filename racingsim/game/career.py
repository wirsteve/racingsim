"""Career mode: the human's driver.

The player's driver is an ordinary ``Driver`` with ``is_player=True``. The world
treats them exactly like everyone else (same scouting, same owners, same money
rules); the only difference is that the AI never makes the player's decisions.
Instead, each off-season the player is shown:

* **team offers**: open seats where the owner would genuinely pick the player over
  the competition (evaluated with the same utility the AI market uses);
* **self-run programmes** they can afford, in any discipline, with travel costs;
* staying put, sitting out a season, or retiring;

plus once-per-off-season actions (pitch sponsors, hire a coach, relocate).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from ..constants import TIER_STRENGTH
from ..util import clamp
from ..world.entities import RETIRED, SIDELINED, Driver
from ..world.factory import make_driver

if TYPE_CHECKING:
    from ..world.world import World, YearSummary

BACKGROUNDS = {
    "modest": ("Working-class family", "Every dollar is hard to find. Cheap classes, used parts.", 6_500),
    "middle": ("Middle-class family", "Weekends at the track are the family hobby.", 12_000),
    "comfortable": ("Comfortable family", "Enough to run a competitive local programme.", 35_000),
    "wealthy": ("Wealthy family", "Can fund a serious regional or junior-formula programme.", 150_000),
    "dynasty": ("Racing dynasty / family business", "Money opens national-level doors. Results still matter.", 600_000),
}
TALENTS = {
    "unknown": ("Unknown", "Nobody knows yet - including you.", None),
    "solid": ("Solid", "A good racer with room to grow.", (60, 72)),
    "gifted": ("Gifted", "Scouts will notice, if they ever see you race.", (72, 84)),
    "generational": ("Generational", "The kind of talent that comes along a few times a decade.", (84, 95)),
}
START_DISCIPLINES = {
    "karting": "Karting",
    "stock_car": "Asphalt ovals (quarter midgets, Bandolero, Legends, street stocks)",
    "dirt_oval": "Dirt ovals (micro sprints, hobby stocks)",
    "club_road": "Club road racing (adults)",
}


def create_player(world: "World", first: str, last: str, region: str, age: int, discipline: str,
                  background: str, talent: str = "unknown") -> Driver:
    if region not in world.geo.regions:
        raise ValueError(f"unknown home region {region!r}")
    if background not in BACKGROUNDS:
        raise ValueError(f"unknown background {background!r}")
    if discipline not in START_DISCIPLINES:
        raise ValueError(f"unknown discipline {discipline!r}")
    age = int(age)
    lo, hi = entry_ages(world, discipline)
    if not lo <= age <= hi:
        raise ValueError(f"{START_DISCIPLINES[discipline].split(' (')[0]} entry classes take drivers aged {lo}-{hi}.")
    if talent not in TALENTS:
        raise ValueError(f"unknown talent {talent!r}")
    rng = world.rng
    reg = world.geo.get(region)
    if age < 18:
        ability = clamp(TIER_STRENGTH[0] + (age - 8) * 0.9 + rng.gauss(0, 3), 15, 55)
    else:
        ability = clamp(33 + rng.gauss(0, 3), 20, 50)
    d = make_driver(world, discipline=discipline, age=age, region=reg, ability=ability, years_racing=0.3)
    d.first_name, d.last_name = (first.strip() or "Rookie"), (last.strip() or "Racer")
    d.is_player = True
    d.family_budget = BACKGROUNDS[background][2] * rng.uniform(0.9, 1.1)
    d.sponsors.clear()
    d.savings = 0.0
    d.first_license_age = age
    d.first_season = world.year
    d.reputation = 1.0
    d.exposure = 0.0
    band = TALENTS.get(talent, TALENTS["unknown"])[2]
    if band:
        d.potential = max(rng.uniform(*band), d.ability + 8)
        d.peak_age = clamp(rng.gauss(29, 2), 25, 33)
    d.demonstrated = d.ability
    world.drivers[d.id] = d
    world.player_id = d.id
    _place_entrant(world, d, discipline)
    d.log(world.year, f"started racing at {age} in the {world.series(d.series_id).name}")
    return d


def entry_ages(world: "World", discipline: str) -> tuple[int, int]:
    """Age range of the entry-level (tier 0-1) self-run classes of a discipline."""
    tpls = [t for t in world.pyramid.templates.values()
            if t.discipline == discipline and t.tier <= 1 and not t.team_based]
    if not tpls:
        return 5, 50
    return min(t.min_age for t in tpls), min(50, max(t.max_age or 50 for t in tpls))


def _place_entrant(world: "World", d: Driver, discipline: str) -> None:
    from ..career.market import enter_self_run, self_run_options
    # Age for the coming (current) season, not the next one.
    d.birth_year += 1
    try:
        options = [o for o in self_run_options(world, d, entrant=True, player_view=True)
                   if o["series"].discipline == discipline]
    finally:
        d.birth_year -= 1
    if not options:
        del world.drivers[d.id]
        world.player_id = None
        raise ValueError(f"Your family can't stretch to a {START_DISCIPLINES[discipline].split(' (')[0].lower()} "
                         "season from that home town. Try a cheaper discipline or a different background.")
    # Nearest, cheapest sensible entry: highest value among affordable options.
    # Highest entry class the family can properly afford; cheaper if tied.
    best = max(options, key=lambda o: (o["afford"] >= 0.8, o["series"].tier, -o["cost"]))
    enter_self_run(world, d, best["series"], best["afford"], entrant=True)


# ---------------------------------------------------------------------------- off-season menu
def team_offers(world: "World", d: Driver) -> list[dict]:
    """Open seats whose owner would pick the player over the field right now."""
    from ..career.market import _eligible, _utility, _would_accept, seat_gap, seat_role
    from ..career.scouting import categorize, is_aware, rate_for_team
    m = world.market
    rng = random.Random(world.config.seed * 1_000_003 + world.year * 7919 + d.id)
    offers: list[dict] = []
    seen: set[int] = set()
    under_contract = d.team_id is not None and d.contract_years > 0
    for _, _, team_id, slot in sorted(m.queue):
        team = world.teams[team_id]
        if team.roster[slot] is not None or team_id in seen:
            continue
        s = world.series(team.series_id)
        tpl = s.template
        role = seat_role(tpl, slot)
        if under_contract and tpl.tier <= d.tier:
            continue
        if not _eligible(world, d, tpl, role):
            continue
        if d.proficiency.get(tpl.discipline, 0.0) < 0.12 and d.max_tier < tpl.tier and role != "am":
            continue
        if role == "am" and categorize(d, world.year + 1) not in ("bronze", "silver"):
            continue
        conn = d.connections.get(f"team:{team.id}", 0) + (
            d.connections.get(f"mfr:{team.manufacturer_id}", 0) if team.manufacturer_id else 0)
        if not is_aware(world, tpl.tier, team.home_region, tpl.discipline, d, connection=conn * 0.5, rng=rng):
            continue
        gap = seat_gap(team, tpl, role)
        u, cov, absorbed = _utility(world, team, tpl, role, gap, d, rng=rng)
        if cov < 0.5 and not absorbed:
            continue
        pool = m.buckets.get(tpl.tier, [])
        best_ai = -1e9
        for c in rng.sample(pool, min(120, len(pool))):
            if c.is_player or c.id in m.signed or c.status == RETIRED or c.team_id == team.id:
                continue
            if not _eligible(world, c, tpl, role) or not _would_accept(world, c, team, tpl):
                continue
            if c.proficiency.get(tpl.discipline, 0.0) < 0.12 and c.max_tier < tpl.tier:
                continue
            uc, cc, ab = _utility(world, team, tpl, role, gap, c, rng=rng)
            if cc >= 0.5 or ab:
                best_ai = max(best_ai, uc)
        if u < best_ai - 0.2:
            continue
        seen.add(team_id)
        funded = gap <= 0 or absorbed
        perf, _ = rate_for_team(team, d, tpl.discipline, tpl.tier, world.year, world)
        salary = 0.0
        if funded and tpl.pro:
            salary = tpl.salary_top * clamp(0.15 + 0.2 * perf + (team.equipment - 40) / 120, 0.03, 1.2)
        offers.append({
            "id": f"team:{team.id}:{slot}", "kind": "team", "team_id": team.id, "slot": slot,
            "series_id": s.id, "tier": tpl.tier, "discipline": tpl.discipline, "role": role,
            "equipment": round(team.equipment), "funded": funded, "absorbed": absorbed,
            "bring": 0.0 if funded else round(min(gap, d.available_funding())), "gap": round(max(gap, 0)),
            "coverage": round(min(cov, 1.0), 2), "salary": round(salary), "manufacturer_id": team.manufacturer_id,
            "own_team": d.team_id == team.id or m.expired.get(d.id) == team.id,
            "_gap": gap, "_cov": cov,
        })
    offers.sort(key=lambda o: (-o["tier"], not o["funded"], -o["equipment"]))
    return offers[:12]


def self_run_menu(world: "World", d: Driver) -> list[dict]:
    from ..career.market import self_run_options
    opts = self_run_options(world, d, player_view=True)
    out = []
    for o in opts:
        s = o["series"]
        out.append({"id": f"self:{s.id}", "kind": "self", "series_id": s.id, "tier": s.tier,
                    "discipline": s.discipline, "cost": round(o["cost"]), "afford": round(o["afford"], 2),
                    "part_time": o["afford"] < 0.8, "readiness": round(o["readiness"], 1),
                    "current": s.id == d.series_id, "_afford": o["afford"]})
    # Best few per (tier, discipline) so the menu stays readable.
    out.sort(key=lambda o: (-o["tier"], -min(o["afford"], 1.3), o["cost"]))
    kept, per = [], {}
    for o in out:
        key = (o["tier"], o["discipline"])
        if per.get(key, 0) < 3 or o["current"]:
            kept.append(o)
            per[key] = per.get(key, 0) + 1
    return kept[:40]


def offseason_menu(world: "World") -> dict:
    d = world.player
    m = world.market
    if d is None or d.status == RETIRED:
        return {"choices": [{"id": "continue", "kind": "continue"}], "actions": []}
    if getattr(m, "player_offers", None) is None:
        m.player_offers = team_offers(world, d)
    choices: list[dict] = []
    if d.team_id is not None and d.contract_years > 0:
        choices.append({"id": "stay", "kind": "stay", "team_id": d.team_id, "series_id": d.series_id,
                        "contract_years": d.contract_years})
    choices += m.player_offers
    choices += self_run_menu(world, d)
    from . import owner
    own = owner.drive_choice(world, d)
    if own is not None:
        choices.insert(0, own)
    choices.append({"id": "sit_out", "kind": "sit_out"})
    choices.append({"id": "retire", "kind": "retire"})
    coach_cost = 5_000 * (1 + d.tier)
    actions = [
        {"id": "pitch", "label": "Pitch to sponsors", "used": "pitch" in m.player_actions,
         "detail": "Make the rounds with local and regional businesses (national brands if you race nationally)."},
        {"id": "coach", "label": f"Hire a driver coach (${coach_cost:,.0f})", "used": "coach" in m.player_actions,
         "cost": coach_cost, "detail": "Off-season coaching and sim work: a development boost if you can afford it."},
        {"id": "relocate", "label": "Relocate ($12,000)", "used": "relocate" in m.player_actions, "cost": 12_000,
         "detail": "Move closer to a racing hub (e.g. North Carolina for stock cars, Indiana for open wheel)."},
    ]
    from ..ui.api import SCOUTING_LEVELS
    from ..world.skills import FOCUS
    cur_focus = d.dev_focus or ""
    actions.append({"id": "focus", "label": "Development focus",
                    "detail": "What you work on this winter and next season: the chosen skills grow half again as "
                              "fast, the rest a little slower. A track-type focus is a winter of sim and test days.",
                    "options": [{"value": "", "label": "Balanced", "selected": not cur_focus}]
                    + [{"value": k, "label": v[0], "selected": k == cur_focus} for k, v in FOCUS.items()]})
    tier_mult = max(1, d.tier if d.series_id else 1)
    level = world.__dict__.get("scouting_level", "standard")
    actions.append({"id": "scouting", "label": "Scouting budget",
                    "detail": "How well you can read other drivers next season: better scouting means sharper reports "
                              "on rivals, teammates and the drivers you might hire.",
                    "options": [{"value": k, "label": f"{k.title()}" + (f" (${v[1] * tier_mult:,.0f})" if v[1] else ""),
                                 "selected": k == level} for k, v in SCOUTING_LEVELS.items()]})
    for a in owner.actions(world, d):
        a["used"] = a["id"] in m.player_actions
        actions.append(a)
    return {"choices": choices, "actions": actions}


def apply_choice(world: "World", summary: "YearSummary", option_id: str) -> str:
    from ..career.lifecycle import retire
    from ..career.market import _sign, enter_self_run, release_seat
    d = world.player
    if d is None or d.status == RETIRED:
        return "Career over - the world keeps turning."
    menu = offseason_menu(world)
    choice = next((c for c in menu["choices"] if c["id"] == option_id), None)
    if choice is None:
        raise ValueError("That option is no longer available.")
    kind = choice["kind"]
    if kind == "team":
        team = world.teams[choice["team_id"]]
        s = world.series(team.series_id)
        _sign(world, d, team, choice["slot"], s, choice["_gap"], choice["_cov"], choice["absorbed"],
              summary, world.market.queue)
        world.market.signed.add(d.id)
        if choice["funded"] and not choice["absorbed"]:
            pass
        return f"Signed with {team.name} for the {s.name}."
    if kind == "self":
        s = world.series(choice["series_id"])
        _vacate(world, d)
        enter_self_run(world, d, s, choice["_afford"])
        return f"You'll run your own car in the {s.name}" + (" (part-time - money is tight)." if choice["part_time"] else ".")
    if kind == "stay":
        return "Staying put for another season."
    if kind == "own_team":
        from . import owner
        return owner.drive(world, d, summary)
    if kind == "sit_out":
        _vacate(world, d)
        d.series_id = None
        d.status = SIDELINED
        d.seasons_sidelined += 1
        d.log(world.year + 1, "sat out the season")
        return "You'll sit out next season."
    if kind == "retire":
        _vacate(world, d)
        retire(world, d, summary)
        return "You hang up the helmet."
    return "OK"


def apply_action(world: "World", action: str, arg: Optional[str] = None) -> str:
    from ..career.sponsorship import pitch_for_player
    d = world.player
    m = world.market
    if d is None or d.status == RETIRED:
        return "No active career."
    if action in m.player_actions:
        return "You've already done that this off-season."
    from . import owner
    if action in ("found_team", "team_budget", "team_priority", "sell_team"):
        msg = owner.act(world, d, action, arg)
        if not msg.startswith(("Pick", "You already", "You don't", "Starting a team")):
            m.player_actions.add(action)
        return msg
    if action == "focus":
        from ..world.skills import FOCUS
        if arg not in FOCUS and arg not in ("", None):
            return "Pick a focus."
        d.dev_focus = arg or ""
        m.player_actions.add("focus")
        return f"Focus: {FOCUS[arg][0].lower()}." if arg else "A balanced program: no special focus."
    if action == "scouting":
        from ..ui.api import SCOUTING_LEVELS
        if arg not in SCOUTING_LEVELS:
            return "Pick a scouting budget."
        cost = SCOUTING_LEVELS[arg][1] * max(1, d.tier if d.series_id else 1)
        if cost and d.savings * 0.75 + d.available_funding() < cost:
            return "You can't afford that scouting budget."
        if cost:
            _spend(d, cost)
        world.scouting_level = arg
        m.player_actions.add("scouting")
        return f"Scouting set to {arg} for next season" + (f" (${cost:,.0f})." if cost else ".")
    if action == "pitch":
        m.player_actions.add("pitch")
        msg = pitch_for_player(world, d)
    elif action == "coach":
        cost = 5_000 * (1 + d.tier)
        if d.savings * 0.75 + d.available_funding() < cost:
            return "You can't afford a coach right now."
        _spend(d, cost)
        m.player_actions.add("coach")
        gain = min(max(0.0, d.potential - d.ability), world.rng.uniform(0.6, 1.8))
        d.ability += gain
        for disc in list(d.proficiency):
            if disc == d.primary_discipline:
                d.proficiency[disc] = round(min(1.0, d.proficiency[disc] + 0.04), 3)
        msg = "Long winter of coaching and sim sessions. You feel sharper." if gain > 0.4 else \
              "The coach says you're close to what you can be."
    elif action == "relocate":
        if not isinstance(arg, str) or arg not in world.geo.regions:
            return "Pick a region to move to."
        if d.savings * 0.75 + d.available_funding() < 12_000:
            return "You can't afford the move."
        _spend(d, 12_000)
        r = world.geo.get(arg)
        d.home_region = r.code
        d.country = r.country
        d.lat, d.lon = r.lat + world.rng.uniform(-0.3, 0.3), r.lon + world.rng.uniform(-0.3, 0.3)
        m.player_actions.add("relocate")
        d.log(world.year, f"moved to {r.name}")
        msg = f"Moved to {r.name}. New tracks, new people, new costs."
    else:
        return "Unknown action."
    m.player_offers = None  # money/location changed: owners re-evaluate
    return msg


def _spend(d: Driver, amount: float) -> None:
    """Savings first; the rest comes out of next season's racing money, not the family's yearly budget."""
    from ..sim.season import charge
    charge(d, amount)


def _vacate(world: "World", d: Driver) -> None:
    """Walking away from a team seat puts it back on the market for the AI to fill."""
    from ..career.market import _push, release_seat
    old = release_seat(world, d)
    if old is not None:
        team, slot = old
        _push(world.market.queue, team, slot, world.series(team.series_id).template)
