"""P0.5e (21-11, #301): the cloud's results brought to the PC's application: only what changed, never half a file, never
a path outside its folder; the window shows them before the PC's own report, and says where its data come from."""
import json
import sys
from pathlib import Path

from tennisbio.app import p0_api, p0_nube, p0_ventana
from tennisbio.infra.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]


def _cloud(tmp_path: Path, files: dict[str, bytes]) -> LocalStorage:
    vol = tmp_path / "vol"
    for rel, data in files.items():
        (vol / "output" / rel).parent.mkdir(parents=True, exist_ok=True)
        (vol / "output" / rel).write_bytes(data)
    man = {"generado": "2026-11-21 08:00 UTC", "partidos": ["m1"], "ficheros": {k: len(v) for k, v in files.items()}}
    (vol / "output" / "resultados_app.json").write_text(json.dumps(man), encoding="utf-8")
    return LocalStorage(vol)


def test_only_what_changed_is_brought(tmp_path):
    files = {"informe_derecha/index.html": b"<html>1</html>", "informe_derecha/videos/g1.mp4": b"v" * 10,
             "auditoria/auditoria.json": b"{}"}
    store, dest = _cloud(tmp_path, files), tmp_path / "pc" / "nube"
    r = p0_nube.pull(store, dest, log=lambda m: None)
    assert r["ok"] and r["bajados"] == 3 and r["partidos"] == ["m1"] and r["generado"].startswith("2026-11-21")
    assert (dest / "informe_derecha" / "videos" / "g1.mp4").read_bytes() == b"v" * 10
    assert p0_nube.pull(store, dest, log=lambda m: None)["bajados"] == 0             # nothing new
    store2 = _cloud(tmp_path, {**files, "informe_derecha/index.html": b"<html>22</html>"})
    assert p0_nube.pull(store2, dest, log=lambda m: None)["bajados"] == 1
    assert (dest / "informe_derecha" / "index.html").read_bytes() == b"<html>22</html>"
    assert not list(dest.rglob("*.part"))
    page, audit, man = p0_nube.local_results(dest)
    assert page.parent.name == "informe_derecha" and audit.name == "auditoria.json" and man["partidos"] == ["m1"]


def test_nothing_is_brought_without_the_list_or_with_bad_paths(tmp_path):
    dest = tmp_path / "pc" / "nube"
    r = p0_nube.pull(LocalStorage(tmp_path / "vacio"), dest, log=lambda m: None)
    assert not r["ok"] and "aún no tiene resultados" in r["motivo"] and not dest.exists()
    for bad in ("../fuera.txt", "/etc/x", "a\\..\\b", "C:/x"):
        store = _cloud(tmp_path / bad.replace("/", "_").replace("\\", "_").replace(":", ""), {"a.txt": b"x"})
        man = json.loads(store.read_bytes("/output/resultados_app.json"))
        man["ficheros"][bad] = 1
        (store.root / "output" / "resultados_app.json").write_text(json.dumps(man), encoding="utf-8")
        r = p0_nube.pull(store, dest, log=lambda m: None)
        assert not r["ok"] and "rutas no válidas" in r["motivo"]
    assert not (tmp_path / "pc" / "fuera.txt").exists()
    store = _cloud(tmp_path / "falta", {"informe_derecha/index.html": b"x", "auditoria/auditoria.json": b"{}"})
    (store.root / "output" / "auditoria" / "auditoria.json").unlink()
    r = p0_nube.pull(store, tmp_path / "pc2", log=lambda m: None)
    assert not r["ok"] and "no se pudo bajar auditoria/auditoria.json" in r["motivo"] and r["bajados"] == 1
    assert p0_nube.local_results(tmp_path / "pc2") is None                     # no list written: not shown as done


