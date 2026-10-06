# OOTP (Out of the Park Baseball) Mechanics: A System-by-System Reference

Purpose: document how OOTP (roughly versions 22-27) gets its simulation depth, so that
racingsim can match it system by system. Everything below is summarized in our own
words, with short quotes only. Each section covers **what the player sees**, **what is
simulated underneath**, **how granular it is**, and **what makes it feel deep**.

**Sources.** The main source is the official online manual
(`manuals.ootpdevelopments.com`, `man=ootp22` / `man=ootp24`; the ootp25+ manual pages
returned errors). It is supplemented by the OOTP wiki, official product and newsletter
pages, and third-party guides and reviews. OOTP forum threads (forums.ootpdevelopments.com)
returned HTTP 403 to direct fetches, so they were not read; only their search-result
snippets are used, and those are marked. Claims marked **[GK]** come from general
knowledge of the game and were not confirmed by a fetched source during this research.
Verify those before relying on exact numbers.

Version notes collected:
- **OOTP 24:** Dynamic Trade Deadline Day; an overhauled International Amateur Free
  Agency (IAFA) system with pool reveals, monthly practices that build loyalty and
  scouting accuracy, and tradable bonus-pool money; pitcher BABIP merged into the
  Movement rating.
- **OOTP 25:** development focus sliders; the Development Lab; new catcher framing and
  basestealing aggressiveness ratings.
- **OOTP 26:** Development Lab 2.0 (progress bars, midterm reports); an overhauled
  scouting model with more detail; an improved historical ratings engine; military service.
- **OOTP 27:** Statcast-style stats (exit velocity, launch angle, xBA, xSLG, Barrel%, pitch
  run values); dynamic weather; new difficulty settings; the World Baseball Classic.

---

## 1. Player ratings

**What the player sees**
- A player profile with ratings shown on a scale the user chooses: 1-5, 2-8, 1-10, 1-20,
  20-80 (in steps of 5), 1-100, or hidden entirely while the math keeps running.
- Ratings are color-coded in five bands: blue (81%+), green, yellow, orange, red (0-20%).
- Every major skill shows **current / potential**, with a vs-LHP / vs-RHP split on the
  ratings page.
- OVR and POT appear as **stars** (half-star steps, maximum 5) or on the 20-80 scale.

**Batting** (current and potential, split vs L/R)
- **Contact** is derived from **BABIP** and **Avoid K's**.
- **Gap power** drives doubles and triples. **HR power** drives home runs. **Eye**
  drives walks. **Avoid K's** drives strikeouts and two-strike decisions.
- Editor-level extras: HBP tendency and triple ratio.
- **Hitter type** (spray / normal / pull) changes only batted-ball direction, not quality.

**Running and other** (no potential)
- Speed, Stealing, Baserunning instincts, Sacrifice bunt, Bunt for hit.
- Steal aggressiveness was added in OOTP 25.

**Pitching**
- **Stuff** (strikeouts; built from the individual pitch grades plus velocity).
- **Movement** (home runs and hard contact; since OOTP 24 it includes pitcher BABIP).
- **Control** (walks).
- These three carry potential ratings. Stamina, Velocity (in mph), Ground-ball %, and
  Hold runners do not.
- Each pitch in the repertoire has its own current and potential grade. The arsenal is
  roughly a dozen possible pitch types **[GK]**, and an MLB starter typically needs
  about three good pitches.
- The pitching ratings are also split vs LHB / RHB.

**Fielding**
- Infield and outfield **Range**, **Error**, and **Arm** are tracked separately.
- Turn double play; Catcher ability; Catcher arm; catcher framing (OOTP 25).
- A composite **rating for every position**, built from those components plus positional
  *experience*. A player loses a position if a component falls below that position's
  minimum.

**Hidden and personality ratings**
- Injury proneness.
- Personality: leadership, loyalty, desire to win, greed, intelligence, work ethic (see §4).

**Under the hood**
- True ratings are stored on a finer internal scale than the display. The old wiki
  describes 1-250, with 1-200 as the normal range; other wiki revisions describe a larger
  internal range. The display scale is only a projection of that internal value.
- **OVR/POT are relative.** They compare a player to the average true (or potential)
  ratings of all players *at that position or role in the league*. A 4-star shortstop
  might be a 3-star second baseman.
- For pitchers, POT uses the projected future role.
- When scouting is on, OVR/POT come only from your scouting director, never from the
  league's OSA (see §2).

**Granularity**
- Roughly 6 batting, 5 running, about 8 fielding components plus about 9 position
  ratings, and about 7 pitching ratings plus per-pitch grades. Most have both a current
  and a potential value, and most batting and pitching ratings have L/R splits. That is
  well over 60 numbers per player.

