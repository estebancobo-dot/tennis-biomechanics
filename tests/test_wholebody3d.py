"""RTMW3D depth decoding (pose.wholebody3d): synthetic SimCC outputs with known keypoints must
decode to the right metres; rtmlib's own decoding compresses depth differences × 0.75."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tennisbio.pose.wholebody3d import SIMCC_SPLIT, Z_RANGE, WholeBody3D, decode_simcc3d, depth_m

K = 133
W_IN, H_IN = 288, 384                     # model input (w, h); depth axis = width (mmpose (288, 384, 288))
BX, BY, BZ = int(W_IN * SIMCC_SPLIT), int(H_IN * SIMCC_SPLIT), int(W_IN * SIMCC_SPLIT)   # 576, 768, 576


def _peak(n, loc, sigma=3.0):
    i = np.arange(n)
    return np.exp(-0.5 * ((i - loc) / sigma) ** 2).astype(np.float32)


def simcc(x_px, y_px, z_m):
    """Raw outputs (1, K, bins) whose maxima are at the given crop pixels and depths (metres)."""
    sx, sy, sz = np.zeros((1, K, BX), np.float32), np.zeros((1, K, BY), np.float32), np.zeros((1, K, BZ), np.float32)
    for k in range(K):
        sx[0, k] = _peak(BX, round(x_px[k] * SIMCC_SPLIT))
        sy[0, k] = _peak(BY, round(y_px[k] * SIMCC_SPLIT))
        z_bin = (z_m[k] / Z_RANGE + 1) * (BZ / SIMCC_SPLIT / 2) * SIMCC_SPLIT
        sz[0, k] = _peak(BZ, round(z_bin))
    return sx, sy, sz


def _truth(seed=0):
    rng = np.random.default_rng(seed)
    # depths on the bin grid (one bin = Z_RANGE / 288 m) so the argmax is exact
    step = Z_RANGE / (BZ / SIMCC_SPLIT / 2) / SIMCC_SPLIT
    z = np.round(rng.uniform(-0.8, 0.8, K) / step) * step
    return rng.integers(10, W_IN - 10, K).astype(float), rng.integers(10, H_IN - 10, K).astype(float), z


def test_depth_m_centre_and_ends():
    assert depth_m(144.0, 576) == pytest.approx(0.0)              # middle of the 288 px depth axis
    assert depth_m(0.0, 576) == pytest.approx(-Z_RANGE)
    assert depth_m(288.0, 576) == pytest.approx(Z_RANGE)


def test_decode_recovers_known_metres():
    x, y, z = _truth()
    k3, sc, k2 = decode_simcc3d(*simcc(x, y, z))
    assert k3.shape == (1, K, 3) and sc.shape == (1, K) and k2 is None
    assert np.allclose(k3[0, :, 0], x) and np.allclose(k3[0, :, 1], y)
    assert np.allclose(k3[0, :, 2], z, atol=1e-6)
    # a known depth difference (e.g. shoulder to shoulder) in metres
    assert k3[0, 6, 2] - k3[0, 5, 2] == pytest.approx(z[6] - z[5], abs=1e-6)


def test_rtmlib_decoding_compresses_depth_by_three_quarters():
    """The bug being corrected: rtmlib divides the depth location by half the input height (192),
    not half the depth axis (144). Same 2D, same scores; depth differences × 288/384."""
    from rtmlib import RTMPose3d

    x, y, z = _truth(1)
    out = simcc(x, y, z)
    center, scale = np.array([500.0, 300.0]), np.array([240.0, 320.0])
    ours, sc, k2 = decode_simcc3d(*out, center=center, scale=scale)
    fake = SimpleNamespace(model_input_size=(W_IN, H_IN), z_range=Z_RANGE)
    rk3, rsc, _, rk2 = RTMPose3d.postprocess(fake, list(out), center, scale)
    assert np.allclose(rk2, k2) and np.allclose(rsc, sc) and np.allclose(rk3[..., :2], ours[..., :2])
    d_ours, d_rtm = np.diff(ours[0, :, 2]), np.diff(rk3[0, :, 2])
    assert np.allclose(d_rtm, d_ours * 288 / 384, atol=1e-6)
    assert np.allclose(d_ours, d_rtm * 4 / 3, atol=1e-6)


def test_wholebody3d_call_returns_metres():
    x, y, z = _truth(2)
    out = simcc(x, y, z)
    center, scale = np.array([100.0, 200.0]), np.array([90.0, 120.0])
    wb = WholeBody3D.__new__(WholeBody3D)
    wb.model = SimpleNamespace(preprocess=lambda frame, box: (frame, center, scale),
                               inference=lambda img: list(out), z_range=Z_RANGE)
    k3, sc, k2 = wb(np.zeros((4, 4, 3)), np.array([0, 0, 10, 10]))
    assert k3.shape == (K, 3) and sc.shape == (K,) and k2.shape == (K, 2)
    assert np.allclose(k3[:, 2], z, atol=1e-6)
    assert np.allclose(k2[:, 0], x / W_IN * scale[0] + center[0] - 0.5 * scale[0])


def test_model_depth_axis_has_width_bins():
    """On a machine with the model: its depth output has the width's bins (2 × 288), not the height's."""
    root = Path(__file__).resolve().parents[1]
    m = next((p for p in (root / "models" / "rtmw3d-x.onnx", root.parents[2] / "models" / "rtmw3d-x.onnx")
              if p.exists()), None)
    if m is None:
        pytest.skip("models/rtmw3d-x.onnx not present")
    import onnxruntime as ort
    s = ort.InferenceSession(str(m), providers=["CPUExecutionProvider"])
    assert s.get_inputs()[0].shape[-2:] == [H_IN, W_IN]
    assert [o.shape[-1] for o in s.get_outputs()] == [BX, BY, BZ]
