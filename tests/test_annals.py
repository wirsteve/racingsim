"""Long memory: splits, PAR, awards, milestones, records, the almanac and the Hall of Fame."""

import copy

import pytest

from racingsim.sim.season import _Acc, positions_above_replacement
from racingsim.world import annals as A
from racingsim.world.entities import RETIRED, SeasonRecord


@pytest.fixture(scope="module")
def world(tracks):
    from racingsim.world.world import World, WorldConfig
    w = World.generate(WorldConfig(seed=8, population_scale=0.12, start_year=2016), tracks=tracks)
    w.run_year()
    return w


def test_par_is_finishing_above_what_the_car_should_do():
    # Ten drivers: the same equipment, finishing percentiles spread out; one great driver in a bad car.
    rows, fit = [], [0, 0.0, 0.0, 0.0, 0.0]
    for i in range(10):
        a = _Acc(series_id="x", starts=20, fin_pct_sum=20 * i / 9, eq_sum=20 * (40 + 3 * i))
        rows.append((i, a))
    rows.append((99, _Acc(series_id="x", starts=20, fin_pct_sum=20 * 0.9, eq_sum=20 * 35)))
    for _, a in rows:
        pct, eq = a.fin_pct_sum / a.starts, a.eq_sum / a.starts
        for _ in range(a.starts):
            fit[0] += 1
            fit[1] += eq
            fit[2] += pct
            fit[3] += eq * pct
            fit[4] += eq * eq
    par = positions_above_replacement(fit, rows)
    assert par[99] == max(par.values())                  # beat the car by the most
    assert min(par.values()) < 0 < par[99]
    assert positions_above_replacement(None, rows) == {}


def test_season_files_par_splits_awards_and_track_winners(world):
    year = world.year - 1
    recs = [r for d in world.drivers.values() for r in d.history if r.year == year]
    assert any(r.par is not None for r in recs)
    assert any(r.splits for r in recs if r.tier >= 3)
    alm = world.annals["almanac"][year]
    assert alm["champions"] and alm["awards"]
    kinds = {a[0] for a in alm["awards"]}
    assert {"Most Valuable Driver", "Driver of the Year"} <= kinds
    for _, _, did, *_ in alm["awards"]:
        assert any(str(year) in x for x in world.drivers[did].awards)
    assert world.annals["track_winners"]
    cup = [r for r in recs if r.series_id == "cup_series" and r.par is not None]
    assert 3 <= max(r.par for r in cup) <= 25                # a WAR-like scale


def test_records_book_and_views(world):
    from racingsim.ui import annals_view
    book = annals_view.records(world, "cup_series")
    assert book["current"] == "cup_series"
    assert book["career"]["wins"]["rows"] and book["season"]["wins"]["rows"]
    top = book["career"]["wins"]["rows"]
    assert [x["value"] for x in top] == sorted((x["value"] for x in top), reverse=True)
    alm = annals_view.almanac(world, None)
    assert alm["year"] == world.year - 1 and alm["champions"]
    assert "inductees" in annals_view.hall_of_fame(world)
    d = next(d for d in world.drivers.values() if any(r.tier >= 3 for r in d.history))
    assert A.career_splits(d)


def test_hall_of_fame_ballot(world):
    w = copy.deepcopy(world)
    year = w.year
    legend, journeyman = [d for d in w.drivers.values() if d.status != RETIRED][:2]
    for d, wins, titles in ((legend, 6, 1), (journeyman, 0, 0)):
        d.status = RETIRED
        d.max_tier = 7
        d.history = [SeasonRecord(year=year - 20 + i, series_id="cup_series", tier=7, discipline="stock_car",
                                  team_id=None, starts=36, wins=wins, top5=12 if wins else 2, avg_finish=10.0,
                                  expected_finish=12.0, championship_pos=1 if i < titles * 3 else 10, field_size=40,
                                  champion=i < titles * 3, par=6.0 if wins else -1.0) for i in range(15)]
    A.hall_of_fame(w)
    ids = [h["id"] for h in w.annals["hof"]]
    assert legend.id in ids and journeyman.id not in ids
    assert any("Hall of Fame" in a for a in legend.awards)
    A.hall_of_fame(w)                                        # nobody is inducted twice
    assert [h["id"] for h in w.annals["hof"]].count(legend.id) == 1


def test_old_saves_load(world):
    rec = SeasonRecord.__new__(SeasonRecord)
    rec.__setstate__({"year": 2000, "series_id": "x"})
    assert rec.splits == {} and rec.par is None
    state = world.__getstate__()
    state.pop("annals")
    w = world.__class__.__new__(world.__class__)
    w.__setstate__(state)
    assert w.annals == {} and A.store(w)["almanac"] == {}


def test_review_fixes_fairness(world):
    from racingsim.world.entities import Driver
    # PAR is skipped when this season's fit doesn't cover every start (a pre-PAR mid-season save).
    rows = [(i, _Acc(series_id="x", starts=10, fin_pct_sum=5.0, eq_sum=500.0)) for i in range(6)]
    assert positions_above_replacement([20, 1000.0, 10.0, 500.0, 50000.0], rows) == {}
    # A generated veteran has no known past: not a rookie, no "first win" news.
    vet = next(d for d in world.drivers.values() if d.history)
    probe = copy.copy(vet)
    probe.history, probe.years_at_tier, probe.is_player = [], 5, False
    assert A.past_unknown(probe, world.year)
    probe.years_at_tier = 0
    assert not A.past_unknown(probe, world.year)
    # Hall of Fame: 40 wins in an 80-race season count for about what 18 do in a 36-race one.
    def season(starts, wins, field):
        return SeasonRecord(year=2000, series_id="x", tier=7, discipline="stock_car", team_id=None, starts=starts,
                            wins=wins, top5=0, avg_finish=5.0, expected_finish=5.0, championship_pos=2,
                            field_size=field, champion=False)
    a, b = copy.copy(vet), copy.copy(vet)
    a.history, b.history, a.crown_jewels, b.crown_jewels = [season(80, 40, 30)], [season(36, 18, 30)], [], []
    assert A.career_value(a)[0] == pytest.approx(A.career_value(b)[0], rel=0.05)
    # Track winners are capped per track.
    w = copy.deepcopy(world)
    for i in range(A.TRACK_WINNERS_KEPT + 50):
        A.note_race(w, "t", "e", 1)
    assert len(w.annals["track_winners"]["t"]) == A.TRACK_WINNERS_KEPT


def test_almanac_milestones_put_the_top_level_first(world):
    alm = world.annals["almanac"][world.year - 1]
    tiers = [m[2] for m in alm["milestones"] if len(m) > 2]
    assert tiers == sorted(tiers, reverse=True)
