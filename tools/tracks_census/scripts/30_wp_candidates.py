"""Step 30: turn Wikipedia/Wikidata pages + list rows into candidate track records.

Output: raw/cand_wp.json  (list of candidate dicts, source-tagged)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mwparserfromhell as mwp
from census_util import ALL_NAMES, banking_category, region_from_text, surface_from_text
from wp_common import load, save
from wikitext_util import find_coord, links, parse_length_mi, strip, years

VENUE_INFOBOX = {"infobox motorsport venue", "infobox venue", "infobox stadium", "infobox racecourse",
                 "infobox sports venue", "infobox raceway", "infobox race track", "infobox nrhp", "infobox park",
                 "infobox amusement park", "infobox casino", "infobox fairground"}
EVENT_INFOBOX = re.compile(r"motor race|race report|recurring event|wec race|settlement|organization|company|"
                           r"nascar team|military|university|motorsport championship|horserace|speedway team|"
                           r"person|racing driver|airport|protected area")
VENUE_CLASS = {"motorsport racing track", "race track", "street circuit", "kart circuit", "speedway",
               "oval track", "dirt track", "racing circuit", "motorsport venue", "roval"}
SERIES_WORDS = re.compile(r"series|cup\b|tour\b|championship|indycar|nascar|arca|imsa|usac|outlaws|lucas oil|scca|"
                          r"trans.?am|formula|grand prix|sportscar|super dirtcar|ascs|powri|usmts|cars tour|pass\b|"
                          r"\bact\b|whelen|modified|late model|sprint|midget|pinty|cascar|truck|xfinity|busch|"
                          r"winston|craftsman|camping world|nhra|ama|motogp|world challenge|pirelli|sro|f1\b|"
                          r"can-am|cart\b|champ car|irl\b|indy|stock car|legends|karting", re.I)
NOT_SERIES = re.compile(r"^(stock car racing|auto racing|motorsport|drag racing|dirt track racing|oval track racing)$", re.I)


def infobox(code):
    for t in code.filter_templates(recursive=False):
        n = re.sub(r"<!--.*?-->", "", str(t.name), flags=re.S).strip().lower()
        if n.startswith("infobox"):
            return n, t
    return None, None


def p(t, *names):
    if t is None:
        return None
    for n in names:
        if t.has(n):
            v = str(t.get(n).value).strip()
            if v and strip(v):
                return v
    return None


def layout_kind(name, surface_txt, turns, length):
    s = (name or "").lower()
    if "drag" in s or "strip" in s:
        return "drag"
    if "motocross" in s or "mx" == s or "off-road" in s or "off road" in s or "rallycross" in s or "skid" in s:
        return "other"
    if "kart" in s:
        return "kart_circuit"
    if "figure" in s:
        return "figure_eight"
    if "roval" in s:
        return "roval"
    if re.search(r"oval|speedway|short track|tri-?oval|quarter.?mile|half.?mile|bullring|dirt track|superspeedway|mile track", s):
        return "oval"
    if re.search(r"road|course|circuit|grand prix|club|full|north|south|east|west|national|international|configuration|long|short|chicane|infield|layout|track [a-z0-9]", s):
        return "road_course"
    if turns is not None:
        return "oval" if turns <= 4 else "road_course"
    return None


def first_num(txt):
    if not txt:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*°", strip(txt)) or re.search(r"(\d+(?:\.\d+)?)", strip(txt))
    if m:
        v = float(m.group(1))
        if 0 <= v <= 45:
            return v
    return None


def parse_page(title, pg, wd):
    w = pg.get("wikitext") or ""
    if w.lstrip().upper().startswith("#REDIRECT"):
        return None, "redirect"
    code = mwp.parse(w[:20000])
    ibn, ib = infobox(code)
    qid = pg.get("qid")
    e = wd.get(qid, {}) if qid else {}
    classes = set(e.get("_classes", []))
    cats = " | ".join(pg.get("categories", [])).lower()
    is_venue = (ibn == "infobox motorsport venue") or bool(classes & VENUE_CLASS) or bool(
        re.search(r"motorsport venues in|race tracks in|speedways in|road courses in|dirt oval|paved oval|"
                  r"defunct motorsport venues|racing venues in|nascar tracks|karting venues", cats))
    if ibn and EVENT_INFOBOX.search(ibn):
        is_venue = False if not (classes & VENUE_CLASS) else is_venue
    if not is_venue:
        return None, f"not venue ({ibn})"
    if re.search(r"drag racing venues|dragstrips", cats) and not re.search(
            r"oval|road course|speedway venues|nascar|dirt|motorsport venues in", cats.replace("drag racing venues", "")):
        pass
    name = re.sub(r"\s*\(.*?\)\s*$", "", pg["title"]).strip()
    rec = {"source": "wp", "wp_title": pg["title"], "qid": qid, "name": name, "infobox": ibn,
           "categories": pg.get("categories", [])}
    # location
    loc = strip(p(ib, "location", "Location", "address"))
    rec["location_raw"] = loc or None
    reg, country = region_from_text(loc)
    if not reg:
        for c in pg.get("categories", []):
            m = re.search(r"(?:venues|tracks|courses|ovals|speedways|buildings and structures|sports venues|sports in) in (.+?)(?: \(state\)| \(U\.S\. state\))?$", c)
            if m:
                reg, country = region_from_text(m.group(1).replace("Category:", ""))
                if reg:
                    break
    rec["region"], rec["country"] = reg, country
    city = None
    if loc:
        parts = [x.strip() for x in re.split(r"[;,]", loc) if x.strip()]
        for i, x in enumerate(parts):
            if region_from_text(x)[0] and i > 0:
                city = parts[i - 1]
                break
        if city is None and parts:
            city = parts[0] if not region_from_text(parts[0])[0] else None
    if city and re.search(r"\d{3,}|road|highway|street|route|\bave\b|\bst\b|drive|county road", city, re.I):
        city = None
    rec["city"] = city
    # coordinates
    coord = pg.get("coord")
    if not coord and e.get("P625"):
        v = e["P625"][0]["v"]
        coord = [v["latitude"], v["longitude"]]
    if not coord:
        c = find_coord(code)
        coord = list(c) if c else None
    rec["coord"] = coord
    # dates
    op = years(p(ib, "opened", "Opened", "opening", "built", "Built")) if ib else []
    rec["opened"] = op[0] if op else None
    clraw = p(ib, "closed", "Closed", "demolished") if ib else None
    cl = years(clraw) if clraw else []
    rec["closed"] = max(cl) if cl else None
    if rec["closed"] and (len(op) > 1 and max(op) > rec["closed"] or re.search(r"reopen|re-open|present", strip(clraw), re.I)):
        rec["reopened_note"] = f"closed {rec['closed']}, later reopened (infobox)"
        rec["closed"] = None
    if rec["opened"] is None:
        for prop in ("P1619", "P571"):
            if e.get(prop):
                try:
                    rec["opened"] = int(e[prop][0]["v"]["time"][1:5])
                    rec["opened_src"] = "wikidata"
                    break
                except Exception:
                    pass
    if rec["closed"] is None:
        for prop in ("P3999", "P576"):
            if e.get(prop):
                try:
                    rec["closed"] = int(e[prop][0]["v"]["time"][1:5])
                    rec["closed_src"] = "wikidata"
                    break
                except Exception:
                    pass
    rec["defunct_category"] = bool(re.search(r"defunct|former|demolished|closed", cats))
    if rec["defunct_category"] and rec["closed"] is None:
        # closure year stated in the article prose (lead/history), e.g. "closed in 1979", "demolished in 2005"
        plain = strip(w[:15000])
        m = re.search(r"\b(?:(?:track|speedway|raceway|facility|venue|it) (?:was |were )?(?:permanently )?(?:closed|demolished|torn down)|"
                      r"(?:closed|demolished|torn down) (?:in|after|following|at the end of)(?: the)?|"
                      r"(?:final|last) (?:auto )?race (?:at the (?:track|speedway) )?(?:was )?(?:held |run )?(?:on|in))"
                      r"(?: [A-Z][a-z]+)?(?: \d{1,2},?)? ((?:19[0-9]{2}|20[0-2][0-9]))\b", plain)
        if m:
            rec["closed"] = int(m.group(1))
            rec["closed_src"] = "wikipedia-text"
            rec["closed_snippet"] = m.group(0)[:90]
    # names
    fn = p(ib, "former_names", "former names", "Previous names", "former_name")
    aliases = []
    if fn:
        for x in re.split(r";|\n|\*", strip(fn)):
            x = re.sub(r"\(.*?\)", "", x).strip(" ,.;")
            if 3 < len(x) < 80 and x.lower() != name.lower():
                aliases.append(x)
    nick = p(ib, "nicknames", "nickname")
    rec["nicknames"] = [x.strip() for x in re.split(r";|,", strip(nick)) if x.strip()][:5] if nick else []
    rec["aliases"] = aliases
    # events -> series
    ev = p(ib, "events", "major_events", "major events", "Major events")
    series = []
    if ev:
        for tgt, lbl in links(ev):
            if SERIES_WORDS.search(tgt) and not NOT_SERIES.match(tgt):
                series.append(tgt.split("#")[0])
        if not series:
            for x in re.split(r";|\n", strip(ev)):
                x = x.strip(" *")
                if 3 < len(x) < 70 and SERIES_WORDS.search(x):
                    series.append(x)
    rec["major_series"] = list(dict.fromkeys(series))
    # layouts
    lays = []
    for i in ["", "2", "3", "4", "5", "6", "7", "8"]:
        lname = strip(p(ib, f"layout{i}", f"layoutname{i}")) if ib else None
        surf = strip(p(ib, f"surface{i}")) if ib else None
        lmi = parse_length_mi(p(ib, f"length{i}_mi", f"miles{i}")) if ib else None
        if lmi is None and ib is not None:
            raw_mi = strip(p(ib, f"length{i}_mi") or "")
            if re.fullmatch(r"\d*\.?\d+", raw_mi or ""):
                lmi = float(raw_mi)
        if lmi is None and ib is not None:
            lkm = p(ib, f"length{i}_km", f"km{i}")
            if lkm:
                try:
                    lmi = round(float(re.findall(r"\d*\.?\d+", strip(lkm))[0]) * 0.621371, 3)
                except Exception:
                    lmi = None
            if lmi is None and p(ib, f"length{i}_mi"):
                try:
                    lmi = float(re.findall(r"\d*\.?\d+", strip(p(ib, f"length{i}_mi")))[0])
                except Exception:
                    pass
        trn = p(ib, f"turns{i}") if ib else None
        try:
            trn = int(re.findall(r"\d+", strip(trn))[0]) if trn else None
        except Exception:
            trn = None
        bank = p(ib, f"banking{i}") if ib else None
        if not any([lname, surf, lmi, trn, bank]):
            continue
        lays.append({"layout": lname, "surface_raw": surf, "surface": surface_from_text(surf), "length_mi": lmi,
                     "turns": trn, "banking_raw": strip(bank)[:120] if bank else None,
                     "kind": layout_kind(lname, surf, trn, lmi)})
    rec["layouts"] = lays
    rec["wd_classes"] = sorted(classes)
    return rec, "ok"


def main():
    pages = load("wp_pages.json")
    wd = load("wd_entities.json")
    labels = load("wd_class_labels.json")
    for q, e in wd.items():
        e["_classes"] = [labels.get(c["v"]["id"]) for c in e.get("P31", []) if labels.get(c["v"]["id"])]
    out, skipped = [], {}
    seen_titles = set()
    for req, pg in pages.items():
        if pg.get("missing") or not pg.get("wikitext"):
            continue
        if pg["title"] in seen_titles:
            continue
        seen_titles.add(pg["title"])
        rec, why = parse_page(req, pg, wd)
        if rec:
            out.append(rec)
        else:
            skipped[pg["title"]] = why
    # Wikidata-only items (no enwiki article) that are tracks with coordinates in NA
    enwiki_q = {pg.get("qid") for pg in pages.values() if pg.get("qid")}
    for q, e in wd.items():
        if q in enwiki_q or not (set(e["_classes"]) & VENUE_CLASS) or not e.get("P625"):
            continue
        cty = {c["v"]["id"] for c in e.get("P17", [])}
        if not cty & {"Q30", "Q16", "Q96"}:
            continue
        v = e["P625"][0]["v"]
        rec = {"source": "wd", "qid": q, "name": e.get("label"), "coord": [v["latitude"], v["longitude"]],
               "wd_classes": e["_classes"], "aliases": e.get("aliases", [])[:5], "sitelinks": e.get("sitelinks", {}),
               "country": {"Q30": "USA", "Q16": "CAN", "Q96": "MEX"}[sorted(cty & {"Q30", "Q16", "Q96"})[0]]}
        if e.get("P2043"):
            try:
                amt = float(e["P2043"][0]["v"]["amount"])
                unit = e["P2043"][0]["v"]["unit"].rsplit("/", 1)[-1]
                rec["length_mi"] = round(amt * {"Q253276": 1, "Q828224": 0.621371, "Q11573": 1 / 1609.344}.get(unit, float("nan")), 4)
            except Exception:
                pass
        for prop, key in (("P1619", "opened"), ("P571", "opened"), ("P576", "closed"), ("P3999", "closed")):
            if e.get(prop) and key not in rec:
                try:
                    rec[key] = int(e[prop][0]["v"]["time"][1:5])
                except Exception:
                    pass
        out.append(rec)
    save("cand_wp.json", out)
    save("cand_wp_skipped.json", skipped)
    print(len(out), "candidates;", len(skipped), "skipped")


if __name__ == "__main__":
    main()
