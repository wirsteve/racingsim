"""Step 1: crawl English Wikipedia motorsport-venue categories for USA/Canada/Mexico.

Output: raw/wp_category_pages.json  {title: [categories it was found in]}
"""
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from wp_common import wp_api_all, save

ROOTS = [
    "Category:Motorsport venues in the United States",
    "Category:Motorsport venues in Canada",
    "Category:Motorsport venues in Mexico",
    "Category:NASCAR tracks",
    "Category:IndyCar Series tracks",
    "Category:Champ Car circuits",
    "Category:ARCA Menards Series tracks",
    "Category:World of Outlaws tracks",
]
# subcategories that are out of scope for a car-racing career sim
EXCLUDE = re.compile(
    r"drag|motocross|off-road|horse|harness|greyhound|dog |motorcycle|supercross|bmx|cycling|velodrome|"
    r"speedway venues|people|events|races|templates|images|lists|by city|stubs|seasons|hydroplane|"
    r"boat|airfield|airport|rally|hill ?climb|stadiums? in|sports venues|ice racing|snowmobile",
    re.I,
)
MAX_DEPTH = 4


def main():
    pages = {}
    seen = set()
    queue = [(r, 0) for r in ROOTS]
    while queue:
        cat, depth = queue.pop(0)
        if cat in seen:
            continue
        seen.add(cat)
        print(depth, cat, flush=True)
        for d in wp_api_all({"action": "query", "list": "categorymembers", "cmtitle": cat,
                             "cmlimit": "500", "cmtype": "page|subcat"}):
            for m in d["query"]["categorymembers"]:
                t = m["title"]
                if m["ns"] == 14:
                    if depth < MAX_DEPTH and not EXCLUDE.search(t.replace("Category:", "")):
                        queue.append((t, depth + 1))
                elif m["ns"] == 0:
                    pages.setdefault(t, []).append(cat)
    save("wp_category_pages.json", pages)
    save("wp_categories_crawled.json", sorted(seen))
    print(len(pages), "pages from", len(seen), "categories")


if __name__ == "__main__":
    main()
