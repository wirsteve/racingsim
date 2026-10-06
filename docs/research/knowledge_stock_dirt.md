# Stock car and dirt oval ecosystem: research report

Date: 2026-10-06. Output folder: `knowledge/stock_dirt/`. Every JSON file parses, and the build script checks every id reference (series, class, body, src).

## What's in the folder
| File | Count | Notes |
|---|---|---|
| series.json | 63 Series | from youth (QMA/NASCAR Youth quarter midgets, Bandolero, Legends, micros, oval karts) up to Cup |
| car_classes.json | 35 CarClass | each class has hp, weight, cost and drivetrain where evidence allowed |
| sanctioning_bodies.json | 22 | NASCAR, ARCA, USAC, WRG/WoO/DIRTcar, UMP, IMCA, USRA, INEX, QMA, NASCAR Youth, ASA, CARS, PASS, CRA, POWRi, ASCS, All Stars, High Limit, Lucas Oil, USMTS, SAS, USLCI |
| career_paths.json | 11 paths | asphalt NASCAR ladder; development-program variant; family-funded fast track; self-funded grinder; dirt late model; dirt-to-NASCAR; USAC sprint/midget; WoO/High Limit pro; asphalt modified; dirt modified; veteran step-down/sideways |
| transitions.json | 42 | 6 are computed from repo history (high confidence); the rest are estimates (low) |
| sources.json / ledger.jsonl | 83 sources / 97 findings | |
| unavailable.json | 6 | racing-reference, thethirdturn (rules), jayski (403), arcaracing.com PDFs (403), a Speedway Motors page (no content), and a temporary Wikipedia API rate-limit (backed off, then completed) |

Breakdown of series by level: tier 0: 5, tier 1: 14, tier 2: 16, tier 3: 16, tier 4: 5, tier 5: 5, tier 6: 1, tier 7: 1. Every requested level has at least one entry. Two series have no `game_template`: the NASCAR weekly umbrella and Baby Grand.

## Findings computed from repo history (`src:racingsim-history-analysis`)
Full-time means at least 80% of the season's maximum starts. Cohorts are each driver's first full-time season. The 5-year windows use 1996-2020 cohorts and the 3-year windows use 1996-2022. Birth dates come from Wikidata. Script: `scratchpad/sd_scripts/trans.py`.
- **Trucks to full-time Xfinity or Cup:** 0.28 within 3 years and 0.34 within 5 years. By era: 0.26 (1996-2005), 0.34 (2006-2015), 0.47 (2016-2020).
- **Trucks straight to Cup:** 0.08 within 3 years, 0.19 within 5 years.
- **Xfinity to full-time Cup:** 0.39 within 3 years, 0.47 within 5 years. This stays the same in every era.
- **Results gate:** drivers who won in their first two full-time seasons moved up far more often:
  - Trucks: 0.59 with an early win vs 0.20 without.
  - Xfinity: 0.85 vs 0.27.
- **Age gate (moved up within 5 years, by age at first full-time season):**
  - Trucks: 0.53 at 22 or younger, 0.35 at 23-27, 0.17 at 28 or older.
  - Xfinity to Cup: 0.57, 0.54 and 0.27 for the same age bands.
- **Truck entrants are getting younger.** Median age at first full-time Truck season:
  - 32.5 in 1996-2005
  - 24 in 2006-2015
  - 22 in 2016-2025
  - New Cup full-timers in 2010-2025 have a median age of 25 (p10 21, p90 29).
- **Dead ends:**
  - 68% of Truck full-timers who started in 1996-2015 never held a full-time Xfinity or Cup seat.
  - 50% of Xfinity full-timers never reached full-time Cup.
  - Median full-time tenure is 2 seasons in Trucks and in Xfinity, and 6 in Cup.
- **Step-downs:** of 111 Cup full-timers who left in 1996-2022, 22 ran full-time Xfinity and 19 ran full-time Trucks within 3 years. Median age at the step-down was 38. The median age at a driver's last full-time Cup season is 39.
- **Cup backgrounds:** of 103 new Cup full-timers in 2000-2025, 77 had a prior full-time Xfinity season and 86 had a prior full-time Xfinity or Trucks season.

## Confidence by category
- **High:**
  - NASCAR national series (computed transitions, ages, schedules)
  - Official age rules (NASCAR 2026, ARCA, INEX, IMCA, USAC 15)
  - Official tour economics: Lucas and WoO Late Model points funds, ASA STARS minimums, Whelen Modified Tour payouts, ASCS and USMTS funds, WoO sprint schedule, Knoxville payout
  - Major class specs (super DLM, 410/360, big-block, ARCA car)
- **Medium:**
  - Cost of national dirt late model and dirt modified tours (FloRacing, about 2017 basis)
  - IMCA costs (Gazette)
  - SLM vs LMSC specs and costs (Short Track Scene)
  - Xfinity team budget (Autopian 2025)
  - Driver ladder examples (Wikipedia bios)
  - CARS, PASS, ASA Midwest and Super DIRTcar histories
- **Low (one secondary source or an informed estimate, each noted):**
  - Most local-class season costs and win purses
  - Field sizes for regional series and NASCAR field limits (not fetched)
  - Truck and Cup budgets (agency or press estimates)
  - All advancement shares below the national level
  - All `advancement_drivers` weights for non-NASCAR series

## Main gaps
1. **ARCA, ARCA East/West, CARS, ASA STARS, USAC and WoO have no history data in the repo.** Their advancement rates are estimates. The other agents' touring scrapes in `../touring/` could be used to compute them later.
2. **ARCA points fund and per-race purses** were not obtained, because arcaracing.com blocks fetching. Only snippets were available (about $5k to win at regular races, about $25.7k at Daytona).
3. **Race lengths for several national series, and NASCAR car specs (hp/weight for Trucks, Xfinity and Cup), are informed estimates.**
4. **Thin coverage of some youth and niche classes:** micro sprint and karting costs, Baby Grand, Thunder Roadster, limited dirt late model, SK modified specs, and local win purses.
5. **The Gazette (Iowa) article's year is unconfirmed.** I assumed about 2023.
6. **Possible error in the history file:** Truck series names for 2021-22 may be mislabeled as "Gander RV & Outdoors" (Camping World Truck Series is likely). This is noted in series.json.
