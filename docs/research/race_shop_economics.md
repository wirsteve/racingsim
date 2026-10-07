# Race shop economics: haulers, facilities, fleet, rollers, engine leases, crew and travel

Scope: what it costs a US racer to run the operation around the car, from weekly short-track racing up to ARCA, Trucks, Xfinity and Cup. This covers transport, the shop, shop equipment, how many cars teams keep, roller prices, engine lease and spec-engine programs, crew pay and travel.

This file does not repeat the per-class chassis, engine, tire and rebuild prices in `data/rules/classes.json`. It also does not repeat the season budgets in `team_economics.md` and `pyramid_economics_geography.md`. It refers to them where useful.

Conventions:
- Money is nominal USD for the year stated.
- **Confidence: high** means a primary or official document (IRS, GSA, FMCSA, ATRI, a manufacturer or retailer price page). **Medium** means a trade or racing outlet quoting named people or itemized budgets. **Low** means a classified listing, a forum post, an aggregator, or a figure seen only in a search-result summary because the page blocked automated access.
- **EST** marks my own estimate. The arithmetic is shown each time.
- Sources that blocked automated access (HTTP 403) were not retried or worked around. Where a figure comes only from a search snippet, it says so.

---

## 0. Summary table

| Item | Range | Year | Confidence |
|---|---|---|---|
| Open car trailer, 18 ft, 7,000 lb, new | $4,300-7,200 | 2025-26 | high (dealer listings) |
| Enclosed car trailer, 24 ft, new | $11,000-22,000 steel/basic-aluminum; ~$54,000 premium aluminum (Featherlite) | 2024-26 | medium |
| 3/4-ton diesel pickup, new (base) | ~$58,000 base; $65,000-90,000 typical crew-cab trims (EST) | 2025 | high (base) / EST |
| 28 ft stacker trailer (2 cars, lift), new | $105,000-128,000 | 2024-26 | medium |
| 48 ft gooseneck 2-car (with living quarters) | $60,000-95,000 new | 2025 | medium |
| Toter home (medium-duty truck with living quarters), used | $48,500-149,000 | 2020s listings | low-medium |
| Full "mobile race shop" toter plus stacker, local/regional | $150,000-250,000 | 2017 | medium |
| Semi rig, used (dirt late model / modified / ARCA level) | ~$250,000 | 2017 | medium |
| Semi rig, used (Xfinity, 2001 trailer + 2016 Kenworth) | $300,000-350,000 | 2025 | medium |
| Truck plus trailer, top World of Outlaws sprint team | ~$500,000 | 2022 | medium |
| Cup hauler, new | ~$400k (2014 team data); $600k-1.2M (2025 aggregator) | 2014/2025 | low |
| Semi running cost per mile (fuel + R&M + tires + insurance) | ~$0.82/mi (EST from ATRI) | 2023-24 | high (inputs) |
| Pickup plus trailer running cost per mile | $0.32 fuel only; ~$0.75-0.85 all-in (EST) | 2025-26 | EST |
| Trailer + contents insurance ($100k insured) | $1,000-1,500 per year | 2017/2024 | medium |
| Race shop rent, Mooresville (8,750 sq ft) | $122,500-146,600 per year ($14 + $2.75 NNN per sq ft) | 2025 | medium |
| National industrial in-place rent | $8.30-8.76 per sq ft per year | 2024-25 | high |
| Build a 40x60 shop (2,400 sq ft) | $45,000-110,000 | 2025 | medium |
| Pull-down rig (Mittler) | $97,500 new; ~$50,000 used | 2025 | medium |
| 4-pad wireless scales (Intercomp) | $1,449-2,695 | 2020s | high (retail) |
| Setup / leveling rack | $3,054-6,495 | 2020s | high (retail) |
| Two-post lift (BendPak 10k lb) | $6,095-7,045 | 2020s | high (retail) |
| TIG welder (Miller Syncrowave 210) | $3,295-3,799 | 2020s | high (retail) |
| Shock dyno | $6,000-7,000 (Performance Trends) to $15,300-17,700 (Penske S-Link) | 2025 | medium |
| Engine dyno cell (SuperFlow 902-class, all-in) | ~$70,000-80,000 | undated forum | low |
| Driver-in-loop sim time | ~$12,000 per day (Dallara IndyCar sim) | 2017 | medium |
| Motion sim rig (CXC Motion Pro II) | $49,000-81,000+ | ~2016-17 | medium |
| Wind tunnel | $490/hr (small A2 tunnel) to $8,000+/hr (full-scale Charlotte) | 2017+ | low-medium |
| Seven-post rig | purchase "millions"; rental rate not found | 2016 | medium / gap |
| Used rollers, asphalt late model (Hamke, Port City, Fury, Howe) | $10,000-25,500 | 2025-26 listings | low-medium |
| Used rollers, dirt late model (Rocket, Longhorn, Black Diamond) | $15,000-30,000 | 2025-26 listings | low-medium |
| New dirt late model complete roller | $55,000-70,000 | 2023 | medium |
| Sprint car roller | $2,000-7,000 old; $30,000-50,000 new/top | 2022-26 | medium/low |
| Modified roller (tour / NASCAR) | $6,500-35,000 | 2025-26 listings | low |
| Retired ARCA / Busch / Truck roller | $3,500-15,000 old chassis; Canada-spec $55,000 | 2025-26 listings | low |
| Xfinity chassis | $35,000 used to $50,000 newer; 7 cars minimum | 2025 | medium |
| Cup Next Gen | 7 cars max per car number; parts $4.7M per year (FRM) | 2022/2025 | high/medium |
| Ilmor 396 (ARCA) | $35,000 + $5,000 install kit; rebuild $10-15k every 1,200-1,500 mi | 2015 | medium |
| Ilmor NT1 (Trucks) | ~$38,000 + ~$17,000 ECU/throttle body/adapters; rebuild every 1,500 mi | 2018-20 | low-medium |
| Xfinity engine lease | ~$800,000 per season (~$24,200 per race) | 2025 | medium |
| ARCA superspeedway engine lease (pre-Ilmor) | ~$50,000 for 2 races | 2014-15 | medium |
| Dirt late model / dirt modified engine maintenance | $10-12 per lap (DLM), $5-8 per lap (modified) | 2017 | medium |
| Weekly crew | volunteers; team often covers pit passes at $20-40 per person per night | 2024-26 | medium |
| Touring crew (dirt late model / sprint) | $600-1,000+ per week; WoO crew chief ~$100k+ | 2017/2022 | medium |
| Xfinity payroll | crew chief $100-150k, car chief $80-100k, mechanic $50-70k, hauler driver $60-80k | 2025 | medium |
| Travel | hotels ~$300/night (Xfinity); per diem $25-60/day; GSA standard $110 lodging + $68 M&IE | 2025-26 | medium/high |