**Why it feels deep**
- Each rating maps to one specific outcome: Eye affects walks only, Power affects HR only.
- Every rating has a hidden "true" value and a scouted, displayed value.
- Stars are relative to position and league, so a player's value changes with the context.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=ratings_overview
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=batting_ratings
- https://manuals.ootpdevelopments.com/index.php?man=ootp17&page=pitching_ratings
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=defensive_ratings
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=other_ratings
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=overall_rating
- https://wiki.ootpdevelopments.com/index.php?oldid=2321
- https://30-30.club/encyclopedia/index.php/Out_of_the_Park_Baseball_25

## 2. Scouting

**What the player sees**
- Every displayed rating is *your scouting director's opinion*, not the truth.
- Scouting reports carry a **Scouting Accuracy** (confidence) label.
- The **OSA** (OOTP Scouting Association) gives a league-wide "second opinion" that
  updates once a year. It is generic and shows no OVR/POT when scouting is on.
- You can request a report on a specific player. There is no per-player scouting
  assignment the way Football Manager has; scouting happens on its own in the background.

**Under the hood**
- The scout perceives each true rating plus an error term. That error depends on:
  - The **scouting director's ratings**. There are 5: Scout Majors, Scout Minors,
    International, Scout Amateurs, and **Projection**, a philosophy setting from
    "ability" (rates potential from what the player can already do) to "tools" (rates
    potential from the ceiling).
  - The **scouting budget**, split across ML / minors / international / amateur.
  - The league-wide **Scouting Accuracy** setting: very low to very high, or 100%.
  - **Player age and origin**. Young and international players carry more error,
    especially on potential.
  - **Random per-player skew**: some players are simply mis-scouted, up or down.
- The OSA represents a baseline director with a baseline budget. If you outspend the
  baseline and have a better director, trust your own scout over OSA. If not, the
  reverse holds.
- Changing your director causes *immediate, large* re-ratings of the whole league.
- Report update frequency can be monthly, bi-monthly, or seasonal.

**Granularity**
- 5 director ratings × 4 budget buckets × a global accuracy setting × age and region
  modifiers × per-player skew.
- OOTP 26 overhauled the model so scouts give more detailed reports.

**Why it feels deep**
- Decisions are made under **uncertainty**, and the stats are the cross-check: guides tell
  players to compare reports with performance because scouts "miss" things.
- The director's philosophy creates a recognizable "eye" for talent.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=scouting
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=scouting_directors
- https://baseballreplayjournal.substack.com/p/scouting-in-ootp
- https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=game_options

## 3. Development and aging

**What the player sees**
- Ratings change over time: monthly or periodically in-season, with bigger moves in the
  off-season and spring training **[GK on exact timing]**.
- From OOTP 25 onward, the player screen has a Development tab:
  - **Focus sliders** split a player's limited practice time across BABIP, Avoid K, Gap,
    Power, Eye, Running, and Defense. For pitchers the choices are pitches vs control
    and similar.
  - The **Development Lab** takes a few players at a time over the off-season and spring.
    Up to about 20 can be assigned to programs such as "Add Pitch" or "Improve Quality of
    Contact."
  - OOTP 26 added progress bars and midterm progress reports.

**Under the hood**
- There are three regimes:
  - **Development**: a young player moves toward his potential.
  - **Maintenance**: a developed player holds his ratings.
  - **Aging**: decline in both current and potential ratings.
- All of it is *weighted random outcomes*.
- The inputs are:
  - **Coaching and staff quality**: GM, manager, bench coach, hitting and pitching
    coaches. Coaches have focus types (hitting: power, contact, patience, or neutral;
    pitching: power, finesse, groundball, or neutral) and work best with players who
    match their style.
  - **Playing time**: matters in the minors. Major leaguers and reserve-roster players
    develop normally without it.
  - **Challenge level**: a player dominating a level stalls; a player overmatched at a
    level can regress.
  - **Talent / potential**: high-potential players usually develop faster.
  - **Age.**
  - **Injuries**: severe injuries can lower current *and* potential ratings.
  - **Spring training.**
  - **Personality**: work ethic and intelligence help development; morale has a minor
    effect.
  - **Pure chance**: "the light bulb … just go[es] on."
- Focus sliders reweight the coaching influence per rating. A neglected rating develops
  more slowly, and its potential is more likely to drop.

**Settings**
- Batter and pitcher **aging speed** and **development speed** multipliers (1.000 =
  normal; they act as fast-forward rates).
- Target development and aging ages: by default development completes around 25 and
  decline begins around 30.
- **Talent Change Randomness (TCR)**: default 100; higher means more volatile potential.
- Development can be frozen entirely (useful for historical play).

**Why it feels deep**
- Potential is not destiny. Busts and late bloomers emerge from the interaction of
  randomness, environment, and management choices.
- The player has levers (level placement, playing time, coaches, focus, the Lab) without
  getting deterministic control.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=player_development
