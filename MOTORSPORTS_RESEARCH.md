# Motorsports Research: How Racing Careers Actually Work

This document records the real-world research behind racingsim's career,
pyramid, track and geography systems (requirement R1), and the assumptions we
made when turning that research into game systems.

It is a **synthesis**. The detailed research briefs, with every figure and full
source lists (about 440 cited URLs), are in [`docs/research/`](docs/research/):

| Brief | Scope |
|---|---|
| [`stock_car_and_dirt_pathways.md`](docs/research/stock_car_and_dirt_pathways.md) | NASCAR/stock car, asphalt short tracks, dirt ovals: entry classes, age rules, licensing, budgets, development programs, crown jewels, pay drivers, sideways moves, veterans, regional starts |
| [`open_wheel_sports_car_touring_club_pathways.md`](docs/research/open_wheel_sports_car_touring_club_pathways.md) | Karting, the USF/Road to Indy ladder, IndyCar economics, the European ladder and Super Licence, sports cars and FIA driver categorisation, touring cars, SCCA/NASA club racing |
| [`driver_case_studies.md`](docs/research/driver_case_studies.md) | 38 real driver careers across 9 archetypes, champion-promotion statistics, patterns |
| [`pyramid_economics_geography.md`](docs/research/pyramid_economics_geography.md) | Track counts, participation, field sizes, promotion flow, budgets, purses, sponsorship, regional ecosystems, visibility/streaming |
| [`track_dataset_notes.md`](docs/research/track_dataset_notes.md) | How the track database was researched and its known data-quality caveats |

Research was carried out in October 2026 from sanctioning-body rulebooks and
announcements, series and track websites, Wikipedia, and motorsport journalism.
Figures marked *(approx.)* are estimates or ranges; *(unverified)* items could
not be confirmed and are treated as soft calibration only.

---

## 1. The twelve findings that shape the game

1. **There is no single ladder.** North American racing is several connected
   trees (asphalt stock car, dirt, open wheel, sports car/touring, club racing),
   with bridges between them: manufacturer scouts use dirt midgets to find NASCAR
   talent; club racers move into pro sports-car cups; Supercars champions move
   to NASCAR and IndyCar; Cup veterans go back to dirt and late models.
2. **Money gates advancement more than talent does, until the very top.** From
   late models through the NASCAR Truck/O'Reilly level and the whole open-wheel
   ladder, seats are largely bought. Above that, Cup/IndyCar/factory seats are
   performance-scouted, but pay drivers still fill the back of the field.
3. **Winning a feeder title does not buy the next seat.** ~90% of NASCAR
   Xfinity/O'Reilly champions reached full-time Cup within two seasons, but only
   ~35% of Truck champions did, and ~50% of Indy Lights/NXT champions got a
   full-time IndyCar seat the next year. A Truck champion (Moffitt, 2018) was
   replaced by a driver who brought money.
4. **The most common "big break" is a person vouching for a driver** (a star
   driver, owner or executive), then a feeder title, then a substitute/injury
   drive, a standout one-off in good equipment, and shootouts/combines.
5. **Age rules are hard gates.** NASCAR-family series approve drivers by track
   type: ARCA from 15 at short tracks and road courses (17 on speedways, 18 at
   Daytona/Talladega); Trucks 16 (18 on ovals over 1.25 mi); O'Reilly 17 on short
   tracks/road courses (from 2026); Cup 18. USF Juniors 14, USF2000 15, USF Pro
   2000 16. FIA categorisation from 16; Super Licence 18.
6. **Elite prospects move fast; most don't.** Median time from first race to
   top-level start in our case studies is ~14 years (P10 ≈ 7, P90 ≈ 19); median
   age at first top-level start ~22; prodigies arrive at 18–20. Development
   programs typically sign prospects around 16 (range 14–19).
7. **The pyramid is extremely steep.** ~900 US oval tracks (~75% dirt) and an
   estimated 80,000–160,000 people racing competitively per year, but only ~2–4
   new full-time Cup drivers and ~2–4 IndyCar rookies per year. Rough odds for a
   grassroots racer reaching Cup/IndyCar: about 1 in 10,000–20,000.
8. **Grassroots attrition is high and cost-driven** (~12–20% per year at local
   levels; ~5–8% at national pro level).
