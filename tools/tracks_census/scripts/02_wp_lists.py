"""Step 2: download and parse Wikipedia list articles of North American race tracks.

Output: raw/wp_list_entries.json  (one row per table row / bullet)
"""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import mwparserfromhell as mwp
from wp_common import RAW, _get, save
from wikitext_util import find_coord, first_link, links, parse_length_mi, strip, years

LISTS = {
    "List_of_auto_racing_tracks_in_the_United_States": "USA",
    "List_of_dirt_track_ovals_in_the_United_States": "USA",
    "List_of_dirt_track_ovals_in_Canada": "Canada",
    "List_of_auto_racing_tracks_in_Canada": "Canada",
    "List_of_auto_racing_tracks_in_Mexico": "Mexico",
    "List_of_NASCAR_tracks": None,
    "List_of_American_Championship_Car_racetracks": None,
    "List_of_sports_venues_in_North_Carolina": "USA",
}
LDIR = os.path.join(RAW, "lists")
os.makedirs(LDIR, exist_ok=True)


def fetch(title):
    p = os.path.join(LDIR, title + ".wiki")
    if not os.path.exists(p):
        txt = _get("https://en.wikipedia.org/w/index.php?" + urllib.parse.urlencode({"title": title, "action": "raw"}),
                   accept="text/plain")
        open(p, "w").write(txt)
    return open(p).read()


def header_key(h):
    h = h.lower()
    for key, pats in [("name", ["track", "name", "venue", "circuit"]),
                      ("city", ["location", "city", "town"]),
                      ("region", ["state", "province"]),
                      ("opened", ["opened", "open", "built", "year"]),
                      ("closed", ["closed", "defunct"]),
                      ("surface", ["surface"]),
                      ("length", ["length", "distance"]),
                      ("series", ["series", "events", "named race"]),
                      ("shape", ["shape", "layout", "type", "crossing"]),
                      ("banking", ["banking"]),
                      ("turns", ["turns"]),
                      ("seasons", ["season"]),
                      ("notes", ["notes"])]:
        if any(p in h for p in pats):
            return key
    return h


def parse_tables(title, text, country):
    code = mwp.parse(text)
    section = []
    rows = []
    for node in code.nodes:
        if isinstance(node, mwp.nodes.Heading):
            lvl = node.level
            section = section[: lvl - 2] + [strip(node.title)]
            continue
        if not (isinstance(node, mwp.nodes.Tag) and str(node.tag) == "table"):
            continue
        trs = [n for n in node.contents.nodes if isinstance(n, mwp.nodes.Tag) and str(n.tag) == "tr"]
        headers = [header_key(strip(n.contents)) for n in node.contents.nodes
                   if isinstance(n, mwp.nodes.Tag) and str(n.tag) == "th"]
        for tr in trs:
            cells = [n for n in tr.contents.nodes if isinstance(n, mwp.nodes.Tag) and str(n.tag) in ("td", "th")]
            if cells and all(str(c.tag) == "th" for c in cells):
                headers = [header_key(strip(c.contents)) for c in cells]
                continue
            if not cells or not headers:
                continue
            style = " ".join(str(a) for a in tr.attributes).lower()
            row = {"list": title, "section": " / ".join(section), "country": country,
                   "defunct_shading": "cccccc" in style}
            raw = {}
            for h, c in zip(headers, cells):
                raw.setdefault(h, str(c.contents))
            name_cell = raw.get("name") or str(cells[0].contents)
            fl = first_link(name_cell)
            row["name"] = strip(re.split(r"<br", name_cell)[0]) or (fl[1] if fl else "")
            if "[[" in row["name"] or "|" in row["name"]:
                row["name"] = re.sub(r"\[\[(?:[^\]|]*\|)?", "", row["name"]).replace("]]", "").split("|")[-1].strip()
            row["name"] = row["name"].strip()
            row["link"] = fl[0] if fl else None
            all_links = links(name_cell)
            row["other_links"] = [l[0] for l in all_links[1:]]
            row["coord"] = find_coord(" ".join(str(c.contents) for c in cells))
            row["city"] = strip(re.split(r"<br", raw.get("city", ""))[0]) or None
            row["region"] = strip(raw.get("region", "")) or None
            row["opened_raw"] = strip(raw.get("opened", "")) or None
            row["closed_raw"] = strip(raw.get("closed", "")) or None
            row["surface"] = strip(raw.get("surface", "")) or None
            row["length_mi"] = parse_length_mi(raw.get("length"))
            row["length_raw"] = strip(raw.get("length", "")) or None
            row["series"] = [l[1] for l in links(raw.get("series", ""))] or (
                [s.strip() for s in strip(raw.get("series", "")).split(";") if s.strip()])
            row["series_links"] = [l[0] for l in links(raw.get("series", ""))]
            row["shape"] = strip(raw.get("shape", "")) or None
            row["banking_raw"] = strip(raw.get("banking", "")) or None
            row["turns_raw"] = strip(raw.get("turns", "")) or None
            row["seasons_raw"] = strip(raw.get("seasons", "")) or None
            row["notes"] = strip(raw.get("notes", ""))[:300] or None
            if row["name"]:
                rows.append(row)
    return rows


def parse_bullets(title, text, country):
    rows = []
    region = None
    section = None
    for line in text.splitlines():
        m = re.match(r"^=+\s*(.+?)\s*=+\s*$", line)
        if m:
            section = strip(m.group(1))
            if country == "Canada":
                region = section
            continue
        m1 = re.match(r"^\*\s*([^*].*)$", line)
        m2 = re.match(r"^\*\*\s*(.+)$", line)
        if m2 and country == "USA":
            body = m2.group(1)
        elif m1 and country == "USA" and not m2:
            region = strip(m1.group(1))
            continue
        elif m1 and country == "Canada":
            body = m1.group(1)
        else:
            continue
        fl = first_link(body)
        rows.append({"list": title, "section": section, "country": country, "region": region,
                     "name": strip(body), "link": fl[0] if fl else None,
                     "link_label": fl[1] if fl else None, "coord": find_coord(body),
                     "surface": "dirt", "shape": "oval"})
    return rows


def main():
    out = []
    for title, country in LISTS.items():
        try:
            text = fetch(title)
        except Exception as e:
            print("fail", title, e)
            continue
        if "dirt_track_ovals" in title:
            rows = parse_bullets(title, text, country)
        else:
            rows = parse_tables(title, text, country)
        print(title, len(rows))
        out.extend(rows)
    save("wp_list_entries.json", out)
    print("total", len(out))


if __name__ == "__main__":
    main()
