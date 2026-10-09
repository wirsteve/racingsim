# Money, sponsors and a guided home screen: design

Date: 2026-10-09. Status: proposed. Owner's direction: "whatever is realistic".

## Why

The owner played a middle-class karting career and ran out of money halfway through the
season, saw no money coming in, could spend the family's whole season on a second car on
day one, never noticed sponsors, and found the UI busy with no guidance (Dashboard and My
Career look the same).

### What a traced season shows (seed 11, NC, age 10, middle-class, 2026)

| | |
|---|---|
| Family money for the season | $11,933 |
| Used kart bought at the start | −$2,397 |
| Trailer and garage upkeep | −$700 |
| Each race weekend | −$1,474 ($290 entry and fuel, $130 tires, $150 crew and spares, **$904 travel**) |
| Purses | $0 (karting pays trophies, which is correct) |
| Sponsors | $0 |
| Result | broke after 6 of 10 races; the last 4 were skipped |

Root causes:

1. **No local karting rung.** The track database has 8 kart tracks in North America, so the
   only karting series is a regional championship (Sebring, Road Atlanta, Atlanta, ...).
   Real kids start with club racing at the nearest kart track.
2. **Towing costs are ~3x too high at grassroots level.** Every tier uses $2.25 a mile
   (`world/regions.py`); a pickup and trailer runs $0.75-0.85 a mile all-in
   (`docs/research/race_shop_economics.md` §1).
3. **New careers are placed where the family covers only 80% of the season**
   (`game/career.py::_place_entrant` picks the highest tier with `afford >= 0.8`).
4. **All money arrives as one lump on day one** (`rules/garage.py::open_account`), so the
   ledger never shows income and a second car can eat the whole season.
5. **Sponsors work but are nearly invisible.** The only player action is one off-season
   "Pitch" button. Deals fold silently into next season's lump. About 1 in 70 local AI
   racers has a sponsor, because each region has only a handful of local sponsors.

## Goals and non-goals

Goals: money flows the way it does in real grassroots racing and the player can see it;
sponsors are a system you work at all season; you start where your family can actually
afford to race; the home screen tells you what to do next.

Non-goals: changing the race engine, the AI driver market (beyond affordability and
sponsor counts), or progression gates. The gates get a play-through check after this
lands (separate task) and are only changed if they turn out broken.

## Design

### 1. Money flow (`rules/funding.py`, new)

- **Family pledge.** The family commits a season amount (`Driver.family_budget`, less what
  was already spent on the car in the off-season). It is paid **per race weekend** into the
  racing account, as a ledger line ("Family: $1,190 for Trackhouse Motorplex"). It is paid
  only for weekends you race. A weekend you skip isn't funded and isn't spent.
- **Your own money.** Savings stay yours. The 25% savings draw into the season's account
  goes away; you spend savings directly when the account is short (as `spend()` does today).
- **Sponsors** pay per race weekend too (see 3), plus result bonuses.
- **Purses** as today (payout sheets, tow money for DNQs).
- **Capital purchases** (cars, engines, haulers, shop upgrades) are paid from what you have
  now: the account plus savings. Future family weekends can't be spent in advance, so a
  second car on day one has to come out of savings.
  - In the off-season, the family may put up to **half** of next season's pledge toward the
    car itself (buying the car over the winter is what real families do). The rest is kept
    for racing.
- **Runway.** `funding.runway(world, d)` projects whether the money lasts: cash on hand plus
  remaining pledged family and sponsor payments, against expected weekend costs (entry,
  tires, travel, overhead, engine wear). It returns `{races_left, races_funded, short_by}`.
  It drives the home-screen warning and the season budget check.
- **Season close.** Unspent family money: half comes back to savings (unchanged). The
  family's unspent pledge simply isn't paid.

### 2. Realistic travel and a local kart rung

- `TOW_COST_PER_MILE` by level:
  - tiers 0-2: **$0.80** (pickup and open or enclosed trailer, all-in);
  - tier 3: **$1.30** (dually and race trailer);
  - tier 4 and up: **$2.25** (unchanged).
  - Lodging: local and regional racers camp at the track or share rooms. Grassroots lodging
    is ×0.5 (EST; to be checked against `docs/research/grassroots_money.md`).
- **Kart tracks:** `data/tracks/kart_venues.json` (being researched: real kart tracks
  with sources and coordinates; no invented locations).
- **New series template `kart_club`:**
  - tier 0, track scope, venue `kart`, ages 5-17;
  - costs from the grassroots research (club entry, membership, tires, LO206 rebuilds);
  - no purse;
  - 8-12 club race days.
