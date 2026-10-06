# racingsim — Project Requirements

racingsim is a deep, text/stat-driven motorsports career and management
simulation in the spirit of sports-management games such as OOTP Baseball.
This document is the canonical list of product requirements. Each requirement
has an ID so code, tests, and design documents can reference it.

Status legend: **[x]** implemented (first pass) · **[~]** partially implemented · **[ ]** not started

---

## R1 — Real-world motorsports research is required

The career ladder must **not** be invented from general knowledge. It must be
derived from active research into how real drivers progress today, and that
research must be recorded in the repository.

| ID | Requirement | Status |
|----|-------------|--------|
| R1.1 | Research real pathways from local/grassroots racing, karting, quarter midgets, Legends, Bandoleros, dirt tracks, asphalt short tracks, regional touring series, club road racing, amateur sports cars, junior open wheel, development series, national touring series, and professional racing. | [x] |
| R1.2 | Research multiple disciplines — at minimum NASCAR/stock car, dirt oval, asphalt short track, IndyCar/open wheel, sports cars/endurance, touring cars, grassroots road racing. Do not assume one ladder. | [x] |
| R1.3 | Understand and document: starting points, typical ages per level, experience before moving up, licensing, how drivers get noticed, how teams discover drivers, sponsorship, family money, pay-driver arrangements, manufacturer development programs, academies, scholarships and shootouts, regional→national translation, running out of funding, sideways moves between disciplines, late bloomers, former pros returning to regional/local racing, and the influence of owners, teams, scouts, manufacturers, sponsors, and agents. | [x] |
| R1.4 | Research real driver career histories as case studies: superstar prospects, traditional ladder climbers, unusual routes, heavily funded drivers, performance-driven drivers, stalled careers, discipline switchers, late arrivals. | [x] |
| R1.5 | Use the observed **patterns** (not one hardcoded ladder) to build career generation and advancement. Many believable pathways must be possible, including ones that never happened in real life. | [x] |
| R1.6 | Maintain `MOTORSPORTS_RESEARCH.md`: ladders researched, real examples, series structures, common ages, funding realities, scouting mechanisms, development programs, track ecosystem, sources, and simulation assumptions. | [x] |
| R1.7 | Research is iterative: research enough for a credible model, implement, test, then improve the model as new information becomes relevant. Do not research forever. | ongoing |

## R2 — Career advancement is systemic

| ID | Requirement | Status |
|----|-------------|--------|
| R2.1 | Advancement depends on interconnected factors: performance, age, potential, reputation, experience, funding, sponsorship, marketability, connections, team relationships, manufacturer relationships, geography, available seats, timing, injuries, personality, championships, notable race performances, scouting exposure. | [x] |
| R2.2 | Winning helps but never guarantees advancement. | [x] |
| R2.3 | A very talented driver can be stuck for lack of funding or exposure. | [x] |
| R2.4 | A less talented driver can advance by bringing sponsorship (pay drivers). | [x] |
| R2.5 | One exceptional performance (e.g., a crown-jewel win, a strong substitute drive) can create a major opportunity. | [x] |
| R2.6 | Development programs can sign 14–17-year-old prospects years before they are ready for the top level. | [x] |
| R2.7 | Veterans can lose national rides and rebuild through regional or local racing. | [x] |
| R2.8 | These stories must **emerge** from the systems, not be scripted. | [x] |

## R3 — A realistic racing pyramid

| ID | Requirement | Status |
|----|-------------|--------|
| R3.1 | Design a pyramid representing the broad structure of real motorsports, informed by research for: number of levels, talent distribution, costs, prestige, ages, field quality, advancement rates, sponsorship needs, team quality, scouting visibility. | [x] |
| R3.2 | Do not need to reproduce every real sanctioning body; use fictionalised series that mirror real structures. | [x] |
| R3.3 | A huge population at the bottom (thousands of fictional racers across local/regional racing) and progressively fewer seats toward the top. Only a tiny fraction ever reach the highest levels. | [x] |
| R3.4 | The player must feel that becoming a professional driver is genuinely difficult. | [x] (validated by funnel tests) |

