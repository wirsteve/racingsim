"""Wikitext helpers: coordinates, lengths, years, cleaning."""
import re

import mwparserfromhell as mwp


def _num(s):
    try:
        return float(str(s).strip())
    except Exception:
        return None


def parse_coord_template(t):
    """Return (lat, lon) from a {{coord}} template node, or None."""
    params = [str(p.value).strip() for p in t.params if not p.showkey]
    # drop trailing non-coordinate params (region:..., type:...)
    vals = []
    for p in params:
        if re.match(r"^(region|type|scale|dim|globe|source|name|display|format|notes)[:=]", p) or ":" in p:
            break
        vals.append(p)
    if not vals:
        return None
    hemis = [i for i, v in enumerate(vals) if v.upper() in ("N", "S", "E", "W")]
    try:
        if len(hemis) >= 2:
            i1, i2 = hemis[0], hemis[1]
            lat_parts = [float(x) for x in vals[:i1] if x != ""]
            lon_parts = [float(x) for x in vals[i1 + 1:i2] if x != ""]

            def dms(parts):
                v = 0.0
                for k, x in enumerate(parts[:3]):
                    v += x / (60 ** k)
                return v

            lat = dms(lat_parts) * (-1 if vals[i1].upper() == "S" else 1)
            lon = dms(lon_parts) * (-1 if vals[i2].upper() == "W" else 1)
        elif len(vals) >= 2 and _num(vals[0]) is not None and _num(vals[1]) is not None:
            lat, lon = float(vals[0]), float(vals[1])
        else:
            return None
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 5), round(lon, 5)


def find_coord(wikicode):
    if isinstance(wikicode, str):
        wikicode = mwp.parse(wikicode)
    for t in wikicode.filter_templates(recursive=True):
        if str(t.name).strip().lower() in ("coord", "coordinates", "coor", "coor d", "coor dms"):
            c = parse_coord_template(t)
            if c:
                return c
    return None


FRACTIONS = {"1/4": 0.25, "1/3": 1 / 3, "3/8": 0.375, "1/2": 0.5, "5/8": 0.625, "3/4": 0.75,
             "7/8": 0.875, "1/5": 0.2, "2/5": 0.4, "1/8": 0.125, "3/10": 0.3, "4/10": 0.4,
             "1/6": 1 / 6, "5/16": 0.3125, "1/10": 0.1, "3/5": 0.6}


def parse_length_mi(text):
    """Best-effort length in miles from wikitext (first value). Returns float or None."""
    if text is None:
        return None
    s = str(text)
    code = mwp.parse(s)
    for t in code.filter_templates(recursive=True):
        n = str(t.name).strip().lower()
        if n in ("convert", "cvt", "convinfobox"):
            ps = [str(p.value).strip() for p in t.params if not p.showkey]
            if len(ps) >= 2:
                v = ps[0].replace(",", "")
                unit = ps[1].lower()
                # range form {{convert|0.4|-|0.5|mi}}
                if unit in ("-", "to", "and", "or", "&") and len(ps) >= 4:
                    unit = ps[3].lower()
                val = _frac_or_num(v)
                if val is None:
                    continue
                if unit in ("mi", "mile", "miles"):
                    return round(val, 4)
                if unit in ("km", "kilometre", "kilometer", "kilometres", "kilometers"):
                    return round(val * 0.621371, 4)
                if unit in ("m", "metre", "meter", "metres", "meters"):
                    return round(val / 1609.344, 4)
                if unit in ("ft", "feet", "foot"):
                    return round(val / 5280, 4)
                if unit in ("yd", "yards"):
                    return round(val / 1760, 4)
    plain = strip(s)
    m = re.search(r"(\d+(?:\.\d+)?|\d+/\d+|\.\d+)\s*[- ]?\s*(mi(?:les?)?|mile|km|kilomet(?:er|re)s?|m(?:et(?:er|re)s?)?|ft|feet)\b", plain, re.I)
    if m:
        val = _frac_or_num(m.group(1))
        unit = m.group(2).lower()
        if val is None:
            return None
        if unit.startswith("mi"):
            return round(val, 4)
        if unit.startswith("k"):
            return round(val * 0.621371, 4)
        if unit in ("ft", "feet"):
            return round(val / 5280, 4)
        if unit.startswith("m"):
            return round(val / 1609.344, 4)
    return None


def _frac_or_num(v):
    v = v.strip()
    if v in FRACTIONS:
        return FRACTIONS[v]
    m = re.match(r"^(\d+)/(\d+)$", v)
    if m and int(m.group(2)):
        return int(m.group(1)) / int(m.group(2))
    try:
        return float(v)
    except ValueError:
        return None


def strip(text):
    """Wikitext -> plain text (links to labels, templates removed, refs dropped)."""
    if text is None:
        return ""
    s = re.sub(r"<ref[^>]*/>", "", str(text))
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?\s*>", "; ", s, flags=re.I)
    code = mwp.parse(s)
    for t in code.filter_templates(recursive=False):
        n = str(t.name).strip().lower()
        try:
            if n in ("convert", "cvt"):
                ps = [str(p.value).strip() for p in t.params if not p.showkey]
                code.replace(t, " ".join(ps[:2]))
            elif n in ("start date", "start date and age", "end date", "opening date"):
                ps = [str(p.value).strip() for p in t.params if not p.showkey]
                code.replace(t, ps[0] if ps else "")
            elif n in ("nowrap", "small", "nobr", "flagicon", "lang", "abbr"):
                ps = [str(p.value).strip() for p in t.params if not p.showkey]
                code.replace(t, ps[0] if ps and n not in ("flagicon",) else "")
            elif n in ("plainlist", "unbulleted list", "ubl", "flatlist", "hlist"):
                ps = [str(p.value).strip() for p in t.params if not p.showkey]
                code.replace(t, "; ".join(ps))
            else:
                code.replace(t, "")
        except ValueError:
            pass
    out = code.strip_code(normalize=True, collapse=True)
    out = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", out)
    out = re.sub(r"\s+", " ", out).strip(" ;,")
    return out


def years(text):
    return [int(y) for y in re.findall(r"\b(18[5-9]\d|19\d\d|20[0-2]\d)\b", strip(text))]


def first_link(wikicode):
    if isinstance(wikicode, str):
        wikicode = mwp.parse(wikicode)
    for l in wikicode.filter_wikilinks():
        tgt = str(l.title).strip()
        if tgt.lower().startswith(("file:", "image:", "category:")):
            continue
        return tgt, strip(l.text) if l.text else tgt
    return None


def links(wikicode):
    if isinstance(wikicode, str):
        wikicode = mwp.parse(wikicode)
    out = []
    for l in wikicode.filter_wikilinks():
        tgt = str(l.title).strip()
        if tgt.lower().startswith(("file:", "image:", "category:")):
            continue
        out.append((tgt, strip(l.text) if l.text else tgt))
    return out
