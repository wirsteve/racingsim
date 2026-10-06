"""Car classes: the real rules a car is built to (data/rules/classes.json).

Each class lists what a racer can actually buy - chassis options, the engine
packages the rules allow in a given season (built, crate, sealed crate, spec,
claimer), the shocks, the tire rule - and the per-night running costs. Money is
in 2025 dollars, like the rest of the model. Every number carries the researched
range, sources and confidence in ``facts``; the single game values are the
midpoints (or a documented design choice, flagged in ``notes``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from ..util import load_json


@dataclass
class Option:
    key: str
    label: str
    usd: float                     # purchase price (2025 USD)
    quality: float                 # 0-100 within the class
    age: int = 0                   # seasons already on a used chassis
    rebuild_usd: float = 0.0       # engines: freshen cost
    rebuild_races: int = 0         # engines: races between freshens
    claim_usd: float = 0.0         # engines/shocks: claim price where a claim rule exists
    sealed: bool = False           # sealed crate: only the factory / approved rebuilder may open it
    weight_break_lb: float = 0.0   # rules weight break given to this package
    years: tuple[int, int] = (1900, 2100)
    note: str = ""

    def available(self, year: int) -> bool:
        return self.years[0] <= year <= self.years[1]


@dataclass
class TireRule:
    usd: float = 150.0             # per tire, mounted
    typical_new: int = 2           # new tires a typical racer buys per night
    max_new: Optional[int] = None  # rule limit per night (None = open)
    life_races: float = 4.0        # nights a tire stays competitive
    spec: str = ""                 # brand / compound
    rule: str = ""                 # plain-language rule


@dataclass
class CarClass:
    key: str
    label: str
    discipline: str
    templates: list[str]
    spread: float                  # how far money can separate cars under these rules (spec 0.5 .. open 1.1)
    chassis: list[Option]
    engines: list[Option]
    shocks: list[Option]
    tires: TireRule
    chassis_life: float = 5.0      # seasons before a chassis is tired
    entry_usd: float = 0.0         # per night: entry fee + pit passes for the crew
    fuel_usd: float = 0.0          # per night: fuel + oil
    misc_usd: float = 0.0          # per night: consumables, small parts
    repair_frac: float = 0.15      # a typical wreck costs this share of a new chassis
    min_weight_lb: Optional[float] = None
    claims: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    confidence: str = "low"
    notes: str = ""
    evidence: list[str] = field(default_factory=list)   # research class keys describing these cars

    def evidence_keys(self) -> list[str]:
        return self.evidence or [self.key]

    def engines_in(self, year: int) -> list[Option]:
        out = [e for e in self.engines if e.available(year)]
        return out or self.engines[:1]

    def engine(self, key: str) -> Optional[Option]:
        return next((e for e in self.engines if e.key == key), None)

    def chassis_opt(self, key: str) -> Optional[Option]:
        return next((c for c in self.chassis if c.key == key), None)

    def shock(self, key: str) -> Optional[Option]:
        return next((s for s in self.shocks if s.key == key), None)

    def per_race_fixed(self) -> float:
        return self.entry_usd + self.fuel_usd + self.misc_usd


def _opt(raw: dict) -> Option:
    years = raw.get("years") or [raw.get("from", 1900), raw.get("to", 2100)]
    return Option(key=raw["key"], label=raw.get("label", raw["key"]), usd=float(raw.get("usd", 0)),
                  quality=float(raw.get("quality", 50)), age=int(raw.get("age", 0)),
                  rebuild_usd=float(raw.get("rebuild_usd", 0)), rebuild_races=int(raw.get("rebuild_races", 0)),
                  claim_usd=float(raw.get("claim_usd", 0)), sealed=bool(raw.get("sealed", False)),
                  weight_break_lb=float(raw.get("weight_break_lb", 0)),
                  years=(int(years[0]), int(years[1])), note=raw.get("note", ""))


def _class(key: str, raw: dict) -> CarClass:
    t = raw.get("tires", {})
    return CarClass(
        key=key, label=raw.get("label", key), discipline=raw.get("discipline", ""),
        templates=list(raw.get("templates", [])), spread=float(raw.get("spread", 1.0)),
        chassis=[_opt(o) for o in raw.get("chassis", [])], engines=[_opt(o) for o in raw.get("engines", [])],
        shocks=[_opt(o) for o in raw.get("shocks", [])],
        tires=TireRule(usd=float(t.get("usd", 150)), typical_new=int(t.get("typical_new", 2)),
                       max_new=t.get("max_new"), life_races=float(t.get("life_races", 4)),
                       spec=t.get("spec", ""), rule=t.get("rule", "")),
        chassis_life=float(raw.get("chassis_life", 5)), entry_usd=float(raw.get("entry_usd", 0)),
        fuel_usd=float(raw.get("fuel_usd", 0)), misc_usd=float(raw.get("misc_usd", 0)),
        repair_frac=float(raw.get("repair_frac", 0.15)), min_weight_lb=raw.get("min_weight_lb"),
        claims=list(raw.get("claims", [])), rules=list(raw.get("rules", [])),
        history=list(raw.get("history", [])), facts=dict(raw.get("facts", {})),
        sources=list(raw.get("sources", [])), confidence=raw.get("confidence", "low"), notes=raw.get("notes", ""),
        evidence=list(raw.get("evidence", [])))


@lru_cache(maxsize=1)
def all_classes() -> dict[str, CarClass]:
    try:
        raw = load_json("rules/classes.json")
    except FileNotFoundError:
        return {}
    return {k: _class(k, v) for k, v in raw.get("classes", {}).items()}


@lru_cache(maxsize=1)
def _by_template() -> dict[str, str]:
    out = {}
    for c in all_classes().values():
        for t in c.templates:
            out.setdefault(t, c.key)
    return out


def class_for_template(template_key: str) -> Optional[CarClass]:
    key = _by_template().get(template_key)
    return all_classes().get(key) if key else None
