# Public dataset ingesters

Requirements: `pip install requests pandas pyarrow`. Run from this folder; downloads are cached in `cache/`.

| Script | Source (license) | Output |
|---|---|---|
| `ingest_nascar_data.py` | nascaR.data parquet files, https://github.com/kyleGrealis/nascaR.data (GPL-3; data used with permission from DriverAverages.com) | `results/nascardata_{cup,nxs,truck}/<year>.json`, packed by `pack_results.py` into `data/results/*.jsonl.gz` |
| `ingest_wikidata_tracks.py` | Wikidata SPARQL (CC0) | `tracks_wikidata.json` (cross-check / candidates) |
| `ingest_osm_tracks.py` | OpenStreetMap via QLever (ODbL, © OpenStreetMap contributors) | `tracks_osm.json` (coordinate cross-check only; not shipped) |
| `validate_tracks.py` | — | coordinate/surface/length agreement report |

Sources that block automated access (USAC, World of Outlaws, Speedhive, nascar.com feeds, Racing-Reference,
The Third Turn) are listed with replacements in `data/knowledge/unavailable.json`.
