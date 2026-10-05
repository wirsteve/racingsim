"""Derive the game-owned layers of a track (profile + simulation ratings) from facts.

The derivation is rule-based so that *every* track in the database -- including a
quarter-mile bullring that few people outside its county know -- gets a sensible
simulation personality without hand-entry. Notable venues can then be fine-tuned
in ``data/track_rating_overrides.json``; every override carries a rationale.

Rule calibration notes (see MOTORSPORTS_RESEARCH.md, "Track ecosystem"):

* Superspeedways (>= 2.5 mi, >= 18 deg banking) race in a draft: low passing
  difficulty, high caution/crash severity, low qualifying importance.
* Flat short ovals (< 0.75 mi, < 15 deg) are brake- and mechanical-grip tracks
  with hard passing and high qualifying importance.
* High-banked short ovals are high-g, high caution, tire-heavy bullrings.
* Intermediate ovals (1-2 mi) reward aero, horsepower and setup.
* Road courses reward brakes/aero; street circuits add walls, hard passing,
  high caution and qualifying importance.
* Dirt ovals change through the night: high setup sensitivity, wide grooves
  (the cushion), high caution, low wet-weather suitability (rain = postponement).
"""

from __future__ import annotations

from dataclasses import fields
from typing import Optional

from ..util import clamp, load_json
from .model import (
    SIM_RATING_FIELDS,
    Track,
    TrackFacts,
    TrackProfile,
    TrackSimRatings,
    WeatherProfile,
)

# Climate by region code; anything unlisted falls back to latitude rules.
_CLIMATE_BY_REGION = {
    # US
    "FL": "subtropical", "LA": "hot_humid", "TX": "hot_humid", "MS": "hot_humid", "AL": "hot_humid",
    "GA": "hot_humid", "SC": "hot_humid", "NC": "temperate", "VA": "temperate", "TN": "temperate",
    "KY": "temperate", "AR": "hot_humid", "OK": "temperate", "AZ": "desert", "NV": "desert",
    "NM": "desert", "UT": "desert", "CA": "marine", "OR": "marine", "WA": "marine",
    "CO": "continental", "WY": "continental", "MT": "continental", "ID": "continental",
    "WI": "continental", "MN": "continental", "MI": "continental", "IA": "continental",
    "IL": "continental", "IN": "continental", "OH": "continental", "PA": "continental",
    "NY": "continental", "NJ": "temperate", "MD": "temperate", "DE": "temperate", "WV": "temperate",
    "CT": "continental", "MA": "continental", "RI": "continental", "NH": "continental",
    "VT": "continental", "ME": "continental", "NE": "continental", "KS": "continental",
    "MO": "temperate", "SD": "continental", "ND": "continental",
    # Canada
    "ON": "continental", "QC": "continental", "NS": "continental", "NB": "continental",
    "PE": "continental", "AB": "continental", "BC": "marine", "MB": "continental", "SK": "continental",
}

_RAIN_RISK = {"subtropical": 60, "hot_humid": 55, "temperate": 45, "continental": 45,
              "marine": 50, "desert": 10}
_HEAT = {"subtropical": 80, "hot_humid": 80, "temperate": 60, "continental": 50,
         "marine": 40, "desert": 85}

_LEVEL_PRESTIGE = {"international": 80, "national": 65, "regional": 35, "local": 20}
_LEVEL_ATTENDANCE = {"international": 85, "national": 70, "regional": 30, "local": 15}


def _climate(facts: TrackFacts) -> str:
    if facts.region and facts.region in _CLIMATE_BY_REGION and facts.country in ("USA", "CAN"):
        return _CLIMATE_BY_REGION[facts.region]
    lat = abs(facts.lat) if facts.lat is not None else 40.0
    if lat < 25:
        return "subtropical"
    if lat < 35:
        return "hot_humid"
    if lat < 45:
        return "temperate"
    return "continental"


