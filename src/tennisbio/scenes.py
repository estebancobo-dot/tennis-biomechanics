"""Shot boundaries (hard cuts and dissolves) and main-camera detection for the cheap pass.

Cuts come from TransNetV2 (models/transnetv2.onnx, made by scripts/export_transnetv2.py) when the
model is there: it looks at 48×27 frames at ~25 fps and finds the cuts between shots of similar
colours that the histograms miss (US Open: blue court, blue/green close-ups and side cameras).
Dissolves are still taken from the histograms as well. Without the model, or if it fails, the
histograms alone decide, as before.

Main camera: on small frames (e.g. 160 px wide, a few fps). Colour alone is not enough: at the US
Open the blue wall behind the players has the court's colour, so close-ups, side views and the crowd
in front of it passed for the main camera (30 of 35 min, of which the court was found in 9.5). The
main camera is therefore confirmed by the court's lines, seen from behind (`court_line_evidence`):
two long sidelines converging upwards with a line across them (baseline, service line). A shot is
main camera when enough of its frames show that, or when it looks like (tiny colour thumbnail) a
view confirmed that way elsewhere in the video (lines hidden by a shadow, faint lines). If the lines
are not seen in a broadcast at all (a low camera, very faint lines) the colour rule decides, as
before: real play must never be dropped (the court stage is the final filter).
The court colour is learned from the video itself (the most frequent hue among the frames), so blue
hard courts, green grass and clay all work.
"""
import math
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
    court_lines: float = 0.0     # share of its frames with the court's lines seen from behind
    main_view: float = 0.0       # share of its frames that look like a view confirmed by the lines
    #                              (only computed for shots the lines do not confirm themselves)


# --- main camera from the court's lines -----------------------------------------------------------
_K3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
LINE_RIDGE = 12            # min top-hat of the darkest channel for a line pixel (white on any surface)
VIEW_TOL = 14.0            # mean abs difference (0-255) of the 16×9 thumbnails of one camera view
THUMB = (16, 9)
MAX_CLUTTER = 0.28         # max share of bright thin pixels on the court between the sidelines
#                            (main camera ≤ 0.22 over 41 broadcasts of RacketVision; crowd ≥ 0.31)


