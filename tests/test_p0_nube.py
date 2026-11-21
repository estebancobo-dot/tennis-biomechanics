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
    assert not r["ok"] and "no se pudo bajar auditoria/auditoria.json" in r["motivo"]
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
    assert seen[-1] == out / "nube" / "informe_derecha" / "index.html"


def test_the_button_brings_them_and_without_the_cloud_says_why():
    api = p0_api.ApiVentana(None, "X", traer=lambda: {"ok": True, "bajados": 2, "recargar": True})
    assert api.traer_resultados()["recargar"] is True
    assert not p0_api.ApiVentana(None, "X").traer_resultados()["ok"]
    assert p0_api.SinNube("sin la clave").traer_resultados() == {"ok": False, "motivo": "sin la clave"}
    src = (ROOT / "src" / "tennisbio" / "app" / "p0_ventana.py").read_text(encoding="utf-8")
    assert "ApiVentana(p0_api.Gestion(store, work / \"subida\"), datos[\"player\"][\"name\"], choose, traer)" in src


def test_the_cloud_writes_the_list_the_application_reads():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    assert p0_nube.MANIFEST == "/output/" + correr.APP_MANIFEST
    assert "modal" not in (ROOT / "src" / "tennisbio" / "app" / "p0_nube.py").read_text(encoding="utf-8").split('"""', 2)[2]
