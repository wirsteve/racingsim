"""IMCA official track directory (https://www.imca.com/view/track-directory/).

The directory page loads its table through the site's public DataTables endpoint
(admin-ajax.php, action=gv_datatables_data) which returns names + geocoded markers.
Each entry page lists size & surface, divisions, night, address, website.
robots.txt: allows all (checked 2026-10-06). >=2 s between requests.
We store only facts (no promoter names / phones / emails).
Output: raw/dir/imca_tracks.json
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from wp_common import RAW, UA

D = os.path.join(RAW, "dir")
os.makedirs(D, exist_ok=True)


def get(url, data=None):
    time.sleep(2.1)
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text_lines(s):
    i = s.find("main-content")
    s = s[i:]
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    return [l.strip() for l in t.split("\n") if l.strip()]


def main():
    page = get("https://www.imca.com/view/track-directory/")
    m = re.search(r'"nonce":"([0-9a-f]+)".*?"configHash":"([0-9a-f]+)"', page)
    nonce, chash = m.group(1), m.group(2)
    body = urllib.parse.urlencode({
        "action": "gv_datatables_data", "view_id": 4138, "post_id": 4138, "nonce": nonce,
        "getData": "false", "hideUntilSearched": "0", "setUrlOnSearch": "true", "noEntriesOption": 0,
        "configHash": chash, "draw": 1, "start": 0, "length": -1, "order[0][column]": 1,
        "order[0][dir]": "asc", "columns[0][name]": "gv_1", "columns[1][name]": "gv_2", "search[value]": ""}).encode()
    dt = json.loads(get("https://www.imca.com/wp-admin/admin-ajax.php", body))
    out = []
    cache_p = os.path.join(D, "imca_entries_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    for row in dt["data"]:
        a = re.search(r'href="([^"]+)">([^<]+)</a>', row["1"])
        url, name = a.group(1).replace("\\/", "/"), html.unescape(a.group(2))
        mk = (row.get("gv_marker") or [{}])[0]
        rec = {"name": name.strip(), "url": url, "lat": _f(mk.get("lat")), "lon": _f(mk.get("long"))}
        if url not in cache:
            try:
                cache[url] = text_lines(get(url))[:40]
            except Exception as e:
                print("fail", url, e)
                continue
            json.dump(cache, open(cache_p, "w"))
        lines = cache[url]
        f = {}
        keys = ["Track Name", "Size & Surface", "Divisions", "Night of Operation", "Website", "Address",
                "Map It", "Entry Map", "Directions & GPS", "Promoter", "Phone", "Email", "Facebook", "Twitter"]
        for i, l in enumerate(lines):
            if l in keys and i + 1 < len(lines):
                if l == "Address":
                    addr = []
                    for x in lines[i + 1:i + 4]:
                        if x in keys:
                            break
                        addr.append(x)
                    f[l] = addr
                else:
                    f.setdefault(l, lines[i + 1] if lines[i + 1] not in keys else None)
        rec["size_surface"] = f.get("Size & Surface")
        rec["divisions"] = f.get("Divisions")
        rec["night"] = f.get("Night of Operation")
        rec["website"] = f.get("Website")
        addr = f.get("Address") or []
        rec["address_lines"] = addr
        cityline = addr[-1] if addr else ""
        mm = re.match(r"^(.*?),\s*([A-Za-z .]+?)\s+([0-9A-Z]{3}\s?[0-9A-Z]{3}|\d{5})?$", cityline)
        if mm:
            rec["city"], rec["state_name"] = mm.group(1).strip(), mm.group(2).strip()
        out.append(rec)
        print(len(out), name, rec.get("size_surface"), rec.get("city"), flush=True)
    json.dump(out, open(os.path.join(D, "imca_tracks.json"), "w"), indent=1)


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


if __name__ == "__main__":
    main()
