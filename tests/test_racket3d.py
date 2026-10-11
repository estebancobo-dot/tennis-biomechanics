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
