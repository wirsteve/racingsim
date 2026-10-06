"""The driver market ("silly season") and self-funded racing decisions.

Two kinds of rides exist, mirroring the real pyramid (research A 14.4, B 10.1):

1. **Self-run** (youth, local, most regional touring, club racing): the driver's
   family/sponsors buy the car and pay to race. Choice of series depends on money,
   distance from home (travel cost), age rules and the driver's own ambition.
2. **Team seats** (development series and up): an owner fills a seat. Every seat has
   a *funding gap* = season cost - what the team raises itself. Candidates are
   scored by the owner's weights on performance, potential, money, marketability,
   and connections. A driver who cannot cover the gap needs the owner to make a
   "talent bet" (absorb the gap) -- which happens, but rarely and mostly for
   standout results, manufacturer prospects, or breakout performances.

Seats are filled from the top of the pyramid down, so each signing opens a seat
lower down: the cascade is what makes timing matter.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from ..constants import TIER_STRENGTH
from ..util import clamp, haversine_mi
from ..world.entities import ACTIVE, PART_TIME, RETIRED, SIDELINED, Driver, Team
from ..world.regions import travel_cost
from .scouting import categorize, is_aware, perceived_level, rate_for_team

if TYPE_CHECKING:
    from ..world.series import Series, SeriesTemplate
    from ..world.world import World, YearSummary


# ----------------------------------------------------------------------------- seat money
def seat_role(tpl: "SeriesTemplate", slot: int) -> str:
    if tpl.pro_am:
        return "pro" if slot % tpl.drivers_per_car == 0 else "am"
    return "any"


def seat_gap(team: Team, tpl: "SeriesTemplate", role: str) -> float:
    """USD the driver must bring for this seat (<= 0 means the team pays)."""
    per_seat = tpl.season_cost / tpl.drivers_per_car
    if tpl.pro_am:
        car_raise = team.sponsor_funding * tpl.drivers_per_car
        if role == "am":
            # The paying amateur funds most of the car (research B 4.3: $1-2M in GTD).
            return max(0.35 * tpl.season_cost, tpl.season_cost - car_raise)
        return 0.0 if car_raise >= 0.25 * tpl.season_cost else per_seat * 0.25
    return per_seat - team.sponsor_funding


def season_cost_for(world: "World", d: Driver, series: "Series") -> float:
    """Car budget plus travel from the driver's home for a self-run season."""
    tpl = series.template
    cost = tpl.season_cost
    cache = world.cache.setdefault("travel", {})
    key = (d.id, series.id, round(d.lat, 2), round(d.lon, 2))
    if key in cache:
        return cost + cache[key]
    travel = 0.0
    if tpl.scope == "track":
        miles = haversine_mi(d.lat, d.lon, series.anchor_lat, series.anchor_lon)
        if miles > 30:
            travel = tpl.events * 2 * miles * 0.9  # weekly tow with pickup + open trailer
    else:
        seen: dict[str, float] = {}
        for tid in series.schedule:
            if tid not in seen:
                t = world.tracks.get(tid)
                seen[tid] = travel_cost(d.lat, d.lon, t.facts.lat or d.lat, t.facts.lon or d.lon)
            travel += seen[tid]
        if tpl.tier <= 2:
            travel *= 0.6  # grassroots racers share rigs and skip hotels
    cache[key] = travel
    return cost + travel


def season_outlay(world: "World", d: Driver) -> float:
    """What the driver had to bring this season (self-run budget or pay-seat gap)."""
    series = world.pyramid.series.get(d.series_id) if d.series_id else None
    if series is None:
        return 0.0
    team = world.teams.get(d.team_id) if d.team_id is not None else None
    if team is None:
        return season_cost_for(world, d, series)
    if d.seat_funded or d.id not in team.roster:
        return 0.0
    slot = team.roster.index(d.id)
    return max(0.0, seat_gap(team, series.template, seat_role(series.template, slot)))


def release_seat(world: "World", d: Driver) -> Optional[tuple[Team, int]]:
    if d.team_id is None:
        return None
    team = world.teams.get(d.team_id)
    out = None
    if team is not None:
        for i, did in enumerate(team.roster):
            if did == d.id:
                team.roster[i] = None
                out = (team, i)
    d.team_id = None
    d.seat_funded = False
    d.salary = 0.0
    d.contract_years = 0
    world.seat_coverage.pop(d.id, None)
    return out


