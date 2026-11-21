"""P0.5d: the application's management actions write what the queue reads, in the places the cloud already uses (the
video as /videos/<match><ext>, its record, the click as the PC writes it), and nothing is uploaded for a record that
the queue would refuse."""
import json
import sys
from pathlib import Path

from tennisbio.app import p0_api
from tennisbio.infra import peticiones as pt
from tennisbio.infra.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
import cola  # noqa: E402
import nube  # noqa: E402

FICHA = {"jugadora": "Elena Rybakina", "rival": "Jugadora Ejemplo", "torneo": "Torneo de Ejemplo", "ronda": "R1",
         "fecha": "2026-11-15", "superficie": "dura"}


def make(tmp_path, t0=1_794_800_000.0):
    clock = iter(range(1000))
    store = LocalStorage(tmp_path / "volumen")
    return store, p0_api.Gestion(store, tmp_path / "trabajo", now=lambda: t0 + next(clock))


def test_an_id_comes_from_the_record_and_is_valid():
    m = p0_api.match_id({**FICHA, "rival": "Ñoña Pérez"})
    assert m == "elena-rybakina-nona-perez-torneo-de-ejemplo-r1-2026-11-15" and pt.MATCH_ID.match(m)
    try:
        p0_api.match_id({})
        raise AssertionError("sin jugadoras no hay nombre")
    except ValueError:
        pass


def test_adding_a_match_uploads_the_video_its_record_and_the_request(tmp_path):
    store, g = make(tmp_path)
    video = tmp_path / "Mi Partido.TS"
    video.write_bytes(b"\x47" * 188 * 10)
    r = g.alta(video, FICHA, preparar=True)
    m = r["partido"]
    assert r["ok"] and store.read_bytes(f"/videos/{m}.ts") == video.read_bytes()
    rec = store.read_json(f"/biblioteca/partidos/{m}/partido.json")
    assert rec == {"jugadora": "Elena Rybakina", "opponent": "Jugadora Ejemplo", "tournament": "Torneo de Ejemplo",
                   "date": "2026-11-15", "surface": "dura", "round": "R1"}
    reqs = [(n, store.read_json(f"{pt.FOLDER}/{n}")) for n in store.list(pt.FOLDER)]
    assert [x[1]["tipo"] for x in reqs] == ["alta"] and reqs[0][1]["preparar"] is True
    # the cloud's catalogue reads that record as it reads the PC's (nube.cloud_catalog)
    entry = pt.interpret(reqs)["partidos"]
    cat = nube.cloud_catalog(entry, tmp_path / "volumen" / "biblioteca")["matches"][0]
    assert cat["video"] == f"{m}.ts" and cat["opponent"] == "Jugadora Ejemplo" and cat["tournament"] == "Torneo de Ejemplo"
    assert g.alta(video, FICHA, preparar=True)["ok"] is False                    # never the same match twice


def test_nothing_is_uploaded_for_a_record_the_queue_would_refuse(tmp_path):
    store, g = make(tmp_path)
    video = tmp_path / "partido.txt"
    video.write_bytes(b"x")
    assert g.alta(video, FICHA, preparar=True)["ok"] is False
    video = video.with_suffix(".mp4")
    video.write_bytes(b"x")
    r = g.alta(video, FICHA, preparar=False)                                      # without her yes to the preparation
    assert r["ok"] is False and "preparación" in r["motivo"]
    assert store.list("/videos") == [] and store.list(pt.FOLDER) == []
    assert g.alta(tmp_path / "no.mp4", FICHA, preparar=True)["ok"] is False


def test_the_click_is_the_file_the_pc_writes_and_the_queue_then_waits_for_her_approval(tmp_path):
    store, g = make(tmp_path)
    video = tmp_path / "p.mp4"
    video.write_bytes(b"x")
    m = g.alta(video, FICHA, preparar=True)["partido"]
    assert g.clic(m, 812.4567, near_is_her=False, by="clothes")["ok"]
    pick = store.read_json(f"/biblioteca/partidos/{m}/etapas/identidad_clic.json")
    assert pick["t"] == 812.457 and pick["near_is_her"] is False and pick["by"] == "clothes"
    reqs = [(n, store.read_json(f"{pt.FOLDER}/{n}")) for n in store.list(pt.FOLDER)]
    assert "aprobación" in pt.interpret(reqs)["esperas"][m]
    assert g.aprobar(m, {"horas_gpu": 2.1, "coste_eur": 0})["ok"]
    reqs = [(n, store.read_json(f"{pt.FOLDER}/{n}")) for n in store.list(pt.FOLDER)]
    jobs = pt.interpret(reqs)["trabajos"]
    assert jobs[-1]["id"] == f"app_{m}" and jobs[-1]["aprobado"] is True and cola.check_queue(jobs) == []
    assert jobs[-2]["id"] == f"app_fina_{m}"


