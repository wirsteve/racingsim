"""Merge research outputs into the repository's knowledge layer.

    python tools/knowledge/merge.py STAGING_DIR [STAGING_DIR ...]

Each staging dir may contain any of: sources.json, ledger.jsonl, unavailable.json,
sanctioning_bodies.json, car_classes.json, series.json, career_paths.json,
career_stages.json, transitions.json, advancement_factors.json, economics.json,
datasets.json, tracks_new.json / venues.json ({"new": [...]}), tracks_enrich.json.

What it does
* ids are canonicalised (``series:ARCA_Menards`` -> ``series:arca-menards``); entities
  with the same normalised name are merged and every reference is rewritten;
* ranged facts from several sources are merged by confidence: the higher-confidence
  value wins; equal confidence with overlapping ranges -> union of the ranges and
  their sources; disagreements are kept in ``data/knowledge/merge_log.json``;
* new tracks are validated against the track schema and de-duplicated against the
  existing database and each other (normalised name/alias in the same state, or
  within 1.5 km with a shared name token) before landing in
  ``data/tracks/census_venues.json``; facts about existing tracks go to
  ``data/track_enrich.json``.
Existing knowledge files are inputs too, so merging is incremental and idempotent.
"""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
KDIR = ROOT / "data" / "knowledge"
ENTITY_FILES = ["sanctioning_bodies.json", "car_classes.json", "series.json", "career_paths.json",
                "career_stages.json", "transitions.json", "advancement_factors.json", "economics.json",
                "datasets.json"]
CONF_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}
FACT_KEYS = {"min", "max", "value", "category"}
REF_PREFIXES = ("series:", "body:", "class:", "path:", "stage:", "factor:", "src:", "track:", "driver:", "econ:")


# ------------------------------------------------------------------ helpers
def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def canon_id(x: str) -> str:
    if not isinstance(x, str) or ":" not in x:
        return x
    prefix, rest = x.split(":", 1)
    if prefix not in {p.rstrip(":") for p in REF_PREFIXES}:
        return x
    if prefix in ("track", "driver"):
        return x  # track ids / wiki titles are already canonical
    rest = unicodedata.normalize("NFKD", rest).encode("ascii", "ignore").decode().lower()
    rest = re.sub(r"[^a-z0-9.]+", "-", rest).strip("-")
    return f"{prefix}:{rest}"


def load(path: Path):
    if not path.exists():
        return None
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(path.read_text(encoding="utf-8"))


def items(data) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, dict):
        if "new" in data and isinstance(data["new"], list):
            return data["new"]
        out = []
        for k, v in data.items():
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("id", k)
                out.append(v)
        return out
    return [x for x in data if isinstance(x, dict)]


def flatten_economics(raw) -> list[dict]:
    """economics.json may be {topic: [entries]}: flatten to entries with ids and topics."""
    if not isinstance(raw, dict) or not any(isinstance(v, list) for v in raw.values()):
        return items(raw)
    out = []
    for topic, entries in raw.items():
        if topic.startswith("_") or not isinstance(entries, list):
            continue
        for i, e in enumerate(entries):
            if not isinstance(e, dict):
                continue
            subject = e.get("series") or e.get("tier") or e.get("flow") or e.get("level") or i
            e = dict(e, topic=topic, level=e.get("level") or e.get("tier") or e.get("series"))
            e["id"] = canon_id(f"econ:{topic}-{str(subject).replace('series:', '')}")
            out.append(e)
    return out


def is_fact(v) -> bool:
    return isinstance(v, dict) and bool(FACT_KEYS & set(v))


def rewrite(obj, alias: dict):
    """Canonicalise every id-looking string and apply the alias map, recursively."""
    if isinstance(obj, str):
        c = canon_id(obj) if obj.startswith(REF_PREFIXES) else obj
        return alias.get(c, c)
    if isinstance(obj, list):
        return [rewrite(x, alias) for x in obj]
    if isinstance(obj, dict):
        return {k: rewrite(v, alias) for k, v in obj.items()}
    return obj