# ----------------------------------------------------------------------------- self-run
def _template_index(world: "World") -> dict[str, list["Series"]]:
    idx = world.cache.get("tpl_index")
    if idx is None:
        idx = defaultdict(list)
        for s in world.pyramid.active():
            idx[s.template.key].append(s)
        world.cache["tpl_index"] = idx
    return idx


def _region_local_index(world: "World") -> dict[tuple[str, str], list["Series"]]:
    """For each (region, template) the track-scope series sorted by distance from the region."""
    idx = world.cache.get("local_index")
    if idx is None:
        idx = {}
        tpls = _template_index(world)
        for code, region in world.geo.regions.items():
            for key, series in tpls.items():
                if not series or series[0].scope != "track":
                    continue
                ranked = sorted(series, key=lambda s: haversine_mi(region.lat, region.lon, s.anchor_lat, s.anchor_lon))
                idx[(code, key)] = ranked[:10]
        world.cache["local_index"] = idx
    return idx


def _self_run_instances(world: "World", d: Driver, tpl: "SeriesTemplate") -> list["Series"]:
    instances = _template_index(world).get(tpl.key, [])
    if not instances:
        return []
    if tpl.scope == "track":
        near = _region_local_index(world).get((d.home_region, tpl.key), [])
        scored = sorted(near, key=lambda s: haversine_mi(d.lat, d.lon, s.anchor_lat, s.anchor_lon))
        reach = tpl.regional_draw_mi * 1.6 or 150
        return [s for s in scored[:4] if haversine_mi(d.lat, d.lon, s.anchor_lat, s.anchor_lon) <= reach] or scored[:1]
    if tpl.scope == "region":
        region = world.geo.regions.get(d.home_region)
        mine = [s for s in instances if region and s.region_key == region.macro_region]
        if mine:
            return mine
        return sorted(instances, key=lambda s: haversine_mi(d.lat, d.lon, s.anchor_lat, s.anchor_lon))[:1]
    return instances


def _candidate_disciplines(world: "World", d: Driver, age: int) -> list[tuple[str, float]]:
    """(discipline, switching penalty). Youth graduate from karting/QM into cars."""
    disc = d.primary_discipline
    out = [(disc, 0.0)]
    region = world.geo.regions.get(d.home_region)
    culture = region.culture if region else {}
    if disc == "karting" and age >= 12:
        # Families who can afford the formula-car ladder keep their kids in karts longer.
        stay = 2.5 if age <= 14 and d.available_funding() >= 40_000 else 0.0
        out += [("stock_car", -2 - stay + culture.get("stock_car", 30) / 25),
                ("dirt_oval", -2 - stay + culture.get("dirt_oval", 30) / 25)]
        if age >= 16:
            out.append(("club_road", -4 + culture.get("club_road", 20) / 25))
    elif d.tier == 0 and age >= 12:
        other = "dirt_oval" if disc == "stock_car" else "stock_car"
        out.append((other, -6 + culture.get(other, 30) / 20))
    elif age >= 16 and world.rng.random() < 0.06:
        for other in ("stock_car", "dirt_oval", "club_road"):
            if other != disc:
                out.append((other, -10 + culture.get(other, 30) / 15))
    return out


