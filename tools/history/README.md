# History data scrapers

These scripts built `data/history/` from Wikipedia season articles and Wikidata
driver records (birth dates, birthplaces). They were not used to contact
racing-reference.info, whose terms restrict automated access.

| Script | Output (written next to the script) |
|---|---|
| `scrape_nascar_cup.py` | `nascar_cup/<year>.json`, `drivers_cup.json` |
| `scrape_nascar_lower.py` | `nascar_xfinity/<year>.json`, `nascar_trucks/<year>.json`, `drivers_xfinity_trucks.json` |
| `scrape_openwheel.py` | `cart_champcar/`, `irl_indycar/`, `indy_lights/`, `pro_mazda/`, `usf2000/`, `drivers_openwheel.json` |

```bash
cd tools/history
python scrape_nascar_cup.py --refresh 2026        # e.g. pick up the end of the current season
cp -r nascar_cup ../../data/history/ && cp drivers_cup.json ../../data/history/
```

HTTP responses are cached in `cache_*` folders (git-ignored), so re-runs are fast
and offline. Wikipedia rate-limits aggressive clients: the scripts pause between
requests and fall back to `index.php?action=raw` when the API returns 429.

Season file format (all series):

```json
{"series": "...", "year": 1996, "official_name": "NASCAR Winston Cup Series",
 "teams": [{"team": "...", "manufacturer": "...", "cars": [{"number": "24", "full_time": true,
            "drivers": [{"name": "Jeff Gordon", "wiki": "Jeff_Gordon"}]}]}],
 "standings": [{"pos": 1, "name": "...", "wiki": "...", "points": 4657, "wins": 2, "starts": 31,
                "top5": 21, "top10": 24}],
 "schedule": [{"round": 1, "date": "1996-02-18", "race": "Daytona 500",
               "track": "Daytona International Speedway", "city": "Daytona Beach", "state": "FL",
               "winner": "Dale Jarrett", "winner_wiki": "Dale_Jarrett"}]}
```
