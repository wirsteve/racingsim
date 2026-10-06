"""Write tools/touring/existing_tracks.json (id, name, city, region, aliases) for the scrapers' venue matching."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..")))
from racingsim.tracks.database import TrackDatabase  # noqa: E402

rows = [{"id": t.id, "name": t.facts.name, "city": t.facts.city, "region": t.facts.region, "aliases": t.facts.aliases,
         "lat": t.facts.lat, "lon": t.facts.lon} for t in TrackDatabase.load()]
json.dump(rows, open(os.path.join(HERE, "existing_tracks.json"), "w"), indent=0)
print(len(rows), "tracks")