# ------------------------------------------------------------------ entity merge
class Merger:
    def __init__(self):
        self.log: list[dict] = []

    def merge_fact(self, eid: str, attr: str, a: dict, b: dict) -> dict:
        ra, rb = CONF_RANK.get(a.get("confidence")), CONF_RANK.get(b.get("confidence"))
        a_lo, a_hi = _bounds(a)
        b_lo, b_hi = _bounds(b)
        disjoint = None not in (a_lo, a_hi, b_lo, b_hi) and (a_hi < b_lo or b_hi < a_lo)
        if disjoint or a.get("category", b.get("category")) != b.get("category", a.get("category")):
            self.log.append({"entity": eid, "attribute": attr, "kept": a if ra >= rb else b,
                             "other": b if ra >= rb else a, "reason": "conflicting values"})
        if ra != rb:
            win = dict(a if ra > rb else b)
            win["sources"] = _union(win.get("sources"), (b if ra > rb else a).get("sources"))
            return win
        if disjoint or None in (a_lo, a_hi, b_lo, b_hi):
            out = dict(a)
            out["sources"] = _union(a.get("sources"), b.get("sources"))
            return out
        out = dict(a)
        if "min" in a or "min" in b:
            out["min"], out["max"] = min(a_lo, b_lo), max(a_hi, b_hi)
            out.pop("value", None) if out["min"] != out["max"] else None
        out["sources"] = _union(a.get("sources"), b.get("sources"))
        out["notes"] = "; ".join(x for x in (a.get("notes"), b.get("notes")) if x) or None
        return out

    def merge_entity(self, a: dict, b: dict, path: str = "") -> dict:
        out = dict(a)
        for k, vb in b.items():
            va = out.get(k)
            key = f"{path}{k}"
            if va is None or va == "" or va == []:
                out[k] = vb
            elif is_fact(va) and is_fact(vb):
                out[k] = self.merge_fact(a.get("id", "?"), key, va, vb)
            elif isinstance(va, list) and isinstance(vb, list):
                if all(isinstance(x, (str, int, float)) for x in va + vb):
                    out[k] = _union(va, vb)
                elif k == "steps":
                    out[k] = va if len(va) >= len(vb) else vb
                else:
                    out[k] = va + [x for x in vb if x not in va]
            elif isinstance(va, dict) and isinstance(vb, dict):
                out[k] = self.merge_entity(va, vb, key + ".")
            elif k == "confidence":
                out[k] = va if CONF_RANK.get(va, 0) >= CONF_RANK.get(vb, 0) else vb
            elif va != vb and k not in ("id",):
                if isinstance(va, str) and isinstance(vb, str) and len(vb) > len(va) and k in ("description", "notes"):
                    out[k] = vb
                elif not isinstance(va, (dict, list)):
                    self.log.append({"entity": a.get("id"), "attribute": key, "kept": va, "other": vb,
                                     "reason": "different text values"})
        return out


def _bounds(f: dict):
    lo = f.get("min", f.get("value"))
    hi = f.get("max", f.get("value"))
    num = lambda x: x if isinstance(x, (int, float)) and not isinstance(x, bool) else None  # noqa: E731
    return num(lo), num(hi)


def _union(a, b) -> list:
    out = []
    for x in (a or []) + (b or []):
        if x not in out:
            out.append(x)
    return out


def merge_entities(groups: dict[str, list[list[dict]]], merger: Merger) -> tuple[dict, dict]:
    """groups: file -> list of item lists. Returns (file -> merged items, alias map)."""
    alias: dict[str, str] = dict(load(KDIR / "aliases.json") or {})  # curated id equivalences
    merged: dict[str, dict[str, dict]] = {}
    for fname, lists in groups.items():
        by_id: dict[str, dict] = {}
        by_name: dict[str, str] = {}
        for lst in lists:
            for e in lst:
                e = rewrite(e, {})
                eid = e.get("id") or (f"econ:{norm_text(e.get('topic', ''))}-{norm_text(e.get('level', ''))}"
                                      if fname == "economics.json" else e.get("name"))
                if fname == "transitions.json":
                    eid = f"{e.get('from')}->{e.get('to')}"
                if fname == "datasets.json":
                    eid = norm_text(e.get("name") or e.get("url"))
                if not eid:
                    continue
                e["id"] = e.get("id") or eid if fname not in ("transitions.json", "datasets.json") else e.get("id")
                nkey = norm_text(e.get("name")) if fname not in ("transitions.json", "economics.json", "datasets.json") else None
                target = eid if eid in by_id else by_name.get(nkey) if nkey else None
                if target and target != eid:
                    alias[eid] = target
                if target:
                    by_id[target] = merger.merge_entity(by_id[target], e)
                else:
                    by_id[eid] = e
                    if nkey:
                        by_name[nkey] = eid
        merged[fname] = by_id
    for fname in merged:
        merged[fname] = {k: rewrite(v, alias) for k, v in merged[fname].items()}
        for v in merged[fname].values():
            if "id" in v and v["id"] in alias:
                v["id"] = alias[v["id"]]
    return merged, alias


