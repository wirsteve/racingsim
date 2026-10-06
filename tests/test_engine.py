"""Lap-by-lap race engine, OOTP-style driver ratings and ratings from real results."""

import random
import statistics

import pytest

from racingsim.sim import engine as E
from racingsim.sim.race import Entry
from racingsim.world import skills as S


@pytest.fixture(scope="module")
def cup(tracks):
    from racingsim.world.world import World, WorldConfig
    w = World.generate(WorldConfig(seed=4, population_scale=0.12, start_year=2018), tracks=tracks)
    entries = [Entry([w.drivers[d]], t.equipment) for t in w.teams_in("cup_series") for d in t.roster[:t.cars] if d]
    return w, entries


def test_race_is_complete_and_consistent(cup):
    w, entries = cup
    tr = w.tracks.get("charlotte-motor-speedway-nc")
    r = E.run(entries, tr, 7, 0.6, random.Random(1), detail=True, stages=2)
    f = r.finishes
    assert [x.position for x in f] == list(range(1, len(entries) + 1))
    assert sorted(x.box["start"] for x in f) == list(range(1, len(entries) + 1))
    assert sum(x.box["led"] for x in f) == r.laps                     # every lap had a leader
    assert all(x.box["laps"] == r.laps for x in f if not x.dnf)
    assert all(20 <= x.box["rating"] <= 150 for x in f)
    assert f[0].box["status"] == "running" and r.log and len(r.stages) == 2


def test_engine_is_deterministic(cup):
    w, entries = cup
    tr = w.tracks.get("martinsville-speedway-va")
    a = E.run(entries, tr, 7, 0.6, random.Random(7))
    b = E.run(entries, tr, 7, 0.6, random.Random(7))
    assert [x.entry.drivers[0].id for x in a.finishes] == [x.entry.drivers[0].id for x in b.finishes]


def test_skill_and_track_character_matter(cup):
    w, entries = cup
    tr = w.tracks.get("charlotte-motor-speedway-nc")
    best = max(entries, key=lambda e: e.drivers[0].ability + e.equipment)
    worst = min(entries, key=lambda e: e.drivers[0].ability + e.equipment)
    pos_best, pos_worst = [], []
    for i in range(12):
        f = E.run(entries, tr, 7, 0.6, random.Random(i)).finishes
        pos = {x.entry.drivers[0].id: x.position for x in f}
        pos_best.append(pos[best.drivers[0].id])
        pos_worst.append(pos[worst.drivers[0].id])
    assert statistics.mean(pos_best) + 8 < statistics.mean(pos_worst)
    # Superspeedways wreck more cars than road courses.
    ss, road = w.tracks.get("talladega-superspeedway-al"), w.tracks.get("watkins-glen-international-ny")
    crashes = lambda t: sum(sum(x.crashed for x in E.run(entries, t, 7, 0.6, random.Random(i)).finishes) for i in range(8))
    assert crashes(ss) > crashes(road) * 2


def test_driver_rating_follows_the_fitted_curve():
    box = lambda start, arp, led=0, most=False: {"start": start, "arp": arp, "led": led, "most_led": most, "status": "running"}
    win = E.driver_rating(1, 40, box(3, 3, 120, True), 300)
    tenth = E.driver_rating(10, 40, box(12, 11), 300)
    thirtieth = E.driver_rating(30, 40, box(30, 29), 300)
    assert win > 120 and 75 < tenth < 100 and 35 < thirtieth < 60


def test_skills_profile_and_old_drivers(cup):
    w, _ = cup
    d = next(iter(w.drivers.values()))
    p = S.profile(d)
    assert set(p["skills"]) == set(S.SKILLS) and all(20 <= v["now"] <= 80 for v in p["skills"].values())
    assert all(v["pot"] >= v["now"] for v in p["skills"].values())
    d.skills, d.personality, d.track_skill = {}, {}, {}      # a driver from an old save
    S.ensure(d)
    assert d.skills and d.personality and d.track_skill
    assert len(S.personality_report(d, exact=False)) == len(S.PERSONALITY)


def test_aging_turns_speed_into_savvy():
    from racingsim.world.entities import Driver
    d = Driver(id=1, first_name="Old", last_name="Pro", birth_year=1980, home_region="NC", country="USA", lat=35, lon=-80,
               ability=70, potential=70, peak_age=30, consistency=50, racecraft=50, aggression=50, feedback=50,
               adaptability=50, marketability=50, professionalism=50, determination=50)
    S.ensure(d)
    speed0, tires0 = d.skills["speed"], d.skills["tire_management"]
    rng = random.Random(3)
    for age in range(34, 40):
        S.develop(d, age, 30, rng)
    assert d.skills["speed"] < speed0 - 2 and d.skills["tire_management"] > tires0 + 1


def test_real_drivers_rated_from_results(tracks):
    from racingsim.world.world import World, WorldConfig
    w = World.generate(WorldConfig(seed=2, population_scale=0.12, start_year=2005), tracks=tracks)
    rusty = next((d for d in w.drivers.values() if d.name == "Rusty Wallace"), None)
    if rusty is None:
        pytest.skip("Rusty Wallace not in this world")
    assert S.track_bonus(rusty, "short") > S.track_bonus(rusty, "superspeedway")
