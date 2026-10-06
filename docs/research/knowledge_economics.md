# Why drivers advance, stall or quit - evidence and game weights

Research layer for the racingsim career model (economics / advancement). Generated 2026-10-06. Every number here is also in the JSON files with sources and confidence. Repo-derived numbers cite `src:racingsim-history-analysis` (script `analyse_history.py`, output `computed_evidence.json`).

## Headline findings

1. **Results matter a lot, but they don't guarantee a move up.** Within 3 seasons of the title, 91% of Xfinity champions, 75% of Indy Lights champions and only 48% of Truck champions held a full-time seat one level up. Finishing P11 or lower as a full-timer gives an 11-17% chance (Pro Mazda, Indy Lights, Trucks, Xfinity). The other direction also holds: 51% of full-time Cup rookies since 1997 had never won an Xfinity race, and 30% had never run a full Xfinity season.
2. **Age is the strongest modifier of results.** A top-5 Truck finisher aged 20-25 moved up within 3 seasons ~75% of the time. Aged 35+, the rate was 18%. In Xfinity, top-5 finishers aged 20-29 reached Cup ~90% of the time, against 50% at 30-34 and 29% at 35+. The median age of a driver's first full-time season fell by 8-11 years between the late 1990s and the 2010s (Cup 33 → 25, Trucks 33 → 22, Xfinity 30 → 23).
3. **Connections roughly double promotion odds.** Truck top-5 finishers on Cup-affiliated teams moved up 59% of the time, against 27% on independent teams. In Xfinity the figures were 84% and 47%. Owner-drivers and family-named teams almost never move up (Trucks 4% vs 26%). Family money buys staying power more than promotion.
4. **Equipment explains a large share of results at the top, much less in spec junior formulas.** The share of a driver's season result that teammates also share (ICC) is 0.781 in Xfinity and 0.57 in Cup (2015-26), and 0.389 in IndyCar. In USF2000 it is 0.183 and in Indy Lights about 0. For comparison, F1 is 86-88% constructor according to the literature. Drivers who changed teams saw their results move by 0.2-0.47 times the change in team strength.
5. **Money is the gate from tier 4 up.** Typical seat prices are ARCA ~$1.0-1.4M per season, Indy NXT ~$1.2-1.5M, Trucks $1.5-3.5M, competitive Xfinity $4-5M, and $6-8M to bring to a Cup seat. Junior-ladder scholarships cover about half the cost of the next step. Several USF champions stalled for lack of funding.
6. **Seat availability (timing) is very uneven.** The share of full-time seats that change hands each winter (median) is Cup 16%, IndyCar 25%, Xfinity 39%, Trucks 39%, Indy Lights 58% and USF2000/Pro Mazda ~69%. 59% of new full-time Cup drivers came from full-time Xfinity or Trucks seats, and 36% had been Cup part-timers.
7. **Most careers end by fading out, not by retiring in one go.** About 53% of Cup careers that ended went through part-time Cup seasons first. 30% dropped to full-time lower-series rides (median age 37) and 10% left directly. The median last full-time Cup season came at age 41, against 32 in IndyCar.

## Recommended default advancement weights per tier

Each cell is the share of a promotion or retention decision at that game tier that the factor drives. Every column sums to 1.0. The `min`/`max` ranges in `advancement_factors.json` widen these values by ±25%, ±35% or ±50% for high, medium and low confidence. These weights are calibrated judgements anchored on the computed rates below. They are not regression coefficients.

