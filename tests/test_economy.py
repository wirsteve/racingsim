"""The economic loop: fans, team books, charters, spending into speed, owners selling up."""

import copy

import pytest

from racingsim.world import fans as F
from racingsim.world import finance as FI


@pytest.fixture(scope="module")
def world(tracks):
    from racingsim.world.world import World, WorldConfig
    w = World.generate(WorldConfig(seed=9, population_scale=0.12, start_year=2017), tracks=tracks)
    w.run_year()
    return w


def test_every_racing_team_keeps_books(world):
    year = world.year - 1
    for t in world.teams.values():
        if world.series(t.series_id).dormant:
            continue
        b = t.books[-1]
        assert b["year"] == year
        assert b["net"] == pytest.approx(sum(b["revenue"].values()) - sum(b["costs"].values()), abs=10)
    cup = world.teams_in("cup_series")
    assert sum(t.charters for t in cup) == FI.CHARTERS
    per_car = [sum(t.books[-1]["revenue"].values()) / t.cars for t in cup]
    assert 5e6 < min(per_car) and max(per_car) < 60e6          # research: $8.2M-$43M per car (2024)


def test_charter_money_by_era_and_results():
    assert FI.charter_pay(2015, 0.5) == 0
    assert FI.charter_pay(2020, 0.9) > FI.charter_pay(2020, 0.1)
    assert FI.charter_pay(2026, 0.0) > 0


def test_money_buys_speed_and_broke_owners_sell(world):
    from racingsim.sim.season import SeasonResults
    w = copy.deepcopy(world)
    teams = sorted(w.teams_in("stock_national"), key=lambda t: t.equipment)
    rich, poor = teams[len(teams) // 2], teams[len(teams) // 2 - 1]
    rich.spend, poor.spend = FI.SPEND_MAX, FI.SPEND_MIN
    before = rich.equipment - poor.equipment
    poor.cash = -1e9
    FI.close_books(w, SeasonResults())
    assert rich.equipment - poor.equipment > before
    assert poor.books[-1].get("sold") and poor.cash > 0


def test_fans_follow_results_where_people_watch(world):
    from racingsim.sim.season import SeasonResults
    from racingsim.world.entities import SeasonRecord
    w = copy.deepcopy(world)
    a, b = [d for d in w.drivers.values() if d.status == "active"][:2]
    a.fans = b.fans = 100.0
    a.marketability = b.marketability = 50
    res = SeasonResults()
    for d, tier, wins in ((a, 7, 6), (b, 3, 6)):
        res.records[d.id] = SeasonRecord(year=w.year, series_id="x", tier=tier, discipline="stock_car", team_id=None,
                                         starts=30, wins=wins, top5=12, avg_finish=8.0, expected_finish=10.0,
                                         championship_pos=2, field_size=30)
    F.season_update(w, res)
    assert a.fans > b.fans > 50
    assert F.label(2500) == "2.5M" and F.label(35) == "35k" and F.label(0.8) == "800"


def test_old_team_without_books_loads(world):
    t = next(iter(world.teams.values()))
    state = dict(t.__dict__)
    state.pop("books")
    t2 = t.__class__.__new__(t.__class__)
    t2.__setstate__(state)
    assert t2.books == []
