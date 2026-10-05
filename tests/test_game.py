"""Career mode + UI API: the player drives the decisions, the world does the rest."""

import json

import pytest

from racingsim.game.session import Game
from racingsim.ui import server
from racingsim.world.entities import RETIRED


@pytest.fixture()
def game(tmp_path, monkeypatch):
    monkeypatch.setattr("racingsim.game.session.SAVE_DIR", tmp_path)
    return Game.new("Test", "Driver", "NC", 14, "stock_car", "comfortable", "gifted", seed=3, scale=0.25)


def test_new_career_places_player_locally(game):
    p = game.world.player
    assert p.is_player and p.series_id
    s = game.world.series(p.series_id)
    assert s.tier <= 1 and not s.template.team_based
    assert game.phase == "season" and game.runner.week == 0


def test_sim_to_next_race_stops_after_player_races(game):
    p = game.world.player
    target = game.runner.next_week_for(p)
    game.sim_until("race")
    assert game.runner.week == target
    assert any(n["kind"] == "player" for n in game.world.news)


def test_season_end_opens_offseason_with_choices(game):
    game.sim_until("season")
    assert game.phase == "offseason"
    menu = game.menu()
    kinds = {c["kind"] for c in menu["choices"]}
    assert {"self", "sit_out", "retire"} <= kinds
    assert {a["id"] for a in menu["actions"]} == {"pitch", "coach", "relocate"}


def test_ai_never_moves_the_player(game):
    p = game.world.player
    game.sim_until("season")
    current = next(c for c in game.menu()["choices"] if c["kind"] == "self" and c["current"])
    game.choose(current["id"])
    assert p.series_id == current["series_id"]  # exactly where the player chose, not the AI
    assert game.phase == "season" and game.world.year == 2027


def test_actions_are_once_per_offseason(game):
    game.sim_until("season")
    first = game.act("pitch")
    assert first
    assert "already" in game.act("pitch")
    game.act("relocate", "IN")
    assert game.world.player.home_region == "IN"


def test_multi_season_playthrough_all_choice_types(game):
    p = game.world.player
    for year in range(4):
        game.sim_until("season")
        menu = game.menu()
        teams = [c for c in menu["choices"] if c["kind"] == "team"]
        selfs = [c for c in menu["choices"] if c["kind"] == "self"]
        if year == 2:
            game.choose("sit_out")
            assert p.series_id is None
            continue
        pick = teams[0] if teams else max(selfs, key=lambda c: (c["tier"], c["afford"]))
        game.choose(pick["id"])
        assert p.series_id == pick["series_id"]
        if pick["kind"] == "team":
            assert p.team_id == pick["team_id"]
    game.sim_until("season")
    game.choose("retire")
    assert p.status == RETIRED
    game.sim_until("season")  # the world keeps turning after retirement
    assert game.phase == "season"


def test_save_and_load_round_trip(game):
    game.sim_until("race")
    game.save("t1")
    names = [s["name"] for s in Game.saves()]
    assert "t1" in names
    g2 = Game.load("t1")
    assert g2.world.year == game.world.year and g2.runner.week == game.runner.week
    assert g2.world.player.name == game.world.player.name
    g2.sim_until("season")  # a loaded game keeps running


def test_api_routes_smoke(game):
    server.STATE.game = game
    h = server.handle
    game.sim_until("race")
    p = game.world.player
    for path in ["/api/status", "/api/dashboard", "/api/pyramid", "/api/drivers", "/api/tracks",
                 "/api/news", "/api/jewels", "/api/regions", f"/api/driver/{p.id}",
                 f"/api/series/{p.series_id}", "/api/series/cup_series", "/api/track/martinsville-speedway-va",
                 "/api/instances/local_street_stock"]:
        out = h("GET", path, {}, {})
        json.dumps(out, default=server._default)
    team_id = next(iter(game.world.teams))
    h("GET", f"/api/team/{team_id}", {}, {})
    drivers = h("GET", "/api/drivers", {"tier": "7", "sort": "overall", "limit": "5"}, {})
    assert drivers["rows"] and all(r["tier"] == 7 for r in drivers["rows"])
    h("POST", "/api/sim", {}, {"until": "season"})
    off = h("GET", "/api/offseason", {}, {})
    assert not any(k.startswith("_") for c in off["choices"] for k in c)
    choice = next(c for c in off["choices"] if c["kind"] == "self")
    res = h("POST", "/api/offseason", {}, {"choice": choice["id"]})
    assert res["status"]["phase"] == "season"


def test_scouting_hides_true_ratings_of_others(game):
    from racingsim.ui.api import scouted
    w = game.world
    me = scouted(w, w.player)
    assert me["exact"] is True
    other = next(d for d in w.drivers.values() if not d.is_player)
    rep = scouted(w, other)
    assert rep["exact"] is False and rep["overall"] % 5 == 0
