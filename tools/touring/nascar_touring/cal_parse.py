import re, html, json
def txt(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()
def parse(path):
    h = open(path, encoding='utf-8', errors='replace').read()
    out = {}
    secs = list(re.finditer(r'<a name="(\d{4})"></a>', h))
    for i, m in enumerate(secs):
        y = int(m.group(1))
        body = h[m.end(): secs[i + 1].start() if i + 1 < len(secs) else len(h)]
        tm = re.search(r'<table border=1>(.*?)</table>', body, re.S)
        if not tm:
            continue
        rows = re.findall(r'<tr>(.*?)</tr>', tm.group(1), re.S)
        hdr = [txt(c) for c in re.findall(r'<th>(.*?)</th>', rows[0], re.S)]
        races = []
        for r in rows[1:]:
            cells = [txt(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)]
            div = None
            if len(cells) == len(hdr) + 1:
                div, cells = cells[1], [cells[0]] + cells[2:]
            d = dict(zip(hdr, cells))
            races.append(dict(date=d.get('Date'), division=div, race=d.get('Race'), track=d.get('Track'),
                              pole=d.get('Pole'), winner=d.get('Winner'), make=d.get("Winner's Make")))
        out[y] = races
    return out
if __name__ == '__main__':
    res = {}
    for n in ['hootersprocupseries', 'usaracingprocupseries', 'revoilprocupseries']:
        p = f'dl_other/cal_{n}.html' if n != 'hootersprocupseries' else 'dl_other/cal_procup.html'
        for y, rs in parse(p).items():
            res[y] = dict(page=n, races=rs)
    json.dump(res, open('dl_other/cal_parsed.json', 'w'), indent=0)
    for y, v in sorted(res.items()):
        from collections import Counter
        print(y, v['page'], len(v['races']), Counter(r['division'] for r in v['races']))