- https://manuals.ootpdevelopments.com/index.php?man=ootp17&page=player_development
- https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=game_options
- https://baseballreplayjournal.substack.com/p/injuries-and-aging-in-ootp
- OOTP forum snippets via search (p=5085213, p=5132558): focus sliders, Development Lab,
  and the development / maintenance / aging description.

## 4. Personality, morale, and chemistry

**Personality** (6 ratings, shown on a five-level scale from very low to very high)
- **Leadership** lifts teammates' performance and development.
- **Loyalty** makes a player more willing to extend with his current team.
- **Desire to win** shapes where he signs and hurts morale on a losing team.
- **Greed** matters in negotiations and hurts morale if he feels underpaid.
- **Intelligence** helps teammates, in-game decisions, and development; low intelligence
  means more suspensions.
- **Work ethic** helps teammates and development and makes slumps less likely.
- Personality clues appear in profile text. Personalities can drift over time, and young
  players take years to settle.
- The whole personality model can be switched off.

**Morale** (7 levels: Angry, Very Unhappy, Unhappy, Normal, Good, Very Good, Great)
- There are four components, each **weighted per player**:
  - Team performance: record and streaks. A 10-game losing streak hurts even with a
    winning record.
  - Team transactions: signing stars is good; cutting popular players is bad; the
    player's own promotions and demotions count.
  - Personal performance.
  - **Role on team**, expected vs actual (for example "middle-of-the-order bat").
    Minor leaguers care about role more than stats.
- Low morale causes poorer performance, refused extensions, lower re-sign odds, trade
  demands, and role demands.
- Salary arbitration hurts morale, and losing the case hurts it more.

**Team chemistry**
- Driven mainly by the mix of **player personality classes** on the roster, plus each
  player's **relationship with the manager**.
- A dedicated screen shows the chemistry rating, per-player chemistry morale, class
  assignments, the bench coach's commentary, and specific player concerns.
- Manager personality types (Personable, Easygoing, Normal, Temperamental, Controlling)
  affect relationships.
- Since OOTP 21, coach quality is shown as per-player **"relationship"** and
  **"development influence"** columns.

**Why it feels deep**
- Roster decisions have social side effects: release a popular veteran and the clubhouse
  reacts.
- Contract talks depend on personality, not just money.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=player_personalities
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=player_morale
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=chemistry
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=personnel_ratings
- https://steamcommunity.com/app/1087280/discussions/0/1864993755183441792

## 5. Injuries

**Severity classes**
- **Day-to-day**: the player can still play, but at a percentage penalty. These are a
  risk for compounding injuries in the same area.
- **Out**: from days to nearly a year.
- **Career-ending**: the player usually goes on the 60-day list, then auto-retires at
  season end and his salary obligation is relieved.

**Mechanics**
- Injuries are tied to body regions: arm, leg, and back, with many specific injuries
  under them **[GK: a named list such as "strained oblique" or "torn UCL"]**.
- A hidden **injury proneness** rating affects how often a player is hurt.
- A **body-area history** makes later injuries in the same area more likely.
- Pitcher risk adds **Pitcher Abuse Points** (the cube of pitches over 100, accumulated),
  **rust**, and the current pitch count.
- Minor-league pitch caps: AAA 110, AA 100, A 95, lower levels 90.

**Effects**
- Severe injuries can reduce current *and* potential ratings.
- Optional **delayed diagnosis**: the true severity is revealed later.

**The trainer's role**
- Heal ratings (speed of recovery per body part), Prevent ratings (lower risk per body
  part), and fatigue recovery.

**Fatigue and Rest Status**
- Each game reduces a player's Rest Status and each day off restores it.
- Pitcher fatigue comes mainly from pitches thrown in the last 5 days relative to the
  Stamina rating.
- The UI shows battery icons for fatigue.

**Settings**
- Separate short-term and long-term injury frequency (extremely low to very high).
- Position-player fatigue (none to very high).
- Suspension frequency.

**Why it feels deep**
- Injuries have memory (prone areas), long tails (lost potential), and management levers
  (workload, the trainer).

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=injuries_fatigue
- https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=game_options
- https://baseballreplayjournal.substack.com/p/injuries-and-aging-in-ootp

## 6. Game simulation engine

**What the player sees**
- Play or watch a game live, with a 2D or 3D view and play-by-play text. Replays can be
  saved, and there is an optional "Pitch by Pitch Mode."
- Or sim a day, week, or month and read full box scores and game logs.

**Under the hood**
- The engine resolves **every pitch of every game it simulates**: count leverage, the
  batter's swing and take decisions (Eye, Avoid K), contact quality (Contact/BABIP,
  Power, Gap, Stuff, Movement), batted-ball type (pitcher GB%, hitter type), fielding
  range, error and arm checks, and baserunning decisions (speed, instincts, Arm).
- **L/R splits** apply on every matchup.
- **Fatigue** builds within the game through pitch count against Stamina, and across games
  through Rest Status.
