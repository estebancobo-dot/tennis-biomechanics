import numpy as np

from tennisbio.racket3d import Camera, candidates, describe_face, solve_sequence, synthetic_observation
from tennisbio.validation.racket3d_synth import random_stroke


def test_true_orientation_is_among_candidates():
    rng, cam = np.random.default_rng(1), Camera(20)
    for _ in range(200):
        a = rng.normal(size=3); a /= np.linalg.norm(a)
        n = rng.normal(size=3); n -= (n @ a) * a; n /= np.linalg.norm(n)
        cs = candidates(synthetic_observation(a, n, cam), cam)
        best = min(max(np.degrees(np.arccos(np.clip(a @ ca, -1, 1))), np.degrees(np.arccos(np.clip(n @ cn, -1, 1))))
                   for ca, cn in cs)
        assert best < 1.0


def test_noiseless_stroke_is_mostly_recovered():
    rng, cam = np.random.default_rng(3), Camera(20)
    ok = []
    for _ in range(10):
        A, N, imp = random_stroke(rng)
        _, normals, _ = solve_sequence([synthetic_observation(a, n, cam) for a, n in zip(A, N)], cam, imp)
        ok += [np.degrees(np.arccos(np.clip(p @ q, -1, 1))) < 15 for p, q in zip(normals, N)]
    assert np.mean(ok) > 0.6


def test_describe_face():
    assert describe_face(np.array([0, 0, -1.0]))["points_to"] == "suelo"
    assert describe_face(np.array([0, -1.0, 0]))["points_to"] == "valla trasera"
    d = describe_face(np.array([0, np.cos(0.3), -np.sin(0.3)]))
    assert d["points_to"] == "red" and d["tilt_deg"] > 0          # strings slightly down = closed


def test_hand_prior_palm_sign():
    """Right hand seen from behind, palm towards the net, fingers up: face must point to the net (+Y)."""
    from tennisbio.racket3d import RIGHT_HAND, hand_prior

    k3 = np.zeros((133, 3))
    sc = np.ones(133)
    w, idx, pky = RIGHT_HAND, RIGHT_HAND + 5, RIGHT_HAND + 17
    k3[w] = [100, 200, 0.0]
    k3[idx] = [90, 180, 0.0]      # index knuckle: image-left and up
    k3[pky] = [110, 180, 0.0]     # little-finger knuckle: image-right and up
    k3[8], k3[10] = [100, 260, -0.1], [100, 200, 0.0]   # elbow below/behind the wrist
    p = hand_prior(k3, sc, Camera(0.0), "right", grip_close_deg=0.0, px_per_m=100.0)
    assert p.face[1] > 0.95
    # mirror image for a left-hander: index knuckle on the image-right
    from tennisbio.racket3d import LEFT_HAND
    k3l = np.zeros((133, 3))
    k3l[LEFT_HAND] = [100, 200, 0.0]
    k3l[LEFT_HAND + 5] = [110, 180, 0.0]
    k3l[LEFT_HAND + 17] = [90, 180, 0.0]
    k3l[7], k3l[9] = [100, 260, -0.1], [100, 200, 0.0]
    left = hand_prior(k3l, sc, Camera(0.0), "left", grip_close_deg=0.0, px_per_m=100.0)
    assert left.face[1] > 0.95


def test_observe_keypoints_face_on_and_edge_on():
    from tennisbio.racket3d import HEAD_LENGTH, HEAD_WIDTH, observe_keypoints
    ppm = 100.0
    L, W = HEAD_LENGTH * ppm, HEAD_WIDTH * ppm
    face_on = np.array([[0, -L], [0, 0], [0, 30], [-W / 2, -L / 2], [W / 2, -L / 2]])
    o = observe_keypoints(face_on, ppm)
    assert np.allclose(o.axis2d, [0, -1]) and abs(o.length_ratio - 1) < 1e-6 and abs(o.width_ratio - 1) < 1e-6
    edge_on = face_on.copy()
    edge_on[3:, 0] = 0
    assert observe_keypoints(edge_on, ppm).width_ratio < 1e-6


def test_trunk_rotation_3d_square_and_turned():
    from tennisbio.racket3d import Camera
    from tennisbio.racket_orientation import trunk_rotation_3d
    cam = Camera(0.0)                     # level camera behind the player: x right, depth = towards the net
    k3 = np.zeros((133, 3))
    k3[0] = [0, 0, 0]
    k3[15], k3[16] = [0, 300, 0], [0, 300, 0]
    k3[5], k3[6], k3[11], k3[12] = [-40, 60, 0], [40, 60, 0], [-30, 160, 0], [30, 160, 0]
    sc = np.ones(133)
    sh, hp, *_ = trunk_rotation_3d(k3, sc, cam)
    assert abs(sh) < 1e-6 and abs(hp) < 1e-6
    k3[6, 2], k3[5, 2] = -0.2, 0.2        # right shoulder back (towards the camera), left forward
    sh, hp, *_ = trunk_rotation_3d(k3, sc, cam)
    assert 30 < sh < 70 and abs(hp) < 1e-6


def test_trunk_at_needs_agreeing_readings():
    from tennisbio.racket_orientation import trunk_at
    t = trunk_at({10: (60.0, 30.0), 12: (64.0, 30.0), 14: (62.0, 31.0)}, 12, 4)
    assert t["shoulder_turn_3d_deg"] == 62.0 and t["x_factor_3d_deg"] == 32.0 and t["trunk3d_readings"] == 3
    assert trunk_at({10: (-20.0, 0.0), 12: (60.0, 0.0), 14: (-10.0, 30.0), 16: (70.0, 30.0)}, 12, 4) == {"trunk3d_unstable": True}
    assert trunk_at({10: (60.0, 0.0)}, 10, 4) == {} and trunk_at({}, None, 4) == {}


def test_backhand_hitting_face_is_back_of_hand():
    from tennisbio.racket3d import RIGHT_HAND, Camera, hand_prior
    cam = Camera(20.0)
    k3 = np.zeros((133, 3))
    k3[0], k3[15], k3[16] = [0, 0, 0], [0, 300, 0], [0, 300, 0]
    k3[8], k3[10] = [40, 100, 0], [60, 120, 0]
    k3[RIGHT_HAND + 0], k3[RIGHT_HAND + 5], k3[RIGHT_HAND + 17] = [60, 120, 0], [70, 130, 0.05], [70, 130, -0.05]
    sc = np.ones(133)
    fh = hand_prior(k3, sc, cam, "right", 0.0)
    bh = hand_prior(k3, sc, cam, "right", 0.0, hitting_face="back")
    assert np.allclose(fh.face, -bh.face)
