"""Step 3: fetch wikitext (infobox part), coordinates, wikibase item and categories
for every Wikipedia article found via categories (step 1) and lists (step 2).

Output: raw/wp_pages.json {requested_title: {title, qid, coord, categories, wikitext}}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from wp_common import RAW, load, save, wp_api

OUT = "wp_pages.json"


def main(extra_titles=()):
    titles = set(load("wp_category_pages.json"))
    for r in load("wp_list_entries.json"):
        if r.get("link"):
            titles.add(r["link"].split("#")[0])
    titles |= set(extra_titles)
    titles = {t[0].upper() + t[1:] for t in titles if t and not t.lower().startswith(("list of", "category:"))}
    cache = {}
    if os.path.exists(os.path.join(RAW, OUT)):
        cache = load(OUT)
    todo = sorted(t for t in titles if t not in cache)
    print(len(titles), "titles,", len(todo), "to fetch", flush=True)
    for i in range(0, len(todo), 40):
        batch = todo[i:i + 40]
        params = {"action": "query", "titles": "|".join(batch), "redirects": "1",
                  "prop": "coordinates|pageprops|revisions|categories", "rvprop": "content",
                  "rvslots": "main", "ppprop": "wikibase_item", "clshow": "!hidden", "cllimit": "max",
                  "colimit": "max"}
        pages = {}
        redirect = {}
        norm = {}
        cont = {}
        while True:
            d = wp_api({**params, **cont})
            q = d.get("query", {})
            for n in q.get("normalized", []):
                norm[n["from"]] = n["to"]
            for r in q.get("redirects", []):
                redirect[r["from"]] = r["to"]
            for p in q.get("pages", []):
                rec = pages.setdefault(p["title"], {"title": p["title"], "missing": p.get("missing", False),
                                                    "categories": [], "coord": None, "qid": None, "wikitext": None})
                if p.get("coordinates"):
                    c = p["coordinates"][0]
                    rec["coord"] = [c["lat"], c["lon"]]
                if p.get("pageprops", {}).get("wikibase_item"):
                    rec["qid"] = p["pageprops"]["wikibase_item"]
                rec["categories"] += [c["title"] for c in p.get("categories", [])]
                if p.get("revisions"):
                    txt = p["revisions"][0]["slots"]["main"]["content"]
                    rec["wikitext"] = txt[:20000]
                    rec["length"] = len(txt)
            if "continue" in d:
                cont = d["continue"]
            else:
                break
        for t in batch:
            tt = norm.get(t, t)
            tt = redirect.get(tt, tt)
            if tt in pages:
                rec = dict(pages[tt])
                rec["categories"] = sorted(set(rec["categories"]))
                rec["redirected_from"] = t if tt != t else None
                cache[t] = rec
            else:
                cache[t] = {"title": tt, "missing": True}
        print(i + len(batch), "/", len(todo), flush=True)
        if (i // 40) % 10 == 0:
            save(OUT, cache)
    save(OUT, cache)


if __name__ == "__main__":
    extra = []
    if len(sys.argv) > 1:
        extra = json.load(open(sys.argv[1]))
    main(extra)