def _season_window(facts: TrackFacts, climate: str) -> tuple[int, int]:
    lat = abs(facts.lat) if facts.lat is not None else 40.0
    southern_hemisphere = facts.lat is not None and facts.lat < 0
    if climate in ("subtropical", "desert") or lat < 30:
        window = (1, 12)
    elif lat < 36:
        window = (2, 11)
    elif lat < 41:
        window = (3, 10)
    else:
        window = (4, 9)
    if southern_hemisphere and window != (1, 12):
        window = ((window[0] + 6 - 1) % 12 + 1, (window[1] + 6 - 1) % 12 + 1)
    return window


def size_class(facts: TrackFacts) -> str:
    length = facts.length_mi or 0.4
    banking = facts.banking_deg_turns or 0
    if facts.track_type == "kart_circuit":
        return "kart_circuit"
    if facts.track_type == "figure_eight":
        return "figure_eight"
    if facts.track_type == "street_circuit":
        return "street_circuit"
    if facts.track_type == "roval":
        return "roval"
    if facts.track_type == "road_course":
        return "long_road_course" if length >= 3.0 else "road_course" if length >= 1.8 else "club_circuit"
    if facts.is_dirt:
        return "dirt_short_oval" if length < 0.45 else "dirt_oval" if length <= 0.75 else "dirt_big_oval"
    if length >= 2.5 and banking >= 18:
        return "superspeedway"
    if length >= 2.0:
        return "large_flat_oval" if banking < 15 else "large_oval"
    if length >= 1.0:
        return "intermediate_oval" if banking >= 14 else "flat_intermediate"
    if length >= 0.75:
        return "short_oval"
    if facts.banking_deg_turns is None:
        return "short_oval"  # banking undocumented: treat as a neutral short oval
    return "bullring" if banking >= 18 else "flat_short_oval" if banking < 13 else "short_oval"


def series_suitability(facts: TrackFacts) -> list[str]:
    """Which series *templates* (see data/series.json `venue` keys) the venue can host."""
    sc = size_class(facts)
    out: set[str] = set()
    disc = set(facts.disciplines)
    if facts.track_type == "kart_circuit":
        out.add("kart")
        return sorted(out)
    if disc and disc <= {"quarter_midget", "bandolero"}:
        return ["youth_oval"]  # dedicated youth venues (quarter-midget club tracks)
    if facts.is_dirt and facts.is_oval:
        out.add("dirt_oval")
        if "sprint_car" in disc or "midget" in disc:
            out.add("dirt_open_wheel")
        if "dirt_late_model" in disc or "modified" in disc or "street_stock" in disc or not disc:
            out.add("dirt_full_body")
        if "quarter_midget" in disc:
            out.add("youth_oval")
        return sorted(out)
    if facts.is_oval:
        if sc in ("bullring", "flat_short_oval", "short_oval"):
            out.update({"short_oval", "youth_oval"} if (facts.length_mi or 1) <= 0.5 else {"short_oval"})
        if sc in ("intermediate_oval", "flat_intermediate", "short_oval") and (facts.length_mi or 0) >= 0.75:
            out.add("mid_oval")
        if sc in ("intermediate_oval", "flat_intermediate", "large_oval", "large_flat_oval"):
            out.add("big_oval")
        if sc == "superspeedway":
            out.add("superspeedway")
        if "open_wheel" in disc:
            out.add("open_wheel_oval")
        return sorted(out)
    # road venues
    out.add("road")
    if sc == "club_circuit":
        out.add("club_road")
    elif sc in ("road_course", "long_road_course"):
        out.update({"club_road", "pro_road"})
    elif sc in ("street_circuit", "roval"):
        out.add("pro_road")
    return sorted(out)


