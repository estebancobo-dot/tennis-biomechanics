"""«Aprende su derecha» checked in a real browser over every combination of conditions, on a large
synthetic set that covers every level (the PC tests never have enough strokes to fill them)."""
import json
import random
from pathlib import Path

import pytest

from tennisbio.catalog import Match, Player
from tennisbio.learn import CONDITIONS, learn_keys
from tennisbio.report import build

CHROMIUM = Path("/opt/pw-browsers/chromium")


def synthetic(n=400, seed=3):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        tech = {"phases": {}, "stroke": {}, "classes": {}, "footwork": {}}
        for k in learn_keys():
            if k.startswith("practice."):
                continue
            grp, name = k.split(".", 1)
            if grp == "class":
                continue
            v = rnd.choice([True, False]) if name in ("step_in", "braking_step", "drag_foot", "rear_leg_step_after") else round(rnd.uniform(-1, 1) * 40, 2)
            if rnd.random() < 0.15:                 # missing values happen: the screen must say why
                continue
            if grp in ("stroke", "footwork"):
                tech[grp][name] = v
            else:
                tech["phases"].setdefault(grp, {})[name] = v
        for d, (_, levels) in CONDITIONS.items():
            tech["classes"][d] = rnd.choice(list(levels))
        for c in ("ready_hands", "takeback", "stance_loaded", "ball_phase", "finish", "recovery_first_step", "approach_main"):
            tech["classes"][c] = rnd.choice(["a", "b", "c"])
        tech["footwork"]["steps_reliable"] = rnd.random() > 0.4
        # one measure that jumps between neighbouring frames far more than between strokes: noise
        tech["jitter"] = {"loaded.face_tilt": 200.0, "loaded.shoulder_turn": 0.5, "class.takeback": 0.75}
        out.append({"stroke": "forehand", "match_time_s": 10.0 + i, "impact_source": "audio+ball+swing", "review": [],
                    "metrics": {"contact_height_pct": 55.0}, "phases": {"impact": {"t_rel": 0.0}, "ready": {"t_rel": -0.6}},
                    "technique": tech, "court_pos_m": [1.0, -1.0], "stance": tech["classes"]["stance_impact"]})
    return out


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_every_combination_of_learn_screen(tmp_path):
    from playwright.sync_api import sync_playwright

    from tennisbio.learn_check import check_page

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(synthetic()), encoding="utf-8")
    (d / "probe.json").write_text(json.dumps({"duration": 3600}))
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        r = check_page(pg)
        b.close()
    assert not errors, errors[:3]
    assert r["combinations"] > 600 and r["with_exact_strokes"] > 400
    assert not r["failures"], r["failures"][:5]
    assert r["example"]["rows"] > 40 and r["rows_all"] >= r["valued_all"] > 0


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_noise_is_not_shown_as_her_value(tmp_path):
    from playwright.sync_api import sync_playwright

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(synthetic(60)), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('.nav button[data-tab=\"aprende\"]').click()")
        txt = lambda k: pg.evaluate(f"document.querySelector('.cpk[data-key=\"{k}\"]').children[1].innerText")
        noisy, good, flip = txt("loaded.face_tilt"), txt("loaded.shoulder_turn"), txt("class.takeback")
        b.close()
    assert "no fiable desde la tele" in noisy and "golpes" not in noisy.split("no fiable")[0]
    assert "no fiable" not in good and "°" in good
    assert "no fiable desde la tele" in flip and "%" in flip


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_signature_shows_what_she_repeats(tmp_path):
    from playwright.sync_api import sync_playwright

    rows = synthetic(40)
    for i, r in enumerate(rows):                 # she always loops the takeback; the finish varies
        r["technique"]["classes"]["takeback"] = "bucle"
        r["technique"]["jitter"] = {}
        r["video"] = None
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(rows), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('.nav button[data-tab=\"aprende\"]').click()")
        sig = pg.evaluate("document.getElementById('a-sig').innerText")
        b.close()
    assert "Estilo de su derecha: preparación bucle (100 %)" in sig
    assert "bucle en 40 de 40 golpes" in sig and "Cópialo:" in sig
