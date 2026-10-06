"""Pack the per-season result files into data/results/<source>.jsonl.gz (one race per line)."""
import glob
import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "data", "results"))
os.makedirs(OUT, exist_ok=True)
for ser, src in (("cup", "nascar_cup"), ("nxs", "nascar_xfinity"), ("truck", "nascar_trucks")):
    files = sorted(glob.glob(os.path.join(HERE, "results", f"nascardata_{ser}", "*.json")),
                   key=lambda p: int(os.path.basename(p)[:-5]))
    with gzip.open(os.path.join(OUT, f"{src}.jsonl.gz"), "wt", encoding="utf-8", compresslevel=9) as out:
        for f in files:
            d = json.load(open(f, encoding="utf-8"))
            for r in d["races"]:
                rec = {"source": src, "year": d["year"],
                       **{k: v for k, v in r.items() if k not in ("race_name_source", "repo_schedule_match")}}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(src, len(files), "seasons")