def test_pause_cancel_and_the_queues_answer(tmp_path):
    store, g = make(tmp_path)
    assert g.pausar()["ok"] and g.cancelar("app_prueba_x")["ok"] and g.reanudar()["ok"]
    assert g.cancelar("")["ok"] is False
    reqs = [(n, store.read_json(f"{pt.FOLDER}/{n}")) for n in store.list(pt.FOLDER)]
    out = pt.interpret(reqs)
    assert out["pausa"]["en_pausa"] is False and "app_prueba_x" in out["cancelar"]
    (tmp_path / "volumen" / "cola").mkdir(parents=True)
    (tmp_path / "volumen" / "cola" / "app.json").write_text(json.dumps({"esperas": {"m": "falta el clic"}}), encoding="utf-8")
    (tmp_path / "volumen" / "cola" / "estado.json").write_text(json.dumps(
        {"app_prueba_m": {"estado": "en_marcha", "donde": "kaggle", "progreso": "fine: 40 %"}}), encoding="utf-8")
    st = g.estado()
    assert st["app"]["esperas"]["m"] == "falta el clic"
    assert st["trabajos"]["app_prueba_m"] == {"estado": "en_marcha", "donde": "kaggle", "nota": "fine: 40 %"}


def test_the_click_photos_come_from_the_cloud_when_they_are_made(tmp_path):
    store, g = make(tmp_path)
    assert g.fotos("m", tmp_path / "fotos") == []
    d = tmp_path / "volumen" / "output" / "m" / "identidad_fotos"
    d.mkdir(parents=True)
    (d / "0.jpg").write_bytes(b"jpg")
    (d / "1.jpg").write_bytes(b"jpg")
    assert [f.name for f in g.fotos("m", tmp_path / "fotos")] == ["0.jpg", "1.jpg"]


def test_the_windows_api_has_every_name_the_interface_calls(tmp_path):
    """The interface (ui/src/api.ts) and the window's object (ApiVentana) by the same names: a name missing on either
    side would be a button that does nothing."""
    import re as _re
    ts = (ROOT / "ui" / "src" / "api.ts").read_text(encoding="utf-8")
    block = ts[ts.index("export interface ApiPC"):ts.index("\n}", ts.index("export interface ApiPC"))]   # its own end
    names = set(_re.findall(r"^\s+(\w+)\(", block, _re.M))
    have = {n for n in dir(p0_api.ApiVentana) if not n.startswith("_")}
    assert names and names == have, (names ^ have)


def test_the_window_shows_the_photos_with_their_moments(tmp_path):
    store, g = make(tmp_path)
    api = p0_api.ApiVentana(g, "Elena Rybakina", choose=lambda: "C:/v/x.mp4")
    assert api.elegir_video() == "C:/v/x.mp4" and api.fotos("m") == []
    d = tmp_path / "volumen" / "output" / "m" / "identidad_fotos"
    d.mkdir(parents=True)
    (d / "0.jpg").write_bytes(b"\xff\xd8jpg")
    (d / "1.jpg").write_bytes(b"\xff\xd8jpg")
    (d / "fotos.json").write_text(json.dumps({"by": "clothes", "photos": [
        {"cluster": 0, "t": 61.2, "path": "/kaggle/x/identidad_fotos/0.jpg", "group_by": "clothes"},
        {"cluster": 1, "t": 803.0, "path": "/kaggle/x/identidad_fotos/1.jpg", "group_by": "clothes"}]}), encoding="utf-8")
    ph = api.fotos("m")
    assert [p["t"] for p in ph] == [61.2, 803.0] and ph[0]["src"].startswith("data:image/jpeg;base64,")
    assert ph[0]["by"] == "clothes"


def test_a_record_is_proposed_from_the_files_name():
    p = p0_api.proponer("C:/v/tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026.ts", "Elena Rybakina")
    assert p["jugadora"] == "Elena Rybakina" and p.get("fecha") == "2026-09-10"


def test_the_match_names_her_record_by_its_name(tmp_path):
    """The record's id is looked up by her name in config/players (the cloud's catalogue loads it by id)."""
    d = tmp_path / "players"
    d.mkdir()
    (d / "ryba.yaml").write_text("name: Elena Rybakina\nhand: right\n", encoding="utf-8")
    assert p0_api.player_record("elena rybakina", d) == "ryba"
    assert p0_api.player_record("Otra Persona", d) == "persona"
    assert p0_api.player_record("Elena Rybakina") == "rybakina"          # the repository's own record


