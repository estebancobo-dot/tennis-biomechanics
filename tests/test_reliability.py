"""Technique or noise: a measure that moves more between neighbouring frames than between strokes is
not given as her value."""
import random

from tennisbio.reliability import assess


def strokes(n, spread, noise, seed=1):
    rnd = random.Random(seed)
    return [{"technique": {"phases": {"loaded": {"m": rnd.gauss(50, spread)}}, "jitter": {"loaded.m": abs(rnd.gauss(noise, noise / 4))}}}
            for _ in range(n)]


def test_verdicts():
    assert assess(strokes(30, spread=20, noise=2), {"loaded.m": "°"})["loaded.m"]["verdict"] == "fiable"
    assert assess(strokes(30, spread=5, noise=30), {"loaded.m": "°"})["loaded.m"]["verdict"] == "ruido"
    r = assess(strokes(60, spread=14, noise=8), {"loaded.m": "%"})["loaded.m"]
    assert r["verdict"] == "dudosa" and 6 < r["noise"] < 10


def test_floor_and_few_strokes():
    # a very consistent measure with a tiny jitter is reliable even if its spread is smaller still
    assert assess(strokes(30, spread=0.5, noise=1), {"loaded.m": "°"})["loaded.m"]["verdict"] == "fiable"
    assert assess(strokes(3, spread=20, noise=2), {"loaded.m": "°"})["loaded.m"]["verdict"] == "sin juzgar"
    assert assess([{"technique": {}}] * 10, {"loaded.m": "°"}) == {}