9. **Dirt racing has a different economy.** Hired dirt drivers are paid 30–40%
   of winnings with no salary safety net; top 410 sprint and dirt late model
   drivers can make a living without ever going to NASCAR.
10. **Sports cars run on paying amateurs.** FIA driver categorisation
    (Platinum/Gold/Silver/Bronze) and Pro-Am lineup rules mean every Pro-Am car
    needs a rated amateur who usually funds most of the car ($1–2M a season in
    GTD). This creates a genuine route for wealthy late starters to reach
    national-level racing.
11. **Geography matters economically, not legally.** Charlotte (≈90% of Cup
    teams) and Indianapolis (IndyCar, USAC, Road to Indy) are industry hubs;
    each region has its own grassroots culture (Wisconsin asphalt super late
    models, Iowa IMCA dirt, Central PA 410 sprints, NC/VA late model stock,
    Northeast modifieds, California dirt/road/karting). Families relocate to
    chase careers (the Gordons to Indiana; prospects to Charlotte).
12. **Careers loop back.** Former pros return to regional and local racing
    (Schrader still racing ~70 events a year at 70; Kenseth at Slinger; Labonte
    on modified tours; Harvick in late models with his son), often as owners,
    promoters and mentors.

---

## 2. Career ladders by discipline

### 2.1 Stock cars and asphalt short tracks

```
quarter midgets / karts (5+)
  → Bandolero (7–16) → Legends (10+)
  → street stock / limited late model (12–16+)
  → Late Model Stock (VA/NC) / Pro & Super Late Models (14–40+)
  → regional tours: CARS, ASA STARS & regionals, ARCA East/West, Whelen/SMART modifieds
  → ARCA Menards (15+) → Trucks (16+) → O'Reilly (17+) → Cup (18+)
```

| Level | Typical age | Typical budget (2025 USD) | Notes |
|---|---|---|---|
| Quarter midgets | 5–16 | $3k–15k | ~4,000 QMA drivers; family hobby |
| Bandolero / Legends | 7–16 / 10+ | $8k–20k (Legends turnkey car ~$18k) | INEX: 3,500+ members, 10,000+ Legends cars built |
| Street stock / limited late model | 14–45 | $4k–30k | local weekly entry divisions |
| LMSC / PLM / SLM weekly | 14–40+ | $50k–250k | VA/NC LMSC ~$150–200k for a front-running season |
| Regional SLM tour | 15–35 | $100k–400k | national-tour SLM ~$250k+ with hauler |
| ARCA national | 15–26 | $0.6M–2M | ~$100k/race at a top team |
| Trucks | 16–30 | $0.8M–3.2M driver-brought | ~$130k/race for a good ride |
| O'Reilly | 17–32 | $1M–5M driver-brought | drivers expected to bring ≥$1M |
| Cup | 18+ | ~$20M per car (team) | drivers paid; charters $20–45M+ |

Patterns: elite 2020s prospects go from first car to Cup in ~4–6 years (2–4 in
late models/dirt, 1–2 ARCA, 0–2 Trucks, 1–2 O'Reilly); typical prospects need 8–12
years and many stall at Trucks/O'Reilly at 22–27; late bloomers (Josh Berry, Cup
rookie at 33; Ty Majeski, Truck champion at 30) arrive through dominant short-track
results plus a patron.

### 2.2 Dirt ovals

```
quarter midgets / junior sprints / outlaw karts (5–12)
  → restricted micro (10) → 600cc micro (12–14)
  → midgets (USAC 15+/16+, POWRi younger) and 360 sprints
  → 410 sprints (WoO, High Limit, PA Posse) or dirt late models (Lucas, WoO LM)
IMCA weekly ladder: sport compact → hobby stock → stock car → SportMod → modified
```

* Midget racing is the main dirt→NASCAR bridge (Toyota's alignment with Keith
  Kunz Motorsports since 2009: Larson, Bell, Abreu, Thorson, McIntosh...).
* 410 sprint and dirt late model careers are often self-contained and long
  (drivers racing into their 40s–50s).
* Crown jewels: Chili Bowl (300–385 midget entries; $20k to win), Knoxville
  Nationals ($195k), Kings Royal ($200k), Dirt Late Model Dream ($100k),
  World 100 ($100k from 2026).

### 2.3 Open wheel

