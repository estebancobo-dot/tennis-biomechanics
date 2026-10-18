"""Part 3 of the local application (docs/aplicacion_local.md §4, §6): Windows notifications, the icon next to
the clock, the disk guard in the background and the backup to a USB drive."""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import test_app_core as T  # noqa: E402
from test_app_core import env  # noqa: E402,F401

from tennisbio.app import backup, jobs, notify, storage, window  # noqa: E402
from tennisbio.app.core import App  # noqa: E402


# ---------------------------------------------------------------- notifications ----------------------

def test_notifications_follow_the_switches_and_never_repeat(env):
    a = env.app()
    shown = []
    show = lambda t, x: shown.append(t) or True
    a.db.notice("updated_x", "ok", "Derecha de Rybakina actualizada: 336 ✔, 0 ✘.")
    a.db.notice("error_1", "crit", "AO 2023: error del programa (ValueError). Guardado el diagnóstico.")
    a.db.notice("disk_low", "aviso", "Poco disco: quedan 32 GB. Se pueden liberar 2 GB.")
    a.db.notice("plan", "info", "Nueva versión: recalcula 1 partido.")
    a.db.set_setting("avisos", {"fallo": False})
    notify.send_pending(a.db, show)
    assert shown == ["Tennisbio · Derecha de Rybakina actualizada: 336 ✔, 0 ✘.", "Tennisbio · Poco disco: quedan 32 GB"]
    a.db.notice("disk_low", "aviso", "Poco disco: quedan 32 GB. Se pueden liberar 2 GB.")       # the guard, again
    a.db.set_setting("avisos", {"fallo": True})
    notify.send_pending(a.db, show)
    assert len(shown) == 2                                     # neither the same text again, nor the old one switched on later
    a.db.notice("disk_low", "aviso", "Poco disco: quedan 18 GB. Liberados 3,1 GB.")              # it changed: shown
    notify.send_pending(a.db, show)
    assert shown[-1] == "Tennisbio · Poco disco: quedan 18 GB"


def test_toast_text_is_escaped():
    x = notify.toast_xml("A & B <c>", "1 < 2")
    assert "A &amp; B &lt;c&gt;" in x and "1 &lt; 2" in x and x.startswith("<toast>")


def test_index_from_part_2_gets_the_new_column_without_old_notices_popping_up(env):
    a = env.app()
    a.db.notice("updated_x", "ok", "antes de la parte 3")
    a.db.con.execute("ALTER TABLE notices RENAME TO n_old")
    a.db.con.execute("CREATE TABLE notices (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, level TEXT, text TEXT, "
                     "created TEXT, seen INTEGER DEFAULT 0)")
    a.db.con.execute("INSERT INTO notices (key, level, text, created) SELECT key, level, text, created FROM n_old")
    a.db.con.commit()
    a.close()
    b = env.app()
    assert notify.send_pending(b.db, lambda t, x: True) == []


# ---------------------------------------------------------------- backup -----------------------------

@pytest.fixture
def analysed(env):
    a = env.app()
    T._added(env, a)
    a.work()
    return a


def test_backup_copies_what_took_hours_and_then_only_what_changed(env, analysed, tmp_path):
    a, usb = analysed, tmp_path / "USB"
    usb.mkdir()
    out = a.paths.output
    mdir = next(d for d in out.iterdir() if d.is_dir() and (d / "manifest.json").exists())
    (mdir / "windows").mkdir()
    (mdir / "windows" / "w001.mp4").write_bytes(b"clip" * 100)
    (mdir / "cache.npz.tmp").write_bytes(b"half")                                 # temporary: never copied
    r = backup.run(a, usb)
    base = usb / backup.FOLDER
    assert (base / "output" / mdir.name / "windows" / "w001.mp4").exists() and (base / "output" / mdir.name / "manifest.json").exists()
    assert not (base / "output" / mdir.name / "cache.npz.tmp").exists()
    assert (base / "output" / "analisis" / "rybakina_forehand" / "actual" / "index.html").exists()
    assert (base / "config" / "players" / "rybakina.yaml").exists()
    assert (base / "datos" / "tennisbio.db").exists() and not list((base / "videos").glob("*")) if (base / "videos").exists() else True
    assert r["copied"] > 0 and not r["errors"] and a.db.setting("copia")["copied"] == r["copied"]
    (base / "mio.txt").write_text("algo del usuario")                              # never deleted
    assert backup.run(a, usb)["copied"] == 0                                       # incremental
    (mdir / "manifest.json").write_text("{}")
    assert backup.run(a, usb)["copied"] == 1
    assert (base / "mio.txt").exists()
    r = backup.run(a, usb, videos=True)
    assert list((base / "videos").glob("*.mp4"))


