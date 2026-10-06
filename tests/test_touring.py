"""Real touring series from the knowledge layer replace the generated regional tour of their region."""

import json

import pytest

from racingsim.history.db import HistoryDB
from racingsim.world.world import World, WorldConfig

VENUES = [("Hickory Motor Speedway", "Hickory", "NC"), ("South Boston Speedway", "South Boston", "VA"),
          ("Myrtle Beach Speedway", "Myrtle Beach", "SC"), ("Orange County Speedway", "Rougemont", "NC")]


@pytest.fixture(scope="module")
def tour_world(tmp_path_factory, tracks):
    root = tmp_path_factory.mktemp("hist")
    know = tmp_path_factory.mktemp("know")
    (root / "test_tour").mkdir()
    sched = [{"round": i + 1, "track": n, "city": c, "state": st, "winner": "Ace Driver"}
             for i, (n, c, st) in enumerate(VENUES * 2)]
    standings = [{"pos": 1, "name": "Ace Driver", "wiki": None, "wins": 8, "starts": 8},
                 {"pos": 2, "name": "Bo Second", "wiki": None, "wins": 0, "starts": 8},
                 {"pos": 3, "name": "Cy Third", "wiki": None, "wins": 0, "starts": 7}]
    (root / "test_tour" / "1998.json").write_text(json.dumps(
        {"series": "test_tour", "year": 1998, "official_name": "Test Late Model Tour", "teams": [],
         "standings": standings, "schedule": sched}))
    (know / "series.json").write_text(json.dumps([{
        "id": "series:test-tour", "name": "Test Late Model Tour", "game_template": "late_model_tour",
        "history_source": "test_tour", "years": {"from": 1997, "to": 2001}, "regions": ["NC", "VA", "SC"],
        "names_by_year": [{"from": 1997, "to": 2001, "name": "Test Late Model Tour"}], "confidence": "high",
        "sources": []}]))
    hist = HistoryDB.load(root, tracks, knowledge_dir=know)
    return World.generate(WorldConfig(seed=4, population_scale=0.2, start_year=1998), tracks=tracks, history=hist)


def test_real_tour_replaces_generic_regional_tour(tour_world):
    w = tour_world
    s = w.series("late_model_tour@test-tour")
    assert s.name == "Test Late Model Tour" and s.real_schedule and not s.dormant
    assert s.region_key == "southeast"
    generic = w.pyramid.series.get("late_model_tour@southeast")
    assert generic is None or generic.dormant
    # Other regions keep their generated tour.
    assert any(x.id.startswith("late_model_tour@") and not x.source and not x.dormant for x in w.pyramid.series.values())


def test_real_regulars_seeded_in_their_tour(tour_world):
    w = tour_world
    names = {w.drivers[i].name for k, i in w.real_drivers.items() if k.startswith("name:")}
    assert {"Ace Driver", "Bo Second", "Cy Third"} <= names
    ace = w.drivers[w.real_drivers["name:Ace Driver"]]
    assert ace.series_id == "late_model_tour@test-tour"
    bo = w.drivers[w.real_drivers["name:Bo Second"]]
    assert ace.ability > bo.ability


def test_tour_without_data_uses_known_venues_then_ends(tour_world):
    w = tour_world
    w.run_year()  # 1999: no season file -> known venues
    s = w.series("late_model_tour@test-tour")
    assert not s.dormant and not s.real_schedule
    assert set(s.schedule) <= set(w.history.venues("test_tour"))
    for _ in range(3):
        w.run_year()  # 2002: the tour no longer exists
    assert w.series("late_model_tour@test-tour").dormant
    assert not w.series("late_model_tour@southeast").dormant
