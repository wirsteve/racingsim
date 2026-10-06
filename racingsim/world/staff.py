"""The people around the car (OOTP's coaches, scouts and trainers, for racing).

Every team in a team-run series employs:

* per car - a **crew chief** (strategy calls, setup, in-race adjustments, leadership; a
  strategy-aggression style and a loose/tight setup preference that has to suit the driver),
  a **spotter** (awareness keeps the driver out of wrecks; restarts), a **pit crew** (stop
  speed and consistency);
* per team - a **technical director** (setup baseline, development of the car through the
  season), an **engine builder** (power vs reliability), a **driver coach** (development of
  the team's drivers) and a **medical & fitness** lead (injury prevention and recovery).

Each rating has one legible effect (``crew_effects``) used by the race engine and the season.
Staff age, improve with experience, change jobs every silly season, get fired when results
fall short and retire; retired drivers with racing brains become spotters, coaches and crew
chiefs. The player sees staff through the same 20-80 scale as drivers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..util import clamp

if TYPE_CHECKING:
    from .entities import Driver, Team
    from .world import World

# role: (label, per_car, ratings, description)
ROLES: dict[str, tuple[str, bool, tuple[str, ...], str]] = {
    "crew_chief": ("Crew chief", True, ("strategy", "setup", "adjustments", "leadership"),
                   "Calls the race: pit strategy, setup, adjustments; leads the crew."),
    "spotter": ("Spotter", True, ("awareness", "restarts"),
                "Eyes on the roof: keeps the driver out of wrecks and lines up restarts."),
    "pit_crew": ("Pit crew", True, ("speed", "consistency"),
                 "Over the wall: stop time, and how rarely a stop goes wrong."),
    "technical_director": ("Technical director", False, ("setup", "development"),
                           "Car setup baseline and how fast the car improves through a season."),
    "engine_builder": ("Engine builder", False, ("power", "reliability"),
                       "Horsepower and how often engines let go."),
    "driver_coach": ("Driver coach", False, ("coaching", "mental"),
                     "Develops the team's drivers; helps them handle pressure."),
    "medical": ("Medical & fitness", False, ("recovery", "prevention"),
                "Fitness programme, injury prevention and recovery."),
}
RATING_LABEL = {
    "strategy": "Strategy", "setup": "Setup", "adjustments": "Adjustments", "leadership": "Leadership",
    "awareness": "Awareness", "restarts": "Restarts", "speed": "Speed", "consistency": "Consistency",
    "development": "Development", "power": "Power", "reliability": "Reliability", "coaching": "Coaching",
    "mental": "Mental", "recovery": "Recovery", "prevention": "Prevention",
}
PREFERENCES = ("loose", "neutral", "tight")


@dataclass(eq=False)
class Staff:
    id: int
    first_name: str
    last_name: str
    role: str
    birth_year: int
    ratings: dict[str, float]
    style: dict = field(default_factory=dict)     # crew chief: aggression 0-100, preference
    team_id: Optional[int] = None
    car: Optional[int] = None                     # car index within the team (per-car roles)
    salary: float = 0.0
    contract_years: int = 0
    reputation: float = 30.0
    former_driver: Optional[int] = None
    retired: bool = False
    years: int = 0                                # seasons in this role
    history: list = field(default_factory=list)   # [year, team name, series name, wins, titles]
    wins: int = 0
    titles: int = 0

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def age(self, year: int) -> int:
        return year - self.birth_year

    def overall(self) -> float:
        r = self.ratings
        return sum(r.values()) / max(len(r), 1)


# ------------------------------------------------------------------------------ creation
def new_staff(world: "World", role: str, quality: float, rng: random.Random, age: Optional[int] = None,
              former: Optional["Driver"] = None) -> Staff:
    from .names import driver_name
    first, last = (former.first_name, former.last_name) if former else driver_name(rng)
    age = age if age is not None else int(clamp(rng.gauss(42, 9), 24, 68))
    ratings = {k: round(clamp(rng.gauss(quality, 9), 5, 97), 1) for k in ROLES[role][2]}
    style: dict = {}
    if role == "crew_chief":
        style = {"aggression": round(clamp(rng.gauss(50, 18), 5, 95)), "preference": rng.choice(PREFERENCES)}
    s = Staff(id=world.next_id("staff"), first_name=first, last_name=last, role=role,
              birth_year=world.year - age, ratings=ratings, style=style,
              reputation=clamp(quality * 0.6 + rng.gauss(0, 8), 1, 99),
              former_driver=former.id if former else None)
    world.staff[s.id] = s
    return s


def team_quality(world: "World", team: "Team") -> float:
    """Typical staff rating a team of this level and standing can attract."""
    tier = world.series(team.series_id).tier
    return clamp(30 + tier * 5 + (team.equipment - 55) * 0.35 + (team.reputation - 50) * 0.1, 15, 90)


def staff_team(world: "World", team: "Team", rng: Optional[random.Random] = None) -> None:
    """Fill every empty staff position of a team with new hires at the team's level."""
    rng = rng or world.rng
    q = team_quality(world, team)
    have = {(s.role, s.car) for s in team_staff(world, team.id)}
    for role, (_, per_car, _, _) in ROLES.items():
        for car in (range(team.cars) if per_car else [None]):
            if (role, car) in have:
                continue
            s = new_staff(world, role, q + rng.gauss(0, 4), rng)
            hire(world, s, team, car, years=rng.randint(1, 3))