def self_run_options(world: "World", d: Driver, entrant: bool = False,
                     player_view: bool = False) -> list[dict]:
    """Self-funded programmes a driver could run next season, scored as the AI would.

    ``player_view`` widens the menu for the human: every discipline and every
    regional tour (travel costs make far-away ones expensive), with no random noise.
    """
    rng = world.rng
    age = d.age(world.year) + 1
    funding = d.available_funding()
    current = d.series_id
    out = []
    if player_view:
        discs = [(x, 0.0) for x in sorted({t.discipline for t in world.pyramid.templates.values()})]
    else:
        discs = _candidate_disciplines(world, d, age)
    for disc, switch_pen in discs:
        for tpl in world.pyramid.templates.values():
            if tpl.team_based or tpl.discipline != disc:
                continue
            if age < tpl.min_age or (tpl.max_age is not None and age > tpl.max_age):
                continue
            if entrant and tpl.tier > 1:
                continue
            if player_view and tpl.scope == "region":
                instances = _template_index(world).get(tpl.key, [])
            else:
                instances = _self_run_instances(world, d, tpl)
            for s in instances:
                cost = season_cost_for(world, d, s)
                afford = funding / cost if cost else 3.0
                if afford < 0.45:
                    continue
                readiness = d.demonstrated - TIER_STRENGTH[tpl.tier]
                ambition = (d.determination - 50) / 10
                # Climbing is a young racer's game; by 30 most weekly racers race for fun.
                if tpl.tier > d.tier and tpl.tier >= 3 and age > 26:
                    ambition -= (age - 26) * 0.6
                # Racers climb as high as money and self-belief allow; surplus money
                # beyond "can afford it" adds little, being out of one's depth hurts.
                val = tpl.tier * 9 + clamp(readiness + ambition, -25, 0) * 0.7 + min(afford, 1.3) * 10 + switch_pen
                if tpl.discipline == "karting" and age <= 16:
                    val += 10  # for a kid, karting *is* the ladder (regional -> national karting)
                if afford < 0.8:
                    val -= 8  # part-time is a last resort
                if s.id == current:
                    val += 5  # inertia: most racers stay put
                elif tpl.tier > d.tier and d.series_id and (age <= 30 or tpl.tier <= 2):
                    # After 2-4 seasons at a level racers itch to step up (research A 14.1).
                    val += min(d.years_at_tier, 4) * 1.6
                if not player_view:
                    val += rng.gauss(0, 3)
                out.append({"series": s, "cost": cost, "afford": afford, "value": val,
                            "readiness": readiness})
    return out


def choose_self_run(world: "World", d: Driver, entrant: bool = False) -> bool:
    """Pick next season's self-funded program. Returns False if the driver is sidelined."""
    options = self_run_options(world, d, entrant=entrant)
    if not options:
        if d.status != RETIRED:
            d.status = SIDELINED
        d.series_id = None
        d.seasons_sidelined += 1
        return False
    best = max(options, key=lambda o: o["value"])
    enter_self_run(world, d, best["series"], best["afford"], entrant=entrant)
    _maybe_relocate(world, d)
    return True


def enter_self_run(world: "World", d: Driver, series: "Series", afford: float, entrant: bool = False) -> None:
    release_seat(world, d)
    if series.discipline != d.primary_discipline and series.tier >= 1:
        d.primary_discipline = series.discipline
    moved_up = series.tier > d.tier and not entrant
    d.series_id = series.id
    if series.tier != d.tier:
        d.years_at_tier = 0
    d.tier = series.tier
    d.max_tier = max(d.max_tier, series.tier)
    d.status = ACTIVE if afford >= 0.8 else PART_TIME
    d.seasons_sidelined = 0
    if series.scope == "track":
        d.home_track_id = series.region_key
    if moved_up and series.tier >= 3:
        d.log(world.year + 1, f"moved up to the {series.name}")


def _maybe_relocate(world: "World", d: Driver) -> None:
    """Ambitious stock-car prospects with means move to the industry hub (research C 4.6)."""
    if d.primary_discipline != "stock_car" or d.home_region == "NC":
        return
    age = d.age(world.year)
    if 17 <= age <= 25 and d.tier >= 2 and d.available_funding() >= 120_000 and world.rng.random() < 0.08:
        nc = world.geo.regions.get("NC")
        if nc:
            d.home_region = "NC"
            d.lat, d.lon = 35.5 + world.rng.uniform(-0.2, 0.2), -80.8 + world.rng.uniform(-0.2, 0.2)
            d.log(world.year, "moved to North Carolina to chase a stock car career")


# ----------------------------------------------------------------------------- team seats
def _evolve_teams(world: "World") -> None:
    """Organisations rise and fall: equipment and sponsorship drift year to year."""
    rng = world.rng
    for t in world.teams.values():
        t.equipment = clamp(t.equipment + rng.gauss(0, 2.5) + (55 - t.equipment) * 0.03, 8, 98)
        t.sponsor_funding = max(0.0, t.sponsor_funding * rng.uniform(0.88, 1.12))


