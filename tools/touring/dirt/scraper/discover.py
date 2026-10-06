"""Discover season articles via prefix search + categories + intitle search."""
import json, wiki, sys
found = set()
for y in range(1995, 2027):
    for p in ["World of Outlaws", "USAC", "Lucas Oil", "Super DIRTcar", "All Star", "High Limit", "POWRi", "DIRTcar"]:
        for t in wiki.prefix(f"{y} {p}", 50):
            found.add(t)
    print(y, len(found), flush=True)
for c in ['Category:World of Outlaws Sprint Car seasons', 'Category:World of Outlaws Late Model Series seasons', 'Category:United States Auto Club']:
    found.update(t for t in wiki.category(c) if t[:4].isdigit())
json.dump(sorted(found), open('../cache/season_titles.json', 'w'), indent=0)
print("\n".join(sorted(found)))