## R4 — Real tracks

| ID | Requirement | Status |
|----|-------------|--------|
| R4.1 | Use real-world tracks wherever reasonably possible (major venues **and** local/regional venues), U.S. first, then international. | [x] |
| R4.2 | Use tracks in a restrained, informational/statistical way. No licensed assets, no claims of affiliation, only appropriate factual information. | [x] |
| R4.3 | Factual fields: canonical name, city, region/state, country, approximate length, track type, surface, configuration, banking (where documented), active/inactive, opening year (when known), disciplines, series suitability, prestige, attendance potential, weather profile. | [x] |
| R4.4 | Internal **game ratings** derived from research (not presented as official specs): passing difficulty, tire degradation, mechanical stress, brake stress, engine stress, aero importance, mechanical-grip importance, horsepower importance, qualifying importance, caution probability, crash severity, drafting effect, fuel sensitivity, pit-road time loss, wet-weather suitability, racing-line behaviour, setup sensitivity. | [x] |
| R4.5 | Factual fields and game-derived ratings are stored **separately** in the database. | [x] |
| R4.6 | Tracks are persistent entities with stable IDs. | [x] |

## R5 — Local tracks matter

| ID | Requirement | Status |
|----|-------------|--------|
| R5.1 | Include a large number of local asphalt tracks, dirt tracks, short tracks, club circuits, and regional road courses. | [x] |
| R5.2 | A career can start at a small local track, build regional reputation, move into touring competition, and gradually reach national racing. | [x] |

## R6 — Geography

| ID | Requirement | Status |
|----|-------------|--------|
| R6.1 | Where a driver lives affects nearby tracks, available series, travel costs, scouting exposure, regional championships, team relationships, and sponsorship opportunities. | [x] |
| R6.2 | Different home regions (e.g., Wisconsin vs North Carolina vs Indiana vs California vs Florida vs abroad) produce different early-career ecosystems. | [x] |
| R6.3 | Geography is economically and historically meaningful, never an artificial hard restriction. | [x] |

## R7 — Realism without needless licensing dependence

| ID | Requirement | Status |
|----|-------------|--------|
| R7.1 | Use publicly known facts to make the world recognisable; do not depend on proprietary assets or impersonate a licensed product. | [x] |
| R7.2 | When IP/licensing risk is uncertain, choose the safer implementation while preserving realism. | [x] |
| R7.3 | Flag questionable items in `LICENSING_IP_REVIEW.md` and keep building with a safe abstraction. | [x] |

---

## R8 — Playable career mode and UI

| ID | Requirement | Status |
|----|-------------|--------|
| R8.1 | The player creates a driver (name, home region, starting age, starting discipline, family money, optional talent) and starts at a real local track or youth series near home. | [x] |
| R8.2 | Seasons can be simmed week by week, to the player's next race, or to season end; crown jewels can be entered (max 3/season); combines and shootouts can be applied to. | [x] |
| R8.3 | Each off-season the player chooses from genuine team offers (same owner logic as the AI), self-run programmes in any affordable series (with travel costs), staying, sitting out, or retiring; plus once-per-off-season actions (pitch sponsors, hire a coach, relocate). The AI never decides for the player. | [x] |
| R8.4 | Browser UI: dashboard, career/driver pages (scouting reports for others, exact ratings for the player), series (standings, schedule, results, teams, champions), racing pyramid, drivers browser, teams, track database with map, crown jewels, news wire, save/load, light/dark theme, mobile layout. | [x] |
| R8.5 | Standard library only; `python -m racingsim serve`. | [x] |

---

## R9 — Real-world mode and historical database

