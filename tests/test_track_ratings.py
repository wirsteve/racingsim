"""Rule-derived track ratings behave like the research says venues behave."""

from racingsim.tracks.model import SIM_RATING_FIELDS, TrackFacts
from racingsim.tracks.ratings import build_track, derive_sim_ratings, series_suitability, size_class


def facts(**kw) -> TrackFacts:
    base = dict(name="Test Track", city="X", region="NC", country="USA", track_type="oval",
                surface="asphalt", length_mi=0.5, banking_deg_turns=12, level="local",
                lat=35.0, lon=-80.0)
    base.update(kw)
    return TrackFacts.from_dict(base)


SUPERSPEEDWAY = facts(name="Big Draft", length_mi=2.66, banking_deg_turns=33, level="national")
FLAT_SHORT = facts(name="Paperclip", length_mi=0.526, banking_deg_turns=12, surface="asphalt_concrete")
BULLRING = facts(name="Bowl", length_mi=0.533, banking_deg_turns=28, surface="concrete")
DIRT = facts(name="Clay Half", surface="dirt", length_mi=0.5, banking_deg_turns=14,
             disciplines=["sprint_car", "dirt_late_model"])
ROAD = facts(name="Club Circuit", track_type="road_course", length_mi=4.0, banking_deg_turns=None)
STREET = facts(name="Downtown", track_type="street_circuit", length_mi=1.8, banking_deg_turns=None)


def test_size_classes():
    assert size_class(SUPERSPEEDWAY) == "superspeedway"
    assert size_class(FLAT_SHORT) == "flat_short_oval"
    assert size_class(BULLRING) == "bullring"
    assert size_class(DIRT) == "dirt_oval"
    assert size_class(ROAD) == "long_road_course"


def test_superspeedway_is_a_drafting_lottery():
    s = derive_sim_ratings(SUPERSPEEDWAY)
    short = derive_sim_ratings(FLAT_SHORT)
    assert s.drafting_effect > 80 > short.drafting_effect
    assert s.crash_severity > short.crash_severity
    assert s.qualifying_importance < short.qualifying_importance
    assert s.brake_stress < short.brake_stress


def test_flat_short_track_is_brakes_and_track_position():
    s = derive_sim_ratings(FLAT_SHORT)
    assert s.brake_stress >= 80
    assert s.passing_difficulty >= 65
    assert s.mechanical_grip_importance > s.aero_importance


def test_dirt_is_setup_sensitive_and_rain_averse():
    s = derive_sim_ratings(DIRT)
    assert s.setup_sensitivity >= 80
    assert s.wet_weather_suitability <= 15
    assert s.groove_width >= 60  # the cushion: multiple lines


def test_road_and_street_courses():
    road, street = derive_sim_ratings(ROAD), derive_sim_ratings(STREET)
    assert road.wet_weather_suitability > 50 and street.wet_weather_suitability > 40
    assert street.passing_difficulty > road.passing_difficulty
    assert street.qualifying_importance > road.qualifying_importance


def test_all_ratings_in_range():
    for f in (SUPERSPEEDWAY, FLAT_SHORT, BULLRING, DIRT, ROAD, STREET):
        s = derive_sim_ratings(f)
        for k in SIM_RATING_FIELDS:
            assert 0 <= getattr(s, k) <= 100, (f.name, k)


def test_overrides_apply_and_are_marked():
    t = build_track(FLAT_SHORT, overrides={FLAT_SHORT.id: {"sim": {"brake_stress": 99},
                                                           "display_name": "Renamed"}})
    assert t.sim.brake_stress == 99
    assert t.sim.derivation == "rules+override"
    assert t.display_name == "Renamed" and t.name == "Paperclip"  # facts untouched


def test_series_suitability():
    assert "superspeedway" in series_suitability(SUPERSPEEDWAY)
    assert "short_oval" in series_suitability(FLAT_SHORT)
    assert "dirt_open_wheel" in series_suitability(DIRT)
    assert "pro_road" in series_suitability(ROAD)


def test_fact_validation_rejects_nonsense():
    bad = facts(length_mi=40.0, surface="ice")
    problems = bad.validate()
    assert any("length" in p for p in problems) and any("surface" in p for p in problems)


def test_southern_hemisphere_season_flips():
    from racingsim.tracks.ratings import derive_profile
    aus = facts(name="Mountain", region=None, country="AUS", lat=-33.4, lon=149.6,
                track_type="road_course", length_mi=3.86)
    north = facts(name="Northern", lat=46.0, lon=-89.0, region="WI")
    assert derive_profile(north).weather.season_start_month == 4
    assert derive_profile(aus).weather.season_start_month != 4