| factor | conf | t0 youth | t1 local | t2 local top | t3 regional | t4 nat. dev | t5 feeder | t6 nat. pro | t7 premier |
|---|---|---|---|---|---|---|---|---|---|
| Talent | medium | 0.15 | 0.15 | 0.14 | 0.12 | 0.10 | 0.07 | 0.08 | 0.08 |
| Results | high | 0.15 | 0.15 | 0.16 | 0.15 | 0.13 | 0.13 | 0.14 | 0.20 |
| Equipment quality / team strength | medium | 0.06 | 0.08 | 0.09 | 0.08 | 0.08 | 0.07 | 0.07 | 0.06 |
| Sponsorship | medium | 0.03 | 0.05 | 0.08 | 0.10 | 0.13 | 0.16 | 0.18 | 0.15 |
| Family funding | medium | 0.35 | 0.30 | 0.25 | 0.22 | 0.17 | 0.12 | 0.07 | 0.02 |
| Team / owner funding of the seat | medium | 0.01 | 0.01 | 0.02 | 0.02 | 0.02 | 0.03 | 0.05 | 0.08 |
| Reputation / track record / experience | medium | 0.02 | 0.04 | 0.05 | 0.04 | 0.03 | 0.04 | 0.04 | 0.10 |
| Networking / connections | medium | 0.05 | 0.06 | 0.07 | 0.07 | 0.07 | 0.08 | 0.09 | 0.06 |
| Driver development programs | medium | 0.03 | 0.01 | 0.02 | 0.05 | 0.08 | 0.09 | 0.08 | 0.03 |
| Manufacturer support | low | 0.00 | 0.00 | 0.01 | 0.02 | 0.03 | 0.04 | 0.05 | 0.05 |
| Age | high | 0.08 | 0.06 | 0.06 | 0.07 | 0.08 | 0.09 | 0.07 | 0.06 |
| Crashes and injuries | low | 0.01 | 0.02 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.03 |
| Mechanical reliability | low | 0.01 | 0.02 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 |
| Marketability | low | 0.01 | 0.02 | 0.02 | 0.02 | 0.03 | 0.04 | 0.04 | 0.05 |
| Luck / timing | medium | 0.04 | 0.03 | 0.01 | 0.02 | 0.03 | 0.02 | 0.02 | 0.02 |

How to read it: family money dominates tiers 0-3 and sponsorship dominates tiers 4-6. Results stay at 0.13-0.20 throughout and are highest at the premier level, where keeping the seat depends on results. Age, connections and development programs together make up ~0.2-0.25 at tiers 4-6.

## Computed promotion probabilities (use as base rates)

The table shows the share of drivers who were full-time at any higher rung of the same ladder within 1 and 3 seasons. Drivers who were already full-time higher are excluded. Ranks are among eligible drivers, and every bucket except champion is full-time only.

| series (game tier) | champion 1y / 3y | P2-3 3y | P4-5 3y | P6-10 3y | P11+ 3y | all full-timers 3y |
|---|---|---|---|---|---|---|
| USF2000 (3), cohorts 2006+ | 88% / 100% (n=15) | 72% (n=29) | 43% (n=28) | 39% (n=67) | 30% (n=110) | 43% |
| Pro Mazda / USF Pro (4) | 47% / 42% (n=26) | 48% (n=27) | 37% (n=27) | 30% (n=67) | 17% (n=54) | 33% |
| Indy Lights / NXT (5) | 57% / 75% (n=28) | 46% (n=56) | 31% (n=55) | 20% (n=125) | 11% (n=94) | 28% |
| NASCAR Trucks (5) | 19% / 48% (n=29) | 36% (n=55) | 38% (n=56) | 31% (n=140) | 14% (n=317) | 24% |
| NASCAR Xfinity (6) | 50% / 91% (n=22) | 60% (n=45) | 58% (n=52) | 35% (n=126) | 15% (n=379) | 28% |

Champion promotion rate by era (within 3 seasons): Pro Mazda 1995-2004 0% (n=10), 2005-2014 50% (n=10), 2015-2026 100% (n=6); Indy Lights 1995-2004 70% (n=10), 2005-2014 70% (n=10), 2015-2026 88% (n=8); Trucks 1995-2004 70% (n=10), 2005-2014 20% (n=10), 2015-2026 56% (n=9); Xfinity 1995-2004 78% (n=9), 2005-2014 100% (n=5), 2015-2026 100% (n=8); USF2000 2005-2014 100% (n=6), 2015-2026 100% (n=9). The scholarship-backed open-wheel ladder became near-automatic for champions after ~2010. The weak 2005-14 Truck figure reflects veteran champions (Musgrave, Bodine, Hornaday, Benson, Crafton). Cohort sizes differ between the 1-year and 3-year windows because a 3-year window needs every year measurable, so the 1-year rate can sit above the 3-year rate.

