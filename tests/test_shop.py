"""The race shop: hauler, facilities, the fleet, builds, spare engines, the used market, team facilities."""

import copy
import pickle

import pytest

from racingsim.rules import car as C
from racingsim.rules import garage as G
from racingsim.rules import shop as SH


@pytest.fixture(scope="module")
def base(tracks):
    from racingsim.game.session import Game
    g = Game.new("Shop", "Owner", "NC", 22, "stock_car", "wealthy", seed=5, scale=0.12, start_year=2020)
    g.world.player.savings += 500_000
    return g


@pytest.fixture
def game(base):
    return copy.deepcopy(base)


def _cls(g):
    return G.target_class(g.world, g.world.player)


def test_starting_operation_and_upkeep_against_the_typical(game):
    w, d = game.world, game.world.player
    op = SH.get(w)
    assert op.hauler == "open" and op.season == w.year and SH.level(op, "fab") == 0
    tpl = w.series(d.series_id).template
    base = C.overhead_per_night(_cls(game), tpl)
    assert 0.4 * base - 1e-9 <= SH.overhead(w, tpl, base) <= base
    # The operation a typical racer at this level runs costs nothing on top of the class budget.
    w.__dict__["shop"] = SH.typical(tpl.season_cost)
    assert SH.season_upkeep(w, tpl, base) == pytest.approx(0, abs=1)
    w.__dict__["shop"] = SH.Operation(hauler="semi", levels={"space": 3})
    assert SH.season_upkeep(w, tpl, base) > 50_000


def test_facility_upgrades_pay_change_the_car_and_sell_back(game):
    w, d = game.world, game.world.player
    cls = _cls(game)
    track = G.home_track(w, w.series(d.series_id))
    before_rating = G.player_rating(w, d, cls, track)
    money = d.savings + d.car.account
    for fac in ("setup", "setup", "setup", "fab", "engine"):
        assert "New in the shop" in SH.shop_action(w, d, "upgrade", fac)
    assert "as good as it gets" in SH.shop_action(w, d, "upgrade", "setup")
    assert d.savings + d.car.account < money
    assert G.player_rating(w, d, cls, track) > before_rating
    assert SH.repair_mult(w) < 1 and SH.freshen_mult(w, cls.engine(d.car.engine)) < 1
    sealed = C.Option("x", "Sealed", 5000, 60, sealed=True, rebuild_usd=900, rebuild_races=10)
    assert SH.freshen_mult(w, sealed) == 1.0 and SH.interval_mult(w, sealed) == 1.0
    money = d.savings + d.car.account
    msg = SH.shop_action(w, d, "downgrade", "setup")
    assert "Sold off" in msg and d.savings + d.car.account > money and SH.level(SH.get(w), "setup") == 2


def test_build_a_car_in_the_shop(game):
    w, d = game.world, game.world.player
    cls = _cls(game)
    key = f"{cls.chassis[0].key}|{cls.engines_in(w.year)[0].key}|{(cls.shocks[0].key if cls.shocks else 'stock')}"
    assert "welder" in SH.shop_action(w, d, "build", key)
    SH.shop_action(w, d, "upgrade", "fab")
    SH.shop_action(w, d, "upgrade", "fab")
    msg = SH.shop_action(w, d, "build", key)
    assert "goes on the jig" in msg
    op = SH.get(w)
    assert len(op.projects) == 1
    p = op.projects[0]
    assert p["car"].chassis_q == cls.chassis[0].quality + SH.fac(op, "fab")["build"]
    assert SH.tick(w, d) == []                       # not ready yet
    w.season.week = p["ready_week"]
    assert SH.tick(w, d) and not op.projects and op.backups[-1] is p["car"]
    # Builds fill the shop up to what its space holds.
    cars, _ = SH.capacity(w)
    while SH.cars_kept(w, d) < cars:
        assert "goes on the jig" in SH.shop_action(w, d, "build", key)
    assert "No room" in SH.shop_action(w, d, "build", key)