def test_backup_that_does_not_fit_copies_nothing(env, analysed, tmp_path, monkeypatch):
    usb = tmp_path / "USB"
    usb.mkdir()
    monkeypatch.setattr(storage, "free_bytes", lambda p: 10)
    with pytest.raises(RuntimeError, match="No cabe en el USB"):
        backup.run(analysed, usb)
    assert not (usb / backup.FOLDER).exists()


def test_archived_matches_are_left_out(env, analysed, tmp_path):
    mid = analysed.db.one("SELECT id FROM matches")["id"]
    analysed.db.x("UPDATE matches SET state='archivado' WHERE id=?", mid)
    srcs = [str(s) for s, _ in backup._files(analysed, False)]
    assert not any(f"{mid}/" in s.replace("\\", "/") for s in srcs)


# ---------------------------------------------------------------- icon and background loop ------------

def test_tray_label_says_what_it_does(env, analysed):
    a = analysed
    assert window.tray_text(a) == "Tennisbio · todo al día"
    jobs.enqueue(a.db, "partido", match="x", player="rybakina", reason="r")
    assert window.tray_text(a) == "Tennisbio · 1 trabajo(s) esperando"
    a.db.x("UPDATE jobs SET state='en curso' WHERE match='x'")
    assert window.tray_text(a).startswith("Tennisbio · analizando x · termina ")
    a.db.set_setting("pausa", True)
    assert window.tray_text(a) == "Tennisbio · cola en pausa"
    a.db.notice("error_9", "crit", "fallo")
    assert window.tray_text(a).endswith("· 1 aviso(s)") and len(window.tray_text(a)) <= 127


def test_background_loop_runs_jobs_notifies_and_updates_the_icon(env, monkeypatch):
    a = env.app()
    T._added(env, a)
    a.close()
    monkeypatch.setattr(window, "App", lambda cfg: App(cfg, engine_factory=T.FakeEngine, config_dir=env.cfgdir))
    shown, labels = [], []
    monkeypatch.setattr(notify, "show", lambda t, x: shown.append(t) or True)
    tray = type("Tray", (), {"update": lambda self, t: labels.append(t)})()
    stop = threading.Event()
    th = threading.Thread(target=window.worker, args=(env.cfg, stop), kwargs={"idle_s": 0.2, "tray": tray}, daemon=True)
    th.start()
    for _ in range(100):
        if labels and labels[-1] == "Tennisbio · todo al día":
            break
        time.sleep(0.05)
    stop.set()
    th.join(5)
    b = env.app()
    assert not b.db.q("SELECT id FROM jobs WHERE state NOT IN ('hecho')")          # the match and its report
    assert any("actualizada" in s for s in shown) and labels[-1] == "Tennisbio · todo al día"


def test_window_switches_and_backup_button(env, analysed, tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright
    from test_app_window import CHROMIUM, _browser, _live
    if not CHROMIUM.exists():
        pytest.skip("sin navegador")
    usb = tmp_path / "USB"
    usb.mkdir()
    api = window.Api(analysed)
    monkeypatch.setattr(window.Api, "drives", lambda self: [{"root": str(usb), "free": 64e9, "total": 64e9}])
    page = window.write_page(analysed)
    with sync_playwright() as p:
        b = _browser(p)
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        _live(pg, api)
        pg.goto(page.as_uri())
        pg.wait_for_function("window.__tbReady === true")
        pg.evaluate("location.hash = '#ajustes'")
        pg.click("label:has(input[data-aviso=fin])")                           # as the user: on the switch
        pg.wait_for_timeout(300)
        assert notify.settings(analysed.db)["fin"] is False
        pg.evaluate("location.hash = '#almacenamiento'")
        pg.wait_for_selector("button[data-act=backup]")
        pg.click("button[data-act=backup]")
        for _ in range(100):
            if analysed.db.setting("copia"):
                break
            time.sleep(0.05)
        pg.wait_for_timeout(1500)
        assert "Última copia" in pg.inner_text("#bkBody")
        b.close()
    assert (usb / backup.FOLDER / "datos" / "tennisbio.db").exists()
    assert "Copia de seguridad hecha" in analysed.db.one("SELECT text FROM notices WHERE key='backup'")["text"]


def test_a_second_double_click_does_not_start_a_second_queue(env, monkeypatch):
    shown = []
    monkeypatch.setattr(notify, "show", lambda t, x: shown.append(t) or True)
    monkeypatch.setattr(window, "App", lambda cfg: App(cfg, engine_factory=T.FakeEngine, config_dir=env.cfgdir))
    a = env.app()
    assert not window.already_open(a)                              # the first one takes its place
    pidf = a.paths.data / "ventana.pid"
    import subprocess
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        pidf.write_text(str(other.pid))                            # another Tennisbio is running
        assert window.run(env.cfg) == 0 and shown == ["Tennisbio ya está abierto"]
    finally:
        other.kill()
        other.wait()
    assert not window.already_open(a)                              # it ended: the next one starts normally
