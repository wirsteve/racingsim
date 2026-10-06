# racingsim

An OOTP-style motorsports career and management simulation. You can start a career
at a quarter-mile bullring that only a few thousand fans know, build a regional
reputation, move into touring series, and maybe, if talent, money, timing and the
right people line up, reach national racing.

The world is modelled on **researched** real-world structures (see
[`MOTORSPORTS_RESEARCH.md`](MOTORSPORTS_RESEARCH.md)) and is as real as the data
allows: **real tracks** (with opening/closing years), **real series names** by era
(the Winston Cup in 1996, the Nextel Cup in 2005, the NTT IndyCar Series today),
and a **historical database** of every national NASCAR and open-wheel season since
1995. Start in any year from 1995 to 2026: the national series open with that
season's real teams, drivers and calendar, future stars are kids and prospects at
their real ages, and from there history is yours to rewrite. This is a personal,
unpublished project; see [`LICENSING_IP_REVIEW.md`](LICENSING_IP_REVIEW.md).

## Documents

| Document | Contents |
|---|---|
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | Product requirements with IDs and status |
| [`MOTORSPORTS_RESEARCH.md`](MOTORSPORTS_RESEARCH.md) | Research synthesis: career ladders, case studies, economics, scouting, geography, tracks, simulation assumptions |
| [`docs/research/`](docs/research/) | Detailed research briefs with full source lists |
| [`docs/CAREER_SYSTEM_DESIGN.md`](docs/CAREER_SYSTEM_DESIGN.md) | How research becomes game systems |
| [`LICENSING_IP_REVIEW.md`](LICENSING_IP_REVIEW.md) | IP/licensing notes (personal project — kept as good practice) |
| [`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md) | **The racing data layer:** what was collected, sources used and skipped, validation, confidence, gaps, commands |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Schemas: Series, SanctioningBody, Track, CarClass, CareerStage, CareerPath, Transition, AdvancementFactor, Season, Race, HistoricalDriver/Team, provenance |
| [`docs/OOTP_DEPTH_PLAN.md`](docs/OOTP_DEPTH_PLAN.md) | **The OOTP-depth plan:** OOTP's systems vs ours, the lap-by-lap engine and ratings (phase 1), and the roadmap |
| [`docs/RULES_AND_MONEY.md`](docs/RULES_AND_MONEY.md) | **Cars, rules and money:** class rules, parts, tires, wear and wrecks, real points systems and playoffs, purses — and the evidence behind them |
| [`docs/DATA_REPORT.md`](docs/DATA_REPORT.md) | Generated coverage/confidence report (`python -m racingsim data report`) |
| [`data/CREDITS.md`](data/CREDITS.md) | Data sources and licences |

## Play

**No Python needed.** Download the app for your computer from the repository's
**Actions → Build app** run (artifacts at the bottom of the run page) or from
**Releases** once a version is tagged:

| OS | File | Start it |
|---|---|---|
| Windows | `racingsim-windows.zip` | unzip, double-click `racingsim.exe` (SmartScreen: *More info → Run anyway*) |
| macOS (Apple Silicon) | `racingsim-macos-apple-silicon.zip` | unzip, right-click `racingsim` → *Open* (first time only) |
| Linux | `racingsim-linux.tar.gz` | `tar -xzf … && ./racingsim` |

Your browser opens the game; close the small console window to quit. Saves are kept
in your user folder (`%APPDATA%\racingsim`, `~/Library/Application Support/racingsim`,
`~/.local/share/racingsim`). Instructions also ship in `PLAY.txt`.

From source (Python 3.10+, standard library only):

```bash
python -m racingsim serve        # opens http://127.0.0.1:8765 in your browser
python tools/build_app.py        # build the stand-alone app for this OS (needs: pip install pyinstaller)
```

**Data.** Reference data is compiled into one SQLite database (`data/racingsim.db`)
from the JSON sources in `data/`. It is built automatically on first run from
source and ships prebuilt inside the app. No database server is involved: SQLite
is a file, and it comes with Python.

1. **New Career** — pick the **start year** (1995–2026), your name, home
   state/province, starting age, where you start racing (karting, asphalt ovals,
   dirt, club racing), your family's money, and (optionally) your talent. Money is
   shown in that year's dollars.
2. **The season** — sim week by week, to your next race, or to the end of the
   season. Enter crown-jewel events you're eligible for — they're how local racers
   get seen.
3. **The off-season** — pitch sponsors, hire a coach, or relocate; then pick your
   ride: a team offer (funded, or bring money), your own programme in any series you
   can afford, sit out, or retire.
4. Browse the world: the racing pyramid, every series and team, thousands of
   drivers (scouting reports, not true ratings; real drivers link to Wikipedia),
   371 real tracks on a map, and the news wire. Save/load any time (`saves/` folder).

## Other commands

```bash
python -m racingsim simulate --years 10 --stories      # AI-only world, 10 seasons
python -m racingsim tracks --region WI                  # list Wisconsin venues
python -m racingsim track "Martinsville"                # facts / profile / game ratings
python -m racingsim export-tracks tracks.sqlite         # persist the track database
python -m pytest -q                                     # run the tests
```

## What's implemented

* **Track database**: 1,147 real venues (731 local, 212 regional, 170 national, 34 international;
  USA, Canada, Mexico plus international stops), including historic venues, opening/closing
  years and dormant periods. Sourced facts are kept separate from the game's derived
  profiles and simulation ratings.
* **Racing knowledge layer** (`data/knowledge/` → SQLite): 148 researched series profiles, 40
  sanctioning bodies, 68 car classes, 21 career paths, 71 transitions, 15 advancement factors
  with per-tier weights (used by team owners), economics, and a provenance ledger of 3,000+
  findings from 324 sources. Every number carries a range, a confidence and its sources.
  Browse it in the game's **Encyclopedia**.
* **Touring and grassroots history**: 2,535 seasons and 12,163 races across 101 series:
  ARCA and its East/West lineages, modified tours, CARS, ASA, PASS, Pro Cup, the NASCAR regional
  divisions (All Pro, Southwest, Northwest, Midwest), Dash, World of Outlaws, Lucas Oil, USAC,
  All Stars, ASCS, USMTS, Super DIRTcar, MARS, POWRi and 35 crown-jewel events. Real tours replace
  the generic regional tours for the years they existed. Also 182,760 race-by-race NASCAR results since 1949.
* **Historical database** (`data/history/`, 1995–2026): NASCAR Cup, Busch/Xfinity and
  Truck Series; CART/Champ Car, IRL/IndyCar, Indy Lights, Star/Pro Mazda and USF2000.
  Rosters, standings and calendars, plus 2,500 driver bios. Built from Wikipedia and
  Wikidata with the scrapers in [`tools/history/`](tools/history/).
* **Lap-by-lap racing** (`racingsim/sim/engine.py`): qualifying, tire falloff, fuel windows,
  pit cycles, passing against track difficulty, cautions, superspeedway big ones, restarts,
  stages, box scores (laps led, average running position, passes, driver rating) and
  play-by-play, calibrated against real NASCAR data.
* **OOTP-style driver ratings**: 12 component skills with current/potential, track-type
  splits, personality, scouted 20–80 display; real drivers rated from their actual results.
* **The people around the car**: crew chiefs, spotters, pit crews, technical directors,
  engine builders, driver coaches and medical staff, with ratings, styles and a staff market.
  Morale, rivalries, paybacks with fines and suspensions, team chemistry, and contracts shaped
  by loyalty and ambition.
* **The economic loop**: every team keeps books (sponsors, Cup charters from 2016, owner
  money, purses, merchandise from fan bases, manufacturer support) against running costs, staff
  and salaries; spending buys next year's speed; broke owners sell. Owners set goals and fire
  drivers on the hot seat. **Owner mode**: start, run and sell your own team, and drive for it.
* **Settings and weather**: realism multipliers (crashes, failures, injuries, development
  speed, scouting accuracy, race luck, weather) on a Settings page; rain-outs, rain-shortened
  races, wet road courses and hot days; a development focus and a scouting budget each
  off-season; media power rankings for every series.
* **Long memory**: PAR (positions above replacement, a racing WAR), track-type splits, records
  books, a yearly almanac, awards (Rookie of the Year, Most Popular Driver, Driver of the Year),
  milestones, winners by track and a Hall of Fame.
* **Cars built to real rules** (`data/rules/`): 19 car classes from 126 researched rulebook
  records (track house rules and sanctioning rulebooks), 155 part prices and lifespans, 332
  sources. Chassis, engine packages (built, crate, sealed, spec, claimer — legal by year),
  shocks and tire rules; engines need freshening, tires wear, wrecks cost money, claim rules
  bite. Your **Garage** shows the car, the class rules and a race-by-race money ledger.
* **Real points and purses**: era-correct NASCAR points (Latford, 2004/2007, one-point,
  stages, 2026) with the Chase and elimination playoffs; weekly tracks score like their
  sanctioning body (IMCA, DIRTcar, WISSOTA, Hickory-style, Stafford-style …), with heats,
  DNQs and show-up points; purses from published payout sheets that lag inflation the way
  real weekly purses do.
* **Racing pyramid**: 8 tiers and 43 series templates instantiated onto real tracks (about 800 championships),
  with era names and rungs that appear or go dormant by year:
  weekly divisions at local tracks, regional tours, national ladders in stock cars,
  dirt, open wheel, sports cars, touring cars and club racing.
* **Systemic careers**: thousands of procedurally generated drivers whose
  advancement depends on performance, age, potential, reputation, experience,
  funding, sponsorship, marketability, connections, manufacturer programs,
  geography, available seats, timing, injuries, personality, championships,
  notable performances and scouting exposure.

## Historical mode

* **Start year.** Any year from 1995 to 2026. Tracks that hadn't opened yet, had
  closed, or were idle that year aren't on any calendar. Series carry their period
  names, and manufacturers race only in the years they really did (Pontiac to 2004,
  Dodge 1996–2012, Toyota in NASCAR from 2004).
* **Real grids and calendars.** The national series start with that season's real
  full-time teams and drivers. Ratings come from their actual results around that
  season, measured on the same scale scouts use. Each year's national calendar is
  the real one (Rockingham and North Wilkesboro in 1996, the Roval from 2018).
* **Future stars.** Real drivers whose national careers came later are placed in
  the world at their real age: in karting, legends cars or quarter midgets if they
  are kids, or arriving from overseas racing the year before their real debut. Their
  ceiling reflects what they really achieved, but whether they make it again depends
  on the same money, seats and timing as everyone else.
* **After the start year** the simulation runs free: an alternate history.
* **Money.** Kept internally in 2025 dollars and shown in nominal dollars for the
  year (a $10k youth karting season in 2025 shows as about $3.3k in 1995).
* **Grassroots racing** (local divisions and regional tours) is generated: there is
  no complete public record of every Saturday night feature since 1995.