def derive_profile(facts: TrackFacts, prestige_bonus: int = 0) -> TrackProfile:
    climate = _climate(facts)
    start, end = _season_window(facts, climate)
    prestige = _LEVEL_PRESTIGE.get(facts.level, 20)
    attendance = _LEVEL_ATTENDANCE.get(facts.level, 15)
    if facts.opened and facts.opened < 1960:
        prestige += 6  # history counts for something in racing culture
    if facts.notable_note:
        prestige += 4
    length = facts.length_mi or 0.4
    attendance += int(min(15, length * 4)) if facts.is_oval else int(min(10, length * 2))
    if facts.active is False:
        attendance = 0
    return TrackProfile(
        size_class=size_class(facts),
        prestige=int(clamp(prestige + prestige_bonus)),
        attendance_potential=int(clamp(attendance)),
        weather=WeatherProfile(
            climate=climate,
            season_start_month=start,
            season_end_month=end,
            rain_risk=_RAIN_RISK[climate],
            heat_index=_HEAT[climate],
        ),
        series_suitability=series_suitability(facts),
    )


def derive_sim_ratings(facts: TrackFacts) -> TrackSimRatings:
    sc = size_class(facts)
    length = facts.length_mi or 0.4
    banking = facts.banking_deg_turns if facts.banking_deg_turns is not None else (
        8 if facts.is_oval else 0)

    r = {
        "passing_difficulty": 50, "tire_degradation": 50, "mechanical_stress": 50,
        "brake_stress": 50, "engine_stress": 50, "aero_importance": 50,
        "mechanical_grip_importance": 50, "horsepower_importance": 50,
        "qualifying_importance": 50, "caution_probability": 50, "crash_severity": 50,
        "drafting_effect": 10, "fuel_sensitivity": 50, "pit_road_time_loss": 50,
        "wet_weather_suitability": 5, "setup_sensitivity": 50, "groove_width": 50,
    }

    if sc == "superspeedway":
        r.update(passing_difficulty=15, tire_degradation=30, brake_stress=5, engine_stress=60,
                 aero_importance=80, mechanical_grip_importance=15, horsepower_importance=35,
                 qualifying_importance=15, caution_probability=75, crash_severity=95,
                 drafting_effect=95, fuel_sensitivity=70, pit_road_time_loss=45,
                 setup_sensitivity=35, groove_width=85)
    elif sc in ("large_oval", "large_flat_oval", "intermediate_oval", "flat_intermediate"):
        flat = sc in ("large_flat_oval", "flat_intermediate")
        r.update(passing_difficulty=60 if flat else 50, tire_degradation=55,
                 brake_stress=40 if flat else 25, engine_stress=70, aero_importance=85,
                 mechanical_grip_importance=40 if flat else 30, horsepower_importance=75,
                 qualifying_importance=45, caution_probability=45, crash_severity=80,
                 drafting_effect=int(clamp(20 + length * 12 + (banking - 10))),
                 fuel_sensitivity=65, pit_road_time_loss=55, setup_sensitivity=75,
                 groove_width=int(clamp(35 + banking * 1.5)))
    elif sc in ("short_oval", "flat_short_oval", "bullring") and not facts.is_dirt:
        # Blend flat-paperclip and high-banked-bullring behaviour by banking;
        # undocumented banking sits in the middle.
        if facts.banking_deg_turns is None:
            hb = 0.5
        else:
            hb = clamp((facts.banking_deg_turns - 12) / 8, 0, 1)

        def mix(flat: float, high: float) -> float:
            return flat + (high - flat) * hb

        r.update(passing_difficulty=mix(70, 55), tire_degradation=mix(45, 55),
                 mechanical_stress=mix(55, 65), brake_stress=mix(85, 55), engine_stress=50,
                 aero_importance=20, mechanical_grip_importance=80, horsepower_importance=35,
                 qualifying_importance=70, caution_probability=mix(60, 70),
                 crash_severity=mix(35, 45), drafting_effect=3,
                 fuel_sensitivity=25, pit_road_time_loss=35, setup_sensitivity=65,
                 groove_width=mix(30, 55))
    elif facts.is_dirt and facts.is_oval:
        big = sc == "dirt_big_oval"
        r.update(passing_difficulty=40, tire_degradation=60, mechanical_stress=70,
                 brake_stress=20, engine_stress=65, aero_importance=35 if big else 20,
                 mechanical_grip_importance=75, horsepower_importance=60 if big else 45,
                 qualifying_importance=55, caution_probability=75, crash_severity=60 if big else 45,
                 drafting_effect=3, fuel_sensitivity=15, pit_road_time_loss=10,
                 wet_weather_suitability=10, setup_sensitivity=85,
                 groove_width=int(clamp(60 + banking)))
    elif sc == "figure_eight":
        r.update(passing_difficulty=60, mechanical_grip_importance=70, aero_importance=10,
                 horsepower_importance=30, caution_probability=90, crash_severity=70,
                 drafting_effect=0, qualifying_importance=60, groove_width=20, brake_stress=60)
    elif sc == "street_circuit":
        r.update(passing_difficulty=80, tire_degradation=50, mechanical_stress=75, brake_stress=85,
                 engine_stress=45, aero_importance=45, mechanical_grip_importance=80,
                 horsepower_importance=40, qualifying_importance=85, caution_probability=75,
                 crash_severity=45, drafting_effect=5, fuel_sensitivity=55,
                 pit_road_time_loss=60, wet_weather_suitability=55, setup_sensitivity=70,
                 groove_width=10)
    elif sc == "kart_circuit":
        r.update(passing_difficulty=45, tire_degradation=45, brake_stress=40, engine_stress=40,
                 aero_importance=5, mechanical_grip_importance=75, horsepower_importance=30,
                 qualifying_importance=55, caution_probability=30, crash_severity=15,
                 drafting_effect=35, fuel_sensitivity=10, pit_road_time_loss=0,
                 wet_weather_suitability=70, setup_sensitivity=60, groove_width=30)
    else:  # road courses / rovals / club circuits
        long_course = length >= 3.0
        r.update(passing_difficulty=55 if long_course else 62, tire_degradation=55,
                 mechanical_stress=55, brake_stress=75, engine_stress=55,
                 aero_importance=75 if long_course else 60,
                 mechanical_grip_importance=60 if long_course else 70,
                 horsepower_importance=70 if long_course else 50, qualifying_importance=60,
                 caution_probability=40 if long_course else 45, crash_severity=50,
                 drafting_effect=25 if long_course else 12, fuel_sensitivity=75,
                 pit_road_time_loss=70, wet_weather_suitability=75, setup_sensitivity=65,
                 groove_width=15)
        if sc == "roval":
            r.update(caution_probability=65, wet_weather_suitability=45, passing_difficulty=65)

    # Concrete surfaces in the mix: grip changes and harder-on-tires behaviour.
    if facts.surface in ("concrete", "asphalt_concrete"):
        r["setup_sensitivity"] = int(clamp(r["setup_sensitivity"] + 8))
        r["tire_degradation"] = int(clamp(r["tire_degradation"] + 5))
    # Older venues: assume weathered, more abrasive surfaces unless overridden.
    if facts.opened and facts.opened < 1970 and not facts.is_dirt:
        r["tire_degradation"] = int(clamp(r["tire_degradation"] + 5))

    return TrackSimRatings(**{k: int(clamp(v)) for k, v in r.items()}, derivation="rules")


_OVERRIDES: Optional[dict] = None


def _overrides() -> dict:
    global _OVERRIDES
    if _OVERRIDES is None:
        try:
            _OVERRIDES = load_json("track_rating_overrides.json")
        except FileNotFoundError:
            _OVERRIDES = {}
    return _OVERRIDES


def build_track(facts: TrackFacts, overrides: Optional[dict] = None) -> Track:
    table = _overrides() if overrides is None else overrides
    ov = table.get(facts.id, {})
    profile = derive_profile(facts, prestige_bonus=int(ov.get("prestige_bonus", 0)))
    if "attendance_potential" in ov:
        profile.attendance_potential = int(ov["attendance_potential"])
    sim = derive_sim_ratings(facts)
    sim_ov = ov.get("sim", {})
    if sim_ov:
        valid = {f.name for f in fields(TrackSimRatings)}
        for key, value in sim_ov.items():
            if key in valid and key in SIM_RATING_FIELDS:
                setattr(sim, key, int(clamp(value)))
        sim.derivation = "rules+override"
    return Track(facts=facts, profile=profile, sim=sim, display_override=ov.get("display_name"))