def _tick_contracts(world: "World", queue: list, summary: "YearSummary") -> None:
    rng = world.rng
    coverage = world.seat_coverage
    for team in world.teams.values():
        if world.series(team.series_id).dormant:
            continue
        tpl = world.series(team.series_id).template
        for slot, did in enumerate(team.roster):
            if did is None:
                _push(queue, team, slot, tpl)
                continue
            d = world.drivers.get(did)
            if d is None or d.status == RETIRED:
                team.roster[slot] = None
                _push(queue, team, slot, tpl)
                continue
            d.contract_years -= 1
            role = seat_role(tpl, slot)
            gap = seat_gap(team, tpl, role)
            perf, _ = rate_for_team(team, d, tpl.discipline, tpl.tier, world.year, world)
            release = False
            reason = ""
            if role == "am" and categorize(d, world.year + 1) not in ("bronze", "silver"):
                release, reason = True, "was re-categorised out of the amateur seat"
            elif not d.seat_funded and gap > 0:
                cov = d.available_funding() / gap
                coverage[d.id] = min(1.0, cov)
                if cov < 0.5:
                    release, reason = True, "lost the ride when the money ran out"
            if not release and d.contract_years <= 0:
                age = d.age(world.year) + 1
                if perf > 0.8 and age < 34 and rng.random() < 0.85 and _eligible(world, d, tpl, role):
                    # Stars are locked up before their deal runs out.
                    d.contract_years = rng.randint(2, 3)
                else:
                    # Expiring deal = open seat. The incumbent stays a candidate (with the
                    # team-relationship bonus) but has to beat whoever else is available.
                    world.market.expired[d.id] = team.id
                    release, reason = True, ""
                    if not d.seat_funded and gap > 0:
                        coverage.pop(d.id, None)
            elif not release and d.seat_funded and perf < -1.4 and rng.random() < 0.35:
                release, reason = True, "was released for poor results"
            if release:
                if tpl.tier >= 4 and reason:
                    d.log(world.year, f"{reason} at {team.name} ({world.series(team.series_id).name})")
                release_seat(world, d)
                d.series_id = None
                _push(queue, team, slot, tpl)


def _push(queue: list, team: Team, slot: int, tpl: "SeriesTemplate") -> None:
    heapq.heappush(queue, (-tpl.tier, -team.equipment, team.id, slot))


def _candidate_buckets(world: "World") -> dict[int, list[Driver]]:
    """Drivers worth considering for seats at each tier (prefilter for speed)."""
    buckets: dict[int, list[Driver]] = defaultdict(list)
    for d in world.drivers.values():
        if d.status == RETIRED or d.injury_races > 12:
            continue
        age = d.age(world.year) + 1
        if age < 14:
            continue
        rich = d.available_funding()
        for tier in range(2, 8):
            near_tier = d.max_tier >= tier - 2 or d.tier >= tier - 2
            shown = d.demonstrated >= TIER_STRENGTH[tier] - 3
            funded = rich >= 100_000 * (2 ** (tier - 2)) * 0.5 and d.max_tier >= tier - 3
            if near_tier or shown or funded:
                buckets[tier].append(d)
    return buckets


def _would_accept(world: "World", d: Driver, team: Team, tpl: "SeriesTemplate") -> bool:
    if d.grassroots_veteran and tpl.tier >= 4:
        # Decided once per off-season in run_market: the occasional comeback.
        return d.id in world.market.comeback_open
    cur_tier = d.tier if d.series_id else -1
    if d.team_id is not None and d.series_id and d.contract_years > 0:
        return tpl.tier > cur_tier  # only leave a contract for a promotion
    graduating = d.primary_discipline == "karting" and tpl.discipline == "open_wheel"
    if tpl.discipline != d.primary_discipline and not graduating:
        # Karting -> junior formula is the normal ladder, not a sideways move.
        # Most drivers stay in their discipline. Each off-season a minority are open to a
        # sideways move (more so when stalled or without a ride), and then only for a
        # step up or when the alternative is not racing at all (research C 4.5/5.6).
        if d.id not in world.market.switch_open:
            return False
        if not (tpl.tier > cur_tier or d.series_id is None):
            return False
    if tpl.tier > cur_tier:
        return True
    if tpl.tier == cur_tier:
        cur_team = world.teams.get(d.team_id) if d.team_id else None
        cur_eq = cur_team.equipment if cur_team else 50
        return d.series_id is None or team.equipment > cur_eq + 5
    # A step down: veterans take it to keep racing professionally.
    return d.series_id is None and (cur_tier - tpl.tier) <= 2