def test_used_market_backups_and_engines(game):
    w, d = game.world, game.world.player
    cls = _cls(game)
    items = SH.market(w, d, cls)
    assert len(items) == SH.data()["market"]["listings"] and SH.market(w, d, cls) is items   # stable in a period
    item = items[0]
    blind = SH.shown(w, item)["spread"]
    SH.shop_action(w, d, "upgrade", "fab")
    SH.shop_action(w, d, "upgrade", "fab")
    assert SH.shown(w, item)["spread"] < blind        # a chassis jig measures the car
    assert "Bought" in SH.shop_action(w, d, "buy_used", str(item["id"]))
    op = SH.get(w)
    assert op.backups and op.backups[0] is item["car"] and item not in op.market["items"]
    assert "sold" in SH.shop_action(w, d, "buy_used", str(item["id"]))
    primary = d.car
    acct = primary.account
    assert "primary" in SH.shop_action(w, d, "primary", "0")
    assert d.car is item["car"] and d.car.account == acct and primary.account is None and op.backups[0] is primary
    # Spare engines: buy, swap in, freshen, sell.
    en = cls.engines_in(w.year)[0]
    assert "engine stand" in SH.shop_action(w, d, "buy_engine", en.key)
    old_engine = (d.car.engine, d.car.engine_runs)
    assert "is in the car" in SH.shop_action(w, d, "swap_engine", "0")
    assert d.car.engine_runs == 0 and (op.engines[0]["key"], op.engines[0]["runs"]) == old_engine
    SH.shop_action(w, d, "freshen_engine", "0")
    assert op.engines[0]["runs"] == 0 and op.engines[0]["health"] == 100
    assert "Sold the spare" in SH.shop_action(w, d, "sell_engine", "0") and not op.engines
    money = d.savings + d.car.account
    assert "Sold" in SH.shop_action(w, d, "sell_car", "0") and not op.backups
    assert d.savings + d.car.account > money


def test_backup_car_rolls_out(game):
    w, d = game.world, game.world.player
    cls = _cls(game)
    item = SH.market(w, d, cls)[0]
    best = max(cls.chassis, key=lambda o: o.quality)
    item["car"].condition, item["car"].engine_health = 100, 100     # a better car than the primary
    item["car"].chassis, item["car"].chassis_q, item["car"].chassis_age = best.key, best.quality + 5, 0
    SH.shop_action(w, d, "buy_used", str(item["id"]))
    primary = d.car
    primary.engine_health = 0
    assert SH.ready_car(w, d, cls) and d.car is item["car"]
    # Practice wreck: with a stacker the backup comes off the hauler.
    SH.shop_action(w, d, "hauler", "stacker")
    primary.engine_health, primary.condition, primary.chassis_q = 100, 100, 10.0   # an old, tired primary
    SH.make_primary(w, d, 0)
    assert d.car is primary
    track = G.home_track(w, w.series(d.series_id))
    note = SH.practice(w, d, cls, track, 1, scale=1e6)
    assert "backup" in note and d.car is item["car"] and primary.condition < 100
    # A backup that's worse than the bent primary stays in the hauler.
    SH.make_primary(w, d, SH.get(w).backups.index(primary))
    primary.chassis_q, primary.condition = 99.0, 100
    assert "patched" in SH.practice(w, d, cls, track, 1, scale=1e6) and d.car is primary


def test_shop_survives_a_season_and_save(game, tmp_path, monkeypatch):
    w, d = game.world, game.world.player
    SH.shop_action(w, d, "hauler", "race_trailer")
    SH.shop_action(w, d, "upgrade", "engine")
    SH.shop_action(w, d, "upgrade", "space")
    age = d.car.chassis_age
    game.sim_until("season")
    assert SH.get(w).season == w.year and d.car.ledger
    game.choose("continue")
    assert SH.get(w).season == w.year and SH.get(w).hauler_age == 1
    assert d.car is not None and d.car.cls == _cls(game).key          # same class next season
    assert d.car.chassis_age > age
    assert any("Shop & hauler for the season" in r[1] for r in d.car.ledger)
    blob = pickle.loads(pickle.dumps(game))
    assert SH.get(blob.world).hauler == "race_trailer"


def test_old_saves_load():
    car = C.Car("x", "c", 50, 0, "e", 50, "s", 50)
    state = dict(car.__dict__)
    for k in ("tag", "season_seen", "interval_mult"):
        state.pop(k)
    old = C.Car.__new__(C.Car)
    old.__dict__.update(state)
    assert old.tag == "" and old.season_seen == 0 and old.interval_mult == 1.0


