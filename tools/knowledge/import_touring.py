"""Import touring-series history (asphalt / dirt scrapes) into the repository.

    python tools/knowledge/import_touring.py SCRAPE_DIR [SCRAPE_DIR ...]

For each scrape folder (``series.json``, ``drivers.json``, ``venues.json``, ``<key>/<year>.json``):
* season files -> ``data/history/touring/<key>/<year>.json``  (history source = key)
* driver bios  -> ``data/history/drivers_touring_<folder>.json``
* series       -> knowledge entries linking each series to its game rung (``game_template``)
                  and history source, via ``MAPPING`` below; existing knowledge ids are reused
* venues       -> staged for ``merge.py`` (new tracks need coordinates; see ``geocode``)
Crown-jewel events (one race a year) are imported as history but never become tours.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
HIST = ROOT / "data" / "history" / "touring"
STAGE = ROOT / "tools" / "knowledge" / "staging"

# touring key -> (knowledge id, game template or None for events/knowledge-only)
MAPPING = {
    # asphalt
    "arca": ("series:arca-menards", "stock_national_dev"),
    "arca_east": ("series:arca-menards-east", "stock_regional_dev"),
    "arca_west": ("series:arca-menards-west", "stock_regional_dev"),
    "pinty": ("series:nascar-pintys", "stock_regional_dev"),
    "cascar": ("series:cascar-super-series", "stock_regional_dev"),
    "asa": ("series:asa-national-tour", "late_model_national"),
    "asa_stars": ("series:asa-stars-national", "late_model_national"),
    "whelen_modified": ("series:nascar-whelen-modified-tour", "modified_tour"),
    "whelen_southern_modified": ("series:nascar-whelen-southern-modified-tour", "modified_tour"),
    "smart_modified": ("series:smart-modified-tour", "modified_tour"),
    "oscaar_modified": ("series:oscaar-modified", "modified_tour"),
    "arca_midwest": ("series:asa-midwest-tour", "late_model_tour"),
    "nascar_midwest": ("series:nascar-midwest-series", "late_model_tour"),
    "artgo": ("series:artgo-challenge", "late_model_tour"),
    "asa_late_model": ("series:asa-late-model-challenge", "late_model_tour"),
    "asa_late_model_north": ("series:asa-late-model-north", "late_model_tour"),
    "asa_late_model_south": ("series:asa-late-model-south", "late_model_tour"),
    "cars_lms": ("series:cars-tour-lmsc", "late_model_tour"),
    "cars_slm": ("series:cars-tour-plm", "late_model_tour"),
    "pro_cup": ("series:usar-pro-cup", "late_model_tour"),
    "pass_north": ("series:pass-north", "late_model_tour"),
    "pass_south": ("series:pass-south", "late_model_tour"),
    "pass_national": ("series:pass-super-late-model", "late_model_tour"),
    "southern_super_series": ("series:asa-southern-super-series", "late_model_tour"),
    "cra_super_series": ("series:asa-cra-super-series", "late_model_tour"),
    "cra_all_stars": ("series:jegs-cra-all-stars", "late_model_tour"),
    "apc_united": ("series:apc-united-late-model", "late_model_tour"),
    "oscaar_slm": ("series:oscaar-super-late-model", "late_model_tour"),
    # NASCAR regional touring divisions (1995-2006) and related
    "nascar_southeast": ("series:nascar-all-pro-southeast", "late_model_tour"),
    "nascar_southwest": ("series:nascar-southwest-tour", "late_model_tour"),
    "nascar_northwest": ("series:nascar-northwest-tour", "late_model_tour"),
    "nascar_dash": ("series:nascar-goodys-dash", "late_model_tour"),
    "nascar_autozone_elite": ("series:nascar-autozone-elite-division", None),
    "nascar_sportsman": ("series:nascar-sportsman-division", None),
    # dirt / sprint / midget
    "woo_sprint": ("series:woo-sprint", "outlaw_sprint"),
    "high_limit": ("series:high-limit-racing", "sprint_car_tour"),
    "all_stars": ("series:all-star-circuit-of-champions", "sprint_car_tour"),
    "ascs_national": ("series:ascs-national", "sprint_car_tour"),
    "usac_cra_sprint": ("series:usac-cra-sprint", "sprint_car_tour"),
    "national_sprint_tour": ("series:national-sprint-tour", "sprint_car_tour"),
    "usac_sprint": ("series:usac-national-sprint", "national_sprint"),
    "usac_midget": ("series:usac-national-midget", "national_midget"),
    "usac_silver_crown": ("series:usac-silver-crown", None),
    "lolmds": ("series:lucas-oil-lmds", "dirt_late_national"),
    "woo_late_model": ("series:woo-late-model", "dirt_late_national"),
    "mars_late_model": ("series:mars-late-model", "dirt_late_model_tour"),
    "supr": ("series:supr", "dirt_late_model_tour"),
    "busch_all_star_tour": ("series:busch-all-star-tour", "dirt_late_model_tour"),
    "super_dirtcar": ("series:super-dirtcar-series", "dirt_modified_tour"),
    "usmts": ("series:usmts", "dirt_modified_tour"),
    "dirtcar_358": ("series:dirtcar-358-modified", "dirt_modified_tour"),
    "stss": ("series:short-track-super-series", "dirt_modified_tour"),
    "stss_north": ("series:short-track-super-series-north", None),
    "stss_south": ("series:short-track-super-series-south", None),
    "mars_modified": ("series:mars-modified", "dirt_modified_tour"),
    "powri_midget": ("series:powri-national-midget", "regional_midget"),
    "powri_west_midget": ("series:powri-west-midget", "regional_midget"),
    "usac_western_midget": ("series:usac-western-midget", "regional_midget"),
}
# Period names missing from the scraped name lists (curated; medium confidence).
NAME_FILL = {
    "arca": [{"from": 1995, "to": 1997, "name": "ARCA Bondo/Mar-Hyde Series"}],
    "arca_east": [{"from": 1995, "to": 2005, "name": "NASCAR Busch North Series"},
                  {"from": 2006, "to": 2006, "name": "NASCAR Busch East Series"},
                  {"from": 2010, "to": 2011, "name": "NASCAR K&N Pro Series East"}],
    "whelen_modified": [{"from": 1995, "to": 2004, "name": "NASCAR Featherlite Modified Tour"}],
    "arca_midwest": [{"from": 2013, "to": 2026, "name": "ARCA Midwest Tour"}],
    "cars_lms": [{"from": 2015, "to": 2026, "name": "CARS Late Model Stock Car Tour"}],
    "cars_slm": [{"from": 2015, "to": 2022, "name": "CARS Super Late Model Tour"},
                 {"from": 2023, "to": 2026, "name": "CARS Pro Late Model Tour"}],
    "asa": [{"from": 1995, "to": 2004, "name": "ASA National Tour"}],
}
NAME_REPLACE = {"cars_lms", "cars_slm"}  # the scrape gives both divisions the umbrella name

EVENT_KEYS = {"snowball_derby", "winchester_400", "oxford_250", "slinger_nationals", "all_american_400",
              "florida_governors_cup", "valleystar_300", "la_crosse_oktoberfest", "myrtle_beach_400", "little_500"}
DISCIPLINE = {"asphalt_late_model": "stock_car", "modified": "stock_car", "stock_car": "stock_car",
              "dirt_late_model": "dirt_oval", "sprint_car": "dirt_oval", "midget": "dirt_oval",
              "silver_crown": "dirt_oval", "dirt_modified": "dirt_oval"}
LEVEL_TIER = {"national": 4, "super_regional": 3, "regional": 3}


def import_folder(src: Path, mapping: dict, events: set) -> dict:
    meta = json.loads((src / "series.json").read_text(encoding="utf-8"))
    HIST.mkdir(parents=True, exist_ok=True)
    knowledge, unmapped = [], []
    for key, m in meta.items():
        folder = src / key
        if folder.is_dir():
            dst = HIST / key
            dst.mkdir(exist_ok=True)
            for f in folder.glob("*.json"):
                if f.stem.isdigit():
                    shutil.copy2(f, dst / f.name)
        is_event = key in events or m.get("kind") == "event"
        kid, template = mapping.get(key, (f"series:{key.replace('_', '-')}", None))
        if key not in mapping and not is_event:
            unmapped.append(key)
        years = m.get("years") or [None, None]
        entry = {
            "id": kid if not is_event else f"event:{key.replace('_', '-')}",
            "name": m.get("name"),
            "names_by_year": (NAME_FILL.get(key, []) if key in NAME_REPLACE
                              else NAME_FILL.get(key, []) + (m.get("names_by_year") or [])),
            "discipline": DISCIPLINE.get(m.get("discipline"), m.get("discipline")),
            "level": m.get("level"), "regions": m.get("footprint") or [],
            "years": {"from": years[0], "to": years[1] if years[1] and years[1] < 2026 else None},
            "history_source": key, "confidence": "medium",
            "sources": ["src:wikipedia"] + [s for s in (m.get("sources") or []) if isinstance(s, str) and s.startswith("src:")],
            "notes": m.get("notes"),
        }
        if not is_event:
            entry["game_template"] = template
            entry["game_tier"] = LEVEL_TIER.get(m.get("level"))
            knowledge.append(entry)
    # Crown-jewel event files ({name, track, city, state, winners: [{year, name, wiki}]}) -> one-race seasons.
    for ev in sorted((src / "events").glob("*.json")) if (src / "events").is_dir() else []:
        e = json.loads(ev.read_text(encoding="utf-8"))
        dst = HIST / ev.stem
        dst.mkdir(exist_ok=True)
        for w in e.get("winners") or []:
            if not w.get("year"):
                continue
            season = {"series": ev.stem, "year": w["year"], "official_name": e.get("name"), "data_level": "schedule",
                      "champion": {"name": w.get("name"), "wiki": w.get("wiki")}, "teams": [], "standings": [],
                      "schedule": [{"round": 1, "race": e.get("name"), "track": w.get("track") or e.get("track"),
                                    "city": w.get("city") or e.get("city"), "state": w.get("state") or e.get("state"),
                                    "winner": w.get("name"), "winner_wiki": w.get("wiki")}],
                      "sources": e.get("sources") or []}
            (dst / f"{w['year']}.json").write_text(json.dumps(season, ensure_ascii=False), encoding="utf-8")
    drivers = src / "drivers.json"
    if drivers.exists():
        shutil.copy2(drivers, ROOT / "data" / "history" / f"drivers_touring_{src.name}.json")
    out = STAGE / src.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "series.json").write_text(json.dumps(knowledge, indent=1, ensure_ascii=False), encoding="utf-8")
    # The import decides which rung a series plays and where its history lives.
    overrides = {}
    for e in knowledge:
        names = e["names_by_year"] or [{"from": e["years"]["from"], "to": e["years"]["to"] or 2100, "name": e["name"]}]
        overrides[e["id"]] = {"game_template": e.get("game_template"), "history_source": e["history_source"],
                              "names_by_year": names, "prefer_curated_names": e["history_source"] in NAME_REPLACE}
    (out / "overrides.json").write_text(json.dumps(overrides, indent=1), encoding="utf-8")
    venues = json.loads((src / "venues.json").read_text(encoding="utf-8")) if (src / "venues.json").exists() else {}
    new = venues.get("new", []) if isinstance(venues, dict) else []
    existing = venues.get("existing", []) if isinstance(venues, dict) else []
    (out / "tracks_new.json").write_text(json.dumps(new, indent=1, ensure_ascii=False), encoding="utf-8")
    enrich = [{"id": e["existing_id"], "aliases": [n for n in e.get("names_seen") or []]} for e in existing
              if e.get("existing_id")]
    (out / "tracks_enrich.json").write_text(json.dumps(enrich, indent=1, ensure_ascii=False), encoding="utf-8")
    for name in ("sources.json", "ledger.jsonl", "unavailable.json"):
        if (src / name).exists():
            shutil.copy2(src / name, out / name)
    print(f"{src.name}: {len(meta)} series ({len(knowledge)} tours/rungs), {len(new)} new venues, "
          f"{len(enrich)} existing venues; unmapped: {unmapped}")
    return {"staging": out, "unmapped": unmapped}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        import_folder(Path(p), MAPPING, EVENT_KEYS)
