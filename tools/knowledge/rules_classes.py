"""Curated car classes -> data/rules/classes.json.

Each class lists the chassis, engine, shock and tire options racers actually buy under the class
rules, with prices in 2025 USD. The values are taken from the researched ranges in
data/rules/research.json (cited by source id in each class's ``facts``); ``quality`` is a design
value for how competitive a part is within its class after rules balancing (weight breaks, seals).
Edit here, then run:  python tools/knowledge/rules_classes.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "data" / "rules" / "classes.json"

def F(lo, hi, unit, conf, src, notes=None):
    d = {"min": lo, "max": hi, "unit": unit, "confidence": conf, "sources": src}
    if notes: d["notes"] = notes
    return d

def ch(key, label, usd, q, age=0, note=""):
    return {"key": key, "label": label, "usd": usd, "quality": q, "age": age, **({"note": note} if note else {})}

def en(key, label, usd, q, reb=0, races=0, claim=0, sealed=False, wb=0, years=None, note=""):
    d = {"key": key, "label": label, "usd": usd, "quality": q, "rebuild_usd": reb, "rebuild_races": races}
    if claim: d["claim_usd"] = claim
    if sealed: d["sealed"] = True
    if wb: d["weight_break_lb"] = wb
    if years: d["years"] = years
    if note: d["note"] = note
    return d

def sh(key, label, usd, q, claim=0):
    d = {"key": key, "label": label, "usd": usd, "quality": q}
    if claim: d["claim_usd"] = claim
    return d

C = {}

# ------------------------------------------------------------------ entry / youth
C["quarter_midget"] = dict(label="Quarter midget", discipline="asphalt_oval", templates=["quarter_midget"], spread=0.6,
  chassis=[ch("used", "Used quarter midget", 2500, 45, 3), ch("new", "New chassis (Stanley/Bullrider-type)", 6000, 72)],
  engines=[en("honda120", "Honda 120 / Briggs Animal (class spec)", 900, 60, 250, 20, note="Class-spec engines; frequent freshens keep them legal")],
  shocks=[sh("stock", "Stock shocks", 0, 50), sh("tuned", "Tuned shock package", 600, 65)],
  tires={"usd": 175, "typical_new": 1, "max_new": None, "life_races": 5, "spec": "Hoosier Little Car LC series", "rule": "Hoosier little-car compounds by class"},
  chassis_life=6, entry_usd=60, fuel_usd=15, misc_usd=60, repair_frac=0.08,
  rules=["Ages 5-16, classes by engine and age", "Club-run racing on 1/20-mile ovals"],
  facts={"tire_usd": F(175, 175, "USD per tire", "high", ["src:hoosier_midatl_asphalt_2026"])},
  sources=["src:hoosier_midatl_asphalt_2026"], confidence="low",
  notes="Only the tire price is sourced; chassis and engine costs are estimates.")

C["bandolero"] = dict(label="Bandolero", discipline="asphalt_oval", templates=["bandolero"], spread=0.5,
  chassis=[ch("used", "Used Bandolero", 6000, 55, 3), ch("new", "New Bandolero (INEX)", 11000, 70)],
  engines=[en("vanguard", "Briggs & Stratton Vanguard (sealed, INEX spec)", 1500, 65, 400, 30, sealed=True)],
  shocks=[sh("spec", "INEX spec shocks", 0, 60)],
  tires={"usd": 140, "typical_new": 1, "max_new": 2, "life_races": 6, "spec": "Hoosier Bandolero Edition",
         "rule": "As delivered by INEX/USLCI; minimum durometer 62; no soaking or siping"},
  chassis_life=8, entry_usd=75, fuel_usd=15, misc_usd=80, repair_frac=0.08, min_weight_lb=750,
  rules=["Spec car from INEX: sealed Briggs Vanguard engine", "Minimum weight 750 lb with driver", "Ages 8-16"],
  facts={"min_weight_lb": F(750, 750, "lb", "high", ["src:inex_rulebook_2025"])},
  sources=["src:inex_rulebook_2025", "src:inex_summer_tires_2024"], confidence="medium",
  notes="Tire and car prices are estimates; rules from the INEX rulebook.")

C["legends"] = dict(label="Legend car", discipline="asphalt_oval", templates=["legends_regional"], spread=0.55,
  chassis=[ch("used_old", "Used Legend car (well raced)", 9000, 45, 5), ch("used", "Used Legend car (1-2 yrs)", 14000, 60, 2),
           ch("new", "New INEX Legend car", 19000, 72)],
  engines=[en("yamaha1200", "Yamaha FJ1200 / XJR1250 (sealed spec)", 3500, 65, 1500, 30, sealed=True),
           en("fz09", "Yamaha FZ09 / MT09 (newer spec option)", 6000, 67, 1500, 40, sealed=True, wb=-50, years=[2020, 2100],
              note="Rules dropped 50 lb on FZ09 cars")],
  shocks=[sh("spec", "Spec shocks", 0, 55), sh("built", "Built spec-legal shocks", 1200, 65)],
  tires={"usd": 150, "typical_new": 2, "max_new": None, "life_races": 4, "spec": "Hoosier (USLCI-marked)",
         "rule": "USLCI-marked Hoosiers only; minimum durometer 61; national events impound 4-6 new tires"},
  chassis_life=7, entry_usd=90, fuel_usd=30, misc_usd=180, repair_frac=0.10, min_weight_lb=1300,
  rules=["5/8-scale spec car from INEX", "Sealed Yamaha motorcycle engines; teardown protest fee $2,000",
         "No tire treatment; durometer checks"],
  facts={"min_weight_lb": F(1230, 1300, "lb", "high", ["src:inex_rulebook_2025"]),
         "protest_fee": F(2000, 2000, "USD", "high", ["src:inex_rulebook_2025"])},
  sources=["src:inex_rulebook_2025", "src:inex_summer_tires_2024", "src:inex_asphnat_tires_2024", "src:usl_tt_tires_2025"],
  confidence="medium")

C["mini_stock"] = dict(label="Mini stock / 4-cylinder", discipline="asphalt_oval", templates=["local_mini_stock"], spread=0.7,
  chassis=[ch("junker", "Converted street car", 1500, 40, 0), ch("built", "Built 4-cylinder racer", 4000, 60, 1),
           ch("top", "Top-built mini stock", 7500, 72)],
  engines=[en("stock", "Stock 4-cylinder", 600, 55, 300, 30), en("fresh", "Freshened stock-spec 4-cylinder", 1800, 65, 500, 30)],
  shocks=[sh("oe", "OE replacement shocks/struts", 200, 50)],
  tires={"usd": 110, "typical_new": 1, "max_new": None, "life_races": 6, "spec": "DOT street tires",
         "rule": "DOT street tires (e.g. treadwear 200+ and $135 retail cap at LVMS; 400+ treadwear at Wiscasset)"},
  chassis_life=6, entry_usd=50, fuel_usd=20, misc_usd=20, repair_frac=0.20, min_weight_lb=2300,
  rules=["Stock front-wheel-drive 3/4-cylinder cars", "OE-type non-adjustable shocks", "No tire softeners"],
  facts={"min_weight_lb": F(2000, 2600, "lb", "high", ["src:lvms_mini_2025", "src:wisc_t4_2025", "src:langley_ucar_2025"]),
         "tire_cap_usd": F(0, 135, "USD per tire", "high", ["src:lvms_mini_2025"])},
  sources=["src:lvms_mini_2025", "src:wisc_t4_2025", "src:langley_ucar_2025", "src:galesburg-burg-pay"], confidence="medium")

C["street_stock"] = dict(label="Street stock", discipline="asphalt_oval", templates=["local_street_stock"], spread=0.8,
  chassis=[ch("used_old", "Old street stock", 3500, 40, 6), ch("used", "Used race-ready street stock", 7500, 58, 2),
           ch("new", "New-built street stock", 15000, 74)],
  engines=[en("built350", "Built stock-production 350/351", 4500, 62, 2000, 30),
           en("crate602", "GM 602 sealed crate (~350 hp)", 7800, 66, 2500, 50, sealed=True, years=[2002, 2100],
              note="Many tracks allow the 602 as a cost-control option")],
  shocks=[sh("oe", "Over-the-counter shocks", 300, 50, claim=100), sh("spec", "Listed race shocks (AFCO/Pro)", 520, 62, claim=130)],
  tires={"usd": 150, "typical_new": 1, "max_new": 2, "life_races": 5, "spec": "Hoosier 700/790/F-45 track tire",
         "rule": "Official track tire bought and impounded at the track; no conditioners"},
  chassis_life=7, entry_usd=80, fuel_usd=40, misc_usd=40, repair_frac=0.18, min_weight_lb=3200,
  claims=["Shocks claimable ($50-200 per shock depending on track)"],
  rules=["Stock-production V8 or GM 602 crate", "Official spec tire bought at the track", "Non-adjustable listed shocks"],
  facts={"min_weight_lb": F(2900, 3260, "lb", "high", ["src:wisc_strictly_2025", "src:hickory_street_2022", "src:nss_superstock_2026"]),
         "crate602_usd": F(7300, 8300, "USD", "medium", ["src:slashgear_602_2025", "src:racingnews_crate_2018"]),
         "shock_claim_usd": F(50, 200, "USD per shock", "high", ["src:wisc_strictly_2025", "src:hickory_street_2022", "src:nss_superstock_2026"])},
  sources=["src:wisc_strictly_2025", "src:wisc_superstreet_2025", "src:hickory_street_2022", "src:nss_superstock_2026",
           "src:slashgear_602_2025", "src:galesburg-ss-pay"], confidence="medium")

C["limited_late_model"] = dict(label="Limited late model (crate)", discipline="asphalt_oval", templates=["local_limited_late"], spread=0.85,
  chassis=[ch("used_old", "Old late model chassis", 9000, 42, 5), ch("used", "Used late model (1-2 yrs)", 22000, 60, 2),
           ch("new", "New chassis, regional builder", 38000, 74), ch("top", "New chassis, top builder", 50000, 84)],
  engines=[en("built", "Built 'little motor' (iron head 350/351)", 9000, 60, 3500, 25, years=[1995, 2100]),
           en("crate602", "GM 602 sealed crate", 7800, 64, 2500, 60, sealed=True, years=[2002, 2100], wb=-50),
           en("crate604", "GM 604 sealed crate (~400 hp)", 9500, 70, 3500, 50, sealed=True, years=[2002, 2100]),
           en("d347sr", "Ford D347SR sealed crate", 11000, 70, 3500, 50, sealed=True, years=[2010, 2100])],
  shocks=[sh("budget", "Non-adjustable listed shocks", 1000, 50), sh("claimer", "Claimer-legal race shocks", 2400, 66, claim=600)],
  tires={"usd": 200, "typical_new": 2, "max_new": 2, "life_races": 3, "spec": "Hoosier F-45 / 880 or American Racer",
         "rule": "Track-bought tires, usually a 2-new-tire rule; must start the feature on qualifying tires"},
  chassis_life=6, entry_usd=150, fuel_usd=90, misc_usd=420, repair_frac=0.12, min_weight_lb=3100,
  claims=["Shocks claimable ($250-600 each) by cars finishing ahead"],
  rules=["Sealed GM 602/604 or Ford crate engines; broken seals are illegal", "Weight breaks between engine packages (25-125 lb)",
         "Two new tires per night is common", "Claimable shocks keep shock budgets down"],
  history=[{"year": 2002, "fact": "GM circle-track crate engines arrive; tracks start crate late model classes"}],
  facts={"min_weight_lb": F(2625, 3100, "lb", "high", ["src:hickory_llms_2025", "src:stafford_llm_2025", "src:langley_llm_2025", "src:slinger_lm_2026", "src:owosso_lms"]),
         "crate604_usd": F(6000, 10300, "USD", "medium", ["src:racingnews_crate_2018", "src:speedtalk_604_snip"]),
         "crate_refresh_usd": F(1800, 5000, "USD", "low", ["src:speedtalk_604_snip"]),
         "shock_claim_usd": F(250, 600, "USD per shock", "high", ["src:hickory_llms_2025", "src:langley_llm_2025"])},
  sources=["src:hickory_llms_2025", "src:stafford_llm_2025", "src:langley_llm_2025", "src:slinger_lm_2026", "src:owosso_lms",
           "src:racingnews_crate_2018", "src:act_lm_2025"], confidence="medium")

C["late_model_stock"] = dict(label="Late model (weekly top division)", discipline="asphalt_oval", templates=["local_late_model"], spread=0.9,
  chassis=[ch("used_old", "Old late model", 15000, 42, 5), ch("used", "Used late model (1-2 yrs)", 35000, 60, 2),
           ch("new", "New car, regional builder", 55000, 74), ch("top", "New car, top builder", 70000, 85)],
  engines=[en("crate604", "GM 604 sealed crate", 9500, 64, 3500, 50, sealed=True, years=[2002, 2100], claim=10000),
           en("d347sr", "Ford D347SR sealed crate", 11000, 66, 3500, 50, sealed=True, years=[2010, 2100], claim=12000),
           en("built", "Built late model stock engine (NASCAR LMSC rules)", 22000, 82, 6000, 20),
           en("spec", "Harrington Enforcer spec engine", 16000, 76, 4500, 30, years=[2016, 2100])],
  shocks=[sh("listed", "Approved non-adjustable shocks", 1600, 52), sh("top", "Top shock package (single-adjustable)", 4000, 70)],
  tires={"usd": 200, "typical_new": 4, "max_new": 4, "life_races": 2, "spec": "Hoosier F-45 (track-bought)",
         "rule": "Up to 4 race tires per event bought day-of, scanned and impounded"},
  chassis_life=5, entry_usd=200, fuel_usd=120, misc_usd=800, repair_frac=0.12, min_weight_lb=3100,
  claims=["Crate engines claimable at some tracks (GM 604 $10,000, Ford D347SR $12,000)", "Carburetor claim $1,200"],
  rules=["Late Model Stock: built engines, sealed crates or the Harrington spec engine, with weight adjustments",
         "Track-bought Hoosier tires, impounded", "Steel bodies (or approved composite), 3,100 lb minimum"],
  history=[{"year": 1995, "fact": "Mid-1990s LMS engine ~$10-15k; Hoosier tires ~$100-120 mounted"},
           {"year": 2018, "fact": "LMS tire ~$200; a competitive car turns over a set a week"}],
  facts={"min_weight_lb": F(3050, 3150, "lb", "high", ["src:hickory_lms_2024", "src:cars_rulebook_2025_snippet"]),
         "turnkey_car_usd": F(70000, 70000, "USD", "medium", ["src:sts_slm_vs_lms"]),
         "tire_usd_2018": F(200, 200, "USD per tire", "medium", ["src:sts_dalejr_2018"]),
         "tire_usd_1995": F(100, 120, "USD per tire (nominal)", "medium", ["src:sobo_2021_costs"]),
         "engine_claim_usd": F(10000, 12000, "USD", "high", ["src:hickory_lms_2024"])},
  sources=["src:hickory_lms_2024", "src:cars_rulebook_2025_snippet", "src:sts_slm_vs_lms", "src:sts_dalejr_2018", "src:sobo_2021_costs",
           "src:search-cars-2024"], confidence="medium")

C["super_late_model"] = dict(label="Super late model", discipline="asphalt_oval", templates=["late_model_tour", "late_model_national"], spread=1.0,
  chassis=[ch("used", "Used super late model", 40000, 55, 2), ch("new", "New car, regional builder", 75000, 72),
           ch("top", "New car, top builder (turnkey)", 100000, 86)],
  engines=[en("built", "Built open/9:1 engine (~630 hp)", 30000, 84, 9000, 12, years=[1995, 2100]),
           en("ct525", "GM CT525 sealed crate", 11500, 68, 4000, 40, sealed=True, years=[2014, 2100]),
           en("sealed", "SEAL sealed engine (Hamner/McGunegill)", 24000, 82, 7000, 20, sealed=True, years=[2008, 2100]),
           en("sspe", "Southern Super Parts Engine (SSPE)", 26000, 86, 7000, 15, claim=26000, years=[2015, 2100],
              note="Claimable for about $26,000 in ASA southern rules")],
  shocks=[sh("budget", "Twin-tube non-adjustables", 800, 50), sh("mid", "Single-adjustable package", 4000, 68),
          sh("top", "Top shock program", 9000, 84)],
  tires={"usd": 242, "typical_new": 4, "max_new": None, "life_races": 1.5, "spec": "Hoosier ST/F-45 27.0x10.0-15",
         "rule": "Event tires marked and impounded; crown jewels allot a fixed stack (Snowball Derby: 28 tires per car)"},
  chassis_life=4, entry_usd=350, fuel_usd=200, misc_usd=1600, repair_frac=0.12, min_weight_lb=2800,
  claims=["SSPE engines claimable (~$21,000-26,000 by series)"],
  rules=["Engine menu: built/9:1, sealed (SEAL), CT525 crate, SSPE - balanced with weight", "Max 56-58% left side",
         "Event tires marked; must start the feature on qualifying tires", "MSRP caps on calipers ($850) and clutches ($1,600) in unified rules"],
  history=[{"year": 2008, "fact": "Sealed 'SEAL' engine programs spread to cut engine costs"},
           {"year": 2014, "fact": "GM CT525 crate becomes an option in super late model rules"}],
  facts={"min_weight_lb": F(2675, 2850, "lb", "high", ["src:fiveflags_slm_2025", "src:uma_slm_2026", "src:big5_slm_2025", "src:lvms_slm_2020"]),
         "tire_usd": F(242, 242, "USD per tire", "high", ["src:hoosier_midatl_asphalt_2026"]),
         "built_engine_usd": F(25000, 30000, "USD", "medium", ["src:sts_slm_vs_lms"]),
         "turnkey_car_usd": F(100000, 100000, "USD", "medium", ["src:sts_slm_vs_lms"]),
         "sspe_claim_usd": F(21000, 26500, "USD", "high", ["src:fiveflags_slm_2025", "src:big5_slm_2025", "src:srl_2022"]),
         "snowball_tires": F(28, 28, "tires per car", "high", ["src:snowball_tire_2025"])},
  sources=["src:fiveflags_slm_2025", "src:uma_slm_2026", "src:big5_slm_2025", "src:lvms_slm_2020", "src:evergreen_slm_2016",
           "src:hoosier_midatl_asphalt_2026", "src:sts_slm_vs_lms", "src:snowball_tire_2025", "src:srl_2022"], confidence="medium")

C["asphalt_modified"] = dict(label="Asphalt modified (SK / tour type)", discipline="asphalt_oval", templates=["modified_tour"], spread=0.95,
  chassis=[ch("used", "Used modified (Troyer/Chassis Dynamics-type)", 30000, 55, 2), ch("new", "New modified chassis", 55000, 72),
           ch("top", "New car, top builder", 75000, 85)],
  engines=[en("sk_spec", "SK spec engine (Chevy 350, spec parts)", 18000, 70, 5000, 20),
           en("crate604", "GM 604 sealed crate (SK Light / 604 Modified)", 9500, 60, 3500, 50, sealed=True, years=[2008, 2100]),
           en("nascar_spec", "NASCAR spec engine (Whelen Modified Tour)", 32000, 80, 8000, 12, years=[2015, 2100]),
           en("built", "Built steel-block small-block (355-368 ci)", 40000, 86, 10000, 10)],
  shocks=[sh("listed", "Listed coil-overs (capped price)", 2000, 58), sh("top", "Top shock program", 6000, 78)],
  tires={"usd": 175, "typical_new": 4, "max_new": None, "life_races": 2, "spec": "Hoosier (American Racer from 2026 on the Whelen Mod Tour)",
         "rule": "Sole-supplier tires bought at the track; tour limits race tires per event (e.g. 10 purchasable, 7 usable)"},
  chassis_life=5, entry_usd=300, fuel_usd=180, misc_usd=900, repair_frac=0.15, min_weight_lb=2645,
  rules=["Open-wheel asphalt modifieds: spec SK engines weekly, built engines on tour", "Coil-over shocks from a published list",
         "Tour tire limits per event"],
  facts={"min_weight_lb": F(2525, 2660, "lb", "high", ["src:stafford_sk_2025", "src:speedbowl_sk_2025", "src:thompson_sklite_2025"]),
         "tour_tire_usd": F(150, 190, "USD per tire", "medium", ["src:aarn_wmt_tires_2015"]),
         "engine_usd": F(24000, 40000, "USD", "medium", ["src:racedayct_wmt_engines_2015"]),
         "shock_cap_usd": F(500, 500, "USD per shock", "high", ["src:speedbowl_sk_2025"])},
  sources=["src:stafford_sk_2025", "src:speedbowl_sk_2025", "src:thompson_sklite_2025", "src:aarn_wmt_tires_2015",
           "src:racedayct_wmt_engines_2015", "src:racedayct_ar_wmt_2026"], confidence="medium")

# ------------------------------------------------------------------ dirt weekly
C["sport_compact"] = dict(label="Sport compact", discipline="dirt_oval", templates=["local_sport_compact"], spread=0.65,
  chassis=[ch("junker", "Converted front-drive compact", 1200, 45, 0), ch("built", "Well-built compact", 3500, 65, 1)],
  engines=[en("stock", "Stock OEM 4-cylinder", 500, 60, 250, 40)],
  shocks=[sh("oe", "OE shocks", 150, 50)],
  tires={"usd": 80, "typical_new": 0, "max_new": None, "life_races": 8, "spec": "DOT passenger tires", "rule": "Any DOT passenger tire, 60 series or taller"},
  chassis_life=5, entry_usd=50, fuel_usd=20, misc_usd=35, repair_frac=0.25,
  claims=["Whole car claimable for $1,500 cash (or $500 plus exchange) - IMCA Sport Compact"],
  rules=["Stock front-wheel-drive 3/4-cylinder cars", "Complete-car claim rule caps spending"],
  facts={"car_claim_usd": F(1500, 1500, "USD", "high", ["src:imca_spc_2026"])},
  sources=["src:imca_spc_2026"], confidence="medium")

C["hobby_stock"] = dict(label="Hobby / factory stock", discipline="dirt_oval", templates=["local_hobby_dirt"], spread=0.75,
  chassis=[ch("oem", "OEM-frame hobby stock", 3500, 45, 3), ch("built", "Well-built OEM-frame car", 8000, 62, 1),
           ch("roller", "New roller (Charger-type)", 18000, 75)],
  engines=[en("claim", "Claim engine (stock 350)", 2500, 60, 1000, 40, claim=550),
           en("crate602", "GM 602 sealed crate", 7300, 66, 2500, 60, sealed=True, years=[2002, 2100])],
  shocks=[sh("stock", "Stock-type shocks", 200, 50, claim=50)],
  tires={"usd": 90, "typical_new": 1, "max_new": None, "life_races": 6, "spec": "DOT passenger tires (IMCA) / Hoosier (UMP)", "rule": "DOT 205/70-75 passenger tires (IMCA)"},
  chassis_life=6, entry_usd=60, fuel_usd=35, misc_usd=60, repair_frac=0.2,
  claims=["Engine claim $550, shocks $50 each, carburetor $100 (IMCA Hobby Stock)", "UMP Factory Stock: whole car claim $1,000"],
  rules=["Stock frames and stock-appearing engines", "Claim rules keep engines cheap"],
  history=[{"year": 1997, "fact": "IMCA engine claim price $325 (1989-97); about $550 today for most divisions"}],
  facts={"engine_claim_usd": F(550, 550, "USD", "high", ["src:imca_hs_2026"]),
         "roller_usd": F(3995, 19995, "USD", "high", ["src:charger_2026"]),
         "build_usd": F(3500, 10000, "USD", "low", ["src:dirttrackhq_cost"])},
  sources=["src:imca_hs_2026", "src:dirtcar_fs_2026", "src:charger_2026", "src:dirttrackhq_cost", "src:verdegan_1997"], confidence="medium")

C["dirt_modified"] = dict(label="Dirt modified (IMCA/UMP type)", discipline="dirt_oval", templates=["local_dirt_modified", "dirt_modified_tour"], spread=0.85,
  chassis=[ch("used_old", "Old modified", 6000, 42, 5), ch("used", "Used modified (1-2 yrs)", 12000, 60, 2),
           ch("new", "New roller", 22000, 74), ch("top", "New roller, top builder", 27000, 84)],
  engines=[en("claim_budget", "Claim engine (budget build)", 4500, 58, 2000, 30, claim=1050, years=[1995, 2100]),
           en("claim_strong", "Claim engine (strong build)", 12000, 76, 4000, 25, claim=1050, years=[1995, 2100],
              note="Worth far more than the claim price: a target if you win"),
           en("crate604", "GM 604 sealed crate", 9500, 70, 3500, 60, sealed=True, years=[2013, 2100]),
           en("imca_spec", "IMCA spec engine", 13100, 74, 4000, 40, years=[2025, 2100])],
  shocks=[sh("steel", "Steel non-adjustable shocks", 600, 55, claim=100), sh("top", "Top non-adjustable package", 1200, 68, claim=100)],
  tires={"usd": 180, "typical_new": 1, "max_new": None, "life_races": 4, "spec": "Hoosier G60-15 IMCA-stamped (spec)",
         "rule": "IMCA spec tire (Hoosier since 2005); grooving allowed since 2021"},
  chassis_life=5, entry_usd=110, fuel_usd=70, misc_usd=420, repair_frac=0.12, min_weight_lb=2450,
  claims=["Engine claim $1,050 (IMCA Modified; $550 UMP, winner only)", "Shocks $100 each (IMCA), $350 (UMP)"],
  rules=["Steel non-adjustable shocks, one per wheel (IMCA)", "Claim engine or sealed 604 crate; IMCA spec engine from 2025",
         "Spec Hoosier tire; 2,450 lb minimum"],
  history=[{"year": 1997, "fact": "IMCA engine claim $325; Wisconsin claimer engines cost $1,200-4,500 to build"},
           {"year": 2005, "fact": "Hoosier becomes IMCA's spec tire supplier"},
           {"year": 2013, "fact": "IMCA allows the GM 604 crate in Modifieds"},
           {"year": 2025, "fact": "IMCA adds a spec engine option"}],
  facts={"min_weight_lb": F(2400, 2500, "lb", "high", ["src:imca_mod_2026", "src:dirtcar_ump_mod_2026", "src:wissota_mod_2026", "src:usra_mod_2025"]),
         "tire_usd": F(165, 197, "USD per tire", "medium", ["src:hoosier_g60_retail"]),
         "crate604_usd": F(8000, 12300, "USD", "medium", ["src:crate_prices_2025"]),
         "spec_engine_usd": F(13000, 13200, "USD", "medium", ["src:imca_spec_2025"]),
         "engine_claim_usd": F(550, 1050, "USD", "high", ["src:imca_mod_2026", "src:dirtcar_ump_mod_2026"]),
         "roller_usd": F(20000, 25000, "USD", "low", ["src:vc_mod_chassis", "src:dirttrackhq_cost"])},
  sources=["src:imca_mod_2026", "src:imca_mod_2024", "src:dirtcar_ump_mod_2026", "src:wissota_mod_2026", "src:usra_mod_2025",
           "src:hoosier_g60_retail", "src:crate_prices_2025", "src:imca_spec_2025", "src:verdegan_1997", "src:vc_mod_chassis"],
  confidence="medium")

C["dirt_late_model"] = dict(label="Dirt late model", discipline="dirt_oval", templates=["local_dirt_late_model", "dirt_late_model_tour"], spread=1.05,
  chassis=[ch("used", "Used late model", 25000, 55, 2), ch("new", "New car, regional builder", 45000, 72),
           ch("top", "New car, top builder (Longhorn/Rocket-type)", 60000, 86)],
  engines=[en("crate604", "GM 604 sealed crate", 9500, 55, 3500, 50, sealed=True, years=[2002, 2100]),
           en("ct525", "GM CT525 sealed crate", 11500, 66, 4000, 40, sealed=True, years=[2014, 2100]),
           en("open", "Open aluminum engine (800-900 hp)", 55000, 90, 11000, 15)],
  shocks=[sh("budget", "Budget mono-tubes", 2500, 52), sh("top", "Top shock program", 12000, 82)],
  tires={"usd": 240, "typical_new": 2, "max_new": None, "life_races": 1.5, "spec": "Hoosier NLMT2/3/4 (LCB/VCB)",
         "rule": "Spec Hoosier list; track or series picks the right-rear compound"},
  chassis_life=3, entry_usd=200, fuel_usd=180, misc_usd=1400, repair_frac=0.12, min_weight_lb=2350,
  rules=["Open engines (cam-in-block, single 4-bbl) or sealed crates, balanced by weight", "2,350 lb minimum (WoO/Lucas/DIRTcar)",
         "Spec Hoosier tires"],
  history=[{"year": 2014, "fact": "CT525 sealed crate becomes a low-cost late model option"}],
  facts={"min_weight_lb": F(2300, 2350, "lb", "high", ["src:dirtcar_lm_2026", "src:woo_lm_rules", "src:lolmds_2025", "src:los_lm"]),
         "open_engine_usd": F(40000, 70000, "USD", "medium", ["src:jj_dlm_engines", "src:lolmds_2025"]),
         "engine_life_laps": F(800, 1200, "laps", "medium", ["src:lolmds_2025"]),
         "tire_usd": F(230, 249, "USD per tire", "medium", ["src:hoosier_nlmt_retail"]),
         "complete_car_usd": F(25000, 100000, "USD", "low", ["src:jj_dlm_cost"])},
  sources=["src:dirtcar_lm_2026", "src:woo_lm_rules", "src:lolmds_2025", "src:los_lm", "src:jj_dlm_engines", "src:hoosier_nlmt_retail",
           "src:jj_dlm_cost", "src:flo_summernats_2017"], confidence="medium")

C["sprint_360"] = dict(label="360 sprint car", discipline="dirt_oval", templates=["local_sprint", "sprint_car_tour"], spread=1.0,
  chassis=[ch("used", "Used sprint car", 12000, 55, 1), ch("new", "New roller", 25000, 76), ch("top", "New roller, top builder", 32000, 86)],
  engines=[en("built360", "360 steel-block (budget build)", 25000, 70, 6000, 15),
           en("top360", "Top 360 (700-750 hp)", 40000, 86, 9000, 12)],
  shocks=[sh("std", "Standard shocks", 1500, 55), sh("top", "Top shock program", 5000, 80)],
  tires={"usd": 300, "typical_new": 1, "max_new": None, "life_races": 1.5, "spec": "Hoosier 105/16-15 right rear", "rule": "Spec Hoosier list"},
  chassis_life=1.5, entry_usd=150, fuel_usd=120, misc_usd=1000, repair_frac=0.18, min_weight_lb=1475,
  rules=["360 ci steel block", "Sprint chassis are often replaced within a season after crashes"],
  facts={"min_weight_lb": F(1475, 1500, "lb", "high", ["src:ascs_2024", "src:ascs_2025_news"]),
         "engine_usd": F(25000, 40000, "USD", "low", ["src:ascs_2024"])},
  sources=["src:ascs_2024", "src:ascs_2025_news", "src:hoosier_gp_sprint"], confidence="low")

C["midget"] = dict(label="Midget", discipline="dirt_oval", templates=["regional_midget"], spread=1.0,
  chassis=[ch("used", "Used midget", 15000, 55, 2), ch("new", "New midget chassis", 30000, 78)],
  engines=[en("used_engine", "Used 4-cylinder midget engine", 20000, 65, 8000, 20),
           en("trd", "Toyota TRD / Stanton SR-11x", 52000, 86, 22000, 25)],
  shocks=[sh("std", "Standard shocks", 1500, 55), sh("top", "Top shock program", 4500, 78)],
  tires={"usd": 260, "typical_new": 1, "max_new": None, "life_races": 2, "spec": "Hoosier SP3 right rear", "rule": "Spec Hoosier SP3 RR; LR D-12 or harder"},
  chassis_life=3, entry_usd=150, fuel_usd=80, misc_usd=1600, repair_frac=0.15, min_weight_lb=1035,
  rules=["1,035 lb minimum with driver", "4-cylinder engines (Toyota/Stanton/Esslinger/Honda)"],
  facts={"min_weight_lb": F(1035, 1035, "lb", "high", ["src:usac_midget_2025", "src:powri_midget", "src:xtreme_midget"]),
         "engine_usd": F(45000, 60000, "USD", "low", ["src:midget_cost_snip"]),
         "season_usd": F(150000, 400000, "USD", "low", ["src:midget_cost_snip"])},
  sources=["src:usac_midget_2025", "src:powri_midget", "src:xtreme_midget", "src:midget_cost_snip"], confidence="low")

C["micro_sprint"] = dict(label="Micro sprint (600cc)", discipline="dirt_oval", templates=["micro_sprint"], spread=0.85,
  chassis=[ch("used", "Used micro", 5000, 55, 2), ch("new", "New micro sprint", 12000, 76)],
  engines=[en("600", "600cc motorcycle engine", 5000, 70, 1200, 25), en("600_top", "Top-built 600cc", 11000, 82, 2000, 20)],
  shocks=[sh("std", "Standard shocks", 800, 55), sh("top", "Top shocks", 2000, 75)],
  tires={"usd": 175, "typical_new": 1, "max_new": None, "life_races": 3, "spec": "Hoosier (spec stamps)", "rule": "Spec right-rear stamps"},
  chassis_life=3, entry_usd=80, fuel_usd=30, misc_usd=300, repair_frac=0.15, min_weight_lb=740,
  facts={"min_weight_lb": F(725, 750, "lb", "high", ["src:powri_micro"]), "season_usd": F(15000, 35000, "USD", "low", ["src:powri_micro"])},
  rules=["600cc 4-cylinder motorcycle engines", "725-750 lb with driver"], sources=["src:powri_micro"], confidence="low")

# ------------------------------------------------------------------ karting & club road
C["kart_junior"] = dict(label="Kart (junior/club)", discipline="karting", templates=["youth_karting"], spread=0.65,
  chassis=[ch("used", "Used kart chassis", 1500, 50, 2), ch("new", "New kart chassis", 4500, 75)],
  engines=[en("lo206", "Briggs LO206 (factory sealed)", 800, 62, 250, 30, sealed=True, years=[2010, 2100]),
           en("ka100", "IAME KA100 (100cc)", 3000, 72, 1000, 8, years=[2017, 2100]),
           en("kt100", "Yamaha KT100", 1500, 64, 500, 8, years=[1995, 2016])],
  shocks=[sh("none", "Kart (no shocks)", 0, 60)],
  tires={"usd": 65, "typical_new": 2, "max_new": None, "life_races": 2, "spec": "Spec kart tires (Evinco/MG/Vega)", "rule": "Spec tire per series; sets included in entry at national events"},
  chassis_life=2, entry_usd=120, fuel_usd=20, misc_usd=150, repair_frac=0.08,
  rules=["Spec engines with hour-based rebuilds (KA100 top end every 10-12 hours)", "Spec tires"],
  facts={"lo206_usd": F(759, 848, "USD", "medium", ["src:lo206_snippets"]), "ka100_rebuild_usd": F(575, 1555, "USD", "medium", ["src:iame_service_snippets"])},
  sources=["src:skusa_protour_2026_pricing", "src:iame_service_snippets", "src:lo206_snippets", "src:kt100_snippets", "src:wordracing_costs"], confidence="medium")

C["kart_senior"] = dict(label="Kart (national TaG)", discipline="karting", templates=["national_karting"], spread=0.8,
  chassis=[ch("used", "Used chassis", 2000, 55, 1), ch("new", "New chassis", 5500, 78)],
  engines=[en("x30", "IAME X30 125cc TaG", 4500, 76, 1000, 6, years=[2012, 2100]),
           en("rotax", "Rotax Senior MAX", 3600, 74, 900, 8, sealed=True), en("yamaha", "Yamaha KT100 (pre-TaG era)", 1500, 70, 500, 6, years=[1995, 2011])],
  shocks=[sh("none", "Kart (no shocks)", 0, 60)],
  tires={"usd": 70, "typical_new": 4, "max_new": None, "life_races": 1.5, "spec": "Evinco / Mojo spec", "rule": "2 race sets included in the event entry at national events"},
  chassis_life=1.5, entry_usd=900, fuel_usd=60, misc_usd=900, repair_frac=0.08,
  rules=["X30 configuration frozen since 2014", "Spec tires included in entry"],
  facts={"x30_usd": F(4000, 4900, "USD", "medium", ["src:iame_service_snippets"]), "tire_set_usd": F(262, 274, "USD per set", "high", ["src:skusa_protour_2026_pricing"])},
  sources=["src:skusa_protour_2026_pricing", "src:skusa_protour_2026_purse", "src:rotax_service_snippets", "src:iame_service_snippets"], confidence="medium")

C["club_spec_miata"] = dict(label="Club road racer (Spec Miata type)", discipline="road", templates=["club_regional", "club_national"], spread=0.6,
  chassis=[ch("budget", "Budget Spec Miata", 8000, 48, 10), ch("good", "Good Spec Miata", 22000, 65, 5), ch("top", "Pro-built Spec Miata", 55000, 82, 1)],
  engines=[en("stock", "Stock-spec engine", 3000, 60, 3000, 15), en("pro", "Pro-built spec engine", 6000, 75, 5500, 18)],
  shocks=[sh("spec", "Spec shocks", 1200, 60)],
  tires={"usd": 215, "typical_new": 2, "max_new": None, "life_races": 3, "spec": "Hoosier SM7.5 / Toyo RR", "rule": "Spec DOT tire; 10-20 heat cycles"},
  chassis_life=12, entry_usd=450, fuel_usd=150, misc_usd=300, repair_frac=0.1, min_weight_lb=2400,
  rules=["Production MX-5 with the Spec Miata kit", "Spec tire"],
  facts={"season_usd": F(6660, 30000, "USD", "medium", ["src:nomoney_sm_2023", "src:sm_cost_snippets"]),
         "tire_usd": F(200, 230, "USD per tire", "medium", ["src:sm_cost_snippets"])},
  sources=["src:nomoney_sm_2023", "src:sm_cost_snippets", "src:wiki_specmiata"], confidence="medium")

# Research records filed under other keys that describe the same cars.
EVIDENCE = {
    "late_model_stock": ["limited_late_model", "pro_late_model"],
    "limited_late_model": ["pro_late_model"],
    "super_late_model": ["pro_late_model"],
    "asphalt_modified": ["asphalt_modified_sk"],
    "street_stock": ["pure_stock", "truck_class"],
    "hobby_stock": ["dirt_stock_car"],
    "dirt_modified": ["sport_mod"],
    "dirt_late_model": ["crate_late_model"],
    "sprint_360": ["sprint_305", "sprint_410"],
    "club_spec_miata": ["spec_racer_ford", "formula_f"],
}
for k, extra in EVIDENCE.items():
    C[k]["evidence"] = [k] + extra

out = {"_comment": "Car classes: what racers buy and run under each class's rules. Money in 2025 USD; 'facts' carry the researched ranges with sources and confidence (data/rules/research.json holds the full evidence). Option 'quality' is a 0-100 design value: competitive speed of that part within the class after rules balancing.",
       "classes": C}
json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=1)
print(len(C), "classes")
