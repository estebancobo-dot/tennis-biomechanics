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
    assert "ensure_sapiens2(py, data, models, vol, est)" in src
    assert 'modal_put(vol, [dst], dst.parent, "/" + models.relative_to(data).as_posix())' in src   # beside the others
    assert correr.SAPIENS2_ONNX == sp.ONNX.name
    exp = (ROOT / "scripts" / "export_sapiens2.py").read_text(encoding="utf-8")
    assert 'SIZE = (512, 384)' in exp and "dynamo=True" in exp and 'attn_implementation="eager"' in exp


def _rms_graph(dim: int = 64):
    """A float32 ONNX graph with one RMS norm written as torch.export writes Sapiens2's (x² → mean → + eps → √ → 1/·,
    times x, times its weight), its constants shared as the export shares them."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    nodes = [helper.make_node("Pow", ["x", "two"], ["sq"], name="p"),
             helper.make_node("ReduceMean", ["sq", "axes"], ["ms"], name="m", keepdims=1),
             helper.make_node("Add", ["ms", "eps"], ["mse"], name="a"),
             helper.make_node("Sqrt", ["mse"], ["rt"], name="s"),
             helper.make_node("Reciprocal", ["rt"], ["inv"], name="r"),
             helper.make_node("Mul", ["x", "inv"], ["xn"], name="n"),
             helper.make_node("Mul", ["w", "xn"], ["y"], name="o")]
    init = [numpy_helper.from_array(np.array(2.0, np.float32), "two"),
            numpy_helper.from_array(np.array([-1], np.int64), "axes"),
            numpy_helper.from_array(np.array(1e-6, np.float32), "eps"),
            numpy_helper.from_array(np.linspace(0.5, 1.5, dim).astype(np.float32), "w")]
    g = helper.make_graph(nodes, "rms", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 8, dim])],
                          [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 8, dim])], init)
    return helper.make_model(g, opset_imports=[helper.make_opsetid("", 18)], ir_version=8)


def _run(model, x, outputs=None):
    import onnxruntime as ort
    s = ort.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])
    return s.run(outputs, {"x": x})


def test_the_norms_are_rescaled_with_the_same_arithmetic_and_fit_half_precision(tmp_path):
    """prueba_gauff_v33 (21-11): Sapiens2 in plain half precision on the GPU broke the fine pass (the body shook twice as
    much): its residual stream reaches ~600, squared past fp16's 65504 inside every RMS norm. Rescaling by a power of
    two changes no bit in float32 and keeps every value of the norm small."""
    import onnx
    from onnx import helper
    from tennisbio.pose.variants import to_fp16

    rng = np.random.default_rng(0)
    x = rng.normal(0, 30, (1, 8, 64)).astype(np.float32)
    x[0, :, 3] = 598.0                                                  # one massive channel, as the real network has
    m = _rms_graph()
    ref = _run(m, x)[0]
    assert [n.name for n in sp.rms_chains(m)[0]] == ["p", "m", "a", "s", "r"]
    assert sp.scale_rms(m) == 1 and len(m.graph.node) == 9
    onnx.checker.check_model(m)
    m.graph.output.extend([helper.make_empty_tensor_value_info(v) for v in ("sq", "rms0_raiz")])
    got, sq, root = _run(m, x, ["y", "sq", "rms0_raiz"])
    assert np.array_equal(got, ref)                                     # the same bits
    assert (x ** 2).max() > 65504 and sq.max() < 65504 / 32            # the square fits, with room
    onnx.save(_rms_graph(), str(tmp_path / "rms.onnx"))
    h = to_fp16(tmp_path / "rms.onnx", tmp_path / "rms_h.onnx", sp.scale_rms)
    half = _run(onnx.load(str(h)), x)[0]
    assert np.isfinite(half).all() and np.abs(half - ref).max() < 2e-2 * np.abs(ref).max()
    assert sp.scale_rms(onnx.ModelProto()) == 0                         # no norms: nothing to do


def test_a_crop_that_overflows_anyway_is_redone_in_full_precision(monkeypatch, capsys):
    from tennisbio.pose import estimator

    class S:
        def __init__(self, v):
            self.v, self.calls = v, 0

        def run(self, _, feed):
            self.calls += 1
            return [np.full((1, 308, 128, 96), self.v, np.float32)]

    p = object.__new__(sp.Sapiens2Pose)
    p.session, p.input, p.half, p.full, p.fallbacks, p.src, p.device = S(np.nan), "input", True, None, 0, "m", "cuda"
    p.idx = sorted({k for k in sp.TO_HALPE26 if k >= 0})
    full = S(0.5)
    monkeypatch.setattr(estimator, "_ort_session", lambda path, dev: full)
    img = np.zeros((300, 300, 3), np.uint8)
    kp, sc = p(img, [[100, 50, 140, 210], [10, 10, 60, 120]])
    assert p.fallbacks == 2 and full.calls == 2 and np.isfinite(kp).all() and sc[0, 0] == pytest.approx(0.5)
    assert "precisión completa" in capsys.readouterr().out
    p.half, p.session = False, S(np.nan)                               # in full precision nothing is redone
    p(img, [[100, 50, 140, 210]])
    assert p.fallbacks == 2
