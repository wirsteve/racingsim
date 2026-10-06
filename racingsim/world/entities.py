"""Persistent world entities: drivers, teams, sponsors, manufacturers.

Driver ratings are *hidden truth* values on a 0-100 scale. Teams, sponsors and
manufacturers never read them directly when making decisions; they work from
results, reputation and scouting reports (see ``career/scouting.py``), which is
what lets genuinely talented drivers go unnoticed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DISCIPLINES = ("karting", "stock_car", "dirt_oval", "open_wheel", "sports_car", "touring_car", "club_road")

# Status values
ACTIVE = "active"          # has a ride (own car or team seat) this season
PART_TIME = "part_time"    # racing a partial schedule because money ran short
SIDELINED = "sidelined"    # wants to race, cannot afford/obtain a ride this season
RETIRED = "retired"


@dataclass
class SeasonRecord:
    year: int
    series_id: str
    tier: int
    discipline: str
    team_id: Optional[int]
    starts: int
    wins: int
    top5: int
    avg_finish: float
    expected_finish: float      # finish predicted from equipment -> outperformance signal
    championship_pos: int
    field_size: int
    champion: bool = False
    crown_jewel_wins: list[str] = field(default_factory=list)
    note: str = ""
    series_name: str = ""       # the series' name that season (names change by era)
    team_name: str = ""         # for real (imported) seasons, where no Team entity exists
    points: Optional[float] = None  # championship points under that season's real system
    top10: int = 0
    winnings: float = 0.0       # purses + points fund (2025 USD)
    dnq: int = 0                # nights the car missed the feature
    poles: int = 0
    laps_led: int = 0
    laps: int = 0
    dnfs: int = 0
    avg_start: Optional[float] = None
    rating: Optional[float] = None  # average NASCAR-style driver rating (lap-by-lap races)
    par: Optional[float] = None     # positions above replacement (sim/season.py)
    splits: dict = field(default_factory=dict)  # track type -> [starts, wins, top5, finish sum, laps led]

    def __setstate__(self, state: dict) -> None:
        state.setdefault("splits", {})   # records saved before splits existed
        self.__dict__.update(state)


@dataclass
class SponsorDeal:
    sponsor_id: int
    amount: float               # USD per season
    years_left: int


@dataclass
class Driver:
    id: int
    first_name: str
    last_name: str
    birth_year: int
    home_region: str
    country: str
    lat: float
    lon: float

    # ---- hidden ratings (0-100) ----
    ability: float              # current overall driving ability
    potential: float            # ceiling ability
    peak_age: float             # individual development curve
    consistency: float
    racecraft: float
    aggression: float
    feedback: float             # technical feedback / car development
    adaptability: float         # ease of moving between disciplines
    marketability: float        # media / sponsor appeal (charisma, story, presence)
    professionalism: float
    determination: float        # persistence; resists quitting after setbacks

    # ---- discipline experience: proficiency 0..1 of ability usable in discipline ----
    proficiency: dict[str, float] = field(default_factory=dict)
    primary_discipline: str = "stock_car"

    # ---- money ----
    family_budget: float = 0.0  # what the family will spend on racing per season
    savings: float = 0.0        # personal wealth (pro salaries accumulate here)
    sponsors: list[SponsorDeal] = field(default_factory=list)

    # ---- career state ----
    status: str = ACTIVE
    series_id: Optional[str] = None
    team_id: Optional[int] = None
    seat_funded: bool = False   # True: team pays; False: driver brings the money
    contract_years: int = 0
    salary: float = 0.0
    home_track_id: Optional[str] = None
    tier: int = 0
    max_tier: int = 0
    years_at_tier: int = 0
    seasons_sidelined: int = 0
    first_season: int = 0

    # ---- reputation / exposure ----
    reputation: float = 0.0     # 0-100 broad standing in the paddock
    exposure: float = 0.0       # 0-100 how visible to scouts this year
    momentum: float = 0.0       # -50..50 recent trajectory ("hot hand")
    demonstrated: float = 0.0   # results-based level the paddock believes in (scouting view)
    breakout: int = 0           # seasons left on a "standout one-off" flag (research C 5.3)
    first_license_age: int = 0  # age of first competition licence (Bronze rule for Pro-Am)
    grassroots_veteran: bool = False  # ex-national driver now racing locally by choice
    is_player: bool = False           # the human's driver: the AI never decides for them
    real: bool = False                # a real person (historical mode)
    wiki: Optional[str] = None        # their Wikipedia article title
    connections: dict[str, float] = field(default_factory=dict)  # "team:12" -> 0..1, "mfr:3" -> 0..1
    program_mfr: Optional[int] = None
    program_years: int = 0
    scholarship: float = 0.0    # prize money earmarked for next season

    # ---- stats ----
    career_starts: int = 0
    career_wins: int = 0
    titles: list[str] = field(default_factory=list)
    crown_jewels: list[str] = field(default_factory=list)
    history: list[SeasonRecord] = field(default_factory=list)
    events: list[str] = field(default_factory=list)  # narrative log ("2027: signed by ...")

    # ---- health ----
    injury_races: int = 0
    injury_history: int = 0
    season_spend: float = 0.0   # one-off costs this season beyond savings (coaching, entries)
    car: Optional[object] = None  # own car (racingsim.rules.car.Car) when racing a self-run class

    # ---- OOTP-style ratings (racingsim/world/skills.py) ----
    skills: dict[str, float] = field(default_factory=dict)       # skill -> offset around ability
    track_skill: dict[str, float] = field(default_factory=dict)  # track type -> experience 0..1
    personality: dict[str, float] = field(default_factory=dict)  # work_ethic, intelligence, ... 0-100
    durability: float = 50.0                                     # high = rarely injured, heals fast
    # ---- personality in action (racingsim/career/morale.py) ----
    morale: float = 60.0                                         # 0-100
    rivals: dict[int, float] = field(default_factory=dict)       # driver id -> grudge heat 0-100
    suspension: int = 0                                          # races left on a suspension
    awards: list[str] = field(default_factory=list)              # "2027 Cup Series Rookie of the Year"
    goal: dict = field(default_factory=dict)                     # this season's owner goal (career/goals.py)
    fans: float = 0.0                                            # fan base, thousands (world/fans.py)
    job_security: float = 60.0                                   # 0-100: how safe the seat is

    def __setstate__(self, state: dict) -> None:
        # Saves from before OOTP-style ratings: per-skill data is created lazily (skills.ensure).
        for k in ("skills", "track_skill", "personality", "rivals"):
            state.setdefault(k, {})
        state.setdefault("awards", [])
        state.setdefault("goal", {})
        self.__dict__.update(state)

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def age(self, year: int) -> int:
        return year - self.birth_year

    def sponsor_money(self) -> float:
        return sum(d.amount for d in self.sponsors)

    def available_funding(self) -> float:
        """Money the driver can bring to a ride this season."""
        savings_draw = self.savings * 0.25
        return max(0.0, self.family_budget + self.sponsor_money() + savings_draw + self.scholarship
                   - self.season_spend)

    def effective_ability(self, discipline: str) -> float:
        return self.ability * (0.55 + 0.45 * self.proficiency.get(discipline, 0.0))

    def log(self, year: int, text: str) -> None:
        self.events.append(f"{year}: {text}")

    @property
    def active(self) -> bool:
        return self.status in (ACTIVE, PART_TIME)


@dataclass
class Team:
    id: int
    name: str
    series_id: str
    home_region: str
    owner_type: str             # "family", "privateer", "pro", "factory"
    equipment: float            # 0-100 car quality
    sponsor_funding: float      # USD per seat per season the team raises itself
    cars: int
    drivers_per_car: int = 1
    manufacturer_id: Optional[int] = None
    # How the owner weighs candidates (sum ~ 1). Underfunded teams lean on money.
    w_performance: float = 0.45
    w_potential: float = 0.2
    w_money: float = 0.25
    w_marketability: float = 0.1
    w_connections: float = 0.6   # how much relationships (team, manufacturer, scholarship) sway the owner
    roster: list[int] = field(default_factory=list)
    history: list[tuple[int, float]] = field(default_factory=list)  # (year, avg championship pct)
    reputation: float = 50.0
    # ---- money (world/finance.py) ----
    cash: float = 0.0           # the owner's racing account, 2025 USD
    spend: float = 0.0          # spending level: 1.0 = the series' full-season cost per car
    charters: int = 0           # Cup charters held (2016 on)
    books: list[dict] = field(default_factory=list)  # one ledger per season
    player_owned: bool = False  # owner mode (game/owner.py)
    funding_anchor: float = 0.0  # what the organisation raised when its books opened (sponsors drift back to it)
    budget_mode: str = "normal"

    def __setstate__(self, state: dict) -> None:
        state.setdefault("books", [])   # saves from before team finances
        self.__dict__.update(state)

    @property
    def seats(self) -> int:
        return self.cars * self.drivers_per_car


@dataclass
class Sponsor:
    id: int
    name: str
    industry: str
    scope: str                  # "local", "regional", "national"
    region: Optional[str]       # home state for local/regional sponsors
    budget: float               # total USD per season they will commit to racing
    min_tier: int
    max_tier: int
    loyalty: float              # 0..1 chance-weight of renewing when results dip
    committed: float = 0.0


@dataclass
class Manufacturer:
    id: int
    name: str
    disciplines: list[str]
    program_budget: float       # USD/season for driver development support
    program_slots: int
    aggressiveness: float       # 0..1 how young/early they sign
    prospects: list[int] = field(default_factory=list)
    years: dict = field(default_factory=dict)          # discipline -> [first, last] season raced
    program_years: Optional[list] = None               # [first, last] season with a driver program

    def races(self, discipline: str, year: int) -> bool:
        if not self.years:
            return discipline in self.disciplines
        span = self.years.get(discipline)
        if not span:
            return False
        spans = span if isinstance(span[0], list) else [span]  # one or several stints
        return any(a <= year <= b for a, b in spans)

    def runs_program(self, year: int) -> bool:
        if not self.program_years or self.program_slots <= 0:
            return False
        return self.program_years[0] <= year <= self.program_years[1]

    def active_disciplines(self, year: int) -> list[str]:
        return [d for d in self.disciplines if self.races(d, year)]
