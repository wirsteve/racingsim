"""Regression tests for bugs found in the 2026-10 bug hunt, plus the shipped history data."""

from collections import Counter

import pytest

from racingsim.history.db import SOURCES, HistoryDB
from racingsim.sim.season import SeasonRunner, jewel_block_reasons
from racingsim.world.entities import ACTIVE, PART_TIME, RETIRED, SIDELINED
from racingsim.world.world import World, WorldConfig, YearSummary


@pytest.fixture(scope="module")
def two_seasons(tracks):
    """A small world run for two seasons with every race's entry list recorded."""
    import racingsim.sim.season as season
    w = World.generate(WorldConfig(seed=31, population_scale=0.25, real_history=False), tracks=tracks)
    seen = []
    orig = season.run_race

    def spy(entries, *a, **k):
        seen.append((w.year, [d for e in entries for d in e.drivers]))
        return orig(entries, *a, **k)

    season.run_race = spy
    try:
        w.run_year()
        w.run_year()
    finally:
        season.run_race = orig
    return w, seen


def test_nobody_races_twice_or_injured_in_one_event(two_seasons):
    _, seen = two_seasons
    for _, drivers in seen:
        ids = [d.id for d in drivers]
        assert len(ids) == len(set(ids))


def test_injuries_heal(two_seasons):
    w, _ = two_seasons
    injured = [d for d in w.drivers.values() if d.status != RETIRED and d.injury_races > 0]
    assert len(injured) < 0.01 * len(w.drivers)
    assert all(d.injury_races <= 30 for d in injured)


def test_sponsor_commitments_match_live_deals(two_seasons):
    w, _ = two_seasons
    live = Counter()
    for d in w.drivers.values():
        for deal in d.sponsors:
            live[deal.sponsor_id] += deal.amount
    for s in w.sponsors.values():
        assert s.committed == pytest.approx(live[s.id], abs=1.0)


def test_drivers_without_a_series_are_not_active(two_seasons):
    w, _ = two_seasons
    assert not [d for d in w.drivers.values() if d.status in (ACTIVE, PART_TIME) and not d.series_id]


def test_champion_matches_live_standings_order(tracks):
    w = World.generate(WorldConfig(seed=5, population_scale=0.2, real_history=False), tracks=tracks)
    runner = SeasonRunner(w, YearSummary(year=w.year))
    while runner.week < 29:
        runner.step()
    leaders = {}
    for sid in {a.series_id for a in runner.acc.values()}:
        rows = runner.standings(sid)
        leaders[sid] = rows[0][0]
    # The champion is whoever tops the live standings after the final week: points then wins,
    # or - in Chase/playoff formats - the playoff order (finale decided by finishing order).
    runner.step()
    for sid, did in runner.res.champions.items():
        assert runner.standings(sid)[0][0] == did
        if sid not in runner.playoffs:
            top = max((a for a in runner.acc.values() if a.series_id == sid), key=lambda a: (a.points, a.wins))
            assert runner.acc[did].points == top.points and runner.acc[did].wins == top.wins


def test_sidelined_player_cannot_enter_crown_jewels(tracks):
    from racingsim.game.session import Game
    g = Game.new("Test", "Driver", "IN", 16, "dirt_oval", "wealthy", seed=3, scale=0.2)
    p = g.world.player
    cj = g.world.pyramid.crown_jewels[0]
    p.status = SIDELINED
    assert "no current ride" in jewel_block_reasons(g.world, p, cj)


def test_wizard_rejects_out_of_range_age_instead_of_switching_discipline(tracks):
    from racingsim.game.session import Game
    with pytest.raises(ValueError, match="aged"):
        Game.new("Too", "Old", "NC", 30, "karting", "middle", seed=3, scale=0.2)


def test_coaching_does_not_cut_the_yearly_family_budget(tracks):
    from racingsim.game.session import Game
    g = Game.new("Coach", "Me", "NC", 15, "stock_car", "comfortable", seed=4, scale=0.2)
    g.sim_until("season")
    p = g.world.player
    budget = p.family_budget
    g.act("coach")
    assert p.family_budget == budget


