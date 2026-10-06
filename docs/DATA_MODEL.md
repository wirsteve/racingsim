# Racing knowledge layer: data model

The knowledge layer is a set of JSON source files under `data/knowledge/` (plus the
historical season files under `data/history/`) compiled into the SQLite database
`data/racingsim.db` by `python -m racingsim data build`. JSON is the source of
truth (diffable and hand-editable); SQLite is what the game reads.

## Conventions

**Measured attributes** (costs, horsepower, ages, field sizes …) are *ranged
facts*, never false precision:

```json
"annual_cost_usd": {"min": 40000, "max": 100000, "unit": "USD/season", "year_basis": 2025,
                    "confidence": "medium", "sources": ["src:speed51-late-model-costs"],
                    "notes": "self-built crate late model, local weekly program"}
```

* Use `"value"` for single values, `"min"`/`"max"` for ranges, and `"category"` for
  qualitative values (e.g. `"banking": {"category": "high"}`).
* `confidence` is `high`, `medium` or `low`. High means two or more independent
  reliable sources, or an official source. Low means one secondary source or an
  informed estimate (say so in `notes`).
* `sources` lists source ids (`src:<slug>`) defined in the ledger.

**Ids** are lowercase slugs: `series:arca-menards`, `body:usac`, `class:super-late-model`,
`track:<existing track id>`, `path:asphalt-stock-car`, `driver:<wiki title or slug>`.

**Provenance.** Every entity has `"sources": [...]` and an overall `"confidence"`.

## Entities (JSON files in `data/knowledge/`)

| File | Entity | Key fields |
|---|---|---|
| `sources.json` | Source | `id, name, url, kind, reliability, license, accessed, notes` |
| `ledger.jsonl` | LedgerEntry (one per finding) | `source, url, info, accessed, reliability, confidence, notes, entities[]` |
| `unavailable.json` | SourceUnavailable | `source, url, reason, checked, replacement_source` |
| `sanctioning_bodies.json` | SanctioningBody | `id, name, abbrev, country, founded, defunct, website, scope, notes, confidence, sources` |
| `car_classes.json` | CarClass | `id, name, discipline, chassis, drivetrain, engine, horsepower{}, weight_lb{}, tires, spec_rules, new_car_cost_usd{}, used_car_cost_usd{}, notes, confidence, sources` |
| `series.json` | Series | see below |
| `career_stages.json` | DriverCareerStage | `id, name, description, age_range{}, typical_duration_years{}, typical_series[], exits[] (outcome, share{}), confidence, sources` |
| `career_paths.json` | CareerPath | see below |
| `transitions.json` | CareerTransition | `from, to, frequency (common/occasional/rare), share_of_movers{}, typical_age{}, gating{talent,money,sponsorship,connections,manufacturer,results,age} weights, examples[], confidence, sources` |
| `advancement_factors.json` | AdvancementFactor | `id, name, description, weight_by_level{tier: {min,max}}, evidence, confidence, sources` |
| `datasets.json` | DatasetEvaluation | `name, url, coverage, accuracy, license, update_frequency, usefulness, used (bool), notes` |
| `tracks_extra.json` | Track (new venues) | the `data/tracks/*.json` schema plus `banking_category`, `major_series[]`, `prestige_category` |

### Series

```json
{"id": "series:arca-menards", "name": "ARCA Menards Series",
 "names_by_year": [{"from": 2019, "to": 2026, "name": "ARCA Menards Series"}],
 "sanctioning_body": "body:arca", "discipline": "stock_car", "car_class": "class:arca-stock-car",
 "level": "national", "game_tier": 4, "scope": "national", "regions": ["USA"],
 "years": {"from": 1953, "to": null},
 "typical_age": {"min": 16, "max": 30, "confidence": "medium", "sources": []},
 "entry_age": {...}, "exit_age": {...}, "experience_level": "advanced amateur / development pro",
 "race_length": {"min": 80, "max": 200, "unit": "miles"}, "track_types": ["superspeedway", "intermediate", "short_oval", "road_course", "dirt_mile"],
 "field_size": {...}, "season_events": {...}, "annual_cost_usd": {...}, "win_purse_usd": {...}, "points_fund_usd": {...},
 "team_structure": "teams", "equipment_ownership": "team-owned; drivers often bring sponsorship (pay seats)",
 "licensing": "NASCAR/ARCA license; age 15 on short tracks and road courses, 18 on superspeedways",
 "prerequisites": "...", "feeder_series": ["series:..."], "next_steps": ["series:nascar-trucks"],
 "advancement_rate": {"min": 0.05, "max": 0.15, "unit": "share of full-time drivers reaching the next level within 3 years"},
 "advancement_drivers": {"talent": 0.3, "money": 0.35, "sponsorship": 0.2, "connections": 0.15},
 "dead_ends": "...", "notes": "...", "confidence": "medium", "sources": ["src:..."],
 "game_template": "stock_national_dev", "history_source": "arca"}
```

`game_template` ties a real series to the simulation rung it plays as. `history_source`
names the `data/history/<dir>/` that holds its seasons.

### CareerPath

```json
{"id": "path:asphalt-stock-car", "name": "Asphalt stock car (NASCAR ladder)", "discipline": "stock_car",
 "description": "...",
 "steps": [{"order": 1, "stage": "Youth", "series": ["series:bandolero", "series:legends"],
            "typical_age": {"min": 8, "max": 16}, "typical_years": {"min": 2, "max": 5},
            "advance_share": {"min": 0.2, "max": 0.4, "confidence": "low"},
            "gating": {"talent": 0.4, "money": 0.4, "connections": 0.2}, "notes": "..."}],
 "crossovers": [{"from": "series:...", "to": "series:...", "frequency": "occasional", "notes": "..."}],
 "dead_ends": ["..."], "examples": [{"driver": "driver:Kyle_Busch", "route": "..."}],
 "confidence": "medium", "sources": ["src:..."]}
```

## Historical tables (compiled from `data/history/`)

| Table | Contents |
|---|---|
| `season(source, year, official_name, data_level, n_regulars, field, doc)` | one row per series-season |
| `standing(source, year, pos, name, wiki, points, wins, starts, top5, top10, team)` | final standings |
| `race(source, year, round, date, race, track, city, state, winner, winner_wiki, cancelled, track_id)` | calendar and winners, matched to track ids at build time |
| `driver(wiki, name, qid, birth_date, birth_place, state, country)` | HistoricalDriver |
| `team(...)` | HistoricalTeam (team name, years, manufacturer, cars) |
