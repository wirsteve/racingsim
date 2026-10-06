"""Research-based owner selection weights (from ``advancement_factors.json``).

The economics research gives, per tier, how much each factor drives advancement.
Owners choosing drivers act on the driver-side factors, grouped as the market uses them:

    performance   = talent + results + half of reputation
    potential     = age (youth premium) + development-program backing
    money         = sponsorship + family funding
    marketability = marketability + half of reputation
    connections   = connections + manufacturer support

Equipment, injuries, reliability and luck are simulated directly (team equipment,
crashes, randomness), so they are not double-counted here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

GROUPS = {
    "performance": {"factor:talent": 1.0, "factor:results": 1.0, "factor:reputation": 0.5},
    "potential": {"factor:age": 1.0, "factor:development-program": 1.0},
    "money": {"factor:sponsorship": 1.0, "factor:family-funding": 1.0},
    "marketability": {"factor:marketability": 1.0, "factor:reputation": 0.5},
    "connections": {"factor:connections": 1.0, "factor:manufacturer-support": 1.0},
}
CONNECTION_REFERENCE = 0.14  # tier-5 research share at which the market's base connection weight applies


@lru_cache(maxsize=16)
def selection_weights(tier: int) -> Optional[dict]:
    """Normalised {performance, potential, money, marketability} plus a connections multiplier, or None."""
    try:
        from .api import Knowledge
        k = Knowledge.default()
        rows = k._rows("SELECT factor_id, w_min, w_max FROM advancement_weight WHERE tier = ?", (tier,)) if k else []
    except Exception:  # pragma: no cover - database missing or older schema
        rows = []
    w = {f: ((lo or 0) + (hi or 0)) / 2 for f, lo, hi in rows}
    if not w:
        return None
    raw = {g: sum(w.get(f, 0) * m for f, m in parts.items()) for g, parts in GROUPS.items()}
    core = {g: raw[g] for g in ("performance", "potential", "money", "marketability")}
    total = sum(core.values()) or 1.0
    out = {g: v / total for g, v in core.items()}
    out["connections"] = max(0.5, min(1.6, raw["connections"] / CONNECTION_REFERENCE))
    return out
