"""Cheap gate of the fine pass: does a window possibly hold a confirmed stroke of the target?

The fine pass spends most of its time on the full-rate pose of each window (~62 %), and most
windows of the cheap pass end up with no confirmed stroke. The ball track of the window is needed
anyway (it is cached and reused by the full pass), so the gate reads only the ball: it is a
NECESSARY condition of what the full pass would confirm, derived from the code that confirms:

A candidate of the cheap pass becomes a stroke only when an impact of the full pass lies within
CONFIRM_TOL_S of it (stages._fine_stroke). After impacts.fuse_with_ball, every impact is one of:

1. at a ball hit of the target's end ("ball+swing" or "ball": the impact frame IS the hit frame);
2. (near end only) a swing/audio impact kept because the ball is NOT well seen around it: fewer
   than SEEN_NEEDED of the frames within ±SEEN_HALF_S are seen (a swing with the ball well seen and
   no hit is dropped). Far strokes count only when the ball confirms them, so only 1 applies there.

So a window can be skipped only when, for every candidate, there is no target-side ball hit within
CONFIRM_TOL_S (+ margin) AND, near end, the ball is well seen around every frame within
CONFIRM_TOL_S (+ margin). Ball hits and visibility are computed exactly as in clip_pipeline.run_clip
(clean_track, ball_hits, the same window frames). Pose, audio, tracking and wrist speed can only
REMOVE impacts, never add one where these conditions fail, so the gate has no false negatives by
construction. When unsure (no ball model, an empty track, a frame outside the track), it passes.

The same conditions say WHERE a confirmable impact can be (possible_impacts): at a target-side ball
hit near a candidate, or (near end) at a frame near a candidate where the ball is not well seen. A
window that passes needs the pose only around those (pose_keep, fine_pass.pose_ranges): from the
wait and the opponent's hit before them to the recovery after them; the rest of a long window of a
rally (the other player's shots, the end of the point) is not posed.
"""
import numpy as np

from .ball import ball_hits, clean_track
from .impacts import SEEN_HALF_S, SEEN_NEEDED

CONFIRM_TOL_S = 0.4          # a candidate is confirmed by an impact of the full pass within this (s)


def seen_fraction(seen: np.ndarray, frame: int, fps: float) -> float | None:
    """Fraction of frames with the ball seen within ±SEEN_HALF_S of `frame`, as fuse_with_ball
    computes it; None when that range is empty (fuse_with_ball then keeps the swing)."""
    w = max(1, round(SEEN_HALF_S * fps))
    a, b = max(0, frame - w), min(len(seen), frame + w + 1)
    return float(seen[a:b].mean()) if b > a else None


def possible_impacts(track: np.ndarray, frame_w: int, frame_h: int, fps: float, targets: list[float],
                     side: str = "near", margin_s: float = 0.1) -> list[tuple[int, int, str]]:
    """Where an impact the full pass could confirm may lie: (first, last frame, reason) for every
    target-side ball hit within CONFIRM_TOL_S (+ margin) of a candidate ("golpe_de_bola": the
    impact frame is the hit frame) and, near end, for every candidate with frames within that
    tolerance where the ball is not well seen ("bola_no_vista": a swing could stand at any of them;
    first..last of those frames; ball hits also carry the ball's x, y there). Empty: no stroke can be
    confirmed (the gate). track: raw ball
    track of the window (T, 3), cleaned here as run_clip does."""
    t = clean_track(np.asarray(track, float), width=frame_w)
    hits = [h for h in ball_hits(t, frame_h, fps) if h.side == side]
    seen = ~np.isnan(t[:, 0])
    tol = (CONFIRM_TOL_S + max(0.0, margin_s)) * fps
    out = []
    for c in targets:
        for h in hits:
            if abs(h.frame - c) <= tol and not any(p[0] == h.frame and p[2] == "golpe_de_bola" for p in out):
                out.append((h.frame, h.frame, "golpe_de_bola", h.x, h.y))
    if side == "near":
        for c in targets:
            lo, hi = max(0, int(np.ceil(c - tol))), int(np.floor(c + tol))
            bad = []
            for g in range(lo, hi + 1):
                f = None if g >= len(seen) else seen_fraction(seen, g, fps)
                if f is None or f < SEEN_NEEDED:     # beyond the track, or the ball not well seen
                    bad.append(g)
            if bad:
                out.append((bad[0], bad[-1], "bola_no_vista"))
    return out