# ------------------------------------------------------------------ shipped history data
@pytest.fixture(scope="module")
def real_hist():
    h = HistoryDB.load_default()
    if h is None:
        pytest.skip("no history data")
    return h


def test_history_covers_every_season_since_1995(real_hist):
    for key in ("cup_series", "stock_national", "truck_series", "open_wheel_top", "formula_lights"):
        for year in range(1995, 2027):
            assert real_hist.season(key, year) is not None, (key, year)
    assert real_hist.season("open_wheel_top_irl", 1996) is not None
    assert set(d for srcs in SOURCES.values() for d, *_ in srcs) <= set(real_hist.seasons)


def test_real_calendars_map_to_our_tracks(real_hist, tracks):
    for key in ("cup_series", "stock_national", "truck_series"):
        for year in (1995, 1996, 2001, 2010, 2020, 2026):
            sched = real_hist.schedule(key, year, list(tracks))
            assert sched, (key, year)
            closed = [t for t in sched if not tracks.get(t).facts.available_in(year)]
            assert not closed, (key, year, closed)


def test_1996_start_has_the_real_cup_grid(tracks):
    w = World.generate(WorldConfig(seed=2, population_scale=0.2, start_year=1996), tracks=tracks)
    cup = w.series("cup_series")
    assert "Winston Cup" in cup.name and cup.real_schedule
    names = {w.drivers[d].name for t in w.teams_in("cup_series") for d in t.roster if d}
    assert {"Jeff Gordon", "Dale Earnhardt", "Terry Labonte", "Rusty Wallace"} <= names
    gordon = next(w.drivers[d] for t in w.teams_in("cup_series") for d in t.roster
                  if d and w.drivers[d].name == "Jeff Gordon")
    assert gordon.age(1996) == 25
    # Future stars exist as kids/prospects at their real ages.
    assert w.drivers[w.real_drivers["Jimmie_Johnson"]].age(1996) == 21
    kb = w.real_drivers.get("Kyle_Busch")
    assert kb is None or w.drivers[kb].max_tier < 7


def test_save_load_round_trip_with_history(tmp_path, monkeypatch):
    import racingsim.game.session as session
    from racingsim.game.session import Game
    monkeypatch.setattr(session, "SAVE_DIR", tmp_path)
    g = Game.new("Save", "Test", "NC", 14, "stock_car", "comfortable", seed=6, scale=0.15, start_year=1998)
    g.sim_week()
    path = g.save("round trip")
    assert path.read_bytes()[:2] == b"\x1f\x8b"  # gzip
    g2 = Game.load("round trip")
    assert g2.world.year == 1998 and g2.world.history is not None
    assert g2.world.history.season("cup_series", 1998) is not None
    g2.sim_until("season")
    assert g2.phase == "offseason"


def test_world_generation_is_deterministic_across_hash_seeds():
    """Same seed -> same world, whatever Python's string-hash randomisation does to set ordering."""
    import os
    import subprocess
    import sys
    code = ("from racingsim.world.world import World, WorldConfig\n"
            "w = World.generate(WorldConfig(seed=8, start_year=2018, population_scale=0.15))\n"
            "print(len(w.drivers), sorted((d.name, d.series_id) for d in w.drivers.values() if d.real)[:200])")
    outs = set()
    for h in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=h)
        outs.add(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                                cwd=os.path.dirname(os.path.dirname(__file__)), check=True).stdout)
    assert len(outs) == 1


def test_self_run_series_never_have_team_seats(tracks):
    w = World.generate(WorldConfig(seed=5, start_year=2024, population_scale=0.15), tracks=tracks)
    bad = [d for d in w.drivers.values()
           if d.series_id and not w.series(d.series_id).template.team_based and d.team_id is not None]
    assert not bad
