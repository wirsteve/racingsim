# racingsim

An OOTP-style motorsports career and management simulation. You can start a career
at a quarter-mile bullring that only a few thousand fans know, build a regional
reputation, move into touring series, and maybe, if talent, money, timing and the
right people line up, reach national racing.

The world is modelled on **researched** real-world structures (see
[`MOTORSPORTS_RESEARCH.md`](MOTORSPORTS_RESEARCH.md)) and uses **real tracks** in a
restrained, factual way, with fictional series, people, teams, manufacturers and
sponsors (see [`LICENSING_IP_REVIEW.md`](LICENSING_IP_REVIEW.md)).

## Documents

| Document | Contents |
|---|---|
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | Product requirements with IDs and status |
| [`MOTORSPORTS_RESEARCH.md`](MOTORSPORTS_RESEARCH.md) | Research synthesis: career ladders, case studies, economics, scouting, geography, tracks, simulation assumptions |
| [`docs/research/`](docs/research/) | Detailed research briefs with full source lists |
| [`docs/CAREER_SYSTEM_DESIGN.md`](docs/CAREER_SYSTEM_DESIGN.md) | How research becomes game systems |
| [`LICENSING_IP_REVIEW.md`](LICENSING_IP_REVIEW.md) | IP/licensing risk register and safe abstractions |

## Quick start

Requires Python 3.10+ (standard library only; `pytest` for tests).

```bash
python -m racingsim simulate --years 10 --stories      # generate a world, run 10 seasons
python -m racingsim tracks --region WI                  # list Wisconsin venues
python -m racingsim track "Martinsville"                # facts / profile / game ratings
python -m racingsim export-tracks tracks.sqlite         # persist the track database
python -m pytest -q                                     # run the tests
```

## What's implemented

* **Track database**: several hundred real venues (major and grassroots) stored as
  sourced facts, plus separately derived game profiles and simulation ratings,
  persisted to SQLite.
* **Racing pyramid**: 8 tiers and 39 series templates instantiated onto real tracks:
  weekly divisions at local tracks, regional tours, national ladders in stock cars,
  dirt, open wheel, sports cars, touring cars and club racing.
* **Systemic careers**: thousands of procedurally generated drivers whose
  advancement depends on performance, age, potential, reputation, experience,
  funding, sponsorship, marketability, connections, manufacturer programs,
  geography, available seats, timing, injuries, personality, championships,
  notable performances and scouting exposure.
