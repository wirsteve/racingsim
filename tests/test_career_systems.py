"""Systemic career behaviour (R2, R3, R6): stories must emerge, not be scripted."""

from collections import Counter

from racingsim.constants import TIER_STRENGTH
from racingsim.career.market import seat_gap, seat_role
from racingsim.career.scouting import categorize
from racingsim.reports import archetype_counts, cohort_outcomes, funnel
from racingsim.world.entities import RETIRED
from racingsim.world.world import World, WorldConfig


# --------------------------------------------------------------------------- pyramid (R3)
def test_pyramid_is_wide_at_the_bottom(simulated_world):
    counts = {row["tier"]: row["drivers"] for row in funnel(simulated_world)}
    grassroots = counts.get(0, 0) + counts.get(1, 0) + counts.get(2, 0)
    pro = counts.get(5, 0) + counts.get(6, 0) + counts.get(7, 0)
    assert grassroots > 8 * pro
    assert counts[1] > counts[3] > counts[7]
    assert counts[2] > counts[4]


def test_reaching_the_top_is_rare(simulated_world):
    co = cohort_outcomes(simulated_world)
    assert co["share_reaching_tier"][7] < 0.03
    assert co["share_reaching_tier"][5] < 0.08
    # Of drivers who *started* in this simulation, almost nobody is already at the top.
    started_here = [d for d in simulated_world.drivers.values()
                    if d.first_season > simulated_world.config.start_year]
    assert started_here
    assert sum(d.max_tier >= 6 for d in started_here) / len(started_here) < 0.01


def test_tiers_have_realistic_age_bands(simulated_world):
    rows = {r["tier"]: r for r in funnel(simulated_world)}
    assert rows[0]["age_median"] <= 14
    assert 17 <= rows[5]["age_median"] <= 34
    assert 22 <= rows[7]["age_median"] <= 40


def test_population_is_stable(simulated_world):
    summaries = simulated_world.summaries
    first = sum(summaries[0].drivers_by_tier.values())
    last = sum(summaries[-1].drivers_by_tier.values())
    assert 0.7 < last / first < 1.3


# --------------------------------------------------------------------------- money (R2.3/R2.4)
def test_pay_drivers_exist_at_national_level(simulated_world):
    w = simulated_world
    pay = [d for d in w.drivers.values() if d.status != RETIRED and d.tier >= 4
           and d.team_id is not None and not d.seat_funded]
    assert len(pay) >= 10
    weaker = [d for d in pay if d.ability < TIER_STRENGTH[d.tier]]
    assert weaker, "some funded drivers should be below the level of their series"


def test_talent_can_be_stranded(simulated_world):
    counts = archetype_counts(simulated_world)
    assert counts["stalled_talent"] >= 1
    assert counts["ran_out_of_money"] >= 1


def test_winning_does_not_guarantee_promotion(simulated_world):
    """Feeder champions often do not move up the next year (Moffitt pattern)."""
    w = simulated_world
    champs, promoted = 0, 0
    for d in w.drivers.values():
        for i, r in enumerate(d.history[:-1]):
            if r.champion and 3 <= r.tier <= 5:
                champs += 1
                if d.history[i + 1].tier > r.tier:
                    promoted += 1
    assert champs >= 10
    assert 0 < promoted < champs


# --------------------------------------------------------------------------- pathways (R2.5-R2.8)
def test_many_archetypes_emerge(simulated_world):
    counts = archetype_counts(simulated_world)
    present = [k for k, v in counts.items() if v > 0]
    for required in ("pay_driver", "discipline_switcher", "development_signee",
                     "veteran_returned_to_grassroots", "shootout_or_combine_winner"):
        assert counts[required] > 0, required
    assert len(present) >= 8


def test_development_programs_sign_teenagers(simulated_world):
    ages = []
    for d in simulated_world.drivers.values():
        for e in d.events:
            if "development program at" in e:
                ages.append(int(e.rsplit(" ", 1)[1]))
    assert ages
    assert min(ages) <= 17
    assert sum(ages) / len(ages) < 21


def test_multiple_routes_to_national_level(simulated_world):
    """Drivers reaching tier 5+ came through more than one discipline/route."""
    w = simulated_world
    routes = Counter()
    for d in w.drivers.values():
        if d.max_tier >= 5 and d.first_season > w.config.start_year - 6:
            lower = [r for r in d.history if r.tier <= 3]
            if lower:
                routes[lower[0].discipline] += 1
    assert len(routes) >= 2


