"""How the paddock *perceives* drivers: results-based levels, exposure, reputation.

Teams never read a driver's hidden ability. They see:

* ``demonstrated`` -- a results-based estimate of level, adjusted for the tier the
  results came in and for equipment (beating your car's expected finish counts);
* ``exposure`` -- how visible the driver was this year (series visibility, wins,
  titles, crown-jewel results, substitute drives, home-region industry hubs);
* ``reputation`` -- a slow-moving paddock standing.

Because exposure gates *awareness*, a dominant driver at an unstreamed bullring in
a remote region can stay invisible -- the "never got the call" story (R2.3).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from ..constants import NOTICE_THRESHOLD, TIER_SPREAD, TIER_STRENGTH
from ..util import clamp, logistic
from ..world.entities import RETIRED, SIDELINED, Driver, SeasonRecord

if TYPE_CHECKING:
    from ..sim.season import SeasonResults
    from ..world.entities import Team
    from ..world.world import World


def record_percentiles(rec: SeasonRecord) -> tuple[float, float]:
    fin, exp = rec.note.split("|")
    return float(fin), float(exp)


def season_level(rec: SeasonRecord) -> tuple[float, float]:
    """(demonstrated level, reliability) implied by one season's results."""
    fin, exp = record_percentiles(rec)
    perf = fin + 0.45 * (fin - exp)              # beating your equipment counts
    level = TIER_STRENGTH[rec.tier] + (perf - 0.5) * 2.4 * TIER_SPREAD[rec.tier]
    level += 2.0 * rec.champion + min(rec.wins, 6) * 0.4
    reliability = min(1.0, rec.starts / 10)
    return level, reliability


def update_after_season(world: "World", results: "SeasonResults") -> None:
    hub_cache = {}
    jewel_pos: dict[int, int] = {}
    jewel_vis: dict[str, int] = {cj.key: cj.visibility for cj in world.pyramid.crown_jewels}
    jewel_hits: dict[int, float] = {}
    for key, order in results.crown_jewel_results:
        vis = jewel_vis.get(key, 60)
        for pos, did in enumerate(order, start=1):
            if pos == 1:
                jewel_hits[did] = jewel_hits.get(did, 0) + vis * 0.55
            elif pos <= 5:
                jewel_hits[did] = jewel_hits.get(did, 0) + vis * 0.15
            elif pos <= 10:
                jewel_hits[did] = jewel_hits.get(did, 0) + vis * 0.05

    for d in world.drivers.values():
        if d.status == RETIRED:
            continue
        rec = results.records.get(d.id)
        new_exposure = 0.0
        if rec is not None:
            level, rel = season_level(rec)
            w = 0.55 * rel
            d.demonstrated = d.demonstrated * (1 - w) + level * w
            fin, _ = record_percentiles(rec)
            vis = world.series(rec.series_id).template.visibility
            new_exposure += vis * (0.25 + 0.75 * fin ** 2) + min(rec.wins, 8) * vis * 0.03
            if rec.champion:
                new_exposure += vis * 0.35
            if d.age(world.year) <= 19 and rec.tier <= 3:
                # A teenager winning at the local level gets talked about: word travels to
                # regional owners and manufacturer scouts faster than results alone suggest.
                new_exposure += min(rec.wins, 8) * 1.5 + (6 if rec.champion else 0)
            d.momentum = clamp(d.momentum * 0.5 + (fin - 0.5) * 40, -50, 50)
            # Reputation drifts toward what the driver has shown at this level.
            target = clamp(rec.tier * 9 + fin * 25 + (12 if rec.champion else 0))
            d.reputation = clamp(d.reputation * 0.75 + target * 0.25)
        else:
            d.demonstrated -= 0.6 if d.status == SIDELINED else 0.2
            d.reputation *= 0.85 if d.status == SIDELINED else 0.95
            d.momentum *= 0.5
        new_exposure += jewel_hits.get(d.id, 0)
        if d.breakout > 0:
            new_exposure += 25
        # Industry hubs: racing near Charlotte/Indianapolis puts you in front of decision makers.
        region = world.geo.regions.get(d.home_region)
        if region is not None:
            key = (region.code, d.primary_discipline)
            if key not in hub_cache:
                hub_cache[key] = max(region.industry_hubs.values(), default=0)
            new_exposure += hub_cache[key] * 0.06
        new_exposure += (d.marketability - 50) * 0.08
        d.exposure = clamp(d.exposure * 0.45 + new_exposure)
        if d.id in jewel_hits:
            d.reputation = clamp(d.reputation + jewel_hits[d.id] * 0.12)


