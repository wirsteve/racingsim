# Career System Design

How the research in `MOTORSPORTS_RESEARCH.md` is translated into game systems.
The core design rule is from requirement R2.8: **careers are not scripted**.
No code says "a prodigy goes Legends → late models → ARCA → Trucks". Instead the
code models the forces that produce those paths, and the paths emerge from them.

## 1. Architecture

```
racingsim/
  tracks/      factual track records -> derived profile + simulation ratings, SQLite persistence
  world/       geography, the series pyramid, entities (drivers/teams/sponsors/manufacturers),
               procedural generation, the World container
  sim/         statistical race model and season runner (incl. substitutes, injuries, crown jewels)
  career/      scouting/perception, lifecycle (aging, attrition, comebacks, entrants),
               sponsorship market, development programs/scholarships/shootouts,
               the seat market, off-season orchestration
  reports.py   funnel statistics, archetype detection, career stories
  cli.py       `python -m racingsim ...`
data/
  tracks/*.json                  factual layer (sourced)
  track_rating_overrides.json    hand-tuned game ratings with rationale
  series.json                    pyramid templates, shootouts, crown-jewel events
  regions.json                   geography calibration
  disciplines.json               skill transfer between disciplines
```

### The yearly loop

```
season (sim/season.py)
  every series runs its calendar on real tracks
  -> results, titles, purses, injuries, substitute drives, crown-jewel events
off-season (career/offseason.py)
  1. scouting.update_after_season   demonstrated level, exposure, reputation
  2. scholarships consumed / champion scholarships awarded
  3. lifecycle.develop / retirements (incl. veterans returning to grassroots)
  4. sponsorship.update             renew, collapse, new deals
  5. programs.manufacturer_programs / run_shootouts
  6. market.run_market              team seats top-down, then self-run choices
  7. lifecycle.new_entrants         next cohort of kids, teens and adult late starters
```

## 2. The pyramid

Eight tiers (0 youth → 7 premier professional). 40 series templates in
`data/series.json` produce 614 championships on the current track database (505 weekly track divisions, 88 regional series, 21 national series):

| Scope | Instantiated | Examples |
|---|---|---|
| `track` | once per suitable real local/regional track | "{track} Street Stock", "{track} Late Model", "{track} Modified" |
| `region` | once per macro-region with suitable tracks | "{region} Late Model Tour", "{region} Legends Car Series" |
| `national` | once | "Formula Lights Championship", "Premier Stock Car Cup" |

Each template carries the calibrated economics: season cost, field size, purse,
prestige, scouting visibility, equipment weight in the race model, minimum ages,
age-by-track rules, licence prerequisites, scholarships and team structure
(self-run vs team seats, single-driver vs Pro-Am two-driver cars).

Because local series are instantiated per real track, the base of the pyramid is
literally the real map of grassroots racing: a region with many dirt tracks gets
many dirt championships.

## 3. Drivers: hidden truth vs. what the paddock sees

| Hidden (true) | Perceived |
|---|---|
| ability, potential, peak age | `demonstrated` level from results (tier-adjusted, equipment-adjusted) |
| consistency, racecraft, aggression, feedback, adaptability | `exposure` this year (visibility × results, crown jewels, breakouts, hubs) |
| marketability, professionalism, determination | `reputation` (slow-moving) |
| proficiency per discipline | |

Owners, sponsors and manufacturers decide from the **perceived** column. Only
shootouts (controlled tests in identical cars) read true ability, which is why
they are the classic way an unfunded talent breaks through.

## 4. How each R2.1 factor enters the model

| Factor | Mechanism | Code |
|---|---|---|
| Performance | race results → `demonstrated`; titles; wins | `career/scouting.py` |
| Age | min/max ages, age-by-track approvals, development curve, retirement hazard, potential estimates | `world/series.py`, `career/lifecycle.py` |
| Potential | hidden ceiling; scouts estimate it from shown level + youth headroom | `career/scouting.estimated_potential` |
| Reputation | slow paddock standing; sponsor appeal; substitute picks | `scouting.update_after_season` |
| Experience | per-discipline proficiency grows with starts; licence start counts | `lifecycle.develop`, `market._eligible` |
| Funding | family budget (heavy-tailed), personal sponsors, savings, scholarships, program money | `Driver.available_funding` |
| Sponsorship | local/regional/national sponsor market with renewals and collapses | `career/sponsorship.py` |
| Marketability | sponsor appeal, owner weight, exposure | sponsorship + market utility |
| Connections | `team:`, `mfr:`, `target:` relationship strengths that decay | market utility, awareness |
| Team relationships | strengthen while driving for a team; substitutes earn them | `lifecycle.develop`, `season._pick_substitute` |
| Manufacturer relationships | development programs; affiliated teams favour their prospects | `career/programs.py`, market utility |
| Geography | home track choice, travel costs, regional tours, sponsor locality, hub exposure, relocation | `market.season_cost_for`, `choose_self_run`, `_maybe_relocate` |
| Available seats | finite team seats per series; top-down cascade | `market.run_market` |
| Timing | contracts expire at different times; cascades open seats; team equipment drifts | `market._tick_contracts`, `_evolve_teams` |
| Injuries | crash → injury → missed races → substitute drives; career-threatening injuries | `sim/season.py`, `lifecycle.retirements` |
| Personality | determination (persistence, ambition), professionalism (owner appeal, development), aggression (crashes) | throughout |
| Championships | exposure, reputation, scholarships | `scouting`, `programs` |
| Notable performances | crown-jewel wins, substitute "breakout" flag, outperforming equipment | `season._crown_jewels`, `scouting` |
| Scouting exposure | awareness gate per tier: if nobody notices you, you are not a candidate | `scouting.is_aware` |