def gate_window(track: np.ndarray, frame_w: int, frame_h: int, fps: float, targets: list[float],
                side: str = "near", margin_s: float = 0.1) -> dict:
    """Decision for one window. track: raw ball track of the window (T, 3) (as cached; cleaned here
    as run_clip does); targets: frames of the candidates within the window (float).

    Returns {"passed": bool, "reason": str, "possible": possible_impacts(...), ...}. Reasons:
    "golpe_de_bola" (a target-side ball hit near a candidate), "bola_no_vista" (near end: the ball
    is not well seen near a candidate, a swing could stand), "sin_golpe" (gated: neither)."""
    if track is None or not len(track) or not targets:
        return {"passed": True, "reason": "sin_datos_de_bola"}
    pos = possible_impacts(track, frame_w, frame_h, fps, targets, side, margin_s)
    hit = [p for p in pos if p[2] == "golpe_de_bola"]
    if hit:
        c0 = next(c for c in targets if any(abs(p[0] - c) <= (CONFIRM_TOL_S + max(0.0, margin_s)) * fps for p in hit))
        best = min((p[0] for p in hit if abs(p[0] - c0) <= (CONFIRM_TOL_S + max(0.0, margin_s)) * fps),
                   key=lambda f: abs(f - c0))
        return {"passed": True, "reason": "golpe_de_bola", "hit_s": round(best / fps, 2), "possible": pos}
    if pos:
        return {"passed": True, "reason": "bola_no_vista", "at_s": round(pos[0][0] / fps, 2), "possible": pos}
    t = clean_track(np.asarray(track, float), width=frame_w)
    return {"passed": False, "reason": "sin_golpe", "hits": sum(h.side == side for h in ball_hits(t, frame_h, fps))}


def pose_keep(n_frames: int, possible: list, fps: float, pre_s: float = 2.8, post_s: float = 2.0,
              join_s: float = 1.0, full_frac: float = 0.85, fill_every: int = 0) -> np.ndarray | None:
    """Frames of a window the pose is needed on (fine_pass.pose_ranges), or None for all of them.

    An impact at frame i is analysed with the pose from up to 2.2 s before it (its wait, back to
    half a second before the opponent's hit; analyze_stroke) and the opponent's hit up to 2.5 s
    before (court displacement, footwork), to 0.8-1.0 s after (finish, recovery steps), and the
    footwork reads where she is at the opponent's next hit; with the 0.3 s smoothing of positions:
    pre_s = 2.8 s, post_s = 2.0 s around every possible impact (possible_impacts). Gaps shorter than
    join_s are posed too (a new tracking start costs more than it saves), and when that covers
    full_frac of the window the whole window is posed, exactly as without ranges.
    fill_every: outside the stretches, one frame in every fill_every is posed too (she is followed
    through the whole window and her height is measured over it, as without ranges)."""
    if not possible or n_frames <= 0:
        return None
    keep = np.zeros(n_frames, bool)
    for lo, hi, *_ in possible:
        keep[max(0, int(lo - round(pre_s * fps))):min(n_frames, int(hi + round(post_s * fps)) + 1)] = True
    k = np.r_[0, keep.astype(int), 0]
    e = np.flatnonzero(np.diff(k))
    runs = list(zip(e[::2], e[1::2]))
    for (a0, b0), (a1, b1) in zip(runs, runs[1:]):
        if a1 - b0 < join_s * fps:
            keep[b0:a1] = True
    if not keep.any() or keep.mean() >= full_frac:
        return None
    if fill_every and fill_every > 1:
        keep[::int(fill_every)] = True
    return keep
