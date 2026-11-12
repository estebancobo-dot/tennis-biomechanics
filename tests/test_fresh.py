"""#263 (12-11): the matches from scratch. What an analysis computed goes to a dated archive (never deleted); the folder
keeps only what is not computed: the match's record, the user's click and the video when it lives there."""
import json

import yaml

from tennisbio import fresh


def _library_match(root):
    d = root / "partidos" / "sin-fecha" / "sin-fecha_f43dd2_rybakina"
    (d / "etapas" / "identidad_fotos").mkdir(parents=True)
    for f in ("score.json", "identity.json", "ball_track.npz", "identidad_clic.json", "source.mkv", "source.json",
              "manifest.json"):
        (d / "etapas" / f).write_text("x" * 10)
    (d / "partido.json").write_text(json.dumps({"jugadora": "elena-rybakina"}))
    w = d / "golpes" / "elena-rybakina" / "windows"
    w.mkdir(parents=True)
    (w / "w1.mp4").write_text("v" * 100)
    (w / "w1_345efe3f.npz").write_text("p" * 50)
    (d / "golpes" / "elena-rybakina" / "strokes.json").write_text("[]")
    return d


def test_only_the_users_click_the_record_and_the_video_stay(tmp_path):
    d = _library_match(tmp_path)
    p = fresh.plan(d)
    assert sorted(p["keep"]) == ["etapas/identidad_clic.json", "etapas/source.json", "etapas/source.mkv", "partido.json"]
    assert {"etapas/score.json", "etapas/ball_track.npz", "etapas/identidad_fotos", "golpes"} <= set(p["move"])
    assert p["bytes"] >= 150


def test_executed_it_moves_everything_else_to_the_dated_archive(tmp_path):
    d = _library_match(tmp_path)
    cfg = {"paths": {"output": str(tmp_path / "output"), "library": str(tmp_path)}}
    rep = fresh.run(cfg, tmp_path / "output", [d], execute=True, stamp="20261112_1500")
    arch = tmp_path / "archivo" / "desde_cero_20261112_1500" / "partidos" / "sin-fecha" / "sin-fecha_f43dd2_rybakina"
    assert rep["partidos"][0]["archivo"] == str(arch) and rep["partidos"][0]["movidos"] == rep["partidos"][0]["mueve"]
    assert sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()) == [
        "etapas/identidad_clic.json", "etapas/source.json", "etapas/source.mkv", "partido.json"]
    assert (arch / "golpes" / "elena-rybakina" / "windows" / "w1_345efe3f.npz").exists()     # nothing deleted
    assert (arch / "etapas" / "score.json").exists() and (arch / "etapas" / "ball_track.npz").exists()
    assert json.loads((tmp_path / "output" / "capturas_diag" / "desde_cero.json").read_text())["ejecutado"] is True


def test_without_executing_nothing_moves_and_a_missing_click_is_said(tmp_path):
    d = _library_match(tmp_path)
    (d / "etapas" / "identidad_clic.json").unlink()
    rep = fresh.run({"paths": {}}, tmp_path / "output", [d], execute=False, stamp="s")
    assert (d / "etapas" / "score.json").exists() and "movidos" not in rep["partidos"][0]
    assert "sin clic" in rep["partidos"][0]["aviso"]


def test_a_flat_folder_keeps_its_own_click_at_its_root(tmp_path):
    d = tmp_path / "output" / "osaka"
    d.mkdir(parents=True)
    for f in ("identidad_clic.json", "score.json", "strokes.json"):
        (d / f).write_text("{}")
    assert fresh.plan(d)["keep"] == ["identidad_clic.json"]


def test_the_flow_archives_before_running_and_then_runs_the_whole_completo_flow():
    flows = yaml.safe_load(open("config/flujos.yaml", encoding="utf-8"))
    steps = [s.get("tennisbio") or s.get("script") for s in flows["desde_cero"]["pasos"]]
    assert steps.index(["desde-cero", "--ejecutar"]) < steps.index(["run", "--all"])
    completo = [s.get("tennisbio") or s.get("script") for s in flows["completo"]["pasos"]]
    assert [s for s in steps if s != ["desde-cero", "--ejecutar"]] == completo