def _utility(world: "World", team: Team, tpl: "SeriesTemplate", role: str, gap: float,
             d: Driver, rng=None) -> tuple[float, float, bool]:
    """(utility, funding coverage, team absorbs gap)."""
    rng = rng or world.rng
    perf, pot = rate_for_team(team, d, tpl.discipline, tpl.tier, world.year, world)
    funding = d.available_funding()
    absorbed = False
    if gap > 0:
        coverage = funding / gap
        money = clamp(coverage, 0, 1.5)
    else:
        coverage = 1.0
        money = clamp(funding / max(1.0, tpl.season_cost), 0, 0.5)
    market = (d.marketability - 50) / 25 + d.reputation / 100
    conn = d.connections.get(f"team:{team.id}", 0.0)
    if team.manufacturer_id is not None:
        conn += 0.8 * d.connections.get(f"mfr:{team.manufacturer_id}", 0.0)
    conn += 0.5 * d.connections.get(f"target:{tpl.key}", 0.0)
    if d.home_region == team.home_region:
        conn += 0.1
    u = (team.w_performance * perf * 1.6 + team.w_potential * pot + team.w_money * money * 2.2
         + team.w_marketability * market + 0.6 * conn + d.professionalism / 400 + rng.gauss(0, 0.25))
    # Development ladders are for young drivers: owners (and the families paying) invest in
    # teenagers, not 35-year-olds (research A 6, B 2.5). Older money goes to Pro-Am seats.
    age = d.age(world.year) + 1
    if role != "am" and not tpl.pro_am:
        over = age - tpl.typical_age[1]
        if over > 0:
            u -= over * (0.35 if tpl.tier <= 5 else 0.2)
    if tpl.pro_am or tpl.drivers_per_car > 1:
        cat = categorize(d, world.year + 1)
        if role == "am":
            u += {"bronze": 1.2, "silver": 0.3}.get(cat, -9)
        elif tpl.pro_am:
            u += {"platinum": 0.5, "gold": 0.4, "silver": 0.0}.get(cat, -0.5)
        else:
            # All-pro lineups (prototype / GT Pro): rated professionals only.
            u += {"platinum": 0.6, "gold": 0.4, "silver": -0.3}.get(cat, -9)
    if gap > 0 and coverage < 0.5:
        # Talent bet: owner finds the money for a standout (Bell/Larson/Chastain patterns).
        bet = (perf - 0.9) * 0.35 + (team.reputation - 50) / 250 + 0.35 * conn + (0.25 if d.breakout else 0)
        if role != "am" and rng.random() < clamp(bet, 0, 0.85):
            absorbed = True
            coverage = 1.0
    return u, coverage, absorbed


def _eligible(world: "World", d: Driver, tpl: "SeriesTemplate", role: str) -> bool:
    age = d.age(world.year) + 1
    if age < tpl.min_age or (tpl.max_age is not None and age > tpl.max_age):
        return False
    if d.max_tier < tpl.license_min_tier and not (role == "am" and d.max_tier >= tpl.license_min_tier - 2):
        return False
    if d.career_starts < tpl.license_min_starts:
        return False
    return True


def open_market(world: "World", summary: "YearSummary") -> None:
    """Contracts tick; open seats are queued. The player may act before close_market."""
    rng = world.rng
    _evolve_teams(world)
    m = world.market
    m.expired = {}
    m.queue = []
    m.signed = set()
    _tick_contracts(world, m.queue, summary)
    m.buckets = _candidate_buckets(world)
    m.switch_open = {
        d.id for d in world.drivers.values()
        if d.status != RETIRED and rng.random() < (
            0.08 + d.adaptability / 600 + (0.15 if d.status == SIDELINED or d.years_at_tier >= 3 else 0.0))}
    m.comeback_open = {
        d.id for d in world.drivers.values()
        if d.grassroots_veteran and d.status != RETIRED and rng.random() < 0.08}