def seed_staff(world: "World") -> None:
    """World generation: staff every team-run team and build a free-agent pool."""
    rng = random.Random(world.config.seed * 31 + 7)
    world.cache["staff_seeding"] = True      # lookups below must not try to seed again
    for team in sorted(world.teams.values(), key=lambda t: t.id):
        staff_team(world, team, rng)
    world.cache.pop("staff_seeding", None)
    for role in ROLES:
        n = max(3, len(world.teams) // 6)
        for _ in range(n):
            new_staff(world, role, rng.uniform(25, 70), rng)
    rebuild_index(world)


def hire(world: "World", s: Staff, team: "Team", car: Optional[int], years: int = 2) -> None:
    s.team_id, s.car = team.id, car
    s.contract_years = years
    s.salary = salary_for(world, s, team)
    world.cache.pop("staff_by_team", None)


def release(world: "World", s: Staff) -> None:
    s.team_id, s.car, s.contract_years, s.salary = None, None, 0, 0.0
    world.cache.pop("staff_by_team", None)


def salary_for(world: "World", s: Staff, team: "Team") -> float:
    tier = world.series(team.series_id).tier
    base = {0: 0, 1: 0, 2: 15_000, 3: 40_000, 4: 70_000, 5: 120_000, 6: 200_000, 7: 400_000}[min(tier, 7)]
    if s.role == "crew_chief":
        base *= 2.0
    elif s.role in ("pit_crew",):
        base *= 2.5   # a whole over-the-wall crew
    return round(base * (0.5 + s.overall() / 80))


# ------------------------------------------------------------------------------ lookup
def ensure_seeded(world: "World") -> None:
    """Saves from before staff existed: hire everyone (and build the free-agent pool) on first use."""
    if not world.staff and world.teams and not world.cache.get("staff_seeding"):
        seed_staff(world)


def rebuild_index(world: "World") -> dict:
    ensure_seeded(world)
    idx: dict[int, list[Staff]] = {}
    for s in world.staff.values():
        if s.team_id is not None and not s.retired:
            idx.setdefault(s.team_id, []).append(s)
    world.cache["staff_by_team"] = idx
    return idx


def team_staff(world: "World", team_id: int) -> list[Staff]:
    idx = world.cache.get("staff_by_team")
    if idx is None:
        idx = rebuild_index(world)
    return idx.get(team_id, [])


def member(world: "World", team_id: int, role: str, car: Optional[int] = None) -> Optional[Staff]:
    for s in team_staff(world, team_id):
        if s.role == role and (car is None or s.car == car or s.car is None):
            return s
    return None


def driver_preference(d: "Driver") -> str:
    """How the driver likes the car to feel (stable per driver)."""
    return PREFERENCES[(d.id * 2654435761) % 3]


# ------------------------------------------------------------------------------ effects
def crew_effects(world: "World", team_id: Optional[int], car: int, driver: Optional["Driver"]) -> Optional[dict]:
    """What this car's people are worth on race day (None for cars without a team; missing roles count as
    average)."""
    if team_id is None:
        return None
    return effects(lambda role: member(world, team_id, role, car), driver)


PLAYER_ROLES = ("crew_chief", "spotter", "pit_crew")


def player_crew(world: "World") -> dict[str, Staff]:
    """People the player hired for their own car this season."""
    out = {}
    for role, sid in (getattr(world, "player_crew", None) or {}).items():
        s = world.staff.get(sid)
        if s is not None and not s.retired and s.team_id is None:
            out[role] = s
    return out


def player_effects(world: "World", driver: "Driver") -> Optional[dict]:
    crew = player_crew(world)
    if not crew:
        return None
    return effects(lambda role: crew.get(role), driver, neutral=True)


def hire_cost(world: "World", s: Staff, tier: int) -> float:
    """A season of a freelance crew member for a self-run racer at this level."""
    base = {0: 1_500, 1: 3_000, 2: 8_000, 3: 25_000, 4: 45_000, 5: 90_000, 6: 150_000, 7: 300_000}[min(max(tier, 0), 7)]
    if s.role == "pit_crew":
        base *= 1.5
    elif s.role == "crew_chief":
        base *= 1.3
    return round(base * (0.4 + s.overall() / 70))


def effects(get, driver: Optional["Driver"], neutral: bool = False) -> dict:
    """Race-day numbers from whoever ``get(role)`` returns (missing roles count as average)."""
    r = lambda role, key, default=50.0: (m.ratings.get(key, default) if (m := get(role)) else default)  # noqa: E731
    cc = get("crew_chief")
    setup = (r("crew_chief", "setup") + r("technical_director", "setup")) / 2
    chem = 0.0
    if cc is not None and driver is not None:
        pref = cc.style.get("preference", "neutral")
        dp = driver_preference(driver)
        chem = 0.8 if pref == dp else (-1.5 if "neutral" not in (pref, dp) else 0.0)
    return {
        "setup_mean": (setup - 50) * 0.06 + chem,                       # perf points
        "setup_sd": clamp(1.25 - setup / 200, 0.7, 1.3),                # multiplies setup variance
        "adjust": clamp(1.2 - r("crew_chief", "adjustments") / 250, 0.75, 1.25),
        "pit_s": clamp(1.25 - r("pit_crew", "speed") / 200, 0.78, 1.25),  # multiplies stop time
        "pit_sd": clamp(1.3 - r("pit_crew", "consistency") / 150, 0.6, 1.3),
        "strategy": r("crew_chief", "strategy"),
        "aggression": cc.style.get("aggression", 50) if cc else 50,
        "awareness": r("spotter", "awareness"),
        "restarts": (r("spotter", "restarts") - 50) / 10,              # restart points
        "mech": clamp(1.3 - r("engine_builder", "reliability") / 170, 0.7, 1.3),
        "power": (r("engine_builder", "power") - 50) * 0.08,            # equipment points
        "development": 0.0 if neutral else (r("technical_director", "development") - 50) / 50,
        "chemistry": chem,
    }


def coach_bonus(world: "World", d: "Driver") -> float:
    """Development multiplier from the team's driver coach (0.9 .. 1.15)."""
    if d.team_id is None:
        return 1.0
    c = member(world, d.team_id, "driver_coach")
    return 1.0 if c is None else clamp(1 + (c.ratings.get("coaching", 50) - 50) / 330, 0.9, 1.15)


def medical(world: "World", d: "Driver") -> tuple[float, float]:
    """(injury chance multiplier, recovery multiplier) from the team's medical lead."""
    if d.team_id is None:
        return 1.0, 1.0
    m = member(world, d.team_id, "medical")
    if m is None:
        return 1.0, 1.0
    return (clamp(1.2 - m.ratings.get("prevention", 50) / 250, 0.8, 1.2),
            clamp(0.8 + m.ratings.get("recovery", 50) / 250, 0.8, 1.2))


# ------------------------------------------------------------------------------ the off-season
def offseason(world: "World", summary=None) -> list[str]:
    """Staff age and develop, contracts tick, poor results cost jobs, positions get filled.
    Returns news lines."""
    rng = world.rng
    news = []
    year = world.year
    ensure_seeded(world)
    team_pct = _team_results(world)
    for s in sorted(world.staff.values(), key=lambda x: x.id):
        if s.retired:
            continue
        age = s.age(year)
        for k in s.ratings:   # experience until ~50, then slow decline
            drift = (0.6 if age < 40 else 0.25 if age < 52 else -0.5) + rng.gauss(0, 0.8)
            s.ratings[k] = round(clamp(s.ratings[k] + drift, 5, 97), 1)
        s.years += 1
        if age >= 62 and rng.random() < 0.15 + (age - 62) * 0.05:
            s.retired = True
            release(world, s)
            continue
        if s.team_id is None:
            continue
        team = world.teams.get(s.team_id)
        if team is None or world.series(team.series_id).dormant:
            release(world, s)
            continue
        pct = team_pct.get(team.id)
        if pct is not None:
            s.reputation = clamp(s.reputation * 0.85 + (pct * 100) * 0.15 + (s.wins and 2), 1, 99)
        s.contract_years -= 1
        expect = clamp((team.equipment - 30) / 70, 0.15, 0.85)
        fired = (s.role == "crew_chief" and pct is not None and pct < expect - 0.25 and rng.random() < 0.5)
        if fired or (s.contract_years <= 0 and rng.random() < 0.35 + (0.3 if pct is not None and pct < expect else 0)):
            if fired and s.role == "crew_chief" and world.series(team.series_id).tier >= 5:
                news.append(f"{team.name} part ways with crew chief {s.name}")
            release(world, s)
        elif s.contract_years <= 0:
            s.contract_years = rng.randint(1, 3)
            s.salary = salary_for(world, s, team)
    _hire_round(world, rng, news)
    rebuild_index(world)
    return news


def _team_results(world: "World") -> dict[int, float]:
    """Last season's average championship percentile per team (1 = champion)."""
    out: dict[int, list[float]] = {}
    for d in world.drivers.values():
        if d.history and d.history[-1].year == world.year and d.history[-1].team_id is not None:
            r = d.history[-1]
            out.setdefault(r.team_id, []).append(1 - (r.championship_pos - 1) / max(1, r.field_size - 1))
    return {k: sum(v) / len(v) for k, v in out.items()}


def _hire_round(world: "World", rng: random.Random, news: list[str]) -> None:
    """Open positions are filled top-down: the best teams hire first, from the free agents when someone
    suitable is available, otherwise a newcomer. Old unemployed staff drift out of the sport."""
    pool: dict[str, list[Staff]] = {}
    for s in world.staff.values():
        if not s.retired and s.team_id is None:
            pool.setdefault(s.role, []).append(s)
    for role in pool:
        pool[role].sort(key=lambda s: -s.overall())
    teams = sorted((t for t in world.teams.values() if not world.series(t.series_id).dormant),
                   key=lambda t: (-world.series(t.series_id).tier, -t.reputation, t.id))
    idx = rebuild_index(world)
    for team in teams:
        have = {(s.role, s.car) for s in idx.get(team.id, [])}
        q = team_quality(world, team)
        for role, (_, per_car, _, _) in ROLES.items():
            for car in (range(team.cars) if per_car else [None]):
                if (role, car) in have:
                    continue
                cands = [s for s in pool.get(role, []) if s.overall() <= q + 12]
                pick = cands[0] if cands else None
                if pick is None:
                    pick = new_staff(world, role, q + rng.gauss(-3, 5), rng, age=int(clamp(rng.gauss(36, 7), 24, 60)))
                else:
                    pool[role].remove(pick)
                hire(world, pick, team, car, years=rng.randint(1, 3))
                if role == "crew_chief" and world.series(team.series_id).tier >= 5:
                    news.append(f"{team.name} hire {pick.name} as crew chief")
    # Nobody waits forever: the free-agent pool stays about the size it started at.
    cap = max(3, len(world.teams) // 6)
    for role, left in pool.items():
        for i, s in enumerate(sorted(left, key=lambda x: -x.overall())):
            if i >= cap or (s.age(world.year) >= 55 and rng.random() < 0.3):
                s.retired = True


def from_retired_driver(world: "World", d: "Driver") -> Optional[Staff]:
    """Some retiring racers stay in the sport: spotters, coaches, crew chiefs."""
    from . import skills
    rng = world.rng
    if d.max_tier < 3 or d.is_player or rng.random() > 0.25:
        return None
    iq = skills.trait(d, "intelligence")
    fb = d.feedback
    if fb > 60 and iq > 55 and rng.random() < 0.4:
        role = "crew_chief"
    elif iq > 50 and rng.random() < 0.5:
        role = "driver_coach"
    else:
        role = "spotter"
    q = clamp(25 + d.max_tier * 5 + (iq - 50) * 0.3 + (fb - 50) * 0.2, 15, 85)
    s = new_staff(world, role, q, rng, age=d.age(world.year), former=d)
    return s


def record_season(world: "World", results) -> None:
    """Credit staff with wins and titles: per-car people for their own car, team-wide roles for the team."""
    champs = set(results.champions.values())
    team_w: dict[int, int] = {}
    car_w: dict[tuple, int] = {}
    team_t: set = set()
    car_t: set = set()
    for did, rec in results.records.items():
        if rec.team_id is None or rec.team_id not in world.teams:
            continue
        team = world.teams[rec.team_id]
        team_w[team.id] = team_w.get(team.id, 0) + rec.wins
        car = team.roster.index(did) // max(team.drivers_per_car, 1) if did in team.roster else None
        if car is not None:
            car_w[(team.id, car)] = car_w.get((team.id, car), 0) + rec.wins
        if did in champs:
            team_t.add(team.id)
            if car is not None:
                car_t.add((team.id, car))
    for s in world.staff.values():
        if s.retired or s.team_id is None or s.team_id not in world.teams:
            continue
        team = world.teams[s.team_id]
        if ROLES[s.role][1]:
            w, t = car_w.get((team.id, s.car), 0), int((team.id, s.car) in car_t)
        else:
            w, t = team_w.get(team.id, 0), int(team.id in team_t)
        s.wins += w
        s.titles += t
        s.history.append([world.year, team.name, world.series(team.series_id).name, w, t])
