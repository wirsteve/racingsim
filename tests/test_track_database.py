"""The real-world track database: coverage, integrity and layer separation (R4, R5)."""

import sqlite3
from collections import Counter

from racingsim.tracks.model import SIM_RATING_FIELDS, TrackFacts


def test_loads_and_validates(tracks):
    assert len(tracks) >= 250
    for t in tracks:
        assert not t.facts.validate(), t.name
        assert t.facts.sources, f"{t.name} has no source"


def test_ids_are_stable_slugs(tracks):
    ids = [t.id for t in tracks]
    assert len(ids) == len(set(ids))
    assert all(i == i.lower() and " " not in i for i in ids)


def test_grassroots_venues_dominate(tracks):
    levels = Counter(t.facts.level for t in tracks)
    assert levels["local"] + levels["regional"] > levels["national"] + levels["international"]
    dirt = sum(1 for t in tracks if t.facts.is_dirt)
    assert dirt >= 60
    short = sum(1 for t in tracks if t.facts.is_oval and not t.facts.is_dirt
                and (t.facts.length_mi or 1) < 0.75)
    assert short >= 60
    club = sum(1 for t in tracks if t.facts.track_type == "road_course" and t.facts.level != "national")
    assert club >= 20


def test_every_key_region_has_a_local_scene(tracks):
    for region in ("WI", "NC", "IN", "CA", "FL", "PA", "IA", "VA", "NY", "OH"):
        local = [t for t in tracks if t.facts.region == region and t.facts.level in ("local", "regional")]
        assert len(local) >= 3, region


def test_famous_venues_present_with_sensible_game_ratings(tracks):
    by_name = {t.name: t for t in tracks}
    daytona = by_name["Daytona International Speedway"]
    martinsville = by_name["Martinsville Speedway"]
    assert daytona.sim.drafting_effect > 80
    assert martinsville.sim.brake_stress > daytona.sim.brake_stress
    assert martinsville.sim.passing_difficulty > daytona.sim.passing_difficulty
    for name in ("Indianapolis Motor Speedway", "Road America", "Bristol Motor Speedway",
                 "Eldora Speedway", "Knoxville Raceway", "Watkins Glen International"):
        assert name in by_name, name
    assert by_name["Eldora Speedway"].facts.is_dirt


def test_factual_and_game_layers_are_separate(tracks):
    fact_fields = set(TrackFacts.__dataclass_fields__)
    assert not fact_fields & set(SIM_RATING_FIELDS)
    t = next(iter(tracks))
    d = t.to_dict()
    assert set(d) == {"facts", "profile", "sim"}


def test_sqlite_persistence(tracks, tmp_path):
    path = tmp_path / "tracks.sqlite"
    tracks.save_sqlite(path)
    conn = sqlite3.connect(path)
    try:
        n_facts = conn.execute("select count(*) from track_facts").fetchone()[0]
        n_sim = conn.execute("select count(*) from track_sim_ratings").fetchone()[0]
        n_prof = conn.execute("select count(*) from track_profile").fetchone()[0]
        cols = [r[1] for r in conn.execute("pragma table_info(track_facts)")]
    finally:
        conn.close()
    assert n_facts == n_sim == n_prof == len(tracks)
    assert "drafting_effect" not in cols  # game ratings never leak into the factual table


def test_nearest_tracks_are_local(tracks):
    # Slinger, Wisconsin: the nearest venues should be Wisconsin short tracks.
    near = tracks.nearest(43.33, -88.29, limit=3)
    assert all(t.facts.region == "WI" for _, t in near)
