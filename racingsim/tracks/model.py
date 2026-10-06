"""Track entity model.

A track is stored in three deliberately separate layers (requirement R4.5):

* ``TrackFacts``    -- publicly documented, sourced facts (name, location, length,
                       surface, banking, opening year, ...). Unknowns are ``None``;
                       we never guess a fact.
* ``TrackProfile``  -- descriptive classifications *derived* by the game from the
                       facts (size class, prestige, attendance potential, climate
                       profile, series suitability). Clearly game-owned.
* ``TrackSimRatings`` -- internal simulation ratings (0-100). These are our model,
                       informed by research, and are **not** official specifications.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Optional

TRACK_TYPES = {"oval", "road_course", "street_circuit", "roval", "kart_circuit", "figure_eight"}
SURFACES = {"asphalt", "concrete", "asphalt_concrete", "dirt", "clay"}
LEVELS = {"international", "national", "regional", "local"}
DISCIPLINES = {
    "stock_car", "late_model", "modified", "sprint_car", "midget", "dirt_late_model",
    "open_wheel", "sports_car", "touring_car", "club_road", "karting", "legends",
    "quarter_midget", "bandolero", "street_stock", "motorcycle",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass
class TrackFacts:
    id: str
    name: str
    city: Optional[str]
    region: Optional[str]
    country: str
    track_type: str
    surface: Optional[str]          # None when undocumented; game layer treats as paved
    length_mi: Optional[float]
    configuration: Optional[str] = None
    turns: Optional[int] = None
    banking_deg_turns: Optional[float] = None
    banking_deg_straights: Optional[float] = None
    opened: Optional[int] = None
    active: Optional[bool] = True   # None = status unconfirmed
    disciplines: list[str] = field(default_factory=list)
    level: str = "local"
    notable_note: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    sources: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)  # former / naming-rights names (search only)
    closed: Optional[int] = None      # last year the venue held racing (None = still open / unknown)
    history: list[dict] = field(default_factory=list)  # [{year, change}] reconfigurations since 1995
    dormant: list[list[int]] = field(default_factory=list)  # [[first, last]] seasons with no (national) racing
    major_series: list[str] = field(default_factory=list)   # notable series hosted (facts, for display/prestige)
    banking_category: Optional[str] = None  # flat | moderate | high (when degrees are unknown)
    prestige_category: Optional[str] = None  # low | medium | high | iconic (research judgement, see sources)
    confidence: Optional[str] = None        # high | medium | low for the record as a whole

    @property
    def is_active(self) -> bool:
        """Game treats an unconfirmed status as operating."""
        return self.active is not False

    def available_in(self, year: int) -> bool:
        """Did the venue host racing in ``year``? (opened/closed years; unknown = assume yes)."""
        if self.opened is not None and self.opened > year:
            return False
        if any(lo <= year <= hi for lo, hi in self.dormant):
            return False
        if self.closed is not None:
            return year <= self.closed
        if self.active is False:
            return year <= 2015  # closed at an undocumented date: assume open in the 1990s-2000s
        return True

    @property
    def is_dirt(self) -> bool:
        return self.surface in ("dirt", "clay")

    @property
    def is_oval(self) -> bool:
        return self.track_type in ("oval", "figure_eight")

    @property
    def is_road(self) -> bool:
        return self.track_type in ("road_course", "street_circuit", "roval")

    def validate(self) -> list[str]:
        problems = []
        if not self.name:
            problems.append("missing name")
        if self.track_type not in TRACK_TYPES:
            problems.append(f"bad track_type {self.track_type!r}")
        if self.surface is not None and self.surface not in SURFACES:
            problems.append(f"bad surface {self.surface!r}")
        if self.level not in LEVELS:
            problems.append(f"bad level {self.level!r}")
        if self.length_mi is not None and not (0.05 <= self.length_mi <= 15.0):
            problems.append(f"implausible length {self.length_mi}")
        if self.banking_deg_turns is not None and not (0 <= self.banking_deg_turns <= 45):
            problems.append(f"implausible banking {self.banking_deg_turns}")
        if self.opened is not None and not (1850 <= self.opened <= 2030):  # fairground horse tracks predate cars
            problems.append(f"implausible opened {self.opened}")
        if self.closed is not None and not (1900 <= self.closed <= 2030):
            problems.append(f"implausible closed {self.closed}")
        if self.lat is not None and not (-90 <= self.lat <= 90):
            problems.append("bad lat")
        if self.lon is not None and not (-180 <= self.lon <= 180):
            problems.append("bad lon")
        unknown = set(self.disciplines) - DISCIPLINES
        if unknown:
            problems.append(f"unknown disciplines {sorted(unknown)}")
        return problems

    @classmethod
    def from_dict(cls, raw: dict) -> "TrackFacts":
        data = dict(raw)
        data.setdefault("id", slugify(f"{raw['name']}-{raw.get('region') or raw.get('country')}"))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class WeatherProfile:
    climate: str                 # hot_humid | temperate | continental | desert | marine | subtropical
    season_start_month: int      # typical local racing season window
    season_end_month: int
    rain_risk: int               # 0-100 game rating
    heat_index: int              # 0-100 game rating (tire/engine/driver heat stress)


@dataclass
class TrackProfile:
    """Game-derived descriptive classification. Not an official statement."""
    size_class: str              # e.g. short_oval, intermediate_oval, superspeedway, road_course
    prestige: int                # 0-100
    attendance_potential: int    # 0-100
    weather: WeatherProfile
    series_suitability: list[str]  # discipline/series-template keys this venue can host


SIM_RATING_FIELDS = (
    "passing_difficulty", "tire_degradation", "mechanical_stress", "brake_stress",
    "engine_stress", "aero_importance", "mechanical_grip_importance", "horsepower_importance",
    "qualifying_importance", "caution_probability", "crash_severity", "drafting_effect",
    "fuel_sensitivity", "pit_road_time_loss", "wet_weather_suitability", "setup_sensitivity",
    "groove_width",
)


@dataclass
class TrackSimRatings:
    """Internal 0-100 simulation ratings. Our model, not official specs."""
    passing_difficulty: int
    tire_degradation: int
    mechanical_stress: int
    brake_stress: int
    engine_stress: int
    aero_importance: int
    mechanical_grip_importance: int
    horsepower_importance: int
    qualifying_importance: int
    caution_probability: int
    crash_severity: int
    drafting_effect: int
    fuel_sensitivity: int
    pit_road_time_loss: int
    wet_weather_suitability: int
    setup_sensitivity: int
    groove_width: int            # racing-line behaviour: 0 = single groove, 100 = wide multi-groove
    derivation: str = "rules"    # "rules" or "rules+override"


@dataclass
class Track:
    facts: TrackFacts
    profile: TrackProfile
    sim: TrackSimRatings
    display_override: Optional[str] = None  # release-build renaming hook (LICENSING_IP_REVIEW 2.1)

    @property
    def id(self) -> str:
        return self.facts.id

    @property
    def name(self) -> str:
        return self.facts.name

    @property
    def display_name(self) -> str:
        return self.display_override or self.facts.name

    def to_dict(self) -> dict:
        return {"facts": asdict(self.facts), "profile": asdict(self.profile), "sim": asdict(self.sim)}