```
karting (5–15) → USF Juniors (14+) → USF2000 (15+) → USF Pro 2000 (16+) → Indy NXT → IndyCar
             ↘ F4 US / FR Americas (Super Licence points) ↘ European F4 → FRECA → F3 → F2
```

| Rung | Budget | Champion scholarship (2025) |
|---|---|---|
| USF Juniors | $120–150k | ~$250k toward USF2000 |
| USF2000 | ~$350–550k *(approx.)* | $405k toward USF Pro 2000 |
| USF Pro 2000 | ~$500–700k *(approx.)* | $546–595k toward Indy NXT |
| Indy NXT | ~$1.2–1.5M | $850k (tests + 2 races incl. Indy 500) |
| IndyCar | $6–15M per car | — |

* **The funding cliff:** the Pro 2000 scholarship covers less than half an NXT
  season; several dominant champions (Sikes, d'Orlando, Porto) stalled for money.
* Stars spend one year per rung; normal drivers 1–3 years and often repeat to win
  a scholarship.
* 2027 IndyCar licensing keys on Indy NXT results (12-start minimum; title or
  top-3 = "competitively qualified"); oval tests and the Indy 500 Rookie
  Orientation Program are separate gates.

### 2.4 Sports cars, touring cars and club racing

```
club racing (SCCA/NASA, novice permit from 14; Spec Miata most popular class)
  → MX-5 Cup (15+) / GR Cup → Carrera Cup / Super Trofeo / Ferrari Challenge
  → Michelin Pilot Challenge (GT4/TCR) / VP Challenge
  → WeatherTech GTD (Pro-Am) → GTD Pro / GTP / WEC (factory)
touring: TC America / TCR → Pilot Challenge TCR; abroad: BTCC, Supercars (Super2/3)
```

* **MX-5 Cup is the clearest amateur-to-pro bridge:** Mazda-powered club
  champions are nominated to a shootout ($350k in prizes in 2025); the MX-5 Cup
  champion receives a $250k scholarship. Connor Zilisch went Spec Miata at 15 →
  shootout → MX-5 Cup → LMP2 class wins at Daytona/Sebring at 17–18 → NASCAR.
* **FIA categorisation:** Bronze = first licence after 30 (performance-assessed);
  Silver = under 30, or started young; Gold/Platinum = pros with significant
  results. Age downgrades at 55/60/65. GTD requires a Silver or Bronze per car
  (Bronze mandate since 2023).
* Club racing is both a pipeline for late starters and a destination for retired
  pros; Runoffs ~400–970 entries; SCCA ~51,600 members (incl. autocross).

---

## 3. Funding realities

| Tier | Family | Personal sponsors | Team/owner | Manufacturer | Prize money |
|---|---|---|---|---|---|
| Youth & local | 80–95% | 5–15% | 0% | 0% | 0–5% |
| Regional short track | 50–70% | 20–40% | 0–10% | 0% | 5–15% |
| In a development program | 0–20% | 20–40% | 30–60% | 10–30% | 5% |
| ARCA | 30–60% | 30–50% | 0–20% | 0–40% | <5% |
| Trucks | 20–40% | 40–60% | 10–30% | 0–30% | 5–10% |
| O'Reilly | 10–30% | 40–60% | 20–40% | 0–20% | 5–10% |
| Cup | 0% | 0% (team sells) | ~100% | via team | via team |
| Dirt pro (hired) | 0% | via owner | owner funds car | engine/brand deals | driver gets 30–40% of winnings |

* **Pay drivers:** typical prices $40–45k/race at a back-marker O'Reilly team,
  $100–150k at a front-runner, plus crash deposits; part-time "race buying" of
  5–15 races; owners swap drivers mid-season for funded ones.
* **Family money buys entry and longevity, not top-team promotion** (Menard: 13
  Cup seasons, 1 win; Stroll; Burton; Deegan).
* **When money runs out:** part-time schedule or smaller team → step down a level
  → back to late models to rebuild → industry role (engineer, spotter, coach,
  crew chief) → switch to dirt where purses pay → retire.
* **Sponsorship sizes:** local $500–10k (often product); regional $10–75k; Truck
  primary $75–300k/season; O'Reilly $250k–1.5M; Cup $5–35M/season. Sponsor
  collapse is the most common reason careers stall (Wallace 2017, Chastain 2018,
  Moffitt 2018, Karam, Hornish).

## 4. How drivers get noticed

* **Crown-jewel events** are dense showcases: Snowball Derby ($50k), Martinsville
  late model stock 300 (~77–90 cars for 40 spots), Oxford 250, Winchester 400,
  All American 400, Slinger Nationals, Chili Bowl, Knoxville Nationals, Kings
  Royal, Dream, World 100, Super DIRT Week, New Smyrna's winter series.
* **Manufacturer scouting:** e.g. Toyota's scouts attend hundreds of races a
  year, rate each driver 1–10 adjusted for equipment and field strength, and see
  a prospect only 3–4 times a season; résumé portals.
* **Visibility tiers:** network TV (Cup/IndyCar/IMSA) → cable (O'Reilly, Trucks,
  ARCA, NXT) → pay-per-view streams of crown jewels and national dirt tours →
  local streams (FloRacing covers 1,000+ events/year; IMCA TV at 54 tracks) →
  weekly tracks with no stream at all.
* **Sim racing:** Byron (iRacing → Legends at 15), Caruth (eNASCAR IGNITE);
  GT Academy (Mardenborough: Le Mans podium within ~3 years of his first race).
* **Combines and shootouts:** NASCAR's development combine (~20 invited aged
  14–26, 6–10 selected, placed at Rev Racing); MX-5 Cup shootout; historic Road
  to Indy karting shootouts ($200k USF2000 scholarship); Team USA Scholarship;
  Chris Griffis test.
