"""Minimal wikitext helpers: table parsing, link extraction, text cleanup."""
import re

REF_RE = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")
MONTHS = {m: i for i, m in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"], 1)}
MON3 = {k[:3]: v for k, v in MONTHS.items()}
MON3["sept"] = 9

def strip_refs(s):
    return COMMENT_RE.sub("", REF_RE.sub("", s))

def _split_top(s, sep="|"):
    """split template args on | at depth 0."""
    out, depth, cur, i = [], 0, "", 0
    while i < len(s):
        c2 = s[i:i+2]
        if c2 in ("{{", "[["):
            depth += 1; cur += c2; i += 2; continue
        if c2 in ("}}", "]]"):
            depth -= 1; cur += c2; i += 2; continue
        if s[i] == sep and depth == 0:
            out.append(cur); cur = ""; i += 1; continue
        cur += s[i]; i += 1
    out.append(cur)
    return out

def expand_templates(s):
    """Replace common inline templates with their display text; drop others."""
    for _ in range(6):
        m = None
        # innermost templates first
        new = re.sub(r"\{\{([^{}]*)\}\}", lambda mm: _tpl(mm.group(1)), s)
        if new == s: break
        s = new
    return s

def _tpl(body):
    parts = _split_top(body)
    name = parts[0].strip().lower().replace("_", " ")
    args = [p for p in parts[1:]]
    pos = [a.strip() for a in args if not re.match(r"^\s*[\w ]+\s*=", a)]
    kw = {}
    for a in args:
        mm = re.match(r"^\s*([\w ]+?)\s*=(.*)$", a, re.S)
        if mm: kw[mm.group(1).strip()] = mm.group(2).strip()
    if name in ("sortname",):
        if len(pos) >= 2:
            first, last = pos[0], pos[1]
            disp = (first + " " + last).strip()
            if len(pos) >= 3 and pos[2]:
                return "[[%s|%s]]" % (pos[2], disp)
            if kw.get("nolink"):
                return disp
            return "[[%s]]" % disp
    if name in ("sort", "sortkey") and len(pos) >= 2:
        return pos[1]
    if name in ("dts", "date", "start date", "dts2"):
        return "{{DATE|" + "|".join(pos) + "}}".replace("{{", "@@").replace("}}", "@@") if False else "DATE(" + "/".join(pos) + ")"
    if name in ("nowrap", "small", "big", "nobr", "center", "lang", "nowrap begin", "abbr", "tooltip", "bold", "b", "plainlist", "flatlist", "sup", "smaller", "nbsp"):
        if name in ("abbr", "tooltip") and pos: return pos[0]
        if name == "lang" and len(pos) >= 2: return pos[1]
        if name == "nbsp": return " "
        return pos[0] if pos else ""
    if name in ("ubl", "unbulleted list", "hlist", "plainlist"):
        return ", ".join(pos)
    if name in ("convert", "cvt") and pos:
        return pos[0] + " " + (pos[1] if len(pos) > 1 else "")
    if name in ("coord",):
        return "COORD(" + "/".join(pos) + ")"
    if name in ("flagicon", "flag icon", "flagcountry", "flag", "flagu"):
        return "" if name in ("flagicon", "flag icon") else (pos[0] if pos else "")
    if name in ("ndash", "snd", "–"): return "–"
    if name in ("mdash",): return "—"
    if name in ("=", "!"): return {"=": "=", "!": "|"}[name]
    if name == "yes" or name == "no" or name.startswith("table") or name in ("n/a", "na", "dunno", "tba", "tbd", "won", "won-"):
        return pos[0] if pos and name not in ("n/a", "na") else ""
    if name in ("racing driver flag", "flagathlete"):
        return pos[0] if pos else ""
    return ""

def links(s):
    return [(m.group(1).strip(), (m.group(2) if m.group(2) is not None else m.group(1)).strip()) for m in LINK_RE.finditer(s)
            if not re.match(r"^(File|Image|Category|wikt|w):", m.group(1), re.I)]

def clean(s):
    s = strip_refs(s)
    s = expand_templates(s)
    s = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", "", s, flags=re.I)
    s = LINK_RE.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1), s)
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = re.sub(r"<br\s*/?>", ", ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "").replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s).strip(" ,")
    return s

class Cell:
    __slots__ = ("raw", "header", "rowspan", "colspan")
    def __init__(self, raw, header):
        self.raw, self.header = raw, header
        self.rowspan = self.colspan = 1
    @property
    def text(self): return clean(self.raw)
    @property
    def links(self): return links(expand_templates(strip_refs(self.raw)))
    def __repr__(self): return ("!" if self.header else "|") + self.text

def _cell_split(line, header):
    """line content after leading | or !; split on || (and !! for header lines)."""
    seps = r"\|\||!!" if header else r"\|\|"
    # split at depth zero
    parts, depth, cur, i = [], 0, "", 0
    while i < len(line):
        c2 = line[i:i+2]
        if c2 in ("{{", "[["): depth += 1; cur += c2; i += 2; continue
        if c2 in ("}}", "]]"): depth -= 1; cur += c2; i += 2; continue
        if depth == 0 and (c2 == "||" or (header and c2 == "!!")):
            parts.append(cur); cur = ""; i += 2; continue
        cur += line[i]; i += 1
    parts.append(cur)
    cells = []
    for p in parts:
        # attribute|content (depth 0 single pipe)
        sp = _split_top(p)
        attrs = ""
        if len(sp) >= 2 and re.search(r"(style|rowspan|colspan|align|class|width|bgcolor|scope|data-sort-value|nowrap)\s*[=-]|^\s*$", sp[0]) and "[[" not in sp[0] and "{{" not in sp[0]:
            attrs, content = sp[0], "|".join(sp[1:])
        else:
            content = p
        c = Cell(content, header)
        m = re.search(r"rowspan\s*[=-]\s*\"?(\d+)", attrs);  c.rowspan = int(m.group(1)) if m else 1
        m = re.search(r"colspan\s*[=-]\s*\"?(\d+)", attrs);  c.colspan = int(m.group(1)) if m else 1
        cells.append(c)
    return cells

def tables(wikitext, with_context=False):
    """Yield (heading_path, caption, rows) where rows = list of list of Cell, with rowspan/colspan expanded."""
    text = COMMENT_RE.sub("", wikitext)
    lines = text.split("\n")
    out = []
    heading = []
    stack = []
    for ln in lines:
        s = ln.strip()
        hm = re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", s)
        if hm and not stack:
            lvl = len(hm.group(1))
            heading = heading[:lvl-2] + [clean(hm.group(2))]
            continue
        if s.startswith("{|"):
            stack.append({"rows": [], "cur": None, "caption": "", "heading": list(heading), "last": None})
            continue
        if not stack: continue
        t = stack[-1]
        if t["last"] is not None and t["last"].raw.count("{{") > t["last"].raw.count("}}"):
            t["last"].raw += "\n" + ln   # inside a multi-line template (e.g. an unwrapped {{cite web}})
            continue
        if s.startswith("|}"):
            if t["cur"] is not None: t["rows"].append(t["cur"])
            stack.pop()
            out.append((t["heading"], t["caption"], _expand(t["rows"])))
            continue
        if s.startswith("|+"):
            t["caption"] = clean(s[2:]); continue
        if s.startswith("|-"):
            if t["cur"] is not None: t["rows"].append(t["cur"])
            t["cur"] = []; continue
        if s.startswith("!") or s.startswith("|"):
            if t["cur"] is None: t["cur"] = []
            cells = _cell_split(s[1:], s.startswith("!"))
            t["cur"].extend(cells); t["last"] = cells[-1]
            continue
        # continuation line
        if t["last"] is not None:
            t["last"].raw += "\n" + ln
    return out

def _expand(rows):
    grid = []
    pending = {}  # col -> [cell, remaining]
    for r in rows:
        if not r: continue
        new = []
        ci = 0
        it = iter(r)
        col = 0
        cells = list(r)
        k = 0
        while k < len(cells) or any(c >= col for c in pending):
            if col in pending:
                c, rem = pending[col]
                new.append(c)
                if rem - 1 <= 0: del pending[col]
                else: pending[col] = [c, rem - 1]
                col += 1; continue
            if k >= len(cells):
                if not any(c > col for c in pending): break
                col += 1; new.append(Cell("", False)); continue
            c = cells[k]; k += 1
            for j in range(c.colspan):
                new.append(c)
                if c.rowspan > 1: pending[col] = [c, c.rowspan - 1]
                col += 1
        grid.append(new)
    return grid

def parse_date(s, year=None):
    """Return YYYY-MM-DD / YYYY-MM or None from a messy date string."""
    if not s: return None
    m = re.search(r"DATE\((\d{4})/(\d{1,2}|\w+)/(\d{1,2})", s)
    if m:
        mo = m.group(2)
        mo = int(mo) if mo.isdigit() else MONTHS.get(mo.lower()) or MON3.get(mo.lower()[:3])
        if mo: return "%s-%02d-%02d" % (m.group(1), mo, int(m.group(3)))
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m: return m.group(0)
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:\s*[-–/&,]\s*\d{1,2})?(?:st|nd|rd|th)?,?\s*(\d{4})?", s)
    if m:
        mo = MONTHS.get(m.group(1).lower()) or MON3.get(m.group(1).lower()[:4]) or MON3.get(m.group(1).lower()[:3])
        y = m.group(3) or year
        if mo and y: return "%s-%02d-%02d" % (y, mo, int(m.group(2)))
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s*(\d{4})?", s)
    if m:
        mo = MONTHS.get(m.group(2).lower()) or MON3.get(m.group(2).lower()[:3])
        y = m.group(3) or year
        if mo and y: return "%s-%02d-%02d" % (y, mo, int(m.group(1)))
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", s)
    if m and year:
        return "%s-%02d-%02d" % (year, int(m.group(1)), int(m.group(2)))
    return None

