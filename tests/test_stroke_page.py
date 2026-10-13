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


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_layer_groups_and_full_screen(tmp_path):
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
        pg.wait_for_timeout(800)
        pg.click("#lpreset button[data-v=video]")
        none = pg.evaluate("Object.values(layers).some(Boolean)")
        pg.click("#lpreset button[data-v=body]")
        body = pg.evaluate("Object.keys(layers).filter(k => layers[k]).sort().join(',')")
        pg.click("#layers button[data-v=racket]")                 # one more layer by hand: no group marked
        mixed = pg.evaluate("[layers.racket, document.querySelectorAll('#lpreset button[aria-pressed=true]').length]")
        pg.reload()
        pg.wait_for_timeout(500)
        kept = pg.evaluate("Object.keys(layers).filter(k => layers[k]).sort().join(',')")
        pg.evaluate("(async () => { showTab('golpe'); await loadStroke(STROKES[0]); })()")
        pg.wait_for_timeout(500)
        pg.click("#fs")
        pg.wait_for_timeout(500)
        full = pg.evaluate("document.fullscreenElement && document.fullscreenElement.id")
        pg.evaluate("document.exitFullscreen()")
        pg.wait_for_timeout(500)
        out = pg.evaluate("[!!document.fullscreenElement, cv.width]")
        b.close()
    assert not errors, errors[:3]
    assert none is False and body == "ang,skel" and mixed == [True, 0] and kept == "ang,racket,skel"
    assert full == "player" and out == [False, 1280]


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_two_main_views_and_more(tmp_path):
    """Menu: «Cópiala» and «Sus golpes» first, the rest in «Más» (to practise / technical); every screen
    still reachable, the stroke page counts as «Sus golpes» and goes back to it."""
    from playwright.sync_api import sync_playwright

    s, ser = stroke_and_series()
    s["technique"]["jitter"] = {"loaded.base_court_m": 0.01}
    d = tmp_path / "m1"
    (d / "series").mkdir(parents=True)
    (d / "series" / "x.json").write_text(json.dumps(ser), encoding="utf-8")
    (d / "strokes.json").write_text(json.dumps([s] * 6), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P", height_m=1.84))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        main = pg.evaluate("[...document.querySelectorAll('.nav > button')].map(b => b.dataset.tab)")
        more = pg.evaluate("[...document.querySelectorAll('#nav-more button')].map(b => b.dataset.tab)")
        pg.evaluate("(async () => { showTab('golpe'); await loadStroke(STROKES[0]); })()")
        pg.wait_for_timeout(500)
        cur_golpe = pg.evaluate("document.querySelector('.nav button[aria-current=page]').dataset.tab")
        pg.click("#g-back")
        back = pg.evaluate("document.querySelector('.screen:not([hidden])').id")
        pg.evaluate("showTab('fiabilidad')")
        rel = pg.evaluate("document.getElementById('rel-body').textContent")
        opened = pg.evaluate("document.getElementById('nav-more').open")
        b.close()
    assert not errors, errors[:3]
    assert main == ["aprende", "videoteca"]
    assert set(more) == {"comparar", "lateral", "modelo", "pista", "conclusiones", "explorador", "fiabilidad", "datos"}
    assert cur_golpe == "videoteca" and back == "tab-videoteca" and opened
    assert "Base al armar" in rel


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_merged_views_keep_every_piece(tmp_path):
    """The old screens live inside the new ones: every block still there and filled (the typical curves need
    12 strokes, as before), and their old names
    still open them (patrón típico in Cópiala, pista in Sus golpes, panel and comparativas in Conclusiones)."""
    from playwright.sync_api import sync_playwright

    s, ser = stroke_and_series()
    d = tmp_path / "m1"
    (d / "series").mkdir(parents=True)
    (d / "series" / "x.json").write_text(json.dumps(ser), encoding="utf-8")
    (d / "strokes.json").write_text(json.dumps([dict(s, match_time_s=30.0 + i, court_pos_m=[0.5 * i - 1, -1.0]) for i in range(6)]), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P", height_m=1.84))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(600)
        filled = pg.evaluate("""['kpis', 'concl', 'c-say', 'court', 'p-stats'].map(id => [id, !!document.getElementById(id)
                                  && document.getElementById(id).innerHTML.trim().length > 20])""")
        res = {}
        for old, sel in (("modelo", "#sec-modelo"), ("pista", "#lib-pista"), ("panel", "#sec-resumen"), ("comparativas", "#sec-cambia")):
            pg.evaluate(f"showTab('{old}')")
            pg.wait_for_timeout(200)
            res[old] = pg.evaluate(f"""[document.querySelector('.screen:not([hidden])').id, (() => {{ const e = document.querySelector('{sel}');
                                        return !!e && !e.hidden && (e.tagName !== 'DETAILS' || e.open) && !!e.offsetParent; }})()]""")
        pg.evaluate("showTab('datos')")
        datos = pg.evaluate("document.getElementById('datos-body').innerText")
        b.close()
    assert not errors, errors[:3]
    assert all(ok for _, ok in filled), filled
    assert res == {"modelo": ["tab-aprende", True], "pista": ["tab-videoteca", True], "panel": ["tab-conclusiones", True],
                   "comparativas": ["tab-conclusiones", True]}
    assert "6 del lado cercano" in datos and "Golpes dudosos" in datos


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_phone_width(tmp_path):
    """At a phone's width (390 px): no sideways scroll on any main screen and «Más» opens under the two
    main entries, full width, without squeezing them."""
    from playwright.sync_api import sync_playwright

    s, ser = stroke_and_series()
    d = tmp_path / "m1"
    (d / "series").mkdir(parents=True)
    (d / "series" / "x.json").write_text(json.dumps(ser), encoding="utf-8")
    (d / "strokes.json").write_text(json.dumps([s] * 3), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P", height_m=1.84))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        widths = {}
        for tab in ("aprende", "videoteca", "conclusiones", "fiabilidad", "datos"):
            pg.evaluate(f"showTab('{tab}')")
            pg.wait_for_timeout(200)
            widths[tab] = pg.evaluate("document.documentElement.scrollWidth")
        pg.evaluate("showTab('aprende'); document.getElementById('nav-more').open = false")   # «datos» had opened it
        pg.click("#nav-more summary")
        more = pg.evaluate("document.getElementById('nav-more').getBoundingClientRect().width")
        main = pg.evaluate("Math.min(...[...document.querySelectorAll('.nav > button')].map(b => b.getBoundingClientRect().width))")
        b.close()
    assert all(w <= 390 for w in widths.values()), widths
    assert more > 300 and main > 120
