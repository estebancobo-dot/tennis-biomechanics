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
    # the conditions draw from their own generator: adding a condition (20-10: golpe angulado, bola corta
    # cerca de la red) must not reshuffle the measures of every stroke
    rnd_c = random.Random(seed + 1000)
    out = []
    for i in range(n):
        tech = {"phases": {}, "stroke": {}, "classes": {}, "footwork": {}}
        for k in learn_keys():
            if k.startswith("practice."):
                continue
            grp, name = k.split(".", 1)
            if grp == "class":
                continue
            v = rnd.choice([True, False]) if name in ("step_in", "braking_step", "drag_foot", "rear_leg_step_after", "back_heel_lift") else round(rnd.uniform(-1, 1) * 40, 2)
            if rnd.random() < 0.15:                 # missing values happen: the screen must say why
                continue
            if grp in ("stroke", "footwork"):
                tech[grp][name] = v
            else:
                tech["phases"].setdefault(grp, {})[name] = v
        for d, (_, levels) in CONDITIONS.items():
            tech["classes"][d] = rnd_c.choice(list(levels))
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
        pg.evaluate("document.getElementById('a-more').open = true; document.getElementById('a-phases-d').open = true")   # the extras, unfolded
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
        pg.evaluate("document.getElementById('a-more').open = true")          # «Su firma» lives in the extras
        sig = pg.evaluate("document.getElementById('a-sig').innerText")
        b.close()
    assert "Estilo de su derecha: preparación bucle (100 %)" in sig
    assert "bucle en 40 de 40 golpes" in sig and "Cópialo:" in sig


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_target_with_her_number_guide_and_glossary(tmp_path):
    from playwright.sync_api import sync_playwright

    rows = synthetic(40)
    for r in rows:                                # she drops 14 cm; the face tilt is noise (jitter 200)
        r["technique"]["stroke"]["hip_drop_cm"] = 14.0
        r["technique"]["jitter"]["stroke.hip_drop_cm"] = 0.5
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(rows), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P", height_m=1.84))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('.nav button[data-tab=\"aprende\"]').click()")
        mine = lambda k: pg.evaluate(f"(document.querySelector('.cpk[data-key=\"{k}\"] .mine') || {{}}).textContent || ''")
        before, noisy = mine("stroke.hip_drop_cm"), mine("loaded.face_tilt")
        pg.fill("#a-uh", "1.70")
        pg.dispatch_event("#a-uh", "change")
        after = mine("stroke.hip_drop_cm")
        guide = pg.evaluate("document.getElementById('a-guide').hidden")
        pg.evaluate("document.getElementById('a-more').open = true")          # the guide lives in the extras
        pg.click("#a-guide-x")
        hidden = pg.evaluate("[document.getElementById('a-guide').hidden, document.getElementById('a-guide-show').hidden]")
        terms = pg.evaluate("[document.querySelectorAll('#a-gloss dt').length, document.querySelectorAll('#a-phases abbr.gl').length]")
        b.close()
    assert not errors, errors[:3]
    assert "Baja la cadera unos 14 cm desde la espera" in before and "como ella" in before
    assert noisy == ""                            # noise never becomes a target
    assert "unos 13 cm (a tu altura)" in after    # 14 × 1.70 / 1.84
    assert guide is False and hidden == [True, False]
    assert terms[0] >= 20 and terms[1] > 0


