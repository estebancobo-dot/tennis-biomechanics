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


def test_second_method_and_untestable():
    # stable but the independent 3D reading says something else: bias, not her value
    rows = [{"technique": {"phases": {"loaded": {"shoulder_turn": 60.0 + i}}, "jitter": {"loaded.shoulder_turn": 1.0}},
             "metrics": {"shoulder_turn_3d_deg": 15.0 + i, "trunk3d_rigid": True}} for i in range(8)]
    r = assess(rows, {"loaded.shoulder_turn": "°"})["loaded.shoulder_turn"]
    assert r["verdict"] == "sesgo" and r["med2d"] > r["med3d"]
    for x in rows:
        x["metrics"]["shoulder_turn_3d_deg"] = x["technique"]["phases"]["loaded"]["shoulder_turn"] + 2
    assert assess(rows, {"loaded.shoulder_turn": "°"})["loaded.shoulder_turn"]["verdict"] == "fiable"
    # a value that never moves with the phase instants is not validated by this test
    flat = [{"technique": {"stroke": {"swing_low_to_high": 40.0 + i}, "jitter": {"stroke.swing_low_to_high": 0.0}}} for i in range(8)]
    assert assess(flat, {"stroke.swing_low_to_high": "°"})["stroke.swing_low_to_high"]["verdict"] == "no comprobable"


def test_derived_measure_takes_the_verdict_of_its_source():
    rows = [{"technique": {"phases": {"loaded": {"shoulder_turn": 60.0 + i}}, "stroke": {"shoulder_brake": 50.0 + i},
                           "jitter": {"loaded.shoulder_turn": 1.0, "stroke.shoulder_brake": 0.0}},
             "metrics": {"shoulder_turn_3d_deg": 15.0 + i, "trunk3d_rigid": True}} for i in range(8)]
    r = assess(rows, {"loaded.shoulder_turn": "°", "stroke.shoulder_brake": "%"})
    assert r["stroke.shoulder_brake"]["verdict"] == "sesgo" and r["stroke.shoulder_brake"]["from"] == "loaded.shoulder_turn"
