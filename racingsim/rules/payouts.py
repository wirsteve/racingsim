"""Purses and fees (data/rules/payouts.json).

Payout tables are published sheets in the dollars of the year they were
published (nominal). Weekly-track purses have barely moved in nominal terms
since the 1990s while costs tripled, which is one of the defining economics of
short-track racing: a 1996 feature win paid about what it pays now. Each
assignment carries a ``drift`` - the share of motorsport cost inflation the
purse kept pace with (0 = flat nominal, 1 = constant real value) - so tables
travel across eras the way real purses did.

Amounts returned are in 2025 dollars, like everything else in the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from ..history.economy import price_index
from ..util import load_json


@dataclass
class Table:
    key: str
    label: str
    year: int
    by_position: list[float] = field(default_factory=list)   # nominal $ for P1, P2, ...
    to_start: float = 0.0           # every feature starter past the table
    dnq: float = 0.0                # tow money for cars that miss the feature
    points_fund: list[float] = field(default_factory=list)   # season-end payout by championship position
    note: str = ""
    sources: list[str] = field(default_factory=list)
    confidence: str = "low"


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return load_json("rules/payouts.json")
    except FileNotFoundError:
        return {}


@lru_cache(maxsize=1)
def tables() -> dict[str, Table]:
    known = set(Table.__dataclass_fields__)
    return {k: Table(key=k, **{a: b for a, b in v.items() if a in known and a != "key"})
            for k, v in _data().get("tables", {}).items()}


@lru_cache(maxsize=4096)
def assignment(template_key: str, year: int) -> Optional[tuple[str, float]]:
    """(table key, drift) for this series and season, or None (use the template's purse curve)."""
    for a in _data().get("assign", []):
        if template_key in a.get("templates", []) and a.get("from", 0) <= year <= a.get("to", 9999):
            return a["table"], float(a.get("drift", 0.3))
    return None


def _factor(table: Table, year: int, drift: float) -> float:
    """Nominal-dollars-in-``table.year`` -> 2025 dollars in ``year``."""
    grow = price_index(year) / price_index(table.year)
    nominal = 1 + drift * (grow - 1)
    return nominal / price_index(year)


class Purse:
    """Pays one series for one season."""

    def __init__(self, template, year: int):
        self.tpl = template
        self.table: Optional[Table] = None
        a = assignment(template.key, year)
        if a and a[0] in tables():
            self.table = tables()[a[0]]
            self.k = _factor(self.table, year, a[1])

    def pay(self, position: int, field_size: int) -> float:
        t = self.table
        if t is None:
            return legacy(position, self.tpl.purse_win)
        if position <= len(t.by_position):
            return t.by_position[position - 1] * self.k
        return t.to_start * self.k

    def dnq(self) -> float:
        return (self.table.dnq * self.k) if self.table else 0.0

    def points_fund(self, position: int) -> float:
        t = self.table
        if t is None or position > len(t.points_fund):
            return 0.0
        return t.points_fund[position - 1] * self.k


def legacy(position: int, purse_win: float) -> float:
    """The original generic curve, for series without a researched table."""
    if purse_win <= 0:
        return 0.0
    return purse_win * max(0.04, 1.0 / (1.0 + 0.45 * (position - 1)))
