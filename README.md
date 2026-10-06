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

## Play

Requires Python 3.10+ (standard library only — nothing to install).

```bash
python -m racingsim serve        # opens http://127.0.0.1:8765 in your browser
```

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

* **Track database**: 371 real venues (100 local, 151 regional, 91 national, 29 international,
  including 59 historic venues such as Nazareth, Pikes Peak and the Milwaukee Mile's
  idle years) stored as sourced facts with opening/closing years and dormant
  periods, plus separately derived game profiles and simulation ratings, persisted
  to SQLite.
* **Historical database** (`data/history/`, 1995–2026): NASCAR Cup, Busch/Xfinity and
  Truck Series; CART/Champ Car, IRL/IndyCar, Indy Lights, Star/Pro Mazda and USF2000.
  Rosters, standings and calendars, plus 2,500 driver bios. Built from Wikipedia and
  Wikidata with the scrapers in [`tools/history/`](tools/history/).
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
