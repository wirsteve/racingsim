"""Real-world rules: car classes, points systems, playoffs, purses and the player's garage."""

import random
import statistics

import pytest

from racingsim.history.economy import price_index
from racingsim.knowledge.validate import rules_issues
from racingsim.rules import car as C
from racingsim.rules.classes import all_classes, class_for_template
from racingsim.rules.payouts import Purse
from racingsim.rules.points import assignment, score_race, system_for
from racingsim.world.series import load_templates


def test_rules_data_is_consistent():
    assert rules_issues() == []
    assert len(all_classes()) >= 15


def test_every_self_run_short_track_template_has_a_class():
    for t in load_templates()[0]:
        if not t.team_based and t.discipline in ("stock_car", "dirt_oval") and t.tier <= 4:
            assert class_for_template(t.key) is not None, t.key


def test_points_tables_by_era_and_sanctioning_body():
    assert system_for("cup_series", 1996).finish_points(1, 43) == 175
    assert system_for("cup_series", 2005).finish_points(1, 43) == 180
    assert system_for("cup_series", 2018).finish_points(2, 40) == 35
    assert assignment("cup_series", 2018)[1] == "playoffs_2017"
    assert assignment("local_dirt_modified", 2020, "track", "IA")[0] == "imca_weekly"
    assert assignment("local_dirt_modified", 2020, "track", "IL")[0] == "dirtcar_weekly"
    assert assignment("local_dirt_modified", 2020, "track", "MN")[0] == "wissota_weekly"
    hickory = system_for("local_late_model", 2020, "track", "NC")
    assert hickory.finish_points(1, 24) == 48 and hickory.finish_points(24, 24) == 2


def test_latford_bonuses_reward_the_winner():
    sysm = system_for("cup_series", 1996)
    order = [(i, 100 - i) for i in range(43)]
    pts = score_race(sysm, order, random.Random(1))
    assert pts[0] >= 180 and max(pts.values()) == pts[0]


def test_weekly_purses_barely_move_in_nominal_terms():
    tpl = {t.key: t for t in load_templates()[0]}["local_late_model"]
    nominal_1996 = Purse(tpl, 1996).pay(1, 20) * price_index(1996)
    nominal_2021 = Purse(tpl, 2021).pay(1, 20) * price_index(2021)
    assert nominal_1996 < nominal_2021 < nominal_1996 * 2   # weekly purses lag far behind costs


def test_money_buys_speed_more_in_open_classes():
    rng = random.Random(4)
    classes = all_classes()

    def gap(key):
        c = classes[key]
        rate = lambda r: statistics.mean(C.rating(car, c, None, 50, tire_wear=C.steady_wear(c, car.new_tires, None))
                                         for car in (C.ai_car(c, 2024, r, rng, None) for _ in range(150)))
        return rate(2.2) - rate(0.5)
    assert gap("dirt_late_model") > gap("legends") > 0
    assert gap("super_late_model") > gap("bandolero")


def test_worn_engine_and_tires_cost_speed_and_reliability():
    c = all_classes()["dirt_modified"]
    car = C.typical_build(c)
    fresh, risk = C.rating(car, c, None, 50), C.mech_risk(c, car, 50)
    opt = c.engine(car.engine)
    car.engine_runs = opt.rebuild_races * 2
    car.tire_wear = 0.9
    assert C.rating(car, c, None, 50) < fresh - 3
    assert C.mech_risk(c, car, 50) > risk * 2


def test_player_runs_a_season_on_a_real_budget(tracks):
    from racingsim.game.session import Game
    from racingsim.rules.garage import garage_action
    from racingsim.ui.garage_view import garage
    g = Game.new("Gar", "Age", "IA", 16, "dirt_oval", "comfortable", seed=9, scale=0.15, start_year=2016)
    p = g.world.player
    v = garage(g)
    assert v["available"] and "car" in v
    assert garage_action(g.world, p, "tires", value=99).startswith("You'll buy")
    assert p.car.new_tires <= C.max_new(all_classes()[p.car.cls])
    g.sim_until("season")
    assert p.car.account is None                     # season closed, money banked
    texts = [row[1] for row in p.car.ledger]
    assert any("entry, pit passes" in t for t in texts)
    assert p.savings >= 0
    rec = p.history[-1]
    assert rec.points is not None and rec.points > 0


def test_playoff_champion_comes_from_the_final_four(tracks):
    from racingsim.sim.season import SeasonRunner
    from racingsim.world.world import World, WorldConfig, YearSummary
    w = World.generate(WorldConfig(seed=3, population_scale=0.12, start_year=2019), tracks=tracks)
    r = SeasonRunner(w, YearSummary(year=w.year))
    w.season = r
    r.run_to_end()
    st = r.playoffs["cup_series"]
    assert len(st["alive"]) == 4 and len(st["field"]) == 16
    assert r.res.champions["cup_series"] == st["final_order"][0]


def test_garage_api_rejects_bad_input(tracks):
    from racingsim.game.session import Game
    from racingsim.ui import server
    server.STATE.game = Game.new("Api", "Test", "NC", 14, "stock_car", "middle", seed=2, scale=0.12)
    try:
        with pytest.raises(server.ApiError):
            server.handle("POST", "/api/garage", {}, {"action": "tires", "value": "four"})
        with pytest.raises(server.ApiError):
            server.handle("POST", "/api/garage", {}, {"key": "x"})
        out = server.handle("POST", "/api/garage", {}, {"action": "nonsense"})
        assert "Unknown" in out["message"] or not out["available"]
        assert server.handle("GET", "/api/knowledge/rules", {}, {})["points"]
    finally:
        server.STATE.game = None
