"""MotionAGFormer 2D→3D lifter (candidate, request #203; scripts/export_motionagformer.py), against RTMW3D
(tennisbio.pose.wholebody3d) for the trunk rotation.

Input: one person's COCO-17 2D keypoints over consecutive frames (the 2D pose the fine pass already has) and their
scores. As the repository's demo (`demo/vis.py`, `demo/lib/preprocess.py`): COCO → the 17 Human3.6M joints (pelvis,
spine, thorax, head made from the COCO points), x and y normalised by the image width (x/w·2 − 1, y/w·2 − h/w), the
score as third channel; sequences cut into the model's clip length (the last, or a shorter sequence, resampled to it
by repeating frames); the clip and its left-right flip averaged; the pelvis set to 0.

Output: (T, 17, 3) relative to the pelvis in the camera's axes (x right, y down, z away from the camera), one scale
for the three axes (the image width's), so the direction of a segment, hence a turn about the vertical, needs no
metric scale."""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Human3.6M joints (the demo's order): 0 pelvis, 1 right hip, 4 left hip, 11 left shoulder, 14 right shoulder
H36M_R_HIP, H36M_L_HIP, H36M_L_SH, H36M_R_SH = 1, 4, 11, 14
H36M_FROM_COCO = [9, 11, 14, 12, 15, 13, 16, 4, 1, 5, 2, 6, 3]     # demo/lib/preprocess.py h36m_coco_order
COCO_TO_H36M = [0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]      # coco_order
LEFT, RIGHT = [1, 2, 3, 14, 15, 16], [4, 5, 6, 11, 12, 13]          # flip_data: the joint pairs swapped by a mirror


def coco_to_h36m(kp: np.ndarray, sc: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(T, 17, 2) COCO keypoints and (T, 17) scores → Human3.6M (demo/lib/preprocess.py coco_h36m and
    h36m_coco_format)."""
    kp = np.asarray(kp, np.float32)
    sc = np.asarray(sc, np.float32)
    out = np.zeros_like(kp)
    htps = np.zeros((len(kp), 4, 2), np.float32)                 # head, thorax, pelvis, spine
    htps[:, 0, 0] = kp[:, 1:5, 0].mean(1)
    htps[:, 0, 1] = kp[:, 1:3, 1].sum(1) - kp[:, 0, 1]
    htps[:, 1] = kp[:, 5:7].mean(1)
    htps[:, 1] += (kp[:, 0] - htps[:, 1]) / 3
    htps[:, 2] = kp[:, 11:13].mean(1)
    htps[:, 3] = kp[:, [5, 6, 11, 12]].mean(1)
    out[:, [10, 8, 0, 7]] = htps
    out[:, H36M_FROM_COCO] = kp[:, COCO_TO_H36M]
    out[:, 9] -= (out[:, 9] - kp[:, 5:7].mean(1)) / 4
    out[:, 7, 0] += 2 * (out[:, 7, 0] - out[:, [0, 8], 0].mean(1))
    out[:, 8, 1] -= (kp[:, 1:3, 1].mean(1) - kp[:, 0, 1]) * 2 / 3
    s = np.zeros_like(sc)
    s[:, H36M_FROM_COCO] = sc[:, COCO_TO_H36M]
    s[:, 0] = sc[:, [11, 12]].mean(1)
    s[:, 8] = sc[:, [5, 6]].mean(1)
    s[:, 7] = s[:, [0, 8]].mean(1)
    s[:, 10] = sc[:, [1, 2, 3, 4]].mean(1)
    return out, s


def normalise(kp: np.ndarray, w: float, h: float) -> np.ndarray:
    """demo/lib/utils.py normalize_screen_coordinates on (…, 2) image px."""
    return np.asarray(kp, np.float32) / w * 2 - np.array([1, h / w], np.float32)


def flip(x: np.ndarray) -> np.ndarray:
    """demo flip_data: x mirrored and the left/right joints swapped."""
    y = np.array(x, copy=True)
    y[..., 0] *= -1
    y[..., LEFT + RIGHT, :] = y[..., RIGHT + LEFT, :]
    return y


def clips(n: int, length: int) -> list[np.ndarray]:
    """Frame indices of each clip of `length` covering a sequence of n frames (demo turn_into_clips: consecutive
    clips; a sequence or last clip shorter than `length` resampled to it, frame i repeated as floor(linspace))."""
    out = []
    for a in range(0, max(n, 1), length):
        m = min(length, n - a)
        idx = np.arange(a, a + m) if m == length else a + np.clip(np.floor(np.linspace(0, m, length, endpoint=False)),
                                                                   0, m - 1).astype(int)
        out.append(idx)
    return out


def line_yaw_world(p: np.ndarray, a: int, b: int, r_c2w: np.ndarray) -> np.ndarray:
    """Direction about the world vertical (deg, atan2 of the world y and x of b − a) of the segment a→b of camera-axes
    3D points (…, J, 3), with r_c2w the camera-to-world rotation of a world whose z is up."""
    d = (np.asarray(p, float)[..., b, :] - np.asarray(p, float)[..., a, :]) @ np.asarray(r_c2w, float).T
    return np.degrees(np.arctan2(d[..., 1], d[..., 0]))


class MotionAGFormerLifter:
    def __init__(self, onnx_path: str | Path, device: str = "cpu"):
        from ..pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)
        shape = self.sess.get_inputs()[0].shape
        self.length = int(shape[1])
        self.name = self.sess.get_inputs()[0].name

    def lift(self, kp: np.ndarray, sc: np.ndarray, w: float, h: float) -> np.ndarray:
        """(T, 17, 3) Human3.6M joints relative to the pelvis, camera axes, from (T, 17, 2) COCO image px and (T, 17)
        scores of one person in consecutive frames of a w×h video. Frames with no 2D (NaN) are filled from the nearest
        frames that have it before lifting (the output at those frames is a guess: callers skip them)."""
        kp = np.array(kp, np.float32)
        sc = np.array(sc, np.float32)
        miss = ~np.isfinite(kp).all((1, 2))
        if miss.all():
            return np.full((len(kp), 17, 3), np.nan, np.float32)
        if miss.any():
            have = np.flatnonzero(~miss)
            near = have[np.clip(np.searchsorted(have, np.arange(len(kp))), 0, len(have) - 1)]
            kp[miss], sc[miss] = kp[near[miss]], 0.0
        k, s = coco_to_h36m(kp, sc)
        x = np.concatenate([normalise(k, w, h), s[..., None]], -1)
        out = np.full((len(kp), 17, 3), np.nan, np.float32)
        for idx in clips(len(kp), self.length):
            clip = x[idx]
            inp = np.stack([clip, flip(clip)]).astype(np.float32)
            y = np.asarray(self.sess.run(None, {self.name: inp})[0], np.float32)
            y = (y[0] + flip(y[1])) / 2
            y[:, 0] = 0                                       # pelvis at 0, as the demo (output_3D[:, :, 0, :] = 0)
            first = np.unique(idx, return_index=True)[1]       # each frame once: its first place in the clip
            out[idx[first]] = y[first]
        return out
