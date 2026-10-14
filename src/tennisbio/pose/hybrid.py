"""Hybrid pose for the fine pass: YOLO11m-pose finds every person, RTMPose-x Halpe26 refines the big ones.

The cascade professional systems use, measured on the PC (docs/estado_del_arte.md, "Resultado de la
prueba de modelos"; trial class pose.variants._Hybrid): the same strokes found, keypoint jitter −35 %,
feet seen in 99.7 % of the frames, ~2× the cost of YOLO in half precision. YOLO keeps the config's
precision (fp16 on the iGPU); RTMPose stays in full precision (in half precision it is slower on
DirectML).

Off by default: `fine_pass.pose_model: yolo` (config/default.yaml). With `hybrid`, `extract_fine` writes
the same window cache as pose.yolo.extract plus `feet` / `feet_confs` (the 6 Halpe26 foot points:
big toes, small toes, heels, in skeleton.FOOT_NAMES order), so the stroke pipeline reads it unchanged.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from ..pipeline import savez_atomic
from .yolo import _fps, _objects, appearance  # noqa: F401  (_fps: re-exported for the fine pass)

POSE_MODELS = ("yolo", "hybrid")
FOOT_SLICE = slice(20, 26)          # Halpe26: left/right big toe, left/right small toe, left/right heel
MIN_REL_HEIGHT = 0.6                # RTMPose only on people at least this tall relative to the tallest
MATCH_IOU = 0.3                     # a caller's target box picks the detection it overlaps this much


def _empty(n: int = 0):
    return (np.zeros((n, 4), np.float32), np.zeros((n, 17, 2), np.float32), np.zeros((n, 17), np.float32),
            np.zeros((n, 6, 2), np.float32), np.zeros((n, 6), np.float32))


def _iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU matrix (len(a), len(b)) of xyxy boxes."""
    a, b = np.asarray(a, float).reshape(-1, 4), np.asarray(b, float).reshape(-1, 4)
    x0 = np.maximum(a[:, None, 0], b[None, :, 0])
    y0 = np.maximum(a[:, None, 1], b[None, :, 1])
    x1 = np.minimum(a[:, None, 2], b[None, :, 2])
    y1 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area = lambda z: np.clip(z[:, 2] - z[:, 0], 0, None) * np.clip(z[:, 3] - z[:, 1], 0, None)
    return inter / np.maximum(area(a)[:, None] + area(b)[None, :] - inter, 1e-9)


class HybridPose:
    """predict(img, conf) → boxes (N, 4) xyxy, keypoints (N, 17, 2), keypoint conf (N, 17), as
    pose.backend.PoseModel; predict_feet adds the 6 foot points (N, 6, 2) and their conf (N, 6)
    (zero confidence for the people RTMPose did not run on: YOLO has no feet).

    yolo: a PoseModel (or anything with predict(img, conf) and, optionally, prepare(img)).
    rtm: callable (img, boxes (M, 4)) → Halpe26 keypoints (M, 26, 2), scores (M, 26)
    (pose.estimator.PoseEstimator)."""

    def __init__(self, yolo, rtm, min_rel_height: float = MIN_REL_HEIGHT):
        self.yolo, self.rtm, self.min_rel_height = yolo, rtm, float(min_rel_height)

    @property
    def backend(self) -> str:
        return f"hybrid({getattr(self.yolo, 'backend', 'yolo')}+rtmpose-x)"

    def prepare(self, img: np.ndarray):
        """YOLO's input for img, computable ahead in a reader thread (PoseModel.prepare)."""
        prep = getattr(self.yolo, "prepare", None)
        return prep(img) if prep is not None else None

    def refined(self, boxes: np.ndarray, targets=None) -> np.ndarray:
        """Indices of the detections RTMPose runs on: the target-sized people (height ≥ min_rel_height
        × the tallest), or, with targets (M, 4) given by the caller (e.g. the tracked player's box),
        only the detection that best overlaps each target (IoU ≥ MATCH_IOU)."""
        boxes = np.asarray(boxes, float).reshape(-1, 4)
        if not len(boxes):
            return np.zeros(0, int)
        if targets is not None:
            t = np.asarray(targets, float).reshape(-1, 4)
            if not len(t):
                return np.zeros(0, int)
            iou = _iou(t, boxes)
            best = iou.argmax(1)
            return np.unique(best[iou[np.arange(len(t)), best] >= MATCH_IOU])
        h = boxes[:, 3] - boxes[:, 1]
        return np.flatnonzero(h >= self.min_rel_height * h.max())

    def predict_feet(self, img: np.ndarray, conf: float = 0.3, targets=None, prepared=None):
        """boxes, kps (17), confs (17), feet (N, 6, 2), feet_confs (N, 6)."""
        if prepared is not None:
            b, k, c = self.yolo.predict(img, conf=conf, prepared=prepared)
        else:
            b, k, c = self.yolo.predict(img, conf=conf)
        b = np.asarray(b, np.float32).reshape(-1, 4)
        if not len(b):
            return _empty()
        k, c = np.array(k, np.float32).reshape(-1, 17, 2), np.array(c, np.float32).reshape(-1, 17)
        fk, fc = np.zeros((len(b), 6, 2), np.float32), np.zeros((len(b), 6), np.float32)
        big = self.refined(b, targets)
        if len(big):
            rk, rc = self.rtm(img, b[big])
            rk, rc = np.asarray(rk, np.float32).reshape(-1, 26, 2), np.asarray(rc, np.float32).reshape(-1, 26)
            k[big], c[big] = rk[:, :17], rc[:, :17]
            fk[big], fc[big] = rk[:, FOOT_SLICE], rc[:, FOOT_SLICE]
        return b, k, c, fk, fc

    def predict(self, img: np.ndarray, conf: float = 0.3, targets=None, prepared=None):
        b, k, c, _, _ = self.predict_feet(img, conf, targets, prepared)
        return b, k, c


