"""Normalisation helpers shared by the census build."""
import math
import re
import unicodedata

US = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
      "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
      "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
      "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
      "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
      "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
      "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
      "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
      "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
      "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC", "Puerto Rico": "PR"}
CA = {"Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB",
      "Newfoundland and Labrador": "NL", "Newfoundland": "NL", "Nova Scotia": "NS", "Ontario": "ON",
      "Prince Edward Island": "PE", "Quebec": "QC", "Québec": "QC", "Saskatchewan": "SK",
      "Northwest Territories": "NT", "Nunavut": "NU", "Yukon": "YT"}
MX = {"Aguascalientes": "AGU", "Baja California": "BCN", "Baja California Sur": "BCS", "Campeche": "CAM",
      "Chiapas": "CHP", "Chihuahua": "CHH", "Coahuila": "COA", "Colima": "COL", "Mexico City": "CMX",
      "Distrito Federal": "CMX", "Ciudad de México": "CMX", "Durango": "DUR", "Guanajuato": "GUA",
      "Guerrero": "GRO", "Hidalgo": "HID", "Jalisco": "JAL", "State of Mexico": "MEX", "México": "MEX",
      "Estado de México": "MEX", "Michoacán": "MIC", "Michoacan": "MIC", "Morelos": "MOR", "Nayarit": "NAY",
      "Nuevo León": "NLE", "Nuevo Leon": "NLE", "Oaxaca": "OAX", "Puebla": "PUE", "Querétaro": "QUE",
      "Queretaro": "QUE", "Quintana Roo": "ROO", "San Luis Potosí": "SLP", "San Luis Potosi": "SLP",
      "Sinaloa": "SIN", "Sonora": "SON", "Tabasco": "TAB", "Tamaulipas": "TAM", "Tlaxcala": "TLA",
      "Veracruz": "VER", "Yucatán": "YUC", "Yucatan": "YUC", "Zacatecas": "ZAC"}
ABBR_COUNTRY = {**{v: "USA" for v in US.values()}, **{v: "CAN" for v in CA.values()}, **{v: "MEX" for v in MX.values()}}
ALL_NAMES = {**{k: (v, "USA") for k, v in US.items()}, **{k: (v, "CAN") for k, v in CA.items()},
             **{k: (v, "MEX") for k, v in MX.items()}}
ALL_NAMES.update({"Washington (state)": ("WA", "USA"), "Georgia (U.S. state)": ("GA", "USA"),
                  "New York (state)": ("NY", "USA"), "Chihuahua (state)": ("CHH", "MEX")})


