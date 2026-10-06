# Data credits and licenses

| Data | Source | License / terms | Where |
|---|---|---|---|
| NASCAR race-by-race results 1949–2026 (Cup), 1982– (Xfinity), 1995– (Trucks) | [nascaR.data](https://github.com/kyleGrealis/nascaR.data) by Kyle Grealis; data used with permission from DriverAverages.com | GPL-3.0 | `data/results/*.jsonl.gz`, table `race_result` |
| National-series seasons (rosters, standings, calendars) 1995–2026 | Wikipedia season articles | Facts extracted (CC BY-SA text not copied) | `data/history/` |
| Driver birth dates/places, track coordinates | Wikidata | CC0 | `data/history/drivers*.json`, `data/tracks/` |
| Track coordinate cross-checks | OpenStreetMap (© OpenStreetMap contributors) | ODbL 1.0 (used for verification only; not shipped) | `tools/ingest/datasets/` |
| Research facts (series, costs, ladders, economics) | See `data/knowledge/sources.json` (one entry per source) and `ledger.jsonl` | Facts with citations | `data/knowledge/` |

Racing-Reference and The Third Turn were not accessed by any script (Cloudflare block /
robots.txt disallow); see `data/knowledge/unavailable.json` for these and other skipped
sources and their replacements.