A 'P-anything' outcome of at least one start at the higher level is far more common (Trucks top-5: ~77%; Xfinity top-5: 81-89%). Part-time cameos are cheap, but full-time seats are what money gates. Over a whole career, drivers whose first full-time season in a series was before 2022 reached a full-time seat higher up at these rates: USF2000 33%, Pro Mazda 36%, Indy Lights 30%, Trucks 36%, Xfinity 47%. Reaching an established premier career (3+ full-time seasons) is rarer: USF2000 6%, Pro Mazda 10%, Indy Lights 18%, Trucks 17%, Xfinity 35%.

### Age multiplier (top-5 finishers, promotion within 3 seasons)

| age at season | Trucks → higher | Xfinity → Cup | Indy Lights → IndyCar | suggested multiplier vs ≤25 |
|---|---|---|---|---|
| <=19 | 100% (n=5) | 100% (n=4) | 71% (n=14) | 1.0 |
| 20-22 | 77% (n=22) | 87% (n=15) | 49% (n=49) | 1.0 |
| 23-25 | 75% (n=12) | 93% (n=28) | 54% (n=41) | 1.0 |
| 26-29 | 56% (n=9) | 92% (n=13) | 29% (n=24) | 0.6-0.9 (open wheel 0.5) |
| 30-34 | 29% (n=21) | 50% (n=24) | 11% (n=9) | 0.3-0.55 (open wheel 0.2) |
| 35+ | 18% (n=71) | 29% (n=35) | 0% (n=1) | 0.15-0.3 |

### Connection multiplier (NASCAR, promotion within 3 seasons)

| finish | Trucks: Cup-affiliated / independent | Xfinity: Cup-affiliated / independent |
|---|---|---|
| top5 | 59% (n=56) / 27% (n=74) | 84% (n=57) / 47% (n=53) |
| P6-10 | 49% (n=45) / 26% (n=85) | 41% (n=56) / 33% (n=60) |
| P11+ | 22% (n=37) / 13% (n=259) | 23% (n=44) / 14% (n=314) |

Suggested multiplier for a pipeline/affiliated team is ×1.5-2.2 at tiers 5-6. 'Affiliated' comes from a hand-made list of Cup organisations and their satellites, so treat it as medium confidence.

## Team / equipment share of results

