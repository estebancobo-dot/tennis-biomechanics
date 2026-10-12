import numpy as np

from tennisbio.model import build_model


def _strokes(n=300, seed=0):
    """Synthetic strokes: a fast ball shortens the takeback (−12 %); fast balls are also more often
    'defence', which by itself changes nothing. The shoulder turn at loading never changes."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        fast = rng.random() < 0.35
        defence = rng.random() < (0.6 if fast else 0.1)
        high = rng.random() < 0.3
        tp = 50 - (12 if fast else 0) + rng.normal(0, 4)
        sh = 85 + rng.normal(0, 5)
        hip_h = 48 - (4 if high else 0) * -1 + rng.normal(0, 1.5)
        out.append({"stroke_id": f"m{i % 3}-{i:07d}", "side": "near", "technique": {
            "phases": {"loaded": {"shoulder_turn": sh, "hip_height": hip_h}},
            "stroke": {"takeback_path": tp},
            "footwork": {"steps_to_impact": int(rng.integers(2, 6))},
            "classes": {"ball_speed": "rápida" if fast else "media", "intent": "defensa" if defence else "neutra",
                        "ball_height": "pecho-hombro" if high else "cintura-pecho", "stance_impact": "abierto"},
            "pose": {"loaded": [[0.0, 0.5]] * 17}}})
    return out


def test_model_finds_the_real_adaptation_and_not_the_confounded_one():
    m = build_model(_strokes())
    eff = {(e["key"], e["factor"], e["level"]): e for e in m["effects"]}
    tp = eff.get(("stroke.takeback_path", "ball_speed", "rápida"))
    assert tp is not None and -15 < tp["diff"] < -9
    assert ("stroke.takeback_path", "intent", "defensa") not in eff        # adjusted for the ball speed
    assert ("loaded.hip_height", "ball_height", "pecho-hombro") in eff
    assert "loaded.shoulder_turn" in m["constants"]
    assert all(e["key"] != "loaded.shoulder_turn" for e in m["effects"])
    v = m["variants"]["ball_speed"]["rápida"]
    assert v["n"] > 80 and not v["usual"] and v["strokes"]
    assert m["skeleton"]["loaded"][0] == [0.0, 0.5]
    assert m["typical"]["loaded.shoulder_turn"]["n"] == 300


def test_model_with_few_strokes_says_nothing():
    m = build_model(_strokes(n=8))
    assert m["typical"] == {} and m["effects"] == [] and m["variants"] == {}


def test_inseparable_situations_claim_nothing():
    """'defence' is exactly 'very fast ball' here: neither can be told apart, so no effect is claimed
    for them even though the takeback is shorter in both."""
    import numpy as np
    rng = np.random.default_rng(3)
    rows = []
    for i in range(200):
        fast = i % 3 == 0
        rows.append({"stroke_id": f"m0-{i:07d}", "side": "near", "technique": {
            "phases": {}, "stroke": {"takeback_path": 50 - (12 if fast else 0) + rng.normal(0, 3)}, "footwork": {},
            "classes": {"ball_speed": "muy rápida" if fast else "media", "intent": "defensa" if fast else "neutra"}}})
    m = build_model(rows)
    assert not [e for e in m["effects"] if e["key"] == "stroke.takeback_path"]
