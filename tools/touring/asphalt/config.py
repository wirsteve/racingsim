"""Series configuration for the asphalt touring-series scraper."""

YEARS = (1995, 2026)
CURRENT_YEAR = 2026

# champ: list of champion sources: (kind, page, heading_substring, column_substring_or_None, year_from, year_to)
#   kind "table": a wikitable under heading containing heading_substring; year in first col, champion in column
#   kind "list": bullet list "* YEAR name" under heading containing heading_substring
# season_re: regex matching Wikipedia season article titles (group 1 = year)
# main_schedules: [(page, heading_substring_with_{y}, year)] season schedule tables embedded in main articles
# division: for multi-division season articles: winner column filter + standings heading filter

SERIES = {
    "arca": dict(
        name="ARCA Menards Series", discipline="stock_car", level="national",
        main="ARCA Menards Series",
        season_re=r"^(\d{4}) ARCA (?:Bondo/Mar-Hyde|Re/Max|Racing|Menards) Series$",
        champ=[("table", "ARCA Menards Series", "Seasons", "champion", 1995, 2026)],
    ),
    "arca_east": dict(
        name="ARCA Menards Series East", discipline="stock_car", level="super_regional",
        main="ARCA Menards Series East",
        season_re=r"^(\d{4}) (?:NASCAR Busch (?:Grand National )?North Series|NASCAR Busch East Series|NASCAR Camping World East Series|NASCAR K&N Pro Series East|ARCA Menards Series East)$",
        champ=[("table", "ARCA Menards Series East", "Seasons", "champion", 1995, 2026)],
    ),
    "arca_west": dict(
        name="ARCA Menards Series West", discipline="stock_car", level="super_regional",
        main="ARCA Menards Series West",
        season_re=r"^(\d{4}) (?:NASCAR (?:Winston West|West|AutoZone West|Camping World West) Series|NASCAR K&N Pro Series West|ARCA Menards Series West)$",
        champ=[("table", "ARCA Menards Series West", "Seasons", "champion", 1995, 2026)],
    ),
    "whelen_modified": dict(
        name="NASCAR Whelen Modified Tour", discipline="modified", level="super_regional",
        main="NASCAR Whelen Modified Tour",
        season_re=r"^(\d{4}) NASCAR (?:Whelen|Featherlite) Modified (?:Tour|Series)$",
        champ=[("table", "NASCAR Whelen Modified Tour", "Champions", "driver", 1995, 2026)],
    ),
    "whelen_southern_modified": dict(
        name="NASCAR Whelen Southern Modified Tour", discipline="modified", level="regional",
        main="SMART Modified Tour",
        season_re=r"^(\d{4}) NASCAR Whelen Southern Modified Tour$",
        champ=[("table", "SMART Modified Tour", "Champions", "driver", 2005, 2016)],
        main_seasons=("SMART Modified Tour", "{y} season", 2005, 2016),
    ),
    "smart_modified": dict(
        name="SMART Modified Tour", discipline="modified", level="regional",
        main="SMART Modified Tour",
        season_re=r"^(\d{4}) (?:SMART Modified Tour|Southern Modified Auto Racing Teams season)$",
        champ=[("table", "SMART Modified Tour", "Champions", "driver", 1995, 2004),
               ("table", "SMART Modified Tour", "Champions", "driver", 2021, 2026)],
        main_seasons=("SMART Modified Tour", "{y} season", 1995, 2004),
    ),
    "asa": dict(
        name="ASA National Tour", discipline="asphalt_late_model", level="national",
        main="American Speed Association",
        champ=[("list", "American Speed Association", "List of ASA National Champions", None, 1995, 2004)],
    ),
    "asa_late_model": dict(
        name="ASA Late Model Series (Challenge Division)", discipline="asphalt_late_model", level="regional",
        main="ASA Late Model Series",
        champ=[("list", "ASA Late Model Series", "Challenge Division", None, 2003, 2010)],
    ),
    "asa_late_model_north": dict(
        name="ASA Late Model Series (Northern Division)", discipline="asphalt_late_model", level="regional",
        main="ASA Late Model Series",
        champ=[("list", "ASA Late Model Series", "Northern Division", None, 2003, 2010)],
    ),
    "asa_late_model_south": dict(
        name="ASA Late Model Series (Southern Division)", discipline="asphalt_late_model", level="regional",
        main="ASA Late Model Series",
        champ=[("list", "ASA Late Model Series", "Southern Division", None, 2003, 2010)],
    ),
    "asa_stars": dict(
        name="ASA STARS National Tour", discipline="asphalt_late_model", level="national",
        main="American Speed Association",
        season_re=r"^(\d{4}) ASA STARS National Tour$",
        champ=[("list", "American Speed Association", "List of ASA National Champions", None, 2023, 2026)],
        main_schedules=[("American Speed Association", "{y} ASA STARS National Tour Schedule", 2025)],
    ),
    "southern_super_series": dict(
        name="ASA Southern Super Series", discipline="asphalt_late_model", level="regional",
        main="American Speed Association",
        champ=[],
        main_schedules=[("American Speed Association", "{y} ASA Southern Super Series Schedule", 2025)],
    ),
    "artgo": dict(
        name="ARTGO Challenge Series", discipline="asphalt_late_model", level="regional",
        main="ARTGO",
        champ=[("list", "ARTGO", "Past ARTGO Champions", None, 1995, 1997)],
    ),
    "nascar_midwest": dict(
        name="NASCAR Midwest Series (RE/MAX Challenge Series)", discipline="asphalt_late_model", level="regional",
        main="ARTGO",
        champ=[("list", "ARTGO", "Past NASCAR/Midwest Champions", None, 1998, 2006)],
    ),
    "arca_midwest": dict(
        name="ARCA Midwest Tour", discipline="asphalt_late_model", level="regional",
        main="ASA Midwest Tour",
        season_re=r"^(\d{4}) (?:ASA|ARCA) Midwest Tour season$",
        champ=[("table", "ASA Midwest Tour", "Champions and Rookies", "champion", 2007, 2026),
               ("list", "ARTGO", "Past ASA/ARCA Midwest Tour Champions", None, 2007, 2026)],
        main_schedules=[("ASA Midwest Tour", "{y} ASA Midwest Tour Schedule", 2024),
                        ("ASA Midwest Tour", "{y} ASA Midwest Tour Schedule", 2025),
                        ("ASA Midwest Tour", "{y} ASA Midwest Tour Schedule", 2026)],
    ),
    "cars_lms": dict(
        name="CARS Late Model Stock Tour", discipline="asphalt_late_model", level="regional",
        main="CARS Tour",
        season_re=r"^(\d{4}) CARS Tour$",
        division=dict(winner=r"\bLMS|late model stock", standings=r"late model stock|\bLMS"),
        champ=[("table", "CARS Tour", "Champions", "late model stock", 2015, 2026)],
    ),
    "cars_slm": dict(
        name="CARS Super Late Model / Pro Late Model Tour", discipline="asphalt_late_model", level="regional",
        main="CARS Tour",
        season_re=r"^(\d{4}) CARS Tour$",
        division=dict(winner=r"\bSLM|\bPLM|super late|pro late", standings=r"super late|pro late|\bSLM|\bPLM"),
        champ=[("table", "CARS Tour", "Champions", "super late model|pro late model", 2015, 2026)],
    ),
    "pro_cup": dict(
        name="USAR Hooters Pro Cup Series", discipline="asphalt_late_model", level="super_regional",
        main="CARS Tour",
        champ=[("list", "CARS Tour", "ProCup Champions (2001", None, 2001, 2014),
               ("list", "CARS Tour", "ProCup Series Champions (1997", None, 1997, 2000)],
    ),
    "pass_north": dict(
        name="PASS North Super Late Models", discipline="asphalt_late_model", level="regional",
        main="Pro All Stars Series",
        champ=[("table", "Pro All Stars Series", "Champions", "north", 2001, 2026)],
    ),
    "pass_south": dict(
        name="PASS South Super Late Models", discipline="asphalt_late_model", level="regional",
        main="Pro All Stars Series",
        champ=[("table", "Pro All Stars Series", "Champions", "south", 2001, 2026)],
    ),
    "pass_national": dict(
        name="PASS National Super Late Model Series", discipline="asphalt_late_model", level="super_regional",
        main="Pro All Stars Series",
        champ=[("table", "Pro All Stars Series", "Champions", "national", 2001, 2026)],
    ),
    "cra_super_series": dict(
        name="ASA/CRA Super Series", discipline="asphalt_late_model", level="regional",
        main="CRA Super Series",
        champ=[("table", "CRA Super Series", "Champions", "super series", 1997, 2026)],
        main_schedules=[("Champion Racing Association", "{y} ASA/CRA Super Series Schedule", 2025),
                        ("CRA Super Series", "{y} ASA/CRA Super Series Schedule", 2026)],
    ),
    "cra_all_stars": dict(
        name="JEGS/CRA All-Stars Tour", discipline="asphalt_late_model", level="regional",
        main="Champion Racing Association",
        champ=[("table", "Champion Racing Association", "CRA Champions", "all-stars", 1997, 2026)],
        main_schedules=[("Champion Racing Association", "{y} JEGS/CRA All-Stars Tour Schedule", 2025)],
    ),
    "pinty": dict(
        name="NASCAR Canada Series", discipline="stock_car", level="national",
        main="NASCAR Canada Series",
        season_re=r"^(\d{4}) NASCAR (?:Canadian Tire Series|Pinty's Series|Canada Series|Pinty's FanCave Challenge)$",
        champ=[("table", "NASCAR Canada Series", "List of series champions", "champion", 2007, 2026)],
    ),
    "cascar": dict(
        name="CASCAR Super Series", discipline="stock_car", level="national",
        main="CASCAR Super Series",
        champ=[("table", "CASCAR Super Series", "Past champions", "champion", 1995, 2006)],
    ),
    "apc_united": dict(
        name="APC United Late Model Series", discipline="asphalt_late_model", level="regional",
        main="APC United Late Model Series",
        champ=[("table", "APC United Late Model Series", "Champions", "champion", 1995, 2026)],
    ),
    "oscaar_modified": dict(
        name="OSCAAR Modified Series", discipline="modified", level="regional",
        main="OSCAAR",
        champ=[("table", "OSCAAR", "OSCAAR Modified Series", "champion", 1995, 2026)],
    ),
    "oscaar_slm": dict(
        name="OSCAAR Outlaw Super Late Model Series", discipline="asphalt_late_model", level="regional",
        main="OSCAAR",
        champ=[("table", "OSCAAR", "OSCAAR Outlaw Super Late Model Series", "champion", 1995, 2026)],
    ),
}