---

## 1. Haulers and transport

### 1.1 Open and enclosed trailers (weekly racers)
- **New 18 ft open car trailer, 7,000 lb GVWR: $4,299-7,200.** H&H 18x82 is $4,999 (2025) to $5,699 (2026). Load Trail 18x83 is $7,200 (2026). Carry-On 7x18 wood deck is $4,299. Confidence: high (dealer listings).
  - https://www.truckpaper.com/listing/for-sale/255842313/2026-h-and-h-trailers-18-ft-x-82-in
  - https://www.truckpaper.com/listing/for-sale/257325121/2026-load-trail-18-ft-x-83-in
- **New 24 ft enclosed car trailer:**
  - Haulin HLAFT 8.5x24, 10,000 lb: MSRP $12,995, sale price $10,995 (2026).
  - Mission 8.5x24 aluminum with finished interior: $21,995 (2024).
  - Sundowner 24 ft gooseneck: $33,900 (2026).
  - Confidence: medium (dealer listings, partly seen via search summary).
  - https://www.trailersusa.com/detail/new-haulin-trailers-hlaft-85-x-24-10000-enclosed-car-hauler-cargo-trailer-stk096569depere-u5186523
  - https://showroom.auction123.com/mobile_space/inventory/11130/2024/Mission/ID_2109542878.html
- **Premium aluminum 24 ft:** a used 2020 Featherlite 4410 was listed at $40,000 against "$54K" new retail. Confidence: low (classified, search summary). https://rennlist.com/forums/market/1420863
- **28 ft stacker (2 cars, lift), new:**
  - 2026 ATC Rom 750S: $106,950-128,463.
  - 2024 Bravo Icon 28 ft: $104,995.
  - Confidence: medium (dealer listings).
  - https://www.rvpark.com/rvs/7003161-2026-28-rom-750s-stacker-for-sale-in-mountain-home-id
  - https://www.dragzine.com/news/rig-of-the-month-2024-28-bravo-aluminum-icon-trailer
- **Used 24 ft custom stacker with a 4,000 lb Gemini lift:** $47,500-50,000. Confidence: low. https://showroom.auction123.com/vehicle_selling_solutions/inventory/11537/EBMS824TA67000713.html
- **48 ft gooseneck:**
  - New 48 ft Vintage gooseneck with 12 ft living quarters: $94,900 (Flying A Motorsports).
  - New 2025 Sundowner 48 ft aluminum 2-car: $59,995.
  - Used 2012 Featherlite 36 ft gooseneck stacker with lift: sold at auction for $70,000.
  - Used 2017 Millennium 50 ft double stacker: $52,900.
  - Confidence: medium/low.
  - https://www.dragzine.com/?p=2017423
  - https://www-backend.pcarmarket.com/auction/2012-featherlite-gooseneck-stacker-trailer
  - https://www.p1groupe.com/inventory/2017-millennium-trailers-50%E2%80%99-continental-cargo

### 1.2 Tow vehicle (pickup)
- **2025 3/4-ton diesel base prices:**
  - F-250 Power Stroke: $57,890 (high-output version $60,390).
  - Silverado 2500HD Duramax: $58,110.
  - The diesel engine adds $10,000-13,000 over the base gas truck on each brand.
  - Confidence: high (manufacturer pricing via Diesel Army).
  - https://www.dieselarmy.com/news/these-are-the-least-expensive-new-diesel-trucks-you-can-buy-in-2025/
- **EST:** racers usually buy crew-cab 4x4 trims, so plan on $65,000-90,000 new. Used 5-10-year-old diesels are roughly $25,000-50,000 (EST, not sourced).
- **Towing economy:** a 2025 Silverado 2500HD Duramax towing a ~4,400 lb, 24 ft enclosed trailer got 11.8 mpg. A 3/4-ton towing ~11,000 lb got 11.5 mpg. Confidence: medium (TFLtruck tests). https://tfltruck.com/2024/11/video-small-vs-big-diesel-truck-which-tows-better-costs-less-on-the-denver-100-mpg-loop/

### 1.3 Toter homes and "mobile race shops"
- **Used toter homes:**
  - 2000 Renegade on Freightliner FL70: $48,500.
  - Tandem-axle Renegade: $79,000.
  - Low-mile 2007 Haulmark 17 ft toter: $149,000.
  - Confidence: low-medium (listings).
  - https://www.dragzine.com/news/rig-of-the-month-low-mile-like-new-2007-haulmark-toterhome
  - https://www.race-cars.com/Advert/Details/131424/2003-freightlinernrc-renegade-trailer-fl112
- **2017 FloRacing (dirt late model):**
  - Local and regional racers' toter-plus-stacker "mobile race shops" run **$150,000-250,000**.
  - A modern trailer starts at ~$250,000, and high-end trailers cost $400,000-500,000.
  - Dropping the toter saves ~$75,000, which the article equates to 900+ hotel room-nights.
  - Confidence: medium.
  - https://www.floracing.com/article/57691-do-we-need-the-toterhome-rig-and-stacker-trailer
- **2025:** top dirt late model teams "often stay in place" in "million dollar toter home setups" rather than hotels. Sprint car teams mostly use hotels. Confidence: medium (DIRTRACKR). https://dirtrackr.com/daily/1353