| ID | Requirement | Status |
|----|-------------|--------|
| R9.1 | Real series names by era (e.g. Winston → Nextel → Sprint → Monster Energy → NASCAR Cup Series; CART/Champ Car; IRL → IndyCar), applied every season. | [x] |
| R9.2 | Real tracks with opening/closing years and dormant periods; historic venues (Nazareth, Pikes Peak, Rockingham's idle years, …) available only in the years they raced. | [x] |
| R9.3 | Choose a start year from 1995 to 2026. The national series start with that season's real teams, drivers and calendar; ratings are derived from real results. | [x] |
| R9.4 | Real future drivers enter the world at their real ages (youth classes, or arriving from overseas before their debut). Their ceiling reflects their real achievements, but the outcome is simulated. | [x] |
| R9.5 | Prices shown in that year's nominal dollars; manufacturers race only in their real participation years. | [x] |
| R9.6 | History data built from Wikipedia/Wikidata with re-runnable scrapers (`tools/history/`); Racing-Reference not scraped (terms). | [x] |
| R9.7 | Grassroots (local/regional) racing remains generated; local tracks and their divisions are real places. | [x] |

---

## R10 — Racing knowledge/data layer

| ID | Requirement | Status |
|----|-------------|--------|
| R10.1 | Normalized schemas for Series, SanctioningBody, Track, CarClass, DriverCareerStage, CareerPath (with detailed steps), Transition, AdvancementFactor, Season, Race, HistoricalDriver, HistoricalTeam (`docs/DATA_MODEL.md`). | [x] |
| R10.2 | Every fact carries provenance and confidence. Unknown precision is stored as ranges or categories, never invented. | [x] |
| R10.3 | Research ledger (source, URL, info, date, reliability, confidence, notes, entities) and a log of sources skipped for access restrictions, each with its replacement. | [x] |
| R10.4 | Source fallback: official bodies, series and tracks, then results archives, Wikipedia/Wikidata, public databases, news, PDFs, secondary sources. Never bypass robots.txt, CAPTCHAs, Cloudflare or rate limits. | [x] |
| R10.5 | Public datasets evaluated for coverage, accuracy, licence, update frequency and usefulness; permitted ones ingested (nascaR.data, Wikidata, OSM). | [x] |
| R10.6 | Ingestion scripts, deduplication and entity matching, idempotent merging with a conflict log, cross-source validation and gap filling. | [x] |
| R10.7 | Multiple career paths across stock car, dirt, open wheel, sports car, modified, sprint/midget and road racing, including crossovers and dead ends. | [x] |
| R10.8 | Career advancement driven by research-weighted factors (talent, results, money, sponsorship, connections, programs, age, marketability …), not "win and advance". | [x] |
| R10.9 | One command re-runs and updates the whole pipeline (`python -m racingsim data update`); the game database is compiled SQLite shipped inside the app. | [x] |
| R10.10 | Stand-alone app for Windows, macOS and Linux with no Python install needed, built on every push. | [x] |

## Known gaps (tracked for the next iteration)

* Agents/managers are modelled implicitly (an awareness boost for drivers with
  means or reputation), not as entities (R1.3, R2.1 "connections").
* International ladders beyond the North American pyramid (overseas drivers arrive as imports) (R4.1, R6.2).
* Sports-car (IMSA/ALMS/Grand-Am) season history; many dirt/short-track seasons are champion-only (see `docs/DATA_PIPELINE.md` §8); the 1995–2006 Star Mazda and several early USF2000 seasons list only the champion.
* Drivers becoming owners/promoters after retirement.
* Calibration deviations recorded in `MOTORSPORTS_RESEARCH.md` §12.

## Traceability

| Area | Where |
|------|-------|
| Research | `MOTORSPORTS_RESEARCH.md` |
| Licensing / IP review | `LICENSING_IP_REVIEW.md` |
| System design | `docs/CAREER_SYSTEM_DESIGN.md` |
| Pyramid & series data | `data/series.json`, `data/disciplines.json` |
| Geography data | `data/regions.json` |
| Track facts (factual layer) | `data/tracks/*.json` |
| Track game ratings (derived layer) | `racingsim/tracks/ratings.py`, `data/track_rating_overrides.json` |
| Career systems | `racingsim/career/` |
| Career mode | `racingsim/game/` |
| Web UI + JSON API | `racingsim/ui/` |
| Historical database | `data/history/`, `racingsim/history/`, `tools/history/` |
| Track history (closures, dormancy) | `data/track_years.json`, `data/tracks/historic_venues.json` |
| Tests | `tests/` |
