"""OOTP-style driver ratings: component skills, track-type skills and personality.

Overall talent stays ``Driver.ability`` / ``Driver.potential`` (everything that reasons about
"how good is this driver" keeps working). On top of it every driver has:

* **Component skills** (current and potential): speed, qualifying, consistency, racecraft,
  defending, restarts, tire management, fuel saving, car control, composure, feedback and
  fitness. Each is stored as an *offset* around overall ability, so a driver can be a
  brilliant qualifier who can't save tires, or a slow-but-smart veteran. The race engine uses
  the skill that matters for each phase of a race.
* **Track-type skills** (short track, intermediate, superspeedway/draft, road course, dirt):
  experience-driven, learned from laps run on that kind of track, with a talent component.
* **Personality**: work ethic, intelligence, leadership, loyalty, greed, ambition and temper
  (hidden; scouts and the media get impressions). They drive development, aging, contract
  behaviour, incidents and team effects.
* **Durability** (injury proneness).

Development and aging work per skill: physical tools (speed, fitness, car control) peak and
fade with age; savvy (tire and fuel management, restarts, defending, feedback, composure)
keeps growing with experience and intelligence, so 38-year-olds win with smarts while
19-year-olds win with speed - the way real careers look.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from ..util import clamp

if TYPE_CHECKING:
    from .entities import Driver

# key: (label, description, kind) - kind: "physical" fades with age, "savvy" grows with experience,
# "skill" develops with seat time.
SKILLS: dict[str, tuple[str, str, str]] = {
    "speed": ("Speed", "Raw pace: how fast the driver can make a car go over a lap.", "physical"),
    "qualifying": ("Qualifying", "Putting the lap together when it counts: one or two laps, no margin.", "skill"),
    "consistency": ("Consistency", "Lap after lap at pace without mistakes.", "skill"),
    "racecraft": ("Racecraft", "Setting up and completing passes in traffic.", "skill"),
    "defending": ("Defending", "Holding a position: placing the car, managing the driver behind.", "savvy"),
    "restarts": ("Restarts", "Gaining spots on starts and restarts; reading the field.", "savvy"),
    "tire_management": ("Tire management", "Saving tires over a long run so there is grip left at the end.", "savvy"),
    "fuel_saving": ("Fuel saving", "Stretching a tank without giving up much time.", "savvy"),
    "car_control": ("Car control", "Driving a loose, damaged or wet car; saving it when it steps out.", "physical"),
    "composure": ("Composure", "Late in races, leading, under pressure: no unforced errors.", "savvy"),
    "feedback": ("Feedback", "Telling the crew what the car needs; improves setups over a weekend.", "savvy"),
    "fitness": ("Fitness", "Stamina for long and hot races; recovery from injury.", "physical"),
}
LEGACY = {"consistency", "racecraft", "feedback"}  # stored as 0-100 traits on Driver since v1

TRACK_TYPES: dict[str, str] = {
    "short": "Short tracks", "intermediate": "Intermediate ovals", "superspeedway": "Superspeedways (draft)",
    "road": "Road courses", "dirt": "Dirt tracks",
}

PERSONALITY: dict[str, tuple[str, str]] = {
    "work_ethic": ("Work ethic", "Puts in the hours: develops faster, ages slower."),
    "intelligence": ("Intelligence", "Learns tracks and race strategy quickly; manages tires and fuel."),
    "leadership": ("Leadership", "Lifts a team: crew morale, teammates, sponsor relations."),
    "loyalty": ("Loyalty", "Stays with a team and sponsor that stayed with them."),
    "greed": ("Greed", "Follows the money: salary demands, jumping to the highest bidder."),
    "ambition": ("Desire to win", "Wants to be in the best car and to move up; will leave a losing team."),
    "temper": ("Temper", "Short fuse: payback on track, run-ins with rivals and the media."),
}


def _seed(d: "Driver", salt: int) -> random.Random:
    return random.Random(d.id * 7_368_787 + salt)


def ensure(d: "Driver") -> None:
    """Create skill offsets and personality for drivers that predate them (old saves).

    Track-type experience is built later, on first use (``track_skills``): it depends on the
    level the driver has raced at, which isn't known yet when a driver is created."""
    if d.skills and d.personality:
        return
    rng = _seed(d, 11)
    if not d.skills:
        d.skills = new_offsets(rng)
    if not d.personality:
        d.personality = new_personality(rng, d)