- **Day-to-day injuries** reduce effectiveness by a percentage.
- **Park factors** multiply outcomes: AVG (overall, LHB, RHB), 2B, 3B, HR (overall, LHB,
  RHB), with 1.000 as neutral.
  - Park type (open, retractable, dome) and surface (grass, turf) are part of the park
    profile.
  - The wiki states that dimensions are *purely cosmetic*: the factors drive the
    outcomes, and dimensions only flavor the play-by-play.
  - Historical factors are derived from home vs road run environments, with discrete
    factors for BABIP, 2B and 3B per ball in play, and HR per at-bat.
- **Weather**: temperature affected play in at least OOTP 22, OOTP 24 had rain-delay
  complaints, and OOTP 27 adds "dynamic weather."
- **League totals / modifiers** calibrate the whole run environment to a target era. The
  historical "Statistical Accuracy" option re-tunes these every year.

**Strategy for simulated games**
- Sliders for stealing, baserunning aggressiveness, hit-and-run, sacrifice bunt, and bunt
  for hit, plus pinch-hitting and bullpen usage tendencies.
- The manager's **style** (Conventional, Sabermetric, Smallball, Tactician, Unorthodox)
  shapes AI tactics.
- Depth charts, lineups vs LHP/RHP, and pitching roles feed the AI.

**Output**
- Box score, game log, play-by-play, a pitch-by-pitch replay, and Statcast-like batted-ball
  data (OOTP 27).
- Retention of box scores, logs, and replays is configurable per league and team.

**Why it feels deep**
- Outcomes emerge from granular events, so stats come out of the sim rather than being
  rolled directly.
- One engine serves both "watch it" and "sim 10 years," so the numbers stay consistent.

Sources:
- https://wiki.ootpdevelopments.com/index.php?oldid=2326
- https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=game_options
- https://www.ootpdevelopments.com/out-of-the-park-baseball-home/
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=personnel_ratings
- Forum snippets via search: pitch-by-pitch engine, factor derivation, strategy-slider
  meanings, OOTP 22 temperature.

## 7. Statistics, records, and history

**Stats tracked**
- Standard counting and rate stats.
- **Sabermetrics**: OOTP computes yearly league constants, much like FanGraphs' "guts"
  table, to produce wOBA, FIP, and **WAR** split for hitters and pitchers. Baserunning
  and fielding metrics include UBR, BsR, and zone rating; users have reported errors in
  some of these.
- OOTP 27 adds exit velocity, launch angle, xBA, xSLG, Barrel%, and pitch run values.

**Views**
- Splits: L/R, home/away, by month, and more.
- Game logs and career stats at every level (majors, minors, international, postseason).
  Retention can be limited to keep save files small.
- League leaders, records (single-game, season, career, franchise), and the
  **almanac / league history**: past standings, award winners, leaders, and transactions
  **[GK on exact page names]**.

**Awards**
- Season-end awards and an All-Star Game appear on the event calendar. The award set
  includes MVP, Pitcher of the Year, Rookie of the Year, Gold Glove, Silver Slugger, and
  Reliever of the Year, plus Player of the Week and Player of the Month **[GK]**.
- **Hall of Fame** voting for players **[GK: a writers-style ballot with a 75%
  threshold]**. Managers can be elected too.

**Why it feels deep**
- Every simulated pitch feeds a permanent, browsable history. Careers and records gain
  meaning over decades.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=league_events
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=manager_model
- https://www.ootpdevelopments.com/out-of-the-park-baseball-home/
- Forum snippets via search: WAR, wOBA, FIP constants and metric errors.

## 8. Team management: rosters, depth, and staff

**Organization**
- A parent club and its affiliate chain (AAA down to rookie and complex leagues).
- **Active and secondary (40-man) rosters**, minor-league **options**, **waivers**,
  **DFA**, **Rule 5**, injured lists, and September roster expansion.
- Rules are configurable per league.

**Depth and lineups**
- Lineups vs LHP and RHP, defensive depth charts by position, pitching staff roles (SP1-5,
  closer, setup, and so on), and AI auto-management per level if delegated.

**Staff**
- A parent team has 7 staff: GM, manager, bench coach, hitting coach, pitching coach,
  scouting director, and trainer. Affiliates have 3: manager, hitting coach, pitching coach.
- Staff are signed to contracts and hired from an **Available Personnel** pool. A new hire
  can sharply change the team's scouting views and development.
- What each role does:
  - **GM**: roster strategy and valuation, trade frequency and aggressiveness, loyalty to
    own players, and age preference.
  - **Manager**: personality, style, and roster strategy.
  - **Bench coach**: running and fielding development.
  - **Hitting and pitching coaches**: a focus type.
  - **Scouting director**: the 5 ratings in §2.
  - **Trainer**: heal and prevent ratings by body part, plus fatigue recovery.
