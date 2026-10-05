# Track Dataset Notes

How the real-world track database (`data/tracks/*.json`) was researched, what it
covers, and its known data-quality caveats. Each record carries its own
`sources` list (510 source URLs across 312 venues).

## Coverage (first pass)

| Measure | Count |
|---|---|
| Venues | **312** (269 USA, 29 Canada, 14 international) |
| Level | 99 local · 134 regional · 63 national · 16 international |
| Type | 219 ovals · 75 road courses · 13 street circuits · 2 rovals · 3 kart circuits |
| Surface | 199 asphalt · 95 dirt/clay · 12 concrete or mixed · 6 undocumented |
| Status | 18 inactive (kept for history) · 4 unconfirmed |
| Geography | 45 US states, 8 Canadian provinces |

Files:

* `major_venues.json`: every 2024–26 NASCAR national-series and IndyCar venue,
  IMSA/SCCA major road courses, 26 premier dirt ovals, regional paved short tracks
  that host major events, and 14 international circuits for future expansion.
* `local_regional_venues.json`: grassroots asphalt short tracks, dirt tracks,
  club road courses, kart circuits and quarter-midget tracks, deliberately spread
  so every region has its own ecosystem (Carolinas/Virginia late model tracks,
  Wisconsin/Michigan asphalt, New England modifieds, NY/PA dirt, Indiana sprint
  tracks, Iowa/Plains IMCA tracks, the Southeast dirt late model belt, West Coast,
  Pacific Northwest, Ontario, Quebec and the Maritimes).

## Sources

Wikipedia infoboxes and article text (via the Wikipedia API), The Third Turn wiki
(structured short-track pages), official track websites, racingcircuits.info for
road-course layouts, and OpenStreetMap/Nominatim for coordinates.

## Normalisation applied when importing

1. **Neutral names over naming-rights names** (see `LICENSING_IP_REVIEW.md`):
   e.g. "Atlanta Motor Speedway" (not the current sponsor name), "Road Atlanta",
   "Laguna Seca Raceway", "Indianapolis Raceway Park", "Gateway Motorsports Park",
   "Mosport Park", "California Speedway". Commercial names are kept in `aliases`
   for search only.
2. **Duplicates across the two research files** (24 venues) were merged into the
   major-venue record, keeping all source URLs. Distinct venues sharing a site
   (Las Vegas oval vs. its bullring, Nürburgring GP vs. Nordschleife, Daytona oval
   vs. road course) are separate records.
3. **Street-circuit surfaces** with no documented surface were recorded as paved
   mixed asphalt/concrete (they run on public roads) and flagged in
   `configuration`.
4. **Opening years** can predate motor racing where a fairground horse track was
   converted (Knoxville 1878, Stafford 1870); notes say so.

## Known caveats

* **Lengths:** 12 venues have no verifiable length (`null`). Sources conflict for
  some (e.g. Huset's 0.333 vs 0.375 mi; Iowa 0.875 vs 0.894; Texas 1.44 vs 1.5;
  Boone 1/3 vs 1/4; Buttonwillow 3.0 vs 2.64). We kept the value the track itself
  or Wikipedia states as current.
* **Banking:** documented for fewer than half of ovals (126 ovals have `null`).
  The game layer treats undocumented banking as a neutral mid-banked oval.
* **Surfaces** for a handful of paved national venues were missing from infoboxes
  and set to asphalt without a specific source.
* **Coordinates:** about 13 dirt tracks use town-centre coordinates (noted in the
  record); two Wikipedia coordinates were wrong and replaced from OpenStreetMap.
* **Disciplines and level** are research classifications based on the series a
  track hosts, not single-source facts.
* **Active status** may lag very recent closures or re-openings.
* **Thin categories:** karting and quarter-midget venues (7 entries) and no
  dedicated figure-eight tracks yet. Some notable short tracks are not yet included.
* Excluded for unverifiable status: East Bay Raceway Park, Atomic Speedway,
  Calistoga, Langley Speedway.

## Game-derived layers

`racingsim/tracks/ratings.py` derives a size class, prestige, attendance
potential, climate/season window, series suitability and 17 simulation ratings
from the facts. 23 notable venues have hand-tuned overrides with written
rationale in `data/track_rating_overrides.json`. These layers are internal game
ratings, not official specifications.

## Next steps

* Add more karting/quarter-midget venues, figure-eight tracks, and Plains/Texas
  weekly dirt tracks (IMCA has 240+ sanctioned tracks; we have a sample).
* International ladders' venues (UK short ovals, Australian speedways, European
  circuits) when those regions are modelled.
