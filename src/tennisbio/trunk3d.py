"""Shoulder and hip turn in 3D from the 2D pose with MotionAGFormer (B3, step 2.5, 03-11).

Adopted after request 83 (scripts/bench_candidates.py --only mag3d): against a reference triangulated from two
calibrated views of CalTennis, 58 % of its frames within 15° of the trunk turn (RTMW3D, the former model: 13 %),
median error 12° (40°), and it runs on the 2D pose the fine pass already has (no image model; ~200 frames/s on the
CPU). Config `trunk3d.model: motionagformer` (default) or `rtmw3d` (the former reading, from the hand's 3D model);
when the MotionAGFormer file is missing, the former reading is kept and the pipeline says so.

Same convention and the same stability rules as racket_orientation.trunk_rotation_3d / trunk_at: 0 = line square to
the net, + = dominant side turned back (towards the camera), world frame from the broadcast camera's pitch.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .skeleton import COCO17, Skeleton

# Human3.6M joints of MotionAGFormer's output (pose.motionagformer)
H_R_HIP, H_L_HIP, H_L_SH, H_R_SH = 1, 4, 11, 14
MIN_SCORE = 0.5
_LIFTERS: dict = {}


def model_name(cfg: dict) -> str:
    """`trunk3d.model`: motionagformer (default), metrabs (21-11, #309: its integrated test) or rtmw3d."""
    return str((cfg.get("trunk3d") or {}).get("model") or "motionagformer").lower()


def model_path(cfg: dict) -> Path | None:
    """The MotionAGFormer ONNX of `trunk3d.onnx` when `trunk3d.model` is motionagformer and it exists, else None."""
    from .config import resolve_path

    t = cfg.get("trunk3d") or {}
    if (t.get("model") or "motionagformer") != "motionagformer":
        return None
    p = resolve_path(t.get("onnx") or "models/motionagformer_xs.onnx")
    return p if p is not None and Path(p).exists() else None


def lifter(path: Path, device: str = "cpu"):
    """One session per process (CPU: DirectML does not load this model, request 83)."""
    key = str(path)
    if key not in _LIFTERS:
        from .pose.motionagformer import MotionAGFormerLifter
        _LIFTERS[key] = MotionAGFormerLifter(path, "cpu")
    return _LIFTERS[key]


def coco17(img: np.ndarray, conf: np.ndarray, sk: Skeleton) -> tuple[np.ndarray, np.ndarray]:
    """(T, 17, 2) and (T, 17) in COCO order from a run's keypoints in any schema."""
    idx = [sk[n] for n in COCO17]
    return np.asarray(img, float)[:, idx], np.asarray(conf, float)[:, idx]


def turns(X: np.ndarray, pitch_deg: float, hand: str = "right") -> np.ndarray:
    """(T, 4): shoulder turn, hip turn (deg) and the two segment lengths (model units) of MotionAGFormer joints in
    camera axes (x right, y down, z away), in the court frame of racket_orientation.trunk_rotation_3d."""
    from .racket3d import Camera

    r, u, f = Camera(pitch_deg).basis
    to_w = lambda p: p[..., 0:1] * r - p[..., 1:2] * u + p[..., 2:3] * f
    dom = 1 if hand == "right" else -1
    out = []
    for a, b in ((H_L_SH, H_R_SH), (H_L_HIP, H_R_HIP)):
        d = to_w(X[:, b]) - to_w(X[:, a])
        out.append((-dom * np.degrees(np.arctan2(d[:, 1], d[:, 0])), np.hypot(d[:, 0], d[:, 1])))
    return np.stack([out[0][0], out[1][0], out[0][1], out[1][1]], 1)


def rotations(lift, img: np.ndarray, conf: np.ndarray, sk: Skeleton, size: tuple[int, int], pitch_deg: float,
              hand: str = "right") -> dict[int, tuple]:
    """frame → (shoulder turn, hip turn, shoulder length, hip length) where the four trunk points are seen."""
    kp, sc = coco17(img, conf, sk)
    if not len(kp):
        return {}
    X = lift.lift(kp, sc, *size)
    rt = turns(X, pitch_deg, hand)
    seen = (sc[:, [5, 6, 11, 12]] >= MIN_SCORE).all(1) & np.isfinite(rt).all(1)
    return {int(f): tuple(float(v) for v in rt[f]) for f in np.flatnonzero(seen)}


def trunk(lift, img, conf, sk, size, pitch_deg, hand, loaded_frame, half_window) -> tuple[dict, dict]:
    """(the stroke's trunk metrics at the loaded frame, the per-frame readings) as stroke_faces gives them."""
    from .racket_orientation import trunk_at

    rot = rotations(lift, img, conf, sk, size, pitch_deg, hand)
    m = trunk_at(rot, loaded_frame, half_window)
    if m:
        m["trunk3d_model"] = "motionagformer"
    return m, rot


# ---------------------------------------------------------------- MeTRAbs (21-11, #309): one calibrated view

_METRABS: dict = {}


def metrabs():
    """One MeTRAbs per process (TensorFlow; tennisbio.pose.metrabs3d)."""
    if "m" not in _METRABS:
        from .pose.metrabs3d import Metrabs
        _METRABS["m"] = Metrabs()
    return _METRABS["m"]


def intrinsics(H: np.ndarray, frame_shape) -> np.ndarray:
    """The camera's K from the court's homography (court.focal_and_rotation: the focal, principal point at the centre)."""
    from .court import CourtFit, focal_and_rotation

    h, w = frame_shape[:2]
    f, _, _ = focal_and_rotation(CourtFit(np.asarray(H, float), 1.0), frame_shape)
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])


