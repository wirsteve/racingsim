"""Race-day weather.

Each venue has a climate profile (tracks/ratings.py: rain risk and heat 0-100 by climate). On race
day:

* **Rain** - weekly short tracks and dirt tracks are rained out (the night is lost: no race, no
  purse); a touring or national oval race that has started can be called short once past halfway;
  road courses race on in the wet, where car control matters and mistakes multiply.
* **Heat** - hot days wear tires faster and wear out drivers who aren't fit.

A rain-out rate near 10% of weekly race nights in wet climates (less in the desert) is a game-scale
estimate (EST): weekly tracks commonly lose a few nights a season to weather.
"""

from __future__ import annotations

import random
from typing import Optional

RAIN_PER_RISK = 0.2      # chance of rain on a race day per point of rain risk (0-100) / 100
HOT_PER_HEAT = 0.35      # chance of a hot day per point of heat index / 100


def roll(track, tier: int, rng: random.Random, scale: float = 1.0) -> Optional[dict]:
    """Weather for one race (None = an ordinary dry day)."""
    if scale <= 0:
        return None
    w = track.profile.weather if getattr(track, "profile", None) else None
    rain_risk = (w.rain_risk if w else 45) / 100
    heat = (w.heat_index if w else 55) / 100
    from ..world.skills import track_type_of
    tt = track_type_of(track)
    if rng.random() < rain_risk * RAIN_PER_RISK * scale:
        if tt == "road":
            return {"kind": "wet", "text": "Rain: a wet race"}
        if tier <= 2:
            return {"kind": "rainout", "text": "Rained out"}
        if rng.random() < 0.55:
            return {"kind": "rain_short", "share": round(rng.uniform(0.55, 0.9), 2), "text": "Rain-shortened"}
        return {"kind": "delay", "text": "Rain delay"}
    if rng.random() < heat * HOT_PER_HEAT * scale:
        return {"kind": "hot", "text": "Hot and slick"}
    return None
