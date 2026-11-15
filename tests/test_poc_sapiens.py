"""#307 (15-11): the Sapiens2 proof of concept compares it with the fine pass's pose on the same crops and with the same
cleaning; its 308 points are taken to the hybrid's by name, and its rule is the one written before measuring."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from tennisbio.infra import poc_sapiens as ps
from tennisbio.skeleton import COCO17, FOOT_NAMES

ROOT = Path(__file__).resolve().parents[1]
# names of Sapiens2's 308 points (goliath order) that the mapping uses, from its keypoints308.py (read 15-11)
SAPIENS = {0: "nose", 1: "left_eye", 2: "right_eye", 3: "left_ear", 4: "right_ear", 5: "left_shoulder",
           6: "right_shoulder", 7: "left_elbow", 8: "right_elbow", 9: "left_hip", 10: "right_hip", 11: "left_knee",
           12: "right_knee", 13: "left_ankle", 14: "right_ankle", 15: "left_big_toe", 16: "left_small_toe",
           17: "left_heel", 18: "right_big_toe", 19: "right_small_toe", 20: "right_heel", 41: "right_wrist",
           62: "left_wrist"}


def test_its_points_go_to_the_hybrids_by_name():
    assert [SAPIENS[i] for i in ps.TO_COCO17] == COCO17
    assert [SAPIENS[i] for i in ps.TO_FEET] == list(FOOT_NAMES)
    kp, sc = np.arange(616, dtype=float).reshape(308, 2), np.linspace(0, 1, 308)
    body, bc, feet, fc = ps.to_hybrid(kp, sc)
    assert body.shape == (17, 2) and feet.shape == (6, 2) and body[9, 0] == 124.0 and fc[0] == sc[15]


def test_jitter_seen_and_agreement():
    t = np.arange(20, dtype=float)
    smooth = np.zeros((20, 17, 2))
    smooth[:, :, 0] = 5 * t[:, None]                       # steady motion: no acceleration
    shaky = smooth.copy()
    shaky[::2, :, 1] += 2.0                                 # ±2 px every other frame
    assert ps.jitter(smooth, 100.0, ps.BODY) == 0.0
    assert ps.jitter(shaky, 100.0, ps.BODY) == pytest.approx(0.04)
    conf = np.full((20, 17), 0.9)
    conf[:5, 5:17] = 0.1
    assert ps.seen(conf, ps.BODY) == pytest.approx(0.75)
    assert ps.agreement(smooth, shaky, 100.0, ps.BODY) == pytest.approx(0.01)
    assert ps.jitter(smooth[:2], 100.0, ps.BODY) is None


def test_a_series_is_read_as_the_fine_pass_wrote_it():
    ser = {"n": 3, "kp": [[float(i) for i in range(34)], None, [None] * 34], "conf": [[0.9] * 17, None, [0.2] * 17],
           "box": [[0, 0, 50, 100], None, [0, 10, 50, 130]],
           "feet": [[[1, 2], None, [3, 4], [5, 6], [7, 8], [9, 10]], None, None], "feet_conf": [[0.8] * 6, None, None]}
    s = ps.stroke_inputs(ser)
    assert s["body"].shape == (3, 17, 2) and s["body"][0, 1, 0] == 2.0 and np.isnan(s["body"][1:]).all()
    assert s["feet"][0, 2, 1] == 4.0 and np.isnan(s["feet"][0, 1]).all() and s["feet_conf"][0, 0] == 0.8
    assert s["boxes"][1] is None and s["height"] == 110.0


def test_the_kaggle_job_measures_on_the_reference_tests_outputs(monkeypatch):
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import cola
    import correr
    j = correr.parse_job('{"accion": "medir", "prueba": "sapiens2", "partido": "g", "base": "prueba_gauff_v26"}')
    args = correr.poc_args(j, Path("/d/models"), None)
    assert args[args.index("--previa") + 1] == "/d/previa" and args[args.index("--dispositivo") + 1] == "cuda"
    with pytest.raises(ValueError):
        correr.parse_job('{"accion": "medir", "prueba": "sapiens2"}')            # needs its match
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert '/kaggle_pruebas/{job.get(\'base\') or \'prueba_gauff_v26\'}/output/{TEST_PREFIX}{job[\'partido\']}' in src
    calls = []

    class R:
        returncode, stdout, stderr = 0, "", ""
    monkeypatch.setattr(cola, "_kaggle", lambda a: calls.append(a) or R())
    job = {"id": "medir_sapiens2", "accion": "medir", "prueba": "sapiens2", "partido": "g", "base": "prueba_gauff_v26",
           "donde": "kaggle"}
    assert not cola.check_queue([job]) and cola.kaggle_launch(job)
    assert calls[-1][calls[-1].index("--base") + 1] == "prueba_gauff_v26"
    nb = (ROOT / "cloud" / "kaggle" / "cuaderno.py").read_text(encoding="utf-8")
    assert 'job["base"] = a.base' in nb


def test_the_rule_is_written_before_measuring():
    doc = (ROOT / "docs" / "registro_decisiones.md").read_text(encoding="utf-8")
    assert "#307" in doc and ps.MARGIN_BODY == 0.9
    assert "10 %" in (ps.__doc__ or "")
    json.dumps({"ok": True})
