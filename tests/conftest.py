import pytest

from racingsim.tracks import TrackDatabase
from racingsim.world.world import World, WorldConfig

SIM_YEARS = 8


@pytest.fixture(scope="session")
def tracks() -> TrackDatabase:
    return TrackDatabase.load()


@pytest.fixture(scope="session")
def fresh_world(tracks) -> World:
    return World.generate(WorldConfig(seed=11, population_scale=0.4), tracks=tracks)


@pytest.fixture(scope="session")
def simulated_world(tracks) -> World:
    """A seeded world advanced several seasons; shared by the systemic tests."""
    w = World.generate(WorldConfig(seed=7, population_scale=0.4), tracks=tracks)
    for _ in range(SIM_YEARS):
        w.run_year()
    return w
