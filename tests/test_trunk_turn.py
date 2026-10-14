"""Shoulder/hip turn from a synthetic 3D skeleton seen by a camera like the TV one (behind the near
baseline, ~7.5 m up, pitched 18° down): the 2D method (kinematics.line_turn) and the 3D one
(racket_orientation.trunk_rotation_3d / trunk_at) must both recover known turns."""
import numpy as np
import pytest

from tennisbio.kinematics import line_turn
from tennisbio.racket3d import Camera
from tennisbio.racket_orientation import RTMLIB_Z_SCALE, trunk_at, trunk_rotation_3d
from tennisbio.skeleton import COCO17, Skeleton

PITCH = 18.0
C = np.array([0.0, -18.0, 7.5])                  # camera centre, court metres (y towards the net, z up)
F, W, Hh = 2000.0, 1920, 1080
TURNS = [0.0, 45.0, 90.0, 120.0]
J = {n: i for i, n in enumerate(COCO17)}


def _rot():
    p = np.radians(PITCH)
    x = np.array([1.0, 0, 0])
    z = np.array([0, np.cos(p), -np.sin(p)])      # viewing direction
    return np.stack([x, np.cross(z, x), z])       # rows: camera x (right), y (down), z (forward)


def project(P):
    Pc = (np.atleast_2d(P) - C) @ _rot().T
    return np.c_[F * Pc[:, 0] / Pc[:, 2] + W / 2, F * Pc[:, 1] / Pc[:, 2] + Hh / 2]


def homography():
    R = _rot()
    K = np.array([[F, 0, W / 2], [0, F, Hh / 2], [0, 0, 1.0]])
    return K @ np.column_stack([R[:, 0], R[:, 1], -R @ C])


def body(theta_sh, theta_hip, centre, hand="right"):
    """COCO17 joints in court metres; + turn = dominant side back (towards the camera)."""
    dom = 1 if hand == "right" else -1
    cx, cy = centre
    P = np.zeros((17, 3))

    def pair(name, half, z, th):
        t = np.radians(th)
        v = half * np.array([np.cos(t), -dom * np.sin(t)])
        P[J[f"right_{name}"]] = [cx + v[0], cy + v[1], z]
        P[J[f"left_{name}"]] = [cx - v[0], cy - v[1], z]

    pair("shoulder", 0.19, 1.40, theta_sh)
    pair("hip", 0.15, 0.95, theta_hip)
    pair("elbow", 0.22, 1.12, theta_sh)
    pair("wrist", 0.24, 0.88, theta_sh)
    pair("knee", 0.12, 0.50, 0.0)
    pair("ankle", 0.13, 0.08, 0.0)
    for n, z in (("nose", 1.65), ("left_eye", 1.68), ("right_eye", 1.68), ("left_ear", 1.66), ("right_ear", 1.66)):
        P[J[n]] = [cx, cy, z]
    return P


def frames(centre, hand="right"):
    """A coil from square-on to 120° (hips half of it), then back."""
    sh = np.r_[np.linspace(0, 120, 25), np.linspace(120, 0, 13)]
    return sh, [body(s, s / 2, centre, hand) for s in sh]


@pytest.mark.parametrize("centre,hand", [((0.0, -1.0), "right"), ((3.5, -1.0), "right"), ((-3.5, -0.5), "left"),
                                         ((-3.0, -2.0), "right")])
def test_2d_turn_recovers_known_turns(centre, hand):
    sh, bodies = frames(centre, hand)
    kp = np.stack([project(P) for P in bodies])
    sk = Skeleton("coco17", hand)
    turn = line_turn(kp, sk, "shoulder", H=homography())
    hip = line_turn(kp, sk, "hip", H=homography())
    beta = abs(np.degrees(np.arctan2(centre[0], centre[1] - C[1])))     # oblique view of her
    for t in TURNS:
        i = int(np.argmin(np.abs(sh[:25] - t)))
        # square-on, whether she is turned towards or away from the oblique line of sight is not
        # observable in the width: up to 2β there (line_turn); from 45° on it is exact
        assert turn[i] == pytest.approx(sh[i], abs=3 if t else 2 * beta + 3), (t, turn[i])
        if t >= 45:                             # near square-on the side of the oblique view is ambiguous
            assert hip[i] == pytest.approx(sh[i] / 2, abs=3)
            assert turn[i] - hip[i] == pytest.approx(sh[i] / 2, abs=4)        # X-factor


