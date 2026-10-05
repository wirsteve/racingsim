# Licensing / IP Review

**Status:** living document. Last reviewed alongside the first implementation of
the career ecosystem and track database.
**Context:** racingsim is a personal project that is not being published or
distributed. The risks below only matter if that ever changes; the safe
abstractions stay in place because they cost little, but nothing here blocks
using real names locally.

**Not legal advice.** This is an engineering risk register: it records what the
game uses from the real world, why, the safer abstraction we chose where risk
was unclear, and what a lawyer should confirm before any commercial release.

Guiding policy (requirement R7):

1. Use publicly known **facts** to make the world recognisable.
2. Never depend on proprietary assets or present the game as an officially
   licensed product.
3. When unsure, pick the safer implementation that keeps as much realism as
   possible, flag it here, and keep building.

---

## 1. Summary table

| # | Item | What we do now | Risk | Safer fallback already supported? |
|---|------|----------------|------|-----------------------------------|
| 1 | Real track **names** | Plain-text names of real venues, used factually | Low–Medium | Yes: `display_name` override in `data/track_rating_overrides.json`; saves use stable IDs |
| 2 | Track **facts** (location, length, surface, banking, opening year) | Stored with source URLs | Low | n/a (facts are not protectable) |
| 3 | Track **simulation ratings** | Our own derived model, labelled "not official" | Low | n/a |
| 4 | Track **logos, layouts as artwork, photos, maps** | **Not used** | High if used | n/a |
| 5 | Sanctioning-body & series names (NASCAR, IndyCar, ARCA, IMSA, SCCA, USAC, World of Outlaws, …) | **Not used in game data.** Series are fictional ("Premier Stock Car Cup") | High if used | Yes |
| 6 | Event names (e.g. famous crown-jewel races) | **Not used.** Fictional event names at real venues | Medium–High if used | Yes |
| 7 | Real **people** (drivers, owners) | **Not used in game.** All people are procedurally generated; a blocklist prevents generating famous real driver names | High if used | Yes |
| 8 | Real **teams** | **Not used.** Generated team names | High if used | Yes |
| 9 | Real **manufacturers / brands** | **Not used.** Four fictional manufacturers | High if used | Yes |
| 10 | Real **sponsors / consumer brands** | **Not used.** Generated sponsor names | High if used | Yes |
| 11 | Real people / series named in **research docs** | Named in `MOTORSPORTS_RESEARCH.md` and `docs/research/` as factual citations | Low (internal documentation, factual, cited) | Keep research docs out of the shipped game build |
| 12 | Real-world economic figures (budgets, purses) | Used to calibrate, presented in game only as fictional series economics | Low | n/a |
| 13 | Rule structures (age-by-track approval, Pro-Am driver categorisation, scholarships ladders) | Re-implemented as generic game mechanics with our own names | Low | n/a |

---

## 2. Details and decisions

### 2.1 Real track names (flag: **review before release**)
- **Decision:** use real names in a restrained, informational way, as deep sports
  management games commonly reference real venues. The game must not show track
  logos, official artwork, sponsor title names of venues, or imply endorsement.
- **Concerns:**
  - Many venue names are registered trademarks, and some include corporate
    naming rights (e.g. a sponsor's name embedded in the venue's current
    commercial name). We store the **commonly used/canonical name** and avoid
    sponsor-bearing naming-rights titles where a neutral name is in common use.
  - A few venues trade on their name as a brand (e.g. famous speedways). Using the
    name to identify the place where fictional races happen is a nominative/factual
    use, but this should be confirmed by counsel for the target markets.
- **Safe fallback:** the track layer is data-only. A release build can apply a
  `display_name` override table to rename any venue without touching
  facts, ratings or saves (saves reference stable track IDs, not names).
- **Done:** naming-rights names were replaced with neutral common names on import
  (e.g. "Atlanta Motor Speedway", "Road Atlanta", "Laguna Seca Raceway",
  "Gateway Motorsports Park", "Mosport Park"); commercial names are kept only in a
  search-only `aliases` field. See `docs/research/track_dataset_notes.md`.
