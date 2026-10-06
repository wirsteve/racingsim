"""Geography: home regions, discipline cultures, travel economics (requirement R6).

Geography is never a hard restriction. It changes *economics and exposure*:
a Wisconsin kid has cheap access to asphalt super late models and expensive
access to Southern late-model tours; an Indiana kid lives next door to USAC
sprint cars and the open-wheel industry; a North Carolina kid can drive to a
Cup team's shop.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..util import haversine_mi, load_json, weighted_choice

# Per-mile cost of towing a race car to an event and back (truck, trailer, fuel,
# lodging amortised). Calibrated in MOTORSPORTS_RESEARCH.md ("Travel economics").
TOW_COST_PER_MILE = 2.25
FLY_THRESHOLD_MI = 900          # beyond this crew/drivers usually fly; car is hauled by team
FLY_EVENT_COST = 2_500


@dataclass
class Region:
    code: str
    name: str
    country: str
    macro_region: str
    lat: float
    lon: float
    racer_weight: float
    culture: dict[str, float]
    sponsor_market: float
    industry_hubs: dict[str, float] = field(default_factory=dict)

    def hub(self, discipline: str) -> float:
        return self.industry_hubs.get(discipline, 0.0)


class Geography:
    def __init__(self, regions: list[Region], macro_descriptions: dict[str, str]):
        self.regions = {r.code: r for r in regions}
        self.macro_descriptions = macro_descriptions
        self._by_macro: dict[str, list[Region]] = {}
        for r in regions:
            self._by_macro.setdefault(r.macro_region, []).append(r)

    @classmethod
    def load(cls) -> "Geography":
        raw = load_json("regions.json")
        regions = [Region(**r) for r in raw["regions"]]
        return cls(regions, raw.get("macro_regions", {}))

    def get(self, code: str) -> Region:
        return self.regions[code]

    def macro_regions(self) -> list[str]:
        return sorted(self._by_macro)

    def in_macro(self, macro: str) -> list[Region]:
        return self._by_macro.get(macro, [])

    def random_home(self, rng: random.Random, discipline: str | None = None) -> Region:
        regions = list(self.regions.values())
        if discipline:
            weights = [r.racer_weight * (0.2 + r.culture.get(discipline, 0) / 100) for r in regions]
        else:
            weights = [r.racer_weight for r in regions]
        return weighted_choice(rng, regions, weights)

    def favoured_discipline(self, rng: random.Random, region: Region, youth: bool) -> str:
        """Which discipline a newcomer from this region gravitates to.

        Youth entrants skew to karting (most common entry worldwide) and to the
        local oval scene; adult entrants skew to local full-bodied cars and club racing.
        """
        disc = list(region.culture)
        weights = []
        for d in disc:
            w = region.culture[d]
            if youth and d == "karting":
                w *= 1.6
            if youth and d in ("sports_car", "touring_car", "club_road"):
                w *= 0.15
            if not youth and d in ("karting", "open_wheel"):
                w *= 0.25
            if d in ("sports_car", "touring_car"):
                w *= 0.3  # few people *start* in pro sports cars
            weights.append(w)
        return weighted_choice(rng, disc, weights)


def travel_cost(home_lat: float, home_lon: float, venue_lat: float, venue_lon: float) -> float:
    """Approximate round-trip cost for one event, for a self-transported small team."""
    d = haversine_mi(home_lat, home_lon, venue_lat, venue_lon)
    if d > FLY_THRESHOLD_MI:
        return FLY_EVENT_COST + FLY_THRESHOLD_MI * TOW_COST_PER_MILE
    lodging = 0 if d < 150 else 350 if d < 500 else 700
    return 2 * d * TOW_COST_PER_MILE + lodging
