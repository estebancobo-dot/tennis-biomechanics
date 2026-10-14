"""Her height in image px (body_scale): from the court and her real height, robust to posture, to
missing faces and to which frames were posed; checked against her body segments."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from tennisbio.body_scale import (ANKLE_FRAC, LEG_FRAC, TORSO_FRAC, height_scale, segment_height,
                                  vertical_px)
from tennisbio.kinematics import body_height, scale_track
from tennisbio.skeleton import Skeleton

SK = Skeleton("coco17", "right")
FPS = 50.0
HEIGHT = 1.84


def tv_camera(f=1900.0, pitch=16.0, h=9.0, back=20.0, size=(1920, 1080), x0=0.0):
    """3x4 projection of a broadcast main camera: behind the near baseline (court y = 0), elevated,
    looking down the court (court x right, y towards the net, z up)."""
    w, hh = size
    K = np.array([[f, 0, w / 2], [0, f, hh / 2], [0, 0, 1.0]])
    p = np.radians(pitch)
    fwd = np.array([0.0, np.cos(p), -np.sin(p)])
    right = np.array([1.0, 0, 0])
    down = np.cross(fwd, right)
    R = np.vstack([right, down, fwd])
    C = np.array([x0, -back, h])
    return K @ np.c_[R, -R @ C]


def project(P, X):
    q = np.c_[X, np.ones(len(X))] @ P.T
    return q[:, :2] / q[:, 2:]


def court_H(P):
    """Court (x, y, 1) → image homography of the camera (the ground plane z = 0)."""
    return P[:, [0, 1, 3]] / P[2, 3]


def body3d(x, y, height=HEIGHT, crouch=0.0, lean_deg=0.0, hop=0.0):
    """COCO-17 joints (17, 3) in court metres of a player seen from behind (facing +y), with standard
    anthropometric heights. crouch: hips lowered by this share of the height (knees bent forward);
    lean_deg: trunk leaning towards the net; hop: both feet (and the body) lifted by this many metres."""
    H = height
    hip_z = (0.52 - crouch) * H + hop
    lean = np.radians(lean_deg)
    up = np.array([0.0, np.sin(lean), np.cos(lean)])           # the trunk's axis
    hipc = np.array([x, y, hip_z])
    sh = hipc + TORSO_FRAC * H * up
    head = hipc + 0.41 * H * up
    knee_fwd = 0.6 * crouch * H
    j = np.zeros((17, 3))
    j[0] = head + [0, 0.05 * H, 0]                               # nose (on the far side of the head)
    j[1], j[2] = head + [-0.02 * H, 0.04 * H, 0.01 * H], head + [0.02 * H, 0.04 * H, 0.01 * H]
    j[3], j[4] = head + [-0.045 * H, 0, 0], head + [0.045 * H, 0, 0]
    j[5], j[6] = sh + [-0.11 * H, 0, 0], sh + [0.11 * H, 0, 0]
    j[7], j[8] = sh + [-0.14 * H, 0, -0.17 * H], sh + [0.14 * H, 0, -0.17 * H]
    j[9], j[10] = sh + [-0.15 * H, 0.05 * H, -0.33 * H], sh + [0.16 * H, 0.05 * H, -0.33 * H]
    j[11], j[12] = hipc + [-0.09 * H, 0, 0], hipc + [0.09 * H, 0, 0]
    knee_z = 0.285 * H + hop - 0.3 * crouch * H
    j[13], j[14] = [x - 0.09 * H, y + knee_fwd, knee_z], [x + 0.09 * H, y + knee_fwd, knee_z]
    j[15], j[16] = [x - 0.10 * H, y, ANKLE_FRAC * H + hop], [x + 0.10 * H, y, ANKLE_FRAC * H + hop]
    return j


def track(P, xs, ys, seed=0, noise=0.8, **kw):
    """(T, 17, 2) image keypoints of the player at the court points (xs[t], ys[t]), with pose jitter."""
    rng = np.random.default_rng(seed)
    kp = np.stack([project(P, body3d(x, y, **kw)) for x, y in zip(xs, ys)])
    return kp + rng.normal(0, noise, kp.shape)


def true_px(P, x, y, height=HEIGHT):
    return float(vertical_px(P, np.array([[x, y]]), height)[0])


@pytest.mark.parametrize("pitch,f,h,back", [(14.0, 2300.0, 8.0, 24.0), (18.0, 1900.0, 9.5, 20.0), (22.0, 1600.0, 11.0, 17.0)])
def test_court_scale_is_her_height_at_every_court_position(pitch, f, h, back):
    """Synthetic main camera (elevated, behind, pitch 14-22°): standing at any point of the near half
    (and at the far baseline), the scale is the image length of her real height there within 2 %,
    with the camera recovered from the court homography alone (focal length, pitch, position)."""
    P = tv_camera(f, pitch, h, back)
    H = court_H(P)
    for x, y in [(-3.0, -2.0), (0.0, 0.0), (3.5, 1.0), (1.0, 4.0), (-2.0, 6.0), (0.0, 23.0)]:
        img = track(P, np.full(60, x), np.full(60, y), noise=0.5 if y < 12 else 0.2)
        assert (img[:, :, 1] < 1080).all() and (img[:, :, 1] > 0).all(), (x, y)      # in the picture
        ht, src, info = height_scale(img, SK, FPS, HEIGHT, H, (1080, 1920))
        assert src == "court", (x, y, info)
        assert np.median(ht) == pytest.approx(true_px(P, x, y), rel=0.02), (x, y)
        assert info["segments_ratio"] == pytest.approx(1.0, abs=0.08)


def test_court_scale_does_not_change_when_she_crouches_and_the_former_one_does():
    """Knees bent and trunk leaning: the court scale stays (it is where she stands, not her posture);
    nose → ankle, the former estimate, reads her about 10 % shorter."""
    P = tv_camera()
    H = court_H(P)
    stand = track(P, np.zeros(60), np.zeros(60))
    low = track(P, np.zeros(60), np.zeros(60), crouch=0.12, lean_deg=30)
    h_stand = np.median(height_scale(stand, SK, FPS, HEIGHT, H, (1080, 1920))[0])
    h_low, src, _ = height_scale(low, SK, FPS, HEIGHT, H, (1080, 1920))
    assert src == "court"
    assert np.median(h_low) == pytest.approx(h_stand, rel=0.01)
    assert np.median(h_stand) == pytest.approx(true_px(P, 0, 0), rel=0.015)
    assert body_height(low, SK) < 0.92 * body_height(stand, SK)


def test_court_scale_without_any_face_seen():
    """From behind the face is rarely found: without a single nose the court scale is the same and
    the former estimate has nothing."""
    P = tv_camera()
    H = court_H(P)
    img = track(P, np.full(80, 1.0), np.full(80, -1.0))
    ref = height_scale(img, SK, FPS, HEIGHT, H, (1080, 1920))[0]
    img[:, SK["nose"]] = np.nan
    ht, src, info = height_scale(img, SK, FPS, HEIGHT, H, (1080, 1920))
    assert src == "court" and "pose_ratio" not in info
    np.testing.assert_allclose(ht, ref)
    assert np.isnan(body_height(img, SK))


def test_court_scale_follows_her_as_she_moves_and_ignores_a_hop():
    """Running from behind the baseline to the service line she gets smaller in the image: the scale
    follows frame by frame (within 3 %); a split-step hop (feet 25 cm up for 0.12 s) is not read as
    moving away (within 1 %)."""
    P = tv_camera()
    H = court_H(P)
    T = 150
    ys = np.r_[np.full(40, -2.0), np.linspace(-2.0, 5.0, 70), np.full(40, 5.0)]
    xs = np.linspace(-1.0, 2.0, T)
    img = track(P, xs, ys)
    ht, src, _ = height_scale(img, SK, FPS, HEIGHT, H, (1080, 1920))
    truth = np.array([true_px(P, x, y) for x, y in zip(xs, ys)])
    assert src == "court"
    assert truth[0] > 1.15 * truth[-1]                       # a real change of size in the picture
    assert np.max(np.abs(ht / truth - 1)) < 0.03
    # a hop at the start, standing still
    hop = img.copy()
    for t in range(10, 16):
        hop[t] = project(P, body3d(xs[t], ys[t], hop=0.25)) + (img[t] - project(P, body3d(xs[t], ys[t])))
    hh = height_scale(hop, SK, FPS, HEIGHT, H, (1080, 1920))[0]
    assert np.max(np.abs(hh[:40] / ht[:40] - 1)) < 0.01


def test_court_scale_does_not_depend_on_which_frames_were_posed():
    """Pose ranges (fine_pass.pose_ranges with a frame in five posed elsewhere): around the stroke the
    scale is exactly that of the whole window; the former estimate changes with the frames posed."""
    P = tv_camera()
    H = court_H(P)
    T = 400
    ys = -1.5 + 2.5 * np.sin(np.linspace(0, 3 * np.pi, T))
    xs = 3.0 * np.cos(np.linspace(0, 2 * np.pi, T))
    crouch = 0.08 * (1 + np.sin(np.linspace(0, 9 * np.pi, T))) / 2
    rng = np.random.default_rng(3)
    img = np.stack([project(P, body3d(x, y, crouch=c, lean_deg=30 * c / 0.08)) for x, y, c in zip(xs, ys, crouch)])
    img += rng.normal(0, 0.8, img.shape)
    img[rng.random(T) < 0.9, SK["nose"]] = np.nan              # the face is seen in ~10 % of the frames
    whole, src, _ = height_scale(img, SK, FPS, HEIGHT, H, (1080, 1920))
    assert src == "court"
    impact = 250
    keep = np.zeros(T, bool)
    keep[::5] = True
    keep[impact - int(2.8 * FPS):impact + int(2.0 * FPS)] = True
    part = img.copy()
    part[~keep] = np.nan
    ht = height_scale(part, SK, FPS, HEIGHT, H, (1080, 1920))[0]
    a, b = impact - int(1.0 * FPS), impact + int(0.8 * FPS)
    np.testing.assert_array_equal(ht[a:b], whole[a:b])
    assert body_height(part, SK) != pytest.approx(body_height(img, SK), rel=0.003)


def test_a_court_the_body_contradicts_is_not_used():
    """A court read before a zoom (or a wrong fit): her trunk and legs measured with it are not those of
    a person of her height, so her body segments give the scale (within 6 %)."""
    P = tv_camera()
    Z = np.array([[1.6, 0, -0.6 * 960], [0, 1.6, -0.6 * 540], [0, 0, 1.0]])    # zoom ×1.6 about the centre
    img = track(Z @ P, np.zeros(60), np.full(60, -0.5))
    ht, src, info = height_scale(img, SK, FPS, HEIGHT, court_H(P), (1080, 1920))
    assert src == "segments" and info["court"] == "contradicha_por_el_cuerpo"
    assert np.median(ht) == pytest.approx(true_px(Z @ P, 0, -0.5), rel=0.06)


def test_without_court_segments_then_pose():
    P = tv_camera()
    img = track(P, np.zeros(60), np.zeros(60), crouch=0.04)
    ht, src, info = height_scale(img, SK, FPS, HEIGHT, None, None)
    assert src == "segments" and info["court"] == "sin_pista"
    assert np.median(ht) == pytest.approx(true_px(P, 0, 0), rel=0.06)
    assert segment_height(img, SK) == pytest.approx(np.median(ht), rel=0.01)
    # nothing but a head and the feet: the former estimate, as before
    only = np.full_like(img, np.nan)
    only[:, [SK["nose"], SK["left_ankle"], SK["right_ankle"]]] = img[:, [SK["nose"], SK["left_ankle"], SK["right_ankle"]]]
    ht2, src2, _ = height_scale(only, SK, FPS, HEIGHT, None, None, mode="segments")
    assert src2 == "pose" and np.isfinite(ht2).all()


def test_pose_mode_is_the_former_scale():
    P = tv_camera()
    img = track(P, np.zeros(60), np.zeros(60))
    ht, src, _ = height_scale(img, SK, FPS, HEIGHT, court_H(P), (1080, 1920), mode="pose")
    assert src == "pose"
    np.testing.assert_array_equal(ht, scale_track(img, SK, body_height(img, SK), FPS))
    with pytest.raises(ValueError):
        height_scale(img, SK, FPS, HEIGHT, None, None, mode="feet")


def test_leg_and_trunk_shares_are_those_of_the_synthetic_body():
    """The segment shares (TORSO_FRAC, LEG_FRAC) read on an upright synthetic player give back her height."""
    P = tv_camera()
    img = track(P, np.zeros(30), np.zeros(30), noise=0.0)
    assert segment_height(img, SK) == pytest.approx(true_px(P, 0, 0), rel=0.04)
    assert LEG_FRAC + ANKLE_FRAC == pytest.approx(0.52, abs=0.01)


# ---- run_clip: the fine pass gets the court of the window -------------------------------------------

def _synth_clip(tmp_path, P, n=300, swings=(60, 150, 240), size=(640, 480), keep=None):
    from tennisbio.pipeline import savez_atomic
    from tennisbio.pose.yolo import _objects

    video = tmp_path / "w.avi"
    if not video.exists():
        w = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), int(FPS), size)
        for _ in range(n):
            w.write(np.zeros((size[1], size[0], 3), np.uint8))
        w.release()
    ys = -1.0 + 0.8 * np.sin(np.linspace(0, 2 * np.pi, n))
    xs = np.linspace(-1.0, 1.0, n)
    boxes, kps, confs, feats = [], [], [], []
    for t in range(n):
        if keep is not None and not keep[t]:
            boxes.append(np.zeros((0, 4), np.float32)); kps.append(np.zeros((0, 17, 2), np.float32))
            confs.append(np.zeros((0, 17), np.float32)); feats.append(np.zeros((0, 32), np.float32))
            continue
        k = project(P, body3d(xs[t], ys[t])) + np.random.default_rng(t).normal(0, 0.4, (17, 2))
        for s in swings:
            k[10, 0] += 70 * np.exp(-((t - s) / 4.0) ** 2)
            k[10, 1] -= 30 * np.exp(-((t - s - 3) / 5.0) ** 2)
        c = np.full(17, 0.9, np.float32)
        c[0] = 0.9 if t % 25 == 0 else 0.05                          # face seen in one frame in 25
        x0, y0 = k.min(0) - 5
        x1, y1 = k.max(0) + 5
        boxes.append(np.array([[x0, y0, x1, y1]], np.float32)); kps.append(k[None].astype(np.float32))
        confs.append(c[None]); feats.append(np.full((1, 32), 1 / 32, np.float32))
    return video, dict(fps=FPS, n=n, boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs), feats=_objects(feats)), xs, ys


def test_run_clip_measures_with_the_court_scale_and_the_same_with_pose_ranges(tmp_path):
    from tennisbio.clip_pipeline import keep_key, run_clip
    from tennisbio.fine_gate import pose_keep
    from tennisbio.pipeline import savez_atomic

    P = tv_camera(f=640.0, pitch=17.0, h=9.0, back=19.0, size=(640, 480))
    H = court_H(P)
    video, pose, xs, ys = _synth_clip(tmp_path, P)
    d = tmp_path / "a"
    d.mkdir()
    savez_atomic(d / "w.npz", **pose)
    full = run_clip(video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, court_H=H)
    old = run_clip(video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, court_H=H, height_scale="pose")
    assert full.height_source == "court" and old.height_source == "pose" and full.stats["height_scale"] == "court"
    truth = np.array([true_px(P, x, y) for x, y in zip(xs, ys)])
    assert np.max(np.abs(full.height_t / truth - 1)) < 0.03
    # the swings are found as before (the former scale); only the measures change units
    assert [i.frame for i in full.impacts] == [i.frame for i in old.impacts] and len(full.impacts) == 3
    # pose ranges with a frame in five elsewhere: the stroke inside is measured exactly the same
    keep = pose_keep(300, [(150, 150, "golpe_de_bola")], FPS, pre_s=2.8, post_s=1.2, fill_every=5)
    d2 = tmp_path / "b"
    d2.mkdir()
    savez_atomic(d2 / f"w_r{keep_key(keep)}.npz", **_synth_clip(tmp_path, P, keep=keep)[1])
    part = run_clip(video, d2 / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep,
                    split=False, court_H=H)
    x = min(full.strokes, key=lambda s: abs(s.impact_frame - 150))
    y = min(part.strokes, key=lambda s: abs(s.impact_frame - 150))
    assert x.impact_frame == y.impact_frame and x.phases == y.phases
    assert x.metrics.keys() == y.metrics.keys()
    for k, v in x.metrics.items():
        assert v == y.metrics[k] or (isinstance(v, float) and np.isnan(v) and np.isnan(y.metrics[k])), k