@lru_cache(maxsize=4)
def _rtmpose(url: str, input_size: tuple, device: str):
    """RTMPose-x Halpe26 in full precision (fp16 is slower on DirectML), loaded once per device."""
    from .estimator import PoseEstimator

    return PoseEstimator(url, input_size, device)


@lru_cache(maxsize=4)
def _cached(yolo_name: str, imgsz: int, device: str, url: str, input_size: tuple, min_rel: float) -> HybridPose:
    from .backend import pose_model

    return HybridPose(pose_model(yolo_name, imgsz, device), _rtmpose(url, input_size, device), min_rel)


def hybrid_model(yolo_name: str = "yolo11m-pose", imgsz: int = 960, device: str | None = None,
                 cfg: dict | None = None) -> HybridPose:
    """Loaded once per (YOLO model, size, device) and reused, like backend.pose_model: the YOLO part
    follows the config's precision (backend.set_device); RTMPose is the config's 'performance' pose."""
    from .backend import DEFAULT_DEVICE

    if cfg is None:
        from ..config import load_config
        cfg = load_config()
    pose = cfg["models"]["poses"][(cfg.get("fine_pass") or {}).get("pose", "performance")]
    return _cached(Path(str(yolo_name)).stem, int(imgsz), device or DEFAULT_DEVICE, pose["url"],
                   tuple(int(v) for v in pose["input_size"]), MIN_REL_HEIGHT)


def fine_pose_model(cfg: dict | None = None) -> str:
    """`fine_pass.pose_model` from the config: 'yolo' (default) or 'hybrid'. Anything else → 'yolo'
    with a warning (the analysis never stops for a config typo)."""
    if cfg is None:
        from ..config import load_config
        cfg = load_config()
    m = str((cfg.get("fine_pass") or {}).get("pose_model", "yolo") or "yolo").strip().lower()
    if m not in POSE_MODELS:
        print(f"AVISO: fine_pass.pose_model '{m}' no existe (yolo o hybrid); se usa yolo")
        return "yolo"
    return m


def pose_cache_tag(cfg: dict) -> list:
    """What to add to the fine pass's window cache key (stages: `ph`): nothing with the default, so the
    caches already computed with YOLO stay valid; ['hybrid'] otherwise, so YOLO caches are not reused."""
    return [] if fine_pose_model(cfg) == "yolo" else ["hybrid"]


def extract_hybrid(video: str | Path, out: str | Path, pose_model="yolo11m-pose.pt", imgsz=960, every=1,
                   progress=True, roi: tuple | None = None, frames=None, model: HybridPose | None = None,
                   cfg: dict | None = None) -> Path:
    """pose.yolo.extract with the hybrid model: the same .npz (fps, n, boxes, kps, confs, feats) plus
    feet (per frame (N, 6, 2)) and feet_confs (per frame (N, 6)), all in full-frame coordinates."""
    from ..io.video import capture_frames

    pose = model or hybrid_model(pose_model, imgsz, cfg=cfg)
    fps = _fps(video) / every
    boxes, kps, confs, feats, feet, feet_c = [], [], [], [], [], []
    i = 0
    for frame in (capture_frames(video) if frames is None else frames):
        if i % every:
            i += 1
            continue
        ox = oy = 0
        src = frame
        if roi is not None:
            x0, y0, x1, y1 = (int(v) for v in roi)
            src, ox, oy = frame[y0:y1, x0:x1], x0, y0
        b, k, c, fk, fc = pose.predict_feet(src, conf=0.3)
        if len(b):
            b, k, fk = b + [ox, oy, ox, oy], k + [ox, oy], fk + [ox, oy]
        boxes.append(b.astype(np.float32))
        kps.append(k.astype(np.float32))
        confs.append(c.astype(np.float32))
        feet.append(fk.astype(np.float32))
        feet_c.append(fc.astype(np.float32))
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
        i += 1
        if progress and len(boxes) % 100 == 0:
            print(f"{len(boxes)} frames", flush=True)
    out = Path(out)
    savez_atomic(out, fps=fps, n=len(boxes), boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                 feats=_objects(feats), feet=_objects(feet), feet_confs=_objects(feet_c))
    return out


def extract_fine(video: str | Path, out: str | Path, pose_model="yolo11m-pose.pt", imgsz=960, every=1,
                 progress=True, roi: tuple | None = None, frames=None, cfg: dict | None = None) -> Path:
    """The fine pass's pose extraction, chosen by `fine_pass.pose_model`: pose.yolo.extract (default,
    exactly as before) or extract_hybrid. Same signature as pose.yolo.extract."""
    if fine_pose_model(cfg) == "hybrid":
        return extract_hybrid(video, out, pose_model, imgsz, every, progress, roi, frames, cfg=cfg)
    from .yolo import extract

    return extract(video, out, pose_model, imgsz, every, progress, roi, frames)
