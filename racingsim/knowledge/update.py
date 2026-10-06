"""Re-run the data ingesters listed in ``tools/ingest/registry.json``.

Each entry: ``{"name", "cwd" (relative to the repo), "cmd" [argv], "copy": [{"from", "to"}]}``.
Ingesters cache their downloads, respect robots.txt and rate limits, and write JSON in
the repository formats; ``copy`` moves their outputs into ``data/``. A failing ingester
(network down, source blocked) is reported and skipped; the rest still run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / "tools" / "ingest" / "registry.json"


def run_updates(only: str | None = None) -> list[tuple[str, bool]]:
    if not REGISTRY.exists():
        print("no ingest registry found")
        return []
    results = []
    for entry in json.loads(REGISTRY.read_text()):
        if only and only not in entry["name"]:
            continue
        cwd = ROOT / entry.get("cwd", ".")
        cmd = [sys.executable if c == "python" else c for c in entry["cmd"]]
        print(f"== {entry['name']}: {' '.join(entry['cmd'])}")
        try:
            subprocess.run(cmd, cwd=cwd, check=True, timeout=entry.get("timeout", 7200))
            for c in entry.get("copy", []):
                src, dst = cwd / c["from"], ROOT / c["to"]
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                elif src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            results.append((entry["name"], True))
        except (subprocess.SubprocessError, OSError) as e:
            print(f"   skipped: {e}")
            results.append((entry["name"], False))
    return results
