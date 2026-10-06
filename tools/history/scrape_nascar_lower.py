#!/usr/bin/env python3
"""NASCAR second-tier (Busch Grand National / Busch / Nationwide / Xfinity / O'Reilly Auto Parts) and
Truck Series season history scraper, 1995-2026, from the Wikipedia API + Wikidata.

Outputs (next to this script):
  nascar_xfinity/{year}.json   series key "stock_national"
  nascar_trucks/{year}.json    series key "truck_series"
  drivers_xfinity_trucks.json  wiki title -> bio (Wikidata)

Re-runnable: all raw API responses are cached under cache_lower/.
  python3 scrape_nascar_lower.py                 # use cache where present
  python3 scrape_nascar_lower.py --refresh       # re-fetch season pages + title resolution
  python3 scrape_nascar_lower.py --refresh-bios  # re-fetch Wikidata bios
"""
import re, os, sys, json, time, datetime
import requests
try:
    import mwparserfromhell as mwp
except ImportError:  # pragma: no cover
    os.system(sys.executable + ' -m pip install -q mwparserfromhell')
    import mwparserfromhell as mwp

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, 'cache_lower')
OUT_X = os.path.join(BASE, 'nascar_xfinity')
OUT_T = os.path.join(BASE, 'nascar_trucks')
DRIVERS_OUT = os.path.join(BASE, 'drivers_xfinity_trucks.json')
API = 'https://en.wikipedia.org/w/api.php'
WD_API = 'https://www.wikidata.org/w/api.php'
UA = 'racingsim-personal/1.0'
YEARS = range(1995, 2027)
REFRESH = '--refresh' in sys.argv
REFRESH_BIOS = '--refresh-bios' in sys.argv
for d in (CACHE, OUT_X, OUT_T):
    os.makedirs(d, exist_ok=True)

# ============================================================ HTTP
S = requests.Session()
S.headers['User-Agent'] = UA


def api_get(url, params, tries=15):
    params = dict(params)
    params.setdefault('format', 'json')
    params.setdefault('formatversion', 2)
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=90)
        except Exception as e:  # network hiccup
            print('   network error', e); time.sleep(5 + 3 * i); continue
        if r.status_code == 429 or r.status_code >= 500:
            try:
                ra = int(r.headers.get('retry-after', '20'))
            except ValueError:
                ra = 20
            print(f'   HTTP {r.status_code}; sleeping {ra + 2}s'); time.sleep(ra + 2); continue
        try:
            d = r.json()
        except ValueError:
            time.sleep(5); continue
        if isinstance(d, dict) and d.get('error', {}).get('code') == 'maxlag':
            time.sleep(5); continue
        time.sleep(0.2)
        return d
    raise RuntimeError('API: too many retries')


def cache_json(name, fn, refresh=False):
    p = os.path.join(CACHE, name)
    if os.path.exists(p) and not refresh:
        return json.load(open(p))
    v = fn()
    json.dump(v, open(p, 'w'))
    return v


# ============================================================ series definitions
def series_title(series, y):
    if series == 'stock_national':
        if y <= 2007:
            return f'{y} NASCAR Busch Series'
        if y <= 2014:
            return f'{y} NASCAR Nationwide Series'
        if y <= 2025:
            return f'{y} NASCAR Xfinity Series'
        return f"{y} NASCAR O'Reilly Auto Parts Series"
    if y == 1995:
        return '1995 NASCAR SuperTruck Series'
    if y <= 2008 or y >= 2023:
        return f'{y} NASCAR Craftsman Truck Series'
    if y == 2019:
        return '2019 NASCAR Gander Outdoors Truck Series'
    if y == 2020:
        return '2020 NASCAR Gander RV & Outdoors Truck Series'
    return f'{y} NASCAR Camping World Truck Series'


def official_name(series, y):
    if series == 'stock_national':
        if y <= 2002:
            return 'NASCAR Busch Grand National Series'
        if y <= 2007:
            return 'NASCAR Busch Series'
        if y <= 2014:
            return 'NASCAR Nationwide Series'
        if y <= 2025:
            return 'NASCAR Xfinity Series'
        return "NASCAR O'Reilly Auto Parts Series"
    if y == 1995:
        return 'NASCAR SuperTruck Series by Craftsman'
    if y <= 2008:
        return 'NASCAR Craftsman Truck Series'
    if y <= 2018:
        return 'NASCAR Camping World Truck Series'
    if y == 2019:
        return 'NASCAR Gander Outdoors Truck Series'
    if y <= 2022:
        return 'NASCAR Gander RV & Outdoors Truck Series'
    return 'NASCAR Craftsman Truck Series'


# alternative page titles to try if the primary one is missing
ALT_SUFFIXES = ['NASCAR Busch Series', 'NASCAR Busch Grand National Series', 'NASCAR Nationwide Series',
                'NASCAR Xfinity Series', "NASCAR O'Reilly Auto Parts Series"]
ALT_TRUCK = ['NASCAR Craftsman Truck Series', 'NASCAR SuperTruck Series', 'NASCAR Camping World Truck Series',
             'NASCAR Gander Outdoors Truck Series', 'NASCAR Gander RV & Outdoors Truck Series']


def fetch_pages():
    """Return {(series, year): {'title','revid','wikitext'}} using the cache."""
    want = {}
    for y in YEARS:
        for s in ('stock_national', 'truck_series'):
            want[(s, y)] = series_title(s, y)
    pages = {}
    missing = []
    for k, t in want.items():
        p = os.path.join(CACHE, t.replace(' ', '_').replace('/', '_') + '.json')
        if os.path.exists(p) and not REFRESH:
            pages[k] = json.load(open(p))
        else:
            missing.append(k)
    # batch fetch (10 pages / request: content-heavy)
    for i in range(0, len(missing), 10):
        chunk = missing[i:i + 10]
        titles = [want[k] for k in chunk]
        print('fetching', titles)
        d = api_get(API, dict(action='query', prop='revisions', rvprop='content|ids', rvslots='main',
                              titles='|'.join(titles), redirects=1))
        q = d['query']
        rmap = {}
        for r in q.get('normalized', []) + q.get('redirects', []):
            rmap[r['from']] = r['to']
        got = {p['title']: p for p in q['pages'] if not p.get('missing')}
        for k in chunk:
            t = want[k]
            while t in rmap:
                t = rmap[t]
            if t not in got:
                # try alternatives
                alts = [f'{k[1]} {a}' for a in (ALT_SUFFIXES if k[0] == 'stock_national' else ALT_TRUCK)]
                d2 = api_get(API, dict(action='query', prop='revisions', rvprop='content|ids', rvslots='main',
                                       titles='|'.join(alts), redirects=1))
                cand = [p for p in d2['query']['pages'] if not p.get('missing')]
                if not cand:
                    print('  !! no page for', k); continue
                p = cand[0]
            else:
                p = got[t]
            rec = {'title': p['title'], 'revid': p['revisions'][0]['revid'],
                   'wikitext': p['revisions'][0]['slots']['main']['content']}
            json.dump(rec, open(os.path.join(CACHE, want[k].replace(' ', '_').replace('/', '_') + '.json'), 'w'))
            pages[k] = rec
    return pages


# ============================================================ generic wikitable parsing
def split_top(s, sep):
    """Split s on sep only at top level (not inside [[ ]] or {{ }})."""
    out, dl, dt, i, start, n = [], 0, 0, 0, 0, len(s)
    while i < n:
        if s.startswith('[[', i):
            dl += 1; i += 2; continue
        if s.startswith(']]', i) and dl:
            dl -= 1; i += 2; continue
        if s.startswith('{{', i):
            dt += 1; i += 2; continue
        if s.startswith('}}', i) and dt:
            dt -= 1; i += 2; continue
        if dl == 0 and dt == 0 and s.startswith(sep, i):
            out.append(s[start:i]); i += len(sep); start = i; continue
        i += 1
    out.append(s[start:])
    return out


def extract_tables(wt):
    """All tables as (offset, text); nested tables are extracted separately."""
    tables, stack, off = [], [], 0
    for line in wt.split('\n'):
        st = line.lstrip()
        if st.startswith('{|'):
            stack.append([off, [line]])
        elif stack and st.startswith('|}'):
            stack[-1][1].append(line)
            s, ls = stack.pop()
            tables.append((s, '\n'.join(ls)))
            if stack:
                stack[-1][1].append('<!--NESTEDTABLE-->')
        elif stack:
            stack[-1][1].append(line)
        off += len(line) + 1
    tables.sort()
    return tables


ATTR_RE = re.compile(r'^\s*(?:(?:[a-zA-Z-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s|]+)|nowrap|nowrap="?nowrap"?)\s*)+$', re.I)


def parse_cell(raw, is_header):
    parts = split_top(raw, '|')
    attrs, content = '', raw
    if len(parts) > 1 and (ATTR_RE.match(parts[0]) or parts[0].strip() == ''):
        attrs, content = parts[0], '|'.join(parts[1:])
    rs = re.search(r'rowspan\s*=\s*["\']?\s*(\d+)', attrs)
    cs = re.search(r'colspan\s*=\s*["\']?\s*(\d+)', attrs)
    return {'h': is_header, 'attrs': attrs, 'raw': content.strip(),
            'rowspan': max(1, int(rs.group(1))) if rs else 1,
            'colspan': min(80, max(1, int(cs.group(1)))) if cs else 1}