### 1.4 Semi haulers (touring, ARCA, Truck, Xfinity, Cup)
- **Dirt late model national tour, 2017:** used tractor and trailer **$250,000**; diesel $25,000 per season. Confidence: medium. https://www.floracing.com/articles/5065706-all-it-takes-to-run-a-national-tour-is-guts-talent-and-a-half-million
- **Dirt modified national touring, 2017:** trailer $250,000; diesel $20,000 per year. Confidence: medium. https://www.floracing.com/articles/5967477-the-cost-of-racing-a-national-modified-tour
- **World of Outlaws sprint, 2022:** truck and trailer **~$500,000**; 40,000 miles a year at 6 mpg; "diesel & truck" $50,000 plus truck fees $20,000. Confidence: medium. https://dirtrackr.com/daily/707
  - EST: 40,000 mi / 6 mpg × $5.00/gal = **$33,300 in diesel** (2022 prices).
- **Budget end, 2019:** a complete 410 sprint team was offered at $150,000. That included a 1987 Kenworth T600 (490,000 miles) and a 2009 44 ft stacker, plus 2 cars, 2 engines and spares. Confidence: medium. https://www.thedrive.com/accelerator/31385/someone-is-selling-their-entire-sprint-car-racing-team-for-150000
- **Bare used 53 ft race trailer:** a 2017 Vintage 53x102 race-car trailer was listed at $31,990. Confidence: low (search snippet; the page now returns 404). https://www.itagequipment.com/for-sale/2017-vintage-53x102-race-car-trailer-13950293
- **Xfinity, 2025:** Big Machine Racing's 2001 trailer with a 2016 Kenworth was **$300,000**. A Wood Brothers trailer was listed at **$350,000**. Confidence: medium. https://www.theautopian.com/an-extraordinarily-detailed-accounting-of-how-much-it-really-costs-to-race-in-nascar
- **Cup:**
  - Stewart-Haas Racing data from 2014 (published 2017): haulers **$400,000 each, replaced every 5 years**. Confidence: low (pre-2015 data via a MoneyTips syndication). https://www.nbcnewyork.com/news/national-international/race-car-costs-the-high-price-of-fielding-a-racing-team/2047990/
  - A 2025 aggregator puts a new fully outfitted Cup rig at **$600,000-1.2M**: tractor $160-250k, 53 ft double-deck trailer $350-800k, power and HVAC $25-100k. Used rigs trade at $200-500k. Confidence: low (aggregator, unattributed). https://tpautorepair.net/how-much-does-a-nascar-car-hauler-cost/
  - EST for the game: Cup new **$700k-1.0M**, ARCA/Truck used **$150-350k**.

### 1.5 Running cost per mile
- **ATRI trucking averages (all-industry Class 8):**
  - 2024: total **$2.260/mi**. Fuel $0.48, repair and maintenance $0.198, tires $0.047, truck and trailer payments $0.39, driver wages ~$0.80.
  - 2023: insurance **$0.099/mi**.
  - Confidence: high.
  - https://www.fleetmaintenance.com/equipment/article/55301363/american-transportation-research-institute-atri-breakdown-of-atri-2025-operational-costs-report
  - https://truckingresearch.org/wp-content/uploads/2024/06/ATRI-Operational-Cost-of-Trucking-06-2024.pdf
  - EST race-hauler running cost excluding the driver and depreciation: 0.48 + 0.198 + 0.047 + 0.099 = **~$0.82/mi**.
  - Race rigs run fewer miles than freight trucks, so insurance per mile is likely higher. Treat this as $0.80-1.00/mi.
- **Xfinity, 2025:** hauler fuel $31,000 a year for 52,000 miles at 6 mpg. Confidence: medium (Autopian, above).
  - EST: $31,000 / 52,000 = **$0.60/mi fuel**, which implies ~$3.58/gal.
- **Diesel price:** the 2024 average was $3.76/gal. EIA projected $3.66 for 2025. Confidence: high (EIA via Rigzone). https://www.rigzone.com/news/eia_sees_gasoline_diesel_price_dropping_in_2025_2026-02-dec-2025-182432-article/
- **Pickup + trailer (EST):** $3.66 / 11.5 mpg = **$0.32/mi fuel**.
  - All-in, use the IRS business rate (fuel, maintenance, tires, insurance and depreciation): **72.5¢/mi** from 1 Jan 2026 (70¢ in 2025), revised to 76¢ from 1 Jul 2026. Confidence: high. https://www.irs.gov/newsroom/irs-sets-2026-business-standard-mileage-rate-at-725-cents-per-mile-up-25-cents
  - Add ~$0.03-0.08/mi for trailer tires, bearings and brakes (EST, not sourced).
  - Total: **$0.75-0.85/mi**.
- **Insurance (off-track property: trailer, car, parts, in transit and stored):**
  - $100,000 coverage with a $1,000 deductible costs ~**$1,000 per year** (AP1 Insurance, 2024). The policy does not cover the car in competition.
  - 2017 drag racing figures: trailer plus contents worth $100k ~$1,500 per year; $1M liability from ~$1,500 per year; off-track deductibles $1,000-2,500.
  - Many ordinary truck/trailer policies exclude motorsports claims.
  - Confidence: medium.
  - https://outsidegroove.com/2024/12/insurance-for-racers-do-you-think-youre-protected/
  - https://www.dragzine.com/news/risky-business-how-to-protect-your-car-with-drag-racing-insurance/

### 1.6 CDL requirements
- **Federal definition (49 CFR 383.5).** A CDL is needed for a vehicle "used in commerce" when any of these is true. Confidence: high.
  - It has a GVWR of 26,001 lb or more.
  - It is a combination with a GCWR of 26,001 lb or more *and* the towed unit's GVWR is over 10,000 lb.
  - https://www.fmcsa.dot.gov/registration/commercial-drivers-license/does-definition-cmv-ss-3835-cdl-requirements-include
  - https://csp.colorado.gov/new-carrier-information/commercial-drivers-license-fmcsr-383
