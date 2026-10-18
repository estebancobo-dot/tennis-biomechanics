"""The window (docs/aplicacion_local.md §4, part 2), in a browser: every screen with the cases of §5 (no page
error, no sideways scroll at 1280 and on a phone, the case said in words), and the page wired to the real
`Api` (through a test bridge in place of pywebview): each button changes the index as it says."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import test_app_core as T  # noqa: E402
from test_app_core import env  # noqa: E402,F401 — the same fixture as the core's tests

from tennisbio.app import jobs, storage, videos, window  # noqa: E402
from tennisbio.app.core import App  # noqa: E402

CHROMIUM = Path("/opt/pw-browsers/chromium")
pytestmark = pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la ventana")
SCREENS = ["inicio", "analisis", "partidos", "jugadoras", "cola", "calidad", "almacenamiento", "ajustes"]


@pytest.fixture
def scene(env, monkeypatch):
    """Matches analysed, a doubles one, an error in the queue, a regression, a long plan waiting, low disk,
    a left-handed player without height."""
    (env.cfgdir / "players" / "fernandez.yaml").write_text("name: Leylah Fernandez\nhand: left\n", encoding="utf-8")
    monkeypatch.setattr(storage, "free_bytes", lambda p: 32e9)
    a = env.app()
    _, m1 = T._added(env, a, round="F")
    _, dbl = T._added(env, a, "2023_Eastbourne_dobles_Rybakina.mp4", b"b")
    a.engine.manifests[dbl] = {"candidates": {"summary": {"candidates": 0, "doubles": True}}}
    _, m3 = T._added(env, a, "2024_Indian_Wells_Rybakina_Sabalenka.mp4", b"c")
    a.work()
    a.engine.audit_items = [{"name": "La lección", "status": "falta", "detail": "4 fases sin vídeo"},
                            {"name": "Primera pantalla", "status": "ok", "detail": ""}]
    jobs.enqueue(a.db, "informe", player="rybakina", stroke="forehand", reason="nueva versión del informe")
    a.work()
    _, m4 = T._added(env, a, "2024_Madrid_Rybakina.mp4", b"d")
    a.engine.fail = [ValueError("índice fuera de rango")]
    a.work(max_jobs=1)
    jobs.enqueue(a.db, "partido", match=m3, player="rybakina", reason="nueva versión: cambió fine", confirm=True)
    storage.guard(a.db, a.paths.output)
    return SimpleNamespace(app=a, env=env, m1=m1, dbl=dbl, m3=m3, m4=m4)


def _browser(p):
    return p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])


def test_every_screen_says_its_cases_without_errors_or_sideways_scroll(scene):
    from playwright.sync_api import sync_playwright
    page = window.write_page(scene.app)
    expect = {
        "inicio": ["Hay avisos", "error del programa", "empeoró", "Poco disco"],
        "partidos": ["Australian Open 2023 · F", "Excluido", "dobles", "Error"],
        "cola": ["Reintentar", "Diagnóstico", "por confirmar", "Confirmar"],
        "calidad": ["regresión", "Qué empeoró", "La lección: ok → falta"],
        "almacenamiento": ["Quedan 32 GB libres", "Liberar"],
        "analisis": ["Derecha de Elena Rybakina", "Versión anterior"],
        "jugadoras": ["zurda: medidas reflejadas", "sin altura: 1,80 m ±5 %"],
        "ajustes": ["Franja horaria", "Comprobar qué recalcular"],
    }
    problems = []
    with sync_playwright() as p:
        b = _browser(p)
        for w, h in [(1280, 900), (390, 844)]:
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.on("pageerror", lambda e: problems.append(f"error de página: {e}"))
            pg.goto(page.as_uri())
            pg.wait_for_function("window.__tbReady === true")
            for sc in SCREENS + [f"partido/{scene.m3}", f"partido/{scene.dbl}", "jugadora/fernandez", "jugadora/rybakina"]:
                pg.evaluate(f"location.hash = {json.dumps('#' + sc)}")
                pg.wait_for_timeout(80)
                txt = pg.inner_text(".screen.on")
                if not txt.strip():
                    problems.append(f"{w}: {sc} vacía")
                if pg.evaluate("document.documentElement.scrollWidth > innerWidth + 1"):
                    problems.append(f"{w}: {sc} se sale por el lado")
                for t in expect.get(sc, []):
                    if t not in txt:
                        problems.append(f"{w}: {sc} no dice «{t}»")
        b.close()
    assert not problems, problems


def _live(pg, api):
    """The page wired to the real Api, as pywebview does it (window.pywebview.api.<method>() → promise)."""
    def tbcall(name, args):
        return json.loads(json.dumps(getattr(api, name)(*json.loads(args)), default=str))
    pg.expose_function("tbcall", tbcall)
    pg.add_init_script("""window.pywebview = {api: new Proxy({}, {get: function (t, k) {
        return function () { return window.tbcall(k, JSON.stringify(Array.prototype.slice.call(arguments))); }; }})};""")


def test_buttons_change_the_index_as_they_say(scene, monkeypatch):
    from playwright.sync_api import sync_playwright
    a = scene.app
    api = window.Api(a)
    new_video = scene.env.make("2024_Wimbledon_F_Rybakina_Sabalenka.mp4", b"w")
    monkeypatch.setattr(window.Api, "choose_video", lambda self: str(new_video))
    page = window.write_page(a)
    with sync_playwright() as p:
        b = _browser(p)
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        _live(pg, api)
        pg.goto(page.as_uri())
        pg.wait_for_function("window.__tbReady === true")
        assert pg.is_hidden("#roNote")                                     # live: not read-only
        # pause / resume the queue
        pg.evaluate("location.hash = '#cola'")
        pg.click("button[data-act=pause]")
        pg.wait_for_timeout(300)
        assert a.db.setting("pausa") is True
        # retry the job in error
        err = a.db.one("SELECT id FROM jobs WHERE state='error'")["id"]
        pg.click(f"button[data-act=retry][data-arg='{err}']")
        pg.wait_for_timeout(300)
        assert a.db.one("SELECT state FROM jobs WHERE id=?", err)["state"] == "pendiente"
        # the long plan waiting for one click
        pg.click("button[data-act=confirm_plan]")
        pg.wait_for_timeout(300)
        assert not a.db.q("SELECT id FROM jobs WHERE state='por confirmar'")
        # «Analizar también…»: the rival's forehand
        pg.evaluate("location.hash = '#analisis'")
        pg.click(".head [data-open=also]")
        pg.click("#matrix button.cell[data-k='sabalenka:forehand']")
        assert "pasada fina en" in pg.inner_text("#alsoCost")
        pg.click("#alsoGo")
        pg.wait_for_timeout(400)
        assert a.db.q("SELECT id FROM jobs WHERE kind='rival' AND player='sabalenka'")
        # add a match: choose, proposal, confirm
        pg.evaluate("location.hash = '#partidos'")
        pg.click(".head [data-open=add]")
        pg.click("#addNext")
        pg.wait_for_selector("#fP")
        assert pg.input_value("#fT") == "Wimbledon" and pg.input_value("#fD") == "2024"
        pg.select_option("#fP", "rybakina")
        pg.click("#addNext")
        pg.wait_for_selector("#addDone .alert")
        assert "Encolado" in pg.inner_text("#addDone")
        mid = a.db.one("SELECT id FROM matches WHERE tournament='Wimbledon'")["id"]
        assert a.db.one("SELECT id FROM jobs WHERE kind='partido' AND match=?", mid)
        pg.click("#dlg-add [data-close]")
        # archive, never delete
        pg.evaluate(f"location.hash = '#partido/{scene.m1}'")
        pg.wait_for_timeout(200)
        pg.click("button[data-act=archive]")
        pg.wait_for_timeout(300)
        assert a.db.one("SELECT state FROM matches WHERE id=?", scene.m1)["state"] == "archivado"
        assert (scene.env.vids / "2023_Australian_Open_F_Sabalenka_Rybakina.mp4").exists()
        # the analysis web opens inside the window, with «Volver»
        pg.evaluate("location.hash = '#analisis'")
        pg.wait_for_timeout(200)
        pg.click("a.acard[href='#web/rybakina_forehand']")
        pg.wait_for_timeout(300)
        assert pg.evaluate("document.body.classList.contains('web')")
        src = pg.get_attribute("#webFrame", "src")
        assert src.startswith("file:///") and src.endswith("analisis/rybakina_forehand/actual/index.html")
        pg.click("#webBack")
        pg.wait_for_timeout(200)
        assert not pg.evaluate("document.body.classList.contains('web')")
        b.close()
    assert not errs, errs


def test_read_only_page_says_so_and_changes_nothing(scene):
    from playwright.sync_api import sync_playwright
    page = window.write_page(scene.app)
    with sync_playwright() as p:
        b = _browser(p)
        pg = b.new_page()
        pg.goto(page.as_uri())
        pg.wait_for_function("window.__tbReady === true")
        assert pg.is_visible("#roNote")
        pg.evaluate("location.hash = '#cola'")
        pg.click("button[data-act=pause]")
        pg.wait_for_timeout(200)
        assert "solo lectura" in pg.inner_text("#toast")
        b.close()
    assert not scene.app.db.setting("pausa")


def test_without_the_window_engine_it_opens_in_the_browser(env, monkeypatch):
    """§5.4 «Navegador o motor de la ventana ausente»."""
    import builtins
    opened = []
    real_import = builtins.__import__

    def no_webview(name, *a, **k):
        if name == "webview":
            raise ImportError("no pywebview")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_webview)
    monkeypatch.setattr(window.webbrowser, "open", lambda u: opened.append(u))
    monkeypatch.setattr(window, "App", lambda cfg: App(cfg, engine_factory=T.FakeEngine, config_dir=env.cfgdir))
    assert window.run(env.cfg) == 0
    page = Path(env.cfg["paths"]["data"]) / "tennisbio.html"
    assert page.exists() and opened == [page.resolve().as_uri()]
    assert '"storage"' in page.read_text(encoding="utf-8")                  # the read-only page carries the disk too


def test_the_pc_check_finds_nothing_wrong_in_the_cases(scene, tmp_path):
    """app/check.py, the check the PC runs with the real index: every screen and every match and player page,
    at 1280 and on a phone, with screenshots."""
    from tennisbio.app.check import check
    r = check(scene.app, tmp_path / "capturas_app")
    assert not r["problems"], r["problems"]
    assert r["screens"] >= 2 * (8 + 4 + 3) and (tmp_path / "capturas_app" / "app_cola.png").exists()
    assert "Ventana de Tennisbio: OK" in (tmp_path / "capturas_app" / "ventana.md").read_text(encoding="utf-8")


def test_a_window_engine_that_never_answers_cannot_hang_the_check(scene, tmp_path, monkeypatch):
    """18-10 on the PC: the hidden WebView2 window never loaded and the check waited forever, stopping the
    automatic cycle. The real window now runs in a process killed after its limit."""
    from tennisbio.app import check as C
    import subprocess
    real_run = subprocess.run

    def slow(cmd, **kw):                                     # a child that never ends
        return real_run([sys.executable, "-c", "import time; time.sleep(60)"], **kw)
    monkeypatch.setattr(subprocess, "run", slow)
    import time
    t0 = time.time()
    out = C.live_window(scene.app, tmp_path, timeout_s=2)
    assert time.time() - t0 < 10 and "sin respuesta en 2 s" in out["error"] and not out["ready"]