def track_skills(d: "Driver") -> dict[str, float]:
    """Experience by track type (0..1), built from the driver's background the first time it's needed."""
    if not d.track_skill:
        d.track_skill = initial_track_skill(d, _seed(d, 13))
    return d.track_skill


def new_offsets(rng: random.Random) -> dict[str, float]:
    """Talent profile: how each skill sits around overall ability (sd ~6 = a 20-80 grade either way)."""
    out = {}
    for k in SKILLS:
        if k in LEGACY:
            continue
        out[k] = round(rng.gauss(0, 6), 1)
    # A little structure: quick drivers tend to qualify well; savvy skills move together.
    out["qualifying"] = round(0.55 * out["speed"] + 0.75 * out["qualifying"], 1)
    savvy = rng.gauss(0, 3)
    for k in ("tire_management", "fuel_saving", "defending", "composure"):
        out[k] = round(out[k] * 0.85 + savvy, 1)
    for tt in TRACK_TYPES:   # natural feel for a kind of track (a superspeedway ace, a road-course ringer)
        out[f"tt_{tt}"] = round(rng.gauss(0, 2.5), 1)
    return out


def new_personality(rng: random.Random, d: Optional["Driver"] = None) -> dict[str, float]:
    p = {k: round(clamp(rng.gauss(50, 16), 1, 99)) for k in PERSONALITY}
    if d is not None:
        # The v1 traits already describe two of these.
        p["work_ethic"] = round(d.professionalism)
        p["ambition"] = round(d.determination)
        p["temper"] = round(clamp(0.6 * p["temper"] + 0.4 * d.aggression, 1, 99))
    return p


def initial_track_skill(d: "Driver", rng: random.Random) -> dict[str, float]:
    """Experience by track type from where they've raced (0..1)."""
    disc = d.primary_discipline
    base = d.proficiency.get(disc, 0.3)
    if disc == "dirt_oval":
        weights = {"dirt": 1.0, "short": 0.25, "intermediate": 0.05, "superspeedway": 0.0, "road": 0.0}
    elif disc in ("open_wheel", "sports_car", "touring_car", "club_road", "karting"):
        weights = {"road": 1.0, "short": 0.15, "intermediate": 0.25, "superspeedway": 0.1, "dirt": 0.0}
    else:  # stock cars
        tier = max(d.max_tier, d.tier if d.series_id else 0)
        weights = {"short": 1.0, "intermediate": min(1.0, 0.15 * tier), "superspeedway": min(1.0, 0.1 * tier),
                   "road": 0.1 + 0.05 * tier, "dirt": 0.1}
    known = d.skills or {}   # experience measured from real results (history/ratings.py)
    return {k: round(clamp(max(base * w * rng.uniform(0.8, 1.15), known.get(f"exp_{k}", 0.0)), 0, 1), 3)
            for k, w in weights.items()}


# ---------------------------------------------------------------------------------- reading
def offset(d: "Driver", key: str) -> float:
    if key in LEGACY:
        return (getattr(d, key) - 50) * 0.4
    return d.skills.get(key, 0.0)


def base(d: "Driver", discipline: Optional[str] = None) -> float:
    """Usable ability in a discipline (experience in that kind of car scales raw ability)."""
    return d.effective_ability(discipline or d.primary_discipline)


def value(d: "Driver", key: str, discipline: Optional[str] = None) -> float:
    """Current skill, 0-100 (same scale as ability), in the driver's own discipline by default."""
    return clamp(base(d, discipline) + offset(d, key), 1, 99)


def potential(d: "Driver", key: str) -> float:
    """Ceiling for this skill. Physical tools are near their ceiling early; savvy keeps headroom."""
    extra = {"physical": 0.0, "skill": 1.5, "savvy": 4.0}[SKILLS[key][2]]
    return clamp(d.potential + offset(d, key) + extra, value(d, key), 99)


def track_bonus(d: "Driver", track_type: str) -> float:
    """Talent for a kind of track, in ability points (from results for real drivers)."""
    return d.skills.get(f"tt_{track_type}", 0.0) if d.skills else 0.0


