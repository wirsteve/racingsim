# Rules, cars and money

How the game models what racers actually build, buy and race for: class rules, cars and parts, tires,
wear and wrecks, points systems, playoffs, purses and fees. Everything here is built from researched
evidence in `data/rules/`. That evidence comes from track house rules and sanctioning-body rulebooks
(mostly PDFs), dealer price lists and racing news. Each record carries its sources and a confidence level.

## Evidence (`data/rules/research.json`)

| Records | Count |
|---|---|
| Class rules (one track or body, one year) | 126 |
| Part prices and lifespans | 155 |
| Points systems | 37 |
| Purses, fees and points funds | 67 |
| Race-night formats | 23 |
| Dated history facts | 124 |
| Sources (`sources.json`) | 332 |
| Sources skipped, access restricted (`unavailable.json`) | 47 |

**Coverage**

- Asphalt rulebooks from about 48 bodies:
  - Southeast: Hickory, South Boston/CARS, Langley, New Smyrna, Five Flags/Snowball Derby, ASA southern rules.
  - Northeast: Stafford, Thompson, Speedbowl, Wiscasset, ACT.
  - Midwest: Slinger, Berlin, Owosso, CRA, the unified super late model rules.
  - West: LVMS, SRL, USA Late Model Series, Evergreen, Big 5.
  - National: INEX.
- Dirt rulebooks from about 25 bodies: IMCA 2015/2024/2026, DIRTcar/UMP 2015 and 2026, WISSOTA, USRA, USMTS, Lucas Oil, World of Outlaws, Super DIRTcar, All Stars, ASCS, USAC, POWRi, RaceSaver.
- Pro tiers and karting: NASCAR, ARCA, IndyCar and the Road to Indy, SKUSA/Rotax, Spec Miata.

**Collection rules**

- robots.txt was respected and no blocked source was worked around.
- The Third Turn was not fetched at all.
- The PASS rulebook was deleted unread because PASS's robots.txt blocks AI crawlers.
- CARS Tour, ARCA and MyRacePass pages sit behind Cloudflare or return 403. Their facts come from search results and are marked medium or low confidence.

Re-import after new research with `python tools/knowledge/rules_import.py`.

## Car classes (`data/rules/classes.json`)

There are 19 game classes. Each lists the options a racer can buy under that class's rules, with prices in 2025 dollars:

- **Chassis:** for example, used (age N), new from a regional builder, or new from a top builder.
- **Engines:** the packages the rules allow in a given season — built, crate, sealed crate, spec, or claimer. Each has its rebuild cost and interval, any claim price, weight break, and the years it is legal. For example, GM 602/604 crates from 2002, CT525 from 2014, and the IMCA spec engine from 2025.
- **Shocks**, sometimes with claim prices.
- **Tire rule:** price per tire, how many new tires a typical racer bolts on each night, the rule limit (for example a 2-new-tire rule), life in nights, and the spec compound.
- **Per-night costs:** entry and pit passes, fuel, consumables, plus the chance and cost of a typical wreck.

Option *quality* (0–100) is a design value: how competitive the part is within its class once the rules have balanced it (weight breaks, seals). Class *spread* sets how far money can separate cars:

- Spec Legends and Bandoleros, and claimer Sport Compacts: about 0.5–0.65.
- Super late models and open dirt late models: 1.0 or more.

Edit the values in `tools/knowledge/rules_classes.py` and cite the research source ids. `python -m racingsim data validate` checks the references.

| Game class | Series templates | Evidence keys |
|---|---|---|
| Quarter midget, Bandolero, Legend car | youth/entry asphalt | INEX rulebook |
| Mini stock, Street stock | local asphalt | LVMS, Wiscasset, Langley, Hickory, New Smyrna |
| Limited late model, Late model (weekly top division) | local asphalt | Hickory, Stafford, Langley, Slinger, Owosso, ACT, CARS |
| Super late model | regional/national asphalt tours | ASA southern, unified rules, Big 5, LVMS, SRL, Snowball Derby |
| Asphalt modified | modified tours | Stafford/Thompson/Speedbowl SK, Whelen Modified Tour |
| Sport compact, Hobby stock, Dirt modified, Dirt late model | local/regional dirt | IMCA, DIRTcar/UMP, WISSOTA, USRA/USMTS, Lucas Oil, World of Outlaws |
| 360 sprint, Midget, Micro sprint | dirt open wheel | ASCS, World of Outlaws, All Stars, USAC, POWRi, RaceSaver |
| Kart (club / national), Club road racer | karting, club racing | SKUSA, Rotax, IAME, Spec Miata |

Team-run series (Cup, Xfinity, Trucks, ARCA, IndyCar …) keep a team equipment rating; their researched rules appear in the Encyclopedia.

## How a car becomes speed (`racingsim/rules/car.py`)

| Part | What it contributes | Weighted more at |
|---|---|---|
| Chassis | builder quality, tiring with age, unrepaired crash damage | hard-to-pass tracks |
| Engine | package power, losing up to 18% when overdue for a freshen, damage | horsepower tracks |
| Tires | how worn the set is; new tires each night versus the rule | abrasive, high-wear tracks |
| Shocks | package level | short, flat handling tracks |
| Setup | driver feedback | — |

The rating (50 is a typical competitive car in the class) feeds the race model's equipment term.

Overdue or damaged engines also fail more often. The mechanical-DNF chance comes from engine freshness and health, not from a generic number.

## Racing a car

