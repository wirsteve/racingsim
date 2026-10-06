"""MyRacePass track index (https://www.myracepass.com/tracks/?l=<letter>).

MyRacePass is the results/registration platform that hosts the track directories of
WISSOTA, USRA, ASCS, POWRi, USMTS and many weekly tracks; profiles are maintained by
the tracks themselves ("profile claimed by" the promoter). robots.txt (checked
2026-10-06) does not disallow /tracks/. >=2.5 s between requests.
Output: raw/dir/mrp_index.json [{id, name, place, region_group}]
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from wp_common import RAW, UA

D = os.path.join(RAW, "dir", "mrp")
os.makedirs(D, exist_ok=True)


def get(url):
    time.sleep(2.5)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def main():
    out = {}
    for l in list("abcdefghijklmnopqrstuvwxyz0123456789"):
        p = os.path.join(D, f"index_{l}.html")
        if not os.path.exists(p):
            open(p, "w").write(get(f"https://www.myracepass.com/tracks/?l={l}"))
        s = open(p).read()
        # split by region sections
        for sec in re.split(r"<div class='sectionHead' id='region_\d+'>", s)[1:]:
            reg = re.search(r"<h2>(.*?)</h2>", sec)
            reg = html.unescape(reg.group(1)) if reg else None
            for m in re.finditer(r"<a href='/profile/\?r=(\d+)&amp;rt=track' title='([^']*)'><span class='genInline'>.*?</span><em>(.*?)</em>", sec):
                out[m.group(1)] = {"id": int(m.group(1)), "name": html.unescape(m.group(2)),
                                   "place": html.unescape(m.group(3)), "region_group": reg}
        print(l, len(out), flush=True)
    json.dump(list(out.values()), open(os.path.join(RAW, "dir", "mrp_index.json"), "w"), indent=0)


if __name__ == "__main__":
    main()