- Coach profiles group ratings into Managing, Scouting, Coaching, and Trainer. In modern
  versions the exact coaching values are hidden and surfaced as per-player relationship
  and development-influence scores.

**Why it feels deep**
- Development, injury recovery, scouting, and chemistry all depend on staff. Hiring the
  staff is a strategic layer of its own.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=personnel_model
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=personnel_ratings
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=roster_rules_and_management
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=coach_profile_ratings

## 9. Transactions and AI

**Trades**
- Deals can combine players, cash, and draft picks, with **retained salary**.
- Tools include research trades, a trade block, trade proposals, and an "after the offer"
  response.
- There is a trading deadline. OOTP 24 adds a **Dynamic Trade Deadline Day**: a live,
  time-pressured event while AI teams trade at the same time.
- OOTP 13 reworked the trade AI so blatant exploits (stars for junk) fail.
- AI valuation uses a **configurable "AI player evaluation"** blend of ratings with
  current-year, last-year, and two-years-ago stats (a common setup is 25% each), plus an
  age-based projection adjustment. GM personality affects trade frequency and preferences.
- Reviewers have long criticized AI valuation in some versions, for example undervaluing
  pitchers in OOTP 16.

**Free agency**
- Eligibility comes from service time or release.
- A player choosing a team weighs money, distance from his hometown, league quality, team
  reputation and performance, **manager reputation**, playing time, morale, and
  personality.
- Teams have budget lines for "$ for FA" and "$ for Extensions."
- Compensation rules are configurable (for example Type A/B or qualifying offers).

**Contracts**
- Minor-league deals cost nothing and have no length. Major-league deals are guaranteed:
  releasing a player means paying all remaining salary.
- Contract terms can include salary that varies by year, no-trade clauses, incentives,
  and options **[GK: team, player, and vesting options; opt-outs]**.

**Arbitration**
- Eligibility at 3 to under 6 years of service, plus **Super 2** (the top 17% of players
  with 2+ years).
- The team must offer, or the player becomes a free agent. The arbitrator picks one of the
  two figures. Morale takes a hit.

**Waivers and options**: see §8.

**Draft**
- Inaugural, first-year (amateur), expansion, and Rule 5 drafts.
- The draft budget is use-it-or-lose-it. Amateur scouting drives how prospects are rated.
- Generated draft pools of high school and college players **[GK]**.

**International**
- **IAFA**: OOTP 24 adds bonus pools, pool reveals, monthly practices that build loyalty
  and scouting accuracy, and tradable pool money.
- **Posting** for foreign leagues. Military service for KBO players arrived in OOTP 26.

**Why it feels deep**
- Every transaction runs through budgets, rules, personalities, and scouted uncertainty.
- AI clubs are active market participants with their own strategies.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=trading
- https://www.ootpdevelopments.com/newsletters/nl0093/
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=player_contracts_overview
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=free_agency
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=help_43
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=player_drafts
- https://techgraphs.fangraphs.com/review-ootp-16-still-very-good/
- Search snippets on AI evaluation weights.

## 10. Finances

**Revenue**
- **Gate**: ticket price × attendance. The home team keeps 80% and the visitor gets 20%.
  Attendance is driven by market size, **fan loyalty**, and **fan interest** (winning,
  popular players).
- **Media**: tied to market and interest, but mostly to the league's average and fixed
  media-contract settings.
- **Merchandising**: from performance and popularity.
- **Playoff gate**.
- **Revenue sharing**, received or paid.
- **Owner cash infusions**, at the owner's discretion.
- **Cash received in trades.**

**Expenses**
- Player salaries, staff salaries, cash sent in trades, the scouting budget (per bucket),
  revenue-sharing payments, and the separate draft and international budgets.

**Budget models**
- **Owner-set budget**: arbitrary by owner.
- **Revenue-based**: the GM may spend up to total revenue, but overspending can get the
  GM fired.

**Settings**
- A **financial coefficient** scales all money to an era.
- League-level salary floors, caps, luxury tax, and minimum salary **[GK]**.
- In historical leagues, finances can be realigned each year.
- Ticket price is user-set **[GK]**.

**Why it feels deep**
- The feedback loop: winning raises interest and attendance, which raises revenue,
  budget, and payroll.
- Market size limits ambition. The owner's money is not your money.

Source: https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=the_team_financial_model

## 11. Career / GM mode

**Roles**
- Manager only, GM only, or both. You can also start as commissioner, as owner, or in the
  minors. You can claim a job or start unemployed.

**Reputation**
- **11 ranks**, starting from "greenhorn."
- Built from lifetime record, playoff appearances, titles, and experience.
- Quitting mid-season hurts how owners see you, even if the rank itself doesn't change.

**Jobs**
- The Available Jobs list shows only teams willing to consider you. Their decision weighs
  your reputation, track record, how you treated past owners, and whether minor-league
  experience is needed.
