"""A playable game session: one world + the player's career, stepped from the UI."""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Optional

from ..career.offseason import begin_offseason, complete_offseason
from ..sim.season import SEASON_WEEKS, SeasonRunner
from ..world.entities import RETIRED
from ..world.world import World, WorldConfig, YearSummary
from . import career

SAVE_DIR = Path(__file__).resolve().parent.parent.parent / "saves"
SAVE_VERSION = 1


class Game:
    def __init__(self, world: World):
        self.world = world
        self.phase = "season"
        self.summary = YearSummary(year=world.year)
        world.season = SeasonRunner(world, self.summary)
        self.last_message = ""
        self.version = SAVE_VERSION

    # ------------------------------------------------------------------ setup
    @classmethod
    def new(cls, first: str, last: str, region: str, age: int, discipline: str, background: str,
            talent: str = "unknown", seed: int = 2026, scale: float = 0.6) -> "Game":
        world = World.generate(WorldConfig(seed=seed, population_scale=scale))
        d = career.create_player(world, first, last, region, age, discipline, background, talent)
        game = cls(world)
        s = world.series(d.series_id)
        world.post("player", f"{d.name}, {d.age(world.year)}, from {world.geo.get(d.home_region).name}, "
                             f"starts out in the {s.name}. Every career starts somewhere.",
                   driver_id=d.id, series_id=s.id, week=0, importance=3)
        return game

    # ------------------------------------------------------------------ season
    @property
    def runner(self) -> SeasonRunner:
        return self.world.season

    def sim_week(self) -> list[dict]:
        if self.phase != "season":
            raise ValueError("The season is over: make your off-season decisions first.")
        ran = self.runner.step()
        if self.runner.finished:
            self._end_season()
        return ran

    def sim_until(self, target: str) -> list[dict]:
        """target: 'week', 'race' (until the player's next race has run) or 'season'."""
        if target == "week":
            return self.sim_week()
        ran: list[dict] = []
        player = self.world.player
        stop_week = None
        if target == "race" and player is not None:
            stop_week = self.runner.next_week_for(player)
        start_year = self.world.year
        while self.phase == "season" and self.world.year == start_year:
            ran += self.sim_week()
            if target == "race" and (stop_week is None or self.runner.week >= stop_week):
                break
        return ran

    def _end_season(self) -> None:
        results = self.runner.res
        begin_offseason(self.world, results, self.summary)
        self.world.market.player_actions = set()
        self.world.market.player_offers = None
        self.phase = "offseason"
        p = self.world.player
        if p is not None and p.status == RETIRED:
            # Nothing to decide: roll straight on.
            self._finish_offseason()

    # ------------------------------------------------------------------ off-season
    def menu(self) -> dict:
        if self.phase != "offseason":
            return {"choices": [], "actions": []}
        return career.offseason_menu(self.world)

    def act(self, action: str, arg: Optional[str] = None) -> str:
        if self.phase != "offseason":
            raise ValueError("Actions are available in the off-season.")
        self.last_message = career.apply_action(self.world, action, arg)
        return self.last_message

    def choose(self, option_id: str) -> str:
        if self.phase != "offseason":
            raise ValueError("Nothing to decide right now.")
        msg = "On to next season." if option_id == "continue" else \
            career.apply_choice(self.world, self.summary, option_id)
        self._finish_offseason()
        self.last_message = msg
        return msg

    def _finish_offseason(self) -> None:
        complete_offseason(self.world, self.summary)
        self.world.end_year(self.summary)
        self.summary = YearSummary(year=self.world.year)
        self.world.season = SeasonRunner(self.world, self.summary)
        self.phase = "season"

    # ------------------------------------------------------------------ persistence
    def save(self, name: str) -> Path:
        SAVE_DIR.mkdir(exist_ok=True)
        path = SAVE_DIR / f"{_safe(name)}.rsim"
        with open(path, "wb") as fh:
            pickle.dump(self, fh, protocol=pickle.HIGHEST_PROTOCOL)
        return path

    @staticmethod
    def load(name: str) -> "Game":
        path = SAVE_DIR / f"{_safe(name)}.rsim"
        with open(path, "rb") as fh:
            return pickle.load(fh)

    @staticmethod
    def saves() -> list[dict]:
        if not SAVE_DIR.exists():
            return []
        out = []
        for p in sorted(SAVE_DIR.glob("*.rsim"), key=lambda p: -p.stat().st_mtime):
            out.append({"name": p.stem, "modified": p.stat().st_mtime, "size": p.stat().st_size})
        return out

    @property
    def weeks(self) -> int:
        return SEASON_WEEKS


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:60] or "save"
