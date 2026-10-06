"""Owner mode: start a team, run it, cover its losses, drive for it, sell it."""

import pytest

from racingsim.game import owner as O


@pytest.fixture(scope="module")
def game(tracks):
    from racingsim.game.session import Game
    g = Game.new("Owen", "Owner", "NC", 24, "stock_car", "wealthy", seed=31, scale=0.12, start_year=2016)
    g.sim_until("season")
    return g


def test_start_drive_and_sell_a_team(game):
    w, p = game.world, game.world.player
    opts = O.options(w, p)
    assert opts and all(O.OWNER_TIERS[0] <= o["tier"] <= O.OWNER_TIERS[1] for o in opts)
    cheapest = opts[0]
    p.savings = cheapest["cost"] * 3
    acts = {a["id"] for a in game.menu()["actions"]}
    assert "found_team" in acts
    msg = game.act("found_team", cheapest["value"])
    assert "open for business" in msg
    t = O.owned(w)
    assert t is not None and t.player_owned and t.series_id == cheapest["value"]
    assert p.savings == pytest.approx(cheapest["cost"] * 2)
    assert {s.role for s in __import__("racingsim.world.staff", fromlist=["x"]).team_staff(w, t.id)}
    assert "already done" in game.act("found_team", cheapest["value"])
    assert "team_budget" in {a["id"] for a in game.menu()["actions"]}
    game.act("team_budget", "push")
    assert t.budget_mode == "push"
    choice = next((c for c in game.menu()["choices"] if c["kind"] == "own_team"), None)
    if choice is not None:
        game.choose("own_team")
        assert p.team_id == t.id and p.salary == 0
    else:
        game.choose("continue" if any(c["id"] == "continue" for c in game.menu()["choices"]) else "sit_out")
    assert any(x is not None for x in t.roster)          # the seat is filled, by the owner or the market
    savings = p.savings
    game.sim_until("season")
    b = t.books[-1]
    assert b["year"] == w.year and b["revenue"]["owner"] == 0     # the player's money, not a subsidy
    tpl = w.series(t.series_id).template
    assert t.cash >= -0.25 * tpl.season_cost * t.cars           # losses were covered from savings
    assert b.get("owner_draw", 0) == 0 or p.savings < savings + 1
    msg = game.act("sell_team")
    assert msg.startswith("Sold") and O.owned(w) is None and not t.player_owned


def test_a_team_that_runs_dry_is_sold(game):
    w = game.world
    from racingsim.world.entities import Team
    t = next(iter(w.teams.values()))
    tpl = w.series(t.series_id).template
    t.player_owned, t.cash = True, -10 * tpl.season_cost
    w.owned_team_id = t.id
    w.player.savings = 0
    assert O.settle(w, t, tpl) == "sold"
    assert not t.player_owned and w.owned_team_id is None and t.cash > 0
