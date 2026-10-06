"""Off-season orchestration: the order in which the ecosystem reacts to a season.

The off-season is split in two so a human player can make decisions in the middle:

``begin_offseason``    the paddock digests the season, people age/retire, sponsors
                       move, development programs and shootouts run, contracts tick
                       and the open seats are put on the market;
(player decisions)     see ``racingsim.game.career``;
``complete_offseason`` the AI fills the remaining seats top-down, everyone else
                       picks a self-run programme, and the next cohort arrives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..world.entities import RETIRED, SIDELINED
from ..rules.garage import target_class
from ..world import staff
from . import lifecycle, market, morale, programs, scouting, sponsorship

if TYPE_CHECKING:
    from ..sim.season import SeasonResults
    from ..world.world import World, YearSummary

NEWSWORTHY = ("won the", "development program", "Shootout", "Combine", "first premier-level",
              "seriously injured", "retired from driving", "stepped back")


def begin_offseason(world: "World", results: "SeasonResults", summary: "YearSummary") -> None:
    world.market.event_marks = {d.id: len(d.events) for d in world.drivers.values()}
    staff.record_season(world, results)
    world.player_crew = {}   # freelance crew was hired for the season just run; hires from now are for next year
    morale.season_update(world, results)   # before contracts: unhappy drivers are harder to keep
    _season_news(world, results)
    _pay_from_savings(world)
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
        if d.status == RETIRED:
            continue
        d.savings = max(0.0, d.savings + d.salary * 0.6)  # after taxes/living costs
        age = d.age(world.year)
        if 20 <= age <= 50 and d.team_id is None:
            # Working adults' hobby budgets grow with their careers.
            d.family_budget *= world.rng.uniform(1.0, 1.06)
        if d.team_id is None and d.series_id and d.status != SIDELINED and not (d.is_player and target_class(world, d) is not None):
            # Racers in a cheaper class bank the surplus toward a bigger car.
            surplus = d.family_budget - world.series(d.series_id).template.season_cost
            if surplus > 0:
                d.savings += surplus * 0.5
    # 5. Talent pipelines: manufacturer programs, shootouts, combines.
    programs.manufacturer_programs(world, summary)
    programs.run_shootouts(world, summary)
    world.player_applications = set()
    # 6a. The calendar turns: series renamed, rungs appear or go dormant, venues open/close.
    world.advance_pyramid(world.year + 1)
    # 6b. Silly season opens: contracts tick, open seats go on the market.
    market.open_market(world, summary)


def complete_offseason(world: "World", summary: "YearSummary") -> None:
    # 6b. Seats fill top-down, then everyone else picks a self-run programme.
    market.close_market(world, summary)
    # 6c. Staff: contracts tick, poor results cost crew chiefs their jobs, the best teams hire first.
    for line in staff.offseason(world, summary):
        world.post("staff", line, importance=1)
    # 7. A new cohort arrives to replace those who left.
    active = sum(1 for d in world.drivers.values() if d.status != RETIRED)
    target = world.target_population or active
    count = max(0, int(summary.retirements * 0.95 + (target - active) * 0.4))
    lifecycle.new_entrants(world, summary, count)
    if world.history is not None:
        from ..history.seed import history_entrants
        summary.new_entrants += history_entrants(world, world.year + 1)
    for d in world.drivers.values():
        if d.status != RETIRED:
            d.years_at_tier += 1
    _offseason_news(world)


def run_offseason(world: "World", results: "SeasonResults", summary: "YearSummary") -> None:
    begin_offseason(world, results, summary)
    complete_offseason(world, summary)


def _pay_from_savings(world: "World") -> None:
    """The savings that went into this season's budget are gone."""
    for d in world.drivers.values():
        if d.status == RETIRED or not d.series_id or d.savings <= 0:
            continue
        if d.is_player and target_class(world, d) is not None:
            continue  # the racing account already took the savings it used
        need = market.season_outlay(world, d)
        other = d.family_budget + d.sponsor_money() + d.scholarship
        d.savings -= min(max(0.0, need - other), d.savings * 0.25)


def _season_news(world: "World", results: "SeasonResults") -> None:
    for sid, did in results.champions.items():
        s = world.series(sid)
        if s.tier >= 3 or (world.player_id == did):
            d = world.drivers[did]
            world.post("title", f"{d.name} wins the {s.name} championship", driver_id=did,
                       series_id=sid, week=0, importance=3 if s.tier >= 6 else 2)


def _offseason_news(world: "World") -> None:
    """Notable drivers' career events from this off-season become news items."""
    marks = world.market.event_marks
    for d in world.drivers.values():
        start = marks.get(d.id, 0)
        new = d.events[start:]
        if not new:
            continue
        notable = d.is_player or d.max_tier >= 6 or d.reputation >= 55
        for e in new:
            text = e.split(": ", 1)[-1]
            if d.is_player or (notable and ("signed with" in text or any(k in text for k in NEWSWORTHY))) \
                    or any(k in text for k in ("Shootout", "Combine", "development program at", "first premier-level")):
                world.post("player" if d.is_player else "move", f"{d.name} {text}", driver_id=d.id, week=0,
                           importance=3 if d.is_player else 1)