def track_factor(d: "Driver", track_type: str) -> float:
    """Share of ability usable on this kind of track (0.82 .. 1.0) from experience there."""
    exp = track_skills(d).get(track_type, 0.0)
    return 0.82 + 0.18 * exp


def trait(d: "Driver", key: str) -> float:
    return float(d.personality.get(key, 50)) if d.personality else 50.0


def track_type_of(track) -> str:
    """Classify a track for skills and the race engine."""
    f = track.facts
    surface = (f.surface or "paved").lower()
    if "dirt" in surface or "clay" in surface:
        return "dirt"
    kind = (f.track_type or "").lower()
    if kind in ("road", "street", "road_course", "street_circuit", "roval", "kart_circuit") or "road" in kind or "roval" in kind:
        return "road"
    length = f.length_mi or 0.5
    if length >= 2.0 and track.sim.drafting_effect >= 60:
        return "superspeedway"
    if length > 1.0:
        return "intermediate"
    return "short"


# ---------------------------------------------------------------------------------- development
def develop(d: "Driver", age: int, starts: int, rng: random.Random, laps_by_type: Optional[dict] = None) -> None:
    """Yearly per-skill development on top of overall ability (lifecycle.develop moves ability)."""
    ensure(d)
    we = trait(d, "work_ethic")
    iq = trait(d, "intelligence")
    seat = min(1.0, starts / 18)
    past_peak = age - d.peak_age
    for k, (_, _, kind) in SKILLS.items():
        if k in LEGACY:
            continue
        o = d.skills.get(k, 0.0)
        if kind == "savvy":
            # Experience and brains: keeps improving into the mid/late thirties.
            gain = seat * (0.35 + iq / 250) * (1.0 if age < 40 else 0.4)
            gain *= clamp(1 - o / 25, 0.0, 1.0)   # diminishing returns: savvy tops out
        elif kind == "skill":
            gain = seat * (0.25 + we / 400) * (1.0 if past_peak < 2 else 0.3)
        else:  # physical: little growth after the early twenties, fades past peak
            gain = (0.3 if age < 23 else 0.0) * (0.5 + we / 200)
            if past_peak > 0:
                gain -= (0.25 + 0.06 * past_peak) * (1.3 - we / 150)
        d.skills[k] = round(clamp(o + gain + rng.gauss(0, 0.35), -25, 25), 2)
    # Track-type skills: laps on a kind of track teach it; intelligence speeds learning.
    if laps_by_type:
        ts = track_skills(d)
        for tt, laps in laps_by_type.items():
            cur = ts.get(tt, 0.0)
            learn = laps / (laps + 1500) * (0.6 + iq / 125)
            d.track_skill[tt] = round(min(1.0, cur + (1 - cur) * learn), 3)


# ---------------------------------------------------------------------------------- display
def grade(x: float) -> int:
    """0-100 hidden scale -> OOTP-style 20-80 (5-point steps when scouted)."""
    return int(round(clamp(20 + (x - 15) * 0.75, 20, 80)))


def profile(d: "Driver", noise: float = 0.0, rng: Optional[random.Random] = None, step: int = 1) -> dict:
    """Ratings card on the 20-80 scale; ``noise`` is the scout's error (sd, hidden scale)."""
    ensure(d)
    rng = rng or random.Random(0)

    def show(x: float) -> int:
        g = grade(x + (rng.gauss(0, noise) if noise else 0.0))
        return int(round(g / step) * step)

    skills = {}
    for k in SKILLS:
        now = show(value(d, k))
        skills[k] = {"label": SKILLS[k][0], "now": now, "pot": max(now, show(potential(d, k))), "about": SKILLS[k][1]}
    ts = track_skills(d)
    tracks = {k: {"label": v, "exp": round(100 * ts.get(k, 0.0))} for k, v in TRACK_TYPES.items()}
    return {"skills": skills, "tracks": tracks}


def personality_report(d: "Driver", exact: bool) -> list[dict]:
    """Exact numbers for your own driver; scouts' impressions (words) for everyone else."""
    ensure(d)
    out = []
    for k, (label, about) in PERSONALITY.items():
        v = trait(d, k)
        word = "very high" if v >= 75 else "high" if v >= 60 else "average" if v >= 40 else "low" if v >= 25 else "very low"
        out.append({"key": k, "label": label, "about": about, "value": round(v) if exact else None, "word": word})
    return out
