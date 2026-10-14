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


def gate_window(track: np.ndarray, frame_w: int, frame_h: int, fps: float, targets: list[float],
                side: str = "near", margin_s: float = 0.1) -> dict:
    """Decision for one window. track: raw ball track of the window (T, 3) (as cached; cleaned here
    as run_clip does); targets: frames of the candidates within the window (float).

    Returns {"passed": bool, "reason": str, ...}. Reasons: "golpe_de_bola" (a target-side ball hit
    near a candidate), "bola_no_vista" (near end: the ball is not well seen near a candidate, a
    swing could stand), "sin_golpe" (gated: neither)."""
    if track is None or not len(track) or not targets:
        return {"passed": True, "reason": "sin_datos_de_bola"}
    t = clean_track(np.asarray(track, float), width=frame_w)
    hits = [h for h in ball_hits(t, frame_h, fps) if h.side == side]
    seen = ~np.isnan(t[:, 0])
    tol = (CONFIRM_TOL_S + max(0.0, margin_s)) * fps
    for c in targets:
        near_hit = [h.frame for h in hits if abs(h.frame - c) <= tol]
        if near_hit:
            return {"passed": True, "reason": "golpe_de_bola", "hit_s": round(min(near_hit, key=lambda f: abs(f - c)) / fps, 2)}
    if side == "near":
        for c in targets:
            lo, hi = max(0, int(np.ceil(c - tol))), int(np.floor(c + tol))
            for g in range(lo, hi + 1):
                if g >= len(seen):               # beyond the ball track: cannot be checked
                    return {"passed": True, "reason": "bola_no_vista", "at_s": round(g / fps, 2)}
                f = seen_fraction(seen, g, fps)
                if f is None or f < SEEN_NEEDED:
                    return {"passed": True, "reason": "bola_no_vista", "at_s": round(g / fps, 2)}
    return {"passed": False, "reason": "sin_golpe", "hits": len(hits)}
