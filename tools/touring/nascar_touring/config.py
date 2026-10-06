"""Series configuration for the NASCAR-regional touring-series builder (nascar_touring)."""

YEARS = (1995, 2026)
CURRENT_YEAR = 2026

SERIES = {
    "nascar_southeast": dict(name="NASCAR Southeast Series (Slim Jim All Pro Series / AutoZone Elite Division, Southeast Series)",
                             discipline="asphalt_late_model", level="regional",
                             main="NASCAR AutoZone Elite Division, Southeast Series"),
    "nascar_southwest": dict(name="NASCAR Southwest Series (Featherlite Southwest Tour / AutoZone Elite Division, Southwest Series)",
                             discipline="asphalt_late_model", level="regional",
                             main="NASCAR AutoZone Elite Division, Southwest Series"),
    "nascar_northwest": dict(name="NASCAR Northwest Series (Northwest Tour / AutoZone Elite Division, Northwest Series)",
                             discipline="asphalt_late_model", level="regional",
                             main="NASCAR AutoZone Elite Division, Northwest Series"),
    "nascar_midwest": dict(name="NASCAR Midwest Series (RE/MAX Challenge Series / AutoZone Elite Division, Midwest Series)",
                           discipline="asphalt_late_model", level="regional", main="ARTGO"),
    "artgo": dict(name="ARTGO Challenge Series", discipline="asphalt_late_model", level="regional", main="ARTGO"),
    "nascar_autozone_elite": dict(name="NASCAR AutoZone Elite Division (umbrella of four regional late model series)",
                                  discipline="asphalt_late_model", level="regional", main="NASCAR AutoZone Elite Division"),
    "pro_cup": dict(name="USAR Hooters Pro Cup Series", discipline="asphalt_late_model", level="regional", main="CARS Tour"),
    "nascar_dash": dict(name="NASCAR Goody's Dash Series (ISCARS Dash Touring from 2004)", discipline="stock_car",
                        level="regional", main="ISCARS Dash Touring Series"),
    "nascar_sportsman": dict(name="NASCAR Sportsman Division", discipline="stock_car", level="regional",
                             main="NASCAR Sportsman Division (1989–1995)"),
}
EVENTS = {}

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}
CA_PROVINCES = {
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Nova Scotia": "NS", "Ontario": "ON", "Prince Edward Island": "PE",
    "Quebec": "QC", "Québec": "QC", "Saskatchewan": "SK", "Northwest Territories": "NT", "Yukon": "YT", "Nunavut": "NU",
}
MX_STATES = {"Nuevo León": "NL", "Mexico City": "CMX", "Baja California": "BC", "Querétaro": "QT"}
REGION_NAMES = {**US_STATES, **CA_PROVINCES}
ABBR_TO_COUNTRY = {**{v: "USA" for v in US_STATES.values()}, **{v: "CAN" for v in CA_PROVINCES.values()}}
