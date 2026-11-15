"""T15 (15-11): the ball model's proof of concept (TOTNet against TrackNetV3), its scoring and its job."""
import json
import sys
from pathlib import Path

import numpy as np

from tennisbio.ball_totnet import H, W, peak, prep
from tennisbio.infra import poc_bola

ROOT = Path(__file__).resolve().parents[1]
NAN = float("nan")


def test_scoring_counts_hits_false_and_missed_balls():
    rows = [(1, True, 100.0, 50.0), (2, True, 200.0, 50.0), (3, True, 300.0, 50.0), (4, False, 0.0, 0.0),
            (5, False, 0.0, 0.0)]
    pred = {1: (104.0, 52.0, 0.9),       # hit (within 10 px)
            2: (260.0, 50.0, 0.9),       # found elsewhere: false and missed
            3: (NAN, NAN, 0.1),          # not found: missed
            4: (10.0, 10.0, 0.05),       # found where there is no ball: false
            5: (NAN, NAN, NAN)}
    s = poc_bola.score(pred, rows)
    assert (s["aciertos"], s["falsas"], s["falsas_sin_bola"], s["perdidas"]) == (1, 2, 1, 2)
    assert s["precision"] == 0.333 and s["recall"] == 0.333
    t = poc_bola.score(pred, rows, thr=0.1)                       # the 0.05 false one goes below the threshold
    assert (t["falsas"], t["falsas_sin_bola"]) == (1, 0)
    both = poc_bola.total([s, t])
    assert both["aciertos"] == 2 and both["falsas"] == 3 and both["perdidas"] == 4


def test_threshold_is_picked_on_validation_by_f1():
    rows = [[(1, True, 10.0, 10.0), (2, False, 0.0, 0.0)]]
    preds = [{1: (10.0, 10.0, 0.3), 2: (50.0, 50.0, 0.04)}]
    thr, s = poc_bola.pick_threshold(preds, rows, grid=(0.01, 0.05, 0.5))
    assert thr == 0.05 and s["f1"] == 1.0


def test_totnet_input_and_peak():
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[..., 2] = 255                                            # red in BGR
    x = prep(frame)
    assert x.shape == (3, H, W) and x.dtype == np.float32
    assert np.allclose(x[0], (1 - 0.485) / 0.229, atol=1e-5)      # RGB order: red first
    hm = np.zeros((H, W), np.float32)
    hm[144, 256] = 0.7
    px, py, p = peak(hm, (720, 1280))
    assert abs(px - 641.25) < 1e-6 and abs(py - 361.25) < 1e-6 and p == np.float32(0.7)
    hm[0, W - 1] = 0.9                    # 15-11: a top corner is TOTNet's «no ball» (missing balls clamped there)
    px, py, p = peak(hm, (720, 1280))
    assert np.isnan(px) and np.isnan(py) and abs(p - 0.9) < 1e-6


def test_the_ball_job_runs_on_a_cpu_session():
    sys.path.insert(0, str(ROOT / "cloud"))
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    import cola
    import correr
    j = {"id": "medir_bola", "accion": "medir", "prueba": "bola", "donde": "kaggle", "cpu": True}
    assert not cola.check_queue([j]) and cola.cpu_job(j) and cola.estimate_h(j) == 0.0
    args = correr.poc_args(correr.parse_job(json.dumps({"accion": "medir", "prueba": "bola", "cpu": True})),
                           Path("/d/models"), None)
    assert args[args.index("--totnet") + 1] == "/d/models/totnet_tennis.onnx" and args[-1] == "cpu"
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert '"export_totnet.py"' in src
    exp = (ROOT / "scripts" / "export_totnet.py").read_text(encoding="utf-8")
    assert "weights_only=False, pickle_module=safe" in exp and "class _SafeUnpickler" in exp and "SHA256 =" in exp
