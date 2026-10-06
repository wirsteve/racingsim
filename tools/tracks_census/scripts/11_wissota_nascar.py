"""WISSOTA official current-track list (https://www.wissota.org/Tracks/Current, MyRacePass-hosted;
robots.txt allows /Tracks/) and the 2026 NASCAR Local Racing Series track list from Wikipedia
(nascar.com itself is Cloudflare-blocked for scripts).

Output: raw/dir/wissota_tracks.json, raw/dir/nascar_local_2026.json
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from census_util import region_from_text
from wp_common import RAW, UA

D = os.path.join(RAW, "dir")


def wissota():
    p = os.path.join(D, "wissota_tracks.html")
    if not os.path.exists(p):
        time.sleep(2)
        req = urllib.request.Request("https://www.wissota.org/Tracks/Current", headers={"User-Agent": UA})
        open(p, "w").write(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"))
    s = open(p).read()
    out = []
    for art in re.findall(r'<article class="mrp-article">(.*?)</article>', s, flags=re.S):
        m = re.search(r'<h5><a href="https://www.myracepass.com/tracks/(\d+)"[^>]*>(.*?)</a><small>(.*?)</small>', art)
        if not m:
            continue
        lis = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<li[^>]*>(.*?)</li>", art, flags=re.S)]
        web = re.search(r'<a href="(http[^"]+)" target="_blank">Website</a>', art)
        place = html.unescape(m.group(3)).strip()
        out.append({"name": html.unescape(m.group(2)).strip(), "mrp_id": int(m.group(1)), "place": place,
                    "city": place.split(",")[0].strip(), "region": region_from_text(place)[0],
                    "description": lis[0] if lis else None, "website": web.group(1) if web else None})
    json.dump(out, open(os.path.join(D, "wissota_tracks.json"), "w"), indent=1)
    print("wissota", len(out))


def nascar_local():
    txt = open(os.path.join(RAW, "lists", "NASCAR_Local_Racing_Series.wiki")).read()
    sec = txt.split("==2026 tracks==")[1].split("==References==")[0]
    out = []
    for line in sec.splitlines():
        m = re.match(r"^\*\s*\[\[(?::fr:)?([^\]|]+?)\s*(?:\|([^\]]+))?\]\]\s*[–-]\s*(.+?)\s*\((.+?)\)", line)
        if not m:
            continue
        place = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", m.group(3))
        place = re.sub(r"<ref.*", "", place).strip()
        reg, country = region_from_text(place)
        out.append({"link": m.group(1).strip(), "name": (m.group(2) or m.group(1)).strip(), "place": place,
                    "city": place.split(",")[0].strip(), "region": reg, "country": country, "desc": m.group(4),
                    "frwiki": ":fr:" in line})
    json.dump(out, open(os.path.join(D, "nascar_local_2026.json"), "w"), indent=1)
    print("nascar local", len(out))


if __name__ == "__main__":
    wissota()
    nascar_local()