- AI owners "have their own agendas" and may hire a less qualified candidate.
- Unsolicited offers arrive by message. You apply with one click; there is no negotiation.

**Owner goals and job security**
- Goals used to be mostly win-based (a winning record, the playoffs, a title).
- Newer goals are dynamic and situational, for example "trade for a power hitter," then
  "re-sign him long-term."
- A job-security meter tracks how you stand **[GK on the exact UI]**. Financial
  irresponsibility under the revenue model can get you fired.
- There is a manager score, manager achievements, and a manager Hall of Fame.

**Why it feels deep**
- Your career is its own arc, with constraints from people who are not you: owners and
  other teams' hiring.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=manager_model
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=manager_reputations
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=getting_hired
- https://www.osftw.com/news/829272/out-of-the-park-baseball-16-manager-mode-details-and-more

## 12. League structure and historical mode

**Setup**
- Any structure: leagues, sub-leagues, divisions, affiliates, foreign leagues,
  promotion/relegation, tournaments.
- League-level rules for rosters, finances, free agency, arbitration, and DH.
- Expansion drafts.

**Historical leagues**
- **Real transactions and lineups**: forced, which disables roster, injury, and suspension
  rules. With these on and 1-year recalculation, a season replays very close to real life.
  Each switch you turn off pushes the timeline further from reality.
- **Automatic expansion** at real dates, era-based **strategy adjustment** (steal rates and
  so on), annual **finance realignment**, historical retirement, and missed seasons such as
  military service.
- **Rookies**: auto-import of real rookies, or "random rookies from all eras," normalized.
- **Statistical accuracy**: league-total modifiers re-tuned every year.
- **Ratings from stats**:
  - Recalculated after each season from 1, 3, or 5 years, with an option to double-weight
    the current year.
  - Current ratings come from real stats (Lahman plus park factors) or from neutralized
    stats.
  - **Potential** comes from career totals, remaining career (described as the most
    accurate), peak seasons, or remaining peak seasons.
  - Rookie fielding and stamina bases are chosen separately.
- OOTP 26 improved the historical ratings engine.

**Why it feels deep**
- A slider from "exact replay" to "free alternate history," with the engine calibrated to
  each era.

Sources:
- https://wiki.ootpdevelopments.com/index.php?oldid=2186
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=important_game_concepts

## 13. News, storylines, awards, milestones, and media

**News feed**
- Auto-generated articles on games, transactions, injuries, awards, and milestones.
- The league calendar drives the off-season news cycle: preseason, spring training,
  opening day, the draft, the All-Star Game, the deadline, roster expansion, awards, the
  free-agency filing period, arbitration hearings, Rule 5, and the winter meetings.
- These events are also **auto-play stop points**.

**Storylines** (since OOTP 11, overhauled in OOTP 13)
- Scripted, often interactive, off-field events that can carry real consequences:
  injuries off the field, an age controversy, a TV commercial, a star complaining to the
  media during a slump.
