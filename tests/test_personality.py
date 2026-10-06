"""Personality in action: morale, rivalries and paybacks, team chemistry, contract leanings."""

import random

import pytest

from racingsim.career import morale as M
from racingsim.sim import engine as E
from racingsim.sim.race import Entry
from racingsim.world import skills as S


@pytest.fixture(scope="module")
def world(tracks):
    from racingsim.world.world import World, WorldConfig
    return World.generate(WorldConfig(seed=5, population_scale=0.12, start_year=2016), tracks=tracks)


def _active(world, n):
    ds = [d for d in world.drivers.values() if d.status == "active"][:n]
    for d in ds:
        S.ensure(d)
    return ds


def test_wrecks_build_grudges_and_paybacks_happen(world):
    tr = world.tracks.get("martinsville-speedway-va")
    ds = _active(world, 24)
    hot, target = ds[0], ds[1]
    hot.personality["temper"] = 99
    hot.rivals = {target.id: 100.0}
    paybacks = 0
    for seed in range(60):
        r = E.run([Entry([d], 60.0) for d in ds], tr, 7, 0.6, random.Random(seed))
        paybacks += sum(1 for a, t in r.paybacks if a == hot.id and t == target.id)
        for inst, victims, _ in r.incidents:
            assert inst not in victims
    assert 1 <= paybacks <= 15          # about 12% of races at full heat and temper

    victim, culprit = ds[2], ds[3]
    victim.rivals = {}
    M.incidents(world, [(culprit.id, [victim.id], False)])
    assert victim.rivals[culprit.id] > 10
    before = victim.rivals[culprit.id]
    M.incidents(world, [(culprit.id, [victim.id], True)])      # a big one: less blame
    assert victim.rivals[culprit.id] - before < before


def test_payback_penalties(world):
    from racingsim.sim.season import _Acc, _serve_suspension
    a, t = _active(world, 2)
    a.rivals = {t.id: 90.0}
    a.savings, a.suspension = 1_000_000.0, 0
    acc = {a.id: _Acc(series_id="x", points=100.0)}
    other = {a.id: _Acc(series_id="y", points=100.0)}
    M.payback(world, a.id, t.id, 7, "Cup", "Martinsville", 5, other, "x")
    assert other[a.id].points == 100.0              # a substitute's own championship is untouched
    a.suspension = 0
    world.rng.seed(1)
    news = []
    for _ in range(10):            # suspensions are a judgement call: likely over ten tries at heat 90
        a.rivals[t.id] = 90.0
        news += M.payback(world, a.id, t.id, 7, "Cup", "Martinsville", 5, acc, "x")
    assert acc[a.id].points == 100.0 - 10 * M.PAYBACK_POINTS[7]
    assert a.savings < 1_000_000.0
    assert t.rivals.get(a.id, 0) > 0                 # the target remembers
    assert a.rivals[t.id] < 90                       # settled, for now
    assert a.suspension == 1 and any("suspended" in n for n in news)
    tr = world.tracks.get("martinsville-speedway-va")
    _serve_suspension(world, a, tr, "x", 6)
    assert a.suspension == 0


def test_team_chemistry(world):
    team = next(t for t in world.teams.values() if len([i for i in t.roster if i]) >= 2)
    ds = [world.drivers[i] for i in team.roster if i]
    for d in ds:
        S.ensure(d)
        d.personality.update(leadership=85, temper=30, ambition=50)
        d.morale = 60
    good = M.chemistry(world, team)
    for d in ds:
        d.personality.update(leadership=30, temper=95, ambition=95)
    bad = M.chemistry(world, team)
    assert good > 0 > bad


def test_morale_moves_with_results_and_shapes_contracts(world):
    d = _active(world, 1)[0]
    d.morale = 60
    M.after_race(d, 1, 30, 20, False, False)
    won = d.morale
    M.after_race(d, 30, 30, 5, True, True)
    assert won > 60 > d.morale - 5 and d.morale < won
    d.personality["loyalty"] = 50
    d.morale = 90
    happy = M.resign_chance(d)
    d.morale = 20
    assert M.resign_chance(d) < happy
    assert M.switch_margin(d) < 5                    # unhappy: easier to lure away
    d.personality["loyalty"] = 95
    d.morale = 60
    assert M.switch_margin(d) > 5                    # loyal: needs a clearly better car


def test_offseason_morale_and_rivals_cool(world):
    from racingsim.sim.season import SeasonResults
    d = _active(world, 1)[0]
    other = next(x for x in world.drivers.values() if x.id != d.id and x.status != "retired")
    d.rivals = {other.id: 50.0, -1: 50.0}
    d.morale, d.suspension = 95, 1
    M.season_update(world, SeasonResults())
    assert d.rivals == {other.id: 35.0}               # cooled; unknown drivers dropped
    assert d.morale < 95 and d.suspension == 1      # a late-season suspension carries into next year


def test_seasons_run_with_personality(world):
    world.run_year()
    assert all(1 <= d.morale <= 99 for d in world.drivers.values())
    assert any(d.rivals for d in world.drivers.values())
