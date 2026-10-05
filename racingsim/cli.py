"""Command-line entry point.

    python -m racingsim simulate --years 10 --seed 7
    python -m racingsim tracks --region WI
    python -m racingsim track "Slinger Speedway"
    python -m racingsim export-tracks tracks.sqlite
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .reports import archetype_counts, career_story, cohort_outcomes, find_stories, funnel
from .tracks import TrackDatabase
from .world.world import World, WorldConfig


def _money(x: float) -> str:
    return f"${x / 1e6:.1f}M" if x >= 1e6 else f"${x / 1e3:.0f}k"


def cmd_simulate(args: argparse.Namespace) -> int:
    t0 = time.time()
    world = World.generate(WorldConfig(seed=args.seed, population_scale=args.scale))
    print(f"Generated {len(world.drivers):,} drivers, {len(world.teams)} teams, "
          f"{len(world.pyramid.series)} championships on {len(world.tracks)} real tracks "
          f"({time.time() - t0:.1f}s)")
    for _ in range(args.years):
        s = world.run_year()
        print(f"  {s.year}: entrants {s.new_entrants:4d}  retirements {s.retirements:4d}  "
              f"promotions {s.promotions:3d}  first premier rides {len(s.first_top_tier)}")
    print("\nPyramid after", args.years, "seasons:")
    print(f"  {'tier':<24}{'drivers':>8}{'age p10/med/p90':>18}{'ability':>9}{'funding':>10}")
    for row in funnel(world):
        print(f"  {row['tier']} {row['name']:<22}{row['drivers']:>8}"
              f"{row['age_p10']:>8.0f}/{row['age_median']:.0f}/{row['age_p90']:.0f}"
              f"{row['ability_median']:>9.1f}{_money(row['funding_median']):>10}")
    co = cohort_outcomes(world)
    print("\nShare of everyone who ever raced that reached each level:")
    print("  " + "  ".join(f"T{t}:{v * 100:.2f}%" for t, v in co["share_reaching_tier"].items()))
    print("\nEmergent career archetypes (counts):")
    for k, v in archetype_counts(world).items():
        print(f"  {k:<38}{v}")
    if args.stories:
        print("\nSample careers:")
        for kind, drivers in find_stories(world, per_type=1).items():
            for d in drivers:
                print(f"\n[{kind}]\n{career_story(world, d)}")
    return 0


def cmd_tracks(args: argparse.Namespace) -> int:
    db = TrackDatabase.load()
    rows = [t for t in db if (not args.region or t.facts.region == args.region)
            and (not args.country or t.facts.country == args.country)]
    rows.sort(key=lambda t: (t.facts.country, t.facts.region or "", t.name))
    for t in rows:
        f = t.facts
        length = f"{f.length_mi:.3f} mi" if f.length_mi else "?"
        print(f"{f.country} {f.region or '--':<3} {t.name:<45} {f.surface:<16} {t.profile.size_class:<18} "
              f"{length:>10} {f.level:<9}{'' if f.is_active else ' (inactive)'}")
    print(f"\n{len(rows)} tracks")
    return 0


def cmd_track(args: argparse.Namespace) -> int:
    db = TrackDatabase.load()
    q = args.name.lower()
    matches = [t for t in db if q in t.name.lower() or any(q in a.lower() for a in t.facts.aliases)]
    for t in matches:
        d = t.to_dict()
        print(f"== {t.name}")
        print("  FACTS (sourced):")
        for k, v in d["facts"].items():
            print(f"    {k}: {v}")
        print("  PROFILE (game-derived):")
        for k, v in d["profile"].items():
            print(f"    {k}: {v}")
        print("  SIM RATINGS (internal game model, not official specs):")
        for k, v in d["sim"].items():
            print(f"    {k}: {v}")
    return 0 if matches else 1


def cmd_export(args: argparse.Namespace) -> int:
    db = TrackDatabase.load()
    db.save_sqlite(Path(args.path))
    print(f"wrote {len(db)} tracks to {args.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="racingsim")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("simulate", help="generate a world and simulate seasons")
    s.add_argument("--years", type=int, default=10)
    s.add_argument("--seed", type=int, default=2026)
    s.add_argument("--scale", type=float, default=1.0, help="grassroots population scale")
    s.add_argument("--stories", action="store_true", help="print sample emergent careers")
    s.set_defaults(func=cmd_simulate)
    t = sub.add_parser("tracks", help="list tracks")
    t.add_argument("--region")
    t.add_argument("--country")
    t.set_defaults(func=cmd_tracks)
    one = sub.add_parser("track", help="show one track's facts, profile and sim ratings")
    one.add_argument("name")
    one.set_defaults(func=cmd_track)
    e = sub.add_parser("export-tracks", help="persist the track database to SQLite")
    e.add_argument("path")
    e.set_defaults(func=cmd_export)
    args = p.parse_args(argv)
    return args.func(args)
