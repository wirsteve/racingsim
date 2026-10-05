"""Calibration constants shared across systems.

Every number here is a *design* value derived from MOTORSPORTS_RESEARCH.md
(section "Simulation assumptions"). They are intentionally centralised so the
model can be re-tuned as research improves.
"""

# Mean hidden ability of a regular competitor at each tier (0-100 scale).
# The gaps shrink at the top: the difference between an O'Reilly and a Cup regular
# is smaller than between a street stock and a super late model regular, but the
# number of seats shrinks far faster than the talent pool.
TIER_STRENGTH = (30.0, 37.0, 44.0, 52.0, 58.0, 64.0, 69.0, 74.0)
TIER_SPREAD = (9.0, 9.0, 8.0, 7.0, 6.0, 5.5, 5.0, 4.5)

# Exposure needed before a team at a tier tends to notice a driver (0-100).
NOTICE_THRESHOLD = (0.0, 5.0, 8.0, 14.0, 22.0, 30.0, 38.0, 45.0)

# Family racing budget: heavy-tailed. Median ~ $8k/season; ~5% of racing households
# can fund $80k+; a handful can fund national-level programmes outright
# (Menard/Stroll archetypes).
FAMILY_BUDGET_MEDIAN = 8_000.0
FAMILY_BUDGET_SIGMA = 1.45

# Annual attrition hazards (research F 5.2: 12-20% at T1-T2, 5-8% at T5-T6).
QUIT_HAZARD_BY_TIER = (0.15, 0.16, 0.13, 0.10, 0.08, 0.07, 0.06, 0.05)

# Sponsor-collapse chance per sponsored season (research C 5.4: 3-5%; A 14.7: 15-25%
# at national pro tiers because those deals are larger and more volatile).
SPONSOR_COLLAPSE_BASE = 0.04
SPONSOR_COLLAPSE_NATIONAL = 0.15

# Substitute drive -> full-time seat (research C 5.3): 15-25% base, +25% with a
# strong result. We implement it through a temporary "breakout" flag and a
# reputation boost so the outcome still runs through the market.
SUBSTITUTE_BREAKOUT_FINISH_PCT = 0.25

# Development-program signing age ~ N(16, 1.5), range 14-19 (research C 5.2).
PROGRAM_AGE_MEAN = 16.0
PROGRAM_AGE_SD = 1.5
PROGRAM_AGE_RANGE = (14, 19)

# Probability a retired top-tier pro keeps racing regionally/locally (research A 14.11, C 5.7).
GRASSROOTS_RETURN_PROB = 0.35

# The simulated grassroots base is a compressed sample of reality (~80-160k real US
# racers vs ~11k simulated at population_scale=1), while national seats are modelled
# 1:1. Rare-but-important tails (career-investment families, generational talent)
# must therefore be denser per simulated racer, or too few funded young prospects
# exist to fill real-sized national ladders. REPRESENTATION_RATIO is real racers
# per simulated grassroots racer at scale 1.0.
REPRESENTATION_RATIO = 8.0
# Real-world share of young racers whose families fund a national-level programme
# ($150k+/season), and share of generational talents (both approx., design values).
INVESTMENT_FAMILY_SHARE = 0.003
PRODIGY_SHARE = 0.0015
