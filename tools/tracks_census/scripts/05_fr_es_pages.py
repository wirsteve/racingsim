"""frwiki (Quebec circuits) and eswiki (Mexican circuits) pages: coordinates + Wikidata ids + wikitext.
Output: raw/wp_fr_es_pages.json"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from wp_common import wp_api, save

CATS = [("fr", "Catégorie:Circuit automobile au Québec"), ("fr", "Catégorie:Circuit automobile en Ontario"),
        ("fr", "Catégorie:Circuit de stock car"), ("es", "Categoría:Circuitos de carreras de México")]
out = {}
for lang, c in CATS:
    d = wp_api({"action": "query", "list": "categorymembers", "cmtitle": c, "cmlimit": "500", "cmtype": "page"}, lang=lang)
    titles = [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
    for i in range(0, len(titles), 40):
        q = wp_api({"action": "query", "titles": "|".join(titles[i:i + 40]), "prop": "coordinates|pageprops|revisions",
                    "rvprop": "content", "rvslots": "main", "ppprop": "wikibase_item", "redirects": "1"}, lang=lang)
        for p in q.get("query", {}).get("pages", []):
            co = (p.get("coordinates") or [None])[0]
            out[f"{lang}:{p['title']}"] = {"lang": lang, "title": p["title"], "category": c,
                                          "coord": [co["lat"], co["lon"]] if co else None,
                                          "qid": p.get("pageprops", {}).get("wikibase_item"),
                                          "wikitext": (p.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")[:12000]}
    print(c, len(titles))
save("wp_fr_es_pages.json", out)
