# Data tools

Everything that builds `data/` lives here. One command re-runs the whole source pipeline:

```bash
python -m racingsim data update            # all ingesters in tools/ingest/registry.json, then rebuild + compile
python -m racingsim data update --only touring:dirt   # just one source
python -m racingsim data build             # compile data/racingsim.db from data/ (automatic on first run)
python -m racingsim data validate          # schema, references, ranges, cross-source checks
python -m racingsim data report            # counts + confidence by category -> docs/DATA_REPORT.md
```

| Folder | What it does | Main sources |
|---|---|---|
| `history/` | National series seasons 1995– (NASCAR Cup/Xfinity/Trucks, CART/IRL/IndyCar, Indy Lights, Pro Mazda, USF2000) | Wikipedia season articles, Wikidata |
| `touring/asphalt/` | Asphalt touring series + crown-jewel winners (ARCA, East/West lineages, modifieds, CARS, ASA, PASS, CRA, Pinty's …) | Wikipedia, Wikidata |
| `touring/dirt/scraper/` | Dirt late model, sprint, midget, dirt modified series + crown jewels | Wikipedia, Wikidata, series sites whose robots.txt allows it |
| `touring/nascar_touring/` | NASCAR regional divisions 1995–2006, Goody's Dash, Hooters Pro Cup | Wikipedia, Ultimate Racing History, RacingCalendar.net, Crittenden Automotive Library |
| `tracks_census/` | North American track census | IMCA/WISSOTA directories, MyRacePass track profiles, Wikipedia/Wikidata, Nominatim |
| `ingest/datasets/` | Public datasets: nascaR.data race results (GPL-3), Wikidata/OSM track lists | see `data/CREDITS.md` |
| `knowledge/rules_import.py` | Folds staged rules research (class rules, parts, points, payouts, race formats) into `data/rules/research.json` + `sources.json` | track house rules & sanctioning rulebook PDFs, tire/engine price lists, series sites (robots.txt respected) |
| `knowledge/rules_classes.py` | Curated car classes → `data/rules/classes.json` (edit values here, cite research source ids) | `data/rules/research.json` |
| `knowledge/` | `import_touring.py`, `geocode_venues.py`, `merge.py` (dedupe, entity matching, conflict log), `rebuild.py` (runs all three), `analysis/` (statistics computed from the history) | — |

Every scraper caches its downloads, checks robots.txt for non-Wikimedia sites, rate-limits itself and
writes JSON in the formats documented in `docs/DATA_MODEL.md`. Sources that block automated access
are never worked around; they are recorded with a replacement in `data/knowledge/unavailable.json`.
Curated corrections live in `data/knowledge/aliases.json`, `overrides.json` and `alias_blocklist.json`.