def _line_segments(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(straight bright thin segments [n, 4], mask of bright thin pixels) of a small BGR frame. Court
    lines are white: the darkest channel (min of B, G, R) is high on them and low on any coloured
    surface (blue, green, clay), so its white top-hat isolates them even when they are thinner than
    a pixel at 160 px."""
    m = cv2.min(cv2.min(frame[..., 0], frame[..., 1]), frame[..., 2])      # 20× faster than numpy's min
    ridge = cv2.morphologyEx(m, cv2.MORPH_TOPHAT, _K3)
    mask = (ridge > LINE_RIDGE).astype(np.uint8) * 255
    w = frame.shape[1]
    seg = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=12, minLineLength=max(8, int(0.12 * w)), maxLineGap=2)
    return (np.zeros((0, 4)) if seg is None else seg.reshape(-1, 4).astype(float)), mask


def court_line_evidence(frame: np.ndarray) -> int:
    """How much of a court seen from behind a small frame shows: 2 = two long sidelines converging
    upwards (left one '/', right one '\\') and a line across them covering half the gap between them
    (baseline or service line); 1 = only the converging sidelines; 0 = neither. Close-ups, the crowd,
    the wall behind the players and side views give 0 (their straight segments are letters, rails,
    the line on the floor); a crowd seen from far may give 1, almost never 2."""
    w = frame.shape[1]
    left, right, across = [], [], []
    segs, mask = _line_segments(frame)
    if len(segs) > 60:                                   # noise (crowd): keep the longest ones
        segs = segs[np.argsort(-np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1]))[:60]]
    for x1, y1, x2, y2 in segs:
        if y1 > y2:
            x1, y1, x2, y2 = x2, y2, x1, y1              # (x1, y1) = upper end
        length = math.hypot(x2 - x1, y2 - y1)
        angle = math.degrees(math.atan2(y2 - y1, abs(x2 - x1)))      # 0 horizontal, 90 vertical
        if angle < 8 and length >= 0.2 * w:
            across.append((x1, y1, x2, y2))
        elif 15 <= angle <= 80 and length >= 0.12 * w:
            (left if x1 > x2 else right).append((x1, y1, x2, y2))

    def x_at(s, y):
        return s[0] + (s[2] - s[0]) * (y - s[1]) / ((s[3] - s[1]) or 1e-9)

    best = 0
    for a in left:
        for b in right:
            y_top, y_bot = min(a[1], b[1]), max(a[3], b[3])
            top, bot = x_at(b, y_top) - x_at(a, y_top), x_at(b, y_bot) - x_at(a, y_bot)
            if not (bot > top > 0 and bot > 0.25 * w):
                continue
            # the court between them is a flat surface: few bright thin pixels besides its lines
            # (a crowd seen from far is full of them)
            poly = np.array([[x_at(a, y_top), y_top], [x_at(b, y_top), y_top],
                             [x_at(b, y_bot), y_bot], [x_at(a, y_bot), y_bot]], np.int32)
            inside = np.zeros_like(mask)
            cv2.fillPoly(inside, [poly], 255)
            n_in = cv2.countNonZero(inside)
            if n_in == 0 or cv2.countNonZero(cv2.bitwise_and(mask, inside)) > MAX_CLUTTER * n_in:
                continue
            best = 1
            for h in across:
                y = (h[1] + h[3]) / 2
                lo, hi = x_at(a, y), x_at(b, y)
                if hi > lo and (min(max(h[0], h[2]), hi) - max(min(h[0], h[2]), lo)) >= 0.5 * (hi - lo):
                    return 2
    return best


def view_thumb(frame: np.ndarray) -> np.ndarray:
    """16×9 colour thumbnail (uint8): the layout of a camera view (players and graphics are tiny)."""
    return cv2.resize(frame, THUMB, interpolation=cv2.INTER_AREA)


def _view_dist(th: np.ndarray, refs: np.ndarray, chunk: int = 64) -> np.ndarray:
    """Distance of each thumbnail to the nearest reference view (in chunks: a long shot × 256 views
    would not fit in memory at once)."""
    out = np.empty(len(th), np.float32)
    for i in range(0, len(th), chunk):
        a = th[i:i + chunk].astype(np.float32)
        out[i:i + chunk] = np.abs(a[:, None] - refs[None]).mean(axis=(2, 3, 4)).min(axis=1)
    return out


def _need(n: int, fps: float) -> int:
    """Frames of a shot that must show the evidence: a tenth of it, but never more than a second
    (a missed cut can glue a rally to a long close-up) and at least two (one frame can be noise)."""
    return min(n, max(2, min(math.ceil(0.1 * n), math.ceil(fps))))


def main_camera_from_lines(shots: list[Shot], evidence: np.ndarray, thumbs: np.ndarray, fps: float,
                           min_share: float = 0.1, view_tol: float = VIEW_TOL, max_refs: int = 256) -> dict:
    """Decide `main_camera` of each shot from the court's lines (in place); returns how it went.

    Confirmed: enough frames with evidence 2. Its view: the thumbnails of those frames (only of shots
    where at least 30 % of the frames confirm it, so a stray frame does not make a reference). A
    shot is also main camera when enough of its frames look like one of those views. If the shots
    found this way add up to less than `min_share` of what the colour rule gives, the lines are not
    usable in this broadcast and the colour rule stays (nothing changes)."""
    ev = np.asarray(evidence)
    th = np.asarray(thumbs, np.float32)
    colour = [s.main_camera for s in shots]
    strong = []
    for s in shots:
        n = s.end - s.start
        n2 = int((ev[s.start:s.end] == 2).sum())
        s.court_lines = round(n2 / max(n, 1), 3)
        strong.append(n > 0 and n2 >= _need(n, fps))
    R = np.zeros((max_refs,) + th.shape[1:], np.float32)
    k = 0
    for s, ok in zip(shots, strong):
        if not ok or s.court_lines < 0.3:
            continue
        for t in np.flatnonzero(ev[s.start:s.end] == 2) + s.start:
            if k >= max_refs:
                break
            if k == 0 or _view_dist(th[t:t + 1], R[:k])[0] > view_tol / 3:
                R[k] = th[t]
                k += 1
    main = []
    for s, ok in zip(shots, strong):
        n = s.end - s.start
        sim = int((_view_dist(th[s.start:s.end], R[:k]) <= view_tol).sum()) if k and n > 0 and not ok else 0
        s.main_view = round(sim / max(n, 1), 3)
        main.append(ok or (n > 0 and sim >= _need(n, fps)))
    by_lines = sum(s.end - s.start for s, m in zip(shots, main) if m)
    by_colour = sum(s.end - s.start for s, c in zip(shots, colour) if c)
    info = {"main_rule": "lines", "views": k, "main_frames_colour": by_colour, "main_frames_lines": by_lines}
    if by_lines == 0 or by_lines < min_share * by_colour:
        info["main_rule"] = "colour"              # lines not seen in this broadcast: keep the colour rule
        return info
    for s, m in zip(shots, main):
        s.main_camera = bool(m)
    return info


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
                  threshold: float = 0.5, info: dict | None = None, lines: bool = True) -> tuple[list[Shot], np.ndarray]:
    """Shots from an iterable of small BGR frames; also returns the per-frame main-camera mask.

    Without `cut_model` the frames are the analysis grid itself (histograms only). With it, the
    frames come at `fast_fps` (~25, what TransNetV2 expects): every one goes to the model and the
    ones nearest to the `fps` grid give the histograms; shots are in frames of `fps`. A single
    decoding serves both. Each grid frame also gives its court-line evidence and view thumbnail,
    which decide the main camera (`main_camera_from_lines`; `lines=False`: colour only, as in v2).
    `info`, if given, receives how it went (detector, cuts, error, main-camera rule)."""
    info = {} if info is None else info
    hs, hu, ev, th = [], [], [], []

    def grid_frame(f):
        h, u = frame_features(f)
        hs.append(h)
        hu.append(u)
        if lines:
            ev.append(court_line_evidence(f))
            th.append(view_thumb(f))

    if cut_model is None:
        for f in frames:
            grid_frame(f)
        shots = segment_shots(np.array(hs), np.array(hu)) if hs else []
        info["detector"] = "histogram"
    else:
        stream = CutStream(cut_model, getattr(cut_model, "batch", 4))
        nxt = 0
        for i, f in enumerate(frames):
            stream.add(tn_frame(f))
            if i == grid_index(nxt, fast_fps, fps):
                grid_frame(f)
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
    if lines and shots:
        info.update(main_camera_from_lines(shots, np.array(ev), np.stack(th), fps or 10.0))
    else:
        info["main_rule"] = "colour"
    mask = np.zeros(len(hs), bool)
    for sh in shots:
        mask[sh.start:sh.end] = sh.main_camera
    return shots, mask