* **Relationships:** most case-study careers turned on a specific person
  (Mark Martin → Logano/Kenseth; Jeff Gordon → Johnson; Ganassi → Larson;
  Justin Marks → van Gisbergen; Penske moving drivers between series).

## 5. Development programs

| Archetype | Real-world example | Behaviour we model |
|---|---|---|
| Systematic, analytics-heavy, dirt pipeline | Toyota TD2 + KKM midgets | many slots, signs young, funds steps, releases stalled prospects |
| Team-centric, fewer bigger bets | Chevrolet via Hendrick/JRM/Trackhouse | fewer slots, long commitments |
| Opportunistic, signs proven winners | Ford Performance | moderate aggressiveness |
| Sanctioning-body opportunity program | NASCAR Driver Development (ex-Drive for Diversity) | combine preferring under-funded prospects; funded regional season |
| Factory sports-car juniors | Porsche Junior, Mazda ladder, Toyota GR | sports-car program |

Loyalty is not guaranteed: prospects defect when a pipeline is blocked (Larson
left Toyota for Chevrolet/Ganassi; Deegan left Toyota for Ford).

## 6. Sideways moves, stalls, late bloomers and comebacks

* **Sideways:** dirt → NASCAR transfers well (Gordon, Stewart, Larson, Bell);
  open wheel → NASCAR is mixed (Hornish, Montoya, Patrick, Allmendinger needed
  years); Supercars → NASCAR/IndyCar works for champions (van Gisbergen won his
  Cup debut; McLaughlin); stalled open-wheel drivers pivot to sports cars (~40%).
* **After a stall** (case-study tally): most common is part-time/one-off
  specialist; then sideways move; rebounds happen when a driver (i) keeps racing
  to stay visible, (ii) gets one good result in a better car, (iii) finds a new
  owner willing to take a chance (Chastain, McDowell, Larson, Wallace).
* **Late bloomers:** Chastain's first top seat at 28–29, McDowell's first win at
  36, Berry's Cup debut at 33, Kulwicki's at 30; gentleman sports-car drivers who
  first race in their 30s–50s.
* **Comebacks/returns:** ~30–40% of ex-top-level drivers keep racing regionally;
  ~10–15% run tracks or grassroots teams (Schrader, Kahne, Harvick, Stewart).

## 7. Case studies (summary)

38 careers in [`driver_case_studies.md`](docs/research/driver_case_studies.md).
A selection:

