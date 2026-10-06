"""Minimal wikitext helpers: strip refs, parse wikitables into grids, cell -> (text, links)."""
import re

REF_RE = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def clean_source(t):
    t = COMMENT_RE.sub("", t)
    t = REF_RE.sub("", t)
    t = re.sub(r"\{\{\s*(efn|refn|r|sfn|cn|citation needed|clarify|when|which)\b(?:[^{}]|\{\{[^{}]*\}\})*\}\}", "", t, flags=re.I)
    return t


def split_top(s, sep):
    """Split s on sep, ignoring occurrences inside [[..]] and {{..}}."""
    out, cur, i, dl, dt = [], [], 0, 0, 0
    n, L = len(s), len(sep)
    while i < n:
        if s.startswith("[[", i):
            dl += 1; cur.append("[["); i += 2; continue
        if s.startswith("]]", i) and dl:
            dl -= 1; cur.append("]]"); i += 2; continue
        if s.startswith("{{", i):
            dt += 1; cur.append("{{"); i += 2; continue
        if s.startswith("}}", i) and dt:
            dt -= 1; cur.append("}}"); i += 2; continue
        if dl == 0 and dt == 0 and s.startswith(sep, i):
            out.append("".join(cur)); cur = []; i += L; continue
        cur.append(s[i]); i += 1
    out.append("".join(cur))
    return out


def find_tables(text):
    """Return [(start_offset, table_text)] for every table (nested ones too), in start order.
    Outer tables have their nested tables removed."""
    lines = text.split("\n")
    stack, res, off = [], [], 0
    for ln in lines:
        s = ln.lstrip()
        if s.startswith("{|"):
            for st in stack:
                st[2] += 1
            stack.append([off, [], 0])
        for st in stack:
            if st[2] == 0 or (st is stack[-1]):
                st[1].append(ln)
        if s.startswith("|}") and stack:
            st = stack.pop()
            res.append((st[0], "\n".join(st[1])))
            for o in stack:
                o[2] -= 1
        off += len(ln) + 1
    res.sort(key=lambda x: x[0])
    return res


def _attr_split(cell):
    parts = split_top(cell, "|")
    if len(parts) >= 2 and not parts[0].strip().startswith(("[[", "{{", "'")) and (re.search(r"\w+\s*=", parts[0]) or re.fullmatch(r"\s*(nowrap|scope=\w+)\s*", parts[0], re.I)):
        return parts[0], "|".join(parts[1:])
    if len(parts) >= 2 and parts[0].strip() == "":
        return "", "|".join(parts[1:])
    return "", cell


def _span(attr, name):
    m = re.search(name + r'\s*=\s*"?\s*(\d+)', attr, re.I)
    return int(m.group(1)) if m else 1


def parse_table(tt):
    """Return list of rows; each row a list of dicts {raw, header, attr}; spans expanded."""
    body = tt.split("\n")[1:]
    rows, cur, caption = [], None, None
    pending = None  # last cell to append continuation lines to
    for ln in body:
        s = ln.strip()
        if s.startswith("|}"):
            break
        if s.startswith("|+"):
            caption = s[2:]; continue
        if s.startswith("|-"):
            if cur is not None:
                rows.append(cur)
            cur = []; pending = None; continue
        if s.startswith("!") or s.startswith("|"):
            if cur is None:
                cur = []
            header = s.startswith("!")
            content = s[1:]
            seps = "!!" if header else "||"
            pieces = split_top(content, seps)
            if header and len(pieces) == 1:
                pieces = split_top(content, "||")
            for p in pieces:
                attr, raw = _attr_split(p)
                c = {"raw": raw.strip(), "header": header, "attr": attr}
                cur.append(c); pending = c
            continue
        if pending is not None:
            pending["raw"] += "\n" + ln
    if cur:
        rows.append(cur)
    # expand spans
    grid, carry = [], {}
    for r in rows:
        out, ci, cells = [], 0, list(r)
        while cells or any(k >= ci for k in carry):
            if ci in carry:
                c, left = carry[ci]
                out.append(dict(c, spanned=True))
                if left - 1 > 0:
                    carry[ci] = (c, left - 1)
                else:
                    del carry[ci]
                ci += 1; continue
            if not cells:
                if any(k > ci for k in carry):
                    out.append({"raw": "", "header": False, "attr": "", "spanned": True}); ci += 1; continue
                break
            c = cells.pop(0)
            rs, cs = _span(c["attr"], "rowspan"), _span(c["attr"], "colspan")
            for k in range(cs):
                cc = c if k == 0 else dict(c, spanned=True)
                out.append(cc)
                if rs > 1:
                    carry[ci] = (c, rs - 1)
                ci += 1
        grid.append(out)
    return grid, caption


LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")


def _tpl_name_args(inner):
    parts = split_top(inner, "|")
    name = parts[0].strip()
    args, named = [], {}
    for p in parts[1:]:
        m = re.match(r"\s*([\w ]+?)\s*=(.*)$", p, re.S)
        if m and not p.strip().startswith("[["):
            named[m.group(1).strip().lower()] = m.group(2).strip()
        else:
            args.append(p.strip())
    return name, args, named


