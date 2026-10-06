"""Staff: crew chiefs, spotters, pit crews, technical directors, engine builders, coaches, medical."""

import random
import statistics

import pytest

from racingsim.sim import engine as E
from racingsim.sim.race import Entry
from racingsim.world import staff as ST


@pytest.fixture(scope="module")
def world(tracks):
    from racingsim.world.world import World, WorldConfig
    return World.generate(WorldConfig(seed=11, population_scale=0.12, start_year=2016), tracks=tracks)


def test_every_team_is_fully_staffed(world):
    for team in world.teams.values():
        have = {(s.role, s.car) for s in ST.team_staff(world, team.id)}
        for role, (_, per_car, _, _) in ST.ROLES.items():
            for car in (range(team.cars) if per_car else [None]):
                assert (role, car) in have, (team.name, role, car)
    assert any(s.team_id is None for s in world.staff.values())   # a free-agent pool exists


def test_people_change_race_outcomes(world):
    tr = world.tracks.get("charlotte-motor-speedway-nc")
    drivers = [d for d in world.drivers.values() if d.status == "active"][:24]
    good = {"setup_mean": 0, "setup_sd": 1, "adjust": 1, "pit_s": 0.78, "pit_sd": 0.6, "strategy": 50,
            "aggression": 50, "awareness": 95, "restarts": 0, "mech": 1, "power": 0, "development": 0, "chemistry": 0}
    bad = dict(good, pit_s=1.25, pit_sd=1.3, awareness=5)
    stops = {"good": [], "bad": []}
    crashes = {"good": 0, "bad": 0}
    for i in range(30):
        entries = [Entry([d], 70.0, crew=(good if j % 2 == 0 else bad)) for j, d in enumerate(drivers)]
        r = E.run(entries, tr, 7, 0.6, random.Random(i))
        for f in r.finishes:
            k = "good" if f.entry.crew is good else "bad"
            crashes[k] += f.crashed
            stops[k].append(f.position)
    assert crashes["good"] < crashes["bad"]
    assert statistics.mean(stops["good"]) < statistics.mean(stops["bad"])


def test_crew_chief_chemistry(world):
    team = next(t for t in world.teams.values() if ST.member(world, t.id, "crew_chief", 0) and t.roster and t.roster[0])
    cc = ST.member(world, team.id, "crew_chief", 0)
    d = world.drivers[team.roster[0]]
    cc.style["preference"] = ST.driver_preference(d)
    match = ST.crew_effects(world, team.id, 0, d)["chemistry"]
    cc.style["preference"] = "loose" if ST.driver_preference(d) == "tight" else "tight"
    other = ST.crew_effects(world, team.id, 0, d)["chemistry"]
    assert match > other


def test_offseason_turnover_keeps_teams_staffed(world):
    import copy
    w = copy.deepcopy(world)
    w.run_year()
    assert any(s.history for s in w.staff.values())
    for team in w.teams.values():
        if w.series(team.series_id).dormant:
            continue
        roles = {s.role for s in ST.team_staff(w, team.id)}
        assert roles == set(ST.ROLES), team.name


def test_player_hires_a_crew(tracks):
    from racingsim.game.session import Game
    from racingsim.rules.garage import garage_action
    from racingsim.ui.garage_view import garage
    g = Game.new("Crew", "Boss", "IA", 17, "dirt_oval", "wealthy", seed=21, scale=0.12, start_year=2016)
    w, p = g.world, g.world.player
    v = garage(g)
    cand = v["crew"]["roles"][1]["candidates"][0]          # a spotter
    before = p.car.account + p.savings if p.car and p.car.account is not None else p.savings + p.available_funding()
    msg = garage_action(w, p, "hire", str(cand["id"]))
    assert "joins your crew" in msg and w.player_crew["spotter"] == cand["id"]
    assert ST.player_effects(w, p)["awareness"] == pytest.approx(w.staff[cand["id"]].ratings["awareness"])
    g.sim_until("season")
    g.choose("stay" if any(c["id"] == "stay" for c in g.menu()["choices"]) else
             next(c["id"] for c in g.menu()["choices"] if c.get("current")))
    assert w.player_crew == {}                               # freelancers leave at season end
    assert before > 0


def test_old_world_without_staff_is_staffed_on_load(world):
    import pickle
    from racingsim.sim.season import SeasonRunner
    from racingsim.world.world import YearSummary
    state = world.__getstate__()
    state.pop("staff")
    w = world.__class__.__new__(world.__class__)
    w.__setstate__(pickle.loads(pickle.dumps(state)))
    assert w.staff == {}
    SeasonRunner(w, YearSummary(year=w.year))
    assert w.staff
