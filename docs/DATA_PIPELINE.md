# Racing data layer: what was built, from where, and how to run it

Status as of 2026-10-06. The live counts are in [`DATA_REPORT.md`](DATA_REPORT.md) (`python -m racingsim data report`), the schemas are in [`DATA_MODEL.md`](DATA_MODEL.md), and the tooling is described in [`../tools/README.md`](../tools/README.md).

## 1. What was collected

| Area | Contents | Count |
|---|---|---|
| **Series profiles** | Real series from youth classes to Cup, IndyCar and IMSA. Each has its sanctioning body, region, years active, names by year, car class, ages, costs, field size, season and race length, team structure, licensing, prerequisites, feeder series and next steps, advancement rate and drivers, dead ends, and the game rung it plays | 148 |
| **Sanctioning bodies** | NASCAR, ARCA, USAC, WoO/DIRTcar, IMCA, USRA, UMP, INEX, QMA, ASA, CARS, PASS, CRA, POWRi, ASCS, All Stars, IndyCar/USF, IMSA, SCCA, NASA, SRO, WKA, SKUSA, … | 40 |
| **Car classes** | Chassis, layout, engine, horsepower, weight and car-cost ranges | 68 |
| **Career paths** | 85 steps in total, each with ages, years at the step, share who move up, and what gates the move. Real drivers are given as examples | 21 |
| **Career stages** | From youth/entry to retirement or becoming an owner/promoter, with ages, durations and how drivers leave each stage | 10 |
| **Transitions** | Moves between series: how often they happen, the share of drivers who make them, typical age and what gates them. 12 are computed from our own history data | 71 |
| **Advancement factors** | Weights for tiers 0–7, now used by team owners in the market | 15 |
| **Economics** | Season budgets, pay-seat prices, sponsorship deal sizes, purses, scholarships, salaries and crash damage | 44 entries |
| **Ranged facts** | Every number is stored as a range or category with a confidence and its sources | 798 |
| **Tracks** | 1,147 venues: 1,016 USA, 96 Canada, 11 Mexico, 24 international. Facts are kept separate from the game's ratings. 776 were added in this pass from the census and touring calendars | 1,147 |
| **Historical seasons** | 101 series from 1934 to 2026. NASCAR seasons before 1995 are derived from race results | 2,535 seasons, 12,163 races (10,138 with a winner) |
| **Race-by-race results** | NASCAR Cup 1949–, Xfinity 1982–, Trucks 1995– (nascaR.data) | 182,760 driver-race rows, 5,042 races |
| **Historical drivers** | Wikipedia/Wikidata bios with birth date and place | 4,046 |
| **Historical teams** | Teams by season | 3,122 teams, 9,615 team-seasons |
| **Provenance** | Defined sources, ledger entries, and logged access refusals | 324 sources, 3,042 ledger entries, 45 refusals |

**Touring and grassroots history now in the game**
- **Asphalt touring series:**
  - ARCA, plus the ARCA East and ARCA West lineages (Busch North → K&N East; Winston West → K&N West).
  - Modified tours: Whelen/Featherlite Modified, Whelen Southern, SMART.
  - Late-model tours: CARS (two divisions), ARCA/ASA Midwest, CRA, ASA National Tour, ASA STARS, PASS.
  - Pro tours: Hooters Pro Cup, Pinty's/CASCAR, APC, OSCAAR.
- **NASCAR regional divisions (1995–2006):** Slim Jim All Pro/Southeast, Southwest, Northwest and Midwest. Also Goody's Dash and ARTGO.
- **Dirt series:**
  - World of Outlaws Sprint and Late Models, Lucas Oil.
  - USAC Sprint, Midget and Silver Crown.
  - All Stars, ASCS, High Limit, USAC/CRA.
  - USMTS, Super DIRTcar, DIRTcar 358, Short Track Super Series.
  - MARS, SUPR, Busch All-Star Tour.
  - POWRi and western midgets.
- **Crown-jewel winner lists (35 events):** Snowball Derby, Oxford 250, Winchester 400, All American 400, Slinger Nationals, the Martinsville late-model race, Knoxville Nationals (since 1961), Chili Bowl, Kings Royal, World 100, the Dream, Super DIRT Week, Turkey Night, Hoosier Hundred, and others.