- The regional karting championship becomes the step up from club racing.
- **New careers start where the family can pay for the whole season**
  (`afford >= 1.0`, including travel and upkeep). They prefer the nearest club rung. If
  nothing is fully affordable, they take the cheapest option and the budget check says so.

### 3. Sponsors as a system (`career/sponsorship.py`)

- **Deals carry terms** (new fields on `SponsorDeal`, defaulted for old saves):
  - `kind`: decal, associate, product or contingency;
  - `per_race` payment;
  - `bonus_win` and `bonus_top5`;
  - `expects`: race every week, top-10 average or podiums;
  - `mood`: 0-100.
  - Grassroots sizes come from the research (local decal sponsors in the hundreds to low
    thousands of dollars a season).
- **Payments** land per race weekend as ledger lines. Bonuses are paid after the race.
- **Mood** follows whether expectations are met (results, starts, exposure). Below 30 you
  get a warning ("Wheeler Auto Body isn't happy: they wanted top-10s"). Below 10 the sponsor
  stops paying and leaves mid-season.
- **Pitching** works in season and in the off-season, once every 4 weeks. Odds use the
  existing appeal (marketability, reputation, results, fans, exposure). Offers can also
  arrive unasked after wins or strong runs. They wait in an offers list for you to accept or
  decline within 3 weeks.
- **Contingency** (if the research supports it): a class's tire, parts or fuel supplier
  pays small amounts for wins and podiums when you run their decal.
- **More local sponsors.** The world gets enough small local businesses that a typical local
  racer can find one or two backers, matching the research's share of a budget that
  sponsors cover. The AI market uses the same pool.
- **Sponsors page** (`#/sponsors`): your deals (per race, bonuses, what they want, mood),
  offers waiting, and the Pitch button with its cooldown.

### 4. Budget check

On the off-season offers, the self-run options and the new-career screen, every option
shows: "Season ≈ $X (entry, tires, travel, upkeep) · you'll have ≈ $Y (family, sponsors,
savings) · covers ≈ N of M races."

### 5. Home screen and guidance (PR 2)

- **One Home** replaces Dashboard and My Career.
  - **"What to do now":** a server-side `todo(game)` list. Each item has a priority, a
    sentence and a button. Examples:
    - "Engine is 3 races past its freshen";
    - "Sponsor offer from X: 2 weeks to answer";
    - "Money lasts about 3 more races";
    - "Your car is wrecked: repair it or roll out the backup";
    - "Off-season: pick next season's ride".
  - Next race, plus money this season (in and out) and the runway.
  - Standings snippet.
  - Career history moves to the driver page.
- **Tips:** a short tip at the top of each page the first time you visit it, with a "Got
  it" button to dismiss it (kept in browser storage; there is also a setting to turn them
  all off).
- **How to play** page, linked from Home and New Career: the season loop, money,
  sponsors, the car, moving up.
- **Navigation** gets three groups:
  - **Race:** Home, Garage, Race Shop, Sponsors, My Series, Crown Jewels.
  - **World:** the existing world pages.
  - **Game:** Settings, Save / Load, How to play, New Career.

## Data and compatibility

- New `SponsorDeal` fields have defaults. Old saves keep their lump-sum account for the
  season in progress; the per-weekend flow starts at the next season open.
- `world.shop` and the other existing fields are unchanged.
- The AI uses the same `season_cost_for` (with the new tow rates) for affordability, so AI
  careers rebalance slightly. The economy and career tests check the ranges still hold.

## Testing

- **Funding:**
  - pledge payments per weekend add up to the pledge;
  - a skipped weekend pays nothing;
  - a capital purchase can't use future weekends;
  - the off-season car cap is half the pledge;
  - runway projection against a simulated season (within ±1 race).
- **Middle-class karting regression:** the traced career (NC, 10, middle) finishes its season
  with money in the account, and starts in club karting where a kart track is nearby.
- **Sponsors:**
  - per-race payments and bonuses hit the ledger;
  - mood falls with poor results and the sponsor leaves below 10;
  - pitch cooldown; offers expire;
  - the share of local AI racers with a sponsor sits in the research range.
- **Travel:** the tow rate by tier.
- **Existing suite:** the economy and career calibration ranges still pass.
- **PR 2:** `todo()` items for each trigger; tips dismiss and persist; Home renders for
  in-season, off-season, team seat, owner and retired players; a Playwright pass in light,
  dark and phone widths.

## Delivery

- **PR 1:** sections 1-4 (money, travel, kart club rung once the track data lands, sponsors,
  budget check).
- **PR 2:** section 5 (home, to-dos, tips, how to play, navigation).
- After both: a play-through of progression gates, reported to the owner.
