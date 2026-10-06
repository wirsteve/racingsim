"""Phase 6: realism settings, weather, development focus, scouting budgets, power rankings."""

import random
import statistics

import pytest

from racingsim.sim import engine as E
from racingsim.sim import weather as W
from racingsim.sim.race import Entry
from racingsim.world import settings as ST
from racingsim.world import skills as S


@pytest.fixture(scope="module")
def world(tracks):
    from racingsim.world.world import World, WorldConfig
    return World.generate(WorldConfig(seed=12, population_scale=0.12, start_year=2018), tracks=tracks)


def _field(world, n=24):
    return [Entry([d], 65.0) for d in [d for d in world.drivers.values() if d.status == "active"][:n]]


def test_settings_validate_and_clamp(world):
    assert ST.get(world, "crashes") == 1.0
    out = ST.update(world, {"crashes": 5, "weather": 0})
    assert out["crashes"] == 2.0 and out["weather"] == 0.0
    with pytest.raises(ValueError):
        ST.update(world, {"nonsense": 1})
    ST.update(world, {k: 1.0 for k in ST.DEFAULTS})
    assert {x["key"] for x in ST.view(world)} == set(ST.DEFAULTS)


def test_crash_and_failure_settings_move_outcomes(world):
    tr = world.tracks.get("bristol-motor-speedway-tn")
    entries = _field(world)
    def run(real):
        cautions = dnf = 0
        for i in range(25):
            r = E.run(entries, tr, 7, 0.6, random.Random(i), realism=real)
            cautions += r.cautions
            dnf += sum(1 for f in r.finishes if f.box["status"] not in ("running", "crash"))
        return cautions, dnf
    calm, wild = run({"crashes": 0.25, "failures": 0.25}), run({"crashes": 2.0, "failures": 2.0})
    assert wild[0] > calm[0] and wild[1] > calm[1]


def test_weather_by_venue_and_effects(world):
    rng = random.Random(1)
    dirt = next(t for t in world.tracks if S.track_type_of(t) == "dirt")
    road = next(t for t in world.tracks if S.track_type_of(t) == "road")
    oval = world.tracks.get("charlotte-motor-speedway-nc")
    kinds = lambda tr, tier: {(W.roll(tr, tier, rng) or {}).get("kind") for _ in range(400)}
    assert "rainout" in kinds(dirt, 1)
    assert "wet" in kinds(road, 5) and "rainout" not in kinds(road, 5)
    assert {"rain_short", "hot"} <= kinds(oval, 7)
    assert all(W.roll(oval, 7, rng, scale=0) is None for _ in range(50))
    r = E.run(_field(world), oval, 7, 0.6, random.Random(3), detail=True, weather={"kind": "rain_short", "share": 0.6})
    assert r.laps < r.scheduled and any("Rain!" in t for _, t in r.log)


def test_wet_road_courses_reward_car_control(world):
    road = next(t for t in world.tracks if S.track_type_of(t) == "road" and t.sim.passing_difficulty < 90)
    ds = [d for d in world.drivers.values() if d.status == "active"][:20]
    for i, d in enumerate(ds):
        S.ensure(d)
        d.skills["car_control"] = 12.0 if i % 2 == 0 else -12.0
    entries = [Entry([d], 65.0) for d in ds]
    good = {"dry": [], "wet": []}
    for i in range(30):
        for kind in ("dry", "wet"):
            r = E.run(entries, road, 6, 0.6, random.Random(i), weather={"kind": kind} if kind == "wet" else None)
            for f in r.finishes:
                if f.entry.drivers[0].skills["car_control"] > 0:
                    good[kind].append(f.position)
    assert statistics.mean(good["wet"]) < statistics.mean(good["dry"])


def test_development_focus(world):
    from racingsim.world.entities import Driver
    def fresh(focus):
        d = Driver(id=77, first_name="Test", last_name="Kid", birth_year=2000, home_region="NC", country="USA", lat=35, lon=-80,
                   ability=50, potential=80, peak_age=28, consistency=50, racecraft=50, aggression=50, feedback=50,
                   adaptability=50, marketability=50, professionalism=50, determination=50)
        S.ensure(d)
        d.dev_focus = focus
        return d
    plain, focused = fresh(""), fresh("management")
    t0 = plain.skills["tire_management"]
    for age in range(19, 24):
        S.develop(plain, age, 30, random.Random(age))
        S.develop(focused, age, 30, random.Random(age))
    assert focused.skills["tire_management"] - t0 > plain.skills["tire_management"] - t0
    learner = fresh("tt_road")
    before = S.track_skills(learner)["road"]
    S.develop(learner, 20, 0, random.Random(1))
    assert S.track_skills(learner)["road"] > before


def test_scouting_budget_sharpens_reports(world):
    from racingsim.ui.api import scouted, scale
    ds = [d for d in world.drivers.values() if d.status == "active" and not d.is_player][:300]
    def err(level):
        world.scouting_level = level
        return statistics.mean(abs(scouted(world, d)["overall"] - scale(d.effective_ability(d.primary_discipline))) for d in ds)
    blind, elite = err("none"), err("elite")
    world.scouting_level = "standard"
    assert elite < blind


def test_power_rankings_and_rainouts_in_a_season(world):
    import copy
    from racingsim.ui.api import power_rankings
    w = copy.deepcopy(world)
    pr = power_rankings(w, "cup_series")
    assert pr and pr[0]["rank"] == 1 and len({x["id"] for x in pr}) == len(pr)
    runner_events = []
    from racingsim.sim.season import SeasonRunner
    from racingsim.world.world import YearSummary
    r = SeasonRunner(w, YearSummary(year=w.year))
    r.run_to_end()
    local = [sid for sid in r.by_series if w.series(sid).tier <= 2]
    ran = sum(len(r.race_log.get(sid, [])) for sid in local)
    scheduled = sum(len(w.series(sid).schedule) for sid in local)
    assert 0.75 * scheduled < ran < scheduled            # some weekly nights are rained out (or short of cars)
