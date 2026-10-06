"""Owner goals and job security."""

import pytest

from racingsim.career import goals as G
from racingsim.world.entities import SeasonRecord


@pytest.fixture(scope="module")
def world(tracks):
    from racingsim.world.world import World, WorldConfig
    w = World.generate(WorldConfig(seed=6, population_scale=0.12, start_year=2018), tracks=tracks)
    G.set_goals(w)
    return w


def _cup(world):
    return sorted(((t.equipment, world.drivers[d]) for t in world.teams_in("cup_series") for d in t.roster[:t.cars] if d),
                  key=lambda x: -x[0])


def test_goals_follow_the_car(world):
    cars = _cup(world)
    best, worst = cars[0][1], cars[-1][1]
    assert best.goal["target"] == 3 and "championship" in best.goal["label"]
    assert worst.goal["target"] > 20
    assert all(d.goal["year"] == world.year and d.goal["series_id"] == "cup_series" for _, d in cars)


def _rec(world, d, pos, wins=0):
    return SeasonRecord(year=world.year, series_id=d.goal["series_id"], tier=7, discipline="stock_car",
                        team_id=d.team_id, starts=36, wins=wins, top5=5, avg_finish=12.0, expected_finish=14.0,
                        championship_pos=pos, field_size=36, champion=pos == 1)


def test_owner_verdicts_move_job_security(world):
    from racingsim.sim.season import SeasonResults
    cars = _cup(world)
    star, slump = cars[10][1], cars[3][1]
    star.job_security = slump.job_security = 60.0
    slump.seat_funded = True
    res = SeasonResults()
    res.records[star.id] = _rec(world, star, 2, wins=4)
    res.records[slump.id] = _rec(world, slump, 34)
    G.review(world, res)
    assert star.goal["result"] == "exceeded" and star.job_security > 60
    assert slump.goal["result"] == "well short" and slump.job_security < 45
    G.review(world, res)                                     # judged once per season
    assert star.goal["result"] == "exceeded"
    slump.job_security = 10
    assert G.fire_chance(slump) > 0.5
    slump.seat_funded = False                                # paid seats aren't fired for results
    assert G.fire_chance(slump) == 0.0
    assert G.security_word(10) == "on the hot seat" and G.security_word(90) == "untouchable"