- **The "commerce" test for racers.** FMCSA guidance (Part 390.3 interpretation) says hauling a race car is not commerce if all of these hold:
  - prize money is declared as ordinary income;
  - costs are not deducted as a business expense;
  - there is no corporate sponsorship.
  - Sponsorship or a for-profit operation brings the hauler under commercial rules: a CDL by weight class, plus a USDOT number. States differ; New York, for example, treats even trophy-only racing as commerce.
  - Confidence: medium (seen in a search summary; the FMCSA page returned 403). https://www.fmcsa.dot.gov/regulations/part-390-ss-3903t-general-applicability-question-21
- **Game rule (EST, my reading of the rules above):**
  - A pickup with an open trailer or a ≤10,000 lb enclosed trailer: no CDL.
  - A dually with a gooseneck over 10,000 lb GVWR (GCWR ≥26,001), or a toter whose own GVWR is ≥26,001: CDL (Class A or B) **once the team is sponsored**.
  - A semi: Class A. Every pro team employs a CDL hauler driver.

---

## 2. Race shop facilities

### 2.1 Rent vs buy
- **Mooresville, 2025: 1046 Gateway Drive**, 8,750 sq ft heated (6,250 climate-controlled), 5 drive-in doors, 3-phase power. Asking **$14.00/sq ft + $2.75 NNN**. Confidence: medium (listing).
  - EST: 8,750 × $16.75 = **$146,600 per year**.
  - The Autopian's Xfinity budget uses the same 8,750 sq ft (Cope Family Racing) shop at **$122,500 per year** ($10,208 a month), which is the base rent alone.
  - https://firstchoicelongview.homefront.com/homes/nc/mooresville/property/1046-gateway-drive-6c539586-be7a-32be-88a9-829166df09bc
  - https://www.theautopian.com/an-extraordinarily-detailed-accounting-of-how-much-it-really-costs-to-race-in-nascar
- **Buying in Mooresville:** a 20,000 sq ft shop costs **~$3.4M** (2025). Confidence: medium (Autopian, above).
  - EST: $3.4M / 20,000 = $170/sq ft.
- **Other Mooresville figures:** small industrial condos model ~$18/sq ft in rent. Packard Place offers 3,300-6,800 sq ft suites. Confidence: low-medium. https://www.loopnet.com/Listing/144-Mccrary-Rd-Condos/40713218/
- **National baseline:** industrial in-place rent averaged **$8.30/sq ft** (Dec 2024) and **$8.76/sq ft** (Dec 2025). Confidence: high (CommercialEdge). https://www.commercialcafe.com/blog/national-industrial-report-december-2025/
- **WoO sprint team, 2022:** shop rental **$40,000 per year**. Confidence: medium. https://dirtrackr.com/daily/707
- **Build your own:** a 40x60 (2,400 sq ft) pole building costs **$45,000-110,000** all-in (2025). The shell is $20-60k, slab $7-25k, insulation and HVAC prep $2-18k, electrical $1.5-9k. Confidence: medium (builder blog). https://info.fbibuildings.com/blog/40-x-60-pole-barn-cost
- **Game tiers (EST):**
  - Home garage: $0 rent; add ~$1,000-3,000 a year in power and heat.
  - Rented 2,400 sq ft bay: at $8-15/sq ft, **$19,000-36,000 per year**.
  - Touring shop, 5,000-9,000 sq ft: **$60,000-150,000 per year**.
  - National team, 20,000+ sq ft: rent it, or buy for ~$3-4M.

### 2.2 Shop equipment

**Lifting, welding, fabrication**
- Two-post lift (BendPak 10AP / 10APX, 10,000 lb): **$6,095-7,045**. Confidence: high (retail). https://mechanicsuperstore.com/collections/vendors/products/bendpak-10ap-10-000-lb-2-post-lift
- TIG welder (Miller Syncrowave 210): **$3,295** for the TIG package, **$3,799** for the TIG/MIG package. Confidence: high (retail). https://store.cyberweld.com/products/miller-syncrowave-210-tig-package-907596
- Tube bender (JD2 Model 32): **$395 manual, $799 hydraulic**, before dies (both now listed as discontinued). Confidence: high (retail). https://www.trick-tools.com/JD2_Model_32_Hydraulic_Tubing_Bender_302001_2248
  - EST: a usable cage and chassis fab corner (bender with 2-3 die sets, notcher, saw, TIG, table) costs **$8,000-15,000**.

**Chassis jig and setup**
- Chassis jig / fixture table: Uni-Jig jigs cost **$4,000-7,000** by size. A custom 4x10 ft ground MIC-6 tool-plate table was $6,500. Confidence: low (undated forum).
  - https://www.tapatalk.com/groups/dsrforum/source-for-chassis-jig-t1969.html
  - https://mail.jalopyjournal.com/forum/posts/11043604
- Scales (Intercomp, 4 wireless pads): **$1,449** (SW787) to **$2,695** (SW777RFX). Confidence: high (retail). https://www.gspeed.com/products/intercomp-sw777rfx%e2%84%a2-wireless-professional-scale-system
- Setup / leveling rack ("setup plate"):
  - Longacre adjustable platen fixture: **$3,054**.
  - Intercomp Quik Rack: **$3,495**.
  - Intercomp full set-up rack: **$6,495**.
  - Confidence: high (retail).
  - https://www.jegs.com/i/longacre-racing-441-72860-72860-adjustable-computer-scale-platen-setup-fixture-w-billet-scale-pad-levelers
  - https://www.jegs.com/i/intercomp-541-102024-scale-set-up-full-rack
- Pull-down rig (Xfinity level): Mittler Bros **$97,500 new, ~$50,000 used** (2025). Confidence: medium (Autopian, above).