def estimated_potential(d: Driver, year: int) -> float:
    """What scouts *believe* the ceiling is: shown level plus youth headroom."""
    age = d.age(year)
    headroom = max(0.0, 25 - age) * 2.0
    return d.demonstrated + headroom


def is_aware(world: "World", team_tier: int, team_region: Optional[str], discipline: str,
             d: Driver, connection: float = 0.0, rng=None) -> bool:
    """Does a decision maker at this tier know this driver exists?"""
    need = NOTICE_THRESHOLD[team_tier]
    p = logistic((d.exposure - need) / 6.0)
    if d.tier >= team_tier - 1 and d.tier >= 3:
        p = max(p, 0.85)           # same / adjacent national tier: everyone watches
    p += connection
    if team_region and team_region == d.home_region:
        p += 0.15
    team_region_obj = world.geo.regions.get(team_region or "")
    driver_region = world.geo.regions.get(d.home_region)
    if team_region_obj and driver_region and team_region_obj.macro_region == driver_region.macro_region:
        p += 0.08
    if has_manager(d):
        p += 0.1
    return (rng or world.rng).random() < p


def has_manager(d: Driver) -> bool:
    """Drivers with means or a name attract management, who shop them to teams."""
    return d.reputation >= 45 or d.family_budget >= 150_000 or d.savings >= 250_000


def categorize(d: Driver, year: int) -> str:
    """FIA-style driver categorisation used by Pro-Am seat rules (research B 4.3).

    Based on *results and career shape*, not merely where someone has raced (an
    amateur paying for a GT seat does not become a pro by sitting in it):
    Platinum = premier-level front-runners or long premier careers; Gold = results
    at national pro level, a national title, or a career begun before 20 with 5+
    seasons of serious racing; Silver = under 30 or first licensed before 30;
    Bronze = first licence after 30. Age downgrades at 55/60/65; never below
    Silver before 27.
    """
    order = ["bronze", "silver", "gold", "platinum"]
    premier = [r for r in d.history if r.tier == 7]
    strong_pro = [r for r in d.history if r.tier >= 5 and r.championship_pos <= max(1, r.field_size // 4)]
    national_titles = [r for r in d.history if r.champion and r.tier >= 4]
    serious_seasons = sum(1 for r in d.history if r.tier >= 3)
    if any(r.championship_pos <= 5 for r in premier) or len(premier) >= 3:
        cat = 3
    elif strong_pro or national_titles or premier or (d.first_license_age < 20 and serious_seasons >= 5):
        cat = 2
    elif d.first_license_age >= 30:
        cat = 0
    else:
        cat = 1
    age = d.age(year)
    if age >= 65:
        cat = 0
    else:
        if age >= 55:
            cat -= 1
        if age >= 60:
            cat -= 1
    if age < 27:
        cat = max(cat, 1)
    return order[max(0, cat)]


def perceived_level(d: Driver, discipline: str, transfer: Optional[float] = None) -> float:
    """Demonstrated level, discounted for inexperience in the target discipline.

    Owners trust results in *their* discipline. If none of the driver's last three
    seasons were in it, the shown level is discounted by how poorly the driver's
    background transfers (research C 5.6: dirt->stock car transfers well; open
    wheel->oval stock car and dirt->sports cars do not).
    """
    prof = d.proficiency.get(discipline, 0.0)
    level = d.demonstrated * (0.78 + 0.22 * prof)
    recent = d.history[-3:]
    if transfer is not None and recent and not any(r.discipline == discipline for r in recent):
        level -= (1.0 - transfer) * 20.0
    if d.breakout > 0:
        level += 3.0
    return level


def tier_z(level: float, tier: int) -> float:
    return (level - TIER_STRENGTH[tier]) / TIER_SPREAD[tier]


def rate_for_team(team: "Team", d: Driver, discipline: str, tier: int, year: int,
                  world: Optional["World"] = None) -> tuple[float, float]:
    """(performance z, potential z) from a team's point of view."""
    transfer = None
    if world is not None and d.history:
        transfer = world.transfer(d.history[-1].discipline, discipline)
    perf = tier_z(perceived_level(d, discipline, transfer), tier)
    age = d.age(year)
    # Past the mid-20s 'potential' becomes 'how many good years are left'.
    pot = tier_z(estimated_potential(d, year), tier) if age <= 26 else perf - 0.25 * max(0, age - 32)
    return perf, pot


def log_scale(x: float) -> float:
    return math.log10(max(x, 1.0))
