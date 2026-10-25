"""Ball-contact candidates: audio transients fused with wrist-speed peaks.

Audio alone is not enough (other courts, crowd, mic handling), and the wrist peak alone is
a few frames off contact. A contact confirmed by both is trusted; one seen only in the swing
is kept with lower confidence and goes to manual review.
"""
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks


def audio_onsets(y: np.ndarray, sr: int, band=(1000, 6000), delta=0.35, hop=128):
    """Times (s) and strengths of sharp broadband transients in the racket-impact band."""
    import librosa

    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    flux = np.maximum(0, np.diff(np.log1p(S[(f > band[0]) & (f < band[1])] * 50), axis=1)).sum(0)
    flux = (flux - np.median(flux)) / (np.percentile(flux, 99) - np.median(flux) + 1e-9)
    w = int(0.15 * sr / hop)
    pk = librosa.util.peak_pick(flux, pre_max=w, post_max=w, pre_avg=3 * w, post_avg=3 * w, delta=delta, wait=3 * w)
    return librosa.frames_to_time(pk + 1, sr=sr, hop_length=hop), flux[pk]


def swing_peaks(wrist_speed: np.ndarray, fps: float, min_gap=0.6, height=2.0, prominence=1.2) -> np.ndarray:
    """Frames where the dominant wrist (body-relative, body heights/s) peaks as in a swing."""
    v = np.nan_to_num(wrist_speed)
    pk, _ = find_peaks(v, distance=max(1, int(min_gap * fps)), height=height, prominence=prominence)
    return pk


SEEN_NEEDED = 0.5      # a swing with the ball seen in at least this fraction of the frames around it...
SEEN_HALF_S = 0.3      # ...within ± this many seconds, and no ball hit, is not a stroke (fuse_with_ball)


@dataclass
class Impact:
    frame: int
    t: float
    source: str            # "audio+swing" or "swing"
    audio_offset_ms: int | None
    confidence: float


def fuse(swing_frames: np.ndarray, fps: float, onset_times: np.ndarray, tol=0.12) -> list[Impact]:
    """Snap each swing to the nearest audio transient within `tol` seconds when there is one."""
    out = []
    for f in swing_frames:
        t = f / fps
        if len(onset_times):
            j = int(np.argmin(np.abs(onset_times - t)))
            dt = float(onset_times[j] - t)
            if abs(dt) <= tol:
                ta = float(onset_times[j])
                out.append(Impact(int(round(ta * fps)), ta, "audio+swing", int(dt * 1000), 0.9))
                continue
            out.append(Impact(int(f), t, "swing", int(dt * 1000), 0.5))
        else:
            out.append(Impact(int(f), t, "swing", None, 0.5))
    return out


def fuse_with_ball(impacts: list[Impact], fps: float, hits: list, ball_seen: np.ndarray, boxes: list,
                   tol=0.2, seen_needed=SEEN_NEEDED, wrist_speed: np.ndarray | None = None, min_arm_speed=1.2,
                   min_gap=0.4, side="near") -> list[Impact]:
    """Refine and filter swing/audio impacts with the ball (tennisbio.ball.ball_hits, near side).

    - A near-player ball hit within `tol` s of a swing: the contact is the ball's turning point.
    - A swing with the ball well seen around it (≥ seen_needed of the frames within ±0.3 s) but no
      ball hit: not a stroke (running, shadow swings, racket twirls) → dropped.
    - A swing where the ball is not seen: kept as it was (cannot be checked).
    - A ball hit next to the tracked player with no detected swing peak: added (source "ball") if
      the dominant wrist still moves at least min_arm_speed body heights/s within ±tol (a ball
      turning near a still player is a bounce, a net cord or a tracking error, not a stroke).
    - Two impacts closer than min_gap s: the one with more evidence is kept.
    ball_seen: (T,) bool; boxes: tracked player box per frame or None; wrist_speed: (T,) body-relative.
    """
    near = [h for h in hits if h.side == side]          # hits of the tracked player's end
    used, out = set(), []
    w = max(1, round(SEEN_HALF_S * fps))
    for imp in impacts:
        best = min(near, key=lambda h: abs(h.frame - imp.frame), default=None)
        if best is not None and abs(best.frame - imp.frame) <= tol * fps:
            used.add(best.frame)
            src = ("audio+" if imp.source.startswith("audio") else "") + "ball+swing"
            out.append(Impact(best.frame, best.frame / fps, src, imp.audio_offset_ms, 0.95))
            continue
        a, b = max(0, imp.frame - w), min(len(ball_seen), imp.frame + w + 1)
        if b > a and ball_seen[a:b].mean() >= seen_needed:
            continue
        out.append(imp)
    for h in near:
        if h.frame in used or h.frame >= len(boxes) or boxes[h.frame] is None:
            continue
        x0, y0, x1, y1 = boxes[h.frame]
        bw = x1 - x0
        if not (x0 - bw <= h.x <= x1 + bw and y0 - 0.3 * (y1 - y0) <= h.y <= y1):
            continue
        if wrist_speed is not None:
            a, b = max(0, h.frame - round(tol * fps)), min(len(wrist_speed), h.frame + round(tol * fps) + 1)
            seg = wrist_speed[a:b]
            if not (np.isfinite(seg).any() and np.nanmax(seg) >= min_arm_speed):
                continue
        out.append(Impact(h.frame, h.frame / fps, "ball", None, 0.7))
    out.sort(key=lambda i: i.frame)
    kept = []
    for imp in out:
        if kept and imp.frame - kept[-1].frame < min_gap * fps:
            if imp.confidence > kept[-1].confidence:
                kept[-1] = imp
            continue
        kept.append(imp)
    return kept


def add_spotted(impacts: list[Impact], fps: float, spotted: list[float], hits: list, wrist_speed: np.ndarray | None,
                n_frames: int, tol: float, side: str = "near", snap_s: float = 0.2) -> list[Impact]:
    """The learned spotter's strokes (tennisbio.spotting, times in s within the clip) that no impact of the
    rules lies within `tol` of: added as impacts (source "spotter"), since the spotter is the detector
    (90 % of her strokes found against F3Set, docs/validacion_detector.md) and the rules only time them.
    The contact is the nearest ball hit of her end within snap_s ("spotter+ball"), else the fastest frame
    of her dominant wrist within snap_s, else the spotter's own frame."""
    near = [h.frame for h in hits if h.side == side]
    out = list(impacts)
    for t in spotted:
        f0 = int(round(t * fps))
        if not 0 <= f0 < n_frames or any(abs(i.frame - f0) <= tol * fps for i in out):
            continue
        w = max(1, round(snap_s * fps))
        hit = min(near, key=lambda f: abs(f - f0), default=None)
        if hit is not None and abs(hit - f0) <= w:
            out.append(Impact(hit, hit / fps, "spotter+ball", None, 0.8))
            continue
        f = f0
        if wrist_speed is not None:
            a, b = max(0, f0 - w), min(len(wrist_speed), f0 + w + 1)
            seg = wrist_speed[a:b]
            if b > a and np.isfinite(seg).any():
                f = a + int(np.nanargmax(seg))
        out.append(Impact(f, f / fps, "spotter", None, 0.6))
    out.sort(key=lambda i: i.frame)
    return out
