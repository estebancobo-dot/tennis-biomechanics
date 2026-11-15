"""P0.5a (15-11, #305): the new application (ui/ built into app/p0/index.html) with made-up data, walked in a browser."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from tennisbio.app import p0_app

ROOT = Path(__file__).resolve().parents[1]
# pieces of the walk that later steps bring (docs/p0_plan.md §3 bis); none left since P0.5c
PENDING: set = set()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_built_page_is_the_one_of_its_sources():
    """The interface is built in Claude's cloud (the PC has no Node) and the build goes to the repository: it must be
    the build of the sources that are there (scripts/construir_ui.py writes their fingerprint)."""
    build = _load("construir_ui", ROOT / "scripts" / "construir_ui.py")
    stamp = (ROOT / "src" / "tennisbio" / "app" / "p0" / "huella.txt").read_text(encoding="utf-8").strip()
    assert stamp == build.fingerprint(), "ui/ cambió sin volver a construir: python scripts/construir_ui.py"


def test_no_source_of_the_interface_is_left_out_of_the_repository():
    """15-11: «*.ts» in .gitignore (the broadcasts' video type) had left the TypeScript sources out of the repository:
    the build there could not be made again from it."""
    import shutil
    import subprocess

    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("sin git")
    build = _load("construir_ui", ROOT / "scripts" / "construir_ui.py")
    files = [f"ui/{f}" for f in build.SOURCES] + sorted(p.relative_to(ROOT).as_posix()
                                                         for p in (ROOT / "ui" / "src").rglob("*") if p.is_file())
    r = subprocess.run(["git", "check-ignore", "--no-index", *files], cwd=ROOT, capture_output=True, text=True)
    assert r.stdout.split() == [], f"fuentes de ui/ que git no guarda: {r.stdout.split()}"
    assert "ui/src/contrato.ts" in files and "ui/vite.config.ts" in files


def test_the_data_go_into_the_page_safely():
    d = p0_app.ejemplo()
    d["known"] = ["</script><script>alert(1)</script>"]
    html = p0_app.pagina(d)
    assert p0_app.SLOT not in html and "<\\/script><script>alert(1)<\\/script>" in html
    assert "</script><script>alert(1)" not in html
    assert d["ejemplo"] is True and all("ejemplo" in p["name"] for p in d["players"])


def test_the_example_is_walked_without_errors():
    """Every screen, panel, phase and tab of the application opens without a JavaScript error and nothing overflows at
    the desktop widths (#301) — the same walk as the validated mockup's (design/p0/recorrer_maqueta.py)."""
    pytest.importorskip("playwright")
    walk = _load("recorrer_maqueta", ROOT / "design" / "p0" / "recorrer_maqueta.py")
    html = p0_app.pagina(p0_app.ejemplo())
    for w, h in ((1920, 1080), (1280, 800)):
        r = walk.walk(html, w, h)
        assert [e for e in r["errores"] if e not in PENDING] == [], r["errores"]
        assert r["desborde"] == {}, r["desborde"]
        names = set(r["estados"])
        for s in walk.MANAGEMENT + ("partido_ficha", "anadir_1", "anadir_5", "golpes", "golpe"):
            assert s in names, s
        assert sum(n.startswith("leccion_fase_") for n in names) == 9
        assert all(f"mas_{s}" in names for s in walk.MORE + walk.OPTIONAL_MORE)
        assert "situacion_celda" in names and "apoyo" in r["estados"]["situacion_celda"]
        assert "Datos de ejemplo" in r["estados"]["inicio"]


def test_the_swing_path_is_drawn_on_a_canvas():
    """#306 (15-11): the swing's whole path over the stroke (the short the user chose) is a real drawing, not a word
    beside a placeholder: the stroke's panel has a canvas with dots on it when the stroke has its path."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    html = p0_app.pagina(p0_app.ejemplo())
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page(viewport={"width": 1280, "height": 800})
        p.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body>' + html + "</body></html>")
        p.evaluate("() => location.hash = 'visor'")
        p.wait_for_timeout(200)
        p.click('[data-tab="golpes"]')
        p.wait_for_timeout(150)
        ids = [s["id"] for s in p0_app.ejemplo()["strokes"] if s.get("trayectoria")]
        p.click(f'[data-stroke="{ids[0]}"]')
        p.wait_for_timeout(300)
        drawn = p.evaluate("""() => { const c = document.querySelector('canvas[data-trayectoria]'); if (!c) return -1;
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
            for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; }""")
        b.close()
    assert drawn > 200, drawn


FAKE_PC = """() => { window.__calls = [];
  const answers = {elegir_video: "C:/tenis/videos/partido.mp4", proponer: {rival: "Rival de ejemplo", torneo: "Torneo"},
                   fotos: [{src: "data:image/gif;base64,R0lGODlhAQABAAAAACw=", t: 12.5, by: "clothes"}]};
  window.pywebview = {api: new Proxy({}, {get: (_, k) => (...a) => { window.__calls.push([k, a]);
    return Promise.resolve(k in answers ? answers[k] : {ok: true, cuando: "ahora", partido: "jugadora-rival-torneo"}); }})};
}"""


def _page(pw, fake: bool):
    b = pw.chromium.launch()
    p = b.new_page(viewport={"width": 1280, "height": 800})
    p.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                  + p0_app.pagina(p0_app.ejemplo()) + "</body></html>")
    if fake:
        p.evaluate(FAKE_PC)
    return b, p


def test_management_works_only_in_the_pcs_window_and_says_so():
    """P0.5d: in a browser there is no window: every management action is disabled and says where it works (never a
    button that pretends); the queue's waits and refused requests are shown."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b, p = _page(pw, fake=False)
        p.evaluate("() => location.hash = 'cola'")
        p.wait_for_timeout(200)
        cola = p.evaluate("() => [...document.querySelectorAll('button[data-pc]')].map(x => [x.dataset.pc, x.disabled, x.title])")
        text = p.inner_text("body")
        p.evaluate("() => location.hash = 'inicio'")
        p.wait_for_timeout(150)
        inicio = p.inner_text("body")
        b.close()
    assert cola and all(dis and "aplicación del PC" in t for _, dis, t in cola), cola
    assert "Lo que la cola no pudo hacer" in text and "no es de un tipo conocido" in text
    assert "falta el clic" in inicio


def test_the_wizard_asks_the_pc_for_each_step_with_her_yes_to_the_preparation():
    """P0.5d: with the PC's window, the wizard chooses the video, fills its record, uploads it only with her yes to the
    preparation, sends her click on a photo and her approval; the queue's pause goes the same way."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b, p = _page(pw, fake=True)
        p.evaluate("() => location.hash = 'partidos'")
        p.wait_for_timeout(150)
        p.click("[data-add]")
        p.wait_for_timeout(150)
        p.click('[data-pc="elegir"]')
        p.wait_for_timeout(150)
        p.click('[data-step="1"]')
        p.wait_for_timeout(100)
        assert p.is_disabled('[data-pc="alta"]')                     # not without her yes
        p.check('input[type="checkbox"]')
        p.click('[data-pc="alta"]')
        p.wait_for_timeout(150)
        p.click('[data-step="1"]')
        p.click('[data-pc="fotos"]')
        p.wait_for_timeout(150)
        p.click('[data-pc="clic"]')
        p.wait_for_timeout(100)
        p.click('[data-step="1"]')
        p.click('[data-pc="aprobar"]')
        p.wait_for_timeout(100)
        p.keyboard.press("Escape")
        p.evaluate("() => location.hash = 'cola'")
        p.wait_for_timeout(150)
        p.click('[data-pc="pausar"]')
        p.wait_for_timeout(100)
        calls = p.evaluate("() => window.__calls")
        b.close()
    by = {k: a for k, a in calls}
    assert [k for k, _ in calls] == ["elegir_video", "proponer", "alta", "fotos", "clic", "aprobar", "pausar"], calls
    ruta, ficha, preparar = by["alta"]
    assert ruta == "C:/tenis/videos/partido.mp4" and preparar is True
    assert ficha["jugadora"] == "Jugadora de ejemplo" and ficha["rival"] == "Rival de ejemplo" and ficha["torneo"] == "Torneo"
    assert by["clic"] == ["jugadora-rival-torneo", 12.5, True, "clothes"]
    assert by["aprobar"][0] == "jugadora-rival-torneo" and by["aprobar"][1]["coste_eur"] == 0


def test_the_measures_explorer_lists_every_measure_with_its_strokes():
    """Design change 1 (docs/p0_diseno.md §10): every measure by family, with how many strokes have it and her typical
    value; a measure opens its spread and its extreme strokes (with their video panel)."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    d = p0_app.ejemplo()
    with sync_playwright() as pw:
        b, p = _page(pw, fake=False)
        p.evaluate("() => location.hash = 'visor'")
        p.wait_for_timeout(200)
        p.click('[data-tab="mas"]')
        p.click('[data-sub="medidas"]')
        p.wait_for_timeout(150)
        rows = p.evaluate("() => [...document.querySelectorAll('tr[data-medida]')].map(r => r.dataset.medida)")
        key = f"{d['phases'][2]['id']}.medida_1"
        p.click(f'tr[data-medida="{key}"]')
        p.wait_for_timeout(100)
        detail = p.inner_text("[data-medida-detalle]")
        extremes = p.evaluate("() => document.querySelectorAll('[data-medida-golpe]').length")
        p.click('[data-fam="contexto"]')
        p.wait_for_timeout(100)
        ctx = p.evaluate("() => [...document.querySelectorAll('tr[data-medida]')].map(r => r.dataset.medida)")
        b.close()
    checks = [c["key"] for f in d["phases"] for c in f["checks"]]
    assert set(checks) <= set(rows) and {"sh", "xf"} <= set(rows)
    assert "12 golpes" in detail and extremes == 6
    assert ctx and all(k.startswith("ctx.") for k in ctx)


def test_tactics_put_her_strokes_together_by_point():
    """Design change 2 (docs/p0_diseno.md §10): the length of her points (counted by point), where in the point she
    misses, two forehands in a row, and a whole point on a numbered mini-map whose strokes open their panel."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b, p = _page(pw, fake=False)
        p.evaluate("() => location.hash = 'visor'")
        p.wait_for_timeout(200)
        p.click('[data-tab="mas"]')
        p.click('[data-sub="tactica"]')
        p.wait_for_timeout(150)
        text = p.inner_text("section.content")
        dots = p.evaluate("() => document.querySelectorAll('[data-minimapa] text').length")
        golpes = p.evaluate("() => document.querySelectorAll('[data-punto-golpe]').length")
        p.click('[data-punto="1"]')
        p.wait_for_timeout(100)
        text2 = p.inner_text("section.content")
        b.close()
    # the example: 12 strokes in 4 points of 3 (two per match, 100 s apart), 1.º to 3.º each
    assert "4 puntos vistos desde su principio" in text and "punto 1 de 4" in text and "punto 2 de 4" in text2
    assert dots == 3 and golpes == 3
    assert "Dos derechas seguidas" in text and "8 pares" in text


def test_the_return_says_how_it_is_found_and_its_variants():
    """Design change 3 (docs/p0_diseno.md §10): the return of serve: how it is recognised, the serve received, the side,
    first or second serve, the kind of return, where she waits; each return opens its panel."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b, p = _page(pw, fake=False)
        p.evaluate("() => location.hash = 'visor'")
        p.wait_for_timeout(200)
        p.click('[data-tab="mas"]')
        p.click('[data-sub="resto"]')
        p.wait_for_timeout(150)
        text = p.inner_text("section.content")
        n = p.evaluate("() => document.querySelectorAll('[data-resto]').length")
        b.close()
    restos = [g for g in p0_app.ejemplo()["strokes"] if g.get("play") == "resto"]
    assert n == len(restos) == 4
    assert "icono de saque del marcador" in text and "El saque que recibe" in text and "Tipo de resto" in text
    assert "4 restos de derecha" in text.replace("\n", " ") or "4\nrestos de derecha" in text
    assert "pocos" in text            # 4 returns: below the minimum, no median of where she waits


def test_everything_the_matrix_marks_not_measurable_is_said():
    """Design change 9 (docs/p0_diseno.md §10): each row the coverage matrix marks ✘ is in «Lo que la tele no mide», with
    its reason and source, without repeating what the report's own list says, and without code names or markdown."""
    md = (ROOT / "docs" / "matriz_cobertura.md").read_text(encoding="utf-8")
    rows = p0_app.no_medible(md, [])
    names = [r[0] for r in rows]
    assert "Mirada" in names and "Empuñadura (bisel)" in names and "Fuerzas, momentos articulares" in names
    assert all("`" not in t and "**" not in t and "()" not in t for _, t in rows)
    assert dict(rows)["Empuñadura (bisel)"] == "Mano de 20-40 px (Yandell; Elliott 1997)."
    again = p0_app.no_medible(md, [["Fuerzas y momentos articulares", "solo cinemática"]])
    assert "Fuerzas, momentos articulares" not in [r[0] for r in again] and len(again) == len(rows) - 1
