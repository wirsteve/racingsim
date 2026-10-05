"""Personal sponsorship market.

Sponsors are mostly local businesses backing local racers (research F 2.3/5.5):
cash or product worth $500-$10k at the grassroots, regional brands at touring
level, national brands only at national tiers. Sponsors buy *visibility and
story*, not lap times: marketability, reputation and home-market ties matter as
much as results. Deals collapse (research C 5.4), which is the most common way
careers stall.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ..constants import SPONSOR_COLLAPSE_BASE, SPONSOR_COLLAPSE_NATIONAL
from ..util import clamp
from ..world.entities import RETIRED, SIDELINED, Driver, Sponsor, SponsorDeal

if TYPE_CHECKING:
    from ..sim.season import SeasonResults
    from ..world.world import World

# Typical deal size bands by tier (USD/season), research F 5.5.
DEAL_BANDS = {
    0: (300, 2_000), 1: (500, 4_000), 2: (1_500, 12_000), 3: (10_000, 75_000),
    4: (50_000, 500_000), 5: (150_000, 1_500_000), 6: (300_000, 3_000_000), 7: (1_000_000, 8_000_000),
}


def _appeal(d: Driver) -> float:
    recent = d.history[-1] if d.history else None
    results = 0.0
    if recent:
        results = (1 - (recent.avg_finish - 1) / max(1, recent.field_size - 1)) * 30 + recent.wins * 3
    return d.marketability * 0.6 + d.reputation * 0.6 + results + d.exposure * 0.3


def _sign(world: "World", sponsor: Sponsor, d: Driver, amount: float, years: int) -> None:
    d.sponsors.append(SponsorDeal(sponsor.id, amount, years))
    sponsor.committed += amount


def initial_personal_sponsors(world: "World") -> None:
    """Seed the world: split some family money into sponsor deals so funding has texture."""
    rng = world.rng
    for d in world.drivers.values():
        if d.tier >= 4 and not d.seat_funded and d.family_budget > 150_000 and rng.random() < 0.65:
            # Pay drivers at national level are usually sponsor-backed, not family-backed.
            amount = d.family_budget * rng.uniform(0.5, 0.9)
            d.family_budget -= amount
            sponsor = _find_sponsor(world, d, amount)
            if sponsor:
                _sign(world, sponsor, d, amount, rng.randint(1, 3))
            else:
                d.family_budget += amount
    _new_deals(world)


def _find_sponsor(world: "World", d: Driver, amount: float) -> Sponsor | None:
    rng = world.rng
    candidates = [s for s in world.sponsors.values()
                  if s.min_tier <= d.tier <= s.max_tier and s.budget - s.committed >= amount * 0.5
                  and (s.scope == "national" or s.region == d.home_region)]
    return rng.choice(candidates) if candidates else None


def update(world: "World", results: "SeasonResults") -> None:
    rng = world.rng
    # Existing deals: expire, renew or collapse.
    for d in world.drivers.values():
        if not d.sponsors:
            continue
        kept = []
        for deal in d.sponsors:
            sponsor = world.sponsors.get(deal.sponsor_id)
            if sponsor is None:
                continue
            collapse = SPONSOR_COLLAPSE_NATIONAL if sponsor.scope == "national" else SPONSOR_COLLAPSE_BASE
            if d.status in (RETIRED, SIDELINED) or rng.random() < collapse:
                sponsor.committed -= deal.amount
                if deal.amount >= 100_000 and d.status != RETIRED:
                    d.log(world.year, f"lost backing from {sponsor.name}")
                continue
            deal.years_left -= 1
            if deal.years_left <= 0:
                rec = results.records.get(d.id)
                ok = rec is not None and (rec.wins > 0 or rec.championship_pos <= max(3, rec.field_size // 3))
                p_renew = sponsor.loyalty * (1.0 if ok else 0.55) * (0.7 + d.marketability / 160)
                if rng.random() < p_renew:
                    deal.years_left = rng.randint(1, 3)
                    deal.amount *= rng.uniform(0.9, 1.25) if ok else rng.uniform(0.7, 1.0)
                else:
                    sponsor.committed -= deal.amount
                    continue
            kept.append(deal)
        d.sponsors = kept
    _new_deals(world)


def _new_deals(world: "World") -> None:
    rng = world.rng
    by_region_tier: dict[tuple[str, int], list[Driver]] = defaultdict(list)
    national: dict[int, list[Driver]] = defaultdict(list)
    for d in world.drivers.values():
        if d.status == RETIRED or not d.series_id:
            continue
        by_region_tier[(d.home_region, d.tier)].append(d)
        if d.tier >= 4:
            national[d.tier].append(d)
    sponsors = list(world.sponsors.values())
    rng.shuffle(sponsors)
    for s in sponsors:
        free = s.budget - s.committed
        if free <= 300:
            continue
        tier = rng.randint(s.min_tier, s.max_tier)
        lo, hi = DEAL_BANDS[tier]
        if free < lo:
            continue
        if s.scope == "national":
            pool = national.get(tier, [])
        else:
            pool = by_region_tier.get((s.region, tier), [])
        if not pool:
            continue
        sample = rng.sample(pool, min(25, len(pool)))
        best = max(sample, key=lambda d: _appeal(d) + rng.gauss(0, 12) - 6 * len(d.sponsors))
        if _appeal(best) < 25 + tier * 6:
            continue
        amount = min(free, rng.uniform(lo, hi) * clamp(0.5 + _appeal(best) / 120, 0.5, 1.6))
        _sign(world, s, best, amount, rng.randint(1, 3))


def pitch_for_player(world: "World", d: Driver) -> str:
    """The player knocks on doors. Odds follow the same appeal logic sponsors use."""
    rng = world.rng
    tier = max(0, min(7, d.tier))
    local = [s for s in world.sponsors.values() if s.region == d.home_region
             and s.min_tier <= tier <= s.max_tier and s.budget - s.committed > 300]
    national = [s for s in world.sponsors.values() if s.scope == "national"
                and s.min_tier <= tier <= s.max_tier and s.budget - s.committed > 50_000]
    pool = local + national
    if not pool:
        return "Nobody returned your calls. Try again when you're racing at a higher level or in a bigger market."
    rng.shuffle(pool)
    appeal = _appeal(d)
    wins = []
    national_signed = False
    for s in pool[:4]:
        p = clamp((appeal - (18 + tier * 6)) / 60 + 0.25, 0.05, 0.8)
        if s.scope == "national":
            if national_signed:
                continue
            p *= 0.45  # national brands rarely sign off a cold call
        if rng.random() < p:
            lo, hi = DEAL_BANDS[tier]
            # Deal size tracks how appealing you are, not just the tier you race in.
            share = clamp(appeal / 110, 0.05, 1.0) * rng.uniform(0.5, 1.0)
            amount = min(s.budget - s.committed, lo + (hi - lo) * share)
            if amount < 250:
                continue
            _sign(world, s, d, amount, rng.randint(1, 2))
            wins.append(f"{s.name} (${amount:,.0f}/season)")
            national_signed = national_signed or s.scope == "national"
        if len(wins) >= 2:
            break
    if not wins:
        return "Plenty of handshakes, no signatures. Results and a bigger audience would help."
    d.log(world.year, "signed sponsorship with " + ", ".join(wins))
    return "New backing: " + "; ".join(wins)
