# Race Engine Calibration: Real-World Targets

Research to calibrate the lap-by-lap race engine. It covers NASCAR national
series (Cup, Xfinity/O'Reilly "NXS", Trucks), weekly short-track asphalt and
dirt racing, IndyCar, weather, and research on driver skill.

**Confidence tags:** **[H]** = measured from a full dataset or an official
source. **[M]** = one or two reliable reports, or a computation with known
caveats. **[L]** = an estimate derived from first principles or a single
anecdote; check it before treating it as a hard target.

Last researched: 2026-10-06.

---

## 0. Data sources and method

Two downloadable datasets were analysed directly. Most numbers below are
computed from these files rather than copied from articles.

| Dataset | Content | Source |
|---|---|---|
| `nascaR.data` parquet files (Cup 1949–2026 race 31, NXS 1982–, Trucks 1995–) | One row per car per race: start, finish, laps, laps led, status (running/accident/engine…), per-race Driver Rating (2005+), team | Kyle Grealis' CRAN package, data scraped with permission from DriverAverages.com. Files: `https://nascar.kylegrealis.com/{cup,nxs,truck}_series.parquet` (URL in package source: https://cloud.r-project.org/src/contrib/nascaR.data_3.1.0.tar.gz) |
| SCORE Network NASCAR loop-data season table (Cup 2007–2022, 1,111 driver-seasons) | Season Driver Rating, avg start/mid-race/finish, avg running position, green-flag passes, quality passes, fastest laps, laps in top 15, laps led | https://data.scorenetwork.org/motor_sports/NASCAR_driver_ratings.html (CSV: https://data.scorenetwork.org/data/nascar_driver_statistics.csv) |

**Track-type classification used in computed tables:**
short = paved oval < 1.0 mi; "mile" = 1.0–1.1 mi (Dover, Phoenix, New
Hampshire, Rockingham); intermediate = 1.1–1.99 mi; large oval = 2.0–2.5 mi
non-drafting (Michigan, Fontana, Pocono, Indianapolis); superspeedway =
Daytona, Talladega, and Atlanta from 2022 onward; road = road and street
courses.

**Eras:** 1995–2004 (Gen-4 and late Winston Cup); 2005–2012 (Car of Tomorrow
and start-and-park years); 2013–2021 (Gen-6); 2022–2026 (Next Gen). The
2026 season runs through race 31.

**Blocked sources:** racing-reference.info, driveraverages.com, mrn.com,
frontstretch.com, nascar.com Racing Insights pages and racer.com returned
403 or 429, so this research did not use them.

---

## 1. NASCAR loop data: definitions, formulas, typical values

### 1.1 Definitions [H unless noted]

Loop data comes from transponders on each car and timing wires ("scoring
loops") cut into the track and pit road every few hundred feet. NASCAR has
published it since 2005 and has sent it to teams in real time since 2018.
([NBC/Dr. Diandra on loop passing](https://www.nbcsports.com/nascar/news/dr-diandra-loop-data-passing-kyle-larson-chase-elliott-brad-keselowski-denny-hamlin-brad-keselowski), [SMT](https://smt.com/nascar-will-provide-teams-with-loop-data-in-real-time-this-season/))

| Stat | Definition |
|---|---|
| **Driver Rating** | A formula combining **Wins, Finish, Top-15 Finish, Average Running Position While on Lead Lap, Average Speed Under Green, Fastest Lap, Led Most Laps, Lead-Lap Finish**. Maximum **150** per race. ([Jayski](https://www.jayski.com/2015/05/13/top-10-all-star-driver-ratings/), [SCORE](https://data.scorenetwork.org/motor_sports/NASCAR_driver_ratings.html)) |
| Average Running Position (ARP) | Mean of the car's position at every scoring loop or lap |
| Mid-race position | Position at the halfway point |
| Green Flag Passes | Passes for position under green, counted at every loop crossing. Includes momentary swaps, so totals run high. |
| Green Flag Times Passed | Times the car was passed under green |
| Pass Differential | Green Flag Passes minus Green Flag Times Passed |
| **Quality Passes** | Green-flag passes of a car that is running in the top 15 |
| % Quality Passes | Quality Passes / Green Flag Passes |
| Fastest Laps | Number of laps on which the driver had the fastest lap of the field |
| Laps in Top 15 (and %) | Laps completed while running in the top 15 |
| Laps Led (and %) | Laps led at the start/finish line |
| **Closers** | Positions gained or lost over the **last 10% of the race**. Example: Newman led 2012 with +68 positions over the season. ([Jayski "Loopies" 2012](https://www.jayski.com/2012/12/22/nascars-2012-loopies/)) [M] |
| Speed in Traffic / Speed Early in Run / Speed Late in Run / Fastest on Restarts | Category average green-flag speeds in particular situations (in traffic, at the start of a run, at the end of a run). NASCAR has never published exact thresholds. [L for definitions] |

**Caveat on passes [H]:** Loop passes count every swap at a loop, so they
overstate real passing. At the 2022 fall Bristol race, loop data showed
2,690 green-flag passes against 1,710 in 2021 (+55%). Counting only passes
held longer than a straightaway gave +11.9% for the same drivers. If the sim
reports "green-flag passes", generate them from position swaps at sub-lap
granularity. If it only resolves positions once per lap, apply a multiplier
of about 1.5–3x. ([NBC](https://www.nbcsports.com/nascar/news/dr-diandra-loop-data-passing-kyle-larson-chase-elliott-brad-keselowski-denny-hamlin-brad-keselowski))

### 1.2 The Driver Rating formula

NASCAR (Stats LLC) has never published the point weights. Secondary sources
describe this structure: finish, ARP and average green-flag speed each score
up to 180 points on a sliding scale modelled on the 2004–2006 points table
(1st = 180). Bonuses cover win, top-15, fastest laps, most laps led and
lead-lap finish. The raw maximum is about 900 points, and the result is
divided by 6 to give the 0–150 scale. Treat this as **[M-L]**. It comes from
the DriverAverages explainer as quoted in search results; that page itself
returned 403. (https://www.driveraverages.com/drvavg/nascar-driverratings.php)

**Empirical replacement for the sim [H]:** this was fitted on 19,599 Cup
driver-races from 2013–2026.

* A linear model gives Rating ≈ 103.7 − 1.10·Finish + 3.0·Win + 7.0·Top15
  + 84.9·(share of laps led) − 0.84·Start − 5.9·LedMost (collinear with laps
  led) + 0.4·LeadLap. R² = 0.84 and the residual SD is 11 points; ARP and
  speed account for the residual.
* Mean rating by finishing position:

| Finish | 1 | 2 | 3 | 5 | 10 | 15 | 20 | 25 | 30 | 35 | 40 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mean rating | 127.6 | 114.2 | 109.1 | 100.6 | 86.6 | 76.3 | 64.2 | 55.6 | 48.1 | 45.4 | 41.2 |

* Winners' ratings: p10 = 104.5, median = 129.8, p90 = 148.4. A perfect 150
  happens a few times a season, when a driver dominates from the front.
* **For the sim:** compute the rating as a weighted blend of finish rank, ARP
  rank and green-speed rank (each mapped 180 down to about 30 by position),
  plus bonuses, then divide by 6. Tune it until the table above is reproduced.

### 1.3 Typical season values: full-time Cup drivers, 2007–2022 [H]

Computed from the SCORE dataset. "Full-time" means at least 85% of the
season's maximum laps (n ≈ 500 driver-seasons). Per-race figures assume
36 races.

| Stat | Bottom (p10) | Median | Top (p90) | Best seen |
|---|---|---|---|---|
| Season Driver Rating | 50 | 78 | 100 | 118.9 (Harvick 2015) |
| Avg running position | 28.7 | 16.9 | 10.6 | 7.2 (Truex 2017) |
| Avg finish | 27.2 | 17.5 | 11.8 | 7.3 |
| Avg mid-race position | 28.4 | 17.1 | 10.6 | 5.3 |
| Green-flag passes per race | 67 | 85 | 102 | 125 |
| Quality passes per race | 11 | 39 | 56 | 67 |
| % quality passes | 15% | 44% | 63% | 73% |
| Fastest laps per race | 1.2 | 4.2 | 17 | 38 |
| % laps in top 15 | 4% | 50% | 81% | 93% |
| % laps led | 0% | 0.8% | 9.6% | 28.7% |
| Season pass differential | −212 | +5 | +262 | +661 |
| Wins | 0 | 0 | 4 | 10 |

* **Season leaders:** the top Driver Rating each season is 100–119; the p90
  driver sits at about 98–101; the median full-timer at 73–83.
  Examples: Johnson 2007 = 110.3 (ARP 9.3, 10 wins); Truex 2017 = 116.1
  (ARP 7.2, 8 wins); Elliott 2022 = 99.3 (ARP 11.2, 4 wins). In 2024,
  Larson's average rating was 102.1 at mid-season.
  ([NASCAR.com](https://www.nascar.com/news-media/2024/07/25/handing-out-cup-series-awards-olympic-break/amp/))
* **How the stats relate:**
  * Season rating correlates with ARP at r = −0.98, and Rating ≈ 128.6 − 2.85·ARP.
  * Rating correlates with % laps in top 15 at r = 0.97, % quality passes at
    0.95, fastest laps at 0.82, and pass differential at only 0.59.
  * Average finish correlates with ARP at r = 0.97, and with average start at 0.91.
* **Year-to-year persistence:** season Driver Rating r = 0.85; season average
  finish r = 0.80. Driver and team quality are very sticky between seasons.

---

## 2. Race structure

### 2.1 Race lengths [H]

Median winner's laps and miles per race type, computed from the results data:

| Track type | Cup | Xfinity/NXS | Trucks |
|---|---|---|---|
| Short (<1 mi) | 400–500 laps (~266 mi; Martinsville 400 laps since 2024, Bristol 500, Richmond 400) | 250 laps (~160–190 mi) | 200–250 laps (~108–135 mi) |
| ~1 mile (Dover/Phoenix/NHMS) | 300–312 laps (~318 mi) | 200 laps (~200 mi) | 150–200 laps (~180–200 mi) |
| Intermediate 1.5 mi | 267 laps / 400 mi (Charlotte 600 = 400 laps) | 200 laps / 300 mi | 134–167 laps / 200–250 mi |
| Large oval (2–2.5 mi) | 160–200 laps / 400 mi | 100–125 laps / 250 mi | 75–100 laps / ~190 mi |
| Superspeedway | 188–200 laps / 500 mi (Atlanta 260 laps / 400 mi) | 113–124 laps / 270–300 mi | 100 laps / 250 mi |
| Road course | 68–110 laps / ~220 mi | 68–80 laps / 150–200 mi | 64–73 laps / ~150 mi |

### 2.2 Stage lengths [H; Cup 2025]

Stages were introduced in 2017. Stage 1 and Stage 2 are each about 20–30% of
the race; the final stage is 40–55%. Points go to the top 10 in each stage.
Under current rules a race is official once Stage 2 ends (**[M]**, not
re-verified this pass).
([Yahoo 2025 stage lengths](https://www.yahoo.com/news/nascar-stage-lengths-2025-race-184729728.html))

| Race | Stages (laps) |
|---|---|
| Daytona 500 | 65 / 65 / 70 (200) |
| Talladega | 60 / 60 / 68 (188) |
| Atlanta | 60 / 100 / 100 (260) |
| Las Vegas, Homestead, Texas, Kansas | 80 / 85 / 102 (267) |
| Phoenix | 60 / 125 / 127 (312) |
| Martinsville | 80 / 100 / 220 (400) |
| Bristol | 125 / 125 / 250 (500) |
| Darlington | 90 / 95 / 108 (293) |
| Nashville | 90 / 95 / 115 (300) |
| Pocono | 30 / 65 / 65 (160) |
| Charlotte 600 | 4 × 100 |
| COTA | 20 / 25 / 50 |
| Mexico City | 20 / 25 / 55 |
| Chicago Street | 20 / 25 / 30 |

On road courses, Stage 1 is usually set **shorter than a fuel run**, so teams
choose between pitting before the stage ends and staying out for stage points.

### 2.3 Cautions

**Season-level figures for Cup [H]:**

| Season | Total cautions | Per race | Natural (unplanned) per race | % laps under caution |
|---|---|---|---|---|
| 2001–2004 | n/a | ~8–10 [M] | ~8–10 | 14.0, 14.7, 17.0, 16.5% |
| 2005 | n/a | 10.4 | ~10.2 (368 natural, the 20-year peak) | 16.6% |
| 2008 / 2009 | n/a | 8.8 / 8.4 | n/a | 13.5 / 13.9% |
| 2012 | n/a | n/a | n/a | 10.8% (all-time low) |
| 2018 | n/a | n/a | 4.6 (166 natural, the low) | 13.0% |
| 2021 | 258 | 7.2 | n/a | 14.0% |
| 2022 (Next Gen yr 1) | 302 | 8.4 | 6.4 (229 natural; 73 planned) | 16.8% |
| 2023 | 252 | 7.0 | 5.5 (197) | 14.6% |
| 2024 | 254 | 7.1 | ~5.5 | 15.1% (1,469 of 9,744 laps, ≈41 caution laps per race) |
| 2025 (first 12 races) | 90 | 7.5 (on pace for ~288) | n/a | 17.4% |

Sources: [Building Speed caution % 2001–2025](https://buildingspeed.org/2025/04/04/are-caution-lengths-increasing-in-2025/), [Building Speed 2022 cautions](https://buildingspeed.org/2022/11/24/2022-cautions-by-race-and-type/), [Building Speed 2023 by the numbers](https://buildingspeed.org/2023/12/14/2023-nascar-by-the-numbers/), [NBC Dr. Diandra cautions](https://www.nbcsports.com/nascar/news/nascar-cup-series-cautions-on-the-rise-chase-elliott-brad-keselowski-austin-cindric-denny-hamlin-dr-diandra), [ESPN/Jayski cautions page](https://promo.espn.com/news/stats/story?page=NASCAR-Sprint-Cup-Cautions-and-Crashes).

* **Debris cautions:** peaked at 89 in 2005 (2.5 per race). Since the
  2017 damaged-vehicle policy there have been ≤21 per season. Model "phantom"
  debris cautions as an era-specific knob.
* **Causes in 2023:** accidents 41%, spins 20%, other 17%, planned 22%
  (51 stage breaks plus 4 competition cautions).
* **Spins jumped with the Next Gen car:** 20 in 2021, 60 in 2022, 50 in
  2023. It is harder to catch a slide.

**Caution length in laps [H]** ([Building Speed](https://buildingspeed.org/2021/05/13/caution-lengths-growing-nascar/)):

| Cause | Laps per caution |
|---|---|
| Accident | 6.1 (1990s), 5.4 (2000s), 5.2 (2010s), 5.0 (2018–20), 5.5–5.9 (2024–25) |
| Spin | 4.6–4.9 |
| Debris | 4.7–4.8 |
| Stage end | 6–7.8 |
| Competition caution | 4–4.5 |
| Oil/fluid on track | ~6 (engine 7) |

**Per-track averages, Cup [H]** ([Motorsports-Reference](https://www.motorsports-reference.com/charts/historical/average-cautions-cup/)):

| Track type | Stage era (2017–) | Next Gen | Older modern era |
|---|---|---|---|
| Short: Bristol | 9.1 | 8.4 | 9.7 |
| Short: Martinsville | 8.7 | 6.8 | 10.4 |
| Short: Richmond | 4.9 | 4.9 | 7.7 |
| Short: North Wilkesboro | n/a | n/a | 4.3–5.4 (historic) |
| Short: Bristol dirt | 14.0 | n/a | n/a |
| ~1 mile: Dover | 7.1 | 8.3 | 7.1 |
| ~1 mile: Phoenix | 7.4 | 7.1 | 7.3 |
| ~1 mile: NHMS | 8.5 | 9.6 | 8.1 |
| Intermediate: Charlotte | 10.5 | 12.3 | 8.0 |
| Intermediate: Texas | 9.9 | 12.4 | 8.5 |
| Intermediate: Kansas | 7.9 | 7.7 | 8.2 |
| Intermediate: Las Vegas | 6.1 | 6.3 | 6.4 |
| Intermediate: Homestead | 5.0 | 5.0 | 6.6 |
| Intermediate: Darlington | 7.7 | 7.2 | 8.2 |
| Intermediate: Nashville | n/a | 9.4 | n/a |
| Large oval: Michigan | 7.4 | 8.2 | 5.5 |
| Large oval: Pocono | 6.1 | 8.0 | 6.6 |
| Large oval: Indianapolis | 9.0 | 7.0 | 7.0 |
| Superspeedway: Daytona | 7.1 | 6.2 | 6.1 |
| Superspeedway: Talladega | 6.7 | 4.9 | 5.3 |
| Superspeedway: Atlanta (drafting) | n/a | 9.4 | n/a |
| Road: Sonoma | 4.7 | 4.6 | 5.2 |
| Road: Watkins Glen | 3.9 | 4.0 | 5.2 |
| Road: COTA | n/a | 5.2 | n/a |
| Road: ROVAL | 6.9 | 4.8 | n/a |
| Road: Road America | 3.0 | n/a | n/a |
| Road: Chicago Street | n/a | 7.0 | n/a |

Stage-era and Next Gen counts include two stage-end cautions per race. At
superspeedways, a few large multi-car crashes ("the Big One", typically
10–20 cars) matter more than the caution count.

**Engine guidance:**

* Hazard rate per green lap per car should vary by track type and era. Aim
  for natural cautions per race of about 3–4 on road courses, 4–6 on
  superspeedways, 5–7 on intermediates and ~1-mile ovals, and 5–8 on short
  tracks.
* Add two stage cautions where stages exist.
* Overtime/GWC finishes are common: 13 of 36 Cup races in 2024 went to
  overtime, a record ([NASCAR.com](https://www.nascar.com/news-media/2024/05/07/analysis-2024-shaping-up-as-all-time-nascar-season/amp/)).

### 2.4 Lead changes, leaders, winners [H computed / M reported]

**Number of distinct leaders per race** (drivers who led at least 1 lap),
computed from results data:

| Track type | Cup 1995–04 | Cup 2005–12 | Cup 2013–21 | Cup 2022–26 | NXS 2022–26 | Truck 2022–26 |
|---|---|---|---|---|---|---|
| Short | 8.2 | 8.3 | 7.4 | 7.5 | 6.9 | 4.3 |
| ~1 mile | 8.3 | 9.0 | 7.3 | 7.4 | 7.0 | 5.1 |
| Intermediate | 10.2 | 11.1 | 8.7 | 10.3 | 6.5 | 6.5 |
| Large oval | 10.6 | 10.6 | 8.9 | 11.1 | 7.6 | 5.2 |
| Superspeedway | 11.8 | 18.3 | 15.6 | 17.8 | 10.4 | 10.2 |
| Road | 7.1 | 6.9 | 7.5 | 7.0 | 5.5 | 5.1 |

**Lead changes [M]**, from individual race reports:

* Short tracks: 10–20 typical. Next Gen at Phoenix averaged 12.6; Gen-5b
  was 19.5. Bristol's spring 2024 race on a high-wear tire set a short-track
  record of 56 (outlier).
* Intermediates: about 15–25 (Las Vegas spring 2024 had 24 among 15
  drivers).
* Superspeedways: 30–60. The 2024 Daytona 500 had 41 among 20 drivers;
  drafting Atlanta jumped from the mid-20s to the mid-60s.
* Road courses: 5–12.
* Martinsville spring 2024 had 13 among 8 drivers; Nashville 2024 had 20
  among 9.

Sources: [NBC short tracks](https://nbcsports.com/nascar/news/dr-diandra-short-tracks-stymie-nascars-next-gen-race-car), [Wikipedia 2024 Daytona 500](https://en.wikipedia.org/wiki/2024_Daytona_500), [Wikipedia 2024 Pennzoil 400](https://en.wikipedia.org/wiki/2024_Pennzoil_400), [Wikipedia 2024 Cook Out 400](https://en.wikipedia.org/wiki/2024_Cook_Out_400_(Martinsville)), [Building Speed Nashville](https://buildingspeed.org/2024/07/01/2024-nashville-race-report/).

**Distinct winners per season [H]:**

* Cup: 13.6 (1995–04), 14.5 (2005–12), 13.8 (2013–21), 16.0 (2022–26).
* The most wins by one driver averages 8.0, 7.0, 7.3 and 5.6 for those
  eras. Next Gen spreads wins more evenly.
* NXS: 13.6–15.1 per season. Trucks: 10.5–11.9.

### 2.5 DNFs [H computed from status field]

Mean DNFs per race (all non-"running" statuses) and their causes:

| Era (Cup) | DNF per race | % of field | Crash/DVP | Engine | Other mechanical* |
|---|---|---|---|---|---|
| 1995–2004 | 7.8 | 18% | 3.6 | 2.4 | 4.2 (incl. engine) |
| 2005–2012 | 7.5 | 17% | 3.0 | 1.4 | 4.4 (inflated by start-and-park "brakes/vibration") |
| 2013–2021 | 5.3 | 13% | 3.4 | 0.8 | 1.9 |
| 2022–2026 | 5.1 | 14% | 4.1 | 0.3 | 1.1 |

\*In the computed data, "mech" includes engine.

**DNF by track type, Cup 2022–26:**

| Track type | DNF per race | % of field | Crash DNFs |
|---|---|---|---|
| Superspeedway | 9.6 | 25% | 8.7 |
| Large oval | 6.9 | 19% | n/a |
| Intermediate | 4.8 | 13% | n/a |
| ~1 mile | 4.4 | 12% | n/a |
| Road | 3.3 | 9% | n/a |
| Short | 2.6 | 7% | n/a |

* **Pattern across all eras:** superspeedways have the most DNFs (22–28% of
  the field) and short tracks and road courses the fewest.
* **NXS:** 27% of the field DNF'd in 1995–2012 (more underfunded cars and
  start-and-parks), 22% in 2013–21, 17% in 2022–26.
* **Trucks:** 23–26% before 2022, 15% in 2022–26. Superspeedways run 34–45%
  of the field historically and 23% now.
* **Long-run context:** in 1980 car failures caused more than 4x as many DNFs
  as crashes; by 2000 the two were equal; in 2021 crashes caused about twice
  as many as failures. Crashes are now 60–75% of DNFs, and engines about 11%
  in 2021. ([Building Speed car failures](https://buildingspeed.org/2021/10/29/car-failures-and-dnfs/), [NBC DNFs 2022](https://www.nbcsports.com/nascar/news/chase-elliott-ryan-blaney-martin-truex-jr-denny-hamlin-dr-diandra-dnfs-up-55-in-2022), [Datablends](https://datablends.us/2024/05/23/quantifying-how-nascar-races-have-ended-over-time/))
* **Recent seasons:** 2023 had 167 DNFs (12.7% of starts), 129 of them
  accidents. 2022 had 217.

### 2.6 Starting position, pole, finishing order [H computed]

| Cup era / track | Pole wins % | Pole avg finish | Winner's median start | Win from top 5 | Win from top 10 | Win from >20th | Corr(start, finish) |
|---|---|---|---|---|---|---|---|
| All 1995–2004 | 12.4% | 13.5 | 7 | 46% | 62% | 15% | 0.32 |
| All 2005–2012 | 13.9% | 12.8 | 7 | 46% | 63% | 14% | 0.42 |
| All 2013–2021 | 14.2% | 11.3 | 8 | 42% | 68% | 9% | 0.52 |
| All 2022–2026 | 15.4% | 11.8 | 5 | 50% | 68% | 7% | 0.37 |
| Short (all eras) | 13.0% | 11.5 | 6 | 48% | 67% | 10% | 0.44 |
| Intermediate (all) | 12.5% | 12.1 | 6 | 48% | 67% | 13% | 0.44 |
| Superspeedway (all) | 12.5% | 16.3 | 9 | 35% | 58% | 15% | **0.16** |
| Road (all) | 19.3% | 12.6 | 5 | 52% | 76% | 5% | 0.44 |

* **NXS and Trucks are more predictable:**
  * Pole win rate is 17–21% in NXS and 18–23% in Trucks (~1-mile Truck
    races 28%).
  * 78–83% of winners start in the top 10.
  * Start–finish correlation is 0.5–0.6 (0.22–0.28 at superspeedways).
* **"Fastest car wins" proxies**, Cup 2005–2026:
  * The driver with the **highest Driver Rating wins 54–59%** of races
    (road courses 70–80%, superspeedways 34–41%).
  * The **most-laps-led driver wins ~40%** (road 63%, short tracks ~36%,
    superspeedways 21–33%).
  * NXS and Trucks are higher (top-rated driver wins 60–70%).
* **Next Gen short tracks:** by Dr. Diandra's count, only 25% of
  super-short-track winners started in the top 10 in 2022–23, against 80% in
  Gen-6. On intermediates the share rose to 90%.
  ([NBC](https://www.nbcsports.com/nascar/news/dr-diandra-passing-problems-make-qualifying-more-important-but-only-at-some-tracks))
* **Cars finishing on the lead lap:**
  * Cup: 12–16 in 1995–2004, rising to 22–25 now.
  * Road courses: 27–31.
  * Short tracks: 15–18.

### 2.7 Margin of victory [M]

* Since electronic timing (1993), closest-ever finishes are 0.001 s (Kansas
  2024) and 0.002 s (Darlington 2003; Talladega 2011).
* 2024 averaged 0.222 s over its first 3 races (4th-closest start on record).
  2022 averaged 0.136 s over its first 3. 2023 averaged 1.111 s over its
  first 6.
* **34.5% of Next Gen races (29 of 84) were decided by ≤0.5 s.**
* Typical full-season average MoV: **about 0.8–1.5 s** [L-M]. The
  distribution is heavily right-skewed: many sub-0.3 s finishes (restarts,
  overtimes) plus a tail of 2–8 s blowouts on long green runs.
* IndyCar 2024: closest 0.34 s (Indy 500), largest 9.83 s (Portland).

Sources: [NASCAR.com by the numbers](https://www.nascar.com/news-media/2024/03/09/by-the-numbers-stats-point-to-scintillating-start-2024-nascar-season/amp/), [Open Wheel World](https://www.openwheelworld.net/en/news/16744/By_the_Numbers_The_2024_IndyCar_Series_Season).

---

## 3. Pit stops and strategy

### 3.1 Stop duration (4 tires + fuel)

**Gen-6, five lug nuts, through 2021 [M]**
([Building Speed](https://buildingspeed.org/2021/04/23/pit-stop-costs-the-next-way-to-level-the-playing-field/)):

| Team tier | Average stop | Best |
|---|---|---|
| Elite | 12.5–13.5 s | ~12.5 s |
| Mid-tier | ~15 s | n/a |
| Low-budget | ~19+ s | n/a |

**Next Gen, single lug, 2022 onward [M]:**

* Best average stop per race: 10.22 s (2022), 9.86 s (2023), 9.58 s (2024).
* Typical crews average 10.2–11.9 s; the fastest stops run 9.4–9.8 s.
* Track examples from 2023:

| Track | Best stop | Best average |
|---|---|---|
| Martinsville | 9.68 s | 10.05 s |
| Charlotte | 9.38 s | 10.01 s |
| Talladega | 11.01 s | 11.58 s (fuel-limited) |

* Sources: [NBC Chicago explainer](https://www.nbcchicago.com/nascar-chicago-street-race/how-fast-are-pit-stops-and-much-do-crews-make-heres-an-explainer-ahead-of-the-2024-nascar-chicago-street-race/3479791/), [NASCAR.com pit road stats](https://www.nascar.com/news-media/2023/05/31/pit-road-stats-william-byrons-crew-shines-sets-pace-at-charlotte/).

**Engine guidance:**

* Stop time should be about crew skill + Normal(0, 0.3–0.5 s).
* Add a long tail for errors (loose wheel, dropped lug or jack, uncontrolled
  tire): about 3–6% of stops lose 3–10 s or more, and the most serious incur
  a pass-through penalty. **[L]**
* A two-tire stop saves about 4–6 s with the Next Gen car and about 6 s with
  Gen-6. A fuel-only "splash" is about 3–5 s; fuel is gravity-fed at about
  1 gal/s. **[L]**

### 3.2 Pit-road speed limits and time loss

**Speed limits [M]** ([Sportskeeda 2026 list](https://www.sportskeeda.com/nascar/news-what-pit-road-speed-limit-nascar-everything-need-know)):

| Limit | Tracks |
|---|---|
| 30 mph | Bristol, Martinsville, North Wilkesboro |
| 35 mph | Dover |
| 40 mph | Richmond, Iowa, Gateway, road courses |
| 45 mph | 1.5-mile tracks, Nashville, NHMS |
| 55 mph | Daytona, Talladega, Michigan, Pocono |
| 90 / 45 mph | Atlanta (two zones) |

**Green-flag stop time loss [L, derived]:** pit-road transit at the limit,
plus decel/accel, plus the stop, minus the time to cover the same distance at
race pace.

| Track type | Lap time | Estimated green-stop loss |
|---|---|---|
| Martinsville / Bristol | 15–20 s | 25–35 s, i.e. **1.3–2 laps**. You go a lap down at the shortest tracks. |
| Richmond / Phoenix / Dover | 22–27 s | 28–35 s (~1–1.3 laps) |
| 1.5-mile intermediate | 29–31 s | 30–40 s (~1–1.3 laps) |
| Superspeedway | 46–53 s | 35–45 s, plus losing the draft (~0.8 lap) |
| Road course | 75–130 s | 25–40 s (<0.5 lap) |

* A caution stop costs only about 5–15 s relative to cars that stay out, so
  most strategy pivots on cautions.
* Pit-cycle green-flag stops cost **positions**, not laps, unless a caution
  traps cars on pit road.

### 3.3 Fuel windows

**Formula [H]:** laps = gallons × mpg / track length. The Next Gen fuel cell
holds **20 gal**; the Gen-6 cell held about 18.

**Next Gen mpg [M]** ([Building Speed fuel mileage](https://buildingspeed.org/2025/09/19/fuel-mileage-people-who-know-arent-telling/)):

| Track | mpg |
|---|---|
| Daytona / Talladega | ~6.0 (leader ~5.2, 5th–6th in the draft ~6.1) |
| New Hampshire | 5.3 (≈100-lap window) |
| Iowa | 4.8–5.2 (≈110 laps) |
| Road courses | 3.9–4.4 |

**Resulting green-flag windows:**

| Track type | Laps per tank | Notes |
|---|---|---|
| Superspeedway | ~45–50 | |
| 1.5-mile | ~55–65 [M-L] | Tires usually force stops at 35–50 laps |
| ~1-mile | ~100 | Tire-limited |
| Short tracks | fuel window > tire window | Tires and stages drive stops |
| COTA | ~23–25 | |
| Watkins Glen | ~35 | |
| ROVAL | ~37 | |

* **Fuel-mileage finishes** happen when the last caution falls just inside
  one window from the end, roughly 5–10% of intermediate and large-oval races
  **[L]**. Pocono and Michigan are classic examples.
* Model fuel burn per lap ×1.05–1.15 when leading or in clean air, and ×0.9
  when saving.

### 3.4 Tire falloff

| Situation | Falloff | Confidence and source |
|---|---|---|
| Next Gen, Kansas (intermediate) | ~1.5 s over 30 laps (≈0.05 s/lap) | [M] [NBC](https://www.nbcsports.com/nascar/news/dr-diandra-all-star-race-a-proving-ground-for-softer-tire) |
| Next Gen, Darlington (abrasive) | ~3 s over 30 laps (≈0.10 s/lap) | [M] same |
| Next Gen short-track **option** tire (2024–25) | 2.2–2.3 s over 40–50 laps, about **2x the prime** (~1.1 s) | [M] Goodyear/Mark Keto via [Sportsnaut](https://sportsnaut.com/nascar/is-nascar-about-to-kill-the-best-thing-to-happen-to-short-track-racing) |
| Soft vs prime crossover | ~15–20 laps into a run | [M] |
| Bristol spring 2024 (extreme wear) | Several seconds per run; tires corded in under 50–70 laps if pushed | [M] |
| Day vs night | Fall-off ~1 s over a run on a cool day vs ~2 s on a warm day; daytime track temperature is 30–40 °F hotter | [L-M] weather explainers |
| Gen-6 high-wear tracks (Atlanta old surface, Darlington, Homestead) | Commonly 1.5–3 s over a run | [L] |

**Engine guidance:** model falloff as fast warm-up over 1–3 laps, then a
roughly linear decline of 0.02–0.10 s per lap, with an optional cliff for soft
or high-wear compounds. Scale it by track abrasiveness, track temperature and
driver tire management.

### 3.5 Two tires vs four tires [L-M]

* Two tires buy about 4–6 s on pit road, typically 3–8 positions on a caution
  stop. Over the next run they are about 0.1–0.4 s per lap slower than four.
* Two tires pays off when the race has fewer than about 20–30 laps left,
  when the track has low falloff, or when passing is hard (track-position
  tracks).
* Examples: Pocono 2023; Stewart at Kansas; McMurray (+7 positions, then
  held on).
  ([Frontstretch title only](https://frontstretch.com/2023/07/23/monday-morning-pit-box-two-tires-outlasts-four-at-pocono), [NASCAR.com strategy](https://www.nascar.com/news-media/2015/04/13/strategy-shuffle-pays-off-for-trio-at-texas/amp/))
* At Phoenix, 4-tire green-flag stops led to the win 68% of the time over a
  decade. [L, single source]

### 3.6 Restart and caution rule timeline [H/M]

| Year | Rule |
|---|---|
| ≤2003 | Field raced back to the line when the yellow flew |
| **2003** (Sept, after NHMS) | **Free pass / "Lucky Dog"**: the first lapped car gets its lap back. It is not given to the driver who caused the caution. Initially not awarded in the last 10 laps. ([Wikipedia](https://en.wikipedia.org/wiki/Free_pass_(NASCAR))) |
| Oct 30 2004 | Beneficiary may not pit to take extra fuel advantage under that caution |
| 2004 | Green-white-checkered (one attempt) |
| **June 2009** | **Double-file restarts** with lead-lap cars in front. Lapped cars go to the rear, so the **wave-around** (lapped cars that don't pit move to the tail) is formalised. Free pass now awarded all race. ([Wikipedia 2009 Pocono 500](https://en.wikipedia.org/wiki/2009_Pocono_500), [Jayski wave-around tweak Oct 2009](https://www.jayski.com/2009/10/11/nascar-tweaks-wave-around-rule-for-cup-nationwide-2/)) |
| 2010 / 2016 | Up to three GWC attempts (2010), then "overtime" with an overtime line (2016) [M, recalled; not re-verified] |
| **2017** | **Stages** (top-10 stage points, playoff points); damaged-vehicle policy (DVP) |
| **Jul–Aug 2020** | **Choose rule** at the Bristol All-Star race. Points races from Michigan, Aug 2020, except road courses and Daytona/Talladega. ([NASCAR.com](https://www.nascar.com/news-media/2020/08/06/choose-rule-added-to-majority-of-races-starting-at-michigan/amp/)) |
| 2021 | Choose rule on road courses (reported) [L] |
| **2023** | Choose rule at superspeedways too |
| 2020 / 2023–24 | Wet tires: road courses (Oct 2020 ROVAL); ovals ≤1 mile (exhibition 2023, points race Richmond 2024) |

---

## 4. Lap-time spreads

### 4.1 Qualifying spreads [M, sampled from Wikipedia race pages]

| Race | Entries | P1 | P1→P10 | P1→P20 | P1→P30 | Last |
|---|---|---|---|---|---|---|
| Martinsville 2024 (short) | 37 | 19.718 s | +0.113 (0.57%) | +0.232 (1.2%) | +0.305 (1.5%) | +1.39 (7.0%, an outlier backmarker) |
| Las Vegas 2024 (1.5 mi) | 37 | 29.291 s | +0.289 (1.0%) | +0.301 (1.0%) | +0.504 (1.7%) | n/a |
| Daytona 500 2024 (single-car) | 42 | 49.465 s | +0.444 (0.9%) | +0.633 (1.3%) | +0.761 (1.5%) | n/a |
| Las Vegas 2001 (Gen-4) | 43 | 31.376 s | +0.183 (0.6%) | +0.271 (0.9%) | +0.459 (1.5%) | +0.531 (1.7%) |

* **Rule of thumb:** P1 to P10 is about 0.5–1.0%; P1 to P30 is about 1.5–1.8%.
  The full field spans about 2–3%, plus 1–3 backmarkers at 3–7%.
* The spread is similar across eras because NASCAR rules compress it.
* Race-pace spreads are wider than qualifying, because tire management,
  traffic and dirty air add about 0.5–1% more.
* Sources: [Martinsville](https://en.wikipedia.org/wiki/2024_Cook_Out_400_(Martinsville)), [Las Vegas 2024](https://en.wikipedia.org/wiki/2024_Pennzoil_400), [Daytona 2024](https://en.wikipedia.org/wiki/2024_Daytona_500), [Las Vegas 2001](https://en.wikipedia.org/wiki/2001_UAW-DaimlerChrysler_400).

### 4.2 Race-to-race variance for the same driver [H computed]

**Within-season SD of finishing position**, full-time drivers:

| Driver tier | Cup | NXS / Trucks |
|---|---|---|
| Elite (season avg finish ≤10) | 7.3–10.1 | 7–9.5 |
| Good (10–15) | 10.5–11.3 | 8–10 |
| Mid (15–22) | 9.5–11 | 7.5–10 |
| Back (>22) | 7–9.7 (compressed toward the back) | 5.4–7.7 |

* The overall SD of finish is about 11–12 in Cup and about 9.5–11 in NXS and
  Trucks.
* **Even the best driver's finish has an SD of about 9–10 positions.**
  Bad days (crashes, pit penalties, mechanical failures) are frequent, so the
  sim needs fat-tailed per-race outcomes. Gaussian noise around a skill mean
  is not enough.

---

## 5. Weekly short-track racing: asphalt and dirt

### 5.1 Event structure

**Typical dirt weekly show [M]:**

* Hot laps, then 8-lap heats, B-main if needed (10–12 laps), then features.
* Feature lengths seen at Antioch (CA), June 2025:

| Class | Feature laps | Entries |
|---|---|---|
| IMCA Modified | 20 | 9 |
| IMCA Sport Mod | 20 | 10 |
| IMCA Stock Car | 20 | 10 |
| Hobby Stock | 25 | 10 |
| Pro Stock | 30 | 9 |

* All heats were 8 laps.
  ([Contra Costa News](https://contracosta.news/2025/06/17/clymens-shafer-baca-ryland-smith-win-on-fan-appreciation-night-at-antioch-speedway/amp/))

**Car counts:**

* Strong Midwest weeklies: about 20 crate late models, ~20 modifieds, 18–20
  sport mods, 16–20 stock cars and 12–15 four-cylinders (Adams County,
  2024).
* Weak divisions: about 8 (Revolution Park crate LMs averaged 7.8 in 2025).
* Historic Quincy late-model peaks: 25 cars (2006), about 19–22 cars
  (2005–2009).
  ([Muddy River News](https://muddyrivernews.com/noteworthy/record-car-counts-expected-this-season-as-adams-county-speedway-plans-to-open-sunday/20240426073714/))

**National dirt late model tours [M]:**

* Format: time trials, heats, B-mains (12–15 laps), then a 40–100-lap
  feature with a 24-car starting field.
* Crown jewels: 100 laps.
* Grids are set by passing points over multi-night shows.
  ([Lucas Oil](https://www.lucasdirt.com/press/2019/article/98417))

**Specials (dirt modified example, Bridgeport Danny Serrano weekend) [H for that event]:**

* Format: timed hot laps, a pill or bingo draw sets heats, and the redraw
  number determines the invert in the heat.
* The 60-lap feature counts only green laps.
* Restarts are double-file until 5 laps to go, and the leader chooses lane.
* Cars involved in a caution go to the tail; lapped cars go to the rear.
* There is a wave-around for the first car one lap down.
  ([Bridgeport PDF](https://bridgeportmotorsportspark.com/wp-content/uploads/2026/09/Rules-Procedures.pdf))

**Asphalt late models [M]:**

* South Boston late model stocks (NASCAR Weekly Series) run 100-lap features
  or twin 75s with a 22-car starting field under a handicap system.
  ([NASCAR.com](https://www.nascar.com/news-media/2022/03/21/takeaways-from-south-boston-speedways-2022-opening-day/amp/))
* Super late model touring races are 75–200 laps (CRA/JEGS All-Stars 100,
  ARCA/CRA Super Series 200). Crown jewels run 200–300 laps (Snowball Derby
  300). ([Speed51/STARS](https://starsnationaltour.com/new-information-on-cra-speedfest-at-showtime))
* Weekly super late models: 35–100 laps **[L]**.
* Street stocks and pure stocks: 15–30 laps **[L]**.

### 5.2 Lineups and inverts [M]

* **Heat lineups:** a pill draw, or an invert of points or time.
* **Passing points:** +1 per position gained in the heat, no deductions. The
  points set the feature grid only.
* **Features:** heat winners or top point earners redraw for the front rows,
  with a random invert of 4–8.
* **Handicap systems:** fast cars start at the back (common at weekly asphalt
  tracks).
* **Effect on results [L]:** inverts push the start–finish correlation down
  to about 0.1–0.3, but the fastest car still wins often because features are
  short and fields small. Field-size and invert knobs are the sim's main
  levers for "chaos".
* **Engine guidance [L]:**
  * Weekly dirt features of 20–30 laps: about 0.5–2 cautions, mostly single-
    car spins; the "restart goes to the tail" rule applies to whoever caused
    the caution.
  * DNF rate: about 5–15% (pulled off for damage, flat tires, broken
    suspension).
  * Asphalt late-model 100-lappers: about 3–6 cautions.

### 5.3 Restart rules that differ from NASCAR [M]

* Many local tracks use single-file restarts with lapped cars to the rear.
* Some run double-file until X laps to go.
* Cautions often do not count as laps (green-lap-only features).
* Many tracks impose a time limit or a cap on the number of cautions.

---

## 6. IndyCar

**Race lengths [H]:**

* Road and street courses: about 75–110 laps, 1h45–2h.
* Short ovals: 250 laps (Iowa 0.894 mi, Milwaukee 1 mi), ~2 h.
* Gateway: 260 laps.
* Indianapolis 500: 200 laps / 500 mi, ~3 h (167.8 mph average in 2024).
* Lowest 2024 average speed: Detroit street, 78.3 mph.
  ([Open Wheel World](https://www.openwheelworld.net/en/news/16744/By_the_Numbers_The_2024_IndyCar_Series_Season))

**Pit stops [M]:**

* Road and street: 2–3 stops (Road America is usually 3).
* Short ovals: 3–5.
* Indy 500: 6–7 among contenders (one 2023 crew made 8).
* Stop time: about 6–8 s for 4 tires + fuel (fuel-limited). The 2024 tank
  holds 18.5 gal.
* No refuelling during the first laps of a caution until the pits open.
  Strategy hinges on full-course yellows.
  ([Yahoo/AOL on Indy 500 stops](https://www.aol.com/why-indy-500-pit-stops-061910164.html), [Motorsport.com Road America](https://us.motorsport.com/indycar/news/road-america-needs-yellows-to-vary-strategies-says-edwards-791796/2986649/?nrt=86))

**Push-to-pass [H]:**

* Road and street courses only, never ovals.
* St. Pete, Detroit, Laguna Seca and Thermal: 15 s per push, 150 s total.
* Long Beach, Barber, IMS road course, Road America, Mid-Ohio, Toronto and
  Portland: 20 s per push, 200 s total.
* About +50–60 hp.
* The hybrid (since July 2024 at Mid-Ohio) adds up to 425 kJ per lap of
  driver-deployed boost. P2P plus hybrid gives about +120 hp, taking cars
  past 800 hp.
  ([Fox Sports](https://www.foxsports.com/stories/motor/indycar-push-to-pass-rule-2024-controversy), [IndyCar.com hybrid](https://www.indycar.com/News/2024/05/05-14-Hybrid-Debut))

**Cautions [M-L]:**

* Permanent road courses: often 0–3. 2025 opened with a run of caution-free
  races, and the IMS road course went more than 400 laps without a yellow.
* Street courses: 3–8 (Detroit 2024: 8).
* Short ovals: 1–5 (Iowa 2024: 1–2, Milwaukee: ~4).
* Indy 500: 5–9 (2024: 8).
* Most of the season lead changes come from the Indy 500 (48 in 2024).
  Iowa 2024 race 1 had only 1 lead change.
* 2012 data: 20 full-course cautions in 8 road/street races (2.5 per race).
  14 of the 20 were for contact.
  ([IndyCar.com 2012 notes](https://www.indycar.com/news/2012/08-august/8-8-notes-caution-free-races-reach-two), [Frontstretch 2025](https://frontstretch.com/2025/05/04/indycars-caution-free-streak/), [Yahoo](https://sports.yahoo.com/article/indycar-surprisingly-sees-first-caution-223651324.html))

**Competitive structure:**

* 7 different winners in each of 2023 and 2024; 27 drivers led at least one
  lap in 2024.
* The champion (Palou) won with 2 wins and 13 of 17 top-5s.
* Pole wins are frequent on road and street courses: about half of 2024
  road and street winners started 1st or 2nd [M].

---

## 7. Weather

**NASCAR rain [H/M]:**

* Ovals traditionally stop for rain. Wet tires are now allowed on **road
  courses and ovals ≤1 mile**:
  * Road courses: Cup from the Oct 2020 ROVAL. Xfinity and Nationwide used
    wets earlier, e.g. Montreal 2008 [L recall].
  * Ovals: North Wilkesboro All-Star heats in 2023 (exhibition); Richmond
    2024 was the first points race (damp opening stage); NHMS 2024 ran
    82 wet laps, the oval record.
    ([NBC rain history](https://www.nbcnewyork.com/news/sports/nascar-rain-racing-history-rules-weather-tires/5505261/))
* **Rain impact:** in 2020, 9 of the first 15 Cup races were affected
  ([Beyond the Flag](https://beyondtheflag.com/2020/06/30/nascar-rain-interfered-60-2020-cup-races/)).
  * Full postponements: Daytona 500 only twice ever (2012, 2024).
  * Rain-shortened 500s: 1965, 1966, 2003, 2009.
  * Suggested sim rates **[L]**: ~5–10% of oval races postponed to the next
    day, ~3–6% shortened (official after Stage 2 or past halfway), and
    ~15–30% delayed.
* **Wet road racing:** grip falls about 15–25% and lap times rise 10–20%;
  driver skill spread widens. Bell et al. 2016 found team effects shrink in
  the wet (see §8).

**IndyCar:** races in the rain on road and street courses with Firestone
rain tires; does not race ovals in the wet. The 2024 Indy 500 was delayed
4 h by storms.

**Heat:**

* Hot, sunny track temperatures (+30–40 °F over night) cut grip, raise tire
  wear and roughly double the fall-off over a run. Lap times are typically a
  few tenths to 1 s+ slower **[L-M]**.
* Night races and cool days are faster with less fall-off.
* Practice-to-race temperature changes cause "missed" setups. Model a
  setup-error term that grows with |ΔT|.
* Sources: [Frontstretch night/day](https://frontstretch.com/2019/05/17/night-and-day-difference-for-nascar), [ClickOrlando weather](https://www.clickorlando.com/weather/2024/02/15/weathering-the-track-how-the-weather-affects-race-day/).

---

## 8. Driver skill, team and luck: what research shows

### 8.1 Formula 1 [H]

* **Bell, Smith, Sabel & Jones (2016)**, *J. Quant. Anal. Sports* 12(2),
  F1 1950–2014, cross-classified multilevel model.
  * **The team accounts for ~86% of the variance** in points
    (driver ~14%), and team effects are growing over time.
  * Team effects shrink in **wet weather and on street circuits**, where
    driver skill matters more.
  * ([RePEc](https://ideas.repec.org/a/bpj/jqsprt/v12y2016i2p99-112n3.html), [Plymouth](https://researchportal.plymouth.ac.uk/en/publications/formula-for-success-multilevel-modelling-of-formula-one-driver-an/))
* **van Kesteren & Bergkamp (2023)**, Bayesian rank-ordered logit model,
  2014–2021.
  * **Constructor ~88%** (89% CI 77.5–94.5%), driver ~12%.
  * Random-effect SDs: constructor 1.63, constructor-year form 0.73,
    driver 0.54, driver-year form 0.35.
  * ([PMC10660124](https://pmc.ncbi.nlm.nih.gov/articles/PMC10660124/))

### 8.2 NASCAR [H computed; M literature]

**Variance decomposition** of finishing positions for full-time drivers.
The share of variance is between driver-season means; the remainder is
race-to-race noise ("luck" plus track fit). The "team-season" figure groups
an organisation's cars together.

| Series / era | Between driver-seasons | Between team-seasons |
|---|---|---|
| Cup 1995–2004 | 22% | 16% |
| Cup 2005–2012 | 31% | 25% |
| Cup 2013–2021 | 33% | 29% |
| **Cup 2022–2026 (Next Gen)** | **16%** | **12%** |
| NXS 2013–2021 | 46% | 41% |
| NXS 2022–2026 | 23% | 20% |
| Trucks 2013–2021 | 35% | 31% |

**What this means for calibration:**

* **About 65–85% of single-race finishing variance is within-season noise.**
  Season-level skill and equipment explain only 15–45%, depending on series
  and era.
* Spec cars (Next Gen) reduce the between-driver share.
* Most of the between-driver variance tracks the team: equipment correlates
  with talent because good drivers land in good cars.
* Year-to-year persistence is high (season Driver Rating r = 0.85). A useful
  target: **true ability (car + driver) SD ≈ 0.4–0.7 of the per-race noise
  SD**.

**Literature:**

* Allender (2008, *Sport Journal* / *JBER*), 2003 Cup data. Prior-year
  points, practice speed, team size (number of team members) and a
  "changed teams" flag were the most consistently significant predictors of
  finish. Qualifying speed and pole were significant in only about half of
  races. Experience mattered; rookie status rarely did.
  ([Sport Journal](https://thesportjournal.org/article/do-reliable-predictors-exist-for-the-outcomes-of-nascar-races/), [JBER](https://clutejournals.com/index.php/JBER/article/view/2403))
* Crew chiefs and pit crews: the 2021 Gen-6 pit stop gap of 1–1.5 s
  (mid-tier) to 4+ s (low-budget) per stop is a direct equipment and
  personnel effect worth several positions per race.

### 8.3 Age curves [M]

* **NASCAR:** among retired modern-era drivers with 10+ Cup wins, success
  **peaks around age 34**, declines meaningfully by 40, and is nearly gone by
  45. By the end of their age-44 season, drivers had 93.4% of career wins,
  92.6% of top-5s and 91.3% of top-10s. Recent counter-examples include
  Hamlin, still winning at 43–44, and Harvick.
  ([NASCAR.com 2025](https://www.nascar.com/news-media/2025/07/24/this-is-one-of-hamlins-best-title-chances-yet-how-many-more-will-he-get/), [Kyle Petty analysis via OvalInsider](https://www.ovalinsider.com/nascar-news/nascar-denny-hamlin-prime-45-kyle-petty-analysis-nashville-1085061/))
* **F1:** an inverted-U age–productivity profile with a **peak at 30–32**
  (Castellucci, Padula & Pica, CSEF WP 226, F1 1991–99, with driver, team and
  match fixed effects).
  ([CSEF](https://www.csef.it/WP/wp226.pdf))
* **Engine guidance [L]:**
  * Raw speed and reaction peak at about 25–30.
  * Racecraft, tire saving and consistency keep improving to about 35.
  * Net peak by series: 30–32 open wheel; 32–36 stock car.
  * Decline: about 1–2% of skill per year after 38, accelerating after 43.
  * Dirt and short-track weekly racers often stay competitive into their
    40s and 50s, because experience matters and fitness demands are lower.

### 8.4 Injury rates [M]

* **Circuit racing** (Fuji Speedway, 1996–2000): about **1.2 injuries per
  1,000 competitors per race** for single-seaters and **0.9** for saloon or
  touring cars ([BJSM](https://bjsm.bmj.com/content/38/5/613)).
* **Concussion:** incidence in motorsport studies ranges 6–25%, and
  1.6–17.6% in professional series depending on study length
  ([PMC6094153 review](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6094153/)).
* **NASCAR since 2001:** HANS, SAFER barriers and the CoT, Gen-6 and Next Gen
  cars made fatalities extremely rare, and crash rates "began declining"
  after 2001 (Datablends).
* **Next Gen:** concerns about stiff rear impacts caused concussion absences
  (Kurt Busch 2022, Alex Bowman 2022). NASCAR revised the chassis for 2023.
* **Engine guidance [L]:**
  * Per crash involvement: ~1–3% chance of a race-missing injury in a
    national-series stock car. Superspeedway and high-speed rear impacts
    are higher.
  * Local short track: lower speeds, but older safety equipment.
  * Open wheel: higher severity; leg and foot injuries on oval wall hits.
  * Typical absence: 1–6 races for concussion; up to a season for
    fractures.

---

## 9. Calibration checklist for the engine

Priority targets, in order:

1. **Start–finish correlation** of about 0.35–0.55 in Cup (0.1–0.2 at
   superspeedways) and 0.5–0.65 in NXS and Trucks.
2. **Pole wins** 12–20%; **winner from the top 10** 60–80%; winner from
   outside the top 20 5–15%.
3. **Distinct leaders per race:** 7–8 short, 9–11 intermediate, 15–18
   superspeedway, ~7 road.
4. **Cautions per race:** 7–8 including stage cautions (Next Gen). That is
   about 15% of laps, at 5–6 laps per caution.
5. **DNF** 13–14% of the field (Cup Next Gen), 70–80% of them crashes.
   Superspeedways about 25%; short tracks and road courses 7–9%. For the
   1995–2004 era, raise the total to ~18% with about half mechanical.
6. **Per-driver within-season finish SD** of about 9–11. The season-mean
   share of variance should be 15–45% depending on series and era.
7. **Driver Rating table** by finishing position (§1.2). The season leader
   should reach about 100–118 and the median full-timer about 75–80.
8. **Season distinct winners:** Cup 13–17, Trucks 10–12. The top driver
   should win about 5–8 races.
9. **Pit stops** of about 10–11 s (Next Gen) or 12.5–15 s (Gen-6). A green
   stop costs about 1 lap on ovals of 1.5 mi or less.
10. **Qualifying spread:** P1 to P10 about 0.6–1.0%; P1 to P30 about 1.5–1.8%.

## 10. Open gaps

* Per-race lead-change counts by track type across eras. Racing-Reference has
  them but blocks automated fetching.
* Exact Driver Rating weights and the official definition of speed in
  traffic.
* Systematic IndyCar caution tables by track type.
* Weekly short-track caution and DNF rates. These need a sample of
  MyRacePass result sheets.
* Measured green-flag pit-road loss by track (Racing Insights data).
