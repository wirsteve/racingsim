"""Fetch MyRacePass track profiles (https://www.myracepass.com/tracks/<id>) for North American
tracks in the index and extract only sim facts: size, banking category, composition, shape,
map coordinates, dates of the latest listed events, class names raced.

robots.txt allows /tracks/; >=2.5 s between requests; results cached in raw/dir/mrp_tracks.jsonl
so the script resumes. Names that are clearly not circuit/oval venues (drag strips,
pulls, derby arenas, motocross) are skipped up front.
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

OUT = os.path.join(RAW, "dir", "mrp_tracks.jsonl")
NA = {"Midwest", "Southeast", "West", "Northeast", "Southwest", "Canada", "Mexico"}
SKIP = re.compile(r"drag(way|strip| strip| racing)|\bpull|derby|mud |mud bog|motocross|\bmx\b|tractor|"
                  r"off.?road|atv|bmx|snowmobile|sand ?drag|dragstrip|drags\b|monster truck|rodeo", re.I)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def get(url):
    time.sleep(2.5)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def extract(s):
    rec = {}
    m = re.search(r"q=loc:(-?\d+\.\d+)\+(-?\d+\.\d+)", s)
    if m:
        rec["lat"], rec["lon"] = float(m.group(1)), float(m.group(2))
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    for k in ("SIZE", "BANKING", "COMPOSITION", "SHAPE", "ELEVATION"):
        if k in lines:
            i = lines.index(k)
            if i + 1 < len(lines) and lines[i + 1] not in ("SIZE", "BANKING", "COMPOSITION", "SHAPE", "ELEVATION"):
                rec[k.lower()] = lines[i + 1]
    dates = re.findall(rf"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (?:{MONTHS}) \d+, (\d{{4}})", t)
    rec["event_years"] = sorted({int(y) for y in dates})
    # class names listed under events (short comma lists), keep unique tokens
    classes = set()
    for i, l in enumerate(lines):
        if re.match(rf"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (?:{MONTHS})", l):
            for x in lines[i + 1:i + 3]:
                if "," in x and len(x) < 400:
                    classes |= {c.strip() for c in x.split(",") if 2 < len(c.strip()) < 50}
    rec["classes"] = sorted(classes)[:40]
    # header block: name and city line after "Try MRP"
    if "Try MRP" in lines:
        i = lines.index("Try MRP")
        rec["page_name"] = lines[i + 1] if i + 1 < len(lines) else None
        rec["page_place"] = lines[i + 2] if i + 2 < len(lines) else None
    rec["claimed"] = any(l.startswith("Profile claimed by") for l in lines)
    return rec


def main():
    idx = json.load(open(os.path.join(RAW, "dir", "mrp_index.json")))
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            done.add(json.loads(l)["id"])
    todo = [r for r in idx if r["region_group"] in NA and r["id"] not in done and not SKIP.search(r["name"])]
    print(len(todo), "to fetch", flush=True)
    with open(OUT, "a") as f:
        for n, r in enumerate(todo):
            url = f"https://www.myracepass.com/tracks/{r['id']}"
            try:
                s = get(url)
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    print("blocked/rate-limited", e.code, "- stopping", flush=True)
                    break
                rec = {"error": e.code}
            except Exception as e:
                rec = {"error": str(e)}
            else:
                if "Just a moment" in s[:3000] or "captcha" in s[:5000].lower():
                    print("challenge page - stopping", flush=True)
                    break
                rec = extract(s)
            rec.update({"id": r["id"], "name": r["name"], "place": r["place"], "region_group": r["region_group"], "url": url})
            f.write(json.dumps(rec) + "\n")
            f.flush()
            if n % 25 == 0:
                print(n, r["name"], rec.get("size"), rec.get("composition"), rec.get("event_years")[-1:] if rec.get("event_years") else None, flush=True)


if __name__ == "__main__":
    main()
