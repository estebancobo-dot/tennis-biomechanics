"""T25 (21-11): RF-DETR for the far player, measured again on the cloud's GPU with the PC's own measure; its rule is
written before measuring."""
import json
import sys
from pathlib import Path

from tennisbio.infra import poc_lejana as pl

ROOT = Path(__file__).resolve().parents[1]


def test_the_rule_and_the_result_file(tmp_path, monkeypatch):
    res = {"per_model": {"ours (YOLO11m-pose, mitad lejana)": {"far_found": 0.903, "fps": 9.0},
                         "rfdetr": {"far_found": 1.0, "fps": 6.0}}, "far_rackets": 310}
    assert pl.decide(res)["pasa"] is True
    res2 = {"per_model": {"ours (YOLO11m-pose, mitad lejana)": {"far_found": 0.97}, "rfdetr": {"far_found": 1.0}}}
    assert pl.decide(res2)["pasa"] is False                         # less than 5 points better: set aside
    assert pl.decide({})["pasa"] is False

    class B:
        @staticmethod
        def bench_far(root, device, n):
            assert device == "cuda" and n == 300
            return res
    monkeypatch.setattr(pl, "bench", lambda: B)
    out = tmp_path / "poc.json"
    assert pl.main(["--datos", str(tmp_path), "--salida", str(out)]) == 0
    got = json.loads(out.read_text(encoding="utf-8"))
    assert got["prueba"] == "lejana" and got["regla"]["pasa"] and got["far_rackets"] == 310


def test_the_pcs_bench_is_the_one_measured():
    b = pl.bench()
    assert callable(b.bench_far) and b.EXPORTS["rfdetr"][0].name == "rfdetr_medium_1152.onnx"


def test_kaggle_runs_it_and_keeps_the_exported_model():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    j = correr.parse_job('{"accion": "medir", "prueba": "lejana"}')
    args = correr.poc_args(j, Path("/d/models/models"), None)
    assert args == ["--datos", str(Path("/d/models/datasets")), "--dispositivo", "cuda"]
    assert correr.RFDETR_ONNX == pl.bench().EXPORTS["rfdetr"][0].name
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert 'modal_put(vol, [models / RFDETR_ONNX], models, "/" + models.relative_to(data).as_posix())' in src
    assert correr.wants_rfdetr({"config": {"fine_pass": {"far_detector": "rfdetr"}}})
    assert not correr.wants_rfdetr({"config": {"fine_pass": {"refine": "sapiens2"}}}) and not correr.wants_rfdetr({})
    assert "if wants_rfdetr(job):" in src


def test_the_far_player_is_found_by_the_configured_detector(monkeypatch, tmp_path, capsys):
    """21-11 (T25): fine_pass.far_detector: rfdetr finds the people on the whole frame with RF-DETR; the far one among
    them is chosen by the court as with YOLO. The default stays YOLO on the far half, and its window caches stay valid."""
    import numpy as np
    from tennisbio import stages
    from tennisbio.pose import yolo, yolo_onnx

    monkeypatch.setattr(yolo_onnx, "MODELS_DIR", tmp_path)
    assert yolo.far_detector({}) == "yolo"
    cfg = {"fine_pass": {"far_detector": "rfdetr"}}
    assert yolo.far_detector(cfg) == "yolo" and "rfdetr_medium_1152.onnx" in capsys.readouterr().out   # no model
    (tmp_path / yolo.RFDETR_ONNX).write_bytes(b"x")
    assert yolo.far_detector(cfg) == "rfdetr"
    try:
        yolo.far_detector({"fine_pass": {"far_detector": "otro"}})
        raise AssertionError("a wrong name must be said")
    except ValueError:
        pass
    assert stages._far_tag({}) == [] and stages._far_tag(cfg) == ["far-rfdetr"]
    assert stages.window_cache_key({}) != stages.window_cache_key(cfg)

    class Rf:
        def people(self, frames):
            return [np.array([[10, 20, 30, 80, 0.9]], np.float32)]
    seen = []
    monkeypatch.setattr(yolo, "_far_name", lambda: "rfdetr")
    monkeypatch.setattr(yolo, "_rfdetr", lambda device: Rf())
    monkeypatch.setattr(yolo, "detect_people", lambda frame, roi=None: seen.append(roi) or np.zeros((0, 4)))
    frame = np.zeros((100, 200, 3), np.uint8)
    assert yolo.far_people(frame, np.eye(3)).tolist() == [[10, 20, 30, 80]] and seen == []
    monkeypatch.setattr(yolo, "_far_name", lambda: "yolo")
    monkeypatch.setattr("tennisbio.court_metrics.far_roi", lambda H, shape: (0, 0, 200, 50))
    assert yolo.far_people(frame, np.eye(3)).shape == (0, 4) and seen == [(0, 0, 200, 50)]