def test_2d_turn_past_side_on_is_not_folded():
    sh, bodies = frames((0.0, -1.0))
    kp = np.stack([project(P) for P in bodies])
    turn = line_turn(kp, Skeleton("coco17", "right"), "shoulder")
    assert turn[24] == pytest.approx(120, abs=3)              # |width| read this as 60°
    assert int(np.nanargmax(turn)) == 24                      # the peak of the coil (its timing) is kept


def test_2d_label_swap_is_no_value():
    sh, bodies = frames((0.0, -1.0))
    kp = np.stack([project(P) for P in bodies])
    sk = Skeleton("coco17", "right")
    kp[2, [sk["left_shoulder"], sk["right_shoulder"]]] = kp[2, [sk["right_shoulder"], sk["left_shoulder"]]]
    assert np.isnan(line_turn(kp, sk, "shoulder")[2])


def rtmw3d(P, depth=True, ppm=100.0):
    """What RTMW3D returns through rtmlib for a correct 3D pose: x, y in crop px, depth in metres
    compressed by rtmlib's decoding (× 288/384) and shifted; depth=False: the flat depth seen on the
    broadcast view from behind."""
    r, u, f = Camera(PITCH).basis
    k3 = np.zeros((133, 3))
    k3[:17, 0] = P @ r * ppm
    k3[:17, 1] = -(P @ u) * ppm
    k3[:17, 2] = (P @ f / RTMLIB_Z_SCALE - 0.5) if depth else -0.5
    return k3


@pytest.mark.parametrize("hand", ["right", "left"])
def test_3d_turn_recovers_known_turns(hand):
    sh, bodies = frames((2.0, -1.0), hand)
    sc = np.ones(133)
    height = 1.57 / 0.93                           # nose 1.65 m, ankle 0.08 m
    rot = {i: trunk_rotation_3d(rtmw3d(P), sc, Camera(PITCH), hand, height_m=height) for i, P in enumerate(bodies)}
    for t in TURNS:
        i = int(np.argmin(np.abs(sh[:25] - t)))
        assert rot[i][0] == pytest.approx(sh[i], abs=2) and rot[i][1] == pytest.approx(sh[i] / 2, abs=2)
        assert rot[i][2] == pytest.approx(0.38, abs=0.02)     # a rigid segment keeps its length
        a = trunk_at(rot, i, 1)
        assert a["trunk3d_rigid"] and a["shoulder_turn_3d_deg"] == pytest.approx(sh[i], abs=4)
        assert a["x_factor_3d_deg"] == pytest.approx(sh[i] / 2, abs=4)


def test_3d_flat_depth_is_unobservable_not_a_small_turn():
    sh, bodies = frames((2.0, -1.0))
    sc = np.ones(133)
    rot = {i: trunk_rotation_3d(rtmw3d(P, depth=False), sc, Camera(PITCH), height_m=1.57 / 0.93) for i, P in enumerate(bodies)}
    assert rot[12][0] < 25                          # what the broadcast data showed: a side-on coil read as a small turn
    assert trunk_at(rot, 12, 1) == {"trunk3d_unobservable": True}
    assert trunk_at(rot, 0, 1)["shoulder_turn_3d_deg"] == pytest.approx(0, abs=3)   # square-on it is still seen


def test_2d_backhand_coil_is_referred_to_the_baseline_the_other_way():
    sh, bodies = frames((3.5, -1.0), hand="left")        # dominant (right) side turning forward
    kp = np.stack([project(P) for P in bodies])
    turn = line_turn(kp, Skeleton("coco17", "right"), "shoulder", H=homography(), coil=-1)
    for i in (9, 18, 24):
        assert turn[i] == pytest.approx(sh[i], abs=3)
