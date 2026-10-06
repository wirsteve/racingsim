# Data credits and licenses

| Data | Source | License / terms | Where |
|---|---|---|---|
| NASCAR race-by-race results 1949–2026 (Cup), 1982– (Xfinity), 1995– (Trucks) | [nascaR.data](https://github.com/kyleGrealis/nascaR.data) by Kyle Grealis; data used with permission from DriverAverages.com | GPL-3.0 | `data/results/*.jsonl.gz`, table `race_result` |
| National-series seasons (rosters, standings, calendars) 1995–2026 | Wikipedia season articles | Facts extracted (CC BY-SA text not copied) | `data/history/` |
| Driver birth dates/places, track coordinates | Wikidata | CC0 | `data/history/drivers*.json`, `data/tracks/` |
| Coordinates for some venues (marked "openstreetmap.org … (ODbL)" in their sources) and coordinate cross-checks | OpenStreetMap (© OpenStreetMap contributors) | ODbL 1.0 — those coordinates remain under ODbL | `data/tracks/census_venues.json`, `tools/ingest/datasets/` |
| Local/regional track census (725 venues: location, size, surface, banking category, status) | IMCA and WISSOTA track directories, track-maintained MyRacePass profiles, Wikipedia/Wikidata, Nominatim (OSM geocoder) — robots.txt checked for every scripted site | Facts with per-record source URLs | `data/tracks/census_venues.json`, `data/track_enrich.json` |
| Touring-series history (asphalt + dirt: ARCA, ARCA East/West lineages, modified tours, CARS, ASA, PASS, Pro Cup, Pinty's, World of Outlaws, Lucas Oil, USAC, All Stars, ASCS, USMTS, Super DIRTcar, MARS, crown-jewel winners) | Wikipedia/Wikidata; schedules/champions from usmts.com, ascsracing.com, shorttracksuperseries.com, marsracingseries.com, lucasdirt.com, highlimitracing.com (robots.txt allowed) | Facts | `data/history/touring/` |
| Research facts (series, costs, ladders, economics) | See `data/knowledge/sources.json` (one entry per source) and `ledger.jsonl` | Facts with citations | `data/knowledge/` |

Racing-Reference and The Third Turn were not accessed by any script (Cloudflare block /
robots.txt disallow); see `data/knowledge/unavailable.json` for these and other skipped
sources and their replacements.