def run_market(world: "World", summary: "YearSummary") -> None:
    open_market(world, summary)
    close_market(world, summary)


def close_market(world: "World", summary: "YearSummary") -> None:
    rng = world.rng
    coverage = world.seat_coverage
    m = world.market
    queue, buckets, signed = m.queue, m.buckets, m.signed
    deferred: list = []

    while queue:
        neg_tier, _, team_id, slot = heapq.heappop(queue)
        team = world.teams[team_id]
        if team.roster[slot] is not None:
            continue
        s = world.series(team.series_id)
        tpl = s.template
        role = seat_role(tpl, slot)
        gap = seat_gap(team, tpl, role)
        pool = buckets.get(tpl.tier, [])
        if role == "am":
            pool = [d for d in world.drivers.values()
                    if d.status != RETIRED and d.available_funding() >= gap * 0.5 and d.age(world.year) >= 25]
        sample = pool if len(pool) <= 350 else rng.sample(pool, 350)
        best = None
        for d in sample:
            if d.id in signed or d.status == RETIRED or d.injury_races > 12 or d.is_player:
                continue
            if not _eligible(world, d, tpl, role):
                continue
            prof = d.proficiency.get(tpl.discipline, 0.0)
            if (prof < 0.12 and d.max_tier < tpl.tier and role != "am"
                    and not (d.primary_discipline == "karting" and tpl.discipline == "open_wheel")):
                continue
            conn = d.connections.get(f"team:{team.id}", 0) + (
                d.connections.get(f"mfr:{team.manufacturer_id}", 0) if team.manufacturer_id else 0)
            if not is_aware(world, tpl.tier, team.home_region, tpl.discipline, d, connection=conn * 0.5):
                continue
            if role == "am" and categorize(d, world.year + 1) not in ("bronze", "silver"):
                continue
            if not _would_accept(world, d, team, tpl):
                continue
            u, cov, absorbed = _utility(world, team, tpl, role, gap, d)
            if cov < 0.5 and not absorbed:
                continue
            if best is None or u > best[0]:
                best = (u, d, cov, absorbed)
        if best is None:
            deferred.append((team, slot))
            continue
        _, d, cov, absorbed = best
        _sign(world, d, team, slot, s, gap, cov, absorbed, summary, queue)
        signed.add(d.id)

    # Second pass: owners would rather run an under-funded car than park it.
    for team, slot in deferred:
        if team.roster[slot] is not None:
            continue
        s = world.series(team.series_id)
        tpl = s.template
        role = seat_role(tpl, slot)
        gap = seat_gap(team, tpl, role)
        pool = [d for d in buckets.get(tpl.tier, []) if d.id not in signed and d.team_id is None
                and d.status != RETIRED and not d.is_player and _eligible(world, d, tpl, role)
                and (d.proficiency.get(tpl.discipline, 0) >= 0.12
                     or (d.primary_discipline == "karting" and tpl.discipline == "open_wheel"))]
        if role == "am":
            pool = [d for d in pool if categorize(d, world.year + 1) in ("bronze", "silver")]
        best = None
        for d in pool if len(pool) <= 200 else rng.sample(pool, 200):
            funding = d.available_funding()
            cov = 1.0 if gap <= 0 else funding / gap
            if cov < 0.25:
                continue
            score = perceived_level(d, tpl.discipline) + cov * 10 + rng.gauss(0, 3)
            over = d.age(world.year) + 1 - tpl.typical_age[1]
            if over > 0 and role != "am" and not tpl.pro_am:
                score -= over * 2.0
            if best is None or score > best[0]:
                best = (score, d, min(cov, 1.0))
        if best is None and role == "am" and rng.random() < 0.75:
            # Pro-Am seats are bought by people who made their money elsewhere (research B 4.3).
            d = _gentleman_driver(world, tpl, gap)
            summary.new_entrants += 1
            best = (0.0, d, 1.0)
        if best is not None:
            _, d, cov = best
            _sign(world, d, team, slot, s, gap, cov, False, summary, None)
            signed.add(d.id)

    for did in world.market.expired:
        d = world.drivers[did]
        if d.team_id is None and d.max_tier >= 4:
            d.log(world.year, "was not re-signed when the contract expired")

    # Everyone without a team seat decides their own programme.
    for d in list(world.drivers.values()):
        if d.status == RETIRED or d.team_id is not None or d.is_player:
            continue
        choose_self_run(world, d)
    for did in [k for k in coverage if world.drivers.get(k) is None or world.drivers[k].team_id is None]:
        coverage.pop(did, None)