- **Still flagged:** venues whose *only* common name contains a brand or company
  name: "Lucas Oil Speedway" (Wheatland, MO), "Trackhouse Motorplex" (a race team's
  name on a kart venue), "The Thermal Club", "Jukasa Motor Speedway". Kept as-is
  for now (factual identification); candidates for `display_name` overrides.
- **Action items:** legal review of the top ~60 national venues' names.

### 2.2 Track facts
- Location, length, surface, banking, configuration, opening year and active
  status are public facts. Each record keeps its `sources` list.
- We never copy track **maps/diagrams** or textual descriptions verbatim from
  official sites; `configuration` and `notable_note` are short paraphrases.
- Unknown values are stored as `null` rather than guessed.

### 2.3 Track simulation ratings
- All ratings (passing difficulty, tyre degradation, drafting effect, …) are
  **internal game ratings** computed by `racingsim/tracks/ratings.py` plus hand
  tuning in `data/track_rating_overrides.json`.
- The game UI should label them as game ratings. They are not represented as
  measurements or official specifications.

### 2.4 Series, sanctioning bodies and events
- **Decision:** fictional names for every championship ("Premier Stock Car Cup",
  "Formula Lights Championship", "Outlaw 410 Sprint Car Tour") and for crown-jewel
  events held at real venues ("Gulf Coast Super Late Model Classic").
- Structural mechanics inspired by public rules (minimum ages per track size,
  advancement scholarships, Pro-Am driver categories) are implemented generically.
  Game mechanics are not protectable by trademark; we avoid copying rulebook text.
- The real-world analog of each fictional series is documented **only** in
  `MOTORSPORTS_RESEARCH.md` for designers. That mapping must not be surfaced in
  the shipped UI or marketing.
- **Flag:** some fictional names are generic descriptive phrases ("National Truck
  Series"). Before release, run a trademark search on each final series name.

### 2.5 People, teams, manufacturers, sponsors
- Everything is procedurally generated. `racingsim/world/names.py` contains a
  `REAL_NAME_BLOCKLIST` so the generator never produces the exact name of a
  well-known real driver; extend this list as needed.
- Manufacturer names (`Aurora Motors`, `Bridgeline Automotive`, …) and national
  sponsor names are invented. **Flag:** run a clearance search on these invented
  names before release; replace any that collide with real companies.
- A future "real roster" mod (if ever wanted) must be a user-supplied data pack,
  not shipped content.

### 2.6 Research documents
- `MOTORSPORTS_RESEARCH.md` and `docs/research/*.md` name real drivers, teams,
  series and sponsors, with citations. This is factual research documentation
  inside the source repository, not game content. Keep it out of shipped builds.

### 2.7 Data sources
- Primary sources were Wikipedia, sanctioning-body and track websites, and motorsport
  journalism, cited per fact. We store facts, not copied prose.
- **Flag:** Wikipedia content is CC BY-SA. We extract facts (not protectable) and
  write our own short descriptions; we do not ship copied article text.

---

## 3. Open questions for counsel

1. Nominative use of real venue names in a commercial management sim in the U.S.,
   Canada, U.K., EU and Australia.
2. Whether any venue requires a licence to be named in a game (some venues
   license their names/likeness for racing games, which tends to imply that
   licensing is *available*, not that it is *required* for factual reference).
3. Clearance of final fictional series, manufacturer and sponsor names.
4. Whether the in-game use of public rule structures needs any disclaimer.

## 4. Recommended UI disclaimer (draft)

> racingsim is not affiliated with, endorsed by, or sponsored by any racing
> series, sanctioning body, team, manufacturer or venue. Real venue names are used
> for identification only. All drivers, teams, series, manufacturers and sponsors
> are fictional. Track characteristics shown in the game are internal game ratings.