**The player** has a racing account each season: family budget, sponsors, scholarship and 25% of savings. Every night it is charged:

- entry and pit passes, fuel and consumables, and the new tires bought (cut back when money runs out);
- travel;
- the programme's crew, hauler, practice tires and spares.

The last line makes a typical programme cost what the researched season budget for that series says. Parts and race nights alone come to only 30–60% of a real Late Model Stock or super late model season.

| Event | What happens |
|---|---|
| Purse | paid into the account |
| Wreck | damage taken from the track's crash severity; repaired straight away (auto) or later |
| Mechanical DNF | damages the engine; a blown engine needs a short block |
| Engine past interval | freshened automatically (toggle) |
| Claim rule | a top-5 finisher running an engine worth far more than the claim price can lose it, and gets the claim price |
| Can't afford to race | you miss the night |
| Season end | winnings are yours; half of the unspent family money goes to savings |

Everything lands in the ledger on the **Garage** page.

There you can buy a complete package or individual chassis, engine and shocks (with trade-in), set the tire policy, freshen or repair, and read the class rules with sources.

**AI racers** use the same options and prices. Each off-season they buy and maintain their car from their budget level:

- They keep the car across seasons and freshen it each winter.
- They replace the chassis when it is worn out or when they can afford a step up.
- In-season wear is modelled in steady state for speed.
- Wrecks and failures are paid from a season reserve. Without one, the car stays damaged and slower.

## Points (`data/rules/points.json`)

| System | Used for |
|---|---|
| NASCAR Latford 1975–2003 (175 to win, +5 led a lap, +5 most laps led); 180 to win (2004–06); 185 (2007–10) | Cup, Busch/Xfinity, Trucks, ARCA tiers |
| One-point system 2011–16 (43…1, +3 win, +1/+1) | same |
| Stage racing 2017–25 (40, 35, 34 …; stages 10–1) | same |
| 2026 (win worth 55) | same |
| IMCA weekly (40 down to 17; B-feature 16–11; no show-up points) | weekly dirt in IMCA states (IA, NE, KS, TX …) |
| DIRTcar/UMP weekly (75 down to 26; minimum 10) | weekly dirt in DIRTcar country (IL, IN, OH, PA, NY …) |
| WISSOTA (13 show-up + heats 10–2 + feature 35–11) | MN, ND, WI, MT, MB |
| 2 points per car beaten (Hickory / NASCAR weekly style) | weekly asphalt in the Southeast |
| 50 −2 (Stafford), 100 −2 + heats (Spud), Galesburg table | weekly asphalt in the Northeast, Maine, Michigan |
| Florence (100 −2, heats 20–1, 10 show-up) | Kentucky dirt |
| Lucas Oil (200 to win), World of Outlaws style (150/146 −2), All Stars (50 −1) | national/regional dirt tours |
| IndyCar, CART, Champ Car | open wheel |

**Championship formats**

- Chase 2004–06 (top 10, 5,050 down by 5), 2007–10 (top 12, +10 per win) and 2011–13.
- Elimination playoffs 2014–25: 16 drivers, win and you're in, cut to 12, 8, then 4, with a winner-take-all finale.
- The 2026 Chase: top 16 on points, seeded 2,100 down to 2,000, no eliminations.
- Xfinity and Truck playoffs.

**Race night**

- When more cars show up than the feature takes, heat races decide the field. Non-qualifiers get DNQ points and tow money.
- Systems with heat points award them per heat.

Standings show points, behind, starts, wins, top-5s, top-10s, average finish, winnings and playoff status, as standings sheets do.

## Purses (`data/rules/payouts.json`)

Published payout sheets are kept in their year's dollars. Weekly tables:

| Class | Source | Year | To win | To start |
|---|---|---|---|---|
| Mini stock | Galesburg | 2024 | $300 | $90 |
| Street stock | Galesburg | 2024 | $700 | $150 |
| Limited late model | Galesburg | 2024 | $1,000 | $200 |
| Late Model Stock | South Boston | 2021 | $3,000 | $500 |
| Hobby, modified, crate late model, sport mod, legends | Florence | 2024 | full position lists | — |

Tour tables: ASA STARS, Lucas Oil (with points fund), World of Outlaws Sprints (with points fund).

Each table has a *drift*: the share of motorsport cost inflation the purse kept up with.

- **Tours and crown jewels: 0.75.** The World 100 paid $28k to win in 1995 and $72k in 2025.
- **Weekly tracks: 0.25.** Indiana weekly sprints paid $600–1,000 to win in the 1990s. Local purses have barely moved in nominal terms while costs roughly tripled, so a 1996 career earns relatively more per win than a 2024 one.

Series without a table use the generic curve from `data/series.json`.

## Known gaps

- **Thin before 2005:** little hard rule or price data for 1995–2005 beyond IMCA claim prices, Late Model Stock costs and crown-jewel purses. Engine eras (crates from 2002, CT525 from 2014) come from dated history facts.
- **Estimated values:** quarter midget, micro sprint, midget and 360 sprint costs are low confidence.
- **Missing points tables:** CRA, USAC, Whelen Modified Tour, ASCS and full USRA tables were not found. Those series use the nearest documented system.
- **Unverified formats:** the 2026 Xfinity and Truck formats could not be verified (the session's web-search budget ran out), so they are kept as in 2025 with low confidence.
- **Interpolated payouts:** most tour payout lists have only to-win and to-start published. Positions in between are interpolated and labelled as such.
