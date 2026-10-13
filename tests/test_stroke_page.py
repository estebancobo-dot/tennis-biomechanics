"""«Análisis de golpe» in a real browser: the ball moments with real measures and the user's views of
the body (lowering and rising, the base, the trunk at the finish) drawn from the stroke's series."""
import json
from pathlib import Path

import numpy as np
import pytest

from tennisbio.catalog import Match, Player
from tennisbio.report import build
from tennisbio.technique import CURVE_T

CHROMIUM = Path("/opt/pw-browsers/chromium")


def stroke_and_series():
    n, first, impact = 100, 0, 60                       # 50 fps, impact at frame 60 (t = 0)
    kp = []
    for f in range(n):
        base = [300, 200, 305, 195, 295, 195, 310, 198, 290, 198, 330, 260, 270, 260, 345, 330, 255, 330, 350, 390, 250, 390,
                320, 420, 280, 420, 325, 520, 275, 520, 345, 620, 255, 620]
        kp.append([float(v) for v in base])
    H = [[100.0, 0, 300], [0, -100.0, 700], [0, 0, 1]]
    ser = {"fps": 50.0, "first": first, "impact": impact, "n": n, "kp": kp, "conf": [[1.0] * 17] * n,
           "box": [[240, 180, 360, 640]] * n, "side": "near", "H": H, "ball": [[None, None]] * n,
           "kin": {"Pelvis": [0.1] * n, "Tronco": [0.1] * n, "Brazo": [0.1] * n, "Antebrazo": [0.1] * n},
           "ang": {"Codo": [120.0] * n, "X-factor": [5.0] * n}, "racket": {"elev": [None] * n, "head_cm": [None] * n}}
    hip = np.interp(CURVE_T, [-1.2, -0.8, -0.32, 0.0, 0.2, 0.8], [50, 50, 44, 48, 53, 52])
    tech = {"phases": {"loaded": {"base_court_m": 0.92}, "impact": {"base_court_m": 0.88}, "finish": {"base_court_m": 0.7, "shoulder_width_ratio": 0.6}},
            "stroke": {"hip_drop_cm": 11.0, "hip_rise_after_cm": 17.0, "t_hip_lowest": -0.32, "t_hip_highest": 0.2, "feet_move_m": 0.05},
            "classes": {"finish_trunk": "girado tres cuartos hacia el lado de su revés", "ball_phase": "subiendo"},
            "curves": {"hip": [round(float(v), 1) for v in hip]},
            "ball_phase_of_stroke": {}}
    tech["phases"].update({"ball_net": {"t_to_contact": 0.5}, "ball_bounce": {"t_to_contact": 0.25}})
    s = {"stroke": "forehand", "side": "near", "match_time_s": 30.0, "impact_source": "audio+ball", "review": [],
         "metrics": {"contact_height_pct": 55.0, "time_available_s": 1.0}, "stance": "abierto", "technique": tech,
         "phases": {"ready": {"t_rel": -0.8}, "loaded": {"t_rel": -0.4}, "impact": {"t_rel": 0.0}, "finish": {"t_rel": 0.3}},
         "series": "series/x.json"}
    return s, ser


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_body_views_on_the_stroke_page(tmp_path):
    from playwright.sync_api import sync_playwright

    s, ser = stroke_and_series()
    d = tmp_path / "m1"
    (d / "series").mkdir(parents=True)
    (d / "series" / "x.json").write_text(json.dumps(ser), encoding="utf-8")
    (d / "strokes.json").write_text(json.dumps([s]), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P", height_m=1.84))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("(async () => { showTab('golpe'); await loadStroke(STROKES[0]); })()")
        pg.wait_for_timeout(1500)
        body = pg.evaluate("document.getElementById('bodywrap').innerText")
        ball = pg.evaluate("document.getElementById('bm').innerText")
        b.close()
    assert not errors, errors[:3]
    assert "Baja 11 cm" in body and "sube 17 cm" in body
    assert "cadera −11 cm respecto a la espera" in body                 # the frame label = the curve = the sentence
    assert "Base de 0,92 m → 0,88 m → 0,70 m" in body and "pies plantados" in body
    assert "girado tres cuartos hacia el lado de su revés" in body
    assert "La bola cae" in ball and "pies a 0,90 m" in ball
