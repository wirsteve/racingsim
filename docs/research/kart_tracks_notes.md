# Kart Track Research Notes

Research notes for `docs/research/data/kart_venues.json (staged here until it is de-duplicated and moved into data/tracks/)`, a list of real kart tracks in the USA and Canada where club or local kart racing runs. It gives young drivers a local starting point. Before this list, the track database had only a handful of kart circuits.

## Coverage

| Measure | Count |
|---|---|
| Records | **99** (81 USA, 18 Canada) |
| Status | 98 active, 1 historic (`active: false`: MacArthur Park Raceway, OKC, closed by 2012) |
| Surface | 69 asphalt (sprint/road-style) · 27 dirt/clay ovals · 3 unconfirmed (`null`) |
| Level | 57 local · 37 regional · 5 national |
| Geography | 33 US states, 7 Canadian provinces |

**By state (USA):** AL 2 · AR 2 · AZ 2 · CA 10 · CO 2 · FL 1 · GA 1 · IA 3 · ID 1 · IL 3 · IN 3 · KS 1 · LA 1 · MD 1 · MN 3 · MS 1 · NC 2 · ND 2 · NE 1 · NH 1 · NJ 1 · NM 1 · NV 1 · NY 6 · OH 6 · OK 2 · OR 3 · TN 1 · TX 7 · VA 1 · VT 1 · WA 4 · WI 4

**By province (Canada):** AB 1 · BC 2 · MB 1 · NB 1 · ON 7 · QC 5 · SK 1

All records use the `local_regional_venues.json` schema with `track_type: "kart_circuit"` and `disciplines: ["karting"]`. `turns` and the banking fields are always `null`. Turn counts appear only in `configuration` text when a source states them.

## Duplicates and overlaps

* **No name matches a record in `local_regional_venues.json` or `major_venues.json`.** I skipped the kart circuits and kart-capable venues already in those files (New Castle, Trackhouse Motorplex, Orlando Kart Center, Autobahn, Road America, PittRace, NOLA, NJMP, CMP, AMP, UMC, Ridge, ORP, NCM, Brainerd, ICAR and others). I also skipped car venues whose kart track has no separate name, such as Mission Raceway Park, Merrittville, Spring Mountain and Motorsport Park Hastings.
* **Separately named kart facilities at an existing car venue** were kept because they are physically separate tracks. Gateway Kartplex (Gateway Motorsports Park), COTA Karting, Mosport Karting Centre, Area 27 Kartplex, Willow Springs Kart Track, Pacific Grand Prix (next to Pacific Raceways), G-Force Karts (Richmond Raceway), Académie Tag Karting Mont-Tremblant, Lebanon Valley Kart Track, Can-Am Speedway Karts, Southern Oregon Outlaw Karts (Southern Oregon Speedway grounds), Mini E Raceway (inside Eagle Raceway), Rice Lake Speed Pit Kart Track and Raceway Park Karting (Englishtown). The merge step may prefer to link these to their parent venues.
* **Overlap with `census_venues.json`.** That file was not on the exclusion list, but 16 names here also appear there: Talladega Gran Prix Raceway, Talladega Raceway Park, Cycleland Speedway, Kings Kart Club, Newton Kart Klub, Whiteland Raceway Park, Atwater Karting Speedway, Runestone Go Kart Association, Mountain Creek Speedway, Red River Kart Club, Kart Kanyon Speedway, Martinville Raceway, MacArthur Park Raceway, Thunder Hill Speedway (Menomonie WI), Greg Moore Raceway and Goodwood Kartways. The records here have their own sources and fuller fields, so the merge should dedupe them.
* "Sunset Speedway (WA)" is named that way so it does not clash with the existing Sunset Speedway records (Innisfil ON in local_regional, Banks OR in census).

## Sources used

* **OpenStreetMap via Nominatim** for coordinates and to confirm location (63 records). Each record cites the specific OSM object (`openstreetmap.org/way/…`) plus `https://www.openstreetmap.org/ (Nominatim geocode)`. I kept to at most 1 request per second with a descriptive User-Agent and cached every result. When Nominatim returned HTTP 429, I backed off and then stopped geocoding, which ended the search for more tracks (see Gaps).
* **MyRacePass track pages** (`myracepass.com/tracks/{id}/info`) for dirt kart ovals. These are track-maintained listings. I read size, surface and description from them, and took coordinates from the track's own "View Map" pin (20 records). Where OSM also had the track, the pins agreed with OSM to within about 100 m (Newton, Mountain Creek, Atwater, Thunder Hill). robots.txt allows `/tracks/`, and I fetched pages at least 2 seconds apart.
* **CanadianKartingNews track directory** (`canadiankartingnews.com/?p=5585`) for Canadian track names, cities, lengths and clubs. ASN Canada has no public track list.
* **Official sites:** OVKA, Gateway Kartplex, Stockholm Karting Center, Gulf Coast Karters (racekarts.com map embed), MH Circuit, Area 27, CKRC, Goodwood, Mosport KC and others.
* **Wikipedia:** Whiteland Raceway Park, Greg Moore Raceway, Talladega Gran Prix Raceway, MacArthur Park Raceway, Willow Springs and WKA.
* **News and series pages:** eKartingNews, KartPulse (articles and forum track lists), kartclass.com regional guides, MotorsportReg event listings, county and city park pages, and local news.
* No WKA, AKRA, IKF or SKUSA public track directory exists anymore, so sanctioning bodies were used only through event and news pages. Racing-Reference and The Third Turn were not used. A few sites returned 403 or reset the connection (Hill Country Kart Club, SRA Karting, CKRC, PSGKA, gvkc.org, lafayettemotorsportspark.com). I skipped those sites and did not work around the blocks.

