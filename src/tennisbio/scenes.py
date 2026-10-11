"""Shot boundaries (hard cuts and dissolves) and main-camera detection for the cheap pass.

Works on small frames (e.g. 160 px wide, a few fps). The main broadcast camera shows a large
area of court surface; close-ups, crowd shots and most replays do not. The court colour is
learned from the video itself (the most frequent hue among the frames), so blue hard courts,
green grass and clay all work.
"""
from dataclasses import dataclass

import cv2
import numpy as np

H_BINS, S_BINS = 18, 4


def frame_features(frame: np.ndarray):
    """(normalised hue/saturation histogram, hue histogram of saturated pixels) of a small frame."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hs = cv2.calcHist([hsv], [0, 1], None, [H_BINS, S_BINS], [0, 180, 0, 256]).ravel()
    sat = hsv[..., 1] > 60
    hue = np.bincount((hsv[..., 0][sat].astype(np.int32) * H_BINS // 180).ravel(), minlength=H_BINS).astype(float)
    return hs / (hs.sum() + 1e-9), hue / max(1.0, float(hsv.shape[0] * hsv.shape[1]))


def _dist(a, b):
    """1 - Bhattacharyya coefficient (0 = identical histograms)."""
    return 1.0 - float(np.sum(np.sqrt(a * b)))


@dataclass
class Shot:
    start: int
    end: int                 # exclusive
    main_camera: bool
    court_fraction: float


def detect_boundaries(hists: np.ndarray, cut_thr=0.35, dissolve_thr=0.45, window=6) -> list[int]:
    """Frame indices where a new shot starts: hard cuts (big jump between consecutive frames)
    and dissolves (frames ±window apart differ a lot while consecutive frames change little)."""
    T = len(hists)
    d1 = np.array([_dist(hists[t - 1], hists[t]) for t in range(1, T)])
    cuts = [t for t in range(1, T) if d1[t - 1] > cut_thr]
    dissolves = []
    for t in range(window, T - window):
        far = _dist(hists[t - window], hists[t + window])
        local = d1[t - window:t + window].max() if len(d1) else 0
        if far > dissolve_thr and local < cut_thr:
            dissolves.append(t)
    # merge runs of dissolve frames into their centre, drop those next to a hard cut
    merged, run = [], []
    for t in dissolves:
        if run and t - run[-1] > 1:
            merged.append(run[len(run) // 2]); run = []
        run.append(t)
    if run:
        merged.append(run[len(run) // 2])
    merged = [t for t in merged if all(abs(t - c) > window for c in cuts)]
    return sorted(set(cuts + merged))


def court_hue(hues: np.ndarray) -> int:
    """Dominant saturated hue bin over the whole video (the playing surface)."""
    return int(np.argmax(hues.sum(0)))


def segment_shots(hists: np.ndarray, hues: np.ndarray, min_court=0.25, **kw) -> list[Shot]:
    """Split into shots and mark those that look like the main camera (much visible court)."""
    b = [0] + detect_boundaries(hists, **kw) + [len(hists)]
    ch = court_hue(hues)
    court = hues[:, max(0, ch - 1):ch + 2].sum(1)          # the court hue ± one bin
    shots = []
    for s, e in zip(b[:-1], b[1:]):
        if e > s:
            cf = float(np.median(court[s:e]))
            shots.append(Shot(s, e, cf >= min_court, cf))
    return shots


def analyse_video(frames) -> tuple[list[Shot], np.ndarray]:
    """Shots from an iterable of small BGR frames; also returns the per-frame main-camera mask."""
    hs, hu = zip(*(frame_features(f) for f in frames))
    shots = segment_shots(np.array(hs), np.array(hu))
    mask = np.zeros(len(hs), bool)
    for sh in shots:
        mask[sh.start:sh.end] = sh.main_camera
    return shots, mask
