"""One entry point for compiling the game database.

    python -m racingsim data build      # compile data/racingsim.db (only if inputs changed; --force to rebuild)
    python -m racingsim data validate   # schema, referential and cross-source checks
    python -m racingsim data report     # counts and confidence by category (writes docs/DATA_REPORT.md)
    python -m racingsim data update     # re-run the source scrapers/ingesters, then build
"""

from __future__ import annotations

from pathlib import Path

from ..paths import DATA_DIR, DB_PATH

HISTORY_DIR = DATA_DIR / "history"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"


def inputs() -> list[Path]:
    here = Path(__file__).resolve().parent
    hist = here.parent / "history"
    files = [hist / "db.py", hist / "store.py", here / "build.py",
             DATA_DIR / "track_years.json", DATA_DIR / "track_rating_overrides.json"]
    files += sorted((DATA_DIR / "tracks").glob("*.json"))
    files += sorted(KNOWLEDGE_DIR.glob("*.json*")) if KNOWLEDGE_DIR.exists() else []
    files += sorted((DATA_DIR / "results").glob("*.jsonl.gz"))
    return files


def current_stamp() -> str:
    from ..history import store
    return store.inputs_stamp(HISTORY_DIR, inputs())


def is_stale(target: Path = DB_PATH) -> bool:
    from ..history import store
    return store.stored_stamp(target) != current_stamp()


def build_database(target: Path = DB_PATH, force: bool = False) -> Path:
    """Compile history + knowledge + tracks into ``target`` if anything changed."""
    from ..history import store
    from ..tracks.database import TrackDatabase
    if not force and not is_stale(target):
        return target
    with store._LOCK:
        store.build(HISTORY_DIR, target, TrackDatabase.load(), stamp=current_stamp(),
                    knowledge_dir=KNOWLEDGE_DIR).close()
    return target
