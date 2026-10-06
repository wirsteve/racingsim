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
| Game engine | Pitch by pitch, park factors, weather, box scores, play-by-play | **Lap-by-lap engine** (`sim/engine.py`): qualifying, tire falloff, fuel windows, green and caution pit cycles, passing vs track difficulty, crashes and big ones, mechanical failures (car model), free pass, restarts, stages, box score, play-by-play. Calibrated to real NASCAR data. Weekly local divisions use the fast result-level model, as OOTP does for leagues you don't watch | ✅ Phase 1. Weather and rain still to come |
| Ratings | ~30 ratings, current/potential, L/R splits, OVR/POT stars | 12 component skills (current/potential), 5 track-type experience and talent splits, OVR/POT on 20–80 | ✅ Phase 1. Stars relative to series level still to come |
| Ratings from history | Historical stats → ratings | Real NASCAR drivers rated from race-by-race results: qualifying vs race, laps led, positions gained, crash rate, track specialties | ✅ Phase 1 |
| Scouting | Scout director ratings, budget, accuracy by age/region, league baseline | Error shrinks with the driver's exposure; 5-point steps; personality shown only as impressions | ◐ No scout staff, budget or media rankings yet |
| Development and aging | Weighted random, coaching, playing time, personality, focus, development lab | Ability plus per-skill development: seat time, work ethic, intelligence; physical skills fade, savvy keeps growing; track types learned from laps; off-season coaching | ◐ No competition-level effect, focus sliders or off-season programs yet |
| Personality | 6 traits; morale; chemistry | 7 traits (work ethic, intelligence, leadership, loyalty, greed, desire to win, temper) | ◐ Traits exist; morale, chemistry and contract effects come in Phase 3 |
| Injuries | Types, body areas, proneness, re-injury, trainers | Races out, severity, durability | ◐ No injury types, concussion history, racing hurt or medical staff |
| Stats | Every stat, splits, logs, WAR | Per race: start, laps, laps led, status, ARP, passes, quality passes, fastest laps, pits, driver rating. Per season: poles, laps led, DNFs, average start/finish, rating, winnings, points | ◐ No track-type splits, value metric, records, almanac or HOF |
| Team management / staff | Coaches, scouts, trainers with ratings | Teams have equipment and money only | ❌ Phase 2 |
| Transactions | Trades, FA, contracts, options, waivers, draft | Silly-season market, pay seats, salaries, contract years, development programs, shootouts | ◐ No negotiation, bonuses, release clauses, development loans or buyouts |
| Finances | Gate, media, merch, budgets, owner | The player's own car: real costs, purses, points funds; sponsors | ◐ No team finances, fan base or merchandise |
| Career / GM | GM mode, reputation, firing, job offers | Driver career; reputation; team offers | ◐ No owner or crew-chief careers, no goals or firing |
| League / history | Historical leagues, expansion | 1995–2026 real series, rosters, calendars, 12k+ touring races, real rules and points by era | ✅ Exact replay mode still to come |
| News / storylines / awards | Inbox, storylines, awards, milestones | News wire | ◐ No storylines, awards or milestones |
| Settings | Everything tunable | World size, start year | ❌ Phase 6 |

## Roadmap

Each phase is playable on its own and goes in as its own pull request.

### Phase 1: Driver ratings and the race engine ✅ (this PR)

- OOTP-style ratings: component skills, track types, personality, scouted display.
- Real drivers rated from their results.
- Lap-by-lap engine with box scores and play-by-play; real laps led and stage points.
- Calibrated against real data. Remaining calibration gaps:
  - The strongest Cup entry can still win 9–14 races a season (real: 6–9). This is partly world composition: the best driver also has the best team.
  - Coarse-step AI races under-count lead changes.

### Phase 2: The people around the car

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

### Phase 3: Personality in action

- **Morale:** results, equipment vs teammate, role, contract security.
- **Team chemistry:** multi-car teams.
- **Contract negotiation:** drivers weigh money (greed), car quality and team results (desire to win), loyalty, and location. Contracts add performance bonuses, release clauses and buyouts. Teams can make development-contract loans down the ladder.
- **Temper on track:** payback incidents, pit-road confrontations, fines and penalties, rivalries that persist.

### Phase 4: Stats and long memory

- **Splits:** by track type and by season.
- **A value metric:** Positions Above Replacement, finishes against what the car's equipment should deliver (a racing WAR).
- **Records books:** by series and track.
- **Season almanac, awards and Hall of Fame:**
  - awards: Rookie of the Year, Most Popular Driver;
  - milestones: first win, 100th start;
  - a Hall of Fame ballot.

### Phase 5: The economic loop and other careers

- Team finances: purse, charters and TV money, sponsors (primary and associate), merchandise from driver popularity, manufacturer support, costs.
- A fan base for drivers and teams, from regional to national, driving sponsor appeal.
- Owner and sponsor goals; job security; getting fired.
- **Owner mode:** run a team from a local late model operation up to a Cup charter.

### Phase 6: Scouting, development tools and settings

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
