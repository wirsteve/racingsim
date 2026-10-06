"""Fold every source folder in the repository into data/ (touring history, venues, track census).

    python tools/knowledge/rebuild.py

1. import_touring.py on tools/touring/{asphalt,dirt,nascar_touring}  -> data/history/touring/, staging
2. geocode_venues.py on each staged venue list (Wikidata, then OpenStreetMap coordinates)
3. merge.py with all staging folders + the track census          -> data/knowledge/, data/tracks/census_venues.json
Then run `python -m racingsim data build && python -m racingsim data validate`.
"""
import os
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
T = os.path.join(ROOT, "tools")
DATASETS = os.path.join(T, "ingest", "datasets")


def run(*args):
    print("$", " ".join(os.path.relpath(a, ROOT) if os.path.isabs(a) else a for a in args), flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


touring = [os.path.join(T, "touring", k) for k in ("asphalt", "dirt", "nascar_touring")
           if os.path.exists(os.path.join(T, "touring", k, "series.json"))]
for folder in touring:
    run(os.path.join(T, "knowledge", "import_touring.py"), folder)
    staged = os.path.join(T, "knowledge", "staging", os.path.basename(folder), "tracks_new.json")
    wd, osm = os.path.join(DATASETS, "tracks_wikidata.json"), os.path.join(DATASETS, "tracks_osm.json")
    if os.path.exists(staged) and os.path.exists(wd):
        run(os.path.join(T, "knowledge", "geocode_venues.py"), staged, wd, *([osm] if os.path.exists(osm) else []))
staging = [os.path.join(T, "knowledge", "staging", os.path.basename(f)) for f in touring]
census = os.path.join(T, "tracks_census")
if os.path.exists(os.path.join(census, "tracks_new.json")):
    staging.append(census)
if os.path.exists(os.path.join(DATASETS, "datasets.json")):
    staging.append(DATASETS)
run(os.path.join(T, "knowledge", "merge.py"), *staging)
