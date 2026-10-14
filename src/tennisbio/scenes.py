"""Shot boundaries (hard cuts and dissolves) and main-camera detection for the cheap pass.

Cuts come from TransNetV2 (models/transnetv2.onnx, made by scripts/export_transnetv2.py) when the
model is there: it looks at 48×27 frames at ~25 fps and finds the cuts between shots of similar
colours that the histograms miss (US Open: blue court, blue/green close-ups and side cameras).
Dissolves are still taken from the histograms as well. Without the model, or if it fails, the
histograms alone decide, as before.

Main camera: on small frames (e.g. 160 px wide, a few fps). The main broadcast camera shows a large
area of court surface; close-ups, crowd shots and most replays do not. The court colour is
learned from the video itself (the most frequent hue among the frames), so blue hard courts,
green grass and clay all work.
"""
from dataclasses import dataclass
from typing import Callable, Iterable

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


def _cuts_and_dissolves(hists: np.ndarray, cut_thr=0.35, dissolve_thr=0.45, window=6) -> tuple[list[int], list[int]]:
    """(hard cuts, dissolves) from the histograms: a hard cut is a big jump between consecutive
    frames; a dissolve, frames ±window apart that differ a lot while consecutive frames change
    little (each run of such frames is reduced to its centre)."""
    T = len(hists)
    d1 = np.array([_dist(hists[t - 1], hists[t]) for t in range(1, T)])
    cuts = [t for t in range(1, T) if d1[t - 1] > cut_thr]
    dissolves = []
    for t in range(window, T - window):
        far = _dist(hists[t - window], hists[t + window])
        local = d1[t - window:t + window].max() if len(d1) else 0
        if far > dissolve_thr and local < cut_thr:
            dissolves.append(t)
    merged, run = [], []
    for t in dissolves:
        if run and t - run[-1] > 1:
            merged.append(run[len(run) // 2]); run = []
        run.append(t)
    if run:
        merged.append(run[len(run) // 2])
    return cuts, merged


def _merge(cuts: list[int], dissolves: list[int], window=6) -> list[int]:
    """Cuts plus the dissolves that are not next to a cut (the same transition found twice)."""
    return sorted(set(cuts) | {t for t in dissolves if all(abs(t - c) > window for c in cuts)})


def detect_boundaries(hists: np.ndarray, cut_thr=0.35, dissolve_thr=0.45, window=6) -> list[int]:
    """Frame indices where a new shot starts: hard cuts (big jump between consecutive frames)
    and dissolves (frames ±window apart differ a lot while consecutive frames change little)."""
    cuts, dissolves = _cuts_and_dissolves(hists, cut_thr, dissolve_thr, window)
    return _merge(cuts, dissolves, window)


# --- TransNetV2 ---------------------------------------------------------------------------------
# Reference inference (Souček & Lokoč 2020): windows of 100 frames advancing 50, of which the
# central 50 are kept (25 frames of context on each side); the video is padded with copies of its
# first and last frames. A frame is a transition when its probability exceeds 0.5.
TN_WINDOW, TN_STEP, TN_CONTEXT = 100, 50, 25
TN_SIZE = (48, 27)                 # width, height
TN_FPS = 25.0


def tn_frame(frame_bgr: np.ndarray) -> np.ndarray:
    """A decoded BGR frame as TransNetV2 input: RGB 48×27 (area average, as a direct ffmpeg scale)."""
    if frame_bgr.shape[:2] != TN_SIZE[::-1]:
        frame_bgr = cv2.resize(frame_bgr, TN_SIZE, interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(frame_bgr[..., ::-1])


class CutModel:
    """TransNetV2 (ONNX) on the configured device. If the device fails while running, the session
    is made again on the CPU and the window is repeated there."""

    batch = 4

    def __init__(self, path, device: str = "cpu"):
        from .pose.estimator import _ort_session

        self.path, self._make = str(path), _ort_session
        self.session = _ort_session(self.path, device)

    def __call__(self, windows: np.ndarray) -> np.ndarray:
        """uint8 [n, 100, 27, 48, 3] → probability of a transition at each frame [n, 100]."""
        try:
            return self.session.run(None, {"frames": windows})[0]
        except Exception as e:                     # noqa: BLE001 — iGPU driver problems: CPU instead
            if self.session.get_providers() == ["CPUExecutionProvider"]:
                raise
            print(f"AVISO: la iGPU falló con TransNetV2 ({str(e)[:120]}); se sigue en la CPU")
            self.session = self._make(self.path, "cpu")
            return self.session.run(None, {"frames": windows})[0]


class CutStream:
    """Feeds frames one by one to TransNetV2 with the reference windowing, so a whole match never
    sits in memory. `run` maps uint8 windows [n, 100, 27, 48, 3] to probabilities [n, 100]. If it
    fails, `error` is set and the remaining frames are ignored (the caller falls back)."""

    def __init__(self, run: Callable[[np.ndarray], np.ndarray], batch: int = 4):
        self.run, self.batch = run, max(1, int(batch))
        self.buf: list[np.ndarray] = []
        self.pending: list[np.ndarray] = []
        self.out: list[np.ndarray] = []
        self.n = 0
        self.error: Exception | None = None

    def _flush(self):
        if self.pending and self.error is None:
            try:
                p = np.asarray(self.run(np.stack(self.pending)), np.float32).reshape(len(self.pending), TN_WINDOW)
                self.out.extend(p[:, TN_CONTEXT:TN_CONTEXT + TN_STEP])
            except Exception as e:                 # noqa: BLE001 — any failure → histogram fallback
                self.error = e
        self.pending = []

    def _windows(self):
        while len(self.buf) >= TN_WINDOW:
            self.pending.append(np.stack(self.buf[:TN_WINDOW]))
            del self.buf[:TN_STEP]
            if len(self.pending) >= self.batch:
                self._flush()

    def add(self, frame_rgb: np.ndarray):
        if self.error is not None:
            return
        if self.n == 0:
            self.buf.extend([frame_rgb] * TN_CONTEXT)
        self.buf.append(frame_rgb)
        self.n += 1
        self._windows()

    def finish(self) -> np.ndarray:
        """Probability of a transition at each frame added (empty if the model failed)."""
        if self.n and self.error is None:
            self.buf.extend([self.buf[-1]] * (TN_CONTEXT + TN_STEP - (self.n % TN_STEP or TN_STEP)))
            self._windows()
            self._flush()
        if self.error is not None or not self.n:
            return np.zeros(0, np.float32)
        return np.concatenate(self.out)[:self.n]


def cut_probabilities(frames_rgb: Iterable[np.ndarray], run, batch: int = 4) -> np.ndarray:
    """TransNetV2 probabilities for a sequence of 48×27 RGB frames (reference windowing)."""
    st = CutStream(run, batch)
    for f in frames_rgb:
        st.add(f)
    p = st.finish()
    if st.error is not None:
        raise st.error
    return p


def boundaries_from_probs(p: np.ndarray, thr: float = 0.5) -> list[int]:
    """Frames where a new shot starts: one per run of frames above the threshold, right after its
    most likely frame (TransNetV2 marks the last frame of the outgoing shot of a hard cut; in a
    dissolve the peak is near its middle)."""
    p = np.asarray(p, float)
    above = p > thr
    out, t = [], 0
    while t < len(p):
        if not above[t]:
            t += 1
            continue
        e = t
        while e + 1 < len(p) and above[e + 1]:
            e += 1
        b = t + int(np.argmax(p[t:e + 1])) + 1
        if b < len(p):
            out.append(b)
        t = e + 1
    return out


def court_hue(hues: np.ndarray) -> int:
    """Dominant saturated hue bin over the whole video (the playing surface)."""
    return int(np.argmax(hues.sum(0)))


def segment_shots(hists: np.ndarray, hues: np.ndarray, min_court=0.25, cuts: list[int] | None = None,
                  window=6, **kw) -> list[Shot]:
    """Split into shots and mark those that look like the main camera (much visible court).
    `cuts` (frame indices, e.g. from TransNetV2) replace the histogram hard cuts; the histogram
    dissolves are added in both cases."""
    hcuts, dissolves = _cuts_and_dissolves(hists, window=window, **kw)
    if cuts is not None:
        hcuts = [c for c in cuts if 0 < c < len(hists)]
    b = [0] + _merge(hcuts, dissolves, window) + [len(hists)]
    ch = court_hue(hues)
    court = hues[:, max(0, ch - 1):ch + 2].sum(1)          # the court hue ± one bin
    shots = []
    for s, e in zip(b[:-1], b[1:]):
        if e > s:
            cf = float(np.median(court[s:e]))
            shots.append(Shot(s, e, cf >= min_court, cf))
    return shots


def grid_index(k: int, fast_fps: float, fps: float) -> int:
    """Index, among frames decoded at fast_fps, of frame k of the analysis grid at fps (nearest)."""
    return int(np.floor(k * fast_fps / fps + 0.5))


def to_grid(cuts_fast: list[int], fast_fps: float, fps: float, n: int) -> list[int]:
    """Cuts found at fast_fps as indices of the fps grid: the first grid frame at or after the cut."""
    if not cuts_fast:
        return []
    src = np.array([grid_index(k, fast_fps, fps) for k in range(n)])
    return sorted({int(np.searchsorted(src, c)) for c in cuts_fast} - {0, n})


def analyse_video(frames, cut_model=None, fps: float | None = None, fast_fps: float | None = None,
                  threshold: float = 0.5, info: dict | None = None) -> tuple[list[Shot], np.ndarray]:
    """Shots from an iterable of small BGR frames; also returns the per-frame main-camera mask.

    Without `cut_model` the frames are the analysis grid itself (histograms only). With it, the
    frames come at `fast_fps` (~25, what TransNetV2 expects): every one goes to the model and the
    ones nearest to the `fps` grid give the histograms; shots are in frames of `fps`. A single
    decoding serves both. `info`, if given, receives how it went (detector, cuts, error)."""
    info = {} if info is None else info
    if cut_model is None:
        feats = [frame_features(f) for f in frames]
        hs, hu = [h for h, _ in feats], [u for _, u in feats]
        shots = segment_shots(np.array(hs), np.array(hu)) if hs else []
        info["detector"] = "histogram"
    else:
        stream = CutStream(cut_model, getattr(cut_model, "batch", 4))
        hs, hu, nxt = [], [], 0
        for i, f in enumerate(frames):
            stream.add(tn_frame(f))
            if i == grid_index(nxt, fast_fps, fps):
                h, u = frame_features(f)
                hs.append(h)
                hu.append(u)
                nxt += 1
        p = stream.finish()
        if stream.error is None and hs:
            cuts = to_grid(boundaries_from_probs(p, threshold), fast_fps, fps, len(hs))
            shots = segment_shots(np.array(hs), np.array(hu), cuts=cuts)
            info.update(detector="transnetv2", cuts=len(cuts))
        else:
            if stream.error is not None:
                info["error"] = f"{type(stream.error).__name__}: {stream.error}"[:300]
            shots = segment_shots(np.array(hs), np.array(hu)) if hs else []
            info["detector"] = "histogram"
    mask = np.zeros(len(hs), bool)
    for sh in shots:
        mask[sh.start:sh.end] = sh.main_camera
    return shots, mask