# ------------------------------------------------------------------ tracks
def _km(a, b) -> float:
    if None in (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon")):
        return 1e9
    dlat = math.radians(b["lat"] - a["lat"])
    dlon = math.radians(b["lon"] - a["lon"]) * math.cos(math.radians(a["lat"]))
    return 6371 * math.hypot(dlat, dlon)


GENERIC = {"speedway", "raceway", "motor", "motorsports", "park", "the", "track", "race", "international",
           "fairgrounds", "county", "dirt", "oval", "of", "at", "and", "motorplex", "complex", "center"}


def _tok(name: str) -> set[str]:
    return {t for t in norm_text(name).split() if t not in GENERIC and len(t) > 1}


def _clean_numbers(c: dict) -> None:
    """Numeric facts sometimes arrive as text ("12-24", "0.5 mi"): keep the first number, note the text."""
    for k, cast in (("banking_deg_turns", float), ("banking_deg_straights", float), ("length_mi", float),
                    ("opened", int), ("closed", int), ("turns", int)):
        v = c.get(k)
        if v is None or isinstance(v, (int, float)) and not isinstance(v, bool):
            continue
        m = re.search(r"\d+(?:\.\d+)?", str(v))
        c[k] = cast(float(m.group())) if m else None
        if m and str(v).strip() != m.group():
            c["notable_note"] = "; ".join(x for x in (c.get("notable_note"), f"{k}: {v}") if x)


def merge_tracks(candidates: list[dict], existing: list[dict], merger: Merger) -> tuple[list[dict], dict]:
    from racingsim.tracks.model import TrackFacts
    ex_index = []
    for t in existing:
        names = [t["name"]] + list(t.get("aliases") or [])
        ex_index.append((t, {norm_text(n) for n in names}, set().union(*[_tok(n) for n in names])))
    kept: list[dict] = []
    enrich: dict[str, dict] = {}
    rejected = 0
    for c in candidates:
        c = {k: v for k, v in c.items() if k not in ("existing_id",)}
        if not c.get("name") or c.get("lat") is None or c.get("lon") is None:
            rejected += 1
            continue
        _clean_numbers(c)
        c.setdefault("country", "USA")
        c.setdefault("track_type", "oval")
        c.setdefault("level", "local")
        if c.get("surface") == "clay":
            c["surface"] = "dirt"
        f = TrackFacts.from_dict(c)
        if f.validate():
            merger.log.append({"entity": c["name"], "reason": "rejected track: " + "; ".join(f.validate())})
            rejected += 1
            continue
        names = {norm_text(c["name"])} | {norm_text(a) for a in c.get("aliases") or []}
        toks = set().union(*[_tok(n) for n in [c["name"]] + list(c.get("aliases") or [])])
        match = None
        for t, tnames, ttoks in ex_index:
            same_state = (t.get("region") or "") == (c.get("region") or "")
            near = _km(t, c) < 1.5 if t.get("lat") is not None else False
            if (names & tnames and (same_state or near)) or (near and toks & ttoks):
                if (t.get("surface") or "asphalt") == (c.get("surface") or t.get("surface") or "asphalt") \
                        or (names & tnames):
                    match = t
                    break
        if match is not None:
            e = enrich.setdefault(match["id"], {"aliases": [], "major_series": [], "sources": []})
            for n in [c["name"]] + list(c.get("aliases") or []):
                if norm_text(n) not in {norm_text(x) for x in [match["name"]] + list(match.get("aliases") or []) + e["aliases"]}:
                    e["aliases"].append(n)
            e["major_series"] = _union(e["major_series"], c.get("major_series"))
            e["sources"] = _union(e["sources"], c.get("sources"))
            for k in ("banking_category", "prestige_category", "closed", "active", "opened"):
                if c.get(k) is not None and match.get(k) is None:
                    e.setdefault(k, c[k])
            continue
        dup = next((k for k in kept if (names & ({norm_text(k["name"])} | {norm_text(a) for a in k.get("aliases") or []})
                                         and (k.get("region") == c.get("region")))
                    or (_km(k, c) < 1.5 and toks & _tok(k["name"]) and k.get("surface") == c.get("surface"))), None)
        if dup is not None:
            merged = merger.merge_entity(dup, c)
            kept[kept.index(dup)] = merged
        else:
            kept.append(c)
    print(f"tracks: {len(kept)} new, {len(enrich)} existing enriched, {rejected} rejected")
    return kept, enrich


# ------------------------------------------------------------------ main
def main(staging: list[Path]) -> int:
    merger = Merger()
    groups: dict[str, list[list[dict]]] = {f: [items(load(KDIR / f))] for f in ENTITY_FILES}
    sources = load(KDIR / "sources.json") or {}
    ledger = load(KDIR / "ledger.jsonl") or []
    unavailable = items(load(KDIR / "unavailable.json"))
    track_candidates: list[dict] = []
    track_enrich_in: list[dict] = []
    for d in staging:
        for f in ENTITY_FILES:
            raw = load(d / f)
            groups[f].append(flatten_economics(raw) if f == "economics.json" else items(raw))
        for k, v in (load(d / "sources.json") or {}).items():
            sources.setdefault(canon_id(k), v)
        ledger += load(d / "ledger.jsonl") or []
        unavailable += items(load(d / "unavailable.json"))
        for name in ("tracks_new.json", "venues.json", "tracks_wikidata.json", "tracks_osm_new.json"):
            track_candidates += items(load(d / name))
        track_enrich_in += items(load(d / "tracks_enrich.json"))
    merged, alias = merge_entities(groups, merger)
    # Curated field overrides (persisted): e.g. which game rung / history source a series uses.
    overrides = load(KDIR / "overrides.json") or {}
    for d in staging:
        for k, v in (load(d / "overrides.json") or {}).items():
            overrides.setdefault(canon_id(k), {}).update(v)
    for eid, fields in overrides.items():
        e = merged["series.json"].get(alias.get(eid, eid))
        if e is not None:
            e.update(fields)
    (KDIR / "overrides.json").write_text(json.dumps(dict(sorted(overrides.items())), indent=1), encoding="utf-8")
    KDIR.mkdir(parents=True, exist_ok=True)
    for f, by_id in merged.items():
        rows = sorted(by_id.values(), key=lambda e: str(e.get("id") or e.get("name")))
        (KDIR / f).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    (KDIR / "sources.json").write_text(json.dumps(dict(sorted(sources.items())), indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    seen, led = set(), []
    for e in ledger:
        e = rewrite(e, alias)
        k = (e.get("source"), e.get("url"), e.get("info"))
        if k not in seen:
            seen.add(k)
            led.append(e)
    (KDIR / "ledger.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in led), encoding="utf-8")
    seen, un = set(), []
    for u in unavailable:
        k = (norm_text(u.get("source")), norm_text(u.get("reason"))[:40])
        if k not in seen:
            seen.add(k)
            un.append(u)
    (KDIR / "unavailable.json").write_text(json.dumps(un, indent=1, ensure_ascii=False), encoding="utf-8")

    if track_candidates or track_enrich_in:
        from racingsim.tracks.database import TrackDatabase
        census_path = ROOT / "data" / "tracks" / "census_venues.json"
        prior = json.loads(census_path.read_text()) if census_path.exists() else []
        db = TrackDatabase.load()
        existing = [dict(id=t.id, name=t.facts.name, region=t.facts.region, lat=t.facts.lat, lon=t.facts.lon,
                         aliases=t.facts.aliases, surface=t.facts.surface, closed=t.facts.closed, active=t.facts.active,
                         opened=t.facts.opened, banking_category=t.facts.banking_category,
                         prestige_category=t.facts.prestige_category)
                    for t in db if t.facts.name not in {p["name"] for p in prior}]
        new, enrich = merge_tracks(prior + track_candidates, existing, merger)
        census_path.write_text(json.dumps(sorted(new, key=lambda t: (t.get("region") or "", t["name"])), indent=1,
                                          ensure_ascii=False), encoding="utf-8")
        enrich_path = ROOT / "data" / "track_enrich.json"
        old = json.loads(enrich_path.read_text()) if enrich_path.exists() else {}
        for e in track_enrich_in:
            tid = e.get("id") or e.get("existing_id")
            if tid:
                cur = old.setdefault(tid, {})
                for k, v in e.items():
                    if k in ("id", "existing_id"):
                        continue
                    cur[k] = _union(cur.get(k), v) if isinstance(v, list) else cur.get(k, v)
        for tid, e in enrich.items():
            cur = old.setdefault(tid, {})
            for k, v in e.items():
                cur[k] = _union(cur.get(k), v) if isinstance(v, list) else cur.get(k, v)
        enrich_path.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")
    (KDIR / "merge_log.json").write_text(json.dumps(merger.log, indent=1, ensure_ascii=False, default=str),
                                         encoding="utf-8")
    counts = {f: len(v) for f, v in merged.items()}
    print(json.dumps(counts), f"sources={len(sources)} ledger={len(led)} unavailable={len(un)} "
          f"aliases={len(alias)} merge_log={len(merger.log)}")
    return 0


if __name__ == "__main__":
    sys.exit(main([Path(p) for p in sys.argv[1:]]))