def test_people_added_in_the_application_become_records_in_the_cloud(tmp_path):
    """The queue writes app/personas.json; a cloud session turns each new id into config/players/<id>.yaml of its
    checkout, never over the repository's own record."""
    repo, data = tmp_path / "repo", tmp_path / "data"
    (repo / "config" / "players").mkdir(parents=True)
    (repo / "config" / "players" / "rybakina.yaml").write_text("name: Elena Rybakina\n", encoding="utf-8")
    (data / "app").mkdir(parents=True)
    (data / "app" / "personas.json").write_text(json.dumps([
        {"id": "nueva", "name": "Nueva Persona", "hand": "left", "backhand": "one_handed", "height_m": 1.7},
        {"id": "rybakina", "name": "Otra"}, {"id": "../mal", "name": "x"}]), encoding="utf-8")
    assert nube.write_app_players(repo, data) == ["nueva"]
    import yaml
    assert yaml.safe_load((repo / "config" / "players" / "nueva.yaml").read_text(encoding="utf-8"))["hand"] == "left"
    assert "Elena" in (repo / "config" / "players" / "rybakina.yaml").read_text(encoding="utf-8")
    assert nube.write_app_players(repo, tmp_path / "nada") == []


def test_without_the_cloud_every_action_says_why():
    """P0.5e: without the Modal key the window opens all the same and each button says what is missing."""
    api = p0_api.SinNube("falta la clave de Modal: doble clic en 5_conectar_nube.bat")
    assert api.elegir_video() is None and api.fotos("m") == [] and api.proponer("x.mp4") == {}
    for name in ("alta", "clic", "aprobar", "pausar", "reanudar", "cancelar", "borrar_video"):
        r = getattr(api, name)("a", "b", "c") if name in ("alta", "clic") else getattr(api, name)("a")
        assert r == {"ok": False, "motivo": "falta la clave de Modal: doble clic en 5_conectar_nube.bat"}, name
    names = {n for n in dir(p0_api.ApiVentana) if not n.startswith("_")}
    assert names <= {n for n in dir(api) if not n.startswith("_")}


def test_the_window_builds_its_data_from_the_pcs_report_or_says_it_is_the_example(tmp_path):
    from tennisbio.app import p0_ventana
    d, src = p0_ventana.build_data(tmp_path / "salida", None, tmp_path / "trabajo")
    assert d["ejemplo"] is True and src.startswith("ejemplo (no hay informe")
    sys.path.insert(0, str(ROOT / "scripts"))
    import aplicacion_nueva
    store, why = aplicacion_nueva.storage(tmp_path / "nada" / "salida")
    assert store is None and "5_conectar_nube.bat" in why
    ps1 = (ROOT / "scripts" / "windows" / "aplicacion_nueva.ps1").read_text(encoding="ascii")
    assert "scripts/aplicacion_nueva.py" in ps1 and "Subir-Registros" in ps1
    assert "aplicacion_nueva.ps1" in (ROOT / "6_aplicacion_nueva.bat").read_text(encoding="ascii")


def test_the_window_reads_the_clouds_matches_as_the_queue_does(tmp_path):
    from tennisbio.app import p0_ventana
    store = LocalStorage(tmp_path / "v")
    (tmp_path / "v" / "pc").mkdir(parents=True)
    (tmp_path / "v" / "pc" / "registro_partidos.json").write_text(json.dumps([{"id": "a", "rival": "R"}]), encoding="utf-8")
    (tmp_path / "v" / "app").mkdir()
    (tmp_path / "v" / "app" / "registro_partidos.json").write_text(json.dumps([{"id": "b", "rival": "S"}, {"id": "a"}]),
                                                                   encoding="utf-8")
    (tmp_path / "v" / "output" / "a").mkdir(parents=True)
    (tmp_path / "v" / "output" / "a" / "manifest.json").write_text(json.dumps({"fine": {}}), encoding="utf-8")
    assert p0_ventana.cloud_matches(store) == [{"id": "a", "rival": "R", "analizado": True},
                                               {"id": "b", "rival": "S", "analizado": False}]


def test_the_window_checks_itself_and_leaves_it_in_the_cloud(tmp_path, capsys):
    """21-11 (#310, the user: «ni siquiera sé si la app de Windows funciona bien»): the window tries a few strokes'
    videos and series by itself (ui/src/autocomprobacion.ts) and its numbers reach the volume, where Claude reads them
    with a «leer» job; without the cloud the window opens all the same."""
    store, g = make(tmp_path)
    api = p0_api.ApiVentana(g, "Elena Rybakina")
    r = {"origen": "el informe de la nube", "probados": 3, "videos_ok": 3, "series_ok": 2, "filas": []}
    assert api.autocomprobacion(r) == {"ok": True}
    kept = store.read_json("/app/autocomprobacion.json")
    assert kept["videos_ok"] == 3 and kept["series_ok"] == 2 and kept["cuando"]
    assert "3 de 3 vídeos se abren, 2 series" in capsys.readouterr().out

    class Broken:
        def _put_json(self, *a):
            raise OSError("sin conexión")
    assert p0_api.ApiVentana(Broken(), "X").autocomprobacion(r) == {"ok": True}
    assert "no se pudo dejar en la nube" in capsys.readouterr().out
    ts = (ROOT / "ui" / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "pywebviewready" in ts and "autocomprobar(d)" in ts
    check = (ROOT / "ui" / "src" / "autocomprobacion.ts").read_text(encoding="utf-8")
    assert "d.ejemplo" in check and "videoWidth" in check     # never on the example data; a video that really decodes
