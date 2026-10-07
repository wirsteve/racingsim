"""Fixes from the full UAT pass: money shown in season dollars, what the player can spend, failed actions
reported as failures, new-career validation, the off-season message, the jewel and starter ledger lines."""

import copy

import pytest

from racingsim.history.economy import nominal_usd, price_index
from racingsim.rules import garage as G
from racingsim.rules import shop as SH
from racingsim.rules.fail import Fail
from racingsim.ui import api, server


@pytest.fixture(scope="module")
def base(tracks):
    from racingsim.game.session import Game
    return Game.new("Uat", "Racer", "NC", 20, "stock_car", "comfortable", seed=21, scale=0.12, start_year=1995)


@pytest.fixture
def game(base):
    return copy.deepcopy(base)


def test_messages_are_in_season_dollars(game):
    w, d = game.world, game.world.player
    assert price_index(1995) < 0.6
    assert nominal_usd(1995, 1000) == f"${1000 * price_index(1995):,.0f}"
    d.car.engine_runs, d.car.engine_health = 12, 80
    msg = G.garage_action(w, d, "rebuild")
    cls = G.target_class(w, d)
    cost = SH.freshen_cost(w, cls.engine(d.car.engine), 80)
    assert nominal_usd(1995, cost) in msg and not isinstance(msg, Fail)


def test_failures_are_marked(game):
    w, d = game.world, game.world.player
    d.car.engine_runs, d.car.engine_health = 0, 100
    assert isinstance(G.garage_action(w, d, "rebuild"), Fail)          # nothing to freshen
    d.savings, d.car.account = 0.0, 0.0
    assert isinstance(SH.shop_action(w, d, "upgrade", "engine"), Fail)
    assert isinstance(SH.shop_action(w, d, "nonsense"), Fail)
    server.STATE.game = game
    out = server.handle("POST", "/api/shop", {}, {"action": "upgrade", "key": "engine"})
    assert out["ok"] is False and "more than you have" in out["message"]


def test_status_shows_what_can_be_spent(game):
    d = game.world.player
    d.car.account, d.savings = 1234.0, 100.0
    st = api.status(game)
    assert st["player"]["funding"] == pytest.approx(1334, abs=1)


def test_starter_car_line_doesnt_double_count(game):
    d = game.world.player
    first = d.car.ledger[0]
    assert first[1].startswith("Bought") and first[2] == 0
    budget = next(r for r in d.car.ledger if "season budget" in r[1])
    assert budget[2] == pytest.approx(d.car.ledger[1][2])


def test_new_career_validation():
    for body in ({"region": "NC", "first": " ", "last": "X"}, {"region": "NC", "first": "A", "last": "B", "seed": "abc"},
                 {"region": "NC", "first": "A", "last": "B", "background": "royal"}):
        with pytest.raises(server.ApiError):
            server.handle("POST", "/api/new", {}, body)


def test_offseason_message_is_fresh(game):
    game.last_message = "You'll sit out next season."
    game.sim_until("season")
    assert game.phase == "offseason" and game.last_message == ""
