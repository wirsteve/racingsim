"""Reporting: pyramid funnel statistics and emergent career stories."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Callable, Optional

from .constants import TIER_STRENGTH
from .util import percentile
from .world.entities import RETIRED, Driver

if TYPE_CHECKING:
    from .world.world import World


def funnel(world: "World") -> list[dict]:
    """Per-tier population, ages, budgets and talent: the shape of the pyramid."""
    rows = []
    by_tier: dict[int, list[Driver]] = defaultdict(list)
    for d in world.drivers.values():
        if d.status != RETIRED and d.series_id:
            by_tier[d.tier].append(d)
    for tier in sorted(by_tier):
        ds = by_tier[tier]
        ages = [d.age(world.year) for d in ds]
        rows.append({
            "tier": tier,
            "name": world.pyramid.tier_names.get(tier, str(tier)),
            "drivers": len(ds),
            "age_p10": percentile(ages, 0.1), "age_median": percentile(ages, 0.5), "age_p90": percentile(ages, 0.9),
            "ability_median": percentile([d.ability for d in ds], 0.5),
            "funding_median": percentile([d.available_funding() for d in ds], 0.5),
            "disciplines": dict(Counter(world.series(d.series_id).discipline for d in ds).most_common()),
        })
    return rows


def cohort_outcomes(world: "World", entered_before: Optional[int] = None) -> dict:
    """How far did everyone who has ever raced get? (R3.4: it should be hard.)"""
    ds = [d for d in world.drivers.values() if entered_before is None or d.first_season <= entered_before]
    n = len(ds) or 1
    reached = {t: sum(1 for d in ds if d.max_tier >= t) / n for t in range(8)}
    return {"drivers": len(ds), "share_reaching_tier": reached}


# ---------------------------------------------------------------------------- stories
def _top_tier_ages(d: Driver) -> list[int]:
    return [r.year - d.birth_year for r in d.history if r.tier == 7]


def archetypes(world: "World") -> dict[str, Callable[[Driver], bool]]:
    def first_top_age(d: Driver) -> Optional[int]:
        ages = _top_tier_ages(d)
        return min(ages) if ages else None

    def disciplines_raced(d: Driver) -> set[str]:
        return {r.discipline for r in d.history if r.tier >= 3}

    return {
        "prodigy": lambda d: (a := first_top_age(d)) is not None and a <= 20,
        "late_bloomer": lambda d: (a := first_top_age(d)) is not None and a >= 27,
        "pay_driver": lambda d: d.tier >= 5 and d.team_id is not None and not d.seat_funded
            and d.ability < TIER_STRENGTH[d.tier] - 3,
        "stalled_talent": lambda d: d.status != RETIRED and d.ability >= TIER_STRENGTH[5]
            and d.max_tier <= 3 and d.age(world.year) >= 22,
        "veteran_returned_to_grassroots": lambda d: d.max_tier >= 5 and d.status != RETIRED
            and d.series_id is not None and d.tier <= 2,
        "discipline_switcher": lambda d: len(disciplines_raced(d)) >= 2,
        "shootout_or_combine_winner": lambda d: any("Shootout" in e or "Combine" in e for e in d.events),
        "development_signee": lambda d: any("development program at" in e for e in d.events),
        "crown_jewel_winner_from_local_ranks": lambda d: bool(d.crown_jewels) and d.max_tier <= 3,
        "ran_out_of_money": lambda d: any("money ran out" in e or "lost backing" in e for e in d.events),
    }


def find_stories(world: "World", per_type: int = 2) -> dict[str, list[Driver]]:
    out: dict[str, list[Driver]] = {}
    for name, pred in archetypes(world).items():
        hits = [d for d in world.drivers.values() if d.history and pred(d)]
        hits.sort(key=lambda d: (-d.max_tier, -len(d.events), d.id))
        out[name] = hits[:per_type]
    return out


def archetype_counts(world: "World") -> dict[str, int]:
    return {name: sum(1 for d in world.drivers.values() if d.history and pred(d))
            for name, pred in archetypes(world).items()}


def career_story(world: "World", d: Driver) -> str:
    lines = [f"{d.name} (#{d.id}) - born {d.birth_year}, from {world.geo.get(d.home_region).name}"
             f" | status {d.status} | best level: {world.pyramid.tier_names.get(d.max_tier)}"]
    lines.append(f"  starts {d.career_starts}, wins {d.career_wins}, titles {len(d.titles)},"
                 f" crown jewels {len(d.crown_jewels)}, reputation {d.reputation:.0f}")
    seen_series = None
    for r in d.history:
        name = world.series(r.series_id).name if r.series_id in world.pyramid.series else r.series_id
        if name != seen_series:
            team = world.teams.get(r.team_id).name if r.team_id in world.teams else "own car"
            lines.append(f"  {r.year} (age {r.year - d.birth_year}): {name} [{team}]"
                         f" P{r.championship_pos}/{r.field_size}, {r.wins} wins{' - CHAMPION' if r.champion else ''}")
            seen_series = name
        elif r.champion or r.wins >= 3:
            lines.append(f"  {r.year}: P{r.championship_pos}, {r.wins} wins{' - CHAMPION' if r.champion else ''}")
    for e in d.events:
        lines.append(f"  * {e}")
    return "\n".join(lines)


__all__ = ["funnel", "cohort_outcomes", "find_stories", "archetype_counts", "career_story"]