## Confidence and caveats

* **Coordinate precision.**
  * Most records point at the mapped track or facility (OSM object or MyRacePass pin).
  * Some come from a geocoded street address or an official site map:
    * House-level: Whiteland, Lamar County, Adams, Pat's Acres, SIMA, Wilmington, Genesee Valley KC, Heart of Texas KC and Yreka.
    * Official-site map embed: Gulf Coast Karters and Stockholm.
  * Some are site- or park-level:
    * Area 27 site.
    * Horn Rapids motorsports complex.
    * Englishtown Raceway Park complex.
    * North Lake Park (Lake Garnett).
    * Prairie City: the OSM "Kart Pit" structure inside Prairie City SVRA.
  * **G&J Kartway is street-level only** (Barnetts Mill Rd, Camden OH), so it is rounded to 2 decimals.
  * The Genesee Valley KC and Heart of Texas KC addresses came from AARP Local listings that now redirect away. Treat those two as medium confidence.
* **Surface.**
  * Multi-turn sprint and road-style kart circuits are recorded as `asphalt` when a source calls them paved or a sprint/road course. Several Canadian directory entries give only a length, and their surface is inferred the same way.
  * Hill Country Kart Club, which is concrete, is not included.
  * Three surfaces are `null`: Wilmington Raceway Park, Kinsmen Kart Club and Runestone.
* **Length.** Stated only when a source gives it, converted from metres where needed. Conflicting values are `null` with a note in `configuration`: Mosport 1.2 vs 1.5 km, Thunder Hill 1/8 vs 1/6 mi, Mountain Creek 1/7 vs 1/5 mi.
* **Opened** is filled only when a source gives a year or one can be derived directly:
  * Santa Maria: "52-year run" ending 2010.
  * Texoma: 27th year in 2026.
  * Newton: at its current site since 1974.
* **Active.**
  * Records with 2024–2026 evidence (MotorsportReg events, MyRacePass schedules, news) are solid.
  * The rest are marked active because they were listed without any closure notice. Status may lag recent closures. Examples: Wilmington, Sandy Hook, Moore Park, Thompson Raceway.
  * Ocala Gran Prix (closed 2021) was left out because no verifiable coordinates were found.
* **Level** is a research call based on the series a track hosts, not a fact from a single source:
  * national: IKF Grand Nationals, Canadian Nationals, Challenge of the Americas
  * regional: multi-club or regional series
  * local: club nights and rentals
* **Names.** Neutral names are used where one exists. Musselman Honda Circuit (Tucson) keeps its dealer-sponsor name because no neutral name was found. Whiteland Raceway Park keeps its traditional name, and the K1 Speed rebrand is noted in `configuration`.

## Gaps

* **Below the 120-track goal.** The main limit was coordinates: Nominatim returned 429 several times, and Overpass was not reachable through the proxy. These real tracks are known but left out because their location could not be verified:
  * Brechin Motorsports Park, Canadian Mini Indy (Hamilton), Peterborough Kartways, SRA Karting, Le Lièvre Karting, Karting Thetford, Le Circuit Quyon, EDKRA Warburg track and WF Botkin Raceway.
  * Owosso Kart Speedway (MI), Adkins Raceway (OH), LaFayette Motorsports Park (NY), GSR Kartway (WI) and Hill Country Kart Club (TX).
  * North Texas Karters (Krum TX), PSGKA (Spanaway WA), Spokane Kart Racing Assn and KC Karting Liberty Sprint Track (MO).
  * AMR Homestead-Miami Motorplex, Palm Beach Karting, South Florida Karting, Georgia Karting Komplex, Monticello Kart Racing, Piedmont Kartway (NC), Tri County Kartway (NC) and the SC kartways (Conway, Loris, Blacksburg).
  * Montana Karting Association (Helena) and Big Sky Kartway.
  * X1 Outdoors (MA), Tri State Kart Club / Pomfret (CT), Thundering Valley (ME) and Brown County Kart Track (SD).
  * Ocala Gran Prix (historic).

  A later pass with a working geocoder could add roughly 35 more.
* **States with no record:**
  * USA: AK, CT, DE, HI, KY, MA, ME, MI, MO, MT, PA, RI, SC, SD, UT, WV, WY.
  * Canada: NS, PE, NL and the territories.
  * Some of these gaps come from exclusions rather than a lack of tracks. MI, PA, SC, UT and WV all have karting at car venues already in the database (Grattan/GingerMan, PittRace, CMP, UMC, Summit Point).
  * Kentucky's main sprint venue (NCM) is already in the database.
* **Thin states (1 record):** FL, GA, KS, LA, MD, MS, NE, NH, NJ, NM, NV, TN, VA and VT.
* **Historic tracks:** only one (MacArthur Park Raceway). Other closed tracks found (Long Run Park KY, McCracken County KY, the Memphis and Seymour TN sites, CalSpeed CA) have no verifiable coordinates.
* **Not included on purpose:** indoor and electric rental centres (K1 Speed, Andretti, etc.), family fun-park go-kart tracks with no club racing, and car speedways that only add kart classes to their programmes. Ohsweken, Painesville and Lightning Speedway are examples.
