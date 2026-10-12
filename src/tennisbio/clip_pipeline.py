"""Shared clip pipeline: extract → track the player → find contacts → analyse each stroke.

Used by scripts/analyze_clip.py (visual output) and by the automatic validations, so what is
validated is exactly what produces the results.
"""
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import cv2

import numpy as np

from .io.video import open_capture
from .impacts import Impact, audio_onsets, fuse, fuse_with_ball, swing_peaks
from .pipeline import load_npz, save_npy_atomic
from .kinematics import body_height, clean, scale_track, speed, to_body_frame
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
    ball: np.ndarray | None = None              # (T, 3) ball x, y, confidence (NaN when unseen)
    side: str = "near"
    hits: list = field(default_factory=list)     # ball turns of both players (tennisbio.ball.BallHit)
    strokes: list[StrokeResult] = field(default_factory=list)
    height_t: np.ndarray | None = None          # body height in px per frame (kinematics.scale_track)


def _cv2_frames(video: Path):
    cap = open_capture(video)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        yield frame
    cap.release()


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
    """Initial box of the target.

    'largest': biggest person (phone clips). 'near': near player on the main TV camera = the
    person standing lowest in the image among those at least half as tall as the tallest
    (the chair umpire and line judges are higher up or smaller).
    """
    first = next(t for t in range(len(boxes)) if len(boxes[t]))
    b = boxes[first]
    h = b[:, 3] - b[:, 1]
    if mode == "near":
        cand = np.flatnonzero(h >= 0.5 * h.max())
        return first, b[cand[np.argmax(b[cand, 3])]]
    return first, b[int(np.argmax(h * (b[:, 2] - b[:, 0])))]


