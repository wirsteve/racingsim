# OOTP-depth plan

Goal: a racing career sim as deep as Out of the Park Baseball. Research behind this plan:

- [`research/ootp_mechanics.md`](research/ootp_mechanics.md): every OOTP system, what is simulated, why it feels deep.
- [`research/race_engine_calibration.md`](research/race_engine_calibration.md): the real-world numbers the race engine is tuned to.

## The principles we are building to

From the research. These are OOTP's design rules, translated to racing.

1. **Hidden truth, scouted perception.** Every driver has true ratings. You see a scout's noisy estimate.
2. **Current and potential, both moving.** Potential is a forecast, not a promise.
3. **Atomic simulation, emergent stats.** Laps produce every number; stats and ratings agree without being the same thing.
4. **Each rating has a narrow, legible effect.** Tire management saves tires; restarts gain spots on restarts.
5. **Value is relative to context.** Track-type splits; stars relative to the series level.
6. **The environment multiplies.** Track character, era, weather, level of competition.
7. **People drive outcomes.** Crew chiefs, spotters, pit crews and engine builders with ratings and styles.
8. **Personality, morale and chemistry.** Drivers want money, a good car, a role, to win, loyalty.
9. **The real rules constrain you.** Contracts, sponsors, charters, licences, class rules.
10. **A closed economic loop.** Results bring fans, fans bring sponsors, sponsors bring speed.
11. **Your career is a game too.** Reputation, goals, getting fired, job offers.
12. **A living world.** The AI signs, fires, folds and promotes; the news tells the story.
13. **Long memory.** Records, almanac, Hall of Fame, career logs.
14. **Everything is a setting.** Randomness, injuries, development speed, scouting accuracy.
15. **Weighted randomness, never guarantees.** You get levers, not certainties.

## Where racingsim stands

| System | OOTP | racingsim | Status |
|---|---|---|---|
| Game engine | Pitch by pitch, park factors, weather, box scores, play-by-play | **Lap-by-lap engine** (`sim/engine.py`): qualifying, tire falloff, fuel windows, green and caution pit cycles, passing vs track difficulty, crashes and big ones, mechanical failures (car model), free pass, restarts, stages, box score, play-by-play. Calibrated to real NASCAR data. Weekly local divisions use the fast result-level model, as OOTP does for leagues you don't watch | ✅ Phases 1 and 6: race-day weather (rain-outs at weekly tracks, rain-shortened ovals, wet road courses, hot days) |
| Ratings | ~30 ratings, current/potential, L/R splits, OVR/POT stars | 12 component skills (current/potential), 5 track-type experience and talent splits, OVR/POT on 20–80 | ✅ Phase 1. Stars relative to series level still to come |
| Ratings from history | Historical stats → ratings | Real NASCAR drivers rated from race-by-race results: qualifying vs race, laps led, positions gained, crash rate, track specialties | ✅ Phase 1 |
| Scouting | Scout director ratings, budget, accuracy by age/region, league baseline | Error shrinks with the driver's exposure; 5-point steps; personality shown only as impressions | ✅ Phase 6: a scouting budget (none, standard, extended, elite) and media power rankings as the public baseline. No individual scouts yet |
| Development and aging | Weighted random, coaching, playing time, personality, focus, development lab | Ability plus per-skill development: seat time, work ethic, intelligence; physical skills fade, savvy keeps growing; track types learned from laps; off-season coaching | ◐ No competition-level effect, focus sliders or off-season programs yet |
| Personality | 6 traits; morale; chemistry | 7 traits; morale (race by race and season); rivalries from wrecks, paybacks with points, fines and suspensions; team chemistry; loyalty, desire to win and morale in contract decisions | ✅ Phase 3. Greed waits for negotiation (Phase 5) |
| Injuries | Types, body areas, proneness, re-injury, trainers | Races out, severity, durability; team medical staff speed recovery and soften injuries | ◐ No injury types, concussion history or racing hurt |
| Stats | Every stat, splits, logs, WAR | Per race: start, laps, laps led, status, ARP, passes, quality passes, fastest laps, pits, driver rating. Per season: poles, laps led, DNFs, average start/finish, rating, winnings, points, track-type splits and PAR (positions above replacement, a racing WAR); records books by series; a yearly almanac; winners by track; a Hall of Fame | ✅ Phase 4. Split by season and opponent strength still to come |
| Team management / staff | Coaches, scouts, trainers with ratings | Crew chiefs, spotters, pit crews, technical directors, engine builders, driver coaches, medical: ratings, styles, contracts, aging, firings, a staff market; retired drivers become staff; the player hires their own crew | ✅ Phase 2. Scouts come in Phase 6 |
| Transactions | Trades, FA, contracts, options, waivers, draft | Silly-season market, pay seats, salaries, contract years, development programs, shootouts | ◐ No negotiation, bonuses, release clauses, development loans or buyouts |
| Finances | Gate, media, merch, budgets, owner | The player's own car: real costs, purses, points funds; sponsors. Every team keeps books: sponsors, Cup charters (2016+), owner money, pay drivers, purses, merchandise, manufacturer support against running costs, staff and salaries; spending sets next year's equipment; broke owners sell. Driver fan bases | ✅ Phase 5. No gate or media money for tracks |
| Career / GM | GM mode, reputation, firing, job offers | Driver career; reputation; team offers; owner goals, job security and firing; owner mode (start, run and sell a team, drive for it) | ◐ No crew-chief career |
| League / history | Historical leagues, expansion | 1995–2026 real series, rosters, calendars, 12k+ touring races, real rules and points by era | ✅ Exact replay mode still to come |
| News / storylines / awards | Inbox, storylines, awards, milestones | News wire; Rookie of the Year, Most Popular Driver, Most Valuable Driver, Driver of the Year; first wins and start/win milestones; Hall of Fame inductions; rivalries and paybacks | ◐ No multi-season storylines yet |
| Settings | Everything tunable | World size, start year; realism multipliers for crashes, failures, injuries, development speed, scouting accuracy, race luck and weather, changeable any time | ✅ Phase 6 |

