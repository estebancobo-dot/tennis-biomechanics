"""Part 4 of the local application (docs/aplicacion_local.md §5.1 «Copia al móvil», §6 «Lanzar»): the copy of an
analysis for the phone (a folder and a .zip that work without connection, clips at 720p) and the desktop
shortcut. The copy is checked in a real browser at phone size: the skeleton still falls on the player in the
720p clip (the page draws in the original's pixels and scales only the picture)."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import test_app_core as T  # noqa: E402
from test_app_core import env  # noqa: E402,F401
from test_stroke_page import stroke_and_series  # noqa: E402

from tennisbio.app import mobile, shortcut, storage, window  # noqa: E402
from tennisbio.catalog import Match, Player  # noqa: E402
from tennisbio.report import build  # noqa: E402

CHROMIUM = Path("/opt/pw-browsers/chromium")
RED = (330, 300, 40, 40)                         # a red square in the 1920 × 1080 window, around the wrist (350, 320)


# the test browser (open-source Chromium) has no H.264, which every phone has: the clips the browser must
# decode are VP9 here; the real encoder's H.264 at 720p is checked with ffprobe
VP9 = ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "40", "-deadline", "realtime", "-cpu-used", "8"]


def _window(path: Path, size="1920x1080", codec=("-c:v", "libx264"), bg="color=c=black"):
    x, y, w, h = RED
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{bg}:s={size}:d=2.5" + ("" if "r=" in bg else ":r=50"),
                    "-f", "lavfi", "-i", "sine=d=2.5", "-vf", f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red:t=fill",
                    *codec, "-pix_fmt", "yuv420p", "-shortest", str(path)], check=True)


def _vp9_720(src: Path, dst: Path) -> bool:
    return subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=-2:720", *VP9, "-an", str(dst)]).returncode == 0


def _analysis(root: Path, n=3, size="1920x1080", codec=("-c:v", "libx264"), bg="color=c=black") -> SimpleNamespace:
    """A real analysis web (report.build) published as the app does: <output>/analisis/p_forehand/actual."""
    out = root / "output"
    d = out / "m1"
    (d / "series").mkdir(parents=True)
    (d / "windows").mkdir()
    s, ser = stroke_and_series()
    strokes = []
    for i in range(n):
        (d / "series" / f"x{i}.json").write_text(json.dumps(ser), encoding="utf-8")
        _window(d / "windows" / f"w{i}.mp4", size, codec, bg)
        strokes.append({**s, "series": f"series/x{i}.json", "window": f"w{i}.mp4", "window_impact_s": 1.2, "match_time_s": 30.0 + i})
    (d / "strokes.json").write_text(json.dumps(strokes), encoding="utf-8")
    web = out / "analisis" / "p_forehand" / "actual"
    build([Match("m1", None, Player("p", "P", height_m=1.84))], out, web)
    (web.parent / "analisis.json").write_text(json.dumps({"version": 3}), encoding="utf-8")
    paths = SimpleNamespace(output=out, analyses=out / "analisis", data=root / "datos")
    return SimpleNamespace(paths=paths, web=web, match=d)


def _probe_h(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return int(r.stdout.strip())


def test_phone_copy_has_everything_inside_at_720p_and_a_zip(tmp_path):
    A = _analysis(tmp_path)
    r = mobile.make(A.paths, "p", "forehand")
    dest = tmp_path / "movil" / "p_forehand"
    assert r["dest"] == str(dest) and r["with_video"] == r["strokes"] == 3 and r["encoded"] == 3 and not r["failed"]
    data, _, _ = mobile.read_data((dest / "index.html").read_text(encoding="utf-8"))
    for s in data["strokes"]:
        assert s["video"] == f"v/{s['id']}.mp4" and abs(s["vk"] - 720 / 1080) < 1e-3
        assert _probe_h(dest / s["video"]) == 720
        assert (dest / s["series"]).exists() and (not s.get("thumb") or (dest / s["thumb"]).exists())
    # nothing outside the folder: every relative path stays inside it
    refs = [s[k] for s in data["strokes"] for k in ("video", "series", "thumb") if s.get(k)] + data["exports"]
    assert refs and not [x for x in refs if x.startswith("..") or ":" in x or x.startswith("/")]
    assert data["mobile"]["from_version"] == 3
    with zipfile.ZipFile(r["zip"]) as z:
        names = set(z.namelist())
    assert "p_forehand/index.html" in names and "p_forehand/LEEME.txt" in names
    assert {f"p_forehand/{s['video']}" for s in data["strokes"]} <= names
    # the original web is untouched
    orig, _, _ = mobile.read_data((A.web / "index.html").read_text(encoding="utf-8"))
    assert all("vk" not in s and s["video"].startswith("../") for s in orig["strokes"])


def test_again_only_what_changed_and_what_left_goes(tmp_path):
    A = _analysis(tmp_path)
    mobile.make(A.paths, "p", "forehand", zip_it=False)
    r = mobile.make(A.paths, "p", "forehand", zip_it=False)
    assert r["encoded"] == 0 and r["kept"] == 3
    (A.match / "windows" / "w1.mp4").unlink()                     # its clip is gone from the PC
    r = mobile.make(A.paths, "p", "forehand", zip_it=False)
    data, _, _ = mobile.read_data((Path(r["dest"]) / "index.html").read_text(encoding="utf-8"))
    assert r["missing"] == 1 and r["with_video"] == 2 and r["removed"] == 1
    assert sum(1 for s in data["strokes"] if not s.get("video")) == 1   # «sin vídeo», never a broken link
    assert len(list((Path(r["dest"]) / "v").glob("*.mp4"))) == 2


def test_a_clip_already_small_is_not_enlarged_and_has_no_scale(tmp_path):
    A = _analysis(tmp_path, n=1, size="1280x720")
    r = mobile.make(A.paths, "p", "forehand", zip_it=False)
    data, _, _ = mobile.read_data((Path(r["dest"]) / "index.html").read_text(encoding="utf-8"))
    assert "vk" not in data["strokes"][0] and _probe_h(Path(r["dest"]) / data["strokes"][0]["video"]) == 720


def test_a_clip_that_cannot_be_converted_is_said(tmp_path):
    A = _analysis(tmp_path, n=2)
    r = mobile.make(A.paths, "p", "forehand", zip_it=False, enc=lambda src, dst: src.name != "w0.mp4" and mobile.encode(src, dst))
    assert len(r["failed"]) == 1 and r["with_video"] == 1


def test_no_room_or_no_analysis_copies_nothing(tmp_path, monkeypatch):
    A = _analysis(tmp_path, n=1)
    monkeypatch.setattr(storage, "free_bytes", lambda p: 1e9)
    with pytest.raises(RuntimeError, match="No cabe la copia para el móvil"):
        mobile.make(A.paths, "p", "forehand")
    assert not (tmp_path / "movil" / "p_forehand").exists()
    with pytest.raises(FileNotFoundError, match="Todavía no hay análisis publicado"):
        mobile.make(A.paths, "q", "forehand")


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador")
def test_on_the_phone_the_skeleton_still_falls_on_the_player(tmp_path):
    """Phone size, from the folder (file://): no page error, the stroke's 720p clip plays and the point of the
    wrist in the original's pixels lands on the red square of the picture, as in the PC's web."""
    from playwright.sync_api import sync_playwright
    A = _analysis(tmp_path, n=1, codec=VP9)
    r = mobile.make(A.paths, "p", "forehand", zip_it=False, enc=_vp9_720)
    probe = """async () => { showTab('golpe'); await loadStroke(STROKES[0]); await new Promise(r => setTimeout(r, 600));
      const c = document.createElement('canvas'); c.width = 640; c.height = 360; const ctx = c.getContext('2d');
      drawFrame(ctx, 640, 360, 10, {skel: false, trail: false, ball: false});
      const [sx, sy, sw] = cropRect(10, 640 / 360), k = 640 / sw, x = Math.round((350 - sx) * k), y = Math.round((320 - sy) * k);
      const px = ctx.getImageData(x, y, 1, 1).data; return [px[0], px[1], px[2], MAIN.video.videoHeight]; }"""
    got = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        for name, page in (("pc", A.web / "index.html"), ("movil", Path(r["dest"]) / "index.html")):
            pg = b.new_page(viewport={"width": 390, "height": 844})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(page.resolve().as_uri())
            pg.wait_for_timeout(500)
            got[name] = pg.evaluate(probe)
            assert not errs, (name, errs[:3])
            if name == "movil":                                     # without the scale the point misses the player
                pg.evaluate("STROKES[0].vk = 1")
                got["sin_escala"] = pg.evaluate(probe)
                assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        b.close()
    red = lambda px: px[0] > 150 and px[1] < 90 and px[2] < 90
    assert got["pc"][3] == 1080 and got["movil"][3] == 720
    assert red(got["pc"]) and red(got["movil"]), got
    assert not red(got["sin_escala"]), got


# ---------------------------------------------------------------- from the window --------------------

def _app_with_web(env, codec=("-c:v", "libx264"), bg="color=c=black"):
    """The app after its first analysis, with a real web (report.build) in place of the fake engine's."""
    import os
    import shutil
    a = env.app()
    T._added(env, a)
    a.work()
    web = a.paths.analyses / "rybakina_forehand" / "actual"
    A = _analysis(env.tmp / "src", n=1, codec=codec, bg=bg)
    for f in A.web.iterdir():                                     # a real web in place of the fake engine's
        if f.is_file():
            (web / f.name).write_bytes(f.read_bytes())
    for sub in ("series", "thumbs"):
        if (A.web / sub).exists():
            shutil.copytree(A.web / sub, web / sub, dirs_exist_ok=True)
    data, _, _ = mobile.read_data((web / "index.html").read_text(encoding="utf-8"))
    for s in data["strokes"]:                                     # its clip, from where this web is
        s["video"] = Path(os.path.relpath(A.match / "windows" / "w0.mp4", web)).as_posix()
    (web / "index.html").write_text(mobile.page_html(web / "index.html", data), encoding="utf-8")
    return a


def test_copy_button_makes_it_in_the_background_and_says_where(env, monkeypatch):
    from playwright.sync_api import sync_playwright
    from test_app_window import _browser, _live
    import time
    a = _app_with_web(env)
    api = window.Api(a)
    page = window.write_page(a)
    with sync_playwright() as p:
        if not CHROMIUM.exists():
            pytest.skip("sin navegador")
        b = _browser(p)
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        _live(pg, api)
        pg.goto(page.as_uri())
        pg.wait_for_function("window.__tbReady === true")
        pg.evaluate("location.hash = '#analisis'")
        pg.wait_for_timeout(200)
        assert "Copiar al móvil" in pg.inner_text("#mbBody")
        pg.click("button[data-act=mobile][data-arg=rybakina_forehand]")
        for _ in range(300):
            if (a.db.setting("movil") or {}).get("rybakina_forehand"):
                break
            time.sleep(0.05)
        pg.wait_for_timeout(1500)
        txt = pg.inner_text("#mbBody")
        pg.evaluate("location.hash = '#ajustes'")
        pg.wait_for_timeout(200)
        aj = pg.inner_text(".screen.on")
        b.close()
    m = a.db.setting("movil")["rybakina_forehand"]
    assert m["with_video"] == 1 and Path(m["zip"]).exists() and Path(m["dest"]).name == "rybakina_forehand"
    assert Path(m["dest"]).parent == env.tmp / "movil"
    assert "Última copia" in txt and "Actualizar copia" in txt and "Abrir carpeta" in txt
    assert str(env.tmp / "movil") in aj
    n = a.db.one("SELECT level, text FROM notices WHERE key='movil_rybakina_forehand'")
    assert n["level"] == "ok" and "Copia para el móvil lista: 1 golpes con vídeo" in n["text"]


def test_copy_of_an_analysis_with_nothing_published_says_why(env):
    a = env.app()
    T._added(env, a)
    a.work()
    api = window.Api(a)
    api.mobile("rybakina_forehand")                               # the fake engine's web has no data
    api._mb.join(10)
    n = a.db.one("SELECT level, text FROM notices WHERE key='movil_rybakina_forehand'")
    assert n["level"] == "aviso" and n["text"].startswith("La copia para el móvil no se hizo.")
    with pytest.raises(ValueError):
        api.mobile("nadie_forehand")


# ---------------------------------------------------------------- desktop shortcut -------------------

def test_shortcut_icon_and_script(tmp_path):
    ico = shortcut.write_icon(tmp_path / "tennisbio.ico")
    from PIL import Image
    with Image.open(ico) as im:
        assert im.format == "ICO" and (256, 256) in im.info.get("sizes", {(256, 256)})
    s = shortcut.script(None, ico, Path("C:/tenis/tennis-biomech"))
    assert "GetFolderPath('Desktop')" in s and "Tennisbio.lnk" in s and "wscript.exe" in s
    assert "Tennisbio.vbs" in s and "IconLocation" in s and s.rstrip().endswith("Write-Output $l")
    q = shortcut.script("C:/Users/O'Neil/Escritorio/Tennisbio.lnk", ico)           # quotes in the path
    assert "O''Neil" in q


def test_shortcut_outside_windows_says_so(tmp_path):
    if sys.platform == "win32":
        pytest.skip("en Windows lo hace de verdad")
    r = shortcut.create(tmp_path)
    assert r == {"link": None, "made": False, "error": "no es Windows"}


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador")
def test_the_pc_check_of_the_phone_copy(env, monkeypatch, tmp_path):
    """app/check.py check_mobile, as the PC runs it (request «movil»): the copy made, opened at phone size, and
    the stroke drawn from the copy matching the PC's web."""
    from tennisbio.app import check as C
    a = _app_with_web(env, codec=VP9, bg="testsrc2=r=50")         # a picture with detail everywhere, like the court
    monkeypatch.setattr(mobile, "encode", _vp9_720)
    r = C.check_mobile(a, tmp_path / "capturas_app")
    assert not r["problems"], r["problems"]
    row = r["copias"][0]
    assert row["with_video"] == 1 and row["imagen"]["alto_movil"] == 720 and row["imagen"]["alto_pc"] == 1080
    assert row["imagen"]["diferencia_media"] < 18 and row["imagen"]["brillo"] > 5
    assert (tmp_path / "capturas_app" / "movil_rybakina_forehand.png").exists()
    assert "Copia al móvil y acceso directo: OK" in (tmp_path / "capturas_app" / "movil.md").read_text(encoding="utf-8")
    # the same check finds a copy whose picture is not scaled (the skeleton would miss her)
    make = mobile.make

    def unscaled(*k, **kw):
        res = make(*k, **kw)
        page = Path(res["dest"]) / "index.html"
        data, _, _ = mobile.read_data(page.read_text(encoding="utf-8"))
        for s in data["strokes"]:
            s.pop("vk", None)
        page.write_text(mobile.page_html(page, data), encoding="utf-8")
        return res
    monkeypatch.setattr(mobile, "make", unscaled)
    r = C.check_mobile(a, tmp_path / "capturas_app2")
    assert any("no coincide con el del PC" in p for p in r["problems"]), r


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador")
def test_the_pc_check_uses_the_cycles_report_while_the_app_has_none(env, monkeypatch, tmp_path):
    """On the PC (18-10) the index had 0 analyses of its own: the real report is the automatic cycle's test run.
    Its copy goes aside (output/movil_prueba), never into movil\\."""
    from tennisbio.app import check as C
    a = env.app()
    src = env.tmp / "output" / "_smoke"
    out = src
    d = out / "m1"
    (d / "series").mkdir(parents=True)
    (d / "windows").mkdir()
    s, ser = stroke_and_series()
    (d / "series" / "x0.json").write_text(json.dumps(ser), encoding="utf-8")
    _window(d / "windows" / "w0.mp4", codec=VP9, bg="testsrc2=r=50")
    (d / "strokes.json").write_text(json.dumps([{**s, "series": "series/x0.json", "window": "w0.mp4", "window_impact_s": 1.2}]),
                                    encoding="utf-8")
    build([Match("m1", None, Player("p", "P", height_m=1.84))], out, out / "informe")
    monkeypatch.setattr(mobile, "encode", _vp9_720)
    r = C.check_mobile(a, tmp_path / "capturas_app")
    assert not r["problems"], r["problems"]
    assert r["copias"][0]["id"] == "prueba_smoke" and r["copias"][0]["imagen"]["diferencia_media"] < 18
    assert (env.tmp / "output" / "movil_prueba" / "smoke" / "index.html").exists() and not (env.tmp / "movil").exists()
    a.close()
    b = env.app()                                              # the index rebuilt from the folders: no match from it
    assert not b.db.q("SELECT id FROM matches WHERE id LIKE '%movil%'")


# ---------------------------------------------------------------- straight to the phone (MTP) -------

from tennisbio.app import phone  # noqa: E402

PIXEL = {"name": "Pixel 8", "path": "::{20D04FE0}\\\\?\\usb#vid_18d1&pid_4ee1#3A1B#{6ac27878}", "storages": ["Almacenamiento interno compartido"]}


def test_phones_by_cable_are_listed_and_a_locked_one_says_so(tmp_path):
    one = json.dumps({"name": "Pixel 8", "path": PIXEL["path"], "storages": []})        # PowerShell: a single object
    assert phone.devices(run=lambda s, t: one) == [{"name": "Pixel 8", "path": PIXEL["path"], "storages": []}]
    assert phone.devices(run=lambda s, t: "") == [] and phone.devices(run=lambda s, t: "no json") == []
    (tmp_path / "rybakina_forehand").mkdir()
    (tmp_path / "rybakina_forehand" / "index.html").write_text("x")
    r = phone.send(tmp_path / "rybakina_forehand", {**PIXEL, "storages": []}, run=lambda s, t: 1 / 0)
    assert not r["ok"] and "desbloquéalo" in r["why"]


def test_send_goes_to_a_new_folder_and_the_bookmark_follows_it(tmp_path):
    A = _analysis(tmp_path, n=1)
    res = mobile.make(A.paths, "p", "forehand", zip_it=False)
    dest = Path(res["dest"])
    seen = {}

    def run(script, timeout):
        seen["s"] = script
        return json.dumps({"ok": True, "files": 9, "old": 1})
    r = phone.send(dest, PIXEL, run=run, stamp="20261018-1300")
    s = seen["s"]
    n = sum(1 for f in dest.rglob("*") if f.is_file())
    assert r == {"ok": True, "files": 9, "expected": n, "device": "Pixel 8", "folder": "p_forehand_20261018-1300", "old": 1,
                 "url": "file:///sdcard/Download/p_forehand.html"}
    assert "NewFolder('p_forehand_20261018-1300')" in s and f"Wait $nf.GetFolder {n} " in s
    assert "-like 'p_forehand_2*'" in s and "MoveHere" in s and str(dest) in s and PIXEL["path"] in s
    page = (dest.parent / "p_forehand.html").read_text(encoding="utf-8")
    assert 'location.replace("p_forehand_20261018-1300/index.html")' in page
    # a copy that did not finish: said, never claimed
    r = phone.send(dest, PIXEL, run=lambda s, t: json.dumps({"ok": False, "why": "tiempo", "files": 3}))
    assert not r["ok"] and r["files"] == 3 and r["why"] == "la copia no terminó a tiempo" and "url" not in r


def test_copy_button_passes_it_to_the_connected_phone(env, monkeypatch):
    a = _app_with_web(env)
    monkeypatch.setattr(phone, "devices", lambda: [PIXEL])
    monkeypatch.setattr(phone, "send", lambda folder, dev: {"ok": True, "device": dev["name"], "files": 5, "expected": 5,
                                                           "url": f"file:///sdcard/Download/{folder.name}.html"})
    api = window.Api(a)
    api.mobile("rybakina_forehand")
    api._mb.join(60)
    n = a.db.one("SELECT level, text FROM notices WHERE key='movil_rybakina_forehand'")
    assert n["level"] == "ok" and "Ya está en tu Pixel 8: ábrela en Chrome con file:///sdcard/Download/rybakina_forehand.html" in n["text"]
    assert a.db.setting("movil")["rybakina_forehand"]["phone"]["ok"]
    monkeypatch.setattr(phone, "send", lambda folder, dev: {"ok": False, "device": dev["name"], "why": phone.WHY["bloqueado"]})
    api.mobile("rybakina_forehand")
    api._mb.join(60)
    n = a.db.one("SELECT level, text FROM notices WHERE key='movil_rybakina_forehand'")
    assert n["level"] == "aviso" and "No se pudo pasar al Pixel 8" in n["text"] and ".zip" in n["text"]