**Engine and shock testing**
- Shock dyno:
  - Performance Trends: base **$5,999**, rising to $6,999 (2025).
  - Roehrig: described as more than 3× that; one source says the 3VS costs over $12,500.
  - Penske S-Link PHD-2: **$15,325-17,725**.
  - Confidence: medium.
  - https://www.performancetrends.com/listmanager/May%202025%20Newsletter.htm
  - https://www.gspeed.com/products/s-link-phd-2
  - Note: shock packages for a dirt late model rose from ~$2,500 to "a minimum of $5,000" (2024). https://performanceracing.com/magazine/featured/05-10-2024/cost-controls
- Engine dyno: one shop had **$70,000-80,000** in a complete SuperFlow 902 cell. The cell itself (sound-proofing, ventilation, pumps) can take most of the budget, and enclosure plus ventilation alone runs $10-15k. Confidence: low (undated engineering forum). https://www.eng-tips.com/viewthread.cfm?qid=304732
  - Renting time: shops charge about **$100-150 per hour**, or $600-1,000 a day. Confidence: low (forums). https://www.hpacademy.com/forum/introduction-to-engine-tuning/show/avg-price-to-rent-a-dyno/
  - EST for engine-shop tooling beyond the dyno (boring bar or CNC access, flow bench, balancer, valve machine, measuring tools) at a small builder: **$50,000-150,000** (not sourced). Most short-track teams buy engines rather than build them.

**Simulators, wind tunnels and shaker rigs**
- Driver-in-loop simulator time: Dallara's IndyCar sim in Speedway, IN cost **$12,000 per day** for pro teams (2017). Confidence: medium. https://www.thedrive.com/video/8374/seat-time-in-this-racing-simulator-costs-12000-per-day
  - OEM sims (Chevrolet DiL in Huntersville, Ford in Concord) are given to supported Cup teams, typically ~4-hour sessions weekly. They are not for rent. Confidence: medium. https://www.wfae.org/sports/2023-10-04/sometimes-reality-bites-why-simulators-are-key-for-the-bank-of-america-roval-400
- Motion sim rig to buy: CXC Motion Pro II from **$49,000** (single screen), Pro from **$81,060**; a panoramic display adds $9,000. Confidence: medium (~2016-17 press). https://flyingmag.com/training-recurrent-trainingsimulators-home-based-simulator-offers-flight-and-race-car-experience
  - EST: a static home rig (direct-drive wheel, load-cell pedals, rig, triple screens or VR) costs **$3,000-10,000** (not sourced).
- Wind tunnel:
  - The more advanced Charlotte full-scale tunnel cost "upward of **$8,000** an hour" (2017). Confidence: medium. https://nbcsports.com/nascar/news/kligerman-teams-blowing-money-on-an-idea-whose-time-has-gone-with-the-wind
  - The small A2 tunnel was quoted at **$490 an hour**. Confidence: low (search summary).
- Seven-post shaker rig: building and maintaining one costs "millions of dollars", so most teams rent time (from ARC in Indianapolis, Ohlins in Hendersonville). Confidence: medium. https://www.indycar.com/news/2016/01/01-08-shaker-rig-101-by-pruett
  - A forum puts the purchase at $7-8M. Confidence: low. https://forums.anandtech.com/threads/jeff-gordon-wins-talladega.94455/page-2
  - **No public rental rate was found** (see Gaps).
- Track testing for comparison: short tracks charge **$100-300 per day**. The 2025 CARS Tour Cordele test charged $125 an hour with a 3-hour minimum. Confidence: medium. https://www.shorttrackscene.com/late-model-stock-cars/cars-late-model-stock-tour/it-was-an-outrage-but-cars-tour-drivers-want-nuanced-talk-about-cordele-testing-fee/

### 2.3 Spare parts inventory
- **Dirt late model national tour (2017, 45 races).** Confidence: medium. https://www.floracing.com/articles/5065706-all-it-takes-to-run-a-national-tour-is-guts-talent-and-a-half-million
  - Spare parts (bolts, fluids, suspension): $20,000.
  - Tools, jacks, pit carts: $15,000.
  - 50 aluminum wheels: $10,000.
  - 20 sets of quick-change gears: $2,500.
- **Dirt modified touring (2017):** tools $15,000; replacement parts, shocks, driveline and bodies $10,000. Confidence: medium. https://www.floracing.com/articles/5967477-the-cost-of-racing-a-national-modified-tour
- **410 sprint package (2019):** 16 wheels, 4 new top wings, two sets of fresh shocks plus a spare set, and "bins of spare parts". Confidence: medium (TheDrive, above).
- **Xfinity (2025) consumables per season:**
  - Bodies: a complete body is $10,600, and hanging one is $20-30k of labor. The body budget is ~$464k a year.
  - Brakes: $48,360.
  - Nuts, bolts and supplies: $18,000.
  - Confidence: medium (Autopian, above).
- **Game rule (EST):**
  - Weekly racer: spares worth **10-20% of the car's value** (one front clip's worth of suspension, a nose and body panels, 2-4 extra wheels).
  - Touring short-track team: **$25,000-50,000** (2017 dirt figures: 20,000 + 15,000 + 10,000 + 2,500 = $47,500, tools included).
  - National: **25-40% of the annual budget** goes to parts and bodies.

---

## 3. Cars: rollers, fleet size, chassis life

A **roller** is a complete car without engine and, usually, without transmission. Sellers often also strip the shocks, seat, ballast or electronics. Turnkey prices, and the new-chassis prices by class, are in `classes.json`. The figures below are roller-specific.

### 3.1 Roller prices by class
RacingJunk listings are undated but current as of 2025-26. They were seen through search snippets because the site blocks automated fetching. Confidence: low-medium; these are asking prices.