def parse_rows(tbl):
    rows, cur, last = [], None, None
    for line in tbl.split('\n')[1:]:
        s = line.strip()
        if s.startswith('|}'):
            break
        if s.startswith('|+'):
            continue
        if s.startswith('|-'):
            if cur:
                rows.append(cur)
            cur, last = [], None
            continue
        if s.startswith('!') or s.startswith('|'):
            if cur is None:
                cur = []
            is_h = s.startswith('!')
            pieces = [s[1:]]
            for sp in (['!!', '||'] if is_h else ['||']):
                pieces = [x for p in pieces for x in split_top(p, sp)]
            for p in pieces:
                c = parse_cell(p, is_h)
                cur.append(c); last = c
        elif last is not None:
            last['raw'] += '\n' + line
    if cur:
        rows.append(cur)
    return rows


def to_grid(rows):
    grid, pending = [], {}
    for r, row in enumerate(rows):
        out, c, k = [], 0, 0
        while k < len(row) or (r, c) in pending:
            if (r, c) in pending:
                out.append(pending.pop((r, c))); c += 1; continue
            cell = row[k]; k += 1
            for _ in range(cell['colspan']):
                out.append(cell)
                for dr in range(1, cell['rowspan']):
                    pending[(r + dr, c)] = cell
                c += 1
        grid.append(out)
    return grid


def table_grid(t):
    return to_grid(parse_rows(t))


# ============================================================ text helpers
def _tname(t):
    return str(t.name).strip().lower().replace('_', ' ')


def _pos_args(t):
    return [str(p.value) for p in t.params if not p.showkey]


NOTE_TPLS = {'refn', 'efn', 'efn-lr', 'efn-la', 'efn-ua', 'efn-lg', 'notetag', 'ref', 'sfn', 'cn', 'citation needed',
             'note', 'r', 'rp', 'ref label', 'note label', 'cite web', 'cite news', 'citation', 'nb'}


def strip_refs(s):
    s = re.sub(r'<ref[^>]*/>', '', s or '')
    s = re.sub(r'<ref[^>]*>.*?</ref>', '', s, flags=re.S | re.I)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    if '{{' in s and re.search(r'\{\{\s*(refn|efn|notetag|ref|sfn|cn|citation|note|r|rp|nb|cite)\b', s, re.I):
        code = mwp.parse(s)
        for t in code.filter_templates(recursive=False):
            if _tname(t) in NOTE_TPLS:
                try:
                    code.remove(t)
                except ValueError:
                    pass
        s = str(code)
    return s


KEEP_FIRST = {'tooltip', 'abbr', 'abbreviation', 'h:title', 'nowrap', 'nobr', 'small', 'center', 'tt', 'hs',
              'nowrap begin', 'norap', 'smaller', 'resize', 'big', 'em', 'strong', 'lang', 'nobold', 'noitalic',
              'ill', 'interlanguage link', 'no wrap', 'sup', 'vanchor', 'anchor+', 'plainlist', 'unbulleted list',
              'ubl', 'hlist', 'flatlist', 'sortname-sort'}
DROP = {'flagicon', 'flag icon', 'efn', 'refn', 'ref', 'r', 'cn', 'citation needed', 'sfn', 'dagger',
        'ref label', 'note label', 'nascar driver results legend', 'anchor', 'clarify', 'dead link', 'update',
        'when', 'by whom', 'citation', 'cite web', 'cite news', 'efn-lr', 'efn-la', 'notetag', 'nbsp', 'reflist',
        'legend', 'color box', 'colorbox', 'flagdeco', 'dot', 'flagcountry', '*', 'ref|1|1'}


def expand_templates(s):
    code = mwp.parse(s)
    for t in code.filter_templates(recursive=False):
        nm = _tname(t)
        a = _pos_args(t)
        if nm == 'sortname':
            rep = (a[0].strip() + ' ' + a[1].strip()) if len(a) >= 2 else ' '.join(a)
        elif nm in ('sort', 'sortkey'):
            rep = a[1] if len(a) >= 2 else (a[0] if a else '')
        elif nm in KEEP_FIRST:
            rep = a[0] if a else ''
            if nm in ('plainlist', 'unbulleted list', 'ubl', 'hlist', 'flatlist'):
                rep = '\n'.join(a)
        elif nm in ('ndash', 'snd', 'spaced ndash', 'en dash', 'nsmdns'):
            rep = '–'
        elif nm in ('flagathlete',):
            rep = a[0] if a else ''
        elif nm.startswith('dts') or nm in ('start date', 'date'):
            rep = '{{DATE:' + '|'.join(x.strip() for x in a) + '}}'
            code.replace(t, rep); continue
        else:
            rep = ''
        if '{{' in rep:
            rep = expand_templates(rep)
        try:
            code.replace(t, rep)
        except ValueError:
            pass
    return str(code)


def clean_text(raw, drop_sup=False):
    if raw is None:
        return ''
    s = strip_refs(raw)
    if drop_sup:
        s = re.sub(r'<sup[^>]*>.*?</sup>', '', s, flags=re.S | re.I)
        s = re.sub(r'\{\{\s*(sup|ref)\s*\|[^{}]*\}\}', '', s, flags=re.I)
    s = re.sub(r'<br\s*/?\s*>', '\n', s, flags=re.I)
    s = expand_templates(s)
    s = re.sub(r'\{\{DATE:([^}]*)\}\}', lambda m: ' '.join(m.group(1).split('|')), s)
    txt = mwp.parse(s).strip_code(normalize=True, collapse=True, keep_template_params=False)
    txt = re.sub(r"'''?", '', txt)
    txt = (txt.replace('&nbsp;', ' ').replace('&ndash;', '–').replace('&mdash;', '—').replace('&amp;', '&')
           .replace('&#39;', "'").replace('\xa0', ' '))
    txt = re.sub(r'<[^>]+>', '', txt)
    txt = re.sub(r'[ \t]+', ' ', txt)
    return txt.strip()


def norm_title(t):
    if not t:
        return None
    t = t.replace('&nbsp;', ' ').replace('\xa0', ' ').replace('&amp;', '&')
    t = t.split('#')[0].strip().replace('_', ' ')
    t = re.sub(r'\s+', ' ', t).lstrip(':').strip()
    if not t:
        return None
    t = t[0].upper() + t[1:]
    return t.replace(' ', '_')


NS_SKIP = re.compile(r'^(file|image|category|wikt|wiktionary|template|help|wp|wikipedia|portal|special|s|d|'
                     r'[a-z]{2}(-[a-z]+)?):', re.I)


def links(raw):
    """List of (title, display text) for wikilinks and {{sortname}} in order (refs removed)."""
    s = strip_refs(raw)
    out = []
    for node in mwp.parse(s).filter(recursive=True, forcetype=(mwp.nodes.Wikilink, mwp.nodes.Template)):
        if isinstance(node, mwp.nodes.Wikilink):
            tgt = str(node.title).strip()
            if NS_SKIP.match(tgt):
                continue
            txt = clean_text(str(node.text)) if node.text else tgt.split('#')[0]
            out.append((norm_title(tgt), txt.strip()))
        else:
            nm = _tname(node)
            if nm == 'sortname':
                a = [str(p.value).strip() for p in node.params if not p.showkey]
                kw = {str(p.name).strip(): str(p.value).strip() for p in node.params if p.showkey}
                if len(a) >= 2:
                    name = a[0] + ' ' + a[1]
                    if 'nolink' in kw or (len(a) >= 3 and a[2].lower() == 'nolink'):
                        out.append((None, name)); continue
                    tgt = a[2] if len(a) >= 3 and a[2] else name
                    out.append((norm_title(tgt), name))
    return out


# ============================================================ domain helpers
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
    'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC', 'Washington, D.C.': 'DC',
    'Puerto Rico': 'PR'}
CA_PROV = {'Alberta': 'AB', 'British Columbia': 'BC', 'Manitoba': 'MB', 'New Brunswick': 'NB',
           'Newfoundland and Labrador': 'NL', 'Nova Scotia': 'NS', 'Ontario': 'ON', 'Prince Edward Island': 'PE',
           'Quebec': 'QC', 'Québec': 'QC', 'Saskatchewan': 'SK', 'Northwest Territories': 'NT', 'Nunavut': 'NU',
           'Yukon': 'YT'}
REGION_ABBR = {**US_STATES, **CA_PROV}
ABBR_SET = set(REGION_ABBR.values())

MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                       'september', 'october', 'november', 'december'], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS['sept'] = 9