- In the media-complaint example you choose to fine him, ignore it (and risk losing the
  clubhouse's respect), or label him a cancer and release or trade him.

**Popularity**
- Player popularity feeds morale reactions to transactions and feeds merchandise revenue.

**Why it feels deep**
- The world narrates itself, and occasional choices with consequences turn the numbers
  into stories.

Sources:
- https://www.ootpdevelopments.com/newsletters/nl0094/ (search snippet)
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=league_events
- https://manuals.ootpdevelopments.com/index.php?man=ootp22&page=player_morale

## 14. UI and data depth, and how large worlds sim quickly

**Screens**
- Player profile: ratings, scouting report, stats, splits, logs, contract, injuries,
  morale, personality clues, development tab, and history.
- Team pages: roster, depth chart, finances, staff, transactions, chemistry.
- League pages: standings, leaders, history, almanac, awards, Hall of Fame.
- Custom views and filters let users build their own data tables, for example showing
  personality on a 5-level scale.

**Rating display**
- Many user-chosen scales, colored bands, and stars. True values are hidden behind
  scouting.

**Simulating large worlds**
- Every game uses the same pitch-level engine. The main costs are the number of leagues
  and players and how much data is *kept*.
- Users trim costs by:
  - limiting career split, fielding, and postseason stat retention to "ML only" or none;
  - saving box scores, game logs, and replays only for chosen leagues and teams;
  - minimizing the number and size of leagues.
- Measured speeds:
  - OOTP 17 was about 30% faster than OOTP 16; one large league simmed a year in about
    30 minutes versus 53.
  - A historical setup with 48 minor-league teams across 6 leagues took about 45 seconds
    per off-season day.

**Lesson for us**: simulate everything with one engine, but keep the *detailed artifacts*
(full logs and replays) only for what the player is watching. Store aggregates for the
rest.

Sources:
- https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=game_options
- Search snippets (forums.ootpdevelopments.com p=4193259 and related) on sim speed.

---

## What makes OOTP deep: principles

1. **Hidden truth, scouted perception.** Every player has true ratings. The user sees a
   scout's noisy, biased estimate, and the error depends on budget, staff, age, and region.
2. **Current vs potential, both mutable.** Potential is a forecast that moves (TCR,
   injuries, focus), not a fixed ceiling.
3. **Atomic simulation, emergent statistics.** Pitch-level events produce every stat, so
   stats and ratings agree but are not the same thing.
4. **Each rating has a narrow, legible effect.** Eye affects walks; Power affects HR.
   Users can reason about cause and effect.
5. **Context-relative valuation.** OVR/POT are relative to position and league, and splits
   and park factors make value depend on the situation.
6. **Environment as a multiplier.** Parks, era league totals, weather, and level of
   competition all scale outcomes.
7. **People drive outcomes.** Staff with styles and hidden quality shape development,
   health, scouting, and tactics. Hiring them is strategic.
8. **Personality plus morale plus chemistry.** Players have wants (role, money, winning,
   loyalty) that create friction with optimal play.
9. **Rules-faithful transactions.** Service time, options, waivers, arbitration, budgets,
   and compensation create real constraints and timing puzzles.
10. **A closed economic loop.** Winning raises interest, which raises revenue and budget,
    which raises talent. Market size and the owner bound it.
11. **Your career is a game too.** Reputation, owner goals, firing, and job offers sit
    above the team layer.
12. **A living world.** AI teams trade, sign, draft, and fire. News and storylines narrate
    it. A calendar of events paces the year.
13. **Long memory.** Records, almanac, Hall of Fame, and career logs make decades of play
    meaningful.
14. **Everything is a setting.** Randomness, aging speed, injury rates, accuracy, scales,
    and history fidelity are all tunable, from "exact replay" to "chaos."
15. **Weighted randomness everywhere, never pure determinism.** Players get levers, never
    guarantees.

---

## Mapping: OOTP system to its racing equivalent

| OOTP system | Racing equivalent (suggestion) |
|---|---|
| Pitch-by-pitch engine | **Lap-by-lap engine** (sector-by-sector or corner-segment for key races). Per-lap pace = driver skill × car setup × tire state × fuel load × track condition × traffic, with discrete events (passes, mistakes, contact, cautions, pit cycles) |
| Batting/pitching rating list with narrow effects | Driver ratings with legible effects: **Raw pace** (qualifying), **Racecraft** (passing and defending), **Consistency** (lap-time variance), **Tire management** (degradation), **Fuel saving**, **Restarts**, **Wet/dirt car control**, **Aggression** (pass attempts vs contact risk), **Composure** (mistakes under pressure), **Feedback** (setup quality), **Fitness** (late-race fade), **Ovals vs road courses vs short tracks vs dirt** splits, mirroring L/R splits |
| Current vs potential, both mutable | Current/potential per skill; potential moves with seat time, crashes, and coaching (TCR equivalent) |
| OVR/POT stars relative to position/league | Stars relative to **series level and discipline** (a 4-star Late Model driver may be 2 stars in Xfinity) |
| L/R splits | **Track-type splits**: short oval, intermediate, superspeedway, road course, street, dirt; plus surface/banking |
| Park factors + weather | **Track characteristics**: length, banking, surface abrasiveness (tire wear), grip evolution, passing difficulty, caution likelihood, pit loss time; **weather**: temperature (grip), rain (wet tires or postponement), wind on superspeedways |
| League totals / era modifiers | Era calibration: car-of-the-era pace spread, reliability rates, caution frequency, pit-stop length, so 1995 and 2026 races both look right |
| Fatigue / Rest Status, pitch counts | **Driver fatigue** (heat, race length), **equipment wear** (engine and gearbox mileage, chassis condition), **crew fatigue** on doubleheader weekends |
| Injuries (DTD/Out/career-ending, body areas, proneness) | Crash injuries (concussion protocols, fractures), with **concussion history as re-injury memory**; "DTD" = racing hurt with a pace penalty; a career-ending injury forces retirement; **car damage** is a parallel injury system for equipment |
| Trainer | **Medical / fitness coach** (recovery speed, injury prevention, endurance) |
| Scouting (director ratings, budget, OSA, accuracy by age/region) | **Talent scouting/driver evaluation**: the team's driver-development director with Scout Ovals / Road / Dirt / Juniors (karting) / International ratings plus a Projection style; a budget per ladder tier; a public baseline (**media/rankings**, like OSA); kids in karting and Legends cars are hardest to read |
| Development engine (coaching, playing time, challenge level, Dev Lab, focus sliders) | Development from **seat time**, **competition level** (dominating a weak series stalls growth), **driver coach and simulator program** (focus sliders: qualifying pace vs tire management vs racecraft), an **off-season test/sim "Development Lab"** (programs: "learn road courses," "dirt car control," "fitness block") |
| Aging curves | Discipline-specific peaks (open-wheel earlier, stock car and endurance later); reflexes decline, experience compounds |
| Personality (leadership, loyalty, greed, work ethic, intelligence, desire to win) | Driver personality: **Sponsor-friendliness/marketability**, **Loyalty**, **Greed**, **Work ethic** (sim/test hours), **Racing IQ**, **Temperament** (feuds, retaliation, penalties), **Desire to win** |
| Morale (role vs expectation) and chemistry | Morale from results, **equipment parity vs teammate**, role (lead driver vs development seat), contract security; **team chemistry** among drivers, crew chief, and engineers; teammate feuds |
| Roster / 40-man / minors / options | **Team driver stable**: Cup and national seats, plus **development contracts** in lower series (ARCA, trucks, Late Models, Indy NXT), loan-outs to partner teams, **"option" years**, and the release-or-reserve decision |
| Depth chart / lineups | Seat assignments per event, reserve/backup driver, part-time schedule splitting (car shared by multiple drivers) |
| Coaches/staff with ratings, hiring/firing | **Crew chief** (strategy calls, setup, matching driver "style": loose vs tight preference), **race engineer / car chief** (setup), **spotter** (traffic awareness, wreck avoidance, restart help), **pit crew** (stop time mean and variance, error rate), **engine builder** (power vs reliability), **driver coach**, **team manager** |
| Manager style/strategy sliders | Crew chief strategy sliders: pit aggressiveness (two tires vs four, fuel-only, staying out), qualifying vs race setup bias, risk tolerance late in a race |
| Trades, trade AI | **Seat swaps / driver-for-driver team moves**, buyouts, selling sponsor packages and charters, development-driver loans; AI teams value drivers by a blend of ratings and recent results (the OOTP "AI evaluation" weights) |
| Free agency / contracts / arbitration | Driver contracts (years, salary, **performance bonuses**, sponsor-bring requirements, release clauses, options); **silly season** as the free-agency period; drivers weigh money, equipment quality, team results, hometown/series location, crew chief reputation; no arbitration, but **contract-year leverage** plays a similar role |
| Waivers / DFA | Releasing a driver mid-contract (pay out), parking a car, selling a charter |
| Draft / IAFA | No draft; instead **driver-search programs, karting championships, shootouts, and academies** (Ford/Toyota/Chevy development programs, F1-style junior academies) with **signing budgets**, like the IAFA bonus pool |
| Finances (gate, media, merch, rev sharing, owner cash) | Purse/prize money, **charter/TV revenue share**, **sponsorship** (primary, associate, per-race), merchandise from driver popularity, manufacturer support, owner cash; expenses: chassis, engines (lease vs build), tires, travel, crew salaries, crash damage |
| Fan interest/loyalty, market size | Driver and team **fan base and popularity** (regional to national), track-attendance draw, sponsor appeal |
| Owner goals / job security | **Team owner or sponsor goals**: top-10 points finish, make the playoffs, win a race, develop driver X; sponsor renewal depends on exposure and results |
| Career/GM mode, reputation, job offers | Play as driver, crew chief, or team owner; **reputation ranks** from local bullring to national; job offers come from teams seeing your results and reputation; quitting mid-season hurts reputation |
| WAR | **Racing value metric**: a "points/positions above replacement" figure, i.e., driver finishes vs an expected finish for that car's equipment level (Wins Above Replacement Driver), with an equipment-adjusted pace delta; also **pass differential**, **quality passes**, and **average running position** (Loop Data-style stats) |
| Splits, logs, records, almanac | Per-track-type splits, race logs (lap charts, running order, pit stops), records by track and series, a season almanac, a historical database since 1995 |
| Hall of Fame / awards / milestones | Rookie of the Year, Most Popular Driver, series championships, milestones (first win, 100th start), HOF ballots |
| Storylines / news | Feuds, sponsor scandals, post-race penalties, tech-inspection failures, "driver confronts rival on pit road" choices (fine, defend, or release), family-owned team sale rumors |
| Historical mode (ratings from stats) | Already planned: real 1995+ seasons; ratings derived from historical results (finishes adjusted for team equipment; 1/3/5-year bases; potential from remaining career), with era calibration and an "exact replay" option (real driver changes and schedule) |
| Fast sim of minor leagues | Simulate lower-tier races (local Late Model, weekly shows) with a **coarse model** (stint- or result-level, from ratings plus a variance model) and keep full lap-by-lap only for watched or national races; retain only aggregates and race results for weekly series |
| Calendar of league events / stop points | Racing calendar: preseason testing, the season opener, the playoff cutoff, silly season, banquet/awards, the rules package announcement, the sponsor renewal window |
| Settings for randomness/injury/accuracy | Difficulty and realism settings: crash frequency, mechanical failure rate, development speed, scouting accuracy, rating scale, history fidelity |