def test_the_window_shows_the_clouds_results_first_and_says_so(tmp_path, monkeypatch):
    from tennisbio.app import p0_app
    seen = []
    monkeypatch.setattr(p0_app, "datos_beta", lambda report, audit, est, m: seen.append(report) or {"player": {}})
    out = tmp_path / "salida"
    (out / "informe").mkdir(parents=True)
    (out / "informe" / "index.html").write_text("<html>pc</html>")
    (out / "auditoria").mkdir()
    (out / "auditoria" / "auditoria.json").write_text("{}")
    d, src = p0_ventana.build_data(out, None, tmp_path / "trabajo", out / "nube")
    assert src.startswith("el informe del PC") and d["origen"] == src and seen[-1] == out / "informe" / "index.html"
    store = _cloud(tmp_path, {"informe_derecha/index.html": b"<html>nube</html>", "auditoria/auditoria.json": b"{}"})
    assert p0_nube.pull(store, out / "nube", log=lambda m: None)["ok"]
    d, src = p0_ventana.build_data(out, None, tmp_path / "trabajo", out / "nube")
    assert src == "el informe de la nube (hecho el 2026-11-21 08:00 UTC)" and d["origen"] == src
    assert d["medios"] == "../nube/informe_derecha/"            # its videos and series, from the application's page
    assert seen[-1] == out / "nube" / "informe_derecha" / "index.html"


def test_the_button_brings_them_and_without_the_cloud_says_why():
    api = p0_api.ApiVentana(None, "X", traer=lambda: {"ok": True, "bajados": 2, "recargar": True})
    assert api.traer_resultados()["recargar"] is True
    assert not p0_api.ApiVentana(None, "X").traer_resultados()["ok"]
    assert p0_api.SinNube("sin la clave").traer_resultados() == {"ok": False, "motivo": "sin la clave"}
    src = (ROOT / "src" / "tennisbio" / "app" / "p0_ventana.py").read_text(encoding="utf-8")
    assert "ApiVentana(p0_api.Gestion(store, work / \"subida\"), datos[\"player\"][\"name\"], choose, traer, abrir)" in src


def test_the_cloud_writes_the_list_the_application_reads():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    assert p0_nube.MANIFEST == "/output/" + correr.APP_MANIFEST
    assert "modal" not in (ROOT / "src" / "tennisbio" / "app" / "p0_nube.py").read_text(encoding="utf-8").split('"""', 2)[2]


def test_the_window_opens_at_once_and_brings_the_results_behind_it(tmp_path, monkeypatch):
    """21-11: a first download of the results (videos included) can take minutes: the window opens with what the PC
    has, the results come in pywebview's thread once it is up, and the page is loaded again when they are in."""
    import types
    from tennisbio.app import p0_app
    monkeypatch.setattr(p0_app, "datos_beta", lambda report, audit, est, m: {"player": {"name": "X"}, "strokes": []})
    events = []

    class W:
        def evaluate_js(self, js):
            events.append(("recarga", "index.html" if "reload" in js else js))

    fake = types.SimpleNamespace(OPEN_DIALOG=0,
                                 create_window=lambda *a, **k: events.append(("ventana", Path(k["url"]).name)) or W(),
                                 start=lambda func=None: events.append(("arranca", func is not None)) or (func and func()))
    monkeypatch.setitem(sys.modules, "webview", fake)
    store = _cloud(tmp_path, {"informe_derecha/index.html": b"<html>nube</html>", "auditoria/auditoria.json": b"{}"})
    out = tmp_path / "salida"
    real_pull = p0_nube.pull
    monkeypatch.setattr(p0_nube, "pull", lambda *a, **k: events.append(("trae",)) or real_pull(*a, **k))
    assert p0_ventana.main(store, out_root=out) == 0
    assert events == [("ventana", "index.html"), ("arranca", True), ("trae",), ("recarga", "index.html")], events
    assert (out / "nube" / "informe_derecha" / "index.html").exists()