def _gentleman_driver(world: "World", tpl: "SeriesTemplate", gap: float) -> Driver:
    from ..world.factory import ability_for_tier, make_driver
    rng = world.rng
    age = int(clamp(rng.gauss(46, 8), 30, 68))
    d = make_driver(world, discipline="club_road", age=age, region=world.geo.random_home(rng, tpl.discipline),
                    ability=ability_for_tier(rng, max(0, tpl.tier - 2)), years_racing=rng.uniform(2, 10),
                    budget_floor=gap * 1.1)
    d.first_license_age = max(30, age - 8)
    d.first_season = world.year - 3
    d.proficiency[tpl.discipline] = max(d.proficiency.get(tpl.discipline, 0), 0.55)
    d.max_tier = max(d.max_tier, tpl.tier - 2)
    d.career_starts = max(d.career_starts, tpl.license_min_starts)
    d.reputation = clamp(10 + tpl.tier * 5 + rng.gauss(0, 5))
    world.drivers[d.id] = d
    d.log(world.year, "bought into a Pro-Am seat after success outside racing")
    return d


def _sign(world: "World", d: Driver, team: Team, slot: int, s: "Series", gap: float, cov: float,
          absorbed: bool, summary: "YearSummary", queue: Optional[list]) -> None:
    tpl = s.template
    rng = world.rng
    coverage = world.seat_coverage
    old = release_seat(world, d)
    if old is not None and queue is not None:
        old_team, old_slot = old
        _push(queue, old_team, old_slot, world.series(old_team.series_id).template)
    prev_tier = d.tier if d.series_id else -1
    team.roster[slot] = d.id
    d.team_id = team.id
    d.series_id = s.id
    d.status = ACTIVE
    d.seasons_sidelined = 0
    funded = gap <= 0 or absorbed
    d.seat_funded = funded
    if funded:
        coverage.pop(d.id, None)
    else:
        coverage[d.id] = min(1.0, cov)
    perf, _ = rate_for_team(team, d, tpl.discipline, tpl.tier, world.year, world)
    d.contract_years = 1 if not funded else rng.randint(1, 3 if perf > 0.5 else 2)
    if funded and tpl.pro:
        d.salary = tpl.salary_top * clamp(0.15 + 0.2 * perf + (team.equipment - 40) / 120, 0.03, 1.2)
    else:
        d.salary = 0.0
    if tpl.discipline != d.primary_discipline and tpl.tier >= 3:
        d.primary_discipline = tpl.discipline
    if tpl.tier != d.tier:
        d.years_at_tier = 0
    d.tier = tpl.tier
    d.connections[f"team:{team.id}"] = max(d.connections.get(f"team:{team.id}", 0), 0.4)
    if tpl.tier > d.max_tier:
        summary.promotions += 1
        if tpl.tier == 7:
            summary.first_top_tier.append(d.id)
            d.log(world.year + 1, f"earned a first premier-level ride with {team.name} ({s.name}) at {d.age(world.year + 1)}")
    d.max_tier = max(d.max_tier, tpl.tier)
    resigned = world.market.expired.get(d.id) == team.id
    if not resigned and (tpl.tier >= 3 and tpl.tier != prev_tier or (tpl.tier >= 5 and old is None)):
        how = "funded seat" if funded else f"bringing ${min(gap, d.available_funding()):,.0f}"
        if absorbed:
            how = "team found the funding"
        d.log(world.year + 1, f"signed with {team.name} in the {s.name} ({how})")
    summary.signings.append(f"{d.name} -> {team.name} [{s.name}]")