US_STATES = {"Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY","District of Columbia":"DC"}
CA_PROV = {"Ontario":"ON","Quebec":"QC","Québec":"QC","British Columbia":"BC","Alberta":"AB","Manitoba":"MB","Saskatchewan":"SK","Nova Scotia":"NS","New Brunswick":"NB","Prince Edward Island":"PE","Newfoundland and Labrador":"NL"}
ABBR = {**US_STATES, **CA_PROV}
CODES = set(ABBR.values())
AP = {"Ala.":"AL","Ariz.":"AZ","Ark.":"AR","Calif.":"CA","Colo.":"CO","Conn.":"CT","Del.":"DE","Fla.":"FL","Ga.":"GA","Ill.":"IL","Ind.":"IN","Kan.":"KS","Kans.":"KS","Ky.":"KY","La.":"LA","Md.":"MD","Mass.":"MA","Mich.":"MI","Minn.":"MN","Miss.":"MS","Mo.":"MO","Mont.":"MT","Neb.":"NE","Nebr.":"NE","Nev.":"NV","N.H.":"NH","N.J.":"NJ","N.M.":"NM","N.Y.":"NY","N.C.":"NC","N.D.":"ND","Okla.":"OK","Ore.":"OR","Pa.":"PA","Penn.":"PA","R.I.":"RI","S.C.":"SC","S.D.":"SD","Tenn.":"TN","Tex.":"TX","Va.":"VA","Vt.":"VT","Wash.":"WA","W.Va.":"WV","W. Va.":"WV","Wis.":"WI","Wisc.":"WI","Wyo.":"WY","Ont.":"ON","Que.":"QC","Man.":"MB","Alta.":"AB","Sask.":"SK","B.C.":"BC"}

def state_code(s):
    if not s: return None
    s = s.strip().strip(".,")
    if s.upper() in CODES and len(s) == 2: return s.upper()
    if s in ABBR: return ABBR[s]
    if s + "." in AP: return AP[s + "."]
    if s in AP: return AP[s]
    return None

def split_city_state(s):
    """'Knoxville, Iowa' -> ('Knoxville','IA')"""
    if not s: return (None, None)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 2:
        st = state_code(parts[-1])
        if st: return (", ".join(parts[:-1]), st)
    st = state_code(s)
    if st: return (None, st)
    m = re.match(r"^(.*?)\s+([A-Z]{2})$", s)
    if m and m.group(2) in CODES: return (m.group(1), m.group(2))
    return (s, None)