| series | ICC (teammates' shared share), all years | ICC 2015-26 | team share in 2-way FE (low conf.) | switcher slope | top-3 orgs' win share (median) |
|---|---|---|---|---|---|
| Cup | 0.423 | 0.57 | 0.431 | 0.206 | 71% |
| Xfinity | 0.665 | 0.781 | 0.633 | 0.466 | 70% |
| Trucks | 0.275 | 0.294 | 0.346 | 0.119 | 69% |
| IRL/IndyCar | 0.389 | 0.301 | 0.567 | 0.41 | 78% |
| CART/Champ Car | 0.413 | n/a | 0.667 | 0.373 | 79% |
| Indy Lights | -0.004 | -0.092 | n/a | -0.008 | 92% |
| Pro Mazda | 0.064 | -0.061 | n/a | -0.255 | 88% |
| USF2000 | 0.183 | 0.143 | n/a | 0.144 | 93% |

Metric: NASCAR uses top-10 finishes per start. Open wheel uses mean finishing percentile per race. A 'switcher slope' of 0.4 means that moving to a team whose other drivers score 0.2 better raises the switching driver by about 0.08. Suggested performance-model weight for the car/team: 0.35-0.6 at tiers 5-7 (stock car, IndyCar), 0.1-0.25 in spec ladders, and 0.3-0.5 at local tiers (estimate). The F1 literature (86-88% constructor) sets the upper bound.

## Career stages (see career_stages.json)

| stage | tiers | typical age | typical full-time stay | advance | stay | sideways | quit | conf |
|---|---|---|---|---|---|---|---|---|
| Youth / entry | 0 | 5-16 | 2-8 yrs | 0.20-0.40 | 0.05-0.15 | 0.05-0.15 | 0.40-0.65 | low |
| Local amateur | 1 | 14-60 | 1-15 yrs | 0.10-0.25 | 0.35-0.55 | 0.05-0.15 | 0.25-0.45 | low |
| Advanced amateur / regional | 2,3 | 14-45 | 1-20 yrs | 0.08-0.25 | 0.35-0.55 | 0.05-0.15 | 0.20-0.40 | low |
| Development pro | 3,4 | 15-23 | 1-3 yrs | 0.30-0.40 | 0.00-0.05 | 0.10-0.25 | 0.35-0.55 | medium |
| National pro feeder | 5 | 17-45 | 1-4 yrs | 0.28-0.38 | 0.05-0.18 | 0.19-0.30 | 0.17-0.46 | high |
| National pro (second national tier) | 6 | 18-45 | 1-5 yrs | 0.40-0.50 | 0.10-0.17 | 0.15-0.25 | 0.12-0.20 | high |
| Premier | 7 | 19-50 | 3-15 yrs | 0.00-0.05 | 0.80-0.86 | 0.10-0.17 | 0.01-0.10 | high |
| Veteran / journeyman | 5,6,7 | 30-55 | 2-12 yrs | 0.02-0.08 | 0.50-0.70 | 0.20-0.32 | 0.02-0.06 | medium |
| Grassroots comeback | 2,3 | 25-60 | 1-10 yrs | 0.01-0.05 | 0.50-0.75 | 0.05-0.15 | 0.15-0.35 | low |
| Retirement / owner / promoter | - | 28-70 | 0-30 yrs | 0.00-0.01 | 0.85-0.97 | 0.02-0.10 | 0.00-0.00 | low |

The shares are stage-exit shares over the whole stay. For the premier and veteran stages they are annual rates. Tiers 0-3 and the comeback and retirement stages are informed estimates (low confidence), because the repo has no grassroots data.

### Age facts (median age at first full-time season, by decade of that season)

| series | 1995-99 | 2000s | 2010s | 2020s | median last full-time season (no later FT anywhere) | KM median full-time seasons |
|---|---|---|---|---|---|---|
| USF2000 | 22 | 21 | 19 | 18 | 20 | 1 |
| Pro Mazda | - | 20 | 20 | 19 | 21 | 1 |
| Indy Lights | 26 | 23 | 22 | 22 | 24 | 2 |
| Trucks | 33 | 28 | 22 | 22 | 33 | 2 |
| Xfinity | 30 | 27 | 23 | 23 | 32 | 2 |
| IRL/IndyCar | 32 | 27 | 25 | 24 | 32 | 3 |
| CART | 26 | 26 | - | - | 29 | 2 |
| Cup | 33 | 27 | 25 | 26 | 41 | 7 |

Peak performance age (delta-method aging curve, consecutive full-time seasons): Cup ~31 with a plateau from 30 to 40 and a decline after ~41. IRL/IndyCar ~28 with a plateau from 26 to 35. Xfinity's plateau runs from 26 to 41. Median age at a race win: Cup 33, IndyCar 31, Xfinity 29, Indy Lights 23. Survivor bias makes the late decline look smaller than it is. The Trucks curve (peak ~36) mainly reflects veterans who stay in the series and should not be used as a skill curve.

## Economics summary (see economics.json for every range)

| tier | example | all-in competitive season / seat price | year | conf |
|---|---|---|---|---|
| 0 | quarter midget club / national junior karting | $3-15k / $50-120k | 2015-24 | low |
| 1 | Legends, street/hobby stock | $8-40k (new Legends car $17.5k) | 2022-24 | low |
| 2 | IMCA modified / IMCA late model / Late Model Stock | $30-70k / $60-74k / $150-200k | 2017-18 | medium |
| 3 | DLM or modified national tour / F4 US / USF2000 | $170-550k / $130-195k / $300-550k | 2017-24 | low-medium |
| 4 | ARCA top team / USF Pro 2000 / USAC midget | $1.0-1.4M / $0.65-1.0M / $0.2-0.4M | 2024-25 | low |
| 5 | Trucks (team cost per truck; seat) / Indy NXT | $3-4.5M; $1.5-3.5M seat / $1.2-1.5M | 2017-26 | medium |
| 6 | Xfinity mid-pack team / competitive seat / IMSA GTD car | $3.35-4M / $4-5M (back-marker $0.65M) / $3-5M | 2020-26 | medium |
| 7 | Cup per car / seat money to bring / IndyCar sponsorship target | $18-20M / $6-8M / $8-10M | 2023-25 | medium |

Money flows: Cup purses are ~$9.8-13.7M per race (Daytona 500 $30.3M), and charter payments to a car are $185-500k per race. Xfinity purses are ~$1.65M per race (~$46k per team). A Truck race purse is ~$0.78M, and a small Truck team earned ~$14k per race (2015). ARCA pays ~$5-10k to win, with a $375k points fund. WoO 410 standard purses are $58-70k with a $1.6M points fund. Cup salary estimates (low confidence) run from $0.5-2M for rookies and back-markers to $8-17M for stars, against $0.25-1.2M for typical IndyCar drivers. Truck and Xfinity drivers are often unpaid pay drivers. The scholarships are USF Juniors $242-264k, USF2000 $433-458k, USF Pro $547-682k, Indy NXT $0.5-1.3M (currently $850k) and MX-5 Cup $200k. On crash damage, a Cup wall hit costs $30-100k and a total loss $250-500k. One Xfinity wreck cost three teams ~$250k.

## Injuries and crashes

- Cup: roughly 0.5-1 full-time driver a season misses races through injury, about 1.5-3% of driver-seasons (Stewart 2013, Hamlin 2013, Kyle Busch 2015, Bowman 2022, Kurt Busch 2022, Gragson 2023). Career-ending injuries run at ~0.2-0.5% of driver-seasons (Kurt Busch 2022; Wickens 2018 in IndyCar). This is an informed estimate from those cases (low confidence).
- In the literature, single-seaters see ~1.2 in-race injuries per 1,000 competitor-races, and concussions occur at ~1-1.2 per 1,000 drives. In CART in 1984 there was one accident per ~1,400 racing miles, and 9.5 accidents per injury (pre-modern safety).
- Suggested game defaults per driver-season: P(miss races) 2-4% at paved pro levels and higher on dirt and sprint cars. P(career-ending) 0.2-0.6%. Crash budget is 5-15% of the season budget (estimate). Repeated crashing should cost self-funded drivers their rides first.

## Confidence and gaps

- **High confidence:** the computed transition, age, tenure and turnover rates for the 8 repo series. These are large-n, with Wilson 95% CIs in computed_evidence.json. Also high: official scholarship values, age rules and the charter-trial figures.
- **Medium confidence:** team-strength shares (the ICC is clean, but the 2-way FE suffers limited-mobility bias), the connection multiplier (manual list of affiliated teams), and most cost figures (single-source journalism, 2015-2026 mixed years).
- **Low confidence:** everything at tiers 0-2 (no grassroots data in the repo, so costs and quit rates are estimates), pay-driver *prevalence*, salary estimates, IMSA seat prices, injury rates, marketability and reliability weights.
- **Measurement caveats.** 'Left the dataset' mixes quitting with moves to ARCA, sports cars, Europe or short tracks, so open-wheel quit shares are upper bounds. USF2000 → Pro Mazda outcomes can only be measured from 2006, because Pro Mazda before 2007 is champion-only. The CART tenure figures are truncated by the series ending in 2007. 2026 seasons are partial. Age analysis excludes drivers without Wikidata birth dates (mostly obscure part-timers in the open-wheel ladder).
- **Not found / not computable:** a quantitative share of pay drivers per field; DNF causes (reliability); systematic injury registries for US series; family spend surveys beyond anecdotes; ARCA, IMSA GTD and Indy NXT seat prices beyond 1-2 sources. Racing-Reference and The Third Turn were not used (project rule), and racer.com, forbes.com and nascar.com galleries were blocked or rate-limited (unavailable.json).

## Files

- `advancement_factors.json`: 15 factors, each with `weight_by_level` for tiers 0-7 ({min, mid, max}), evidence, confidence, sources and game notes.
- `career_stages.json`: 10 DriverCareerStage entries with age ranges, durations and exit shares. The pro stages carry the computed annual outcome distributions.
- `economics.json`: season budgets by tier, pay-seat prices, sponsorship deal sizes, purses and funds, scholarships, salaries, crash damage and money flows.
- `computed_evidence.json` and `analyse_history.py`: everything computed from `data/history`. Rerun with `python3 -I analyse_history.py [history_dir] [out.json]`.
- `sources.json`, `ledger.jsonl`, `unavailable.json`: provenance.