| Archetype | Drivers | What the pattern teaches |
|---|---|---|
| Superstar prospect | Logano, Kyle Busch, Elliott, Byron, Zilisch, Herta | signed 15–17 by owners/manufacturers; top level by 18–20 |
| Traditional ladder | Gordon, Stewart, Bell, Kenseth | 14–20 years; titles at each rung; family relocation |
| Unusual route | Larson, Suárez, Byron (sim), van Gisbergen, Mardenborough, Edwards, Kulwicki | combines, sim, business cards, owner-driver |
| Heavily funded | Menard, Burton, Stroll, Deegan | long careers, few wins, no top-team promotion |
| Performance over money | Chastain, Bell, Larson, Wallace | slower, but reach top seats and titles |
| Stalled / ran out of money | Pigot, Karam, Daly, Kaiser, Moffitt, Askew | scholarships buy one seat, not the second |
| Discipline switchers | Hornish, Montoya, Allmendinger, McLaughlin, Johnson, Grosjean, Cindric | transfer depends on discipline pair |
| Late arrivals | Chastain, McDowell, Edwards, Berry, Majeski | patrons and dominant short-track records |
| Back to grassroots | Schrader, Wallace, Labonte, Sauter, Newman, Kahne, Harvick | owners, promoters, mentors, "boss" opponents |

## 8. The pyramid in numbers

