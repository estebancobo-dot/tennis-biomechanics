"""Shared clip pipeline: extract → track the player → find contacts → analyse each stroke.

Used by scripts/analyze_clip.py (visual output) and by the automatic validations, so what is
validated is exactly what produces the results.
"""
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .impacts import Impact, audio_onsets, fuse, swing_peaks
from .kinematics import body_height, clean, speed, to_body_frame
from .skeleton import Skeleton
from .stroke_analysis import StrokeResult, analyze_stroke
from .tracking import track_target


@dataclass
class ClipRun:
    fps: float
    sk: Skeleton
    img: np.ndarray                  # cleaned keypoints of the tracked player (T, K, 2)
    conf: np.ndarray
    boxes: list                      # tracked box per frame or None
    tracked_frac: float
    height_px: float
    onsets: np.ndarray
    impacts: list[Impact]
    rackets: list = field(default_factory=list)
    strokes: list[StrokeResult] = field(default_factory=list)


def load_audio(video: Path, sr=22050):
    import librosa

    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), str(wav)])
        if r.returncode or not wav.exists():
            return np.zeros(0), sr
        y, _ = librosa.load(wav, sr=sr)
    return y, sr


def pick_initial(boxes, mode="largest") -> tuple[int, np.ndarray]:
    """Initial box of the target: 'largest' (near player in TV / phone clips) or 'lowest' (bottom-most)."""
    first = next(t for t in range(len(boxes)) if len(boxes[t]))
    b = boxes[first]
    key = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]) if mode == "largest" else b[:, 3]
    return first, b[int(np.argmax(key))]


def run_clip(video: str | Path, cache: str | Path, hand="right", height_m=1.84, rackets=True,
             init_mode="largest", imgsz=960, log=print) -> ClipRun:
    video, cache = Path(video), Path(cache)
    if not cache.exists():
        from .pose.yolo import extract
        extract(video, cache, imgsz=imgsz, progress=False)
    d = np.load(cache, allow_pickle=True)
    fps, boxes, kps, confs, feats = float(d["fps"]), d["boxes"], d["kps"], d["confs"], d["feats"]
    sk = Skeleton("coco17", hand)
    T = len(boxes)

    _, init = pick_initial(boxes, init_mode)
    sel = track_target(list(boxes), list(feats), init)
    kp = np.full((T, len(sk), 2), np.nan)
    cf = np.zeros((T, len(sk)))
    boxes_t = [None] * T
    for t, j in enumerate(sel):
        if j >= 0:
            kp[t], cf[t], boxes_t[t] = kps[t][j], confs[t][j], boxes[t][j]

    img = clean(kp, cf)
    height_px = body_height(img, sk)
    body = to_body_frame(img, sk, height_px)
    swings = swing_peaks(speed(body[:, sk["dom_wrist"]], fps), fps)
    y, sr = load_audio(video)
    onsets = audio_onsets(y, sr)[0] if len(y) else np.zeros(0)
    impacts = fuse(swings, fps, onsets)
    log(f"jugadora seguida en {np.mean(sel >= 0) * 100:.0f} % · altura ≈ {height_px:.0f} px · {len(impacts)} golpes "
        f"({sum(i.source == 'audio+swing' for i in impacts)} con audio)")
    run = ClipRun(fps, sk, img, cf, boxes_t, float(np.mean(sel >= 0)), height_px, onsets, impacts)

    run.rackets = [[] for _ in range(T)]
    if rackets and impacts:
        rcache = cache.with_name(cache.stem + "_rackets.npz")
        need = sorted({f for imp in impacts for f in range(max(0, imp.frame - int(fps)), min(T, imp.frame + int(0.8 * fps) + 1))})
        if not rcache.exists() or not set(need) <= set(np.load(rcache, allow_pickle=True)["frames"].tolist()):
            from .pose.yolo import extract_rackets
            log(f"segmentando la raqueta en {len(need)} fotogramas")
            extract_rackets(video, need, rcache, imgsz=imgsz)
        rd = np.load(rcache, allow_pickle=True)
        for f, p in zip(rd["frames"], rd["polys"]):
            run.rackets[int(f)] = p

    for imp in impacts:
        prev = [t for t in onsets if 0.5 < imp.t - t < 2.0]
        opp = int(round(prev[-1] * fps)) if prev else None
        run.strokes.append(analyze_stroke(img, cf, sk, fps, height_px, imp.frame, imp.source,
                                          run.rackets if rackets else None, height_m, opp))
    return run
