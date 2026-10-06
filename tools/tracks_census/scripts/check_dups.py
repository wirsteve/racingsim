import os as _os
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", ".."))
"""QA: list near/same-name pairs among new records and between new and existing records."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from census_util import haversine_km, norm_name
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ex = [x for f in __import__('glob').glob(_os.path.join(_REPO, 'data', 'tracks', '*.json'))
      for x in json.load(open(f))]
n = json.load(open(os.path.join(BASE, 'tracks_new.json')))
print('new-new:')
for i, a in enumerate(n):
    for b in n[i + 1:]:
        d = haversine_km((a['lat'], a['lon']), (b['lat'], b['lon']))
        if d < 1 or (norm_name(a['name']) == norm_name(b['name']) and d < 100):
            print(' ', round(d, 2), a['name'], '|', b['name'], a['surface'], b['surface'], a['track_type'], b['track_type'])
print('new-existing:')
for r in n:
    for e in ex:
        if e.get('lat') is None:
            continue
        d = haversine_km((r['lat'], r['lon']), (e['lat'], e['lon']))
        if d < 1 or (norm_name(r['name']) == norm_name(e['name']) and d < 100):
            print(' ', round(d, 2), r['name'], '|', e['name'], r['surface'], e['surface'], r['track_type'], e['track_type'])
