import json

from tennisbio import match_files as mf
from tennisbio import pipeline


def test_flat_folder_keeps_every_file_side_by_side(tmp_path):
    d = tmp_path / "zheng"
    d.mkdir()
    (d / "partido.json").write_text("{}")              # the application's own test info is not the library's
    assert mf.at(d, "scenes.json") == d / "scenes.json"
    assert mf.at(d, "strokes.json") == d / "strokes.json"
    assert mf.at(d, "windows") == d / "windows"


def test_library_folder_splits_cheap_pass_and_strokes(tmp_path):
    d = tmp_path / "partidos" / "2026" / "2026-09-12_us-open_final_rybakina-sabalenka"
    (d / "etapas").mkdir(parents=True)
    (d / "partido.json").write_text(json.dumps({"jugadora": "rybakina-elena"}))
    for name in ("probe.json", "players.npz", "manifest.json", "identity.json", "identidad_clic.json", "identidad_fotos"):
        assert mf.at(d, name) == d / "etapas" / name
    for name in ("strokes.json", "strokes_opponent.json", "windows", "series/w1.json"):
        assert mf.at(d, name) == d / "golpes" / "rybakina-elena" / name


def test_player_folder_without_partido_json(tmp_path):
    d = tmp_path / "m"
    (d / "etapas").mkdir(parents=True)
    (d / "golpes" / "rybakina-elena").mkdir(parents=True)
    assert mf.at(d, "strokes.json") == d / "golpes" / "rybakina-elena" / "strokes.json"


def test_manifest_and_context_follow_the_layout(tmp_path):
    d = tmp_path / "m"
    (d / "etapas").mkdir(parents=True)
    (d / "partido.json").write_text(json.dumps({"jugadora": "rybakina-elena"}))
    pipeline.save_manifest(d, {"probe": {"fingerprint": "x"}})
    assert (d / "etapas" / "manifest.json").exists() and not (d / "manifest.json").exists()
    assert pipeline.load_manifest(d) == {"probe": {"fingerprint": "x"}}
    ctx = pipeline.Context(None, {"paths": {"output": str(tmp_path / "out")}}, d)
    assert ctx.path("court.json") == d / "etapas" / "court.json"
    assert ctx.path("strokes.json") == d / "golpes" / "rybakina-elena" / "strokes.json"
    assert ctx.progress_file() == tmp_path / "out" / "progreso.json"
