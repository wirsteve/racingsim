import re, html, json, glob, os
ROW = re.compile(r"<tr>\s*<td class='rc-table-date-td'><span class='no-wrap'>([^<]*)</span></td>.*?href='/circuit/([^']*)'[^>]*>([^<]*)</a>.*?</div>,\s*([^<]*)<br>\s*<span class='eventname'>(.*?)</span>(.*?)</tr>", re.S)
def txt(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()
def parse(path):
    h = open(path, encoding='utf-8', errors='replace').read()
    title = re.search(r'<h2 class="season-title[^"]*"><span class="season-title-year">(\d{4})</span>\s*(.*?)</h2>', h, re.S)
    out = []
    for m in ROW.finditer(h):
        date, slug, cname, country, ev, rest = m.groups()
        st = txt(rest)
        out.append(dict(date=txt(date), circuit_slug=slug, circuit=txt(cname), country=txt(country), event=txt(ev), status=st))
    return (txt(title.group(2)) if title else None), out
if __name__ == '__main__':
    res = {}
    for f in sorted(glob.glob('dl_rc/*_[12][0-9][0-9][0-9].html')):
        k = os.path.basename(f)[:-5]
        res[k] = parse(f)
    json.dump(res, open('dl_rc/parsed.json', 'w'), indent=0)
    for k, (t, rs) in res.items():
        print(k, t, len(rs), sorted({r['status'] for r in rs}))
