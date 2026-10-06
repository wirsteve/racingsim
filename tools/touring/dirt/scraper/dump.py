import wiki, sys, re
titles = sys.argv[1:]
res = wiki.pages(titles)
for t in titles:
    p = res.get(t)
    if not p: print("MISSING", t); continue
    open('../cache/txt/' + p['title'].replace(' ', '_').replace('/', '_') + '.txt', 'w').write(p['wikitext'])
    secs = re.findall(r"^(={2,4}[^=].*?)\s*$", p['wikitext'], re.M)
    print("==", t, "->", p['title'], len(p['wikitext']), "|", " / ".join(s.strip("= ") for s in secs)[:600], flush=True)
print(wiki.STATS)
