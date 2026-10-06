"""Realism settings (OOTP: "everything is a setting").

Each multiplier scales one part of the simulation; 1.0 is the calibrated default. They can be
changed at any time from the Settings page and apply from the next race or off-season.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..util import clamp

if TYPE_CHECKING:
    from .world import World

DEFAULTS = {
    "crashes": 1.0,       # crash cautions and wrecks
    "failures": 1.0,      # mechanical failures
    "injuries": 1.0,      # injury chance in crashes
    "development": 1.0,   # how fast young drivers grow
    "scouting": 1.0,      # scouting accuracy (higher = sharper reports)
    "luck": 1.0,          # race-to-race randomness
    "weather": 1.0,       # 0 turns rain-outs, wet races and heat off
}
LABELS = {
    "crashes": ("Crashes", "How often cars crash: cautions, wrecks and big ones."),
    "failures": ("Mechanical failures", "Engines, transmissions and parts that let go."),
    "injuries": ("Injuries", "How often a crash hurts the driver."),
    "development": ("Development speed", "How fast young drivers grow toward their potential."),
    "scouting": ("Scouting accuracy", "How close scouting reports come to the truth."),
    "luck": ("Race luck", "Randomness from race to race; lower makes the best car win more often."),
    "weather": ("Weather", "Rain-outs, rain-shortened races, wet road courses and hot days (0 = off)."),
}
RANGE = (0.0, 2.0)


def get(world: "World", key: str) -> float:
    s = world.__dict__.get("settings") or {}
    return float(s.get(key, DEFAULTS[key]))


def all_settings(world: "World") -> dict:
    return {k: get(world, k) for k in DEFAULTS}


def update(world: "World", values: dict) -> dict:
    cur = dict(world.__dict__.get("settings") or {})
    for k, v in values.items():
        if k not in DEFAULTS:
            raise ValueError(f"unknown setting {k}")
        if not isinstance(v, (int, float)):
            raise ValueError(f"{k} must be a number")
        lo = 0.0 if k == "weather" else 0.25
        cur[k] = round(clamp(float(v), lo, RANGE[1]), 2)
    world.settings = cur
    return all_settings(world)


def view(world: "World") -> list[dict]:
    return [{"key": k, "label": LABELS[k][0], "about": LABELS[k][1], "value": get(world, k),
             "min": 0.0 if k == "weather" else 0.25, "max": RANGE[1]} for k in DEFAULTS]
