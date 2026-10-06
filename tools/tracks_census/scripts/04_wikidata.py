"""Step 4: Wikidata.

(a) SPARQL: every item located in USA/Canada/Mexico that is an instance of a subclass of
    race track (Q1777138) or of motorsport racing track (Q2338524), or whose sport is
    auto racing and has coordinates.
(b) wbgetentities for every QID seen on Wikipedia pages (step 3) + SPARQL hits, to get
    P625 coordinates, P2043 length, P571 inception, P1619 opening, P576/P3999 closure,
    P31 classes, P856 website, P131 location, aliases, enwiki sitelink.

Output: raw/wd_sparql.json, raw/wd_entities.json
"""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from wp_common import RAW, _get, load, save, sparql

Q_TRACKS = """
SELECT DISTINCT ?i ?iLabel ?cty ?coord ?class ?classLabel ?article WHERE {
  VALUES ?cty { wd:Q30 wd:Q16 wd:Q96 }
  { ?i wdt:P31/wdt:P279* wd:Q1777138 . }
  UNION { ?i wdt:P31/wdt:P279* wd:Q2338524 . }
  UNION { VALUES ?sport { wd:Q5367 wd:Q5386 wd:Q1758324 wd:Q2141352 wd:Q1935680 } ?i wdt:P641 ?sport . }
  ?i wdt:P17 ?cty .
  OPTIONAL { ?i wdt:P625 ?coord . }
  OPTIONAL { ?i wdt:P31 ?class . }
  OPTIONAL { ?article schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""
# sports: Q5367 motorsport, Q5386 auto racing, Q1758324 stock car racing, Q2141352 dirt track racing, Q1935680 oval track racing


def entities(qids):
    out = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 50):
        b = qids[i:i + 50]
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(b), "format": "json",
            "props": "labels|aliases|claims|sitelinks", "languages": "en|fr|es", "sitefilter": "enwiki|frwiki|eswiki"})
        d = json.loads(_get(url))
        for q, e in d.get("entities", {}).items():
            out[q] = slim(e)
        print("wd", i + len(b), "/", len(qids), flush=True)
    return out


def _vals(e, p):
    res = []
    for c in e.get("claims", {}).get(p, []):
        dv = c.get("mainsnak", {}).get("datavalue")
        if not dv:
            continue
        v = dv["value"]
        res.append({"v": v, "rank": c.get("rank"),
                    "qual": {k: [q.get("datavalue", {}).get("value") for q in qs] for k, qs in c.get("qualifiers", {}).items()}})
    return res


def slim(e):
    r = {"id": e.get("id"), "label": e.get("labels", {}).get("en", {}).get("value"),
         "aliases": [a["value"] for a in e.get("aliases", {}).get("en", [])],
         "sitelinks": {k: v["title"] for k, v in e.get("sitelinks", {}).items()}}
    for p in ["P31", "P17", "P131", "P625", "P2043", "P571", "P1619", "P576", "P3999", "P856", "P137",
              "P127", "P1448", "P1449", "P912", "P5195", "P1083", "P138", "P793", "P2789"]:
        v = _vals(e, p)
        if v:
            r[p] = v
    return r


def main():
    try:
        res = sparql(Q_TRACKS)
        rows = res["results"]["bindings"]
        save("wd_sparql.json", rows)
    except Exception as e:
        print("sparql failed", e)
        rows = load("wd_sparql.json") if os.path.exists(os.path.join(RAW, "wd_sparql.json")) else []
    qids = {r["i"]["value"].rsplit("/", 1)[1] for r in rows}
    pages = load("wp_pages.json")
    qids |= {p["qid"] for p in pages.values() if p.get("qid")}
    print(len(rows), "sparql rows;", len(qids), "qids")
    cache = load("wd_entities.json") if os.path.exists(os.path.join(RAW, "wd_entities.json")) else {}
    todo = [q for q in qids if q not in cache]
    cache.update(entities(todo))
    save("wd_entities.json", cache)
    # class labels
    cls = set()
    for e in cache.values():
        for c in e.get("P31", []):
            cls.add(c["v"]["id"])
    labels = load("wd_class_labels.json") if os.path.exists(os.path.join(RAW, "wd_class_labels.json")) else {}
    todo = sorted(c for c in cls if c not in labels)
    for i in range(0, len(todo), 50):
        b = todo[i:i + 50]
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(b), "format": "json", "props": "labels", "languages": "en"})
        d = json.loads(_get(url))
        for q, e in d.get("entities", {}).items():
            labels[q] = e.get("labels", {}).get("en", {}).get("value")
    save("wd_class_labels.json", labels)


if __name__ == "__main__":
    main()
