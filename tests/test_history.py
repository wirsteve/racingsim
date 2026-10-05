"""Historical mode: real teams/drivers seeded for the start year, real future drivers as prospects."""

import json

import pytest

from racingsim.history.db import HistoryDB, match_track
from racingsim.world.world import World, WorldConfig

SEASON_1996 = {
    "series": "cup_series", "year": 1996, "official_name": "NASCAR Winston Cup Series",
    "teams": [
        {"team": "Hendrick Motorsports", "owner": "Rick Hendrick", "manufacturer": "Chevrolet",
         "cars": [{"number": "24", "full_time": True, "drivers": [{"name": "Jeff Gordon", "wiki": "Jeff_Gordon"}]},
                  {"number": "5", "full_time": True, "drivers": [{"name": "Terry Labonte", "wiki": "Terry_Labonte"}]}]},
        {"team": "Robert Yates Racing", "owner": "Robert Yates", "manufacturer": "Ford",
         "cars": [{"number": "88", "full_time": True, "drivers": [{"name": "Dale Jarrett", "wiki": "Dale_Jarrett"}]}]},
    ],
    "standings": [
        {"pos": 1, "name": "Terry Labonte", "wiki": "Terry_Labonte", "wins": 2, "starts": 31, "top5": 21, "top10": 24},
        {"pos": 2, "name": "Jeff Gordon", "wiki": "Jeff_Gordon", "wins": 10, "starts": 31, "top5": 21, "top10": 24},
        {"pos": 3, "name": "Dale Jarrett", "wiki": "Dale_Jarrett", "wins": 4, "starts": 31, "top5": 17, "top10": 21},
    ],
    "schedule": [
        {"round": 1, "track": "Daytona International Speedway", "city": "Daytona Beach", "state": "FL", "race": "Daytona 500"},
        {"round": 2, "track": "North Carolina Speedway", "city": "Rockingham", "state": "NC", "race": ""},
        {"round": 3, "track": "Richmond International Raceway", "city": "Richmond", "state": "VA", "race": ""},
        {"round": 4, "track": "Atlanta Motor Speedway", "city": "Hampton", "state": "GA", "race": ""},
    ],
}
SEASON_2005 = {
    "series": "cup_series", "year": 2005, "official_name": "NASCAR Nextel Cup Series", "teams": [],
    "standings": [{"pos": 1, "name": "Tony Stewart", "wiki": "Tony_Stewart", "wins": 5, "starts": 36}],
    "schedule": [],
}
DRIVERS = {
    "Jeff_Gordon": {"name": "Jeff Gordon", "birth_date": "1971-08-04", "state": "CA", "country": "USA"},
    "Terry_Labonte": {"name": "Terry Labonte", "birth_date": "1956-11-16", "state": "TX", "country": "USA"},
    "Dale_Jarrett": {"name": "Dale Jarrett", "birth_date": "1956-11-26", "state": "NC", "country": "USA"},
    "Tony_Stewart": {"name": "Tony Stewart", "birth_date": "1971-05-20", "state": "IN", "country": "USA"},
}


@pytest.fixture(scope="module")
def hist(tmp_path_factory):
    root = tmp_path_factory.mktemp("history")
    (root / "nascar_cup").mkdir()
    (root / "nascar_cup" / "1996.json").write_text(json.dumps(SEASON_1996))
    (root / "nascar_cup" / "2005.json").write_text(json.dumps(SEASON_2005))
    (root / "drivers_test.json").write_text(json.dumps(DRIVERS))
    return HistoryDB.load(root)


@pytest.fixture(scope="module")
def world_1996(hist, tracks):
    return World.generate(WorldConfig(seed=9, population_scale=0.2, start_year=1996), tracks=tracks, history=hist)


def test_real_cup_teams_and_drivers_seeded(world_1996):
    w = world_1996
    cup = [t for t in w.teams.values() if t.series_id == "cup_series"]
    names = {t.name for t in cup}
    assert {"Hendrick Motorsports", "Robert Yates Racing"} <= names
    gordon = w.drivers[w.real_drivers["Jeff_Gordon"]]
    assert gordon.name == "Jeff Gordon" and gordon.age(1996) == 25 and gordon.home_region == "CA"
    assert gordon.series_id == "cup_series" and gordon.real
    hendrick = next(t for t in cup if t.name == "Hendrick Motorsports")
    assert w.manufacturers[hendrick.manufacturer_id].name == "Chevrolet"


def test_real_calendar_used(world_1996):
    s = world_1996.series("cup_series")
    assert s.real_schedule
    assert s.schedule[:2] == ["daytona-international-speedway-fl", "rockingham-speedway-nc"]


def test_future_star_appears_as_prospect(world_1996):
    w = world_1996
    stewart = w.drivers[w.real_drivers["Tony_Stewart"]]
    assert stewart.age(1996) == 25 and stewart.max_tier < 7
    assert stewart.potential > stewart.ability


def test_series_named_for_the_era(world_1996):
    w = world_1996
    if w.series("cup_series").template.eras:
        assert "Winston" in w.series("cup_series").name


def test_track_matcher_handles_period_names(tracks):
    assert match_track(tracks, "Sears Point Raceway", "Sonoma", "CA", "", 1996) == "sonoma-raceway-ca"
    assert match_track(tracks, "Lowe's Motor Speedway", "Concord", "NC", "Coca-Cola 600", 2000) == "charlotte-motor-speedway-nc"


def test_world_runs_forward_from_1996(world_1996):
    w = world_1996
    for _ in range(2):
        w.run_year()
    assert w.year == 1998