| Level | Real world (approx.) | Game tier |
|---|---|---|
| Youth (QM, karting, Bandolero) | tens of thousands of kids | T0 |
| Local entry (street/hobby stock, Legends, Spec Miata regional) | ~25,000+ regulars | T1 |
| Local premier (LMSC/SLM, IMCA Mod, 360/410 weekly, dirt LM) | ~12,000 | T2 |
| Regional touring (CARS, ASA, SRL, USMTS, ASCS, POWRi, USAC regional, MX-5 Cup) | ~1,500–2,500 | T3 |
| National development (ARCA, USAC national, USF Pro 2000, GT cups) | ~400 | T4 |
| National pro feeder (Trucks, Indy NXT, Pilot Challenge, Lucas/WoO LM) | ~150 | T5 |
| National pro (O'Reilly, WoO/High Limit 410, GTD) | ~100 | T6 |
| Premier (Cup, IndyCar, GTP/GTD Pro) | ~90 | T7 |

Field sizes used: Cup 36 charters + open (38–40), O'Reilly 38, Trucks 36 cap
(~34 average), IndyCar 27, Indy NXT 20–28, WoO sprint 17 full-timers (we model
the 410 pinnacle with WoO+High Limit-like depth), Lucas ~20, IMSA GTD ~15–22 cars.

## 9. Geography

| Region | Grassroots culture | Typical start | Career implications |
|---|---|---|---|
| NC / VA | LMSC, SLM, Legends; NASCAR industry hub (Charlotte ≈90% of Cup teams; Mooresville "Race City USA") | Bandolero/Legends or karts → limited LM → LMSC | best access to NASCAR teams |
| SC / GA / AL / TN / KY | Super late models (asphalt), dirt late models | karts/Legends → SLM or dirt LM | Snowball Derby, Southern tours |
| Florida | winter racing (New Smyrna series in Feb, Snowball Derby in Dec), karting | karts → SLM/PLM | off-season stage for northern racers |
| Wisconsin / upper Midwest | asphalt super late models (Slinger, Madison, La Crosse, Dells), ASA Midwest Tour | karts → weekly SLM → Midwest tour | Kenseth/Majeski path; far from Charlotte |
| Indiana / Ohio / Illinois | USAC sprint & midget, Eldora, Kokomo; Indianapolis open-wheel hub | QM/micros → USAC | dirt→NASCAR bridge and open-wheel access |
| Pennsylvania | 410 sprints (Williams Grove, Port Royal, Lincoln), 358s, dirt LM | micros/358 → 410 | career sprint-car racers; few go to NASCAR |
| Iowa / Plains | IMCA weekly ladder; Knoxville; Boone Super Nationals (1,100+ cars) | sport compact → hobby → modified | self-contained, low scouting |
| MO / OK / KS / TX | dirt LM, USMTS mods, POWRi midgets, Chili Bowl | micros → midgets | Oklahoma midget route (Bell) |
| New York / New England | asphalt & big-block dirt modifieds, Oxford 250, Super DIRT Week | SK Lite → SK → modified tour | career modified racers |
| California | dirt sprints/midgets, SRL/CARS West SLM, road racing, karting | outlaw karts/micros → 410s; Legends → SLM | many stars, but must travel/relocate |
| Pacific NW / Mountain | small car counts; regional SLM; Washington sprints | regional SLM | usually must relocate to progress |

Season windows: north ~Apr–Sep; south ~Mar–Nov; Florida, Arizona, Southern
California race through winter.

---

## 10. Track ecosystem

See [`docs/research/track_dataset_notes.md`](docs/research/track_dataset_notes.md)
for dataset coverage. Summary:

* **312 venues** (99 local, 134 regional, 63 national, 16 international; 45 US states and 8 provinces), 510 source URLs.
* The database stores **facts** (name, city, state/province, country, type,
  surface, length, configuration, turn banking, opening year, active status,
  disciplines, level, coordinates, sources) separately from the game's **profile**
  (size class, prestige, attendance potential, climate/season window, series
  suitability) and **simulation ratings** (17 internal 0–100 ratings).
* Ratings are derived by rules informed by how venue types race (superspeedway
  drafting, flat short-track braking, dirt track evolution, street-circuit walls),
  then hand-tuned for notable venues with written rationale.
* Local tracks are first-class: each suitable local track hosts its own weekly
  divisions in the game, so the real distribution of grassroots venues shapes
  where careers start.

---

## 11. Real-world → game mapping

Game series names are fictional (see `LICENSING_IP_REVIEW.md`). This mapping is
for designers only and must not appear in the game UI.

| Tier | Game series (template key) | Real-world analog |
|---|---|---|
| 0 | Youth Karting / Quarter Midget / Bandolero / Youth Micro Sprint (regional) | club karting, QMA/USAC .25, INEX Bandolero, restricted micros |
| 1 | {track} Street Stock / {track} Hobby Stock / Legends / Club Racing Regional | weekly entry divisions, IMCA hobby, INEX Legends, SCCA/NASA regional |
| 2 | {track} Late Model / Modified / Dirt Late Model / Sprint Car; National Club Racing; National Karting; Formula Junior | LMSC/SLM weekly, IMCA modified, weekly DLM, 360/410 weekly, SCCA Majors/Runoffs, SKUSA/ROK, USF Juniors/F4 |
| 3 | Late Model Tours, Asphalt Modified Tour, Dirt LM Tours, 360 Sprint Tours, Midget Series, Stock Car Development Series, Formula 2000, Spec Roadster Pro Cup | CARS/ASA/SRL, Whelen/SMART, regional DLM, ASCS, POWRi, ARCA East/West, USF2000, MX-5 Cup |
| 4 | National Stock Car Development, Formula Pro, National Midget, National Non-Wing Sprint, GT One-Make Cup, National Touring Car | ARCA, USF Pro 2000, USAC National Midget, USAC Sprint, GR Cup/Carrera Cup, TC America |
| 5 | National Truck Series, Formula Lights, GT4 & Touring Endurance Challenge, National Dirt Late Model Tour | Trucks, Indy NXT, Michelin Pilot Challenge, Lucas/WoO Late Models |
| 6 | Stock Car National Series, Outlaw 410 Sprint Car Tour, GT Endurance Championship | O'Reilly/Xfinity, WoO/High Limit, IMSA GTD |
| 7 | Premier Stock Car Cup, Premier Open-Wheel Championship, Prototype & GT Pro Endurance | Cup, IndyCar, IMSA GTP/GTD Pro |

Crown-jewel events at real venues get fictional names (e.g. the game's
super-late-model classic at Five Flags Speedway, the indoor midget nationals at
Tulsa Expo Raceway).

---

## 12. Simulation assumptions

These are **design values**, derived from the research and tuned so the
simulation reproduces the observed patterns. They live in `racingsim/constants.py`,
`data/series.json`, `data/regions.json` and `data/disciplines.json`.

| Assumption | Value | Basis |
|---|---|---|
| Ability scale per tier (mean) | 30, 37, 44, 52, 58, 64, 69, 74 | talent compresses at the top; seats shrink faster than talent |
| Family racing budget | lognormal, median ≈ $8k, σ = 1.45; adults' budgets grow through their 20s–40s | most racers self-fund cheap classes; a few families fund national programs |
| Season costs | per series, 2025 USD (e.g. mini stock / sport compact $3–3.5k, street stock $8k, limited late model $35k, weekly late model $90k, regional SLM tour $175k, Formula Junior $150k, Formula 2000 $450k, Formula Pro $650k, ARCA-analog $1M, Truck-analog $2.5M, O'Reilly-analog $4.5M, Cup-analog $20M per car) | research budgets (typical/competitive) |
| Team funding share | junior formula/dev series mostly driver-paid; per-series floors rising with team quality: Truck-analog 35%, O'Reilly-analog 50%, IndyCar-analog 60%, Cup-analog 92%, prototype 95%, dirt pro 55–60% | funding mix table (§3); B 3 |
| Owner weights | e.g. ARCA-analog money 0.5; Truck-analog money 0.4; O'Reilly-analog 0.35; Cup-analog performance 0.6; dirt pro performance 0.75 | research A 14.5, B 10.1 |
| Talent bet | owners absorb a driver's funding gap with probability rising with perceived performance, team stature, manufacturer ties and breakout flags | Bell/Larson/Chastain patterns |
| Attrition | 15/16/13/10/8/7/6/5% per year by tier, modified by results, sidelined seasons, injuries, determination; pros wind down from 38, weekly racers from 48 | research F 5.2; A 11 (career local racers into their 60s) |
| Career-investment families & generational talent | 0.3% / 0.15% of real young racers, scaled up by the grassroots representation ratio (≈8 real racers per simulated one at scale 1) | the simulated base is a compressed sample while national seats are 1:1; rare tails must be denser to feed real-sized ladders |
| Development ladders are young | owners penalise drivers older than a series' typical age band; climbing ambition fades after ~26 for touring-level moves | research A 6, B 2.5 (ARCA/USF ages 15–22) |
| Expiring contracts open the seat | stars under 34 are extended; everyone else competes with the market (incumbents keep a relationship bonus) | silly-season dynamics; Moffitt/Heim cases |
| Owners trust results in their discipline | unusual discipline switches are discounted by (1 − transfer) × 20 level points; drivers are open to sideways moves ~10–25% of off-seasons | research C 5.6, 4.5 |
| Budgets grow and racers save | adult hobby budgets grow 0–6%/yr through 50; surplus in a cheaper class is banked toward a bigger car | how weekly racers step up (street stock → limited late → late model) |
| Veterans' grassroots return | 35% of national-level drivers who would retire instead step back to weekly racing | research A 14.11, C 5.7 |
| Development programs | sign around 16 (range 14–19); fund steps; release stalled prospects | research C 5.2, A 14.9 |
| Sponsor collapse | 4%/season local/regional; 15% national | research C 5.4, A 14.7 |
| Substitute breakout | top-quarter finish as a substitute sets a 2-season breakout flag | research C 5.3 |
| Age-by-track approval | under `full_age`, only ovals ≤ 1.25 mi and road courses | NASCAR 2026 rules |
| Pro-Am | one pro + one paying Bronze/Silver amateur per car | FIA categorisation, IMSA GTD rules |
| Skill transfer | e.g. dirt→stock 0.75, open wheel→sports car 0.85, club→sports car 0.90, stock→open wheel 0.45 | case studies §6 |
| Travel | ~$2.25/towed mile round trip + lodging; flying beyond ~900 mi | research F 5.8 |

### Validation targets

The test suite (`tests/test_career_systems.py`) checks that a seeded simulation
reproduces the research's qualitative shape:

* wide grassroots base, narrow top (grassroots > 8× pro tiers);
* fewer than 3% of everyone who ever raced reaches the premier tier, and almost
  none of a fresh cohort gets there within a few seasons;
* realistic age bands per tier;
* pay drivers exist at national level, some below the level of their series;
* feeder champions are sometimes **not** promoted;
* stalled talents and money-driven exits exist;
* development programs sign teenagers;
* national-level drivers arrive through more than one discipline;
* geography shapes entry disciplines (Iowa dirt-heavy; North Carolina stock-car
  heavy) and local racers race near home;
* age rules and Pro-Am category rules are enforced.

### Calibration results (seed 2026, population scale 1.0, 15 seasons)

| Tier | Drivers | Median age | Research reference |
|---|---|---|---|
| 0 Youth | 1,632 | 10 | QM 5–16, karting 5–15 |
| 1 Local entry | 4,382 | 21 | — |
| 2 Local premier | 3,724 | 24 | — |
| 3 Regional touring | 809 | 31 | real ratio T3:T2 ≈ 1:6 (ours 1:4.6) |
| 4 National development | 124 | 30 | ~400 real (several series folded) |
| 5 National pro feeder | 128 | 36 | Trucks 36 cap, NXT 20–28, Pilot Challenge |
| 6 National pro | 88 | 34 | O'Reilly 38, 410 tours ~32, GTD |
| 7 Premier | 97 | 36 | Cup 38, IndyCar 27, prototype 32 seats |

* Population is stable after the first few seasons (≈1,330–1,400 entrants and
  retirements per year at full scale).
* First premier rides: ~10 per year across the three premier series (Cup-analog
  ~3–4/yr, IndyCar-analog ~2–3/yr, prototype ~2–3/yr); research: Cup 2–4, IndyCar
  2–4 rookies/yr.
* Routes into the premier tier: Cup-analog seats come almost entirely from the
  O'Reilly-analog; IndyCar-analog mostly from Formula Lights with occasional GT,
  sprint-car and stock-car crossovers; prototype seats from GT endurance pros.
* Only 0.75% of everyone who ever raced in the simulation reached the premier tier
  (this includes the seeded initial professionals; for drivers who *entered* the
  simulation it is far lower, as tested).

**Known deviations (to improve):**

* First-premier median age is Cup-analog 26 / IndyCar-analog 24 (research ≈22).
* Upper-tier median ages (34–36) are older than reality (≈28–31), mainly because
  sports-car and dirt pro careers skew older and IndyCar-analog veterans hold seats
  while Formula Lights is filled by weaker pay drivers (the funding cliff).
* Tier 2 is ≈0.85× tier 1 (research ≈0.5×): our tier-1 base is thin because the
  track database samples only a fraction of the ~900 US ovals.
* Absolute ability at the top settles a few points below the design scale
  (perceived levels are results-based, so decisions are unaffected).

---

## 14. Historical data (1995 onward)

**Feasibility.** National series are well documented, but grassroots racing is not.
Every Cup, Busch/Xfinity and Truck season since 1995, and every CART/Champ Car,
IRL/IndyCar, Indy Lights, Star/Pro Mazda and USF2000 season, has a Wikipedia
article with:
- an entry list (team, manufacturer, car number, driver, full-time or part-time);
- final standings with starts, wins, top-5s and top-10s;
- the calendar (date, race, track as named that year, city, winner).

Wikidata adds birth dates and birthplaces for about 99% of drivers who have an
article. Racing-Reference has deeper data, but its terms restrict automated
collection, so it was not used. There is no comparable public record for weekly
local divisions or most regional tours, so those stay generated.

**What the data shows that the game now uses.**
- **Track churn is real.** National calendars changed every few years:
  - North Wilkesboro left after 1996;
  - Rockingham after 2004;
  - Nazareth closed in 2004;
  - Kentucky, Chicagoland and Nashville Superspeedway went dormant for years;
  - the Charlotte Roval arrived in 2018 and street courses in 2023.
  
  `data/track_years.json` records corrected opening years and dormant spans so a
  1996 world has no Kansas (opened 2001) or Iowa (2006).
- **Series names are eras, not constants.** Winston → Nextel (2004) → Sprint (2008)
  → Monster Energy (2017) → NASCAR Cup Series (2020). The CART and IRL split ran
  1996–2007 and reunified in 2008. Both are recorded in `data/series_eras.json`.
- **Age at national debut** (Cup regulars 1995–2026). Most debut in their early to
  mid-twenties. The 1990s–2000s "young gun" wave pulled debut ages down and was
  followed by a return to developmental mileage in the 2010s. Prospects are
  therefore placed at their real ages, and their timing is left to the market.
- **The import pipeline.** In open wheel a large share of national drivers were born
  abroad (Brazil, the UK, Australia/New Zealand, Mexico, Japan…) and arrived in
  their late teens or twenties having climbed European or other ladders. The game
  models them as arrivals the year before their real debut rather than as American
  kids in karting.
- **Inflation matters for a 1995 start.** All money is held in 2025 dollars and
  shown in nominal dollars. The CPI-style index is about 0.33 for 1995.

## 13. Open questions / next research

* International ladders (Canada's Pinty's/APC/Maritimes late models, Mexico,
  UK club/BriSCA/BTCC, Australia Supercars/speedway, European junior formula)
  for when we add those regions.
* Quantified effect of streaming/social media on sponsorship value.
* More precise USF2000/Pro 2000 budgets (currently inferred from scholarship size).
* Ownership paths (drivers becoming team/track owners and promoters).
* Weekly-series purse/points economics per region.