## 2. Career paths modelled

**Stock car**
- Asphalt stock car (the NASCAR ladder)
- Late model → ARCA/Trucks through a development program
- Family-funded fast track
- Self-funded grinder / late bloomer
- Veteran step-downs

**Dirt and open-wheel ovals**
- Dirt late model (local → regional → national tours)
- Dirt → NASCAR crossover
- Sprint/midget USAC route into NASCAR or IndyCar
- WoO/High Limit professional sprint career
- Asphalt modified (SK → Whelen Modified Tour)
- Dirt modified (IMCA → USMTS; Northeast 358 → big-block)

**Open wheel**
- Karting → USF ladder → Indy NXT → IndyCar
- European ladder import
- Scholarship-funded champion route
- Historic CART-era ladder

**Sports car and road racing**
- Club/karting → one-make cups → IMSA → GTD/LMP2 → factory
- Gentleman/Bronze Pro-Am
- Road-course specialist → NASCAR

**Crossovers**
- Open wheel → NASCAR
- Open wheel → sports car
- Karting → oval stock/dirt

## 3. How the research shapes the simulation

- **Who teams hire.** Owners weigh drivers using the advancement-factor weights for their tier.
  - Money counts most in tiers 3–6 (sponsorship plus family money is roughly 0.4 of the decision).
  - At Cup level, performance and marketability count most.
  - Relationships carry more weight in the middle tiers. Truck top-5 finishers on Cup-affiliated teams moved up 59% of the time, against 27% on independent teams.
- **Calibration targets from our own history** (`tools/knowledge/analysis/`):
  - Promotion rates:
    - Trucks → Xfinity/Cup: 0.28 within 3 years.
    - Xfinity → Cup: 0.39.
    - Indy Lights champion → full IndyCar season: 77%.
  - Age effects: drivers under 23 moved up 0.53 of the time, those 28 and over 0.17.
  - Seat turnover per year: Cup 16%, Xfinity/Trucks 39%, Indy Lights 58%.
- **Real touring series replace the generic ones** for the years they existed, with real names, real calendars and real regulars at the start year. When a season has no calendar, the series races at the venues of its nearest documented seasons.
- **Crown jewels** show their real winners from before your start year.
- **Veterans** start with their real records: in a 1995 start, Earnhardt has 616 starts, 84 wins and 7 titles.

## 4. Data sources used (preferred order)

1. **Official sanctioning bodies and series** (rules, schedules, champions, scholarships): IndyCar/USF Pro Championships, IMSA, SCCA, NASCAR/ARCA rulebooks (via search snippets), IMCA and WISSOTA track directories, and the sites of USMTS, ASCS, Short Track Super Series, MARS, Lucas Oil and High Limit. robots.txt was checked on each site and requests were rate-limited.
2. **Track-maintained profiles:** MyRacePass (robots.txt allows).
3. **Wikipedia and Wikidata:** season articles, series and venue articles, and list articles (CC BY-SA text is never copied; Wikidata is CC0).
4. **Public datasets:**
   - nascaR.data (GPL-3; data used with permission from DriverAverages.com).
   - OpenStreetMap (ODbL) for coordinates of some venues and for cross-checks.
   - Nominatim for geocoding.
5. **Public historical databases:** Ultimate Racing History, RacingCalendar.net (user-submitted, so low reliability; used only for dates and venues) and the Crittenden Automotive Library.
6. **News and secondary sources** for costs, salaries, pay-seat prices and development programs. There are 93 news sources; every number is cited in the ledger.
7. **Our own analysis** of the history data (`src:racingsim-history-analysis`).

Per-source licences are listed in `data/CREDITS.md`.

## 5. Sources skipped because of access restrictions (none circumvented)

