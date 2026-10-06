"""Era economics: convert the model's 2025 dollars into a season's nominal dollars.

The simulation runs internally in 2025 dollars (all calibration is in 2025 USD).
For display, money is multiplied by a *motorsport price index* for the season:
racing costs rose faster than general inflation, so the index sits below CPI
for the 1990s (research: a 1990s Late Model Stock programme cost ~$50-60k vs
~$150-200k today). Values come from data/series_eras.json when present.
"""

from __future__ import annotations

from functools import lru_cache

from ..util import load_json


@lru_cache(maxsize=1)
def _table() -> dict[int, float]:
    try:
        raw = load_json("series_eras.json").get("price_index", {})
        table = {int(k): float(v) for k, v in raw.items()}
        if table:
            return table
    except FileNotFoundError:
        pass
    # Fallback: ~4.2%/yr motorsport cost growth back from 2025.
    return {y: round(1.042 ** (y - 2025), 3) for y in range(1990, 2031)}


def price_index(year: int) -> float:
    t = _table()
    if year in t:
        return t[year]
    lo, hi = min(t), max(t)
    return t[lo] if year < lo else t[hi]