def region_from_text(text):
    """Find a state/province in free text like 'Hampton, Virginia' or 'Bemidji, MN'. Returns (abbr, country)."""
    if not text:
        return None, None
    t = text.strip()
    # longest names first
    for name in sorted(ALL_NAMES, key=len, reverse=True):
        if re.search(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", t):
            if name == "Washington" and re.search(r"Washington,? D\.?C", t):
                continue
            if name in ("México",) and "Ciudad de México" in t:
                continue
            return ALL_NAMES[name]
    m = re.search(r",\s*([A-Z]{2})\b", t)
    if m and m.group(1) in ABBR_COUNTRY:
        return m.group(1), ABBR_COUNTRY[m.group(1)]
    return None, None


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\bthe\b", " ", s)
    s = re.sub(r"\bintl\b", "international", s)
    s = re.sub(r"\bmtr\b", "motor", s)
    s = re.sub(r"\bspdwy\b", "speedway", s)
    s = re.sub(r"\bmotorsports?\b", "motorsport", s)
    return re.sub(r"\s+", " ", s).strip()


GENERIC = {"speedway", "raceway", "motor", "motorsport", "park", "international", "race", "track", "racing",
           "county", "fairgrounds", "fair", "grounds", "complex", "circuit", "the", "of", "and", "at", "super",
           "autodrome", "dirt", "oval", "motorplex", "center", "centre", "stadium", "bowl", "arena", "club",
           "association", "inc", "llc", "s", "mile", "short", "paved"}


def core_tokens(s):
    return {t for t in norm_name(s).split() if t not in GENERIC and len(t) > 1}


def name_sim(a, b):
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ca, cb = core_tokens(a), core_tokens(b)
    if not ca or not cb:
        # all-generic names: compare full tokens
        ta, tb = set(na.split()), set(nb.split())
        return len(ta & tb) / max(1, len(ta | tb)) * 0.8
    inter = len(ca & cb)
    return inter / max(1, min(len(ca), len(cb))) * (0.7 + 0.3 * inter / max(1, len(ca | cb)))


def haversine_km(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    p = math.pi / 180
    h = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


FRAC = {"1/8": 0.125, "1/6": 1 / 6, "1/5": 0.2, "1/4": 0.25, "1/3": 1 / 3, "3/8": 0.375, "2/5": 0.4,
        "4/10": 0.4, "7/16": 0.4375, "1/2": 0.5, "5/8": 0.625, "3/4": 0.75, "7/8": 0.875, "3/10": 0.3,
        "1/10": 0.1, "1/20": 0.05, "1/16": 0.0625, "5/16": 0.3125, "3/5": 0.6, "4/5": 0.8, "9/16": 0.5625}


def parse_size_mi(s):
    """'3/8 Mile', '.375 mile', '1/4 mile clay', '0.4 mi', '1 Mile', '1.5 km' -> miles."""
    if not s:
        return None
    t = s.lower().replace("–", "-")
    m = re.search(r"(\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*-?\s*(miles?|mi\b|km|kilomet|meters?|metres?|m\b|ft|feet|'|th)", t)
    if not m:
        return None
    v = m.group(1)
    unit = m.group(2)
    if " " in v:
        whole, fr = v.split()
        val = int(whole) + _fr(fr)
    elif "/" in v:
        val = _fr(v)
    else:
        val = float(v)
    if val is None:
        return None
    if unit.startswith("mi") or unit == "th":
        if unit == "th":  # "1/4th mile"
            pass
        return round(val, 4)
    if unit.startswith("k"):
        return round(val * 0.621371, 4)
    if unit in ("ft", "feet", "'"):
        return round(val / 5280, 4)
    if unit.startswith("m"):
        return round(val / 1609.344, 4)
    return None


def _fr(v):
    if v in FRAC:
        return FRAC[v]
    a, b = v.split("/")
    try:
        return int(a) / int(b) if int(b) else None
    except ValueError:
        return None


def surface_from_text(s):
    if not s:
        return None
    t = s.lower()
    if "concrete" in t and ("asphalt" in t or "paved" in t):
        return "asphalt_concrete"
    if "clay" in t:
        return "clay"
    if "dirt" in t or "gumbo" in t or "red clay" in t or "shale" in t:
        return "dirt"
    if "concrete" in t:
        return "concrete"
    if "asphalt" in t or "paved" in t or "pavement" in t or "blacktop" in t or "tarmac" in t:
        return "asphalt"
    return None


def banking_category(deg=None, text=None):
    if deg is not None:
        if deg < 8:
            return "flat"
        if deg <= 16:
            return "moderate"
        return "high"
    if text:
        t = text.lower()
        if "high" in t:
            return "high"
        if "semi" in t or "moderate" in t or "medium" in t or "slight" in t or "progressive" in t or "variable" in t:
            return "moderate" if "slight" not in t else "flat"
        if "flat" in t or "no bank" in t:
            return "flat"
        if t.strip() == "banked":
            return None
    return None


DISC_PATTERNS = [
    ("quarter_midget", r"quarter.?midget|\bqma\b|\bqmc\b|\.25\b"),
    ("bandolero", r"bandolero"),
    ("legends", r"legend"),
    ("karting", r"\bkart|go.?kart|\bcage kart|champ kart|\bwka\b"),
    ("dirt_late_model", r"(dirt|super|crate|limited|pro|ump|uslmra|imca|steel block|sportsman|wissota|hobby|open wheel)?\s*late models?"),
    ("modified", r"modified|\bmods?\b|sportmod|sport mod|b.?mod|midwest mod|mod.?lite|mod four|tour.type|\bsk\b|dwarf car|\bsportsman\b|stock mod|usmts"),
    ("sprint_car", r"sprint|410|360|305|non.?wing|winged|micro|outlaw kart|mini.?sprint|asc[s]?\b|wingless"),
    ("midget", r"(?<!quarter )(?<!quarter-)\bmidget"),
    ("street_stock", r"street stock|hobby stock|pure stock|mini stock|front.?wheel|fwd|4.?cyl|four.?cyl|compact|hornet|factory stock|stock car|super stock|pro stock|thunder|bomber|enduro|u.?car|road warrior|v.?8|v6|cruiser|buzzbomb|roadrunner|charger|economy|limited stock|hobby|pony stock|truck|crown vic|figure.?8|figure eight|spectator|ministock|sport compact|stinger|renegade|mod 4|4 banger|street car"),
]


def disciplines_from_classes(classes, surface=None, track_type=None):
    out = set()
    blob = " | ".join(classes or []).lower()
    for disc, pat in DISC_PATTERNS:
        if re.search(pat, blob):
            out.add(disc)
    if "dirt_late_model" in out:
        if surface in ("asphalt", "concrete", "asphalt_concrete"):
            out.discard("dirt_late_model")
            out.add("late_model")
        elif surface is None:
            out.discard("dirt_late_model")
            out.add("late_model")
    return sorted(out)