def test_many_files_are_brought_at_once(tmp_path):
    """21-11 (the user: «va super lenta»): 1759 files one after another, ~0.7 s each, took 22 min: several at once."""
    import threading
    import time as _t
    files = {f"informe_derecha/series/s{i}.js": b"x" * i for i in range(1, 41)}
    store = _cloud(tmp_path, files)
    seen, lock = [0, 0], threading.Lock()
    real = store.read_bytes

    def slow(path):
        with lock:
            seen[0] += 1
            seen[1] = max(seen[1], seen[0])
        _t.sleep(0.05)
        with lock:
            seen[0] -= 1
        return real(path)
    store.read_bytes = slow
    t0 = _t.time()
    r = p0_nube.pull(store, tmp_path / "pc", log=lambda m: None)
    assert r["ok"] and r["bajados"] == 40 and seen[1] > 1 and _t.time() - t0 < 40 * 0.05
    assert (tmp_path / "pc" / "informe_derecha" / "series" / "s40.js").read_bytes() == b"x" * 40


def test_the_export_comes_with_the_results_and_opens_with_the_pcs_program(tmp_path, monkeypatch):
    """21-11 (P0.5e): the cloud's export (the short PDF, the montages) is listed in the window and each file opens with
    the PC's own program; nothing outside the results' folder; the disk's room and what the results take, said."""
    from tennisbio.app import p0_app
    monkeypatch.setattr(p0_app, "datos_beta", lambda report, audit, est, m: {"player": {"name": "X"}, "strokes": []})
    out = tmp_path / "salida"
    store = _cloud(tmp_path, {"informe_derecha/index.html": b"<html>nube</html>", "auditoria/auditoria.json": b"{}",
                              "exportar_derecha/resumen.pdf": b"%PDF" * 10, "exportar_derecha/montajes/01_a.mp4": b"m",
                              "exportar_derecha/golpes/g1.mp4": b"g",
                              "exportar_derecha/exportacion.json": json.dumps({"titles": {"01_a.mp4": "Bola rápida"}}).encode()})
    assert p0_nube.pull(store, out / "nube", log=lambda m: None)["ok"]
    d, _ = p0_ventana.build_data(out, None, tmp_path / "trabajo", out / "nube")
    assert [(e["tipo"], e["ruta"]) for e in d["exportados"]] == [
        ("golpe", "exportar_derecha/golpes/g1.mp4"), ("montaje", "exportar_derecha/montajes/01_a.mp4"),
        ("pdf", "exportar_derecha/resumen.pdf")]
    assert d["exportados"][1]["titulo"] == "Bola rápida"                     # the montage's own title, with its accent
    assert d["disco"]["resultados_gb"] >= 0 and d["disco"]["libre_gb"] > 0 and d["disco"]["poco"] in (True, False)
    seen = []
    assert p0_nube.open_result(out / "nube", "exportar_derecha/resumen.pdf", seen.append) == {"ok": True}
    assert p0_nube.open_result(out / "nube", "exportar_derecha/montajes", seen.append)["ok"]       # its folder
    assert seen == [str((out / "nube" / "exportar_derecha" / "resumen.pdf").resolve()),
                    str((out / "nube" / "exportar_derecha" / "montajes").resolve())]
    for bad in ("../fuera.pdf", "/etc/passwd", "C:/x.pdf", "a\\..\\b"):
        assert not p0_nube.open_result(out / "nube", bad, seen.append)["ok"]
    assert "no está en el PC" in p0_nube.open_result(out / "nube", "exportar_derecha/otro.pdf", seen.append)["motivo"]
    assert len(seen) == 2
    api = p0_api.ApiVentana(None, "X", abrir=lambda r: {"ok": True, "r": r})
    assert api.abrir("exportar_derecha/resumen.pdf")["r"] == "exportar_derecha/resumen.pdf"
    assert not p0_api.ApiVentana(None, "X").abrir("x")["ok"] and not p0_api.SinNube("sin clave").abrir("x")["ok"]
