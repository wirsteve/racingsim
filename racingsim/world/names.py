"""Generated names for drivers, teams and grassroots sponsors.

Real national-series people come from the historical database (``racingsim.history``);
everyone else is generated. Generated driver names are checked against a blocklist of
well-known real drivers so a generated racer is never mistaken for a real person
(see LICENSING_IP_REVIEW.md).
"""

from __future__ import annotations

import random

FIRST = (
    "Aaron Adam Aiden Alex Andrew Austin Avery Blake Bobby Brad Brady Brandon Brent Brett Brian "
    "Brody Bryce Caleb Cameron Carson Carter Casey Chad Chase Chris Clay Cody Cole Colin Colton "
    "Connor Corey Dakota Dale Dalton Dan Danny Darren Dawson Derek Devin Dillon Dominic Drew Dustin "
    "Dylan Eli Emma Eric Ethan Evan Garrett Gavin Grant Grayson Hailey Hank Hayden Hunter Ian Isaac "
    "Jace Jack Jackson Jacob Jake James Jared Jason Jay Jeremy Jesse Joel Jordan Josh Justin Kaden "
    "Kaitlyn Kane Kara Keegan Kelly Kendall Kenny Kevin Kody Kyle Landon Lane Layne Leah Levi Logan "
    "Lucas Luke Madison Mark Mason Matt Max Megan Micah Mike Mitch Morgan Nate Nick Noah Nolan Owen "
    "Parker Payton Peyton Quinn Reece Reid Riley Rob Rocco Ross Ryan Sam Sawyer Scott Seth Shane "
    "Shawn Skylar Spencer Stephen Taylor Tanner Tate Terry Toby Todd Travis Trent Trey Tristan Troy "
    "Tucker Tyler Wade Wes Weston Will Wyatt Zach Zane Ana Carlos Diego Javier Luis Mateo Rafael "
    "Andre Marcus Darius Malik Jalen Kenji Hiro Arjun Liam Felix Oscar Lena Sofia"
).split()

LAST = (
    "Abbott Adkins Allison Ames Arnold Atwood Bailey Baker Barnes Barrett Bates Beck Bell Bennett "
    "Blevins Boggs Bowers Boyd Bradley Brock Brooks Bryant Burke Burns Byrd Cain Calhoun Carlson "
    "Carroll Carver Chandler Childers Clark Cline Cobb Cole Collins Combs Conley Cook Cooper Crane "
    "Crawford Crews Cross Curry Dalton Daniels Davenport Dawson Decker Dennison Dixon Dodd Doyle "
    "Duncan Dunn Easley Eaton Elliott Ellis Emerson Farley Faulkner Fields Fisher Fleming Flynn Ford "
    "Foster Fowler Fry Gaines Garner Garrett Gentry Gibbs Gill Glover Goff Graham Graves Gray Greer "
    "Griffin Grimes Hale Hall Hammond Hardin Harmon Harper Hart Hatcher Hawkins Hayes Henson Hicks "
    "Hines Hobbs Holt Hopper Horton Houston Howell Hubbard Huff Hughes Hull Hutchins Ingram Jarvis "
    "Jenkins Keller Kemp Kendrick Kerr Kidd Kirby Knapp Knox Lamb Lane Lawson Leach Lewis Lindsey "
    "Lowe Lyons Mack Maddox Malone Mann Marsh Mason Mathis Maxwell Mayer McBride McCoy McDaniel "
    "McKay Meadows Mercer Miles Moody Morrow Moss Munson Nash Neal Newton Nolan Norris Oakes Odom "
    "Olsen Osborne Owens Pace Parks Parrish Patton Payne Pierce Pike Poole Pratt Price Pruitt Quinn "
    "Ramsey Randall Reeves Rhodes Rich Riggs Rios Roach Rowe Rush Sanders Savage Sawyer Schultz "
    "Sexton Shaw Shelton Short Simmons Sims Slater Sloan Snyder Spears Stanton Steele Stokes Strong "
    "Summers Sutton Swain Tate Thornton Todd Townsend Tucker Turner Tyler Vance Vaughn Wade Walsh "
    "Walton Ward Waters Watts Webb Weeks Wheeler Whitaker Wiley Wilkins Willis Wolfe Woods Wyatt "
    "York Young Zimmerman Kowalski Nowak Lindqvist Moreau Okafor Tanaka Fernandes Gallo Rossi Kruger"
).split()

