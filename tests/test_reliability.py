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


def test_shifted_jitter_and_classes():
    from tennisbio.reliability import shifted_jitter

    base = {"stroke": {"t_loaded": 0.30, "x": None}, "footwork": {"step_in": True}, "classes": {"takeback": "bucle"}}
    moved = [{"stroke": {"t_loaded": 0.30 + d}, "footwork": {"step_in": d > 0}, "classes": {"takeback": "bucle" if d else "recto"}}
             for d in (-0.04, -0.02, 0.02, 0.04)]
    j = shifted_jitter(base, moved)
    assert abs(j["stroke.t_loaded"] - 0.03) < 1e-9 and j["footwork.step_in"] == 0.5 and j["class.takeback"] == 0.0
    flips = [{"technique": {"classes": {"takeback": "bucle"}, "jitter": {"class.takeback": f}}} for f in [0.5] * 6]
    assert assess(flips, {"class.takeback": None})["class.takeback"]["verdict"] == "ruido"
    steady = [{"technique": {"classes": {"takeback": "bucle"}, "jitter": {"class.takeback": 0.0}}}] * 6
    assert assess(steady, {"class.takeback": None})["class.takeback"]["verdict"] == "fiable"
