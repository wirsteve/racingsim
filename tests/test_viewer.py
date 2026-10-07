"""Race viewer: engine replay frames, the replay API, sim-to-race handing the race to the viewer."""

import random

from racingsim.sim import engine as E
from racingsim.sim.race import Entry


def test_replay_frames_are_consistent(tracks):
    from racingsim.world.world import World, WorldConfig
    w = World.generate(WorldConfig(seed=5, population_scale=0.12, start_year=2018), tracks=tracks)
    entries = [Entry([w.drivers[d]], t.equipment, team_id=t.id, car_key=f"{t.id}:{c}")
               for t in w.teams_in("cup_series") for c, d in enumerate(t.roster[:t.cars]) if d]
    r = E.run(entries, w.tracks.get("bristol-motor-speedway-tn"), 7, 0.6, random.Random(2), detail=True, stages=2)
    rp = r.replay
    assert rp and rp["laps"] == r.laps and len(rp["cars"]) == len(entries)
    laps = [f[0] for f in rp["frames"]]
    assert laps == sorted(laps) and laps[-1] == r.laps
    for lap, flag, rows in rp["frames"]:
        assert flag in ("G", "Y") and sorted(row[0] for row in rows) == list(range(len(entries)))
        running = [row[1] for row in rows if row[1] >= 0]
        assert running == sorted(running) and (not running or running[0] == 0)
    assert any(f[1] == "Y" for f in rp["frames"]) and any(row[2] == 1 for f in rp["frames"] for row in f[2])
    winner = r.finishes[0].entry.drivers[0].id
    assert rp["cars"][rp["finish"][0]]["id"] == winner
    assert E.run(entries, w.tracks.get("bristol-motor-speedway-tn"), 7, 0.6, random.Random(2)).replay is None


def test_sim_to_race_opens_the_viewer():
    from racingsim.game.session import Game
    from racingsim.ui import api
    g = Game.new("View", "Er", "NC", 22, "stock_car", "wealthy", seed=8, scale=0.12, start_year=2016)
    ran = g.sim_until("race")
    mine = [x for x in ran if x.get("player") and "replay" in x]
    assert mine
    info = mine[-1]
    rp = api.replay(g.world, info.get("jewel") or info["series_id"], info["event"])
    assert rp and any(c["me"] for c in rp["replay"]["cars"])
    nums = [c["num"] for c in rp["replay"]["cars"]]
    assert len(set(nums)) == len(nums) and all(1 <= n <= 99 for n in nums)
    assert api.race_result(g.world, info.get("jewel") or info["series_id"], info["event"])["has_replay"]
    assert api.replay(g.world, "nope", 0) is None