def test_guide_keys_are_checkpoints_with_targets():
    """The keys of a forehand guide that we already measured are taught in «Cópiala», each with her
    number as a target (turn before the net, hand and elbow at the loaded position, contact against the
    top of the bounce, high finish) and the backswing form. «No pause at the top» is not: the still hand
    does not say whether the racket stops (docs/validacion.md); it is told as not measurable from TV."""
    from tennisbio.explain import NOT_MEASURABLE
    from tennisbio.learn import LESSON, NOT_FROM_TV, SYMPTOMS
    from tennisbio.explain import CLASS_PHASE
    from tennisbio.learn import TARGETS, learn_keys

    keys = set(learn_keys())
    for k in ("stroke.takeback_vs_net", "stroke.dur_preparation", "loaded.wrist_dom_vs_shoulder", "loaded.elbow_dom",
              "stroke.contact_vs_top", "finish.wrist_dom_vs_shoulder"):
        assert k in keys and k in TARGETS, k
    k = "stroke.pause_at_loaded"
    assert k not in keys and k not in TARGETS and all(k not in ks for _, ks in LESSON.values())
    assert all(k not in ks for _, _, ks in SYMPTOMS)
    assert any(w.startswith("Pausa arriba") and "no medible desde la tele" in h.lower() for w, h in NOT_FROM_TV)
    assert any(t.startswith("Pausa arriba") for t in NOT_MEASURABLE)
    assert "class.takeback_loop" in keys and CLASS_PHASE["takeback_loop"] == "loaded"


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_lesson_meets_the_requirements(tmp_path):
    """«La lección», checked as the user's requirements say: every phase with at most 3 keys, each with
    her value, a drill and how to check it; one screen and a half at most; no sideways scroll on a phone;
    the full list of measures still there (folded); no page errors."""
    from playwright.sync_api import sync_playwright

    from tennisbio.learn_check import check_lesson

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(synthetic(200)), encoding="utf-8")
    (d / "probe.json").write_text(json.dumps({"duration": 3600}))
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        r = check_lesson(pg)
        n_cards = pg.evaluate("document.querySelectorAll('#a-phases .cpk').length")
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(300)
        wide = pg.evaluate("document.documentElement.scrollWidth")
        b.close()
    assert not errors, errors[:3]
    assert len(r["phases"]) == 9 and not r["failures"], r["failures"]
    assert r["with_keys"] == 9 and all(1 <= x["keys"] <= 3 for x in r["phases"])
    assert n_cards == len([k for k in learn_keys()])          # nothing removed: every measure still listed
    assert wide <= 400


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
@pytest.mark.parametrize("w,h", [(1280, 900), (1440, 900), (390, 844)])
def test_entry_and_every_screen_meet_the_design(tmp_path, w, h):
    """docs/diseno_definitivo.md §5: the lesson video in the first screen, few headings and buttons
    when it opens, no sideways scroll on any screen, no file name as the title of a stroke."""
    from playwright.sync_api import sync_playwright

    from tennisbio.learn_check import check_entry

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(synthetic(120)), encoding="utf-8")
    (d / "probe.json").write_text(json.dumps({"duration": 3600}))
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": w, "height": h})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(600)
        r = check_entry(pg)
        b.close()
    assert not errors, errors[:3]
    assert not r["failures"], r["failures"]
    assert r["entry"]["vid_top"] < (0.55 * h if w < 600 else h)


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_report_with_no_strokes_opens_without_errors(tmp_path):
    from playwright.sync_api import sync_playwright

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text("[]", encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        note = pg.evaluate("(document.getElementById('empty-note') || {}).innerText || ''")
        b.close()
    assert not errors, errors[:3]
    assert "Todavía no hay golpes analizados" in note


def test_symptoms_link_late_signs_and_errors():
    """Olivari (docs/investigacion_youtube_usuario.md, propuestas 1-2): «Llegas tarde» and «La bola se va
    larga» compare with hitting while moving back and with the ball falling; «La bola se va a la red» says
    where her errors go."""
    from tennisbio.learn import content

    sy = {s["s"]: s for s in content()["symptoms"]}
    for t in ("Llegas tarde: golpeas con la bola a tu lado", "La bola se va larga"):
        assert {"class.back_at_impact", "class.ball_phase", "stroke.contact_vs_top"} <= set(sy[t]["keys"])
        assert [k for k, _, _ in sy[t]["shares"]] == ["class.back_at_impact", "class.ball_phase"]
    assert sy["La bola se va a la red"]["errors"] is True and content()["errors_min"] >= 5
    keys = set(learn_keys())
    assert all(k in keys for s in sy.values() for k in s["keys"])          # every chip has its card


def _symptom_rows(n_err):
    rows = synthetic(40)
    for i, r in enumerate(rows):
        r["technique"]["classes"]["back_at_impact"] = i % 4 == 0              # 10 of 40 moving back
        r["technique"]["classes"]["ball_phase"] = "bola cayendo" if i % 5 == 0 else "bola subiendo"   # 8 of 40
        r["technique"]["jitter"] = {}
        r.pop("outcome", None)
        if i < n_err:                         # errors: half to the net, then long and wide from the bounce
            if i % 2 == 0:
                r["outcome"] = "net"
            else:
                r["outcome"], r["shot_in"] = "out", False
                r["shot_bounce_m"] = [1.0, 25.0] if i % 4 == 1 else [5.0, 20.0]
        elif i < 30:
            r["outcome"] = "rally"
    return rows


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
@pytest.mark.parametrize("n_err", [8, 3])
def test_symptoms_show_her_late_signs_and_errors(tmp_path, n_err):
    from playwright.sync_api import sync_playwright

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(_symptom_rows(n_err)), encoding="utf-8")
    html = build([Match("m1", None, Player("p", "P"))], tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('.nav button[data-tab=\"aprende\"]').click()")
        pg.evaluate("['a-more', 'a-phases-d'].forEach(id => { const d = document.getElementById(id); if (d) d.open = true; })")
        items = pg.evaluate("[...document.querySelectorAll('#a-sym li')].map(li => li.innerText)")
        b.close()
    assert not errors, errors[:3]
    late = next(t for t in items if t.startswith("Llegas tarde"))
    long_ = next(t for t in items if t.startswith("La bola se va larga"))
    net = next(t for t in items if t.startswith("La bola se va a la red"))
    for t in (late, long_):
        assert "Ella, golpea retrocediendo: 25 % de sus golpes (10 de 40)" in t
        assert "Ella, toma la bola cayendo: 20 % de sus golpes (8 de 40)" in t
        assert "Golpea retrocediendo" in t and "Bola subiendo, arriba o cayendo" in t
    assert "Ella, golpea retrocediendo" not in net
    if n_err >= 5:     # 8 errors: 4 net, 2 long (y > 23.77), 2 wide (|x| > 4.115)
        assert "Sus errores (probable" in net
        assert "4 a la red (50 %)" in net and "2 largos (25 %)" in net and "2 anchos (25 %)" in net
        assert "de 8 errores; resultado conocido en 30 de 40 golpes" in net
    else:
        assert "pocos datos: solo 3 errores" in net and "a la red (" not in net