| Source | Reason | Replaced by |
|---|---|---|
| **Racing-Reference** | Cloudflare blocks automated requests | Wikipedia/Wikidata seasons, nascaR.data |
| **The Third Turn** | robots.txt: `User-agent: * Disallow: /` | Wikipedia/Wikidata, official series sites, Ultimate Racing History, Crittenden |
| **USAC (usacracing.com)** | robots.txt blocks AI agents | Wikipedia USAC seasons |
| **World of Outlaws** | robots.txt disallows results and API paths | Wikipedia WoO seasons |
| **nascar.com and its feeds; Jayski; Forbes** | Cloudflare challenge or 403 | nascaR.data; news summaries |
| **Speedhive (MyLaps) API** | robots.txt `Disallow: /` | OpenStreetMap; track sites |
| **Al Kamel (IMSA timing)** | Licence forbids redistribution | Wikipedia IMSA seasons |
| **DriverAverages** | robots.txt blocks AI agents | nascaR.data, which has DriverAverages' permission |
| **USRA, NASA, stockcarracing.fandom** | Bot checks | MyRacePass, Wikipedia |
| **INEX** | Not reachable from this environment | MyRacePass class lists |
| **Overpass API** | Robots rules and timeouts | QLever OSM endpoint, Nominatim |
| **Kaggle** | Login required | nascaR.data |
| **ChampCarStats** | No licence; would need permission | Not used |
| **Ultimate Super Late Model Series** | robots.txt disallows everything | Not used. One homepage fetch happened before the robots.txt check; none of its content is used |

Two more notes:
- **Ultimate Racing History** serves a self-signed HTTPS certificate. It was read over plain HTTP, which is how the site links itself (its robots.txt permits access), and those requests went out directly rather than through the session proxy.
- **All 45 refusals** are in `data/knowledge/unavailable.json` and the database table `source_unavailable`.

## 6. Validation

- **NASCAR results vs. our season files:** race winners agree in 2,929 of 2,929 overlapping races. Season wins and starts for top-10 drivers agree 100%; top-10 counts agree 99.6%.
- **Independent check:** nascaR.data agrees with Neil Paine's Cup data (1972–2025) on 99.88% of finishing positions, 99.79% of starting positions and 99.89% of winners.
- **Derived pre-1995 champions** match the real ones: Earnhardt 1980/86/87/90/91/93/94, Waltrip 1981/82/85, Labonte 1984, Wallace 1989.
- **Coordinates:** OpenStreetMap is within a median 0.10 km of our coordinates, and Wikidata within 0.014 km. 95% of tracks are within 1 km of both.
- **`python -m racingsim data validate`** reports 0 errors. The 12 warnings are kept on purpose:
  - 8 seasons where the source contradicts itself, its standings win totals disagreeing with its own race winners: ARCA 2009, ARCA East 2007, ARCA West 1995–96, SMART 2000–02, WoO Sprint 2015.
  - 2 seasons where only a few race winners are known against full standings: NASCAR Southeast and Southwest 1996.
  - 2 research entries with no source listed.
- **Track matching:** 11,727 of 12,143 historical races (96.6%) are matched to a track in the database.
- **Determinism:** the same seed produces the same world under any Python hash seed (regression test).
- **Ecosystem stability:** in a 25-year AI run on the full pyramid, the population held at about 22,000 and no seats in active series were left empty.

## 7. Confidence by category

| Category | High | Medium | Low |
|---|---|---|---|
| Series profiles | 13 | 96 | 39 |
| Sanctioning bodies | 20 | 17 | 3 |
| Car classes | 10 | 41 | 17 |
| Career paths | 3 | 15 | 3 |
| Career stages | 3 | 2 | 5 |
| Advancement factors | 2 | 9 | 4 |
| Transitions | 12 | 11 | 48 |
| Ranged facts | 131 | 188 | 471 |
| Tracks | 314 | 388 | 21 |

Another 424 tracks are older records with sourced facts but no overall confidence rating.

Overall confidence by area:
- **High:** NASCAR national history (season files plus race-by-race results), the open-wheel ladder history, minimum ages and licensing rules, scholarship values, and the computed transition and age statistics.
- **Medium:** touring-series history where season articles exist, national-series costs, track census records with official or track-maintained sources.
- **Low:** costs and quit rates for grassroots and local classes (no systematic source exists), advancement weights below tier 3, and inherited profile facts. Inherited facts are labelled with the series they came from.