# Well-known real drivers: never generate these exact full names.
REAL_NAME_BLOCKLIST = {
    "Kyle Busch", "Kurt Busch", "Jeff Gordon", "Tony Stewart", "Kyle Larson", "Chase Elliott",
    "Bill Elliott", "Joey Logano", "Ryan Blaney", "Denny Hamlin", "William Byron", "Christopher Bell",
    "Ross Chastain", "Josef Newgarden", "Scott Dixon", "Alex Palou", "Pato O'Ward", "Colton Herta",
    "Matt Kenseth", "Mark Martin", "Carl Edwards", "Kevin Harvick", "Dale Earnhardt", "Ryan Newman",
    "Bobby Labonte", "Terry Labonte", "Kenny Wallace", "Rusty Wallace", "Kenny Schrader", "Ken Schrader",
    "Austin Dillon", "Ty Dillon", "Brad Keselowski", "Alex Bowman", "Tyler Reddick", "Chase Briscoe",
    "Daniel Suarez", "Bubba Wallace", "Michael McDowell", "Justin Allgaier", "Sam Hornish",
    "Will Power", "Graham Rahal", "Conor Daly", "Spencer Pigot", "Kyle Kaiser", "Scott McLaughlin",
    "Shane van Gisbergen", "Jimmie Johnson", "Danica Patrick", "Paul Menard", "Harrison Burton",
    "Jeff Burton", "Ward Burton", "Trevor Bayne", "Carson Hocevar", "Brad Sweet", "David Gravel",
    "Donny Schatz", "Jonathan Davenport", "Brandon Sheppard", "Kasey Kahne", "Dave Blaney",
    "Ryan Preece", "Tanner Gray", "Ryan Sieg", "Jordan Taylor", "Ricky Taylor", "Colin Braun",
    "Austin Cindric", "Ty Majeski", "Corey Heim", "Sammy Smith", "Connor Zilisch", "Chase Bell",
    "Kyle Petty", "Richard Petty", "Mark Smith", "Logan Seavey", "Justin Grant", "Tanner Thorson",
    "Cole Custer", "John Hunter Nemechek", "Erik Jones", "Noah Gragson", "Josh Berry", "Zane Smith",
}

SPONSOR_PATTERNS_LOCAL = (
    "{last} Plumbing", "{last} Auto Body", "{last} Excavating", "{place} Tire & Service",
    "{last} Family Farms", "{place} Lumber", "{last} Electric", "{place} Pizza Co.",
    "{last} Heating & Air", "{place} Feed & Seed", "{last} Concrete", "{place} Credit Union",
    "{last} Trucking", "{place} Auto Parts", "{last} Roofing", "{place} Dental",
)
SPONSOR_PATTERNS_REGIONAL = (
    "{place} Building Supply", "{last} Logistics", "{place} Power Equipment", "{last} Motors",
    "{place} Bank & Trust", "{last} Industrial", "{place} Energy Co-op", "{last} Homes",
)
# Real national brands with long motorsport histories (personal-use game).
SPONSOR_NATIONAL = (
    "Lowe's", "The Home Depot", "DuPont", "Tide", "Miller Lite", "Budweiser", "M&M's", "Target",
    "GEICO", "Snap-on", "Valvoline", "Mobil 1", "Pennzoil", "Menards", "Coca-Cola", "Kellogg's",
    "Interstate Batteries", "UPS", "FedEx", "Caterpillar", "NAPA Auto Parts", "AutoZone",
    "Advance Auto Parts", "Bass Pro Shops", "Sunoco", "Coors Light", "Quaker State", "STP",
    "Havoline", "Cheerios", "Monster Energy", "Mountain Dew", "Hooters", "Goodwrench",
    "Kodak", "Craftsman", "Dewalt", "Busch Light", "Shell", "Gatorade",
)
PLACES = (
    "Tri-County", "Valley", "Lakeside", "Ridge", "Riverbend", "Prairie", "Pine Hill", "Crossroads",
    "Northside", "Mill Creek", "Cedar", "Iron Range", "Bluegrass", "Piedmont", "Coastal", "Tidewater",
    "Heartland", "Sandhills", "Highland", "Twin Rivers", "Big Sky", "Red Clay", "Lowcountry",
)
TEAM_PATTERNS = (
    "{last} Racing", "{last} Motorsports", "{last}-{last2} Racing", "{place} Motorsports",
    "Team {last}", "{last} Performance", "{last} Brothers Racing", "{last} Competition",
)
MANUFACTURERS = (
    ("Aurora Motors", 0.8), ("Bridgeline Automotive", 0.6), ("Corsa Vehicles", 0.7),
    ("Dynamo Motor Co.", 0.5),
)


def driver_name(rng: random.Random) -> tuple[str, str]:
    for _ in range(20):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        if f"{first} {last}" not in REAL_NAME_BLOCKLIST:
            return first, last
    return "Sam", "Okafor"


def sponsor_name(rng: random.Random, scope: str) -> str:
    if scope == "national":
        return rng.choice(SPONSOR_NATIONAL)
    patterns = SPONSOR_PATTERNS_LOCAL if scope == "local" else SPONSOR_PATTERNS_REGIONAL
    return rng.choice(patterns).format(last=rng.choice(LAST), place=rng.choice(PLACES))


def team_name(rng: random.Random, owner_last: str | None = None) -> str:
    last = owner_last or rng.choice(LAST)
    return rng.choice(TEAM_PATTERNS).format(last=last, last2=rng.choice(LAST), place=rng.choice(PLACES))