def parse_date(text, year):
    if not text:
        return None
    t = text.replace(',', ' ')
    m = re.search(r'\b(19\d\d|20\d\d)\s+(\d{1,2})\s+(\d{1,2})\b', t)  # dts y m d
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    m = re.search(r'\b(19\d\d|20\d\d)\s+([A-Za-z]+)\.?\s+(\d{1,2})\b', t)  # dts y Month d
    if m and m.group(2).lower() in MONTHS:
        try:
            return datetime.date(int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))).isoformat()
        except ValueError:
            pass
    m = re.search(r'\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b', t)
    if m and m.group(1).lower() in MONTHS:
        y = year
        m2 = re.search(r'\b(19\d\d|20\d\d)\b', t[m.end():m.end() + 8])
        if m2:
            y = int(m2.group(1))
        try:
            return datetime.date(y, MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
        except ValueError:
            return None
    m = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3,9})\b', t)  # 20 February
    if m and m.group(2).lower() in MONTHS:
        try:
            return datetime.date(year, MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def split_location(text):
    """'Daytona Beach, Florida' -> ('Daytona Beach', 'FL')."""
    if not text:
        return None, None
    t = re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip(' ,')
    t = re.sub(r'\[.*?\]', '', t).strip()
    if not t:
        return None, None
    parts = [p.strip() for p in t.split(',') if p.strip()]
    if len(parts) >= 2:
        reg = parts[-1]
        if reg in REGION_ABBR:
            return ', '.join(parts[:-1]), REGION_ABBR[reg]
        if reg.upper() in ABBR_SET and len(reg) == 2:
            return ', '.join(parts[:-1]), reg.upper()
        if reg in ('Mexico', 'México', 'United States', 'U.S.', 'USA', 'Canada'):
            if len(parts) >= 3 and parts[-2] in REGION_ABBR:
                return ', '.join(parts[:-2]), REGION_ABBR[parts[-2]]
            return ', '.join(parts[:-1]), None
        return ', '.join(parts[:-1]), None
    if t in ('Mexico City',):
        return t, None
    return t, None


MANUF = [(r'chevrolet|chevy|monte carlo|silverado|camaro|lumina', 'Chevrolet'),
         (r'\bford\b|thunderbird|taurus|mustang|f-150|fusion', 'Ford'),
         (r'pontiac|grand prix', 'Pontiac'), (r'dodge|intrepid|charger|avenger', 'Dodge'),
         (r'\bram\b', 'Ram'), (r'toyota|tundra|camry|supra', 'Toyota'), (r'buick|regal|lesabre', 'Buick'),
         (r'oldsmobile|cutlass', 'Oldsmobile'), (r'nissan', 'Nissan'), (r'mazda', 'Mazda')]


def norm_manuf(text):
    if not text:
        return None
    t = text.lower()
    hits = []
    for pat, name in MANUF:
        m = re.search(pat, t)
        if m:
            hits.append((m.start(), name))
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


DRIVER_JUNK = re.compile(r"\((?:R|i|I|r|W|res|reserve|interim)\)|\[\w{1,3}\]|†|‡|\*|#|§", re.U)


def clean_person_name(n):
    n = (n or '').replace('&nbsp;', ' ').replace('\xa0', ' ')
    n = DRIVER_JUNK.sub('', n)
    n = re.sub(r'\(\s*\)', '', n)
    n = re.sub(r'\s+', ' ', n).strip(' ,;:–-/')
    return n


def parse_people(raw, drivers=True):
    """Driver/owner cell -> [{'name','wiki'}] (split on <br>/newlines; links preferred)."""
    if not raw:
        return []
    s = strip_refs(raw)
    s = re.sub(r'<small>.*?</small>', '', s, flags=re.S | re.I)
    s = re.sub(r'\{\{\s*(tooltip|abbr)\s*\|\s*\d[^{}]*\}\}', '', s, flags=re.I)  # round counts
    s = re.sub(r'<sup[^>]*>.*?</sup>', '', s, flags=re.S | re.I)
    pieces = re.split(r'<br\s*/?\s*>|\n|\s+/\s+|\s+&\s+|;|\s+and\s+', s, flags=re.I)
    out, seen = [], set()
    for p in pieces:
        if not p.strip():
            continue
        lk = [l for l in links(p) if l[1]]
        if lk:
            for title, txt in lk:
                name = clean_person_name(txt)
                if not name or re.fullmatch(r'[\d\s,–-]+', name):
                    continue
                key = title or name
                if drivers and re.search(r'\b(Racing|Motorsports|Alliance|Team|Enterprises|Inc\.)\b', name):
                    continue
                if key not in seen:
                    seen.add(key); out.append({'name': name, 'wiki': title})
        else:
            name = clean_person_name(clean_text(p))
            name = re.sub(r'\s*\d+(\s*[,–-]\s*\d+)*\s*$', '', name).strip()  # trailing round lists
            if not name or re.fullmatch(r'[\d\s,–\-()]+', name) or name.lower() in ('tba', 'tbd', 'various', 'n/a',
                                                                                    'none', 'unknown', '–', '-'):
                continue
            if drivers and re.search(r'\b(Racing|Motorsports|Alliance|Team|Enterprises|Inc\.)\b', name):
                continue
            if name not in seen:
                seen.add(name); out.append({'name': name, 'wiki': None})
    return out


def sections_index(wt):
    """[(offset, level, title)] of headings."""
    return [(m.start(), len(m.group(1)), clean_text(m.group(2)))
            for m in re.finditer(r'^(=+)\s*(.*?)\s*=+\s*$', wt, re.M)]


def heading_ctx(heads, off):
    """(nearest heading, nearest level-2 heading) before offset."""
    near, h2 = '', ''
    for o, lv, t in heads:
        if o > off:
            break
        near = t
        if lv == 2:
            h2 = t
    return near, h2


def header_rows(grid):
    """Count leading header rows (all cells header)."""
    n = 0
    for row in grid:
        if row and all(c['h'] for c in row):
            n += 1
        else:
            break
    return n


def col_labels(grid, nh):
    """Combined label per column from the first nh header rows."""
    width = max((len(r) for r in grid[:max(nh, 1)]), default=0)
    labels = []
    for c in range(width):
        parts = []
        for r in range(nh):
            if c < len(grid[r]):
                cell = grid[r][c]
                # skip full-width title rows
                if cell['colspan'] >= max(3, width - 1) and nh > 1:
                    continue
                t = clean_text(cell['raw']).replace('\n', ' ')
                if t and (not parts or parts[-1] != t):
                    parts.append(t)
        labels.append(' '.join(parts).lower())
    return labels


def find_col(labels, *pats, exclude=None):
    for i, l in enumerate(labels):
        for p in pats:
            if re.search(p, l) and not (exclude and re.search(exclude, l)):
                return i
    return None


def cell_at(row, i):
    if i is None or i >= len(row):
        return None
    return row[i]


def ctext(row, i, **kw):
    c = cell_at(row, i)
    return clean_text(c['raw'], **kw).replace('\n', ' ').strip() if c else ''


# ============================================================ table classification + parsing
RACE_ABBR = re.compile(r'^[A-Z0-9]{2,4}\d?$')


def classify(grid):
    if not grid:
        return None, None
    nh = header_rows(grid)
    if nh == 0:
        return None, None
    labels = col_labels(grid, nh)
    last_hdr = [clean_text(c['raw']) for c in grid[nh - 1]]
    n_abbr = sum(1 for t in last_hdr if RACE_ABBR.match(t or ''))
    has = lambda p: any(re.search(p, l) for l in labels)
    if has(r'\bpos') and has(r'driver') and n_abbr >= 3 and not has(r'owner') and not has(r'^no\.?$|car number'):
        return 'standings', (nh, labels)
    if n_abbr >= 3:
        return 'other', (nh, labels)
    if has(r'winning driver|^winner$|^winners?\b') and has(r'^race|race$|event'):
        if has(r'track|venue|^site'):
            return 'schedule', (nh, labels)
        return 'results', (nh, labels)
    if has(r'track|venue|^site') and (has(r'date') or has(r'race|event')):
        return 'schedule', (nh, labels)
    if has(r'driver') and (has(r'team') or has(r'owner')) and not has(r'^pos|^fin|position|top ten') \
            and len(labels) <= 10:
        return 'teams', (nh, labels)
    return 'other', (nh, labels)


def parse_teams_table(grid, nh, labels, section, h2, year):
    ci = dict(team=find_col(labels, r'team', exclude=r'winning'),
              manu=find_col(labels, r'manufacturer|^make|car\(s\)|truck\(s\)|^cars?$|^trucks?$|^manu'),
              num=find_col(labels, r'^no\.?$|^no\b|car number|truck number|^#'),
              driver=find_col(labels, r'driver'),
              owner=find_col(labels, r'owner'),
              rounds=find_col(labels, r'round|^races$|^races\b|schedule'))
    if ci['num'] is None:  # unlabeled number column (e.g. 1997 trucks)
        for i, l in enumerate(labels):
            if i in ci.values():
                continue
            vals = [ctext(r, i) for r in grid[nh:nh + 15]]
            if vals and sum(bool(re.fullmatch(r'\d{1,3}', v)) for v in vals) >= len(vals) * 0.6:
                ci['num'] = i; break
    sec = (section + ' ' + h2).lower()
    if re.search(r'limited|part[- ]time|partial|one[- ]off|part-?time', section.lower()):
        table_ft = False
    elif re.search(r'complete|full', section.lower()):
        table_ft = True
    else:
        table_ft = None
    rows = []
    cur_manu = None
    width = len(labels)
    for row in grid[nh:]:
        if not row:
            continue
        uniq = {id(c) for c in row}
        if len(uniq) == 1 and len(row) >= max(2, width - 1):  # section label row
            t = clean_text(row[0]['raw'])
            if norm_manuf(t):
                cur_manu = norm_manuf(t)
            continue
        if all(c['h'] for c in row) and find_col([clean_text(c['raw']).lower() for c in row], r'driver'):
            continue  # repeated header
        team_c = cell_at(row, ci['team'])
        team_l = links(team_c['raw']) if team_c else []
        team = clean_text(team_c['raw']).replace('\n', ' ') if team_c else None
        team = re.sub(r'\s+', ' ', team or '').strip() or None
        manu = norm_manuf(ctext(row, ci['manu'])) if ci['manu'] is not None else None
        manu = manu or cur_manu
        num = ctext(row, ci['num'])
        m = re.search(r'\d{1,3}', num or '')
        num = m.group(0) if m else (num or None)
        drivers = parse_people(cell_at(row, ci['driver'])['raw']) if cell_at(row, ci['driver']) else []
        owners = parse_people(cell_at(row, ci['owner'])['raw'], drivers=False) if cell_at(row, ci['owner']) else []
        rounds = ctext(row, ci['rounds']) if ci['rounds'] is not None else ''
        if table_ft is not None:
            ft = table_ft
        elif ci['rounds'] is not None:
            ft = bool(re.search(r'full|all', rounds, re.I))
        else:
            ft = True
        if not team and not drivers:
            continue
        rows.append(dict(team=team, team_wiki=team_l[0][0] if team_l else None, manufacturer=manu, number=num,
                         drivers=drivers, owner=', '.join(o['name'] for o in owners) or None, full_time=ft))
    return rows


def assemble_teams(rows):
    teams, order = {}, []
    for r in rows:
        key = ((r['team'] or '').lower(), r['manufacturer'])
        if key not in teams:
            teams[key] = {'team': r['team'], 'owner': r['owner'], 'manufacturer': r['manufacturer'], 'cars': [],
                          '_cars': {}}
            order.append(key)
        t = teams[key]
        if not t['owner'] and r['owner']:
            t['owner'] = r['owner']
        ck = r['number'] or '?'
        if ck not in t['_cars']:
            car = {'number': r['number'], 'full_time': r['full_time'], 'drivers': []}
            t['_cars'][ck] = car; t['cars'].append(car)
        car = t['_cars'][ck]
        car['full_time'] = car['full_time'] or r['full_time']
        have = {(d['wiki'] or d['name']) for d in car['drivers']}
        for d in r['drivers']:
            if (d['wiki'] or d['name']) not in have:
                car['drivers'].append(d); have.add(d['wiki'] or d['name'])
    out = []
    for k in order:
        t = teams[k]
        del t['_cars']
        out.append(t)
    return out


RESULT_NUM = re.compile(r'^(\d{1,2})$')


def parse_standings_table(grid, nh, labels):
    pos_i = find_col(labels, r'\bpos')
    drv_i = find_col(labels, r'driver')
    pts_i = None
    for i, l in enumerate(labels):
        if i > (drv_i or 0) and re.search(r'\bpts\b|points|^pts', l) and not re.search(r'stage|bonus|playoff', l):
            pts_i = i; break
    last_hdr_row = grid[nh - 1]
    race_cols = []
    abbrs = []
    for i in range((drv_i or 1) + 1, pts_i if pts_i is not None else len(labels)):
        c = cell_at(last_hdr_row, i)
        t = clean_text(c['raw']) if c else ''
        if RACE_ABBR.match(t or ''):
            lk = links(c['raw'])
            race_cols.append(i); abbrs.append((t, lk[0][0] if lk else None))
    res = []
    eligible = True
    seen_driver_cells = {}
    for row in grid[nh:]:
        if not row:
            continue
        uniq = {id(c) for c in row}
        if len(uniq) <= 2 and all(c['h'] for c in row):
            txt = clean_text(row[0]['raw']).lower()
            if 'ineligible' in txt or 'not eligible' in txt:
                eligible = False
            continue
        if all(c['h'] for c in row):
            continue  # repeated header row
        dc = cell_at(row, drv_i)
        if dc is None or dc['h'] and not cell_at(row, pos_i):
            continue
        if id(dc) in seen_driver_cells:  # driver spanning two rows -> skip duplicate row
            continue
        seen_driver_cells[id(dc)] = 1
        lk = [l for l in links(dc['raw']) if l[1]]
        name = clean_person_name(lk[0][1] if lk else clean_text(dc['raw']))
        if not name:
            continue
        wiki = lk[0][0] if lk else None
        pos_t = ctext(row, pos_i)
        pm = re.match(r'^(\d+)', pos_t or '')
        pos = int(pm.group(1)) if pm and eligible else None
        pts = None
        if pts_i is not None:
            pt = ctext(row, pts_i, drop_sup=True).replace(',', '')
            m = re.search(r'-?\d+', pt)
            pts = int(m.group(0)) if m else None
        results = []
        for i in race_cols:
            c = cell_at(row, i)
            v = clean_text(c['raw'], drop_sup=True) if c else ''
            v = re.sub(r'[*†‡§#^]|\[\w+\]', '', v).strip()
            results.append(v)
        fins = [int(v) for v in results if RESULT_NUM.match(v)]
        res.append({'pos': pos, 'name': name, 'wiki': wiki, 'points': pts if eligible else pts,
                    'wins': sum(1 for f in fins if f == 1), 'top5': sum(1 for f in fins if f <= 5),
                    'top10': sum(1 for f in fins if f <= 10), 'starts': len(fins), 'eligible': eligible,
                    '_results': results})
    return res, abbrs


def parse_schedule_table(grid, nh, labels, year):
    ci = dict(no=find_col(labels, r'^no\b|^no\.?$|^round|^rd|^#|^no '),
              race=find_col(labels, r'race title|^race$|^race\b|event|race name', exclude=r'winning|distance'),
              track=find_col(labels, r'track|venue|circuit|^site'),
              loc=find_col(labels, r'location|city'),
              date=find_col(labels, r'date'),
              winner=find_col(labels, r'winning driver|^winners?$|^winner\b|race winner'))
    out = []
    k = 0
    for row in grid[nh:]:
        if not row or all(c['h'] for c in row) and len({id(c) for c in row}) <= 2:
            continue
        if all(c['h'] for c in row) and find_col([clean_text(c['raw']).lower() for c in row], r'track|race'):
            continue
        no_t = ctext(row, ci['no']) if ci['no'] is not None else ''
        m = re.match(r'^(\d+)', no_t)
        if ci['no'] is not None and not m:
            continue  # exhibition / non-points rows
        k += 1
        rnd = int(m.group(1)) if m else k
        race_c = cell_at(row, ci['race'])
        race = clean_text(race_c['raw']).replace('\n', ' ') if race_c else None
        if race:
            race = re.sub(r'\s+', ' ', race).strip()
        track_c = cell_at(row, ci['track'])
        track = clean_text(track_c['raw']).split('\n')[0].strip() if track_c else None
        city = state = None
        if track and ',' in track:
            tparts = [x.strip() for x in track.split(',') if x.strip()]
            track = tparts[0]
            rest = tparts[1:]
            if rest and rest[-1] in ('Mexico', 'México', 'Canada', 'United States', 'USA', 'U.S.'):
                rest = rest[:-1]
            if rest and rest[-1] in REGION_ABBR:
                city, state = ', '.join(rest[:-1]) or None, REGION_ABBR[rest[-1]]
            elif rest:
                city = ', '.join(rest)
        if ci['loc'] is not None and ctext(row, ci['loc']):
            city, state = split_location(ctext(row, ci['loc']))
        date_raw = cell_at(row, ci['date'])['raw'] if cell_at(row, ci['date']) else ''
        date = parse_date(clean_text(date_raw), year)
        winner = winner_wiki = None
        if ci['winner'] is not None and cell_at(row, ci['winner']):
            lk = [l for l in links(cell_at(row, ci['winner'])['raw']) if l[1]]
            if lk:
                winner, winner_wiki = clean_person_name(lk[0][1]), lk[0][0]
            else:
                winner = clean_person_name(ctext(row, ci['winner'])) or None
        out.append(dict(round=rnd, date=date, race=race or None, track=track or None, city=city, state=state,
                        winner=winner, winner_wiki=winner_wiki))
    return out


def parse_results_table(grid, nh, labels):
    ci = dict(no=find_col(labels, r'^no\.?$|^no\b|^round|^rd'),
              race=find_col(labels, r'^race|race$|event', exclude=r'winning'),
              winner=find_col(labels, r'winning driver|^winners?$|^winner\b'))
    out = {}
    for row in grid[nh:]:
        if not row or all(c['h'] for c in row) and len({id(c) for c in row}) <= 2:
            continue
        m = re.match(r'^(\d+)', ctext(row, ci['no']))
        if not m:
            continue
        w = cell_at(row, ci['winner'])
        winner = wiki = None
        if w is not None:
            lk = [l for l in links(w['raw']) if l[1]]
            if lk:
                winner, wiki = clean_person_name(lk[0][1]), lk[0][0]
            else:
                winner = clean_person_name(clean_text(w['raw'])) or None
        if winner and re.fullmatch(r'(race )?(cancel+ed|postponed|tba|tbd|–|-)', winner.lower()):
            winner = None
        out[int(m.group(1))] = dict(race=ctext(row, ci['race']) or None, winner=winner, winner_wiki=wiki)
    return out


def parse_race_sections(wt, heads, year):
    """Old Busch pages: '==Races==' with one '===Race===' subsection each."""
    out = []
    races_h2 = [(o, t) for o, lv, t in heads if lv == 2 and re.match(r'^(races|race summaries|race reports|'
                                                                     r'race results|season summary|schedule)', t, re.I)]
    if not races_h2:
        return out
    for h2o, _ in races_h2:
        end = next((o for o, lv, t in heads if o > h2o and lv == 2), len(wt))
        subs = [(o, t) for o, lv, t in heads if h2o < o < end and lv == 3]
        for j, (o, title) in enumerate(subs):
            body_end = subs[j + 1][0] if j + 1 < len(subs) else end
            body = wt[o:body_end]
            body = body.split('\n', 1)[1] if '\n' in body else ''
            date = track = None
            m = re.search(r'(?:held|run|ran|took place|contested|raced)\s+(?:on\s+)?(?:\w+day,?\s+)?'
                          r'([A-Z][a-z]+\.?\s+\d{1,2}(?:,\s*\d{4})?)', body)
            if m:
                date = parse_date(m.group(1), year)
            m = re.search(r'\bat\s+(?:the\s+)?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', body)
            if m:
                track = (m.group(2) or m.group(1)).strip()
            winner = wiki = None
            for line in body.split('\n'):
                ls = line.strip()
                if re.match(r'^#(?!#)', ls):
                    lk = [l for l in links(ls) if l[1]]
                    if lk:
                        winner, wiki = clean_person_name(lk[0][1]), lk[0][0]
                    else:
                        t = clean_text(re.sub(r'^#\s*\d*\s*[-–—]?', '', ls))
                        winner = clean_person_name(t) or None
                    break
            if winner is None:  # top-ten table inside the section
                for off, t in extract_tables(body):
                    g = table_grid(t)
                    nh = header_rows(g)
                    if not g or nh == 0:
                        continue
                    lab = col_labels(g, nh)
                    di = find_col(lab, r'driver')
                    if di is None:
                        continue
                    for row in g[nh:]:
                        c = cell_at(row, di)
                        if c and not c['h']:
                            lk = [l for l in links(c['raw']) if l[1]]
                            winner = clean_person_name(lk[0][1] if lk else clean_text(c['raw']))
                            wiki = lk[0][0] if lk else None
                            break
                    break
            race = re.sub(r'\s*\((?:[A-Z][a-z]+ \d+|\d+|race \d+)\)\s*$', '', title).strip()
            out.append(dict(race=race, date=date, track=track, winner=winner, winner_wiki=wiki))
        if out:
            break
    return out


# ============================================================ season parse
def parse_season(series, year, page):
    wt = page['wikitext']
    heads = sections_index(wt)
    teams_rows, standings, abbrs, sched, results = [], None, [], None, {}
    notes = []
    for off, t in extract_tables(wt):
        try:
            grid = table_grid(t)
        except Exception as e:  # pragma: no cover
            notes.append(f'table parse error: {e}'); continue
        kind, info = classify(grid)
        if kind is None:
            continue
        nh, labels = info
        near, h2 = heading_ctx(heads, off)
        if kind == 'teams':
            if re.search(r'team|driver|entr', h2, re.I) or re.search(r'team|schedule|driver', near, re.I):
                teams_rows += parse_teams_table(grid, nh, labels, near, h2, year)
        elif kind == 'standings' and standings is None:
            if re.search(r'owner', near, re.I):
                continue
            standings, abbrs = parse_standings_table(grid, nh, labels)
        elif kind == 'schedule' and sched is None:
            s = parse_schedule_table(grid, nh, labels, year)
            if len(s) >= 5:
                sched = s
        elif kind == 'results' and not results:
            results = parse_results_table(grid, nh, labels)
        elif kind == 'schedule' and sched is not None and not results:
            # a second schedule-like table with winners acts as results
            s = parse_schedule_table(grid, nh, labels, year)
            if any(r['winner'] for r in s):
                results = {r['round']: dict(race=r['race'], winner=r['winner'], winner_wiki=r['winner_wiki'])
                           for r in s}
    standings = standings or []
    sections = parse_race_sections(wt, heads, year)
    n_rounds = len(abbrs)
    if sched is None:
        notes.append('schedule built from race sections/standings header')
        sched = []
        n = max(n_rounds, len(sections), max(results) if results else 0)
        for i in range(n):
            sec = sections[i] if i < len(sections) and (not n_rounds or len(sections) == n_rounds) else {}
            sched.append(dict(round=i + 1, date=sec.get('date'), race=sec.get('race'), track=sec.get('track'),
                              city=None, state=None, winner=sec.get('winner'), winner_wiki=sec.get('winner_wiki'),
                              _abbr=abbrs[i][0] if i < len(abbrs) else None))
        if sections and n_rounds and len(sections) != n_rounds:
            notes.append(f'race sections ({len(sections)}) != standings columns ({n_rounds}); sections ignored')
    else:
        for i, r in enumerate(sched):
            r['_abbr'] = abbrs[i][0] if i < len(abbrs) and len(abbrs) == len(sched) else None
        # fill missing dates/tracks from race sections when they line up
        if sections and len(sections) == len(sched):
            for r, sec in zip(sched, sections):
                for k in ('date', 'track', 'race'):
                    if not r.get(k) and sec.get(k):
                        r[k] = sec[k]
                if not r.get('winner') and sec.get('winner'):
                    r['winner'], r['winner_wiki'] = sec['winner'], sec['winner_wiki']
    # winners from results table
    for r in sched:
        rr = results.get(r['round'])
        if rr:
            if rr.get('winner'):
                r['winner'], r['winner_wiki'] = rr['winner'], rr['winner_wiki'] or r.get('winner_wiki')
            if not r.get('race') and rr.get('race'):
                r['race'] = rr['race']
    # winners from standings grid (driver with finish 1 in column i) as fallback / cross-check
    if standings and n_rounds:
        win_by_col = {}
        for s in standings:
            for i, v in enumerate(s['_results']):
                if v == '1':
                    win_by_col.setdefault(i, []).append(s)
        aligned = len(sched) == n_rounds
        mism = 0
        for i, r in enumerate(sched):
            if not aligned:
                break
            w = win_by_col.get(i)
            if w and len(w) == 1:
                if not r.get('winner'):
                    r['winner'], r['winner_wiki'] = w[0]['name'], w[0]['wiki']
                elif r['winner'].lower() != w[0]['name'].lower() and not (
                        r.get('winner_wiki') and r['winner_wiki'] == w[0]['wiki']):
                    mism += 1
                elif not r.get('winner_wiki') and r['winner'] == w[0]['name']:
                    r['winner_wiki'] = w[0]['wiki']
        if mism:
            notes.append(f'{mism} schedule winners differ from standings-grid winners (kept schedule/results value)')
        if not aligned:
            notes.append(f'schedule rounds ({len(sched)}) != standings race columns ({n_rounds})')
    teams = assemble_teams(teams_rows)
    for s in standings:
        s.pop('_results', None)
    return dict(teams=teams, standings=standings, schedule=sched, notes=notes,
                abbrs=[a for a, _ in abbrs])


# ============================================================ title canonicalisation
def resolve_titles(titles):
    """title -> {'canon': title|None, 'qid': Q|None, 'disambig': bool}; cached in cache_lower/titles.json."""
    p = os.path.join(CACHE, 'titles.json')
    known = json.load(open(p)) if os.path.exists(p) and not REFRESH else {}
    todo = [t for t in sorted(titles) if t and t not in known]
    print(f'resolving {len(todo)} titles ({len(known)} cached)')
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        d = api_get(API, dict(action='query', titles='|'.join(t.replace('_', ' ') for t in chunk), redirects=1,
                              prop='pageprops', ppprop='wikibase_item|disambiguation'))
        q = d.get('query', {})
        rmap = {}
        for r in q.get('normalized', []):
            rmap[r['from']] = r['to']
        red = {r['from']: r['to'] for r in q.get('redirects', [])}
        pages = {pg['title']: pg for pg in q.get('pages', [])}
        for t in chunk:
            tt = t.replace('_', ' ')
            tt = rmap.get(tt, tt)
            hops = 0
            while tt in red and hops < 5:
                tt = red[tt]; hops += 1
            pg = pages.get(tt)
            if not pg or pg.get('missing') or pg.get('invalid'):
                known[t] = {'canon': None, 'qid': None, 'disambig': False}
            else:
                pp = pg.get('pageprops', {})
                known[t] = {'canon': pg['title'].replace(' ', '_'), 'qid': pp.get('wikibase_item'),
                            'disambig': 'disambiguation' in pp}
        if i % 500 == 0:
            json.dump(known, open(p, 'w'))
    json.dump(known, open(p, 'w'))
    return known


# ============================================================ Wikidata bios
def wd_entities(ids, props='claims|labels'):
    p = os.path.join(CACHE, 'wikidata.json')
    store = json.load(open(p)) if os.path.exists(p) and not REFRESH_BIOS else {}
    todo = [q for q in sorted(set(ids)) if q and q not in store]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        d = api_get(WD_API, dict(action='wbgetentities', ids='|'.join(chunk), props=props, languages='en'))
        for q, e in d.get('entities', {}).items():
            claims = e.get('claims', {})
            slim = {'label': e.get('labels', {}).get('en', {}).get('value')}
            for prop in ('P569', 'P19', 'P131', 'P17', 'P298', 'P31', 'P27'):
                vals = []
                for c in claims.get(prop, []):
                    dv = c.get('mainsnak', {}).get('datavalue', {})
                    v = dv.get('value')
                    if v is None:
                        continue
                    rank = c.get('rank')
                    if rank == 'deprecated':
                        continue
                    if isinstance(v, dict) and 'id' in v:
                        vals.append((v['id'], rank))
                    elif isinstance(v, dict) and 'time' in v:
                        vals.append(((v['time'], v.get('precision')), rank))
                    else:
                        vals.append((v, rank))
                vals.sort(key=lambda x: 0 if x[1] == 'preferred' else 1)
                slim[prop] = [v for v, _ in vals]
            store[q] = slim
        if (i // 50) % 10 == 0:
            json.dump(store, open(p, 'w'))
    json.dump(store, open(p, 'w'))
    return store


STATE_TYPES = {'Q35657', 'Q11828004', 'Q9357527', 'Q107390', 'Q15149663'}  # US state, CA province/territory, federated state, ...


def wd_date(v):
    if not v:
        return None
    t, prec = v[0]
    m = re.match(r'^[+-](\d{4})-(\d\d)-(\d\d)', t)
    if not m:
        return None
    y, mo, d = m.groups()
    if prec is not None and prec < 11:
        return f'{y}-{mo}' if prec == 10 else y
    return f'{y}-{mo}-{d}'


def build_bios(qid_by_title, names):
    ents = wd_entities(qid_by_title.values())
    places = {ents[q]['P19'][0] for q in qid_by_title.values() if q in ents and ents[q].get('P19')}
    ents2 = wd_entities(places)
    # walk P131 upward up to 7 levels
    frontier = set(places)
    for _ in range(7):
        nxt = set()
        for q in frontier:
            e = ents2.get(q, {})
            for p in e.get('P131', [])[:2]:
                if p not in ents2:
                    nxt.add(p)
        if not nxt:
            break
        ents2 = wd_entities(nxt)
        frontier = nxt
    countries = set()
    for q, e in ents2.items():
        countries.update(e.get('P17', [])[:1])
    for q in qid_by_title.values():
        countries.update(ents.get(q, {}).get('P27', [])[:1])
    ents3 = wd_entities(countries)
    store = ents3  # all cached in same dict

    def region_of(place):
        seen, q, depth = set(), place, 0
        queue = [place]
        while queue and depth < 9:
            nq = []
            for q in queue:
                if q in seen:
                    continue
                seen.add(q)
                e = store.get(q, {})
                lab = e.get('label') or ''
                if set(e.get('P31', [])) & STATE_TYPES or lab in REGION_ABBR:
                    if lab in REGION_ABBR:
                        return lab
                nq += e.get('P131', [])[:2]
            queue = nq; depth += 1
        return None

    out = {}
    for title, q in qid_by_title.items():
        e = store.get(q, {}) if q else {}
        bd = wd_date(e.get('P569'))
        place_q = (e.get('P19') or [None])[0]
        pe = store.get(place_q, {}) if place_q else {}
        place_label = pe.get('label')
        region = region_of(place_q) if place_q else None
        cq = (pe.get('P17') or [None])[0] or (e.get('P27') or [None])[0]
        ce = store.get(cq, {}) if cq else {}
        iso3 = (ce.get('P298') or [None])[0]
        if not iso3 and region in US_STATES:
            iso3 = 'USA'
        if not iso3 and region in CA_PROV:
            iso3 = 'CAN'
        state = REGION_ABBR.get(region) if region else None
        bp = None
        if place_label:
            if region and region != place_label and region not in place_label:
                bp = f'{place_label}, {region}'
            elif ce.get('label') and ce.get('label') != place_label and not region:
                bp = f"{place_label}, {ce['label']}"
            else:
                bp = place_label
        out[title] = {'name': names.get(title) or e.get('label') or title.replace('_', ' '), 'birth_date': bd,
                      'birth_place': bp, 'state': state, 'country': iso3, 'qid': q}
    return out


# ============================================================ Wikipedia infobox fallback for bios
COUNTRY_ISO3 = {'U.S.': 'USA', 'U.S': 'USA', 'U. S.': 'USA', 'US': 'USA', 'USA': 'USA', 'United States': 'USA', 'Canada': 'CAN', 'Mexico': 'MEX',
                'México': 'MEX', 'England': 'GBR', 'Scotland': 'GBR', 'Wales': 'GBR', 'United Kingdom': 'GBR',
                'UK': 'GBR', 'Northern Ireland': 'GBR', 'Ireland': 'IRL', 'Australia': 'AUS', 'New Zealand': 'NZL',
                'Brazil': 'BRA', 'Japan': 'JPN', 'France': 'FRA', 'Germany': 'DEU', 'Italy': 'ITA', 'Spain': 'ESP',
                'Netherlands': 'NLD', 'Belgium': 'BEL', 'Switzerland': 'CHE', 'Austria': 'AUT', 'Sweden': 'SWE',
                'Norway': 'NOR', 'Denmark': 'DNK', 'Finland': 'FIN', 'Russia': 'RUS', 'Poland': 'POL',
                'South Africa': 'ZAF', 'Argentina': 'ARG', 'Colombia': 'COL', 'Venezuela': 'VEN', 'Chile': 'CHL',
                'Puerto Rico': 'USA', 'Cuba': 'CUB', 'Israel': 'ISR', 'India': 'IND', 'China': 'CHN',
                'South Korea': 'KOR', 'Philippines': 'PHL', 'Thailand': 'THA', 'Czech Republic': 'CZE',
                'Hungary': 'HUN', 'Portugal': 'PRT', 'Greece': 'GRC', 'Turkey': 'TUR', 'West Germany': 'DEU'}


def infobox_fallback(bios):
    """Fill missing birth_date / birth_place / state / country from the driver's Wikipedia infobox."""
    need = [t for t, b in bios.items() if not b['birth_date'] or not b['birth_place'] or not b['state'] and
            b['country'] in (None, 'USA', 'CAN')]
    p = os.path.join(CACHE, 'infobox.json')
    store = json.load(open(p)) if os.path.exists(p) and not REFRESH_BIOS else {}
    todo = [t for t in need if t not in store]
    print(f'infobox fallback: {len(need)} drivers need data, {len(todo)} to fetch')
    for i in range(0, len(todo), 20):
        chunk = todo[i:i + 20]
        d = api_get(API, dict(action='query', prop='revisions', rvprop='content', rvslots='main', redirects=1,
                              titles='|'.join(t.replace('_', ' ') for t in chunk)))
        q = d.get('query', {})
        back = {}
        for r in q.get('normalized', []) + q.get('redirects', []):
            back[r['to']] = back.get(r['from'], r['from'])
        for pg in q.get('pages', []):
            if pg.get('missing'):
                continue
            wt = pg['revisions'][0]['slots']['main']['content']
            rec = {'birth_date': None, 'birth_place': None}
            for t in mwp.parse(wt[:30000]).filter_templates(recursive=False):
                if 'infobox' not in _tname(t):
                    continue
                for prm in t.params:
                    k = str(prm.name).strip().lower()
                    if k in ('birth_date', 'birth_place', 'birthdate', 'birthplace', 'born'):
                        rec[k.replace('birthdate', 'birth_date').replace('birthplace', 'birth_place')] = \
                            str(prm.value).strip()
                break
            orig = pg['title']
            while orig in back:
                orig = back[orig]
            store[orig.replace(' ', '_')] = rec
        json.dump(store, open(p, 'w'))
    filled = 0
    for t in need:
        rec = store.get(t)
        if not rec:
            continue
        b = bios[t]
        changed = False
        bd_raw = rec.get('birth_date') or rec.get('born') or ''
        if not b['birth_date'] and bd_raw:
            m = re.search(r'\{\{\s*birth[ _]date(?:[ _]and[ _]age)?\s*\|(?:\s*(?:df|mf)\s*=\s*\w+\s*\|)?\s*(\d{4})'
                          r'\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', bd_raw, re.I)
            if m:
                b['birth_date'] = f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
            else:
                m = re.search(r'\{\{\s*birth[ _](?:year|date)[^|]*\|\s*(\d{4})', bd_raw, re.I)
                if m:
                    b['birth_date'] = m.group(1)
                else:
                    b['birth_date'] = parse_date(clean_text(bd_raw), 0) if re.search(r'\d{4}', bd_raw) else None
                    if b['birth_date'] and b['birth_date'].startswith('0000'):
                        b['birth_date'] = None
            changed = changed or bool(b['birth_date'])
        bp_raw = rec.get('birth_place') or ''
        if bp_raw:
            bp = re.sub(r'\s+', ' ', clean_text(bp_raw).replace('\n', ' ')).strip(' ,.')
            if bp:
                parts = [x.strip() for x in bp.split(',') if x.strip()]
                country = None
                if parts and parts[-1] in COUNTRY_ISO3:
                    country = COUNTRY_ISO3[parts[-1]]
                    parts_nc = parts[:-1]
                else:
                    parts_nc = parts
                region = next((x for x in reversed(parts_nc) if x in REGION_ABBR), None)
                if region:
                    country = country or ('CAN' if region in CA_PROV else 'USA')
                if not b['birth_place']:
                    b['birth_place'] = ', '.join(parts_nc) if parts_nc else bp
                    changed = True
                if not b['state'] and region and (b['country'] in (None, country)):
                    b['state'] = REGION_ABBR[region]; changed = True
                if not b['country'] and country:
                    b['country'] = country; changed = True
        filled += changed
    print(f'infobox fallback filled {filled} drivers')


# ============================================================ main
TRACK_FALLBACK = {  # used only when no season page gives a location for the track
    'Daytona International Speedway': ('Daytona Beach', 'FL'), 'Rockingham Speedway': ('Rockingham', 'NC'),
    'North Carolina Speedway': ('Rockingham', 'NC'), 'Richmond International Raceway': ('Richmond', 'VA'),
    'Richmond Raceway': ('Richmond', 'VA'), 'Atlanta Motor Speedway': ('Hampton', 'GA'),
    'Nashville Speedway USA': ('Nashville', 'TN'), 'Nashville Fairgrounds Speedway': ('Nashville', 'TN'),
    'Darlington Raceway': ('Darlington', 'SC'), 'Bristol Motor Speedway': ('Bristol', 'TN'),
    'Hickory Motor Speedway': ('Hickory', 'NC'), 'Nazareth Speedway': ('Nazareth', 'PA'),
    'Charlotte Motor Speedway': ('Concord', 'NC'), "Lowe's Motor Speedway": ('Concord', 'NC'),
    'Dover International Speedway': ('Dover', 'DE'), 'Dover Downs International Speedway': ('Dover', 'DE'),
    'Dover Motor Speedway': ('Dover', 'DE'), 'South Boston Speedway': ('South Boston', 'VA'),
    'Myrtle Beach Speedway': ('Myrtle Beach', 'SC'), 'Watkins Glen International': ('Watkins Glen', 'NY'),
    'Milwaukee Mile': ('West Allis', 'WI'), 'The Milwaukee Mile': ('West Allis', 'WI'),
    'New Hampshire International Speedway': ('Loudon', 'NH'), 'New Hampshire Motor Speedway': ('Loudon', 'NH'),
    'Talladega Superspeedway': ('Lincoln', 'AL'), 'Indianapolis Raceway Park': ('Brownsburg', 'IN'),
    'Lucas Oil Raceway': ('Brownsburg', 'IN'), 'Lucas Oil Raceway at Indianapolis': ('Brownsburg', 'IN'),
    "O'Reilly Raceway Park at Indianapolis": ('Brownsburg', 'IN'), 'Michigan International Speedway': ('Brooklyn', 'MI'),
    'Homestead-Miami Speedway': ('Homestead', 'FL'), 'Homestead–Miami Speedway': ('Homestead', 'FL'),
    'Miami-Dade Homestead Motorsports Complex': ('Homestead', 'FL'), 'Las Vegas Motor Speedway': ('Las Vegas', 'NV'),
    'Texas Motor Speedway': ('Fort Worth', 'TX'), 'California Speedway': ('Fontana', 'CA'),
    'Auto Club Speedway': ('Fontana', 'CA'), 'Gateway International Raceway': ('Madison', 'IL'),
    'World Wide Technology Raceway': ('Madison', 'IL'), 'Pikes Peak International Raceway': ('Fountain', 'CO'),
    'Memphis Motorsports Park': ('Millington', 'TN'), 'Pocono Raceway': ('Long Pond', 'PA'),
    'Phoenix International Raceway': ('Avondale', 'AZ'), 'Phoenix Raceway': ('Avondale', 'AZ'),
    'Nashville Superspeedway': ('Lebanon', 'TN'), 'Kansas Speedway': ('Kansas City', 'KS'),
    'Chicagoland Speedway': ('Joliet', 'IL'), 'Kentucky Speedway': ('Sparta', 'KY'),
    'Iowa Speedway': ('Newton', 'IA'), 'Road America': ('Elkhart Lake', 'WI'),
    'Circuit Gilles Villeneuve': ('Montreal', 'QC'), 'Autódromo Hermanos Rodríguez': ('Mexico City', None),
    'Martinsville Speedway': ('Ridgeway', 'VA'), 'Mesa Marin Raceway': ('Bakersfield', 'CA'),
    'Mesa Marin Raceway ': ('Bakersfield', 'CA'), 'Portland International Raceway': ('Portland', 'OR'),
    'Evergreen Speedway': ('Monroe', 'WA'), 'Tucson Raceway Park': ('Tucson', 'AZ'),
    'Saugus Speedway': ('Santa Clarita', 'CA'), 'Louisville Motor Speedway': ('Louisville', 'KY'),
    'Colorado National Speedway': ('Dacono', 'CO'), 'Heartland Park Topeka': ('Topeka', 'KS'),
    'Flemington Speedway': ('Flemington', 'NJ'), 'North Wilkesboro Speedway': ('North Wilkesboro', 'NC'),
    'Sears Point Raceway': ('Sonoma', 'CA'), 'Sonoma Raceway': ('Sonoma', 'CA'), 'Infineon Raceway': ('Sonoma', 'CA'),
    'I-70 Speedway': ('Odessa', 'MO'), 'Las Vegas Speedway Park': ('Las Vegas', 'NV'),
    'Bullring at Las Vegas Motor Speedway': ('Las Vegas', 'NV'), 'Walt Disney World Speedway': ('Bay Lake', 'FL'),
    'Hawaii Raceway Park': ('Kapolei', 'HI'), 'Mansfield Motorsports Park': ('Mansfield', 'OH'),
    'Mansfield Motorsports Speedway': ('Mansfield', 'OH'), 'Kentucky Speedway ': ('Sparta', 'KY'),
    'Eldora Speedway': ('Rossburg', 'OH'), 'Canadian Tire Motorsport Park': ('Bowmanville', 'ON'),
    'Mosport International Raceway': ('Bowmanville', 'ON'), 'Charlotte Motor Speedway Roval': ('Concord', 'NC'),
    'Circuit of the Americas': ('Austin', 'TX'), 'Mid-Ohio Sports Car Course': ('Lexington', 'OH'),
    'Indianapolis Motor Speedway': ('Speedway', 'IN'), 'Daytona International Speedway road course': ('Daytona Beach', 'FL'),
    'Knoxville Raceway': ('Knoxville', 'IA'), 'Nashville Fairgrounds': ('Nashville', 'TN'),
    'Portland International Raceway ': ('Portland', 'OR'), 'Sonoma Raceway ': ('Sonoma', 'CA'),
    'Lime Rock Park': ('Lakeville', 'CT'), 'North Wilkesboro Speedway ': ('North Wilkesboro', 'NC'),
    'Chicago Street Course': ('Chicago', 'IL'), 'Rockingham Speedway ': ('Rockingham', 'NC'),
    'Milwaukee Mile ': ('West Allis', 'WI'), 'Gateway Motorsports Park': ('Madison', 'IL'),
    'Talladega Superspeedway ': ('Lincoln', 'AL'), 'Bristol Motor Speedway dirt track': ('Bristol', 'TN'),
    'Naval Base Coronado': ('Coronado', 'CA'), 'Coronado Street Course': ('Coronado', 'CA'),
    'Lebanon I-44 Speedway': ('Lebanon', 'MO'), 'Thompson International Speedway': ('Thompson', 'CT'),
    'Watkins Glen International ': ('Watkins Glen', 'NY'), 'St. Petersburg Street Circuit': ('St. Petersburg', 'FL'),
    'Streets of St. Petersburg': ('St. Petersburg', 'FL'), 'Autódromo Hermanos Rodríguez ': ('Mexico City', None),
    'Rockingham Speedway (2025)': ('Rockingham', 'NC'), 'Gateway International Raceway ': ('Madison', 'IL'),
    'Kansas Speedway ': ('Kansas City', 'KS'), 'Phoenix Raceway ': ('Avondale', 'AZ'),
    'Martinsville Speedway ': ('Ridgeway', 'VA'), 'Lanier National Speedway': ('Braselton', 'GA'),
    'Gresham Motorsports Park': ('Jefferson', 'GA'), 'Pikes Peak International Raceway ': ('Fountain', 'CO'),
    'Orange County Speedway': ('Rougemont', 'NC'), 'Volusia Speedway Park': ('Barberville', 'FL'),
    'New Smyrna Speedway': ('New Smyrna Beach', 'FL'), 'Charlotte Roval': ('Concord', 'NC'),
    'EchoPark Speedway': ('Hampton', 'GA'), 'Mexico City': ('Mexico City', None),
    'Grand Prix of Long Beach': ('Long Beach', 'CA'), 'Portland Speedway': ('Portland', 'OR'),
    'Homestead Motorsports Complex': ('Homestead', 'FL'), 'Chicago Motor Speedway': ('Cicero', 'IL'),
    'North Carolina Motor Speedway': ('Rockingham', 'NC'), 'Bristol International Raceway': ('Bristol', 'TN'),
    'Michigan Speedway': ('Brooklyn', 'MI'), 'North Wilkesboro': ('North Wilkesboro', 'NC'),
    'Autódromo Hermanos Rodriguez': ('Mexico City', None), 'Pocono Raceway ': ('Long Pond', 'PA'),
}


def merge_track_locations(all_seasons):
    loc = {}
    for (series, y), d in all_seasons.items():
        for r in d['schedule']:
            if r.get('track') and r.get('city'):
                if r['track'] not in loc or (r.get('state') and not loc[r['track']][1]):
                    loc[r['track']] = (r['city'], r['state'])
    for tr, (c, st) in list(loc.items()):
        if not st and TRACK_FALLBACK.get(tr.strip(), (None, None))[1]:
            loc[tr] = (c, TRACK_FALLBACK[tr.strip()][1])
    abbr_track = {}
    for (series, y), d in all_seasons.items():
        for r in d['schedule']:
            if r.get('_abbr') and r.get('track'):
                abbr_track.setdefault((series, r['_abbr']), {}).setdefault(r['track'], []).append(y)
    for (series, y), d in all_seasons.items():
        for r in d['schedule']:
            if not r.get('track') and r.get('_abbr'):
                cands = abbr_track.get((series, r['_abbr'])) or abbr_track.get(
                    ('truck_series' if series == 'stock_national' else 'stock_national', r['_abbr']))
                if cands:  # nearest season that used this abbreviation
                    best = min(cands.items(), key=lambda kv: min(abs(yy - y) for yy in kv[1]))
                    r['track'] = best[0]
                    d['notes'].append('track names inferred from standings-column abbreviations')
            tr = r.get('track')
            if tr and r.get('city') and not r.get('state'):
                fb = loc.get(tr) if (loc.get(tr) or (None, None))[1] else TRACK_FALLBACK.get(tr.strip())
                if fb and fb[1] and not re.search(r'mexico', tr + (r.get('city') or ''), re.I):
                    r['state'] = fb[1]
            if tr and not r.get('city'):
                if tr in loc:
                    r['city'], r['state'] = loc[tr]
                elif tr.strip() in TRACK_FALLBACK:
                    r['city'], r['state'] = TRACK_FALLBACK[tr.strip()]
                else:
                    for k, v in loc.items():  # loose match
                        if k.lower().replace('–', '-') == tr.lower().replace('–', '-'):
                            r['city'], r['state'] = v; break


def main():
    pages = fetch_pages()
    seasons = {}
    for (series, y), page in sorted(pages.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        d = parse_season(series, y, page)
        d['page'] = page
        seasons[(series, y)] = d
    merge_track_locations(seasons)

    # ---- canonicalise driver wiki titles
    titles = set()
    for d in seasons.values():
        for t in d['teams']:
            for c in t['cars']:
                for dr in c['drivers']:
                    titles.add(dr['wiki'])
        for s in d['standings']:
            titles.add(s['wiki'])
        for r in d['schedule']:
            titles.add(r.get('winner_wiki'))
    titles.discard(None)
    info = resolve_titles(titles)

    def canon(t):
        if not t:
            return None
        i = info.get(t)
        if not i or not i['canon'] or i['disambig']:
            return None
        return i['canon']

    # drop link targets that are not people (e.g. a driver name redirecting to his team's article)
    qid_of = {i['canon']: i['qid'] for i in info.values() if i.get('canon') and i.get('qid')}
    ents = wd_entities(qid_of.values())
    non_human = {t for t, q in qid_of.items() if q in ents and ents[q].get('P31') and 'Q5' not in ents[q]['P31']}
    if non_human:
        print('non-person link targets dropped:', sorted(non_human))
    _canon0 = canon

    def canon(t):  # noqa: F811
        c = _canon0(t)
        return None if c in non_human else c

    name_to_wiki = {}
    for d in seasons.values():
        for s in d['standings']:
            s['wiki'] = canon(s['wiki'])
            if s['wiki']:
                name_to_wiki.setdefault(s['name'], set()).add(s['wiki'])
        for t in d['teams']:
            for c in t['cars']:
                for dr in c['drivers']:
                    dr['wiki'] = canon(dr['wiki'])
                    if dr['wiki']:
                        name_to_wiki.setdefault(dr['name'], set()).add(dr['wiki'])
        for r in d['schedule']:
            r['winner_wiki'] = canon(r.get('winner_wiki'))
    uniq = {n: next(iter(w)) for n, w in name_to_wiki.items() if len(w) == 1}

    def fill(obj, nk, wk):
        if not obj.get(wk) and obj.get(nk) in uniq:
            obj[wk] = uniq[obj[nk]]

    for (series, y), d in seasons.items():
        # season-local first: same name linked elsewhere on the page
        for s in d['standings']:
            fill(s, 'name', 'wiki')
        for t in d['teams']:
            for c in t['cars']:
                for dr in c['drivers']:
                    fill(dr, 'name', 'wiki')
        for r in d['schedule']:
            fill(r, 'winner', 'winner_wiki')

    # ---- write season files
    used = {}
    for (series, y), d in sorted(seasons.items()):
        page = d['page']
        out = {'series': series, 'year': y, 'official_name': official_name(series, y),
               'teams': d['teams'], 'standings': d['standings'],
               'schedule': [{k: v for k, v in r.items() if not k.startswith('_')} for r in d['schedule']],
               'sources': [f"https://en.wikipedia.org/w/index.php?title={page['title'].replace(' ', '_')}"
                           f"&oldid={page['revid']}",
                           'https://www.wikidata.org/ (driver bios: drivers_xfinity_trucks.json)'],
               'notes': d['notes']}
        folder = OUT_X if series == 'stock_national' else OUT_T
        with open(os.path.join(folder, f'{y}.json'), 'w') as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        for s in d['standings']:
            if s['wiki']:
                used.setdefault(s['wiki'], s['name'])
        for t in d['teams']:
            for c in t['cars']:
                for dr in c['drivers']:
                    if dr['wiki']:
                        used.setdefault(dr['wiki'], dr['name'])
        for r in d['schedule']:
            if r.get('winner_wiki'):
                used.setdefault(r['winner_wiki'], r['winner'])

    # ---- driver bios
    qids = {t: (info.get(t) or {}).get('qid') for t in used}
    for t in list(qids):
        if not qids[t]:
            # canonical titles may not be keys in info (if they came via redirect) -> look up by value
            for k, v in info.items():
                if v.get('canon') == t and v.get('qid'):
                    qids[t] = v['qid']; break
    bios = build_bios({t: q for t, q in qids.items() if q}, used)
    for t in used:
        if t not in bios:
            bios[t] = {'name': used[t], 'birth_date': None, 'birth_place': None, 'state': None, 'country': None,
                       'qid': None}
    infobox_fallback(bios)
    with open(DRIVERS_OUT, 'w') as f:
        json.dump(dict(sorted(bios.items())), f, indent=1, ensure_ascii=False)

    validate_and_report(bios)


def validate_and_report(bios):
    print(f"\n{'series':<15}{'year':>5}{'teams':>7}{'cars':>6}{'stand':>7}{'sched':>7}{'winners':>8}{'dates':>6}"
          f"{'tracks':>7}{'city':>5}  notes")
    tot = 0
    for folder, series in ((OUT_X, 'stock_national'), (OUT_T, 'truck_series')):
        for y in YEARS:
            p = os.path.join(folder, f'{y}.json')
            d = json.load(open(p))  # validates JSON
            assert d['series'] == series and d['year'] == y
            sc = d['schedule']
            cars = sum(len(t['cars']) for t in d['teams'])
            print(f"{series:<15}{y:>5}{len(d['teams']):>7}{cars:>6}{len(d['standings']):>7}{len(sc):>7}"
                  f"{sum(1 for r in sc if r['winner']):>8}{sum(1 for r in sc if r['date']):>6}"
                  f"{sum(1 for r in sc if r['track']):>7}{sum(1 for r in sc if r['city']):>5}  "
                  f"{'; '.join(d.get('notes', []))[:90]}")
            tot += 1
    json.load(open(DRIVERS_OUT))
    n = len(bios)
    bd = sum(1 for b in bios.values() if b['birth_date'])
    st = sum(1 for b in bios.values() if b['state'])
    co = sum(1 for b in bios.values() if b['country'])
    qd = sum(1 for b in bios.values() if b['qid'])
    print(f'\n{tot} season files OK. drivers: {n}; qid {qd} ({qd / n:.0%}), birth_date {bd} ({bd / n:.0%}), '
          f'state {st} ({st / n:.0%}), country {co} ({co / n:.0%})')


if __name__ == '__main__':
    main()
