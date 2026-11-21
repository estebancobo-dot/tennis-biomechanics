"""#307 (21-11): Sapiens2 as the fine pass's refiner (fine_pass.refine: sapiens2). Its crop and heatmap decoding are the
transformers processor's ported to numpy (checked against it on a real frame: the same input within 4e-4 and the same
points within 1e-4 px); here what can be checked without the model: the mapping to Halpe26 by name, the crop's shape,
the decoding of a known peak, and that nothing changes for the configurations already in use."""
import sys
from pathlib import Path

import numpy as np
import pytest

from tennisbio.pose import hybrid
from tennisbio.pose import sapiens2 as sp
from tennisbio.skeleton import HALPE26

ROOT = Path(__file__).resolve().parents[1]
SAPIENS = {0: "nose", 1: "left_eye", 2: "right_eye", 3: "left_ear", 4: "right_ear", 5: "left_shoulder",
           6: "right_shoulder", 7: "left_elbow", 8: "right_elbow", 9: "left_hip", 10: "right_hip", 11: "left_knee",
           12: "right_knee", 13: "left_ankle", 14: "right_ankle", 15: "left_big_toe", 16: "left_small_toe",
           17: "left_heel", 18: "right_big_toe", 19: "right_small_toe", 20: "right_heel", 41: "right_wrist",
           62: "left_wrist", 69: "neck"}


def test_its_points_are_halpe26_by_name():
    for h, k in enumerate(sp.TO_HALPE26):
        if k >= 0:
            assert SAPIENS[k] == HALPE26[h], (h, k)
    assert sp.TO_HALPE26[17] == -1 and sp.TO_HALPE26[19] == -1          # head's top, hip: not Sapiens2 points


def test_the_crop_is_the_box_padded_to_four_by_three():
    c, s = sp.crop_params([100, 50, 140, 210])                          # 40 x 160 px: tall, widened to 4:3
    assert c.tolist() == [120.0, 130.0] and s[1] == pytest.approx(200.0) and s[0] / s[1] == pytest.approx(0.75)
    img = np.full((300, 300, 3), 128, np.uint8)
    x, c2, s2 = sp.crop(img, [100, 50, 140, 210])
    assert x.shape == (1, 3, 512, 384) and x.dtype == np.float32
    mid = x[0, :, 256, 192]                                             # grey 128 normalised channel by channel
    assert np.allclose(mid, (128 - sp.MEAN) / sp.STD, atol=1e-3)


def test_a_known_peak_is_decoded_back_to_the_image():
    h, w = 128, 96
    yy, xx = np.mgrid[0:h, 0:w]
    hm = np.zeros((308, h, w), np.float32)
    px, py = 40.3, 70.6                                                 # a sub-pixel peak
    hm[5] = np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * 3.0 ** 2))
    c, s = np.array([500.0, 300.0]), np.array([150.0, 200.0])
    pts, sc = sp.decode(hm, c, s, [5, 6])
    exp = np.array([px, py]) / np.array([w - 1, h - 1]) * s + c - 0.5 * s
    assert np.linalg.norm(pts[0] - exp) < 0.15 and sc[0] == pytest.approx(hm[5].max())
    assert sc[1] == 0.0 and pts[1].tolist() != pts[0].tolist()         # an empty map: no point


def test_halpe26_has_the_hip_between_the_hips_and_no_head_top():
    idx = sorted({k for k in sp.TO_HALPE26 if k >= 0})
    pts = np.array([[float(k), float(k) * 2] for k in idx])
    sc = np.linspace(0.5, 1.0, len(idx))
    kp, s = sp.to_halpe26(pts, sc, idx)
    assert kp[11].tolist() == [9.0, 18.0] and kp[19].tolist() == [9.5, 19.0] and s[17] == 0.0
    assert kp[20].tolist() == [15.0, 30.0] and kp[25].tolist() == [20.0, 40.0]


def test_the_configurations_in_use_keep_their_caches_and_a_missing_model_falls_back(monkeypatch, tmp_path, capsys):
    base = {"fine_pass": {"pose_model": "hybrid"}}
    assert hybrid.pose_cache_tag(base) == ["hybrid"]
    assert hybrid.pose_cache_tag({"fine_pass": {"pose_model": "hybrid", "refine": "rtmpose-x", "refine_fp16": True}}) \
        == ["hybrid", "refine-fp16"]
    monkeypatch.setattr(sp, "ONNX", tmp_path / "no.onnx")
    cfg = {"fine_pass": {"pose_model": "hybrid", "refine": "sapiens2"}}
    assert hybrid.refiner(cfg) == "rtmpose-x" and "export_sapiens2.py" in capsys.readouterr().out
    (tmp_path / "s.onnx").write_bytes(b"x")
    monkeypatch.setattr(sp, "ONNX", tmp_path / "s.onnx")
    assert hybrid.refiner(cfg) == "sapiens2" and hybrid.pose_cache_tag(cfg) == ["hybrid", "sapiens2"]


def test_kaggle_exports_it_once_when_the_settings_ask_for_it():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert "ensure_sapiens2(py, data, models, vol, est)" in src and 'modal_put(vol, [dst], dst.parent, "/models")' in src
    assert correr.SAPIENS2_ONNX == sp.ONNX.name
    exp = (ROOT / "scripts" / "export_sapiens2.py").read_text(encoding="utf-8")
    assert 'SIZE = (512, 384)' in exp and "dynamo=True" in exp and 'attn_implementation="eager"' in exp
