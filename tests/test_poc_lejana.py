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
    assert args == ["--datos", "/d/models/datasets", "--dispositivo", "cuda"]
    assert correr.RFDETR_ONNX == pl.bench().EXPORTS["rfdetr"][0].name
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert 'modal_put(vol, [models / RFDETR_ONNX], models, "/" + models.relative_to(data).as_posix())' in src