# Crown-jewel events: single race per year. venue fixed unless loc_col given.
# src: (kind, page, heading_substring, winner_col, date_col_or_None, loc_col_or_None)
EVENTS = {
    "snowball_derby": dict(name="Snowball Derby", discipline="asphalt_late_model", page="Snowball Derby",
                           src=("table", "Snowball Derby", "Past Snowball Derby winners", "driver", "date", None),
                           track="Five Flags Speedway"),
    "winchester_400": dict(name="Winchester 400", discipline="asphalt_late_model", page="Winchester 400",
                           src=("table", "Winchester 400", "History", "winner", "date", None),
                           track="Winchester Speedway"),
    "oxford_250": dict(name="Oxford 250", discipline="asphalt_late_model", page="Oxford Plains Speedway",
                       src=("table", "Oxford Plains Speedway", "Annual Oxford 250 Champions", "name", None, None),
                       track="Oxford Plains Speedway"),
    "slinger_nationals": dict(name="Slinger Nationals", discipline="asphalt_late_model", page="Slinger Speedway",
                              src=("list", "Slinger Speedway", "List of Slinger Nationals winners", None, None, None),
                              track="Slinger Speedway"),
    "all_american_400": dict(name="All American 400", discipline="asphalt_late_model", page="Fairgrounds Speedway",
                             src=("list", "Fairgrounds Speedway", "All American 400", None, None, None),
                             track="Fairgrounds Speedway"),
    "florida_governors_cup": dict(name="Florida Governor's Cup", discipline="asphalt_late_model", page="New Smyrna Speedway",
                                  src=("table", "New Smyrna Speedway", "Florida Governor's Cup", "winner", None, "location"),
                                  track=None),
    "valleystar_300": dict(name="ValleyStar Credit Union 300 (Martinsville late model)", discipline="asphalt_late_model",
                           page="ValleyStar Credit Union 300",
                           src=("table", "ValleyStar Credit Union 300", "Winners", "driver", None, None),
                           track="Martinsville Speedway"),
    "la_crosse_oktoberfest": dict(name="Oktoberfest (La Crosse) main event", discipline="asphalt_late_model",
                                  page="La Crosse Fairgrounds Speedway",
                                  src=("list", "La Crosse Fairgrounds Speedway", "Main event", None, None, None),
                                  track="La Crosse Fairgrounds Speedway"),
    "myrtle_beach_400": dict(name="Myrtle Beach 400 (Charlie Powell 400)", discipline="asphalt_late_model",
                             page="Myrtle Beach Speedway",
                             src=("table", "Myrtle Beach Speedway", "Charlie Powell 400 Winners", "driver", None, None),
                             track="Myrtle Beach Speedway"),
    "little_500": dict(name="Little 500 (pavement sprint cars)", discipline="sprint_car", page="Anderson Speedway",
                       src=("list", "Anderson Speedway", "Winners", None, None, None),
                       track="Anderson Speedway"),
}

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
