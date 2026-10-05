"""Track database: loads factual records, derives game layers, persists to SQLite.

Factual source files live in ``data/tracks/*.json`` (one JSON array per file).
Game-derived layers are rebuilt from facts + ``data/track_rating_overrides.json``
so the factual layer is never polluted by simulation tuning.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Iterator, Optional

from ..util import DATA_DIR, haversine_mi
from .model import SIM_RATING_FIELDS, Track, TrackFacts
from .ratings import build_track


class TrackDatabase:
    def __init__(self, tracks: Iterable[Track]):
        self._tracks: dict[str, Track] = {}
        for t in tracks:
            if t.id in self._tracks:
                raise ValueError(f"duplicate track id {t.id}")
            self._tracks[t.id] = t

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, directory: Optional[Path] = None, overrides: Optional[dict] = None) -> "TrackDatabase":
        directory = directory or DATA_DIR / "tracks"
        facts: dict[str, TrackFacts] = {}
        for path in sorted(directory.glob("*.json")):
            with open(path, encoding="utf-8") as fh:
                for raw in json.load(fh):
                    f = TrackFacts.from_dict(raw)
                    problems = f.validate()
                    if problems:
                        raise ValueError(f"{path.name}: {f.name}: {'; '.join(problems)}")
                    if f.id in facts:
                        # Same venue present in two research files: keep the richer record.
                        if _richness(f) <= _richness(facts[f.id]):
                            continue
                    facts[f.id] = f
        return cls(build_track(f, overrides) for f in facts.values())

    # ------------------------------------------------------------------ queries
    def __len__(self) -> int:
        return len(self._tracks)

    def __iter__(self) -> Iterator[Track]:
        return iter(self._tracks.values())

    def __contains__(self, track_id: str) -> bool:
        return track_id in self._tracks

    def get(self, track_id: str) -> Track:
        return self._tracks[track_id]

    def active(self) -> list[Track]:
        return [t for t in self._tracks.values() if t.facts.active]

    def suitable(self, venue_key: str, *, levels: Optional[set[str]] = None,
                 regions: Optional[set[str]] = None, countries: Optional[set[str]] = None,
                 active_only: bool = True) -> list[Track]:
        out = []
        for t in self._tracks.values():
            if active_only and not t.facts.active:
                continue
            if venue_key not in t.profile.series_suitability:
                continue
            if levels and t.facts.level not in levels:
                continue
            if regions and t.facts.region not in regions:
                continue
            if countries and t.facts.country not in countries:
                continue
            out.append(t)
        return out

    def nearest(self, lat: float, lon: float, candidates: Optional[Iterable[Track]] = None,
                limit: int = 5) -> list[tuple[float, Track]]:
        pool = candidates if candidates is not None else self.active()
        scored = [
            (haversine_mi(lat, lon, t.facts.lat, t.facts.lon), t)
            for t in pool if t.facts.lat is not None and t.facts.lon is not None
        ]
        scored.sort(key=lambda x: x[0])
        return scored[:limit]

    def by_region(self) -> dict[str, list[Track]]:
        out: dict[str, list[Track]] = {}
        for t in self._tracks.values():
            out.setdefault(f"{t.facts.country}-{t.facts.region}", []).append(t)
        return out

    # -------------------------------------------------------------- persistence
    def save_sqlite(self, path: Path) -> None:
        """Persist as three tables: facts (sourced), profile and sim ratings (game-derived)."""
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.executescript(_SCHEMA)
            for t in self._tracks.values():
                f = t.facts
                cur.execute(
                    "INSERT OR REPLACE INTO track_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f.id, f.name, f.city, f.region, f.country, f.track_type, f.surface,
                     f.length_mi, f.configuration, f.turns, f.banking_deg_turns,
                     f.banking_deg_straights, f.opened, int(f.active), json.dumps(f.disciplines),
                     f.level, f.notable_note, json.dumps([f.lat, f.lon]), json.dumps(f.sources)),
                )
                p = t.profile
                cur.execute(
                    "INSERT OR REPLACE INTO track_profile VALUES (?,?,?,?,?,?)",
                    (f.id, p.size_class, p.prestige, p.attendance_potential,
                     json.dumps(asdict(p.weather)), json.dumps(p.series_suitability)),
                )
                cur.execute(
                    f"INSERT OR REPLACE INTO track_sim_ratings VALUES ({','.join('?' * (len(SIM_RATING_FIELDS) + 2))})",
                    (f.id, *[getattr(t.sim, k) for k in SIM_RATING_FIELDS], t.sim.derivation),
                )
            conn.commit()
        finally:
            conn.close()


def _richness(f: TrackFacts) -> int:
    return sum(v is not None for v in asdict(f).values()) + len(f.sources)


_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS track_facts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT, region TEXT, country TEXT NOT NULL,
    track_type TEXT NOT NULL, surface TEXT NOT NULL, length_mi REAL, configuration TEXT,
    turns INTEGER, banking_deg_turns REAL, banking_deg_straights REAL, opened INTEGER,
    active INTEGER NOT NULL, disciplines TEXT, level TEXT, notable_note TEXT, latlon TEXT,
    sources TEXT
);
CREATE TABLE IF NOT EXISTS track_profile (
    id TEXT PRIMARY KEY REFERENCES track_facts(id), size_class TEXT, prestige INTEGER,
    attendance_potential INTEGER, weather TEXT, series_suitability TEXT
);
CREATE TABLE IF NOT EXISTS track_sim_ratings (
    id TEXT PRIMARY KEY REFERENCES track_facts(id),
    {", ".join(f"{k} INTEGER" for k in SIM_RATING_FIELDS)},
    derivation TEXT
);
"""
