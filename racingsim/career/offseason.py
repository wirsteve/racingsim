"""Off-season orchestration: the order in which the ecosystem reacts to a season."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..world.entities import RETIRED
from . import lifecycle, market, programs, scouting, sponsorship

if TYPE_CHECKING:
    from ..sim.season import SeasonResults
    from ..world.world import World, YearSummary


def run_offseason(world: "World", results: "SeasonResults", summary: "YearSummary") -> None:
    # 1. The paddock digests the season: demonstrated level, exposure, reputation.
    scouting.update_after_season(world, results)
    # 2. Money from last year's vouchers is spent; new vouchers are earned.
    programs.clear_consumed_scholarships(world)
    programs.award_champion_scholarships(world, results)
    # 3. People age, learn, and some walk away (or step back to grassroots racing).
    lifecycle.develop(world, results)
    lifecycle.retirements(world, results, summary)
    # 4. Sponsors renew, walk, or collapse; new local/regional/national deals form.
    sponsorship.update(world, results)
    for d in world.drivers.values():
        if d.status != RETIRED:
            d.savings = max(0.0, d.savings + d.salary * 0.6)  # after taxes/living costs
    # 5. Talent pipelines: manufacturer programs, shootouts, combines.
    programs.manufacturer_programs(world, summary)
    programs.run_shootouts(world, summary)
    # 6. Silly season: team seats top-down, then everyone else picks a self-run program.
    market.run_market(world, summary)
    # 7. A new cohort arrives to replace those who left.
    active = sum(1 for d in world.drivers.values() if d.status != RETIRED)
    target = getattr(world, "target_population", active)
    count = max(0, int(summary.retirements * 0.95 + (target - active) * 0.4))
    lifecycle.new_entrants(world, summary, count)
    for d in world.drivers.values():
        if d.status != RETIRED:
            d.years_at_tier += 1