- **Asphalt late model (pro, super and late model stock chassis):**
  - Hamke rollers: $10,000 and $12,000 (no motor, transmission, shocks or seat). https://www.racingjunk.com/late-models/184814389/hamke-late-model.html
  - Hamke super/pro rebuilt by Preston Peltier: $25,500. https://www.racingjunk.com/late-models/184816003/hamke-car.html
  - Howe super/pro roller: $10,500. https://www.racingjunk.com/nascar-arca-asa-super-cup-hooters/184831860/howe-stock-car-super-pro-template-late-model-roller-for-sal.html
  - Port City and Fury: 2019 Fury/Port City pro roller $14,500; 2019 Port City Gen19 roller $20,000; 2021 Port City roller $20,000-24,000 ($40,000 turnkey). https://www.racingjunk.com/late-models/184827231/2021-port-city-late-model.html
  - Fury super late model: roller (no motor, transmission, seat or shocks) $45,000; complete car $55,000. https://www.racingjunk.com/late-models/184278907/fury-super-late-model-slm-car-sss-spec-complete.html
- **Dirt late model:**
  - Rocket XR1.2 roller (under 20 nights): $20,000. https://www.racingjunk.com/late-models/184795648/rocket-xr1.2-roller-less-than-20-nights-.html
  - 2023 Longhorn: $25,000 without shocks, $30,000 with Bilsteins. https://www.racingjunk.com/late-models/184815733/2023-longhorn-.html
  - 2018-19 Black Diamond: $17,000-19,500.
  - 2021 DRC: $6,500. https://www.racingjunk.com/late-models/184824174/2021-drc-dirt-late-model-roller.html
  - **New 2023:** complete rollers **$55,000-70,000**, "and you need multiple"; engines "another $55 grand" each. Confidence: medium. https://dirtrackr.com/daily/923
- **Sprint car (410/360):**
  - Old rollers $1,000-7,000 (2010 Maxim $2,000; J&J 88/40 $7,000). https://www.racingjunk.com/sprint-cars/184735430/sprintcar-for-sale.-j-j-88-40-roller.html
  - 2020 Maxim roller: ~$40,000 (snippet).
  - New top WoO car without engine: **$30,000-50,000** (2022). Confidence: medium. https://dirtrackr.com/daily/707
- **Modified:**
  - '97 Troyer crate roller: $6,500. '08 Troyer roller: $15,500.
  - 2023 PSR Pro NASCAR modified roller: **$35,000**. https://www.racingjunk.com/modifieds/184814368/nascar-modified-2023-psr-pro-chassis-selling-as-a-roller-.html
  - Dirt modified tour, 2017: two race-ready chassis $60,000, i.e. ~$30k each including running gear. Confidence: medium (FloRacing, above).
- **ARCA / Truck / Busch-era:**
  - Retired chassis: ARCA-legal roller $3,900; Laflen Monte Carlo ARCA roller $3,500; ex-Busch roller $5,000; 2004 Hopkins truck chassis $7,000. https://www.racingjunk.com/nascar-arca-asa-super-cup-hooters/184814308/arca-legal-roller-chassis-comp-body-sold-seperate.html
  - Newer: 2018 RCR Camaro ZL1 (Xfinity/ARCA-type) $15,000; NASCAR Canada roller $55,000. https://www.racingjunk.com/nascar-arca-asa-super-cup-hooters/184801522/2018-nascar-richard-childress-racing-chevy-camaro-zl1-roller.html
  - EST: an ARCA-competitive current roller (body hung, fresh) costs **$40,000-75,000**. This is bracketed by Xfinity chassis at $35-50k before body work (below) plus the $20-30k labor to hang a body (Autopian).
- **Xfinity (2025):** used 2015-2020 chassis ~$35,000; newer ~$50,000; ~7 chassis ≈ $250,000. Confidence: medium. https://www.theautopian.com/an-extraordinarily-detailed-accounting-of-how-much-it-really-costs-to-race-in-nascar

### 3.2 How many cars teams run
- **Cup (Next Gen, from 2022):** at most **7 cars per car number** in inventory. A car cannot be replaced until it has run 3 races, and NASCAR and the supplier decide whether a crashed chassis is repairable. Confidence: high/medium. https://www.cbssports.com/nascar/news/nascar-next-gen-car-explaining-the-ins-and-outs-of-the-nascar-cup-series-new-racecar-for-2022
  - Front Row Motorsports testimony (Dec 2025): parts spend rose from **$1.8M to $4.7M a year** under Next Gen. Repairing even an un-wrecked car costs ~$30,000 a week. Confidence: medium. https://www.ovalinsider.com/nascar-news/nascar-next-gen-car-cost-revealed-front-row-motorsports-trial-charlotte-court-1069683/
- **Xfinity (2025):** **7 minimum**: 2 short-track, 2 intermediate, 2 road-course, 1 superspeedway. Confidence: medium (Autopian, above).
- **ARCA / Trucks:** no clean source.
  - 2010 (out of window): a team owning "2 haulers, 20 cars and 12 engines" needed ~$1M a season (see `team_economics.md` §1.4).
  - EST: a competitive single entry keeps **4-6 cars**: short track (×2), intermediate/mile (×1-2), superspeedway (×1), road course (×1 if scheduled). A budget team keeps 2-3.
- **Dirt late model national tour:** **2 complete cars, 3 engines** (2017). Confidence: medium (FloRacing, above).
- **World of Outlaws sprint:** Kasey Kahne Racing builds "**at minimum five new cars**" a season for Brad Sweet. The trailer carries the primary, a backup and a "kit car" that can be finished at the track, plus several spare engines (2022). Confidence: medium. https://worldofoutlaws.com/sprintcars/off-season-what-off-season/
- **Weekly racers (EST):** street stock, limited late model and hobby classes run **1 car** with spare parts. Top weekly late model stock or super late model teams run **1 primary + 1 backup or rebuildable older car**. Crown-jewel entries (e.g. the Snowball Derby) sometimes bring a backup; one driver raced the backup after an engine failure in testing. https://www.shorttrackscene.com/?p=25034