## Roadmap

Each phase is playable on its own and goes in as its own pull request.

### Phase 1: Driver ratings and the race engine ✅ (this PR)

- OOTP-style ratings: component skills, track types, personality, scouted display.
- Real drivers rated from their results.
- Lap-by-lap engine with box scores and play-by-play; real laps led and stage points.
- Calibrated against real data. Remaining calibration gaps:
  - The strongest Cup entry can still win 9–14 races a season (real: 6–9). This is partly world composition: the best driver also has the best team.
  - Coarse-step AI races under-count lead changes.
  - Laps down come from time gaps: green-flag stops and slow cars lose laps; the free pass gives one back.
    - In a 36-car Cup field, lead-lap finishers average about 11 at Martinsville and 17 at Charlotte. Both are in the real range.
    - Talladega averages 16 lead-lap finishers, low against the real 20–28. Our green-flag pit cycle there costs more laps than the draft would.

### Phase 2: The people around the car ✅

- **Staff entities with ratings and styles:**
  - crew chief (strategy aggression, setup, two-vs-four-tire calls);
  - car chief / engineer (setup quality → per-race setup variance);
  - spotter (wreck avoidance, restarts);
  - pit crew (stop mean and variance, error rate);
  - engine builder (power vs reliability → engine quality and mechanical risk);
  - driver coach (development); medical/fitness (injury recovery).
- **The staff market:** staff age, develop and move between teams; good crew chiefs are scarce.
- **Crew-chief strategy in the engine:** pit calls under caution, fuel-only stops, staying out.
- **Driver–crew-chief chemistry:** a setup preference such as loose vs tight.

### Phase 3: Personality in action ✅ (bonuses, release clauses, buyouts, development loans and pit-road confrontations still to come)

- **Morale:** results, equipment vs teammate, role, contract security.
- **Team chemistry:** multi-car teams.
- **Contract negotiation:** drivers weigh money (greed), car quality and team results (desire to win), loyalty, and location. Contracts add performance bonuses, release clauses and buyouts. Teams can make development-contract loans down the ladder.
- **Temper on track:** payback incidents, pit-road confrontations, fines and penalties, rivalries that persist.

### Phase 4: Stats and long memory ✅

Known gaps:
- Records and Rookie of the Year follow the series id. A real-history era with its own id (e.g. the IRL years of IndyCar) keeps its own records book.
- Drivers generated with a career already behind them have no records from before the world began. They aren't counted as rookies or first-time winners, and their Hall of Fame case counts only the seasons played in this world.

- **Splits:** by track type and by season.
- **A value metric:** Positions Above Replacement, finishes against what the car's equipment should deliver (a racing WAR).
- **Records books:** by series and track.
- **Season almanac, awards and Hall of Fame:**
  - awards: Rookie of the Year, Most Popular Driver;
  - milestones: first win, 100th start;
  - a Hall of Fame ballot.

### Phase 5: The economic loop and other careers ✅ (owner mode up to the national level; buying a Cup charter still to come)

Numbers and sources: [`research/team_economics.md`](research/team_economics.md).

- Team finances: purse, charters and TV money, sponsors (primary and associate), merchandise from driver popularity, manufacturer support, costs.
- A fan base for drivers and teams, from regional to national, driving sponsor appeal.
- Owner and sponsor goals; job security; getting fired.
- **Owner mode:** run a team from a local late model operation up to a Cup charter.

### Phase 6: Scouting, development tools and settings ✅ (individual scouts with specialties still to come)

- **Scouting staff:** scouts with specialties (ovals, road, dirt, karting) and a scouting budget per ladder tier. Media power rankings serve as the public baseline (OOTP's OSA).
- **Off-season programs:** a "development lab" with sim and testing programs, plus focus sliders.
- **Realism settings:** crash frequency, mechanical failures, development speed, scouting accuracy, history fidelity (including exact replay).
- **Weather:** rain-outs and wet road-course racing; heat affecting tires and fitness.

## Performance budget

At the default world size, a season now takes about 15–18 s, up from about 10 s. The cost is lap-by-lap racing for every tour and national race.

The engine keeps this down the way OOTP does:

- races you watch run lap by lap;
- other races run in about 24 coarser steps of the same model;
- the thousands of weekly local features use the fast result-level model.