def metrabs_rotations(model, clip: Path, boxes: list, frames, K: np.ndarray, pitch_deg: float,
                      hand: str = "right") -> dict[int, tuple]:
    """frame → (shoulder turn, hip turn, shoulder length, hip length) from MeTRAbs' trunk in the camera's frame (mm),
    in the same court frame and convention as the 2D-to-3D lifter's (turns)."""
    import cv2

    want = sorted({int(f) for f in frames if 0 <= int(f) < len(boxes) and boxes[int(f)] is not None})
    out: dict[int, tuple] = {}
    if not want:
        return out
    cap = cv2.VideoCapture(str(clip))
    cap.set(cv2.CAP_PROP_POS_FRAMES, want[0])
    f = want[0]
    try:
        while f <= want[-1]:
            ok, fr = cap.read()
            if not ok:
                break
            if f in want:
                p = np.asarray(model.trunk(fr, np.asarray(boxes[f], float), K), float)    # ls, rs, lh, rh
                X = np.zeros((1, 17, 3))
                X[0, H_L_SH], X[0, H_R_SH], X[0, H_L_HIP], X[0, H_R_HIP] = p[0], p[1], p[2], p[3]
                rt = turns(X, pitch_deg, hand)[0]
                if np.isfinite(rt).all():
                    out[f] = tuple(float(v) for v in rt)
            f += 1
    finally:
        cap.release()
    return out


def trunk_metrabs(model, clip: Path, boxes: list, frame_shape, H: np.ndarray, pitch_deg: float, hand: str,
                  loaded_frame: int | None, half_window: int) -> tuple[dict, dict]:
    """(the stroke's trunk metrics at the loaded frame, the per-frame readings), as trunk() gives them, from MeTRAbs on
    the frames around the loaded one (84 ms each on a T4: only those the metrics read)."""
    from .racket_orientation import trunk_at

    if loaded_frame is None:
        return {}, {}
    rot = metrabs_rotations(model, clip, boxes, range(loaded_frame - half_window, loaded_frame + half_window + 1),
                            intrinsics(H, frame_shape), pitch_deg, hand)
    m = trunk_at(rot, loaded_frame, half_window)
    if m:
        m["trunk3d_model"] = "metrabs"
    return m, rot