### 3.3 Chassis life
- **Sprint cars:** EST. 5 new cars across ~90 nights (WoO, above) = **~18 nights per chassis on average**, before crash write-offs. That is consistent with `classes.json` `sprint_360.chassis_life = 1.5` seasons for a local schedule.
- **Dirt late model:** listings advertise "less than 20 nights" as a selling point. One forum account describes a 2016 chassis that sagged after 2 national seasons, so camber had to be dialed in, yet was "still just as fast". Confidence: low. https://www.racingjunk.com/late-models/184795648/rocket-xr1.2-roller-less-than-20-nights-.html
  - EST: national teams replace or rotate chassis every **1-2 seasons**. Weekly racers run one **3-5 seasons**. This matches `classes.json` `dirt_late_model.chassis_life = 3`.
- **Asphalt late model and modified:** no direct source. 10-20-year-old Troyer, Hamke and Howe rollers still trade at $6,500-15,000 (above), which shows long service life at the local level.
  - EST: competitive life of **3-6 seasons** for weekly racing, re-clipped or re-skinned along the way. This matches `classes.json` (late model stock 5, super late model 4, asphalt modified 5).
- **Cup:** 3-race minimum before a car may be replaced (above).

---

## 4. Engines: leases and spec programs
Purchase and rebuild prices for crate and built engines by class are already in `classes.json` (`engines[].usd`, `rebuild_usd`, `rebuild_races`). This section covers lease and spec-engine economics and the per-lap or per-mile cost they imply.

- **Ilmor 396 (ARCA spec engine, introduced 2015):**
  - **$35,000** per engine plus a required **$5,000 install kit** (headers, fuel parts).
  - Rebuilds cost **$10,000-15,000**. An engine must run at least 1,200 miles before a rebuild; it is designed for ~1,500.
  - Engines are sealed, and only Ilmor services them.
  - With ~4,500 miles a season, a team needs 2 engines and 1 refresh, **~$80,000 a season**.
  - The old lease model cost ~**$50,000 for just the two superspeedway races**, after which the engines went back.
  - Confidence: medium (EngineLabs, Dec 2014, about 2015).
  - https://www.enginelabs.com/?p=7958
  - EST per-mile cost: $12,500 / 1,350 mi ≈ **$9/mi** in rebuilds, plus depreciation.
- **Ilmor NT1 (Trucks, optional from 2018):**
  - A garage source put the engine at **~$38,000**; the ECU, Holley throttle body and adapters add **~$17,000**.
  - The team owns the engine and sends it to Ilmor every **1,500 miles**. Getting three or more races between rebuilds saves "in the neighborhood of 35 grand".
  - Confidence: low-medium (NASCAR.com, 2020, via search summary; the page returned 403). https://www.nascar.com/news-media/2020/02/08/ilmor-nt1-engine-powers-gander-rv-outdoors-truck-series/amp/
  - Top Truck teams still lease manufacturer engines (TRD, ECR, Roush Yates). No public per-race price was found.
- **Xfinity lease (2025):** **~$800,000 a season** (~$24,242 per race). Transmission and rear-gear rental is another $44,025 (~$1,335 per race), and shock leasing $26,400 ($800 per race). Confidence: medium (Autopian, above).
- **Cup lease:** $0.8-1.5M a season (low-medium; already in `team_economics.md` §3).
- **Short-track engine maintenance (2017):**
  - Dirt late model: **$10-12 per lap**, serviced every ~1,000 laps.
    - EST: **$10,000-12,000 per freshen**. With 3 engines at $36,000 each, the season maintenance budget is $35,000.
  - Dirt modified: **$5-8 per lap**, ~$20,000 a season for 60 races (~3,000 laps).
  - Confidence: medium (FloRacing, above).
