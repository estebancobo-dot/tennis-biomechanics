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
    from tennisbio.reliability import TRUNK_3D
    r = assess(rows, {"loaded.shoulder_turn": "°"}, TRUNK_3D)["loaded.shoulder_turn"]
    assert r["verdict"] == "sesgo" and r["med2d"] > r["med3d"]
    # by default no second method judges the trunk (the 3D from behind is not a valid reference)
    assert assess(rows, {"loaded.shoulder_turn": "°"})["loaded.shoulder_turn"]["verdict"] == "fiable"
    for x in rows:
        x["metrics"]["shoulder_turn_3d_deg"] = x["technique"]["phases"]["loaded"]["shoulder_turn"] + 2
    assert assess(rows, {"loaded.shoulder_turn": "°"}, TRUNK_3D)["loaded.shoulder_turn"]["verdict"] == "fiable"
    # a value that never moves with the phase instants is not validated by this test
    flat = [{"technique": {"stroke": {"swing_low_to_high": 40.0 + i}, "jitter": {"stroke.swing_low_to_high": 0.0}}} for i in range(8)]
    assert assess(flat, {"stroke.swing_low_to_high": "°"})["stroke.swing_low_to_high"]["verdict"] == "no comprobable"


def test_derived_measure_takes_the_verdict_of_its_source():
    rows = [{"technique": {"phases": {"loaded": {"shoulder_turn": 60.0 + i}}, "stroke": {"shoulder_brake": 50.0 + i},
                           "jitter": {"loaded.shoulder_turn": 1.0, "stroke.shoulder_brake": 0.0}},
             "metrics": {"shoulder_turn_3d_deg": 15.0 + i, "trunk3d_rigid": True}} for i in range(8)]
    from tennisbio.reliability import TRUNK_3D
    r = assess(rows, {"loaded.shoulder_turn": "°", "stroke.shoulder_brake": "%"}, TRUNK_3D)
    assert r["stroke.shoulder_brake"]["verdict"] == "sesgo" and r["stroke.shoulder_brake"]["from"] == "loaded.shoulder_turn"


def _feet(values, key="impact.back_foot_angle_deg", noise=2.0):
    p, m = key.split(".")
    return [{"technique": {"phases": {p: {m: v}}, "jitter": {key: noise}}} for v in values]


def test_physically_impossible_readings_make_a_measure_biased():
    """Foot direction: toes turned back towards her own fence (< -45°) on a planted groundstroke foot is
    the method failing (PC, 14-10: 20-44 % of the forehand readings), not her technique."""
    from tennisbio.reliability import FOOT_RANGE, IMPLAUSIBLE_SHARE, PLAUSIBLE

    assert FOOT_RANGE == (-45.0, 180.0) and IMPLAUSIBLE_SHARE == 0.15
    assert set(PLAUSIBLE) == {f"{p}.{w}_foot_angle_deg" for p in ("loaded", "impact") for w in ("front", "back")}
    k = "impact.back_foot_angle_deg"
    # the real distribution of the PC's near forehands (poc6_35): 5 of 12 below -45°
    real = [-98.5, -82.8, -64.0, -63.9, -48.5, -42.2, -24.2, -7.7, -1.5, 3.3, 35.8, 39.6]
    r = assess(_feet(real), {k: "°"})[k]
    assert r["verdict"] == "sesgo" and r["implausible"] == 5 and r["n_values"] == 12 and r["range"] == [-45.0, 180.0]
    # nominal: all possible, a real spread → reliable, nothing flagged
    ok = assess(_feet([0, 10, 20, 30, 45, 60, 75, 90, 100, 110]), {k: "°"})[k]
    assert ok["verdict"] == "fiable" and "implausible" not in ok
    # edge: the limit itself is possible; 3 of 20 (15 %) impossible is not yet systematic, but is reported
    edge = [-45.0] + [float(x) for x in range(0, 95, 5)]
    assert assess(_feet(edge), {k: "°"})[k]["verdict"] == "fiable"
    some = [-60.0, -70.0, -80.0] + [float(x) for x in range(0, 85, 5)]
    rs = assess(_feet(some), {k: "°"})[k]
    assert rs["verdict"] == "fiable" and rs["implausible"] == 3 and rs["n_values"] == 20
    # 4 of 21 (19 %): systematic
    assert assess(_feet([-90.0] + some), {k: "°"})[k]["verdict"] == "sesgo"
    # error cases: noise stays noise; other measures are not judged by the foot range; too few: not judged
    noisy = assess(_feet([-90, -80, -70, 0, 1, 2, 3, 4], noise=60.0), {k: "°"})[k]
    assert noisy["verdict"] == "ruido"
    other = assess(_feet(real, key="loaded.shoulder_turn"), {"loaded.shoulder_turn": "°"})["loaded.shoulder_turn"]
    assert other["verdict"] != "sesgo" and "implausible" not in other
    assert assess(_feet([-90, -80, 10]), {k: "°"})[k]["verdict"] == "sin juzgar"


def test_consistent_strokes_with_a_moving_instant_are_noise():
    """PC, 14-10 (10 near forehands): the shoulder turn where the backswing starts reads 19-23° in 7 of 10
    strokes, and moving that instant 1-2 frames moves it ±3.4° (the turn is starting there). The strokes
    do not differ more than the instant itself: not given as her value (it was «fiable» only while the
    former height scale, which followed the trunk's image length, spread the strokes apart)."""
    vals = [20.7, 20.2, 20.7, 62.2, 22.9, 22.1, 18.9, 54.5, 22.4, 3.0]
    jit = [4.25, 3.95, 2.15, 1.15, 3.75, 3.95, 1.2, 3.05, 10.5, 0.35]
    rows = [{"technique": {"phases": {"takeback": {"shoulder_turn": v}}, "jitter": {"takeback.shoulder_turn": j}}}
            for v, j in zip(vals, jit)]
    r = assess(rows, {"takeback.shoulder_turn": "°"})["takeback.shoulder_turn"]
    assert r["verdict"] == "ruido" and r["noise"] == 3.4 and r["spread"] < r["noise"]
