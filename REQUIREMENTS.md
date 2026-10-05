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

## Known gaps (tracked for the next iteration)

* Agents/managers are modelled implicitly (an awareness boost for drivers with
  means or reputation), not as entities (R1.3, R2.1 "connections").
* International ladders and venues beyond a seed set of 14 circuits (R4.1, R6.2).
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
| Tests | `tests/` |