- **World of Outlaws sprint (2022):** 410 rebuild every **15-20 nights**; $30,000 a season in engine rebuilds; a new 410 costs $70,000+. Confidence: medium. https://dirtrackr.com/daily/707
- **Crate seal repair:** $3,200 (2022, Performance Racing Industry). https://performanceracing.com/magazine/featured/06-01-2022/competition-costs
- **Short-track lease programs:** no published per-race lease rates were found for late model stock, super late model or modified engines (see Gaps).
  - CARS Tour sealing builders (Charlie's Automotive, PME, RW Engines) can re-verify and re-seal an engine instead of rebuilding it. https://www.shorttrackscene.com/?p=19563
  - EST for the game, a short-track lease or rental: price it like a freshen, plus depreciation, plus margin.
    - Late model stock / super late model: **$1,500-4,000 per race**. Basis: a $25-30k SLM engine refreshed every ~12 races at ~$9k is ~$750/race in rebuilds plus ~$1,000-1,500/race depreciation over ~25 races, then ×1.5 for margin.
    - Crown-jewel or one-off rentals: $5,000-10,000.

---

## 5. Crew, wages and travel

### 5.1 Weekly racers
- Crews are mostly unpaid friends and family. "Friends and family roll through ... on a volunteer basis" even at pro dirt level, and some winning dirt late model teams have zero full-time employees (2025). Confidence: medium. https://dirtrackr.com/daily/1353
  - Example: a 2025 IMCA racer lists ~10 crew, mostly relatives. https://www.dirtondirt.com/story_13775.html
- What the team actually pays is **pit passes** (often covered by the driver):
  - Owosso Speedway: $35 adult (2026). https://www.owossospeedway.com/ticketinfo/
  - Lucas Oil Speedway: $35. https://lucasoilspeedway.com/press/2024/article/160777
  - Grays Harbor: $40. https://10315.app.myracepass.com/fan-info/default.aspx
  - Valley Speedway: a $20 new-crew pit pass promotion. https://m.myracepass.com/tracks/2785/news/2025/article/165671/pit-crew-development-program
  - Confidence: high (track pages).
- **EST weekly crew cost:** 3-4 crew × $35 pass + ~$15 food each = **$150-200 per race night**, or $2,000-4,000 over a 15-20-night season.

### 5.2 Regional and national short-track touring
- **Dirt late model national (2017):**
  - Crew pay runs **$600-1,000+ per week**.
  - Budget **$70,000 a year** for two crew, plus $10,000 for food and miscellaneous.
  - The crew live in the toter, so there are no hotels.
  - Good crew are scarce: only "five to 10" top hired hands are available for 40+ national teams.
  - Confidence: medium. https://www.floracing.com/articles/5065805-good-men-are-hard-to-find-for-the-national-tour-but-are-so-necessary
- **World of Outlaws sprint (2022):**
  - Crew chief ~**$100,000+** a year; car chief ~**$1,000 a week**; tire specialist **$600-800 a week**.
  - 3 full-time crew cost ~$200,000; hotels **$100,000** a season over ~75 race nights.
  - Confidence: medium. https://dirtrackr.com/daily/707
  - EST check on hotels: ~165 nights away × 4 rooms × ~$150 ≈ $99,000, consistent with $100k.
  - Pro crews are typically three paid people (crew chief, car chief, tire guy) plus the driver. https://dirtrackr.com/daily/1353
- **Super late model crown jewels:** hired NASCAR pit crews cost ~$5,000 a race (Snowball Derby, pre-2019; in `team_economics.md` §1.5).

### 5.3 ARCA / Truck / Xfinity
- **Xfinity (2025) salaries:**
  - Crew chief $100,000-150,000; car chief $80,000-100,000; mechanic $50,000-70,000.
  - Hauler driver $60,000-80,000; spotter $26,000-33,000.
  - Total road and shop payroll: $674,500 for 8 people.
  - Over-the-wall pit crew rental: $260,000 a season (~$8,125 per race).
  - NASCAR licenses: $2,000 each.
  - Confidence: medium (Autopian, above).
- **Hauler driver:** a trucking forum says NASCAR hauler drivers average ~$80,000; experienced drivers at major teams make $100,000+ with bonuses on 65,000-70,000 miles a year. Confidence: low. https://www.thetruckersreport.com/truckingindustryforum/threads/nascar-hauler-drivers-make-on-average-80k-a-year.2543408/
- **Entry-level ARCA / Truck crew:** ~$50,000-70,000 a year. Per-race contractors are paid ~$500-2,500. Confidence: low (aggregator and search summaries). https://flowracers.com/blog/nascar-pit-crew-salaries/
- **2017:** Kyle Busch said a competitive truck cost $3.2M a season and "your biggest expense is your people". Confidence: high (owner quote). https://www.foxsports.com/stories/nascar/kyle-busch-talks-about-real-cost-of-going-racing

### 5.4 Travel, per diem and hotels
- **Xfinity (2025):**
  - Hotels **$300 a night**; rental cars **$75 a day**.
  - Charter flights **$1,100 per person per weekend**.
  - Crew per diem **$25 a day** ($10,500 a season); some teams pay $60 a day ($25,200).
  - Catering $40 per person per day (~$480 per race).
  - Travel budget ~$207,300 a season.
  - Confidence: medium (Autopian, above).
- **Federal benchmark, FY2026:** standard CONUS lodging **$110** and M&IE **$68** per day; unchanged from FY2025. Confidence: high. https://www.govinfo.gov/content/pkg/FR-2025-08-19/html/2025-15771.htm
- **Older Cup benchmark:** in 2014 Stewart-Haas Racing data, flights and 44 hotel rooms per race weekend were $82,000+ (low, out of window). https://www.nbcnewyork.com/news/national-international/race-car-costs-the-high-price-of-fielding-a-racing-team/2047990/
- **Game rule (EST), per traveling person per weekend:**
  - Regional short-track tour, 2 nights: 2 × ($130 room ÷ 2 sharing + $40 food) = **~$210**.
  - National short-track tour: the toter replaces hotels; food ~$40-60 a day.
  - ARCA/Truck, 3 nights: 3 × ($200 + $40-60) + ~$225 car-rental share (3 days × $75) = **~$950-1,000**.
  - Xfinity/Cup, flying: 3 × ($300 + $60) + $1,100 charter = **~$2,200**.

---

## 6. Gaps
- **Seven-post rig rental rates:** no public per-day or per-session price was found for ARC, Ohlins or Penske rigs. The only cost found was "millions" to own (IndyCar 2016) and an unsourced $7-8M (forum). Treat rig access as a contract or OEM-alliance perk, or EST $10-20k a day by analogy to the Dallara sim's $12k a day.
- **Short-track engine lease rates** (late model stock, super late model, modified, dirt late model): no published per-race rates. Only purchase, rebuild and per-lap figures exist. The EST is in §4.
- **Truck Series manufacturer lease prices** (TRD, ECR, Roush Yates): not public. Only NT1 purchase and rebuild figures were found.
- **Cup hauler prices:** the only figures are a 2014 team number ($400k) and an unattributed 2025 aggregator range ($0.6-1.2M). No builder (Featherlite, Pegasus, United Express) publishes prices.
- **New roller list prices** from chassis builders (Port City, Fury, Rowdy/Hamke, Longhorn, Rocket, Maxim, J&J): builders publish none. Only used asking prices (RacingJunk snippets) and a 2023 dirt late model quote ($55-70k) were found.
- **ARCA and Truck fleet size and chassis life:** no current source. The 2010 "20 cars, 12 engines" figure is out of window.
- **Chassis life in races or seasons** for asphalt late models and modifieds: no source. ESTs align with `classes.json` `chassis_life`.
- **Engine dyno and engine-shop tooling costs:** only an undated forum figure ($70-80k for a SuperFlow 902 cell).
- **Toter home new prices:** only used listings ($48.5k-149k) and "million dollar" descriptions; no new MSRP.
- **Insurance for commercial (sponsored) race haulers** (auto liability, cargo, USDOT): not found. ATRI's $0.099/mi freight average is the best proxy.
- **CDL / "in commerce" guidance:** the FMCSA interpretation page returned 403 and was read only via a search summary. State rules (e.g. New York) differ.
- **Blocked sources, skipped without workarounds:** Sportskeeda hauler article, Overdrive "Off to the races", Frontstretch (hauler logistics, Van Alst ARCA budget, crew pay), Jayski 2018 engine options article, NASCAR.com NT1 article, RacingJunk category pages.
