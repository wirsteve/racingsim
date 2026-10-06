"""Static method/coverage section appended to REPORT.md by 60_outputs.py."""

TAIL = r"""## Sources and how they were used

| source | kind | what it gave |
|---|---|---|
| IMCA track directory (`src:imca-track-directory`) | official sanctioning body | 173 IMCA-sanctioned weekly tracks (2026): size & surface, divisions, address, geocoded map marker. Read through the page's own public DataTables endpoint; robots.txt allows all. |
| WISSOTA current tracks (`src:wissota-tracks`) | official sanctioning body | 48 member tracks (2026) with size, banking wording and surface; each links to its MyRacePass profile (coordinates). |
| NASCAR Local Racing Series 2026 track list (`src:wp-nascar-local-racing-series`) | wiki (nascar.com is blocked) | 46 member tracks: attribution, surface, size, active-2026 status. |
| MyRacePass track profiles (`src:myracepass`) | results platform | Hosts WISSOTA, USRA, ASCS, POWRi, USMTS and many weekly tracks; profiles are kept by the tracks. Gives size, banking (flat / slightly / semi / high banked), composition, shape, map location and the dates of the latest listed events (used to check 2025/2026 activity). Every North American profile in the A-Z index was fetched once, >= 2.5 s apart (robots.txt allows /tracks/). |
| Wikipedia articles (`src:wikipedia`) | wiki | ~690 venue articles from `Category:Motorsport venues in the United States/Canada/Mexico` (depth 4, drag/motocross/horse subcategories excluded) plus every article linked from the lists below: infobox layouts (length, surface, turns, banking), opened/closed, former names, events, coordinates. |
| Wikipedia lists (`src:wp-list-*`) | wiki | US auto racing tracks (all tables incl. defunct), US/Canada dirt ovals, Canada, Mexico, NASCAR tracks (with seasons), American championship car tracks, NC sports venues. Rows without articles are kept, with coordinates only when the list gives them or another source matches. |
| Wikidata (`src:wikidata`) | wiki | SPARQL over items in USA/CAN/MEX that are (subclasses of) race track / motorsport racing track or whose sport is motorsport / auto / stock-car / dirt / oval racing; wbgetentities for every QID seen: P625, P2043, P571/P1619, P576/P3999, aliases. |
| frwiki / eswiki | wiki | Quebec and Mexican circuit articles (coordinates, QIDs) to confirm and locate venues. |
| Nominatim / OpenStreetMap (`src:nominatim-osm`) | dataset (ODbL) | Gazetteer only: (a) locating a list-only venue when an OSM race-track-type feature with a matching name exists in the right state, (b) reverse geocoding city/state for records with coordinates but no town, (c) tie-breaking conflicting coordinates by the stated town. >= 3 s between requests, cached, backs off on 429. |

Blocked or unusable sources are in `unavailable.json` (NASCAR.com, USRA, NASA/drivenasa, INEX, Overpass API, DIRTcar/UMP, QMA track list, racing-reference, thethirdturn, web-search budget).

## Pipeline (re-runnable)

```
cd knowledge/tracks
python3 -I scripts/01_wp_categories.py      # category crawl -> raw/wp_category_pages.json
python3 -I scripts/02_wp_lists.py           # list articles  -> raw/wp_list_entries.json
python3 -I scripts/03_wp_pages.py           # wikitext/coords/QIDs -> raw/wp_pages.json
python3 -I scripts/04_wikidata.py           # SPARQL + entities -> raw/wd_*.json
python3 -I scripts/05_fr_es_pages.py        # frwiki/eswiki -> raw/wp_fr_es_pages.json
python3 -I scripts/10_imca.py               # IMCA directory -> raw/dir/imca_tracks.json
python3 -I scripts/11_wissota_nascar.py     # WISSOTA + NASCAR local list
python3 -I scripts/20_mrp_index.py          # MyRacePass A-Z index
python3 -I scripts/21_mrp_tracks.py         # MyRacePass profiles (resumable, ~2.5 h)
python3 -I scripts/30_wp_candidates.py      # parse Wikipedia/Wikidata venues
python3 -I scripts/40_candidates.py         # normalise all sources -> raw/cands.json
python3 -I scripts/50_build.py --geocode    # cluster, match existing, resolve fields
python3 -I scripts/60_outputs.py            # deliverables + this report
```
All fetches are cached under `raw/`; a re-run only downloads what is missing.

## Deduplication and matching rules

* **Identity links**: same Wikipedia title (after resolving redirects), same Wikidata QID, same MyRacePass id. A list link is trusted only if the row's name resembles the target title or one of its former names (core-token Jaccard > 0.5). This stops e.g. *New Asheville Speedway* (a redirect) being merged into *Asheville-Weaverville Speedway*, or *Bay Meadows* inheriting a list row's copied Arizona coordinates.
* **Cannot-link**: two different Wikipedia articles, or two different IMCA entries, are never merged; nor is an article's second racing surface with its primary one.
* **Spatial**: within 2 km and name similarity >= 0.6 (core tokens; generic words such as *speedway/raceway/county* ignored), or within 0.5 km from different sources when type and surface agree (renamed venue). Never merged: dirt vs paved unless the names are identical (venues get paved or return to dirt), oval vs road course with different names, drag strip vs circuit, two ovals whose lengths differ by > 1.6x (separate tracks at one complex, e.g. a bullring beside a superspeedway).
* **Same name, same state, coordinates 2-80 km apart**: merged and flagged; the coordinate group backed by more independent sources wins, coordinates shared by two differently named Wikipedia articles are distrusted, ties are broken by distance to the stated town.
* **No coordinates**: attached by exact normalised name/alias in the same state, or near-identical spelling with the same core tokens; otherwise the venue stays in `tracks_unresolved.json`.
* **Existing tracks** (all data/tracks/*.json, 408 ids at build time): matched by shared Wikipedia article URL, then name/alias in the same state, then <= 2 km with similar name and compatible surface/type. Matches go to `tracks_enrich.json` (with `match_basis`), never to `tracks_new.json`.
* **Multiple layouts**: one record per facility, layouts summarised in `configuration`; a second record only for a dirt/paved surface that exists alongside the primary one (historic or temporary surfaces such as Bristol's 2021-23 dirt are not split).

## Field rules

* `surface`: the current official directory (IMCA, WISSOTA, MyRacePass, NASCAR 2026 list) beats the encyclopedia; disagreement is noted. `clay` is kept as published (the merge tool folds it into `dirt`).
* `length_mi`: Wikipedia infobox > list table > IMCA/WISSOTA/MyRacePass fractions ("3/8 mile" = 0.375).
* `banking_category`: from degrees when known (flat < 8, moderate 8-16, high > 16), else the directory wording (*flat / slightly banked* = flat, *semi / progressive banked* = moderate, *high banked* = high), else `unknown`.
* `active`: `true` only with evidence of racing in 2025/2026 (`status_verified_year`, `status_sources`); `false` with a closure year, defunct category/shading or list closure and no recent racing; otherwise `null`. A closure year read from article prose is marked low confidence in `notes`. Inactive venues with no known closure year are not published (the game would treat them as open until 2015); they are in `tracks_unresolved.json`.
* `level`: international (Formula One / Formula E / WTCC), national (NASCAR national series, NASCAR Canada/Pinty's, CASCAR, NASCAR Mexico, AAA/USAC/CART/IndyCar championship cars, IMSA, Trans-Am, ARCA, World of Outlaws, Lucas Oil Late Models, USAC national midgets...), regional (other touring series), else local. For operating tracks only current or post-2000 series count: a one-off 1950s Grand National race appears in `major_series` (with years) and in prestige, but does not make a weekly bullring "national".
* `prestige_category`: high = national-championship racing now or for >= 5 seasons; medium = regional series or brief national use; low = local weekly. `iconic` is never assigned automatically. Basis in `prestige_basis`.
* `disciplines`: mapped from the class names a track runs (MyRacePass events, IMCA divisions) and from series/categories (e.g. *IMCA Modified* -> modified, *Hobby Stock* -> street_stock, *Late Model* on dirt -> dirt_late_model).
* `confidence`: high = coordinates from an encyclopedia/official/directory source and >= 2 independent source families (wiki, official directory, MyRacePass, lists); medium = one strong source; low = coordinates only from the gazetteer, conflicting coordinates/surfaces, or a closure year inferred from prose.

## Coverage estimate

How many venues probably exist (orders of magnitude, low confidence):

* Wikipedia's dirt-oval list cites the National Speedway Directory's figure of **700+ dirt ovals operating in the US**; MyRacePass alone indexes ~2,400 North American profiles (including fairgrounds, drag strips, kart and quarter-midget tracks, and many dormant profiles).
* Paved ovals operating in the US are commonly put at a few hundred (roughly 300-400); permanent road courses about 100; Canada roughly 100-150 active ovals and circuits; Mexico roughly 20-30 permanent circuits.
* So an estimated **1,100-1,400 active car-racing venues** in North America (ovals + road courses, excluding drag strips, mud bogs and pure kart tracks), plus thousands of closed venues.

The best-covered segment is Midwest/Plains dirt (IMCA, WISSOTA, MyRacePass); the weakest is paved weekly tracks in the Southeast and Northeast whose promoters do not use MyRacePass, and Mexican/Quebec local tracks.

## Known gaps / next steps

* NASCAR.com's weekly-series directory, USRA, NASA and INEX could not be read (see `unavailable.json`); the 2026 NASCAR member list came from Wikipedia instead.
* Several hundred venues are known by name only (`tracks_unresolved.json`, reason *no coordinates*): mostly list rows and dormant MyRacePass profiles. An OSM extract (the dataset agent's job) can place many of them.
* Kart tracks and quarter-midget clubs are covered only where they appear on MyRacePass; the QMA club list gives towns only.
* Banking degrees are known for only a small share of local tracks; directory banking categories fill part of the gap.
* MyRacePass shows only the latest few events; a track with no events listed has `active: null`, not `false`.
* Nominatim answered 429 (rate limit, shared egress) a few times; the geocoder backs off 90 s and stops after three refusals, so some list-only venues were never looked up.
* MyRacePass "ZZZ_" profiles (84) are archived duplicates and are ignored.

## Touring venues the coordinator asked about (lookup results, 2026-10-06)

| venue | result |
|---|---|
| Tri-County Motor Speedway / Tri-County Speedway, Hudson NC | `tri-county-speedway-nc` (new): 35.81194, -81.52528 (Wikipedia list; MyRacePass map agrees within 0.1 km), 0.4 mi asphalt, racing listed 2026, confidence high |
| Tri-County Speedway (NC) - other | the only other NC "Tri-County" is `tri-county-race-track-nc`, Brasstown NC, 35.03291, -83.95362, 3/8 mi, racing 2026 (MyRacePass) |
| Summerville Speedway (SC) | MyRacePass profile exists (Summerville, SC; tracks/2645) but gives no map, size or surface; not in OSM by name; unresolved |
| Thunder Hill Raceway (TX) | MyRacePass profile (Kyle, TX; tracks/1903) without map/size; not in OSM by name; unresolved. (Two different Thunder Hill *Speedways* - Mayetta KS and Menomonie WI - are in tracks_new.) |
| Carteret County Speedway / Carteret Motor Speedway (NC) | `carteret-county-speedway-nc` (new): Swansboro NC, 34.72716, -77.06352, 0.4 mi asphalt, racing 2026 |
| Cordele Motor Speedway (GA) | `cordele-motor-speedway-ga` (new): 32.00778, -83.76852, 0.4 mi asphalt, racing 2026 |
| Shady Bowl Speedway (OH) | known from the Wikipedia US list (0.3 mi asphalt, De Graff OH) and MyRacePass (no map); no coordinates found; unresolved |
| CNB Bank Raceway Park (PA) | not found on Wikipedia, MyRacePass or OSM under that name; unresolved (no location guessed) |
| Corrigan Oil Speedway (MI) | `corrigan-oil-speedway-mi` (new): Mason MI, 42.60488, -84.48613, 1/4 mi asphalt, racing 2026 |
| Lonesome Pine International Raceway (VA) | `lonesome-pine-raceway-va` (new): Coeburn VA, 36.93349, -82.50966, 3/8 mi asphalt, racing 2026, NASCAR Local Racing Series 2026 member (alias Lonesome Pine Motorsports Park) |
| Twin State Speedway (NH) | Wikipedia redirects it to Claremont Motorsports Park (existing id `claremont-motorsports-park-nh`, 43.39194, -72.35194); not auto-added as an alias because redirect targets are not trusted without a name match |
| New River All-American Speedway (NC) | same site (0.19 km) as existing `coastal-plains-raceway-nc` (Jacksonville NC, list coords 34.808, -77.499, 0.4 mi asphalt); added as an alias in tracks_enrich |
| Goodyear All-American Speedway (NC) | not found in any source under that name; unresolved |
"""
