import re, html, json, sys, os
ROW = re.compile(r'<tr><td><A HREF="race\.php\?raceid=(\d+)">([^<]*)</a>.*?</td>\s*<td[^>]*>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td></tr>', re.S | re.I)
def txt(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip(' ,')
def parse(path):
    h = open(path, encoding='latin-1').read()
    out = []
    for m in ROW.finditer(h):
        rid, date, race, trk, ser, win = m.groups()
        tid = re.search(r'trackid=(\d+)', trk)
        tname = txt(re.search(r'>([^<]*)</a>', trk).group(1)) if '</a>' in trk.lower() else txt(trk)
        rest = txt(re.sub(r'<A[^>]*>[^<]*</a>', '', trk, flags=re.I))
        parts = [p.strip() for p in rest.split(',') if p.strip()]
        while len(parts) > 2 and parts[-1] in ('Canada', 'USA', 'United States', 'Mexico'):
            parts = parts[:-1]
        city = parts[0] if parts else None
        state = parts[-1] if len(parts) > 1 else None
        wins = [txt(x) for x in re.findall(r'<A[^>]*>(.*?)</a>', win, re.I)] or [txt(win)]
        wids = re.findall(r'uniqid=(\d+)', win)
        out.append(dict(raceid=int(rid), date=txt(date), race=txt(race) or None, track=tname, trackid=int(tid.group(1)) if tid else None,
                        city=city, state=state, series=txt(ser), winners=[w for w in wins if w], winner_ids=wids))
    return out
if __name__ == '__main__':
    from collections import Counter
    allr = {}
    for y in range(1995, 2015):
        allr[y] = parse(f'dl_urh/y{y}.html')
    json.dump(allr, open('dl_urh/parsed.json', 'w'), indent=0)
    c = Counter()
    for y, rs in allr.items():
        for r in rs:
            c[(r['series'])] += 1
    for k, v in sorted(c.items()):
        if re.search(r'NASCAR|USAR|Pro Cup|Hooters|All Pro|Southwest|Northwest|Southeast|Midwest|Elite|Dash|Goody|AutoZone|Featherlite|Slim', k, re.I):
            yrs = sorted({y for y, rs in allr.items() for r in rs if r['series'] == k})
            print(v, k, yrs[0], yrs[-1], len(yrs))
    print(sum(len(v) for v in allr.values()))
