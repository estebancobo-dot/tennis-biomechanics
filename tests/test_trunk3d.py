"""The trunk's 3D turn from MotionAGFormer (adopted 03-11 after request 83)."""
import numpy as np

from tennisbio import trunk3d as T
from tennisbio.skeleton import Skeleton


def _joints(turn_deg, n=5):
    """Camera-axes joints of a body whose shoulder and hip lines are turned by turn_deg about the vertical, seen
    by a camera with no pitch (x right, y down, z away)."""
    X = np.zeros((n, 17, 3))
    a = np.radians(turn_deg)
    for (l, rgt) in ((T.H_L_SH, T.H_R_SH), (T.H_L_HIP, T.H_R_HIP)):
        X[:, l] = [-0.2 * np.cos(a), 0, 0.2 * np.sin(a)]
        X[:, rgt] = [0.2 * np.cos(a), 0, -0.2 * np.sin(a)]
    return X


def test_square_on_is_zero_and_right_shoulder_back_is_positive():
    sq = T.turns(_joints(0), 0.0, "right")
    assert np.allclose(sq[:, :2], 0, atol=1e-6) and np.allclose(sq[:, 2], 0.4)
    back = T.turns(_joints(30), 0.0, "right")          # the right shoulder comes towards the camera (−z)
    assert np.allclose(back[:, :2], 30, atol=1e-6)
    assert np.allclose(T.turns(_joints(30), 0.0, "left")[:, :2], -30, atol=1e-6)


def test_trunk_reads_the_loaded_frame_with_the_same_rules_as_before():
    sk = Skeleton("halpe26", "right")
    n = 12
    img = np.full((n, len(sk.names), 2), 100.0)
    conf = np.ones((n, len(sk.names)))

    class Lift:
        def lift(self, kp, sc, w, h):
            assert kp.shape == (n, 17, 2) and (w, h) == (1280, 720)
            return _joints(40, n)

    m, rot = T.trunk(Lift(), img, conf, sk, (1280, 720), 0.0, "right", 6, 3)
    assert m["shoulder_turn_3d_deg"] == 40 and m["x_factor_3d_deg"] == 0 and m["trunk3d_model"] == "motionagformer"
    assert len(rot) == n


def test_unseen_trunk_gives_no_reading_and_missing_model_keeps_the_former(tmp_path):
    sk = Skeleton("halpe26", "right")
    img, conf = np.zeros((4, len(sk.names), 2)), np.zeros((4, len(sk.names)))

    class Lift:
        def lift(self, kp, sc, w, h):
            return _joints(10, 4)

    assert T.rotations(Lift(), img, conf, sk, (100, 100), 0.0) == {}
    assert T.model_path({"trunk3d": {"onnx": str(tmp_path / "none.onnx")}}) is None
    assert T.model_path({"trunk3d": {"model": "rtmw3d"}}) is None
