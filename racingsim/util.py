"""Small shared helpers: clamping, distances, weighted choice, data paths."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json(relative: str):
    with open(DATA_DIR / relative, encoding="utf-8") as fh:
        return json.load(fh)


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return lo if value < lo else hi if value > hi else value


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def logistic(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def weighted_choice(rng: random.Random, items: Sequence[T], weights: Sequence[float]) -> T:
    total = sum(weights)
    if total <= 0:
        return rng.choice(items)
    pick = rng.random() * total
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if pick <= acc:
            return item
    return items[-1]


def lognormal_money(rng: random.Random, median: float, sigma: float) -> float:
    """Money is heavy-tailed: most families have little, a few have a lot."""
    return median * math.exp(rng.gauss(0.0, sigma))


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = clamp(q, 0, 1) * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)
