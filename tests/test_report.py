import json

from tennisbio.catalog import Match, Player
from tennisbio.report import build, stroke_record


def stroke(t, **kw):
    s = {"stroke": "forehand", "match_time_s": t, "impact_source": "audio+ball+swing", "review": [],
         "metrics": {"x_factor_deg": 20.0, "contact_height_pct": 55.0, "time_available_s": 1.0},
         "phases": {"ready": {"t_rel": -0.6, "method": "split_step_landing", "confidence": 0.9},
                    "recovery": {"t_rel": 0.5, "method": "first_step", "confidence": 0.8}},
         "racket": {"loaded": {"head_above_wrist_cm": 30.0}, "acceleration": {"head_above_wrist_cm": -20.0}},
         "chain": {"proximal_to_distal": True}, "court_pos_m": [1.0, -1.5], "stance": "abierto", "stance_width_m": 0.9}
    s.update(kw)
    return s


def test_stroke_record_situation_and_metrics():
    m = Match("m1", None, Player("p", "P"))
    r = stroke_record(stroke(10.0), 0, m, 100.0, 0)
    assert r["fast"] is True and r["height"] == "media" and abs(r["y"] - 13.385) < 1e-6
    assert r["m"]["xf"] == 20.0 and r["m"]["rDrop"] == 20.0 and r["m"]["split"] == 400 and r["m"]["recov"] == 0.5
    assert r["frac"] == 0.1 and r["sit"]["neutra"] is False


def test_build_writes_page_with_data(tmp_path):
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps([stroke(5.0), stroke(9.0, stroke="backhand")]))
    (d / "probe.json").write_text(json.dumps({"duration": 60}))
    out = build([Match("m1", None, Player("p", "P"))], tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "__DATA__" not in html and '"m1-001"' in html and '"m1-002"' not in html


def test_frame_noise_recovers_white_noise_on_a_ramp():
    import numpy as np
    from tennisbio.report import frame_noise
    rng = np.random.default_rng(0)
    x = list(np.linspace(0, 50, 200) + rng.normal(0, 2.0, 200))
    est = np.median([frame_noise(x, k, half=10) for k in range(20, 180, 10)])
    assert 1.5 < est < 2.6
    assert frame_noise([None] * 10, 5) is None


def test_noise_from_pairs_needs_enough_neutral_strokes():
    import numpy as np
    from tennisbio.report import noise_from_pairs
    rng = np.random.default_rng(1)
    strokes = [{"sit": {"neutra": True}, "tAvail": 1.3 + 0.01 * i, "x": 0.0, "y": 13.0,
                "m": {"contactH": 55.0, "xf": 20 + rng.normal(0, 3)}} for i in range(300)]
    n = noise_from_pairs(strokes)
    assert 2.3 < n["xf"] < 3.8
    assert noise_from_pairs(strokes[:10]) == {}


def test_report_for_the_opponent(tmp_path):
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps([stroke(5.0)]))
    (d / "strokes_opponent.json").write_text(json.dumps([stroke(7.0), stroke(9.0)]))
    m = Match("m1", None, Player("ryba", "E. Rybakina"), opponent="A. Sabalenka", extra={"opponent_id": "saba"})
    from tennisbio.report import collect
    data = collect([m], tmp_path, player_id="saba")
    assert len(data["strokes"]) == 2 and data["matches"][0]["rival"] == "E. Rybakina"
    assert len(collect([m], tmp_path)["strokes"]) == 1