## 8. Remaining gaps

- **655 seasons have only the champion.** This is most acute for the dirt tours (All Stars, ASCS, USAC national series before 2010), PASS, Pro Cup 2013–14 and the ASA National Tour. Their organisers either publish no archives or block automated access.
- **No open source for local weekly-track results.** Local divisions stay generated, though they run at the real tracks.
- **Profile gaps:** 51 series have no field size; cost, age and horsepower are missing for a handful of niche series.
- **Track gaps:**
  - 416 historical races sit at venues with no known coordinates (e.g. Summerville SC, Thunder Hill TX, Shady Bowl OH).
  - The census found 1,370 more name-only venues that it couldn't place.
  - Banking in degrees is known for only a minority of tracks; the rest use a banking category.
- **Missing figures:** pay-driver share per field, ARCA purses and points fund (the ARCA PDFs returned 403), and US injury rates.
- **No series at all:** Southern All Stars, NeSmith, Ultimate SLM, Hav-A-Tampa, UMP Summernationals and Xtreme DIRTcar have no usable public season data.

## 9. Files and database tables

**JSON sources (the source of truth, all in git):**

| Path | Contents |
|---|---|
| `data/knowledge/` | `series.json`, `sanctioning_bodies.json`, `car_classes.json`, `career_paths.json`, `career_stages.json`, `transitions.json`, `advancement_factors.json`, `economics.json`, `datasets.json`, `sources.json`, `ledger.jsonl`, `unavailable.json`, `computed_evidence.json`, `history_analysis_openwheel.json` |
| `data/knowledge/` (curated) | `aliases.json`, `overrides.json`, `alias_blocklist.json`, plus `merge_log.json` (recorded disagreements between sources) |
| `data/history/` | `<series>/<year>.json` national seasons, `touring/<series>/<year>.json`, `drivers*.json` |
| `data/results/` | `nascar_{cup,xfinity,trucks}.jsonl.gz` |
| `data/tracks/` | `major_venues.json`, `local_regional_venues.json`, `historic_venues.json`, `census_venues.json` |
| `data/` (other) | `track_years.json`, `track_enrich.json`, `series.json`, `series_eras.json`, `manufacturers.json`, `CREDITS.md` |

**Compiled database `data/racingsim.db` (SQLite, about 50 MB, shipped inside the app):**

| Group | Tables |
|---|---|
| Knowledge | `series_info`, `series_name`, `series_link`, `sanctioning_body`, `car_class`, `career_stage`, `career_path`, `career_path_step`, `transition`, `advancement_factor`, `advancement_weight`, `economics`, `dataset` |
| Provenance | `fact` (every ranged attribute with confidence and sources), `source`, `ledger`, `source_unavailable` |
| History | `season`, `standing`, `race` (track ids resolved at build time), `race_info`, `race_result`, `driver`, `team`, `series` |
| Tracks | `track_facts` (sourced), `track_profile` and `track_sim_ratings` (derived by the game) |
| Build | `meta` (build stamp) |

## 10. Commands

```bash
python -m racingsim data build              # compile data/racingsim.db (runs automatically when inputs change)
python -m racingsim data validate           # schema / references / ranges / duplicates / cross-source checks
python -m racingsim data report             # counts, confidence, gaps -> docs/DATA_REPORT.md
python -m racingsim data update             # re-run every ingester in tools/ingest/registry.json, rebuild, compile
python -m racingsim data update --only touring:asphalt    # one source
python tools/knowledge/rebuild.py           # re-fold touring/census/dataset outputs into data/ (import, geocode, merge, fill gaps)
python tools/build_app.py                   # stand-alone app for this OS (CI builds Windows/macOS/Linux on every push)
```

Every ingester caches its downloads and rate-limits itself. Re-runs are therefore cheap and mostly offline; pass a scraper's `--refresh` flag to fetch new data, for example the rest of the current season. The merge produces the same output when run twice. Disagreements between sources are logged rather than silently overwritten, and curated fixes live in the three curated files above so they survive re-runs.
