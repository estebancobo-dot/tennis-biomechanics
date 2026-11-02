"""F3ED hit spotter (candidate; scripts/export_f3ed.py), run as F3Set does at test time and as the reference project
does (dsa/gpu/strokes.py): each frame resized to 224 px high and centre-cropped to 224x224 (the model sees the
centre 56 % of a 16:9 frame), every STEP-th frame of 25-30 fps video (at 50-60 fps every 2*STEP-th, since the model
loses most hits at those rates), in clips of 96 samples that overlap by half; the scores of each sample are the
mean over the clips that cover it.

A hit is a sample whose "hit" score wins and whose "no hit" score is the lowest within ±2 samples (F3Set's NMS).
Its side, shot and hand come from the 29 element scores, as in the reference project's decoding. The output has
the fields of tennisbio.spotting.decode ({t, side, kind, score}), so tennisbio.spotting.evaluate measures both."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

CLIP, STEP, CROP = 96, 2, 224
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
ELEMENTS = ("near far deuce middle ad serve return stroke fh bh gs slice volley smash drop lob "
            "T B W CC DL DM II IO approach in winner forced-err unforced-err").split()
GROUPS = {"side": (0, 2), "position": (2, 5), "shot": (5, 8), "hand": (8, 10), "technique": (10, 16),
          "direction": (16, 24), "outcome": (25, 29)}
NMS = 5


def sample_step(fps: float) -> int:
    """Frames between two samples: STEP at 25-30 fps, twice that at 50-60 fps."""
    return STEP * max(1, int(round(float(fps) / 30.0)))


def crop(bgr: np.ndarray) -> np.ndarray:
    """224 px high, centre 224x224, RGB uint8."""
    h, w = bgr.shape[:2]
    small = cv2.resize(bgr, (max(CROP, w * CROP // h), CROP), interpolation=cv2.INTER_AREA)
    x0 = (small.shape[1] - CROP) // 2
    return np.ascontiguousarray(small[:, x0:x0 + CROP, ::-1])


def normalise(rgb: np.ndarray) -> np.ndarray:
    return ((rgb.astype(np.float32) / 255.0 - MEAN) / STD).transpose(2, 0, 1)


def kind_of(el: np.ndarray) -> str:
    """serve / forehand / backhand / other (volleys, smashes) from one sample's element scores."""
    pick = lambda g: ELEMENTS[GROUPS[g][0] + int(np.argmax(el[GROUPS[g][0]:GROUPS[g][1]]))]
    if pick("shot") == "serve":
        return "serve"
    if pick("technique") in ("volley", "smash"):
        return "other"
    return "forehand" if pick("hand") == "fh" else "backhand"


def decode(hit: np.ndarray, elements: np.ndarray, step: int, fps: float) -> list[dict]:
    """Hits from per-sample scores: hit (S, 2) softmax, elements (S, 29); sample i is frame i * step."""
    out = []
    bg = hit[:, 0]
    for i in range(len(hit)):
        w = bg[max(i - NMS // 2, 0):i + NMS // 2 + 1]
        if hit[i].argmax() != 1 or bg[i] != w.min():
            continue
        el = elements[i]
        side = ELEMENTS[int(np.argmax(el[0:2]))]
        out.append({"t": round(i * step / fps, 3), "side": side, "kind": kind_of(el), "score": round(float(hit[i, 1]), 3)})
    return out


class F3edSpotter:
    def __init__(self, onnx_path: str | Path, device: str = "cpu"):
        from ..pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)
        self.name = self.sess.get_inputs()[0].name

    def _run(self, clip: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        x = np.stack([normalise(c) for c in clip])
        if len(x) < CLIP:              # F3Set pads the end of a video with zeros (after normalising)
            x = np.concatenate([x, np.zeros((CLIP - len(x),) + x.shape[1:], np.float32)])
        hit, el = self.sess.run(None, {self.name: x[None].astype(np.float32)})
        return hit[0], el[0]

    def scores(self, frames, fps: float) -> tuple[np.ndarray, np.ndarray, int]:
        """(hit (S, 2), elements (S, 29), step) for every step-th BGR frame of `frames` (any iterable; at most
        one clip of crops is held in memory)."""
        step = sample_step(fps)
        hit_sum, el_sum, cnt = [], [], []
        buf: list[np.ndarray] = []
        start = 0                                  # sample index of buf[0]

        def add(s0: int, h: np.ndarray, e: np.ndarray, n: int):
            while len(cnt) < s0 + n:
                hit_sum.append(np.zeros(2, np.float32)); el_sum.append(np.zeros(29, np.float32)); cnt.append(0)
            for j in range(n):
                hit_sum[s0 + j] += h[j]; el_sum[s0 + j] += e[j]; cnt[s0 + j] += 1
        for k, f in enumerate(frames):
            if k % step:
                continue
            buf.append(crop(f))
            if len(buf) == CLIP:
                h, e = self._run(buf)
                add(start, h, e, CLIP)
                buf = buf[CLIP // 2:]
                start += CLIP // 2
        if buf and (start == 0 or len(buf) > CLIP // 2):
            h, e = self._run(buf)
            add(start, h, e, len(buf))
        if not cnt:
            return np.zeros((0, 2)), np.zeros((0, 29)), step
        c = np.maximum(np.array(cnt, np.float32), 1)[:, None]
        return np.array(hit_sum) / c, np.array(el_sum) / c, step

    def spot(self, frames, fps: float) -> list[dict]:
        hit, el, step = self.scores(frames, fps)
        return decode(hit, el, step, fps)