# --------------------------------------------------------------------------- geography (R6)
def test_geography_shapes_entry_disciplines(tracks):
    w = World.generate(WorldConfig(seed=3, population_scale=0.4), tracks=tracks)
    by_region = {}
    for d in w.drivers.values():
        if d.tier <= 2 and d.series_id:
            by_region.setdefault(d.home_region, Counter())[w.series(d.series_id).discipline] += 1
    iowa, nc = by_region["IA"], by_region["NC"]
    assert iowa["dirt_oval"] > iowa["stock_car"]
    assert nc["stock_car"] > 0
    assert nc["stock_car"] / sum(nc.values()) > iowa["stock_car"] / max(1, sum(iowa.values()))


def test_local_racers_race_near_home(fresh_world):
    from racingsim.util import haversine_mi
    w = fresh_world
    dists = []
    for d in w.drivers.values():
        if d.series_id and w.series(d.series_id).scope == "track":
            s = w.series(d.series_id)
            dists.append(haversine_mi(d.lat, d.lon, s.anchor_lat, s.anchor_lon))
    dists.sort()
    assert dists[len(dists) // 2] < 120


# --------------------------------------------------------------------------- rules
def test_age_rules_enforced(simulated_world):
    w = simulated_world
    for d in w.drivers.values():
        if d.status == RETIRED or not d.series_id:
            continue
        tpl = w.series(d.series_id).template
        assert d.age(w.year) >= tpl.min_age - 1, (d.name, tpl.key)


def test_age_by_track_approval():
    from racingsim.tracks.model import TrackFacts
    from racingsim.tracks.ratings import build_track
    from racingsim.world.series import load_templates
    templates = {t.key: t for t in load_templates()[0]}
    truck = templates["truck_series"]
    big = build_track(TrackFacts.from_dict(dict(name="Big", city="x", region="FL", country="USA",
                      track_type="oval", surface="asphalt", length_mi=2.5, banking_deg_turns=31,
                      level="national", lat=29, lon=-81)), overrides={})
    short = build_track(TrackFacts.from_dict(dict(name="Small", city="x", region="TN", country="USA",
                        track_type="oval", surface="concrete", length_mi=0.533, banking_deg_turns=28,
                        level="national", lat=36, lon=-82)), overrides={})
    assert truck.age_allows_track(16, short)
    assert not truck.age_allows_track(16, big)
    assert truck.age_allows_track(18, big)


def test_pro_am_seats_go_to_amateurs(simulated_world):
    w = simulated_world
    for team in w.teams.values():
        tpl = w.series(team.series_id).template
        if not tpl.pro_am:
            continue
        for slot, did in enumerate(team.roster):
            if did is None or seat_role(tpl, slot) != "am":
                continue
            d = w.drivers[did]
            assert categorize(d, w.year) in ("bronze", "silver"), (d.name, categorize(d, w.year))
            assert seat_gap(team, tpl, "am") > 0


def test_categorization_rules():
    from racingsim.world.entities import Driver
    d = Driver(id=1, first_name="A", last_name="B", birth_year=1980, home_region="NC", country="USA",
               lat=0, lon=0, ability=50, potential=50, peak_age=29, consistency=50, racecraft=50,
               aggression=50, feedback=50, adaptability=50, marketability=50, professionalism=50,
               determination=50, first_license_age=38, max_tier=3)
    assert categorize(d, 2026) == "bronze"
    d.first_license_age = 12
    assert categorize(d, 2026) == "silver"
    d.max_tier = 7
    assert categorize(d, 2026) == "platinum"
    assert categorize(d, 2046) == "silver"  # age downgrades at 55 and 60


def test_determinism(tracks):
    a = World.generate(WorldConfig(seed=5, population_scale=0.2), tracks=tracks)
    b = World.generate(WorldConfig(seed=5, population_scale=0.2), tracks=tracks)
    a.run_year()
    b.run_year()
    assert [(d.id, round(d.ability, 6), d.series_id) for d in a.drivers.values()] == \
           [(d.id, round(d.ability, 6), d.series_id) for d in b.drivers.values()]