def run_clip(video: str | Path, cache: str | Path, hand="right", height_m=1.84, rackets=True,
             init_mode="largest", imgsz=960, log=print, ball=None, side="near",
             init_box: np.ndarray | None = None, max_bottom: float | None = None, roi: tuple | str | None = None) -> ClipRun:
    """Pose, tracking, impacts and stroke analysis of a short clip (cached).

    ball: optional tennisbio.ball.BallTracker; its track is cached next to the pose cache and
    used to time and confirm the strokes (fuse_with_ball).
    side="far": the target is the far player (facing the camera): init_box/max_bottom pick and
    keep her; the keypoints are mirrored left-right for the stroke analysis so that every metric
    reads as for a player seen from behind (run.img keeps the real image coordinates).
    roi: run the pose on that region only, or "follow" (far player: an enlarged crop that follows
    her from init_box; pose.yolo.extract_follow)."""
    video, cache = Path(video), Path(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    if load_npz(cache) is None:          # missing or damaged (interrupted run): extract again
        from .pose.yolo import extract
        if roi == "follow":            # small far player: crop that follows her, enlarged
            from .pose.yolo import extract_follow
            extract_follow(video, cache, init_box, max_bottom=max_bottom)
        else:
            extract(video, cache, imgsz=imgsz, progress=False, roi=roi)
    d = load_npz(cache)
    if d is None:
        raise RuntimeError(f"no se pudo extraer la pose de {video.name}")
    fps, boxes, kps, confs, feats = float(d["fps"]), d["boxes"], d["kps"], d["confs"], d["feats"]
    sk = Skeleton("coco17", hand)
    T = len(boxes)

    cap = open_capture(video)
    fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    first, init = pick_initial(boxes, init_mode)
    if init_box is not None:
        init = np.asarray(init_box, float)
    min_bottom = None
    if init_mode == "near" and side == "near":
        # the near player's feet stay below the net, roughly the lower half of the frame;
        # half of the initial feet height keeps her even when she comes to the net
        min_bottom = float(0.5 * init[3])
    sel = track_target(list(boxes), list(feats), init, min_bottom=min_bottom, max_bottom=max_bottom)
    kp = np.full((T, len(sk), 2), np.nan)
    cf = np.zeros((T, len(sk)))
    boxes_t = [None] * T
    for t, j in enumerate(sel):
        if j >= 0:
            kp[t], cf[t], boxes_t[t] = kps[t][j], confs[t][j], boxes[t][j]

    img = clean(kp, cf)
    height_px = body_height(img, sk)
    img_a = img
    if side == "far":                      # facing the camera: mirror so the analysis sees her from behind
        img_a = img.copy()
        img_a[..., 0] = fw - img_a[..., 0]
    height_t = scale_track(img, sk, height_px, fps)
    body = to_body_frame(img_a, sk, height_t)
    swings = swing_peaks(speed(body[:, sk["dom_wrist"]], fps), fps)
    y, sr = load_audio(video)
    onsets = audio_onsets(y, sr)[0] if len(y) else np.zeros(0)
    impacts = fuse(swings, fps, onsets)
    ball_track = None
    if ball is not None:
        from .ball import ball_hits, clean_track

        bcache = cache.with_name(cache.stem.removesuffix("_far") + "_ball.npy")      # same ball for both ends
        try:
            ball_track = np.load(bcache) if bcache.exists() else None
        except Exception:                 # damaged cache
            bcache.unlink(missing_ok=True)
            ball_track = None
        if ball_track is None:      # same decoder as the pose extraction, so frame indices match
            ball_track = ball.track(_cv2_frames(video), step=max(1, round(fps / 25)))
            save_npy_atomic(bcache, ball_track)
        ball_track = clean_track(ball_track, width=fw)
        n = min(T, len(ball_track))
        hits = ball_hits(ball_track[:n], fh, fps)
        impacts = fuse_with_ball(impacts, fps, hits, ~np.isnan(ball_track[:n, 0]), boxes_t,
                                 wrist_speed=speed(body[:, sk["dom_wrist"]], fps), side=side)
        run_hits = hits
        other = "far" if side == "near" else "near"
        far_hits = [h.frame for h in hits if h.side == other]          # the opponent's hits
    log(f"jugadora seguida en {np.mean(sel >= 0) * 100:.0f} % · altura ≈ {height_px:.0f} px · {len(impacts)} golpes "
        f"({sum(i.source == 'audio+swing' for i in impacts)} con audio)")
    run = ClipRun(fps, sk, img, cf, boxes_t, float(np.mean(sel >= 0)), height_px, onsets, impacts)
    run.side = side
    run.hits = run_hits if ball is not None else []
    run.ball = ball_track
    run.height_t = height_t

    run.rackets = [[] for _ in range(T)]
    if rackets and impacts:
        rcache = cache.with_name(cache.stem + "_rackets.npz")
        need = sorted({f for imp in impacts for f in range(max(0, imp.frame - int(fps)), min(T, imp.frame + int(0.8 * fps) + 1))})
        rd = load_npz(rcache)
        if rd is None or not set(need) <= set(rd["frames"].tolist()):
            from .pose.yolo import extract_rackets
            log(f"segmentando la raqueta en {len(need)} fotogramas")
            extract_rackets(video, need, rcache, imgsz=imgsz)
            rd = load_npz(rcache)
        for f, p in zip(rd["frames"], rd["polys"]):
            run.rackets[int(f)] = p

    for imp in impacts:
        # opponent's hit: from the ball when seen (far-side turn), else the previous audio transient
        prev_ball = [f for f in (far_hits if ball_track is not None else []) if 0.4 * fps < imp.frame - f < 2.5 * fps]
        prev = [t for t in onsets if 0.5 < imp.t - t < 2.0]
        opp = prev_ball[-1] if prev_ball else (int(round(prev[-1] * fps)) if prev else None)
        r = analyze_stroke(img_a, cf, sk, fps, height_px, imp.frame, imp.source,
                           run.rackets if rackets else None, height_m, opp, scale=height_t)
        if ball_track is not None and imp.source.find("ball") >= 0:
            from .ball import bounce_before
            # incoming bounce on her half; her shot lands on the other half (image rows split near the net)
            mine = dict(min_y=0.4 * fh) if side == "near" else dict(max_y=0.55 * fh)
            theirs = dict(max_y=0.55 * fh) if side == "near" else dict(min_y=0.4 * fh)
            b = bounce_before(ball_track[:n], imp.frame, fps, prev_ball[-1] if prev_ball else None, **mine)
            if b is not None:
                r.ball = {"bounce_px": [round(b.x, 1), round(b.y, 1)], "bounce_frame": b.frame}
                r.metrics["bounce_to_impact_s"] = round((imp.frame - b.frame) / fps, 3)
                if r.metrics["bounce_to_impact_s"] < 0.12 and (r.metrics.get("contact_height_pct") or 100) < 35:
                    r.review.append("half_volley_candidate")
            from .ball import bounce_after
            nxt = [f for f in far_hits if f > imp.frame + 0.2 * fps]
            obs_ = bounce_after(ball_track[:n], imp.frame, fps, nxt[0] if nxt else None, **theirs)
            if obs_:                # where her shot lands: candidates in image px, checked on the court later
                r.ball["shot_bounce_candidates"] = [[round(b.x, 1), round(b.y, 1), b.frame] for b in obs_]
        if opp is not None:      # time the ball took from the opponent's racket: fast / slow ball
            r.metrics["time_available_s"] = round((imp.frame - opp) / fps, 3)
            r.metrics["opponent_hit_source"] = "ball" if prev_ball else "audio"
        run.strokes.append(r)
    return run