def expand_templates(s, links):
    """Replace templates with text; record links found in templates."""
    for _ in range(6):
        m = None
        # innermost templates first
        it = list(re.finditer(r"\{\{((?:[^{}]|\{(?!\{)|\}(?!\}))*)\}\}", s))
        if not it:
            break
        out, last = [], 0
        for m in it:
            out.append(s[last:m.start()])
            out.append(_tpl(m.group(1), links))
            last = m.end()
        out.append(s[last:])
        s = "".join(out)
    return s


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def _tpl(inner, links):
    name, args, named = _tpl_name_args(inner)
    ln = name.lower().replace("_", " ").strip()
    if ln in ("flagicon", "flag icon", "flagdeco", "flagu", "nbsp", "-", "!", "efn", "refn", "ref", "hs", "sortkey", "dagger", "double-dagger", "*", "dot", "nowrap begin", "nowrap end", "cite web", "cite news", "dash", "rsr"):
        return {"nbsp": " ", "!": "|", "dash": "–"}.get(ln, "")
    if ln in ("flag", "flagcountry"):
        return args[0] if args else ""
    if ln in ("sortname",):
        first = args[0] if args else ""
        last = args[1] if len(args) > 1 else ""
        nm = (first + " " + last).strip()
        tgt = args[2] if len(args) > 2 and args[2] and args[2] not in ("nolink",) else (None if (len(args) > 2 and args[2] == "nolink") or named.get("nolink") else nm)
        if named.get("nolink"):
            tgt = None
        if tgt:
            return f"[[{tgt}|{nm}]]"
        return nm
    if ln in ("dts", "date table sorting", "dtsort", "start date", "birth date"):
        a = [x for x in args if x]
        try:
            if len(a) >= 3 and a[0].isdigit():
                return f"{MONTHS[int(a[1]) - 1]} {int(a[2])}, {a[0]}" if a[1].isdigit() else f"{a[1]} {a[2]}, {a[0]}"
        except Exception:
            pass
        return " ".join(a)
    if ln in ("sort", "sortname2", "hsort", "ntsh", "nts"):
        return args[-1] if args else ""
    if ln in ("abbr", "tooltip", "abbrlink", "small", "nowrap", "nobr", "big", "center", "lang", "smaller", "larger", "fontcolor", "color", "tt", "em", "strong", "nobold", "noitalic", "ubl", "plainlist", "hlist", "flatlist", "unbulleted list", "plain list", "vertical header", "verth", "align", "linktext"):
        if ln in ("fontcolor", "color"):
            return args[-1] if args else ""
        if ln in ("ubl", "unbulleted list", "hlist", "plainlist", "plain list", "flatlist"):
            return "<br>".join(args)
        if ln in ("abbrlink",):
            return f"[[{args[1]}|{args[0]}]]" if len(args) > 1 else (args[0] if args else "")
        return args[0] if args else (named.get("1", ""))
    if ln in ("ill", "interlanguage link", "illm"):
        t = named.get("lt") or (args[0] if args else "")
        return f"[[{args[0]}|{t}]]" if args else ""
    if ln in ("ntsp",):
        return args[0] if args else ""
    if ln.startswith("flagathlete") or ln == "flagicon image":
        return args[0] if args else ""
    if ln in ("chevrolet", "ford", "toyota", "dodge", "pontiac"):
        return name
    if ln in ("yes", "no", "n/a", "na", "tba", "tbd"):
        return {"tba": "TBA", "tbd": "TBD"}.get(ln, args[0] if args else "")
    if ln in ("convert", "cvt"):
        return " ".join(args[:2])
    if ln == "anchor":
        return ""
    if ln in ("stc", "nascar", "sup"):
        return args[0] if args else ""
    return ""


def cell_text(raw):
    """Return (plain_text, [link_targets_in_order], [(target, text)])."""
    links = []
    s = raw
    s = expand_templates(s, links)
    s = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", "", s, flags=re.I)
    pairs = []

    def rep(m):
        tgt = m.group(1).strip()
        txt = m.group(2) if m.group(2) is not None else tgt
        if tgt.startswith(":"):
            tgt = tgt[1:]
        tgt = tgt.split("#")[0].strip()
        pairs.append((tgt, re.sub(r"'{2,}", "", txt).strip()))
        return txt
    s = LINK_RE.sub(rep, s)
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = re.sub(r"<sup[^>]*>.*?</sup>", "", s, flags=re.I | re.S)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"'{2,}", "", s)
    s = s.replace("&nbsp;", " ").replace("&ndash;", "–").replace("&amp;", "&")
    lines = [re.sub(r"\s+", " ", x).strip() for x in s.split("\n")]
    text = "\n".join(x for x in lines if x)
    return text, [p[0] for p in pairs], pairs


def headings(text):
    """Return list of (offset, level, title)."""
    return [(m.start(), len(m.group(1)), cell_text(m.group(2))[0]) for m in re.finditer(r"^(={2,6})\s*(.*?)\s*\1\s*$", text, re.M)]


def heading_before(hs, off):
    path = {}
    for o, lvl, t in hs:
        if o > off:
            break
        path[lvl] = t
        for k in list(path):
            if k > lvl:
                del path[k]
    return [path[k] for k in sorted(path)]


def year_lists(text):
    """Bullet list items starting with a year: [(heading_path, year, text, pairs)]."""
    hs = headings(text)
    out, off = [], 0
    for ln in text.split("\n"):
        m = re.match(r"^[*#:;]+\s*'*\s*((?:19|20)\d\d)\s*'*\s*[:\-–—]?\s*(.*)$", ln)
        if m:
            txt, _, pairs = cell_text(m.group(2))
            out.append((heading_before(hs, off), int(m.group(1)), txt, pairs))
        off += len(ln) + 1
    return out