## 5. The seat market

Each team seat has a **funding gap** = season cost − what the team raises.
Team funding ratios follow research A 14.4: pay seats dominate junior formula
and development series; Truck/O'Reilly-level teams need drivers to bring a big
share; premier teams fund nearly everything; dirt owners fund the car and pay
the driver from purses.

Seats are processed from the top tier down. For each seat the owner:

1. considers drivers he is **aware** of (exposure vs. tier threshold, connections,
   same region/macro region, management),
2. filters by **eligibility** (age, licence tier/starts, discipline experience),
3. checks the driver **would accept** (promotion, better car, or nothing else),
4. scores with the owner's weights (performance, potential, money,
   marketability) plus connections and, for Pro-Am seats, driver category,
5. requires the driver to cover at least half the gap — **unless** the owner
   makes a *talent bet* and finds the money himself (probability rises with
   performance, team stature, manufacturer ties, and breakout flags).

A signing vacates the driver's previous seat, which is pushed back onto the
queue: this cascade is how a single retirement at the top creates three
opportunities further down. A second pass lets owners run under-funded cars
rather than park them (lower equipment).

Drivers without a team seat choose a **self-run** programme: the highest series
they can afford (car budget + travel from home), constrained by self-belief
(results relative to the level) and inertia, with an itch to move up after
2–4 seasons. Kids aging out of youth classes graduate into the oval, dirt or
club disciplines their region favours.

## 6. Talent pipelines

* **Manufacturer development programs** (4 fictional manufacturers with research-
  derived profiles: systematic/dirt-pipeline, team-centric, opportunistic, sports-car).
  They sign aware prospects around age 16, fund part of each next step, boost
  awareness and favour their affiliated teams' seats, and release prospects who stall.
* **Ladder scholarships** for champions (open-wheel ladder, spec roadster, GT cup).
  Vouchers rarely cover the next step fully — the funding cliff is preserved.
* **Shootouts** (junior formula from karting, spec roadster from club racing) and a
  **combine** that prefers under-funded prospects (opportunity program analog).

## 7. Emergent archetypes (what tests look for)

`reports.archetypes` detects the stories the requirements ask for:
prodigy, late bloomer, pay driver, stalled talent, veteran back at grassroots,
discipline switcher, shootout/combine winner, development signee, crown-jewel
winner from local ranks, ran out of money. `tests/test_career_systems.py`
asserts these arise from a seeded simulation rather than from scripted events.

## 8. Career mode and UI

* `racingsim/game/career.py` — the player's driver is an ordinary `Driver` with
  `is_player=True`. The AI market, self-run choices and retirement skip the player;
  everything else (scouting, sponsors, programs, substitutes, injuries) treats the
  player like anyone else.
* The off-season is split (`begin_offseason` → player decisions → `complete_offseason`).
  Team offers are the open seats where the owner's utility for the player beats the
  best sampled AI candidate (minus a small margin), evaluated with a seeded RNG so
  offers don't change on page refresh.
* `racingsim/sim/season.py` runs a 30-week calendar (`SeasonRunner.step`); crown
  jewels sit on fixed weeks; race results are logged for the UI and a news wire is
  posted from races, titles, signings and career events.
* Player levers: crown-jewel entries (max 3, rented car outside your discipline),
  combine/shootout applications (guaranteed invite, merit-based test), sponsor
  pitches, coaching, relocation, and the choice of ride.
* `racingsim/ui/` — a standard-library HTTP server with a JSON API and a vanilla-JS
  single-page app. Ratings shown for other drivers are scouting reports whose noise
  shrinks with exposure; the player's own ratings are exact.

## 9. Known simplifications / next steps

* One season per year without a detailed calendar overlap model (drivers race one
  primary series plus crown jewels and substitute drives; part-time schedules
  are modelled by attendance share).
* Agents are modelled implicitly (`has_manager` awareness boost) rather than
  as entities.
* International expansion: the data model supports any country; series templates
  are North American for now.
* Ownership paths (drivers becoming owners/promoters) are logged as retirements
  today; a future pass should turn them into team/track owner entities.
