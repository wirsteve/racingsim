#!/usr/bin/env python3
"""Scrape American open-wheel racing history (CART/Champ Car, IRL/IndyCar, Indy Lights, Pro Mazda, USF2000)
from Wikipedia wikitext + Wikidata bios. Re-runnable: all HTTP responses are cached under ./cache_openwheel.
Usage: python3 scrape_openwheel.py [--only cart_champcar irl_indycar ...] [--skip-bios]"""

# ############################## wfetch.py
import os, re, json, time, hashlib, urllib.parse, requests
H = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(H, 'cache_openwheel')
os.makedirs(CACHE, exist_ok=True)
S = requests.Session(); S.headers['User-Agent'] = 'racingsim-personal/1.0'
_api_ok = [True]
def _get(url, params=None, tries=4):
    for i in range(tries):
        time.sleep(0.2)
        try:
            r = S.get(url, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(2 + i * 3); continue
        if r.status_code == 429:
            ra = int(r.headers.get('retry-after', '5') or 5)
            time.sleep(min(ra, 30)); continue
        return r
    return None
def _ck(kind, key):
    return os.path.join(CACHE, kind + '_' + hashlib.md5(key.encode()).hexdigest() + '.json')
def raw(title, follow=True, depth=0):
    """Return (resolved_title, wikitext) or (None, None)."""
    title = title.replace('_', ' ').strip()
    fn = _ck('raw', title)
    if os.path.exists(fn):
        d = json.load(open(fn))
    else:
        d = None
        if _api_ok[0]:
            r = _get('https://en.wikipedia.org/w/api.php', {'action': 'parse', 'page': title, 'prop': 'wikitext', 'format': 'json', 'redirects': 1}, tries=1)
            if r is not None and r.status_code == 200:
                j = r.json()
                if 'parse' in j:
                    d = {'title': j['parse']['title'], 'text': j['parse']['wikitext']['*']}
                else:
                    d = {'title': None, 'text': None}
            else:
                _api_ok[0] = False
        if d is None:
            r = _get('https://en.wikipedia.org/w/index.php', {'title': title, 'action': 'raw'})
            if r is None:
                return None, None  # transient; don't cache
            if r.status_code == 404:
                d = {'title': None, 'text': None}
            elif r.status_code == 200:
                d = {'title': title, 'text': r.text}
            else:
                return None, None
        json.dump(d, open(fn, 'w'))
    if d['text'] and follow and depth < 3:
        m = re.match(r'\s*#REDIRECT\s*\[\[([^\]|#]+)', d['text'], re.I)
        if m:
            return raw(m.group(1), True, depth + 1)
    return d['title'], d['text']
def resolve(title):
    t, _ = raw(title)
    return t
def search(q, limit=10):
    fn = _ck('search', q)
    if os.path.exists(fn): return json.load(open(fn))
    r = _get('https://en.wikipedia.org/w/index.php', {'search': q, 'title': 'Special:Search', 'profile': 'default', 'fulltext': 1, 'limit': limit, 'ns0': 1})
    if r is None: return []
    res = re.findall(r'class="mw-search-result-heading"><a href="/wiki/([^"]+)"', r.text)
    res = [urllib.parse.unquote(x).replace('_', ' ') for x in res]
    json.dump(res, open(fn, 'w')); return res
def entity_by_title(title):
    title = title.replace('_', ' ')
    fn = _ck('ent_t', title)
    if os.path.exists(fn): return json.load(open(fn))
    r = _get('https://www.wikidata.org/wiki/Special:EntityData', {'site': 'enwiki', 'title': title, 'format': 'json'})
    if r is None: return None
    out = None
    if r.status_code == 200:
        try:
            ents = r.json()['entities']; out = list(ents.values())[0]
            out = slim(out)
        except Exception: out = None
    json.dump(out, open(fn, 'w')); return out
def entity(qid):
    fn = _ck('ent', qid)
    if os.path.exists(fn): return json.load(open(fn))
    r = _get('https://www.wikidata.org/wiki/Special:EntityData/%s.json' % qid)
    if r is None: return None
    out = None
    if r.status_code == 200:
        try: out = slim(r.json()['entities'][qid] if qid in r.json()['entities'] else list(r.json()['entities'].values())[0])
        except Exception: out = None
    json.dump(out, open(fn, 'w')); return out
KEEP = {'P569', 'P19', 'P131', 'P17', 'P298', 'P31', 'P27', 'P300', 'P1813', 'P5086'}
def slim(e):
    cl = {}
    for p, sts in e.get('claims', {}).items():
        if p not in KEEP: continue
        vals = []
        for st in sts:
            dv = st.get('mainsnak', {}).get('datavalue')
            if not dv: continue
            v = dv['value']
            if isinstance(v, dict) and 'id' in v: v = v['id']
            elif isinstance(v, dict) and 'time' in v: v = {'time': v['time'], 'precision': v.get('precision')}
            vals.append({'v': v, 'rank': st.get('rank')})
        cl[p] = vals
    lab = e.get('labels', {}).get('en', {}).get('value')
    return {'id': e.get('id'), 'label': lab, 'claims': cl, 'sitelink': e.get('sitelinks', {}).get('enwiki', {}).get('title')}

# ############################## wikitable.py
import re

# ---------------------------------------------------------------- preprocessing
def _strip_balanced_templates(text, names):
    """Remove {{name ...}} templates (balanced braces) for names in `names` (lowercase)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith('{{', i):
            m = re.match(r'\{\{\s*([^{}|\n]+?)\s*(\||\}\})', text[i:])
            if m and m.group(1).strip().lower() in names:
                depth = 0
                j = i
                while j < n:
                    if text.startswith('{{', j):
                        depth += 1; j += 2; continue
                    if text.startswith('}}', j):
                        depth -= 1; j += 2
                        if depth == 0:
                            break
                        continue
                    j += 1
                i = j
                continue
        out.append(text[i])
        i += 1
    return ''.join(out)

NOTE_TEMPLATES = {'refn', 'efn', 'sfn', 'sfnm', 'ref', 'note', 'cn', 'citation needed', 'r', 'efn-ua', 'efn-lr',
                  'rp', 'harvnb', 'notetag', 'nb', 'clarify', 'when', 'dead link', 'webarchive', 'cbignore',
                  'better source needed', 'update after', 'as of', 'failed verification', 'verify source', 'nbsp'}


def preprocess(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'<ref[^>/]*/>', '', text)
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.S)
    text = _strip_balanced_templates(text, NOTE_TEMPLATES)
    text = re.sub(r'<br\s*/?\s*>', '§BR§', text, flags=re.I)
    text = re.sub(r'</?(span|div|center|nowiki)[^>]*>', '', text, flags=re.I)
    # collapse newlines inside templates / links so they don't break table line structure
    out = []
    depth_t = depth_l = 0
    i, n = 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == '{{':
            depth_t += 1; out.append(two); i += 2; continue
        if two == '}}' and depth_t:
            depth_t -= 1; out.append(two); i += 2; continue
        if two == '[[':
            depth_l += 1; out.append(two); i += 2; continue
        if two == ']]' and depth_l:
            depth_l -= 1; out.append(two); i += 2; continue
        c = text[i]
        if c == '\n' and (depth_t or depth_l):
            # stop runaway (unbalanced) at blank-line/table boundary
            nxt = text[i + 1:i + 3]
            if nxt.startswith('|}') or nxt.startswith('{|') or nxt.startswith('\n') or nxt.startswith('|-'):
                depth_t = depth_l = 0
                out.append(c); i += 1; continue
            out.append(' '); i += 1; continue
        out.append(c); i += 1
    return ''.join(out)


# ---------------------------------------------------------------- splitting helpers
def _split_top(s, sep):
    """Split s on sep occurring outside [[..]] and {{..}}."""
    parts, buf = [], []
    dt = dl = 0
    i, n, L = 0, len(s), len(sep)
    while i < n:
        two = s[i:i + 2]
        if two == '{{': dt += 1; buf.append(two); i += 2; continue
        if two == '}}' and dt: dt -= 1; buf.append(two); i += 2; continue
        if two == '[[': dl += 1; buf.append(two); i += 2; continue
        if two == ']]' and dl: dl -= 1; buf.append(two); i += 2; continue
        if dt == 0 and dl == 0 and s.startswith(sep, i):
            parts.append(''.join(buf)); buf = []; i += L; continue
        buf.append(s[i]); i += 1
    parts.append(''.join(buf))
    return parts


ATTR_RE = re.compile(r'^\s*([A-Za-z][\w:-]*\s*(=\s*("[^"]*"|\'[^\']*\'|[^\s|"\']+))?\s*)+$')


def _split_attr(cell):
    """'attrs | content' -> (attrs, content)."""
    dt = dl = 0
    i, n = 0, len(cell)
    while i < n:
        two = cell[i:i + 2]
        if two == '{{': dt += 1; i += 2; continue
        if two == '}}' and dt: dt -= 1; i += 2; continue
        if two == '[[': dl += 1; i += 2; continue
        if two == ']]' and dl: dl -= 1; i += 2; continue
        if cell[i] == '|' and dt == 0 and dl == 0:
            before = cell[:i]
            if before.strip() == '' or (ATTR_RE.match(before) and '=' in before) or re.match(r'^\s*(valign|align|nowrap|style|rowspan|colspan|width|bgcolor|class|scope|data-sort-value)\b', before, re.I):
                return before, cell[i + 1:]
            return '', cell
        i += 1
    return '', cell


def _span(attrs, name):
    m = re.search(name + r'\s*=\s*["\']?\s*(\d+)', attrs, re.I)
    if m:
        try:
            return max(1, min(int(m.group(1)), 200))
        except ValueError:
            pass
    return 1


class Cell:
    __slots__ = ('raw', 'header', 'attrs', 'rs', 'cs', 'origin')

    def __init__(self, raw, header, attrs):
        self.raw = raw.strip()
        self.header = header
        self.attrs = attrs
        self.rs = _span(attrs, 'rowspan')
        self.cs = _span(attrs, 'colspan')
        self.origin = True

    def __repr__(self):
        return ('!' if self.header else '|') + self.raw[:40]


class Table:
    def __init__(self, section, subsection, start):
        self.section = section
        self.subsection = subsection
        self.start = start
        self.rows = []      # list of list of Cell
        self.caption = ''
        self.grid = None

    def build(self):
        grid = []
        pending = {}  # col -> (cell, remaining)
        for row in self.rows:
            if not row and not pending:
                continue
            g = []
            col = 0
            cells = list(row)
            while cells or any(c >= col for c in pending):
                if col in pending:
                    cell, rem = pending[col]
                    g.append(cell)
                    if rem <= 1:
                        del pending[col]
                    else:
                        pending[col] = (cell, rem - 1)
                    col += 1
                    continue
                if not cells:
                    if any(c > col for c in pending):
                        g.append(None); col += 1; continue
                    break
                cell = cells.pop(0)
                for k in range(cell.cs):
                    g.append(cell)
                    if cell.rs > 1:
                        pending[col] = (cell, cell.rs - 1)
                    col += 1
            if g:
                grid.append(g)
        self.grid = grid
        return grid

    # header rows = leading rows consisting only of header cells
    def header_rows(self):
        hr = []
        for g in self.grid:
            if g and all(c is not None and c.header for c in g):
                hr.append(g)
            else:
                break
        if not hr and self.grid:
            g = self.grid[0]
            raws = [c.raw.strip() for c in g if c is not None and c.raw.strip()]
            if len(raws) >= 3 and sum(1 for x in raws if x.startswith("'''")) >= 3 and \
                    re.search(r"(place|pos|driver|name)", ' '.join(raws), re.I):
                for c in g:
                    if c is not None:
                        c.header = True
                hr.append(g)
        return hr

    def headers(self):
        hr = self.header_rows()
        if not hr:
            return []
        width = max(len(g) for g in self.grid) if self.grid else 0
        labels = []
        for j in range(width):
            parts = []
            for g in hr:
                if j < len(g) and g[j] is not None:
                    t = plain(g[j].raw).strip().lower()
                    if t and (not parts or parts[-1] != t):
                        parts.append(t)
            labels.append(' '.join(parts))
        return labels

    def body(self):
        n = len(self.header_rows())
        return [g for g in self.grid[n:] if not all(c is not None and c.header for c in g)]


def tables(text):
    """Return list of Table (all nesting levels), with grids built."""
    text = preprocess(text)
    lines = text.split('\n')
    out = []
    stack = []
    section = subsection = ''
    for ln, line in enumerate(lines):
        s = line.strip()
        if not stack:
            m = re.match(r'^(=+)\s*(.*?)\s*\1\s*$', s)
            if m:
                if len(m.group(1)) == 2:
                    section = m.group(2); subsection = ''
                else:
                    subsection = m.group(2)
                continue
        if s.startswith('{|'):
            t = Table(section, subsection, ln)
            stack.append({'t': t, 'row': None, 'last': None})
            continue
        if not stack:
            continue
        st = stack[-1]
        t = st['t']
        if s.startswith('|}'):
            if st['row'] is not None:
                t.rows.append(st['row'])
            t.build()
            out.append(t)
            stack.pop()
            if stack and stack[-1]['last'] is not None:
                stack[-1]['last'].raw += ' §TABLE§ '
            continue
        if s.startswith('|+'):
            t.caption = s[2:]
            continue
        if s.startswith('|-'):
            if st['row'] is not None:
                t.rows.append(st['row'])
            st['row'] = []
            st['last'] = None
            continue
        if s.startswith('!') or s.startswith('|'):
            header = s.startswith('!')
            body = s[1:]
            if st['row'] is None:
                st['row'] = []
            pieces = _split_top(body, '||')
            if header:
                pp = []
                for p in pieces:
                    pp.extend(_split_top(p, '!!'))
                pieces = pp
            for p in pieces:
                a, c = _split_attr(p)
                cell = Cell(c, header, a)
                st['row'].append(cell)
                st['last'] = cell
            continue
        # continuation line
        if st['last'] is not None:
            st['last'].raw += '\n' + line
        elif s:
            t.caption += ' ' + s
    return out


# ---------------------------------------------------------------- text helpers
LINK_RE = re.compile(r'\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]')


def links(raw):
    """[(target, label)] excluding files/categories/flags."""
    res = []
    for m in LINK_RE.finditer(raw or ''):
        tgt = m.group(1).strip()
        if re.match(r'^(file|image|category|media|wikt|wiktionary|w):', tgt, re.I) or tgt.startswith(':'):
            continue
        lab = m.group(2)
        if lab is None:
            lab = tgt
        lab = plain(lab)
        tgt = tgt.split('#')[0].strip()
        if not tgt:
            continue
        res.append((tgt[0].upper() + tgt[1:], lab))
    return res


FLAG_RE = re.compile(r'\{\{\s*(?:flagicon|flag icon|flagu|flag)\s*\|\s*([^|}]+)', re.I)


def flags(raw):
    res = [m.group(1).strip() for m in FLAG_RE.finditer(raw or '')]
    for m in re.finditer(r'\{\{\s*([A-Z]{3})\s*\}\}', raw or ''):
        res.append(m.group(1))
    return res


def _tmpl_repl(m):
    inner = m.group(1)
    parts = [p.strip() for p in inner.split('|')]
    name = parts[0].strip().lower().replace('_', ' ')
    params = [p for p in parts[1:] if not re.match(r'^[\w -]+=', p)]
    named = dict(p.split('=', 1) for p in parts[1:] if re.match(r'^[\w -]+=', p))
    if name in ('flagicon', 'flag icon', 'flagu', 'color box', 'colorbox', 'legend', 'motorsport class', 'tire', 'ntsh',
                'hs', 'hidden sort key', 'sup', 'convert', 'cvt', 'abbr link', 'small caps', 'anchor', 'sfn', 'efn', 'refn',
                'dagger', 'double-dagger', 'ref', 'sortkey', 'hiddensort'):
        return ''
    if re.match(r'^[a-z]{3}$', name) and name.upper() == parts[0].strip():
        return ''
    if name in ('flag', 'flagcountry'):
        return params[0] if params else ''
    if name in ('tooltip', 'abbr', 'abbrlink', 'nowrap', 'nobr', 'small', 'big', 'center', 'bold', 'nowrap begin',
                'resize', 'smaller', 'larger', 'lang', 'nobold', 'noitalic', 'plainlist', 'longitem', 'nobreak', 'text', 'nbh', 'proper name', 'sic'):
        if name == 'lang' and len(params) >= 2:
            return params[1]
        if name == 'resize' and len(params) >= 2:
            return params[1]
        return params[0] if params else named.get('1', '')
    if name in ('nts', 'number table sorting', 'ntsc', 'sort', 'sorttext', 'sortname'):
        if name == 'sortname' and len(params) >= 2:
            return params[0] + ' ' + params[1]
        if name in ('sort', 'sorttext') and len(params) >= 2:
            return params[1]
        return params[0] if params else ''
    if name in ('dts', 'start date', 'date', 'birth date', 'dtsl'):
        nums = [p for p in params if re.match(r'^\d+$', p)]
        if len(nums) >= 3:
            return '%04d-%02d-%02d' % (int(nums[0]), int(nums[1]), int(nums[2]))
        return ' '.join(params)
    if name in ('ubl', 'unbulleted list', 'plainlist', 'flatlist', 'hlist', 'bulleted list'):
        return '§BR§'.join(params)
    if name in ('ill', 'interlanguage link'):
        return params[0] if params else ''
    if name in ('dash', 'ndash', '–', 'snd', 'spaced ndash'):
        return '–'
    if name in ('mdash', '—'):
        return '—'
    if name in ('em', 'strong', 'code', 'var'):
        return params[0] if params else ''
    if name in ('strikethrough', 'strike', 's'):
        return params[0] if params else ''
    if name in ('n/a', 'na'):
        return '—'
    return ''


def plain(raw, keep_br=False):
    if raw is None:
        return ''
    s = raw
    s = LINK_RE.sub(lambda m: '[[' + m.group(1) + ('\x01' + m.group(2) if m.group(2) is not None else '') + ']]', s)
    for _ in range(8):
        s2 = re.sub(r'\{\{([^{}]*)\}\}', _tmpl_repl, s)
        if s2 == s:
            break
        s = s2
    s = re.sub(r'\{\{|\}\}', '', s)
    s = re.sub(r'\[\[([^\[\]\x01]+)\x01([^\[\]]*)\]\]', r'\2', s)
    s = re.sub(r'\[\[([^\[\]]+)\]\]', lambda m: '' if re.match(r'^(file|image|category):', m.group(1), re.I) else m.group(1), s)
    s = re.sub(r'\[https?://\S+\s*([^\]]*)\]', r'\1', s)
    s = re.sub(r'<sup[^>]*>.*?</sup>', '', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace("'''", '').replace("''", '')
    s = s.replace('&nbsp;', ' ').replace('&ndash;', '–').replace('&mdash;', '—').replace('&amp;', '&')
    s = s.replace('§TABLE§', ' ')
    if keep_br:
        s = s.replace('§BR§', '\n')
    else:
        s = s.replace('§BR§', ' ')
    s = re.sub(r'[ \t ]+', ' ', s)
    return s.strip()


def split_br(raw):
    """Split cell raw on <br> markers / newlines."""
    parts = re.split(r'§BR§|\n', raw or '')
    return [p for p in parts if plain(p).strip() or links(p)]

# ############################## geo.py
import re

US_STATES = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO',
    'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
    'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
    'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
    'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
    'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC', 'Washington, D.C.': 'DC', 'D.C.': 'DC',
}
CA_PROV = {
    'Ontario': 'ON', 'Quebec': 'QC', 'Québec': 'QC', 'British Columbia': 'BC', 'Alberta': 'AB',
    'Manitoba': 'MB', 'Saskatchewan': 'SK', 'Nova Scotia': 'NS', 'New Brunswick': 'NB',
    'Newfoundland and Labrador': 'NL', 'Prince Edward Island': 'PE', 'Yukon': 'YT',
    'Northwest Territories': 'NT', 'Nunavut': 'NU',
}
US_ABBR = set(US_STATES.values())
CA_ABBR = set(CA_PROV.values())

ISO3 = {
    'United States': 'USA', 'USA': 'USA', 'US': 'USA', 'U.S.': 'USA', 'United States of America': 'USA',
    'Canada': 'CAN', 'Brazil': 'BRA', 'Mexico': 'MEX', 'Japan': 'JPN', 'Australia': 'AUS', 'Germany': 'DEU',
    'West Germany': 'DEU', 'United Kingdom': 'GBR', 'Great Britain': 'GBR', 'England': 'GBR', 'Scotland': 'GBR',
    'Wales': 'GBR', 'Northern Ireland': 'GBR', 'UK': 'GBR', 'Netherlands': 'NLD', 'Belgium': 'BEL', 'France': 'FRA',
    'Italy': 'ITA', 'Spain': 'ESP', 'Portugal': 'PRT', 'Switzerland': 'CHE', 'Austria': 'AUT', 'Sweden': 'SWE',
    'Norway': 'NOR', 'Denmark': 'DNK', 'Finland': 'FIN', 'Ireland': 'IRL', 'Republic of Ireland': 'IRL',
    'Colombia': 'COL', 'Venezuela': 'VEN', 'Argentina': 'ARG', 'Chile': 'CHL', 'Uruguay': 'URY',
    'New Zealand': 'NZL', 'South Africa': 'ZAF', 'China': 'CHN', 'Hong Kong': 'HKG', 'Malaysia': 'MYS',
    'Thailand': 'THA', 'India': 'IND', 'Israel': 'ISR', 'Russia': 'RUS', 'Czech Republic': 'CZE', 'Czechia': 'CZE',
    'Hungary': 'HUN', 'Poland': 'POL', 'Greece': 'GRC', 'Monaco': 'MCO', 'Puerto Rico': 'PRI', 'Peru': 'PER',
    'Ecuador': 'ECU', 'Guatemala': 'GTM', 'Costa Rica': 'CRI', 'Dominican Republic': 'DOM', 'Barbados': 'BRB',
    'Singapore': 'SGP', 'Indonesia': 'IDN', 'Philippines': 'PHL', 'South Korea': 'KOR', 'Korea': 'KOR',
    'Taiwan': 'TWN', 'United Arab Emirates': 'ARE', 'Saudi Arabia': 'SAU', 'Turkey': 'TUR', 'Estonia': 'EST',
    'Latvia': 'LVA', 'Lithuania': 'LTU', 'Ukraine': 'UKR', 'Belarus': 'BLR', 'Slovakia': 'SVK', 'Slovenia': 'SVN',
    'Croatia': 'HRV', 'Serbia': 'SRB', 'Romania': 'ROU', 'Bulgaria': 'BGR', 'Luxembourg': 'LUX',
    'Liechtenstein': 'LIE', 'Iceland': 'ISL', 'Paraguay': 'PRY', 'Bolivia': 'BOL', 'Panama': 'PAN',
    'El Salvador': 'SLV', 'Honduras': 'HND', 'Jamaica': 'JAM', 'Bahamas': 'BHS', 'Zimbabwe': 'ZWE',
    'Kenya': 'KEN', 'Egypt': 'EGY', 'Morocco': 'MAR', 'Lebanon': 'LBN', 'Qatar': 'QAT', 'Kuwait': 'KWT',
    'Bahrain': 'BHR', 'Iran': 'IRN', 'Pakistan': 'PAK', 'Vietnam': 'VNM', 'Cuba': 'CUB', 'Nicaragua': 'NIC',
    'Andorra': 'AND', 'San Marino': 'SMR', 'Cyprus': 'CYP', 'Malta': 'MLT', 'Kazakhstan': 'KAZ', 'Georgia': 'GEO',
    'Armenia': 'ARM', 'Trinidad and Tobago': 'TTO', 'Macau': 'MAC', 'Brasil': 'BRA',
}
IOC = {
    'GER': 'DEU', 'NED': 'NLD', 'SUI': 'CHE', 'DEN': 'DNK', 'POR': 'PRT', 'RSA': 'ZAF', 'CHI': 'CHL',
    'URU': 'URY', 'MAS': 'MYS', 'KSA': 'SAU', 'UAE': 'ARE', 'TPE': 'TWN', 'GRE': 'GRC', 'CRO': 'HRV',
    'SLO': 'SVN', 'PHI': 'PHL', 'INA': 'IDN', 'BUL': 'BGR', 'LAT': 'LVA', 'MON': 'MCO', 'PUR': 'PRI',
    'CRC': 'CRI', 'GUA': 'GTM', 'ESA': 'SLV', 'HON': 'HND', 'PAR': 'PRY', 'ZIM': 'ZWE', 'BAH': 'BHS',
    'BAR': 'BRB', 'ENG': 'GBR', 'SCO': 'GBR', 'WAL': 'GBR', 'NIR': 'GBR', 'UK': 'GBR', 'FRG': 'DEU',
    'IRI': 'IRN', 'VIE': 'VNM', 'LIB': 'LBN', 'KUW': 'KWT', 'BRN': 'BHR', 'MGL': 'MNG', 'NGR': 'NGA',
    'ALG': 'DZA', 'ANG': 'AGO', 'TRI': 'TTO', 'HAI': 'HTI', 'ISV': 'VIR', 'SRI': 'LKA', 'BAN': 'BGD',
    'MYA': 'MMR', 'CAM': 'KHM', 'NEP': 'NPL', 'OMA': 'OMN', 'YEM': 'YEM', 'SUD': 'SDN', 'TAN': 'TZA',
    'ZAM': 'ZMB', 'MAD': 'MDG', 'FIJ': 'FJI', 'SAM': 'WSM', 'TGA': 'TON', 'ARU': 'ABW', 'ANT': 'ATG',
    'SKN': 'KNA', 'LCA': 'LCA', 'VIN': 'VCT', 'GRN': 'GRD', 'BIZ': 'BLZ', 'SUR': 'SUR', 'GUY': 'GUY',
    'HK': 'HKG', 'US': 'USA',
}
VALID_ISO3 = set(ISO3.values()) | {'MNG', 'NGA', 'DZA', 'AGO', 'HTI', 'VIR', 'LKA', 'BGD', 'MMR', 'KHM', 'NPL',
                                   'OMN', 'SDN', 'TZA', 'ZMB', 'MDG', 'FJI', 'WSM', 'TON', 'ABW', 'ATG', 'KNA',
                                   'VCT', 'GRD', 'BLZ', 'SUR', 'GUY', 'CHE'}

# Non-US venue cities lacking a country indicator in some tables
CITY_HINTS = {
    'Toronto': ('ON', 'CAN'), 'Vancouver': ('BC', 'CAN'), 'Edmonton': ('AB', 'CAN'), 'Montreal': ('QC', 'CAN'),
    'Montréal': ('QC', 'CAN'), 'Mont-Tremblant': ('QC', 'CAN'), 'Trois-Rivières': ('QC', 'CAN'),
    'Calgary': ('AB', 'CAN'), 'Mosport': ('ON', 'CAN'), 'Bowmanville': ('ON', 'CAN'), 'Mexico City': (None, 'MEX'),
    'Monterrey': (None, 'MEX'), 'Surfers Paradise': (None, 'AUS'), 'Motegi': (None, 'JPN'),
    'Rio de Janeiro': (None, 'BRA'), 'São Paulo': (None, 'BRA'), 'Klettwitz': (None, 'DEU'),
    'Lausitz': (None, 'DEU'), 'Rockingham': (None, 'GBR'), 'Brands Hatch': (None, 'GBR'), 'Assen': (None, 'NLD'),
    'Zolder': (None, 'BEL'), 'Heusden-Zolder': (None, 'BEL'), 'Monterey': ('CA', 'USA'), 'Gold Coast': (None, 'AUS'),
    'Ensenada': (None, 'MEX'), 'Tamworth': (None, 'AUS'), 'Hamilton': ('ON', 'CAN'),
}
MONTHS = {m: i + 1 for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                           'september', 'october', 'november', 'december'])}


def flag_to_iso3(code):
    if not code:
        return None
    c = code.strip()
    if c in ISO3:
        return ISO3[c]
    u = c.upper()
    if u in IOC:
        return IOC[u]
    if len(u) == 3 and u.isalpha():
        return u
    return None


def parse_location(text, flag=None):
    """'Homestead, Florida' -> (city, state, country)."""
    t = re.sub(r'\s+', ' ', (text or '')).strip(' ,')
    parts = [p.strip() for p in re.split(r',|§BR§', t) if p.strip()]
    city = parts[0] if parts else None
    state = country = None
    for p in parts[1:]:
        pc = re.sub(r'\(.*?\)', '', p).strip()
        pc = re.sub(r'^State of ', '', pc)
        if pc in US_STATES or pc in US_ABBR:
            state = US_STATES.get(pc, pc); country = 'USA'
        elif pc in CA_PROV or pc in CA_ABBR:
            state = CA_PROV.get(pc, pc); country = 'CAN'
        elif pc in ISO3:
            country = ISO3[pc]
    if city and len(parts) == 1:
        if city in US_STATES and city not in ('New York', 'Washington'):
            state = US_STATES[city]; country = 'USA'; city = None
        elif city in CA_PROV:
            state = CA_PROV[city]; country = 'CAN'; city = None
        elif city in ISO3 and city not in ('Monaco', 'Singapore', 'Hong Kong', 'Macau'):
            country = ISO3[city]; city = None
    if flag:
        fc = flag_to_iso3(flag)
        if fc:
            if country and country != fc and state:
                pass
            else:
                country = fc
            if fc not in ('USA', 'CAN') and state and country == fc:
                state = None
    if not country and city:
        for k, (st, co) in CITY_HINTS.items():
            if k.lower() in t.lower():
                state = state or st; country = co
                break
    if not country and parts:
        country = 'USA'  # American-series default when no indicator
    return city, state, country


def parse_date(text, year):
    """Return (month, day, explicit_year) or None."""
    t = (text or '').strip()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', t)
    if m:
        return int(m.group(2)), int(m.group(3)), int(m.group(1))
    tl = t.lower()
    m = re.search(r'([a-z]{3,9})\.?\s+(\d{1,2})(?:[^\d]|$)', tl)
    if m:
        mon = next((v for k, v in MONTHS.items() if k.startswith(m.group(1)[:3])), None)
        if mon:
            y = re.search(r'\b(19\d\d|20\d\d)\b', tl)
            return mon, int(m.group(2)), int(y.group(1)) if y else None
    m = re.search(r'(\d{1,2})\s+([a-z]{3,9})', tl)
    if m:
        mon = next((v for k, v in MONTHS.items() if k.startswith(m.group(2)[:3])), None)
        if mon:
            y = re.search(r'\b(19\d\d|20\d\d)\b', tl)
            return mon, int(m.group(1)), int(y.group(1)) if y else None
    m = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', tl)
    if m:
        y = m.group(3)
        if y:
            y = int(y); y = y + 1900 if y < 100 and y > 50 else (y + 2000 if y < 100 else y)
        return int(m.group(1)), int(m.group(2)), y
    return None

# ############################## extract.py
import re


def col(headers, pats, excl=()):
    for p in pats:
        for i, h in enumerate(headers):
            if re.search(p, h) and not any(re.search(e, h) for e in excl):
                return i
    return None


def cell(row, i):
    if i is None or i >= len(row) or row[i] is None:
        return None
    return row[i]


def ctext(row, i, br=False):
    c = cell(row, i)
    return plain(c.raw, keep_br=br) if c else ''


NONPERSON = re.compile(r'(racing|motorsport|team|engine|indy v|chassis|^list of|season|series|championship|grand prix|'
                       r'speedway|raceway|circuit|cars$|tire|rookie|500$|^\d{4} )', re.I)


def person(raw):
    """Extract (name, wiki_target or None, flag_code or None) from a driver-cell fragment."""
    fl = flags(raw)
    lk = [l for l in links(raw) if not NONPERSON.search(l[0]) or re.search(r'\((racing|race car) driver\)|\(racer\)|\(driver\)', l[0], re.I)]
    txt = plain(raw)
    txt = re.sub(r'\s*\((R|r|ROY|Rookie|rookie|W)\)\s*', ' ', txt)
    txt = re.sub(r'[\*†‡#§]+', '', txt).strip(' ,;')
    if lk:
        tgt, lab = lk[0]
        name = re.sub(r'\s*\((R|ROY)\)', '', lab).strip() or txt
        return name, tgt.replace(' ', '_'), (fl[0] if fl else None)
    if not txt or txt in ('—', '-', '–', 'TBA', 'TBD'):
        return None, None, None
    return txt, None, (fl[0] if fl else None)


def int_list(text, total=None):
    t = (text or '').replace('—', '-').replace('–', '-').replace('−', '-')
    if re.search(r'\ball\b', t, re.I):
        return list(range(1, (total or 0) + 1)) if total else 'all'
    out = []
    for a, b in re.findall(r'(\d+)\s*(?:-\s*(\d+))?', t):
        a = int(a)
        if b:
            b = int(b)
            if b >= a and b - a < 60:
                out.extend(range(a, b + 1))
        else:
            out.append(a)
    return out


# ------------------------------------------------------------------ classification
def classify(t):
    h = t.headers()
    if not h or len(t.grid) < 2:
        return None, h
    sec = (t.section + ' ' + t.subsection).lower()
    hasdrv = col(h, [r'driver'], excl=[r'round', r'winn', r'pole', r'fastest', r'most laps']) is not None
    hasteam = col(h, [r'^team|entrant|^teams'], excl=[r'winn']) is not None
    haspos = col(h, [r'^pos', r'^place', r'^rank', r'^p\.?$', r'^pos\.']) is not None
    if not hasdrv and haspos and col(h, [r'^name$', r'^name\b']) is not None:
        hasdrv = True
    if not hasteam and hasdrv and h and h[0] == '' and col(h, [r'chassis', r'engine']) is not None:
        hasteam = True
    haspts = col(h, [r'^(pts|points|total)', r'points$', r'pts$']) is not None
    hasdate = col(h, [r'date']) is not None
    hastrack = col(h, [r'track|circuit|venue|location|course|city|speedway'], excl=[r'track type']) is not None
    haswin = col(h, [r'winn', r'winner', r'^1st']) is not None
    haspole = col(h, [r'pole']) is not None
    if 'key' in ' '.join(h) or h[0] in ('color', 'icon', 'position', 'key symbol'):
        return None, h
    if haspos and hasdrv and (haspts or len(h) >= 6):
        return 'standings', h
    if hasteam and hasdrv and not haspos and not haswin:
        return 'teams', h
    if (haswin or haspole) and not haspos:
        if hasdate and hastrack:
            return 'calendar_results', h
        return 'results', h
    if hasdate and hastrack and not haspos:
        return 'schedule', h
    return None, h


# ------------------------------------------------------------------ teams
def parse_teams(T, total_rounds):
    teams = {}
    order = []
    for t in T:
        h = t.headers()
        ci_team = col(h, [r'^team', r'entrant', r'teams'])
        if ci_team is None and h and h[0] == '':
            ci_team = 0
        ci_eng = col(h, [r'engine', r'^manufacturer', r'^make$', r'power'], excl=[r'chassis'])
        ci_ch = col(h, [r'chassis', r'^car$'])
        ci_chen = col(h, [r'chassis.*engine|chassis/engine'])
        ci_no = col(h, [r'^no\.?$', r'^(car )?(no|#|num|number)', r'^#', r'^car'], excl=[r'chassis'])
        ci_rd = col(h, [r'round', r'^races?$', r'^race\(s\)', r'^rnds?'])
        ci_drv = col(h, [r'driver'], excl=[r'round', r'^no', r'number'])
        if ci_drv is None or ci_team is None:
            continue
        if ci_no == ci_ch:
            ci_no = col(h, [r'^no\.?$', r'^(car )?(no|#|num|number)', r'^#'])
        for row in t.body():
            if len(row) < 2:
                continue
            tc = cell(row, ci_team); dc = cell(row, ci_drv)
            if tc is None or dc is None or tc is dc:
                continue
            team = plain(tc.raw)
            if not team or re.match(r'^(source|sources|notes?)\b', team, re.I):
                continue
            team_wiki = None
            tl = links(tc.raw)
            if tl:
                team_wiki = tl[0][0].replace(' ', '_')
            eng_c = cell(row, ci_eng); ch_c = cell(row, ci_ch)
            manufacturer = chassis = None
            if eng_c is not None:
                el = links(eng_c.raw)
                manufacturer = (el[0][1] if el else plain(eng_c.raw)) or None
            if ch_c is not None and ch_c is not eng_c:
                cl = links(ch_c.raw)
                chassis = (cl[0][1] if cl else plain(ch_c.raw)) or None
            if ci_chen is not None and ci_eng == ci_chen and ci_ch == ci_chen:
                cl = links(cell(row, ci_chen).raw)
                if len(cl) >= 2:
                    chassis, manufacturer = cl[0][1], cl[-1][1]
            if manufacturer:
                manufacturer = re.split(r'\s*§BR§\s*', manufacturer)[0].strip()
            number = ctext(row, ci_no) if ci_no is not None else None
            if number:
                number = re.sub(r'[^\dA-Za-z/ ]', '', number).strip() or None
            # drivers (possibly several per cell separated by <br>)
            dparts = split_br(dc.raw)
            rc = cell(row, ci_rd)
            rparts = split_br(rc.raw) if (rc is not None and rc is not dc) else []
            if rc is not None and rc.rs > 1 and dc.rs == 1 and len(rparts) == 1:
                pass
            key = (team, team_wiki)
            if key not in teams:
                teams[key] = {'team': team, 'team_wiki': team_wiki, 'owner': None, 'manufacturer': manufacturer,
                              'chassis': chassis, 'cars': {}}
                order.append(key)
            tm = teams[key]
            if manufacturer and not tm['manufacturer']:
                tm['manufacturer'] = manufacturer
            if chassis and not tm['chassis']:
                tm['chassis'] = chassis
            car = tm['cars'].setdefault(number or '?', {'number': number, 'drivers': [], '_rounds': set(), '_all': False})
            for k, dp in enumerate(dparts):
                name, wiki, fl = person(dp)
                if not name:
                    continue
                rtxt = plain(rparts[k] if k < len(rparts) else (rparts[0] if len(rparts) == 1 else ''))
                rl = int_list(rtxt, total_rounds)
                if rl == 'all':
                    car['_all'] = True
                elif rl:
                    car['_rounds'].update(rl)
                if rtxt and re.search(r'\ball\b', rtxt, re.I):
                    car['_all'] = True
                if any(d['name'] == name for d in car['drivers']):
                    continue
                car['drivers'].append({'name': name, 'wiki': wiki, 'rounds': rtxt or None,
                                       'nat': flag_to_iso3(fl)})
    out = []
    maxr = max([max(c['_rounds']) for t in teams.values() for c in t['cars'].values() if c['_rounds']] or [0])
    eff_total = min(total_rounds, maxr) if (total_rounds and maxr) else total_rounds
    for key in order:
        tm = teams[key]
        cars = []
        for c in tm['cars'].values():
            if not c['drivers']:
                continue
            if c['_all']:
                ft = True
            elif eff_total and c['_rounds']:
                ft = len(set(r for r in c['_rounds'] if r <= eff_total)) >= eff_total
            else:
                ft = None if not c['_rounds'] else False
            cars.append({'number': c['number'], 'full_time': ft, 'drivers': c['drivers']})
        if cars:
            tm['cars'] = cars
            out.append(tm)
    return out


# ------------------------------------------------------------------ schedule / results
def track_type(raw):
    m = re.search(r'\{\{\s*colou?r ?box\s*\|[^|}]*\|\s*\'*([ORSDT])\'*\s*[|}]', raw or '', re.I)
    if m:
        return {'O': 'oval', 'R': 'road', 'S': 'street', 'D': 'road', 'T': 'road'}.get(m.group(1).upper())
    return None


SKIPPED = []


def parse_rows(t, kind, year):
    h = t.headers()
    ci_rd = col(h, [r'^(rd|rnd|round|race no|no|#|r)\.?$', r'^(rd|rnd|round)\b', r'^race$'])
    if ci_rd is not None and h[ci_rd] == 'race':
        # 'race' as round column only if body values are integers
        vals = [ctext(r, ci_rd) for r in t.body()[:4]]
        if not all(re.match(r'^\d+', v or '') for v in vals):
            ci_rd = None
    ci_date = col(h, [r'date'])
    ci_race = col(h, [r'race name', r'^race$', r'^event', r'^race\b', r'name', r'grand prix'],
                  excl=[r'winn', r'report', r'^race no', r'driver', r'team'])
    ci_track = col(h, [r'track|circuit|venue|course|speedway'], excl=[r'type', r'length', r'record'])
    ci_loc = col(h, [r'location|city|place|^state|country'])
    ci_win = col(h, [r'winning driver', r'winner driver', r'race winner$', r'winner\(s\)', r'^winner', r'winn.*driver',
                     r'race winner', r'winn', r'^1st'],
                 excl=[r'team', r'car', r'chassis', r'engine', r'manufacturer', r'entrant', r'owner'])
    ci_team = col(h, [r'winn.*team|winner team|winning team'])
    rows = []
    for r in t.body():
        if all(c is r[0] for c in r):  # full-width spanning row (notes, etc.)
            continue
        rd_txt = ctext(r, ci_rd) if ci_rd is not None else ''
        rnds = int_list(rd_txt) if rd_txt else []
        if rnds == 'all':
            rnds = []
        if ci_rd is not None and not rnds:
            SKIPPED.extend(l[0] for c in r if c is not None for l in links(c.raw))
            # cancelled / non-championship rows lack a round number
            if re.search(r'cancel|postpon|non-championship|exhibition', plain(' '.join(c.raw for c in r if c)), re.I):
                continue
            if rd_txt and not re.search(r'\d', rd_txt):
                continue
        e = {'_rounds': rnds}
        e['date_raw'] = ctext(r, ci_date)
        e['race'] = ctext(r, ci_race) or None
        rc = cell(r, ci_race)
        e['race_wiki'] = None
        if rc is not None:
            l = links(rc.raw)
            if l:
                e['race_wiki'] = l[0][0].replace(' ', '_')
        tc = cell(r, ci_track)
        e['track'] = None
        e['track_type'] = None
        if tc is not None:
            tl = [x for x in links(tc.raw)]
            e['track'] = (tl[0][1] if tl else plain(tc.raw)) or None
            e['track_type'] = track_type(tc.raw)
            if e['track']:
                e['track'] = e['track'].split('§BR§')[0].strip()
        lc = cell(r, ci_loc)
        e['loc_raw'] = plain(lc.raw) if lc is not None and lc is not tc else ''
        e['loc_flag'] = None
        for c in ([lc] if lc is not None else []) + ([tc] if tc is not None else []) + ([rc] if rc is not None else []):
            fl = flags(c.raw)
            if fl:
                e['loc_flag'] = fl[0]; break
        if not e['loc_raw'] and tc is not None:
            # e.g. "Track, City, State" in a single cell
            pt = plain(tc.raw)
            if ',' in pt:
                e['loc_raw'] = pt.split(',', 1)[1]
        wc = cell(r, ci_win)
        e['winner'] = e['winner_wiki'] = None
        e['_winners'] = []
        e['_cancel'] = False
        if wc is not None and re.search(r'abandon|cancel|postpon|not held|rained out|race called', plain(wc.raw), re.I):
            e['_cancel'] = True
        elif wc is not None and wc is not rc and wc is not tc:
            for part in split_br(wc.raw):
                n, w, _ = person(part)
                if n:
                    e['_winners'].append((n, w))
            if e['_winners']:
                e['winner'], e['winner_wiki'] = e['_winners'][0]
        if not any([e['race'], e['track'], e['date_raw'], e['winner']]):
            continue
        rows.append(e)
    return rows


def build_schedule(sched_rows, res_rows, year, standings_cols):
    # expand multi-round rows
    def expand(rows):
        out = []
        for e in rows:
            rn = e['_rounds']
            if len(rn) > 1:
                for k, x in enumerate(rn):
                    f = dict(e); f['_rounds'] = [x]
                    if len(e['_winners']) == len(rn):
                        f['winner'], f['winner_wiki'] = e['_winners'][k]
                    elif len(e['_winners']) > 1:
                        f['winner'] = f['winner_wiki'] = None
                    out.append(f)
            else:
                out.append(e)
        # sequential numbering if no rounds
        if out and all(not e['_rounds'] for e in out):
            for k, e in enumerate(out):
                e['_rounds'] = [k + 1]
        return out
    S = expand(sched_rows)
    R = expand(res_rows)
    def dup(L):
        rr = [e['_rounds'][0] for e in L if e['_rounds']]
        return len(rr) != len(set(rr))
    if dup(S) or dup(R):
        for L in (S, R):
            for k, e in enumerate(L):
                e['_rounds'] = [k + 1]
    base = S if len(S) >= len(R) else R
    other = R if base is S else S
    om = {}
    for e in other:
        if e['_rounds']:
            om.setdefault(e['_rounds'][0], e)
    STOP = {'grand', 'prix', 'race', 'indy', 'speedway', 'motor', 'international', 'raceway', 'circuit', 'street',
            'streets', 'the', 'park', 'course', 'sports', 'road', 'presented', 'world', 'series', 'championship',
            'indycar', 'cart', 'champ', 'car', 'lights', 'report', 'firestone', 'honda', 'toyota', 'chevrolet',
            'freedom', 'indy', 'mile', 'super', 'auto', 'club', 'race1', 'race2', 'one', 'two'}
    def words(e):
        blob = ' '.join(str(e.get(k) or '') for k in ('race', 'track', 'loc_raw', 'race_wiki')).lower()
        blob = re.sub(r'\b(19|20)\d\d\b', ' ', blob)
        return set(w for w in re.findall(r'[a-zà-ÿ]{4,}', blob) if w not in STOP)
    def sim(a, b):
        return len(words(a) & words(b))
    ptr = 0
    match = {}
    for k, e in enumerate(base):
        rnd = e['_rounds'][0] if e['_rounds'] else None
        same = om.get(rnd)
        if same is not None and (sim(e, same) > 0 or not words(e) or not words(same)):
            match[k] = same
            if same in other:
                ptr = max(ptr, other.index(same) + 1)
            continue
        best, bs = None, 0
        for j in range(max(0, ptr - 1), min(len(other), ptr + 4)):
            sc = sim(e, other[j])
            if sc > bs:
                best, bs = j, sc
        if best is None:
            taken = set(id(v) for v in match.values())
            for j in range(len(other)):
                if id(other[j]) in taken:
                    continue
                sc = sim(e, other[j])
                if sc > bs:
                    best, bs = j, sc
            if best is not None:
                match[k] = other[best]
                continue
        if best is not None:
            match[k] = other[best]; ptr = best + 1
        elif same is not None and not (words(e) and words(same)):
            match[k] = same
    out = []
    used = set()
    for k, e in enumerate(base):
        rnd = e['_rounds'][0] if e['_rounds'] else None
        if rnd is None or rnd in used:
            continue
        used.add(rnd)
        o = match.get(k, {})
        g = lambda key: e.get(key) or o.get(key)
        out.append({'_rnd': rnd, 'date_raw': g('date_raw'), 'race': g('race'), 'race_wiki': g('race_wiki'),
                    'track': g('track'), 'track_type': g('track_type'), 'loc_raw': g('loc_raw'),
                    'loc_flag': g('loc_flag'),
                    'winner': (e.get('winner') if e.get('winner') else o.get('winner')),
                    'winner_wiki': (e.get('winner_wiki') if e.get('winner') else o.get('winner_wiki')),
                    'race_wiki': g('race_wiki'), '_cancel': bool(e.get('_cancel') or o.get('_cancel'))})
    out.sort(key=lambda x: x['_rnd'])
    # dates with season wrap (e.g. 1996-97 IRL)
    md = [parse_date(e['date_raw'], year) for e in out]
    yrs = []
    months = [m[0] if m else None for m in md]
    wrap_idx = None
    prev = None
    for k, m in enumerate(months):
        if m is None:
            continue
        if prev is not None and m < prev - 4:
            wrap_idx = k
        prev = m
    sched = []
    for k, e in enumerate(out):
        m = md[k]
        date = None
        if m:
            y = m[2] or (year - 1 if (wrap_idx is not None and k < wrap_idx) else year)
            try:
                date = '%04d-%02d-%02d' % (y, m[0], m[1])
            except Exception:
                date = None
        city, state, country = parse_location(e['loc_raw'] or '', e['loc_flag'])
        if not city and e['track'] and not re.search(r'speedway|raceway|park|circuit|course|motorsport|international|street|mile|ring|autodromo|autódromo|club', e['track'], re.I):
            city = e['track']
            if not state and city in CITY_HINTS:
                state, country = CITY_HINTS[city][0], CITY_HINTS[city][1]
        sched.append({'round': e['_rnd'], 'date': date, 'race': e['race'], 'track': e['track'], 'city': city,
                      'state': state, 'country': country, 'winner': e['winner'],
                      'winner_wiki': e['winner_wiki'], 'track_type': e['track_type'], 'race_wiki': e['race_wiki'],
                      '_cancel': e['_cancel']})
    return sched


# ------------------------------------------------------------------ standings
START_CODES = {'RET', 'DSQ', 'DQ', 'NC', 'NF', 'DNF', 'EX', 'EXC', 'RTD', 'R', 'ACC', 'MECH', 'CONTACT', 'CRASH',
               'ENGINE', 'FUEL', 'ACCIDENT', 'HANDLING', 'GEARBOX', 'ELECTRICAL', 'SUSPENSION', 'DNF*'}
NOSTART_CODES = {'DNS', 'DNQ', 'DNP', 'WD', 'WTH', 'C', 'NS', 'INJ', 'DNA', 'DNPQ', 'EX*', 'TD', 'DNAQ', 'QUAL',
                 'PO', 'NP', '—', '-', '–', ''}


def result_value(raw):
    t = plain(raw)
    t = re.sub(r'[\*†‡\^~]', '', t).strip()
    t = t.split('§')[0].strip()
    m = re.match(r'^(\d{1,2})(?:\s|$|[A-Za-z]{0,3}$|\D)', t)
    if m:
        return int(m.group(1)), True
    m = re.match(r'^R(\d{1,2})$', t)
    if m:
        return int(m.group(1)), True
    code = re.split(r'[\s/]', t.upper())[0] if t else ''
    if code in START_CODES or code.startswith('RET'):
        return code, True
    return code or None, False


def _standings_table(t, h):
    ci_pos = col(h, [r'^pos', r'^place', r'^rank', r'^p\.?$'])
    ci_drv = col(h, [r'driver'])
    if ci_drv is None:
        ci_drv = col(h, [r'^name'])
    ci_pts = col(h, [r'^(pts|points|total)', r'points$', r'pts$'])
    ci_team = col(h, [r'^team', r'^entrant'])
    nonrace = [r'^team', r'^no\.?$', r'^#', r'^car', r'engine', r'chassis', r'^nat', r'country', r'^wins?$',
               r'^starts?$', r'^races?$', r'^podiums?', r'^poles?$', r'behind', r'^gap', r'^diff', r'^drop', r'^best',
               r'^entrant', r'^pts', r'^points', r'^total', r'^make', r'^rank', r'^pos', r'^class', r'^status']
    width = max(len(g) for g in t.grid)
    lo = ci_drv + 1
    hi = ci_pts if (ci_pts is not None and ci_pts >= ci_drv + 3) else width
    race_cols = [j for j in range(lo, hi) if j != ci_pts
                 and not any(re.search(p, h[j] if j < len(h) else '') for p in nonrace)]
    # header link per race column (deepest header row that has a cell here)
    hr = t.header_rows()
    col_links = []
    for j in race_cols:
        lk = None
        for g in hr:
            if j < len(g) and g[j] is not None:
                l = links(g[j].raw)
                if l:
                    lk = l[0][0]
        col_links.append(lk)
    rows = []
    index = {}
    for r in t.body():
        dc = cell(r, ci_drv)
        if dc is None or dc.header and not plain(dc.raw):
            continue
        name, wiki, fl = person(dc.raw)
        if not name or re.match(r'^(pos|driver|source|sources|points|key|name)\b', name, re.I):
            continue
        res = []
        for j in race_cols:
            c = cell(r, j)
            if c is None or c is dc:
                res.append(None); continue
            res.append(result_value(c.raw))
        tc = cell(r, ci_team)
        tinfo = None
        if tc is not None and tc is not dc:
            tl = links(tc.raw)
            tinfo = (plain(tc.raw), tl[0][0].replace(' ', '_') if tl else None)
        if id(dc) in index:  # continuation row of a rowspanned driver (team change etc.)
            prev = index[id(dc)]
            if tinfo and tinfo[0] and tinfo not in prev['_teams']:
                prev['_teams'].append(tinfo)
            for k, x in enumerate(res):
                if x and x[0] not in (None, '') and (prev['_res'][k] is None or prev['_res'][k][0] in (None, '')):
                    prev['_res'][k] = x
            continue
        if any(rr['name'] == name and rr['wiki'] == wiki for rr in rows):
            continue
        pos_t = ctext(r, ci_pos)
        m = re.match(r'^\s*(\d+)', pos_t or '')
        pos = int(m.group(1)) if m else None
        pts_t = (ctext(r, ci_pts) or '').replace(',', '')
        m = re.search(r'-?\d+(\.\d+)?', pts_t)
        pts = (float(m.group(0)) if '.' in m.group(0) else int(m.group(0))) if m else None
        row = {'pos': pos, 'name': name, 'wiki': wiki, 'points': pts, 'nat': flag_to_iso3(fl), '_res': res,
               '_teams': [tinfo] if tinfo and tinfo[0] else []}
        index[id(dc)] = row
        rows.append(row)
    return rows, col_links


def parse_standings(T, special=None):
    """Return (rows, col_links) from the drivers' standings table."""
    cands = []
    for t in T:
        kind, h = classify(t)
        if kind != 'standings':
            continue
        if re.search(r'rook|nation|team|entrant|owner|manufactur|engine|constructor|chassis|trophy|cup|master|b-?div|'
                     r'amateur|pro-am|chase|oval|road|triple|crown|teams|national class|^national', t.subsection.lower()):
            continue
        cands.append((t, h))
    if not cands:
        return [], []
    rows, col_links = _standings_table(*cands[0])
    if special == 'overview_pairs' and len(cands) > 1:
        # 1995 Indy Lights: first table = points per race, "Complete Overview" = grid/result pairs
        rows2, cl2 = _standings_table(*cands[1])
        by = {(r['name'], r['wiki']): r for r in rows2}
        for r in rows:
            o = by.get((r['name'], r['wiki']))
            if o:
                r['_res'] = o['_res'][1::2]
            else:
                r['_res'] = [None] * len(r['_res'])
        col_links = cl2[1::2]
    for k, rr in enumerate(rows):
        if rr['pos'] is None:
            rr['pos'] = k + 1
    return rows, col_links


def finalize_standings(rows, keep):
    out = []
    for r in rows:
        res = [r['_res'][j] for j in keep]
        out.append({'pos': r['pos'], 'name': r['name'], 'wiki': r['wiki'], 'points': r['points'],
                    'wins': sum(1 for x in res if x and x[0] == 1),
                    'podiums': sum(1 for x in res if x and isinstance(x[0], int) and x[0] <= 3),
                    'top5': sum(1 for x in res if x and isinstance(x[0], int) and x[0] <= 5),
                    'starts': sum(1 for x in res if x and x[1]),
                    'nat': r['nat'],
                    'results': [x[0] if x else None for x in res]})
    return out


def official_name(text, title, year):
    lead = text[:20000]
    lead = re.sub(r'\{\{[Ii]nfobox.*?\n\}\}', '', lead, flags=re.S)
    for m in re.finditer(r"'''(.+?)'''", lead):
        s = plain(m.group(1)).strip()
        if re.match(r'^(%d|%d)' % (year, year - 1), s) and len(s) < 90:
            return s
    return title


ENGINE_MAKERS = ['Ford-Cosworth', 'Cosworth', 'Honda', 'Chevrolet', 'Toyota', 'Infiniti', 'Mazda', 'Buick', 'AER',
                 'Mercedes', 'Oldsmobile', 'Nissan', 'Ilmor', 'Elan', 'Volkswagen', 'Zetec', 'Ford']


def spec_engine(text):
    body = re.sub(r'<ref[^>]*>.*?</ref>', '', text[:60000], flags=re.S)
    for para in re.split(r'\n', body):
        if 'engine' not in para.lower() and 'power plant' not in para.lower() and 'powered' not in para.lower():
            continue
        p = plain(para)
        for sent in re.split(r'(?<=[.!?])\s+', p):
            sl = sent.lower()
            if not re.search(r'engine|power ?plant|powered', sl):
                continue
            if not re.search(r'exclusive|sole |spec|all (teams|cars|entries|drivers)|single|every (car|team|driver)|supplier|identical|each car', sl):
                continue
            hits = [(sent.find(m), m) for m in ENGINE_MAKERS if re.search(r'\b' + re.escape(m) + r'\b', sent)]
            if hits:
                hits.sort()
                return hits[0][1]
    return None


CHASSIS_MAKERS = ['Dallara', 'Lola', 'Reynard', 'Swift', 'Penske', 'Eagle', 'G-Force', 'Panoz', 'Riley', 'Tatuus',
                  'Van Diemen', 'Elan', 'Mygale', 'Star Mazda', 'Ligier', 'Crawford', 'Citation', 'Spectrum']


def spec_chassis(text):
    body = re.sub(r'<ref[^>]*>.*?</ref>', '', text[:60000], flags=re.S)
    for para in body.split('\n'):
        if 'chassis' not in para.lower():
            continue
        for sent in re.split(r'(?<=[.!?])\s+', plain(para)):
            sl = sent.lower()
            if 'chassis' not in sl:
                continue
            hits = [(sent.find(m), m) for m in CHASSIS_MAKERS if re.search(r'\b' + re.escape(m) + r'\b', sent)]
            if hits:
                hits.sort()
                i0 = hits[0][0]
                m = re.match(r'[A-Z][\w-]*(?:\s+[A-Z0-9][\w/-]*){0,2}', sent[i0:])
                return (m.group(0) if m else hits[0][1]).strip()
    return None


SPECIAL = {('indy_lights', 1995): 'overview_pairs'}


def extract(text, title, year, dirname=None):
    T = tables(text)
    groups = {'teams': [], 'schedule': [], 'results': [], 'calendar_results': [], 'standings': []}
    for t in T:
        kind, h = classify(t)
        if kind:
            groups[kind].append(t)
    raw_rows, col_links = parse_standings(T, SPECIAL.get((dirname, year)))
    del SKIPPED[:]
    sched_rows = []
    for t in groups['schedule'] + groups['calendar_results']:
        sched_rows = parse_rows(t, 'schedule', year)
        if sched_rows:
            break
    res_rows = []
    for t in groups['results'] + groups['calendar_results']:
        res_rows = parse_rows(t, 'results', year)
        if res_rows:
            break
    schedule = build_schedule(sched_rows, res_rows, year, len(col_links))
    for e in schedule:
        blob = ' '.join(str(e.get(k) or '') for k in ('race', 'winner', 'date'))
        e['cancelled'] = bool(e.pop('_cancel', False) or re.search(r'cancel|postponed|not held|abandon', blob, re.I))
        if e['cancelled'] and e['winner'] and re.search(r'cancel|postpon|not held|abandon|race', e['winner'], re.I):
            e['winner'] = e['winner_wiki'] = None
    keep = list(range(len(col_links)))
    nsched = len(schedule)
    if nsched and len(col_links) > nsched:
        sw = set((e.get('race_wiki') or '').replace('_', ' ') for e in schedule)
        # drop non-championship / extra columns whose header link doesn't match a scheduled race
        cand = [j for j, l in enumerate(col_links) if not (l and l not in sw)]
        cand2 = [j for j, l in enumerate(col_links) if l and l in sw]
        cand3 = [j for j, l in enumerate(col_links) if not (l and l in SKIPPED)]
        if len(cand) == nsched:
            keep = cand
        elif len(cand2) == nsched:
            keep = cand2
        elif len(cand3) == nsched:
            keep = cand3
        else:
            # drop columns where nobody has a result (e.g. cancelled race)
            nonempty = [j for j in keep if any(r['_res'][j] and r['_res'][j][0] not in (None, '', 'C') for r in raw_rows)]
            if len(nonempty) == nsched:
                keep = nonempty
    standings = finalize_standings(raw_rows, keep)
    for r, s in zip(raw_rows, standings):
        s['_teams'] = r['_teams']
    # winner fallback from standings matrix
    if standings and schedule and len(keep) == len(schedule):
        for k, e in enumerate(schedule):
            if not e['winner'] and not e['cancelled']:
                for s in standings:
                    if s['results'][k] == 1:
                        e['winner'], e['winner_wiki'] = s['name'], s['wiki']; break
    total = len([e for e in schedule if not e['cancelled']]) or len(keep)
    teams = parse_teams(groups['teams'], len(schedule) or len(keep))
    teams_source = 'teams_table' if teams else None
    if not teams and any(s['_teams'] for s in standings):
        teams_source = 'standings_team_column'
        tm = {}
        for s in standings:
            for (tn, tw) in s['_teams']:
                t = tm.setdefault((tn, tw), {'team': tn, 'team_wiki': tw, 'owner': None, 'manufacturer': None,
                                             'chassis': None, 'cars': []})
                t['cars'].append({'number': None,
                                  'full_time': (s['starts'] >= total) if (total and len(s['_teams']) == 1) else False,
                                  'drivers': [{'name': s['name'], 'wiki': s['wiki'], 'rounds': None, 'nat': s['nat']}]})
        teams = list(tm.values())
    if teams and standings:
        st_by = {(x['name'], x['wiki']): x for x in standings}
        for t in teams:
            for c in t['cars']:
                if c['full_time'] is None and total:
                    c['full_time'] = any((st_by.get((dr['name'], dr['wiki'])) or {}).get('starts', 0) >= total
                                         for dr in c['drivers'])
                    c['full_time_source'] = 'standings_starts'
    if teams and all(not t['manufacturer'] for t in teams):
        man = spec_engine(text)
        if man:
            for t in teams:
                t['manufacturer'] = man
                t['manufacturer_note'] = 'spec engine (from page text)'
    if teams and all(not t['chassis'] for t in teams):
        ch = spec_chassis(text)
        if ch:
            for t in teams:
                t['chassis'] = ch
                t['chassis_note'] = 'spec chassis (from page text)'
    for s in standings:
        s.pop('_teams', None)
    for e in schedule:
        e.pop('race_wiki', None)
    return {'official_name': official_name(text, title, year), 'teams': teams, 'standings': standings,
            'schedule': schedule, 'teams_source': teams_source, '_n_race_cols': len(keep), '_n_raw_cols': len(col_links)}

# ############################## main_part.py
# ====================================================================== pipeline
import os, re, json, time, sys, collections, argparse

OUT = os.path.dirname(os.path.abspath(__file__))
SERIES = {
    'cart_champcar': {'years': range(1995, 2008), 'key': lambda y: 'open_wheel_top'},
    'irl_indycar': {'years': range(1996, 2027), 'key': lambda y: 'open_wheel_top_irl' if y <= 2007 else 'open_wheel_top'},
    'indy_lights': {'years': range(1995, 2027), 'key': lambda y: 'formula_lights'},
    'pro_mazda': {'years': range(1995, 2027), 'key': lambda y: 'formula_pro'},
    'usf2000': {'years': [y for y in range(1995, 2027) if not 2007 <= y <= 2009], 'key': lambda y: 'formula_2000'},
}
MAIN_ARTICLE = {'pro_mazda': 'USF Pro 2000 Championship', 'usf2000': 'USF2000 Championship',
                'indy_lights': 'Indy NXT', 'irl_indycar': 'IndyCar Series', 'cart_champcar': 'Champ Car'}
NOTES = {
    ('irl_indycar', 1996): 'IRL inaugural season was a 3-race "1996" season (Jan-May 1996).',
    ('irl_indycar', 1997): 'Stored as 1997: the IRL 1996-97 season (Aug 1996 - Oct 1997); dates of the 1996 rounds keep year 1996.',
    ('irl_indycar', 2008): 'Unification: Champ Car merged into the IRL in Feb 2008; Champ Car teams joined (transition teams). '
                           'Long Beach was run with Champ Car-spec cars on the Motegi weekend; both count for points. '
                           'Rounds are numbered sequentially here.',
    ('cart_champcar', 2004): 'First season under the Champ Car World Series (OWRS) banner after CART bankruptcy.',
    ('cart_champcar', 2007): 'Final Champ Car season before 2008 unification with the IRL IndyCar Series.',
    ('indy_lights', 2002): 'IRL-sanctioned Infiniti Pro Series (first season); the CART-era Indy Lights ended after 2001.',
    ('indy_lights', 2020): 'Season cancelled (COVID-19); no races held.',
}
DIRS = {'cart_champcar': 'cart_champcar', 'irl_indycar': 'irl_indycar', 'indy_lights': 'indy_lights',
        'pro_mazda': 'pro_mazda', 'usf2000': 'usf2000'}


def wiki_url(title):
    return 'https://en.wikipedia.org/wiki/' + title.replace(' ', '_')


def season_links(main):
    t, txt = raw(main)
    return sorted(set(l.strip() for l in re.findall(r'\[\[((?:19|20)\d\d[^\]|#]*)', txt or '')))


def discover():
    out = {}
    cc = season_links('Template:Champ Car seasons')
    out['cart_champcar'] = {int(l[:4]): l for l in cc if 1995 <= int(l[:4]) <= 2007}
    d = {}
    for l in season_links('Template:IndyCar Series seasons'):
        if 'Indianapolis 500' in l:
            continue
        if l.startswith('1996–97'):
            d[1997] = l; continue
        if re.match(r'^\d{4} (Indy Racing League|IndyCar Series)$', l):
            d.setdefault(int(l[:4]), l)
    out['irl_indycar'] = {y: t for y, t in d.items() if 1996 <= y <= 2026}
    d = {}
    for l in season_links('Indy NXT'):
        if ' in IPS' in l or not re.search(r'Indy Lights|Infiniti Pro|Indy Pro Series|Indy NXT', l):
            continue
        y = int(l[:4])
        if 1995 <= y <= 2026 and (y not in d or len(l) < len(d[y])):
            d[y] = l
    out['indy_lights'] = d
    out['pro_mazda'] = {int(l[:4]): l for l in season_links('USF Pro 2000 Championship')
                        if 1995 <= int(l[:4]) <= 2026 and 'Winterfest' not in l and re.search(r'Mazda|Pro 2000', l)}
    out['usf2000'] = {int(l[:4]): l for l in season_links('USF2000 Championship')
                      if 1995 <= int(l[:4]) <= 2026 and ('F2000' in l or 'USF2000' in l) and 'Winterfest' not in l}
    # fill gaps with title guesses (resolved through redirects)
    guesses = {
        'cart_champcar': ['{y} CART season', '{y} Champ Car season', '{y} PPG Indy Car World Series'],
        'irl_indycar': ['{y} IndyCar Series', '{y} Indy Racing League', '{y} IndyCar Series season'],
        'indy_lights': ['{y} Indy Lights season', '{y} Indy Lights', '{y} Indy NXT', '{y} Indy Pro Series', '{y} Infiniti Pro Series'],
        'pro_mazda': ['{y} Star Mazda Championship', '{y} Pro Mazda Championship', '{y} Indy Pro 2000 Championship', '{y} USF Pro 2000 Championship'],
        'usf2000': ['{y} U.S. F2000 National Championship', '{y} USF2000 Championship'],
    }
    for dn, cfg in SERIES.items():
        for y in cfg['years']:
            if y in out[dn] and raw(out[dn][y])[1]:
                continue
            for g in guesses[dn]:
                rt, tx = raw(g.format(y=y))
                if tx:
                    out[dn][y] = rt; break
    return out


def champions_fallback(dn):
    """Champion per year from the series' main article (for seasons without their own page)."""
    t, txt = raw(MAIN_ARTICLE[dn])
    res = {}
    for tb in tables(txt or ''):
        h = tb.headers()
        if not h or not re.match(r'^(season|year)', h[0]):
            continue
        ci = col(h, [r'^champion', r'champion'])
        if ci is None:
            continue
        for r in tb.body():
            c0 = cell(r, 0)
            if c0 is None:
                continue
            m = re.search(r'\b(19\d\d|20\d\d)\b', plain(c0.raw))
            if not m:
                continue
            y = int(m.group(1))
            c = cell(r, ci)
            if c is None:
                continue
            n, w, fl = person(c.raw)
            if n and y not in res:
                res[y] = {'name': n, 'wiki': w, 'nat': flag_to_iso3(fl)}
    return res, t


# ---------------------------------------------------------------- canonical titles / bios
def resolve_light(title):
    """Canonical title for a wiki link (follows redirects); None if page missing."""
    title = title.replace('_', ' ').strip()
    if not title:
        return None
    title = title[0].upper() + title[1:]
    fn = _ck('res', title)
    if os.path.exists(fn):
        return json.load(open(fn))['t']
    cur = title
    out = None
    for _ in range(4):
        r = None
        for i in range(4):
            time.sleep(0.2)
            try:
                r = S.get('https://en.wikipedia.org/w/index.php', params={'title': cur, 'action': 'raw'},
                          timeout=60, stream=True)
            except requests.RequestException:
                r = None; time.sleep(3); continue
            if r.status_code == 429:
                r.close(); time.sleep(10); continue
            break
        if r is None:
            return title  # transient failure: don't cache
        if r.status_code == 404:
            r.close(); out = None; break
        if r.status_code != 200:
            r.close(); return title
        head = b''
        for chunk in r.iter_content(512):
            head += chunk
            if len(head) >= 512:
                break
        r.close()
        m = re.match(r'\s*#REDIRECT\s*:?\s*\[\[([^\]|#]+)', head.decode('utf-8', 'ignore'), re.I)
        if m:
            cur = m.group(1).strip(); cur = cur[0].upper() + cur[1:]
            continue
        out = cur
        break
    json.dump({'t': out}, open(fn, 'w'))
    return out


SPARQL = 'https://query.wikidata.org/sparql'


def sparql_bios(titles):
    """titles: canonical enwiki titles (spaces). Returns {title: bio}."""
    res = {}
    todo = []
    for t in titles:
        fn = _ck('bio', t)
        if os.path.exists(fn):
            res[t] = json.load(open(fn))
        else:
            todo.append(t)
    for i in range(0, len(todo), 60):
        batch = todo[i:i + 60]
        vals = ' '.join('"%s"@en' % t.replace('\\', '\\\\').replace('"', '\\"') for t in batch)
        q = '''SELECT ?t ?item ?dob ?prec ?pob ?pobLabel ?pIso ?pCountry ?stCode ?citIso ?human WHERE {
  VALUES ?t { %s }
  ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?t .
  OPTIONAL { ?item p:P569 ?ds . ?ds a wikibase:BestRank ; psv:P569 ?dv . ?dv wikibase:timeValue ?dob ; wikibase:timePrecision ?prec . }
  OPTIONAL { ?item wdt:P19 ?pob .
    OPTIONAL { ?pob rdfs:label ?pobLabel . FILTER(lang(?pobLabel) = "en") }
    OPTIONAL { ?pob wdt:P17 ?pc . ?pc wdt:P298 ?pIso . OPTIONAL { ?pc rdfs:label ?pCountry . FILTER(lang(?pCountry) = "en") } }
    OPTIONAL { ?pob wdt:P131* ?st . ?st wdt:P300 ?stCode . FILTER(STRSTARTS(?stCode, "US-") || STRSTARTS(?stCode, "CA-")) }
  }
  OPTIONAL { ?item wdt:P27 ?cit . ?cit wdt:P298 ?citIso . }
  BIND(EXISTS { ?item wdt:P31 wd:Q5 } AS ?human)
}''' % vals
        data = None
        for k in range(5):
            time.sleep(1.0)
            try:
                r = S.post(SPARQL, data={'query': q}, headers={'Accept': 'application/sparql-results+json'}, timeout=120)
            except requests.RequestException:
                time.sleep(5); continue
            if r.status_code == 200:
                data = r.json(); break
            time.sleep(10 * (k + 1))
        if data is None:
            print('  SPARQL batch failed', i, file=sys.stderr)
            continue
        agg = {}
        for b in data['results']['bindings']:
            t = b['t']['value']
            a = agg.setdefault(t, {'qid': None, 'dob': [], 'pob': [], 'cit': [], 'human': False})
            a['qid'] = b['item']['value'].rsplit('/', 1)[1]
            a['human'] = b.get('human', {}).get('value') == 'true'
            if 'dob' in b:
                a['dob'].append((b['dob']['value'], int(b['prec']['value'])))
            if 'pob' in b:
                a['pob'].append({'qid': b['pob']['value'].rsplit('/', 1)[1], 'label': b.get('pobLabel', {}).get('value'),
                                 'iso': b.get('pIso', {}).get('value'), 'country': b.get('pCountry', {}).get('value'),
                                 'st': b.get('stCode', {}).get('value')})
            if 'citIso' in b:
                a['cit'].append(b['citIso']['value'])
        for t in batch:
            a = agg.get(t)
            bio = {'qid': None, 'birth_date': None, 'birth_place': None, 'state': None, 'country': None,
                   'citizenship': [], 'is_human': None}
            if a:
                bio['qid'] = a['qid']; bio['is_human'] = a['human']
                if a['dob']:
                    v, p = a['dob'][0]
                    m = re.match(r'^\+?(-?\d{4})-(\d\d)-(\d\d)', v)
                    if m:
                        bio['birth_date'] = ('%s-%s-%s' % m.groups()) if p >= 11 else (
                            '%s-%s' % m.groups()[:2] if p == 10 else m.group(1))
                bio['citizenship'] = sorted(set(a['cit']))
                if a['pob']:
                    first_q = a['pob'][0]['qid']
                    rows = [x for x in a['pob'] if x['qid'] == first_q]
                    isos = [x['iso'] for x in rows if x['iso']]
                    iso = None
                    if isos:
                        pref = [x for x in isos if x in bio['citizenship']]
                        iso = (pref or isos)[0]
                    st = next((x['st'] for x in rows if x['st']), None)
                    label = rows[0]['label']
                    cname = next((x['country'] for x in rows if x['iso'] == iso and x['country']), None)
                    bio['country'] = iso
                    if st and iso in ('USA', 'CAN') and st[:2] == {'USA': 'US', 'CAN': 'CA'}[iso]:
                        bio['state'] = st.split('-', 1)[1]
                    if label:
                        tail = bio['state'] or cname
                        bio['birth_place'] = label + (', ' + tail if tail and tail != label else '')
                    bio['birth_place_qid'] = first_q
            res[t] = bio
            json.dump(bio, open(_ck('bio', t), 'w'))
    return res


def infobox_bio(title):
    """Fallback: birth date / place from the driver's Wikipedia infobox."""
    rt, txt = raw(title)
    if not txt:
        return {}
    txt = re.sub(r'<!--.*?-->', '', txt[:30000], flags=re.S)
    txt = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', txt, flags=re.S)
    out = {}
    m = re.search(r'\|\s*birth_date\s*=([^\n]*)', txt)
    if m:
        v = m.group(1)
        mm = re.search(r'\{\{\s*birth[ _]date(?: and age)?\s*\|(?:[^|}]*=[^|}]*\|)*\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', v, re.I)
        if mm:
            out['birth_date'] = '%04d-%02d-%02d' % tuple(int(x) for x in mm.groups())
        else:
            pd = parse_date(plain(v), None)
            if pd and pd[2]:
                out['birth_date'] = '%04d-%02d-%02d' % (pd[2], pd[0], pd[1])
            else:
                my = re.search(r'\b(19[0-9]\d|200\d)\b', plain(v))
                if my:
                    out['birth_date'] = my.group(1)
    m = re.search(r'\|\s*birth_place\s*=([^\n]*)', txt)
    if m:
        bp = plain(m.group(1)).strip(' ,')
        if bp:
            parts = [x.strip() for x in bp.split(',') if x.strip()]
            state = country = None
            for x in parts[1:]:
                xc = x.replace('U.S.A.', 'USA').replace('U.S.', 'USA').strip(' .')
                if xc in US_STATES or xc in US_ABBR:
                    state = US_STATES.get(xc, xc); country = 'USA'
                elif xc in CA_PROV or xc in CA_ABBR:
                    state = CA_PROV.get(xc, xc); country = 'CAN'
                elif xc in ISO3:
                    country = ISO3[xc]
            if len(parts) == 1 and parts[0] in ISO3:
                country = ISO3[parts[0]]
            if parts and parts[0] in CITY_HINTS and not country:
                state, country = CITY_HINTS[parts[0]]
            out['birth_place'] = bp
            out['state'] = state if country in ('USA', 'CAN') else None
            out['country'] = country
    return out


# ---------------------------------------------------------------- main
def iter_people(d):
    for t in d.get('teams', []):
        for c in t['cars']:
            for dr in c['drivers']:
                yield dr, 'name', 'wiki'
    for s in d.get('standings', []):
        yield s, 'name', 'wiki'
    for e in d.get('schedule', []):
        yield e, 'winner', 'winner_wiki'


def run(only=None, skip_bios=False):
    titles = discover()
    seasons = {}
    for dn, cfg in SERIES.items():
        if only and dn not in only:
            continue
        champs = None
        for y in cfg['years']:
            title = titles[dn].get(y)
            rt, txt = raw(title) if title else (None, None)
            if txt:
                d = extract(txt, rt, y, dn)
                d['sources'] = [wiki_url(rt)]
                d['data_level'] = 'full'
                if not d['standings'] and not d['schedule']:
                    d['data_level'] = 'empty'
            else:
                if champs is None:
                    champs = champions_fallback(dn)
                ch, mt = champs
                c = ch.get(y)
                d = {'official_name': title or None, 'teams': [], 'schedule': [], 'teams_source': None,
                     'standings': ([{'pos': 1, 'name': c['name'], 'wiki': c['wiki'], 'points': None, 'wins': None,
                                     'podiums': None, 'top5': None, 'starts': None, 'nat': c['nat'], 'results': None}]
                                   if c else []),
                     'sources': [wiki_url(mt)], 'data_level': 'champion_only' if c else 'none'}
                if title:
                    d['notes'] = 'Season article "%s" does not exist on Wikipedia (red link); only the champion is known from %s.' % (title, mt)
            if (dn, y) in NOTES:
                d['notes'] = (d.get('notes', '') + ' ' + NOTES[(dn, y)]).strip()
            if dn == 'indy_lights':
                d['era'] = 'CART Indy Lights' if y <= 2001 else 'IRL feeder (Infiniti Pro / Indy Pro / Indy Lights / Indy NXT)'
            if dn == 'irl_indycar':
                d['era'] = 'Indy Racing League' if y <= 2007 else 'unified IndyCar Series'
            if dn == 'indy_lights' and y == 2020:
                for e in d['schedule']:
                    e['cancelled'] = True; e['winner'] = e['winner_wiki'] = None
                d['data_level'] = 'season_cancelled'
            seasons[(dn, y)] = d
            print('  parsed', dn, y, d['data_level'], len(d['standings']), len(d['schedule']), file=sys.stderr)
    # ---- canonicalise driver titles
    links = set()
    for d in seasons.values():
        for obj, nk, wk in iter_people(d):
            if obj.get(wk):
                links.add(obj[wk])
    print('resolving %d driver links' % len(links), file=sys.stderr)
    canon = {}
    for i, l in enumerate(sorted(links)):
        c = resolve_light(l)
        canon[l] = c.replace(' ', '_') if c else None
        if i % 200 == 0:
            print('  resolved', i, file=sys.stderr)
    nat = collections.defaultdict(collections.Counter)
    names = collections.defaultdict(collections.Counter)
    redlinks = collections.Counter()
    for d in seasons.values():
        for obj, nk, wk in iter_people(d):
            w = obj.get(wk)
            if w:
                c = canon.get(w)
                if c is None:
                    redlinks[obj.get(nk)] += 1
                obj[wk] = c
            if obj.get(wk):
                names[obj[wk]][obj[nk]] += 1
                if obj.get('nat'):
                    nat[obj[wk]][obj['nat']] += 1
    # ---- bios
    drivers = {}
    if not skip_bios:
        bios = sparql_bios(sorted(t.replace('_', ' ') for t in names))
    else:
        bios = {}
    nonhuman = set(w for w in names if bios.get(w.replace('_', ' '), {}).get('is_human') is False)
    if nonhuman:
        print('dropping non-person link targets:', sorted(nonhuman), file=sys.stderr)
        for d in seasons.values():
            for obj, nk, wk in iter_people(d):
                if obj.get(wk) in nonhuman:
                    obj[wk] = None
        for w in nonhuman:
            names.pop(w, None)
    for w in sorted(names):
        b = dict(bios.get(w.replace('_', ' '), {}))
        if not b.get('birth_place') or not b.get('birth_date'):
            ib = infobox_bio(w)
            if ib.get('birth_date') and not b.get('birth_date'):
                b['birth_date'] = ib['birth_date']
            if ib.get('birth_place') and not b.get('birth_place'):
                b['birth_place'] = ib['birth_place']
                if ib.get('country') and not b.get('country'):
                    b['country'] = ib['country']; b['_ib_country'] = True
                    b['state'] = ib.get('state')
        nf = nat[w].most_common(1)[0][0] if nat[w] else None
        country = b.get('country')
        src = ('infobox_birthplace' if b.get('_ib_country') else 'wikidata_birthplace') if country else None
        if not country and b.get('citizenship'):
            country = nf if nf in b['citizenship'] else b['citizenship'][0]; src = 'wikidata_citizenship'
        if not country and nf:
            country = nf; src = 'table_flag'
        drivers[w] = {'name': names[w].most_common(1)[0][0], 'birth_date': b.get('birth_date'),
                      'birth_place': b.get('birth_place'), 'state': b.get('state'), 'country': country,
                      'qid': b.get('qid'), 'nationality_flag': nf, 'citizenship': b.get('citizenship') or [],
                      'country_source': src}
        if b and b.get('qid') and b.get('is_human') is False:
            drivers[w]['note'] = 'Wikidata item is not a human (link may point to a disambiguation or wrong page)'
    # ---- write
    for (dn, y), d in sorted(seasons.items()):
        out = {'series': SERIES[dn]['key'](y), 'year': y, 'official_name': d.get('official_name')}
        for k in ('era', 'data_level', 'notes', 'teams_source'):
            if d.get(k):
                out[k] = d[k]
        out['teams'] = d['teams']
        out['standings'] = d['standings']
        out['schedule'] = d['schedule']
        out['sources'] = d['sources'] + ['https://www.wikidata.org (driver bios)']
        p = os.path.join(OUT, DIRS[dn], '%d.json' % y)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(out, open(p, 'w'), ensure_ascii=False, indent=1)
    json.dump(drivers, open(os.path.join(OUT, 'drivers_openwheel.json'), 'w'), ensure_ascii=False, indent=1)
    report(seasons, drivers, redlinks)


def report(seasons, drivers, redlinks):
    print('\n%-14s %4s %-14s %5s %5s %5s %5s %6s %6s %5s' % ('series', 'year', 'level', 'teams', 'cars', 'stand', 'sched', 'winner', 'dated', 'wins='))
    for (dn, y), d in sorted(seasons.items()):
        sch = [e for e in d['schedule'] if not e.get('cancelled')]
        wins = sum((s['wins'] or 0) for s in d['standings'])
        print('%-14s %4d %-14s %5d %5d %5d %5d %6d %6d %5s' % (
            dn, y, d['data_level'], len(d['teams']), sum(len(t['cars']) for t in d['teams']), len(d['standings']),
            len(sch), sum(1 for e in sch if e['winner']), sum(1 for e in sch if e['date']),
            'ok' if (not sch or wins == len(sch)) else str(wins)))
    n = len(drivers)
    def pct(f):
        return 100.0 * sum(1 for v in drivers.values() if f(v)) / max(n, 1)
    print('\nunique drivers with wiki pages: %d' % n)
    print('  qid %.1f%%  birth_date %.1f%%  birth_place %.1f%%  country %.1f%% (birthplace-derived %.1f%%)  state(USA/CAN-born) %.1f%%' % (
        pct(lambda v: v['qid']), pct(lambda v: v['birth_date']), pct(lambda v: v['birth_place']), pct(lambda v: v['country']),
        pct(lambda v: v['country_source'] in ('wikidata_birthplace', 'infobox_birthplace')),
        100.0 * sum(1 for v in drivers.values() if v['state'] and v['country'] in ('USA', 'CAN')) /
        max(1, sum(1 for v in drivers.values() if v['country'] in ('USA', 'CAN') and v['country_source'] in ('wikidata_birthplace', 'infobox_birthplace')))))
    print('red-linked (no article) driver names: %d unique' % len(redlinks))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--skip-bios', action='store_true')
    a = ap.parse_args()
    run(a.only, a.skip_bios)