def test_team_facilities(tracks):
    from racingsim.game import owner as O
    from racingsim.game.session import Game
    from racingsim.sim.season import SeasonResults
    from racingsim.world import finance as FI
    g = Game.new("Team", "Boss", "NC", 30, "stock_car", "wealthy", seed=9, scale=0.12, start_year=2020)
    g.sim_until("season")
    w, p = g.world, g.world.player
    opt = O.options(w, p)[0]
    p.savings = opt["cost"] * 20
    g.act("found_team", opt["value"])
    t = O.owned(w)
    assert "don't own" not in SH.shop_action(w, p, "team_upgrade", "rnd")
    assert SH.team_level(t, "rnd") == 1 and SH.team_upkeep(w, t) > 0 and SH.team_value(w, t) > 0
    for _ in range(3):
        SH.shop_action(w, p, "team_upgrade", "pit")
    assert "as good as it gets" in SH.shop_action(w, p, "team_upgrade", "pit")
    eff = {"setup_mean": 0.0, "pit_s": 1.0, "pit_sd": 1.0, "mech": 1.0}
    SH.team_crew(t, eff)
    assert eff["pit_s"] < 1 and eff["pit_sd"] < 1
    FI.close_books(w, SeasonResults())
    assert t.books[-1]["costs"]["facilities"] == pytest.approx(SH.team_upkeep(w, t), abs=1)
    savings = p.savings
    msg = g.act("sell_team")
    assert msg.startswith("Sold") and p.savings > savings + SH.team_value(w, t) - 1
    old = dict(t.__dict__)
    old.pop("facilities")
    t2 = t.__class__.__new__(t.__class__)
    t2.__setstate__(old)
    assert t2.facilities == {}


def test_no_free_money(game):
    w, d = game.world, game.world.player
    cls = _cls(game)
    SH.shop_action(w, d, "upgrade", "space")
    SH.shop_action(w, d, "upgrade", "space")
    # Buying any listing and selling it straight back loses money.
    for item in list(SH.market(w, d, cls)):
        money = d.savings + d.car.account
        if "Bought" not in SH.shop_action(w, d, "buy_used", str(item["id"])):
            continue
        SH.shop_action(w, d, "sell_car", str(len(SH.get(w).backups) - 1))
        assert d.savings + d.car.account < money
    # Savings put into the shop and sold back in season come home in full when the season closes.
    car = d.car
    car.account, car.drawn, car.winnings = 0.0, 0.0, 0.0
    s0, mark = d.savings, len(car.ledger)
    price = SH.data()["facilities"]["fab"]["levels"][1]["usd"]
    SH.shop_action(w, d, "upgrade", "fab")
    SH.shop_action(w, d, "downgrade", "fab")
    upkeep = -sum(r[2] for r in car.ledger[mark:] if "rest of the season" in r[1])   # the fab's upkeep, prorated
    G.close_account(w, d)
    assert d.savings == pytest.approx(s0 - price + SH.SELL_BACK * price - upkeep, abs=1)


def test_midseason_upkeep_is_paid_once(game):
    w, d = game.world, game.world.player
    w.season.week = 10
    paid = lambda: -sum(r[2] for r in d.car.ledger if "rest of the season" in r[1])  # noqa: E731
    SH.shop_action(w, d, "hauler", "stacker")
    first = paid()
    assert first > 0
    SH.shop_action(w, d, "hauler", "open")
    SH.shop_action(w, d, "hauler", "stacker")
    assert paid() == pytest.approx(first, abs=1)


def test_owner_sees_the_shop(tracks):
    from racingsim.game import owner as O
    from racingsim.game.session import Game
    from racingsim.ui import shop_view
    g = Game.new("Team", "View", "NC", 30, "stock_car", "wealthy", seed=12, scale=0.12, start_year=2020)
    g.sim_until("season")
    w, p = g.world, g.world.player
    opt = O.options(w, p)[0]
    p.savings = opt["cost"] * 20
    g.act("found_team", opt["value"])
    SH.shop_action(w, p, "team_upgrade", "engineering")
    v = shop_view.shop(g)
    assert v["team"] and {f["key"] for f in v["team"]["facilities"]} == set(SH.TEAM_FACILITIES)
    assert next(f for f in v["team"]["facilities"] if f["key"] == "engineering")["level"] == 1
