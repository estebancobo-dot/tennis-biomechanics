import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "tiempos_etapas", Path(__file__).resolve().parents[1] / "scripts" / "tiempos_etapas.py")
te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(te)


def _man(d: Path, fine_s: float, overlap: float = 0.0):
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({
        "probe": {"seconds": 6, "summary": {"duration_min": 35}},
        "scenes": {"seconds": 300}, "fine": {"seconds": fine_s, "overlap_s": overlap}}), encoding="utf-8")


def test_finds_library_matches_and_the_app_test_and_reads_their_stage_times(tmp_path):
    _man(tmp_path / "out" / "_app_nuevo" / "biblioteca" / "partidos" / "2026" / "prueba" / "etapas", 2400)
    _man(tmp_path / "out" / "plano", 600)
    _man(tmp_path / "out" / "plano" / "golpes" / "x", 1)           # never inside a player's folder
    found = te.manifests(tmp_path / "out")
    assert len(found) == 2
    t = te.table(found[0] if "prueba" in str(found[0]) else found[1])
    assert Path(t["carpeta"]).name == "prueba"                      # the match, not «etapas»
    assert t["etapas"][0]["etapa"] == "fine" and t["etapas"][0]["s_por_min_video"] == round(2400 / 35, 2)
    assert t["total_min"] == round((2400 + 300 + 6) / 60, 1) and t["veces_el_video"] == round(2706 / 60 / 35, 2)


def test_overlapping_stages_are_counted_once_and_a_manifest_without_times_is_skipped(tmp_path):
    _man(tmp_path / "a", 1200, overlap=300)
    assert te.table(tmp_path / "a" / "manifest.json")["total_min"] == round((1200 - 300 + 300 + 6) / 60, 1)
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "manifest.json").write_text("{}", encoding="utf-8")
    assert te.table(tmp_path / "b" / "manifest.json") is None


def test_the_parts_inside_a_fine_pass_are_kept(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({
        "probe": {"seconds": 6, "summary": {"duration_min": 35}},
        "fine": {"seconds": 2000, "summary": {"seconds": {"pose": 1500.0, "recorte": 100.0}, "counts": {"frames": 9},
                                              "windows": 40}}}), encoding="utf-8")
    r = te.table(d / "manifest.json")["etapas"][0]
    assert r["partes_s"] == {"pose": 1500.0, "recorte": 100.0} and r["cuentas"] == {"frames": 9}
    assert r["resumen"] == {"windows": 40}


def test_the_ab_bench_sets_any_key_of_b():
    spec = importlib.util.spec_from_file_location(
        "bench_fine_fps", Path(__file__).resolve().parents[1] / "scripts" / "bench_fine_fps.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    cfg = {"fine_pass": {"refine": "rtmpose-x"}}
    b.set_key(cfg, "fine_pass.refine=rtmw-x")
    b.set_key(cfg, "fine_pass.max_fps=30")
    b.set_key(cfg, "trunk3d.enabled=false")
    assert cfg == {"fine_pass": {"refine": "rtmw-x", "max_fps": 30}, "trunk3d": {"enabled": False}}


def test_the_f3set_recount_sets_a_key_for_its_ab():
    spec = importlib.util.spec_from_file_location(
        "validate_recall", Path(__file__).resolve().parents[1] / "scripts" / "validate_recall.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    base = {"fine_pass": {"refine": "rtmpose-x"}}
    out = v.with_settings(base, ["fine_pass.ball_from_spotting=true"])
    assert out["fine_pass"] == {"refine": "rtmpose-x", "ball_from_spotting": True} and "ball_from_spotting" not in base["fine_pass"]
