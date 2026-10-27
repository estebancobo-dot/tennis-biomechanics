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
from .footpoints import tracked_feet
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
    height_t: np.ndarray | None = None          # body height in px per frame (body_scale.height_scale)
    height_source: str = "pose"                 # 'court' | 'segments' | 'pose' (body_scale)
    height_info: dict = field(default_factory=dict)   # its checks (body_scale.height_scale)
    timing: dict = field(default_factory=dict)   # seconds spent in each model (only what was computed now)
    stats: dict = field(default_factory=dict)    # counts of what was computed now (frames posed, rackets...)
    # foot points of the tracked player (hybrid pose, near side), Halpe26 order (skeleton.FOOT_NAMES):
    # left/right big toe, left/right small toe, left/right heel. (T, 6, 2) image px, NaN when unseen;
    # feet_conf (T, 6), 0 when unseen. All NaN / 0 with the YOLO pose (far side, or pose_model: yolo).
    feet: np.ndarray | None = None
    feet_conf: np.ndarray | None = None


def _cv2_frames(video: Path):
    """Every frame with OpenCV (the same decoder as the pose extraction, so frame indices match),
    decoded ahead in a background thread."""
    from .io.video import capture_frames
    return capture_frames(video)


def _tee(frames, feed):
    """The frames, each also handed to `feed` (e.g. a ball.BallFeed) on the way: one decode of the
    window serves the pose and the ball models."""
    for f in frames:
        feed.add(f)
        yield f


def _load_ball_cache(bcache: Path):
    try:
        return np.load(bcache) if bcache.exists() else None
    except Exception:                 # damaged cache
        bcache.unlink(missing_ok=True)
        return None


def ball_cache_path(cache: str | Path) -> Path:
    """Ball track cache next to a pose cache (the same ball for both ends of a window)."""
    cache = Path(cache)
    return cache.with_name(cache.stem.removesuffix("_far") + "_ball.npy")


def window_ball(video: str | Path, cache: str | Path, ball) -> tuple[np.ndarray, float, int, int, float]:
    """The raw ball track of a clip, computed exactly as run_clip does when the pose is cached (all
    frames decoded, the model on every round(fps/25)-th) and saved where run_clip reads it, so the
    full pass reuses it. Returns (track, seconds spent computing it now, frame width, frame height,
    fps), for the gate of the fine pass (fine_gate) before any pose is run."""
    import time
    from .pose.yolo import _fps

    video = Path(video)
    bcache = ball_cache_path(cache)
    fps = float(_fps(video))
    cap = open_capture(video)
    fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    track = _load_ball_cache(bcache)
    took = 0.0
    if track is None:
        t_ = time.time()
        track = ball.track(_cv2_frames(video), step=max(1, round(fps / 25)))
        bcache.parent.mkdir(parents=True, exist_ok=True)
        save_npy_atomic(bcache, track)
        took = time.time() - t_
    return track, took, fw, fh, fps


def load_audio(video: Path, sr=22050):
    import librosa

    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        # a clip without sound (RacketVision) is normal: no audio, and ffmpeg's complaint is not shown
        try:
            r = subprocess.run(timeout=600, args=["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), str(wav)],
                               capture_output=True)
        except subprocess.TimeoutExpired:      # the sound of a clip that hangs: none, as a clip without sound
            return np.zeros(0), sr
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
    first = next((t for t in range(len(boxes)) if len(boxes[t])), None)
    if first is None:                   # nobody in the whole clip (a shot without players)
        return None, None
    b = boxes[first]
    h = b[:, 3] - b[:, 1]
    if mode == "near":
        cand = np.flatnonzero(h >= 0.5 * h.max())
        return first, b[cand[np.argmax(b[cand, 3])]]
    return first, b[int(np.argmax(h * (b[:, 2] - b[:, 0])))]


def keep_key(keep) -> str:
    """Short name of a set of frames (pose caches of fine_pass.pose_ranges carry it)."""
    import hashlib
    return hashlib.sha1(np.packbits(np.asarray(keep, bool)).tobytes() + str(len(keep)).encode()).hexdigest()[:8]


def _anchor(boxes, hits, a: int, b: int, search=5):
    """(frame, box) of the person the ball leaves from at the first of `hits` [(frame, x, y)] that
    has one within ±search frames (the box enlarged as in impacts.fuse_with_ball), or None."""
    for f0, x, y in sorted(hits):
        for d in sorted(range(-search, search + 1), key=abs):
            f = int(f0) + d
            if not a <= f < b or not len(boxes[f]):
                continue
            bx = np.asarray(boxes[f], float)
            bw, bh = bx[:, 2] - bx[:, 0], bx[:, 3] - bx[:, 1]
            ok = (bx[:, 0] - bw <= x) & (x <= bx[:, 2] + bw) & (bx[:, 1] - 0.3 * bh <= y) & (y <= bx[:, 3])
            if ok.any():
                c = np.flatnonzero(ok)
                d2 = np.hypot((bx[c, 0] + bx[c, 2]) / 2 - x, (bx[c, 1] + bx[c, 3]) / 2 - y)
                return f, bx[c[int(np.argmin(d2))]]
    return None


def keep_runs(keep) -> list[tuple[int, int]]:
    """[a, b) stretches of True in a bool mask."""
    k = np.r_[0, np.asarray(keep, bool).astype(int), 0]
    e = np.flatnonzero(np.diff(k))
    return list(zip(e[::2].tolist(), e[1::2].tolist()))


def run_clip(video: str | Path, cache: str | Path, hand="right", height_m=1.84, rackets=True,
             init_mode="largest", imgsz=960, log=print, ball=None, side="near",
             init_box: np.ndarray | None = None, max_bottom: float | None = None, roi: tuple | str | None = None,
             prefetch: bool = True, targets: list | None = None, target_tol: float | None = None,
             keep: np.ndarray | None = None, inits: dict | None = None, anchors: list | None = None,
             split: bool = True, pose_model: str = "yolo", court_H: np.ndarray | None = None,
             height_scale: str = "court", spotted: list | None = None) -> ClipRun:
    """Pose, tracking, impacts and stroke analysis of a short clip (cached).

    ball: optional tennisbio.ball.BallTracker; its track is cached next to the pose cache and
    used to time and confirm the strokes (fuse_with_ball).
    side="far": the target is the far player (facing the camera): init_box/max_bottom pick and
    keep her; the keypoints are mirrored left-right for the stroke analysis so that every metric
    reads as for a player seen from behind (run.img keeps the real image coordinates).
    roi: run the pose on that region only, or "follow" (far player: an enlarged crop that follows
    her from init_box; pose.yolo.extract_follow).
    prefetch: model inputs and appearance computed in other threads (same result, faster).
    targets / target_tol: times (s) where a stroke is wanted (the cheap pass's candidates) and the
    tolerance (s) within which an impact can be matched to one: the racket outline (slow
    model) is segmented only around impacts that can become one of those strokes (the others are
    never kept). None: around every impact.
    keep: optional (T,) bool, the frames to run the pose on (fine_pass.pose_ranges); each stretch
    is tracked on its own, from its first frame (as a window of its own); the pose cache then
    carries keep_key(keep). inits: {first frame of a stretch: far player's box there} (far end).
    anchors: [(frame, x, y)] ball hits of hers (near end, with keep): a stretch holding one starts
    its tracking from the person the ball leaves from. split=False: the kept frames are tracked as
    one clip from its first frame, as without keep (fine_pass.pose_fill_every: between the stretches
    a frame in every few is posed, enough to follow her and to measure her height as the whole window).
    spotted: times (s) of the learned spotter's strokes of this end (spotter.enabled): each one with no
    impact of the rules within target_tol becomes an impact of its own (impacts.add_spotted).
    pose_model: 'yolo' (YOLO11m-pose) or 'hybrid' (pose.hybrid: YOLO + RTMPose-x with the 6 foot points,
    fine_pass.pose_model) for the near side; the far side is always YOLO (extract_follow). The tracked
    player's foot points are run.feet / run.feet_conf (all NaN / 0 without them).
    court_H: court → image homography of the window (real court frame, window pixels), or None;
    height_scale: how her height in px is estimated (body_scale.height_scale: 'court' from court_H and
    height_m, else her body segments; 'pose' as before). run.height_t / run.height_px are that scale;
    the swings are still found with the former one (their thresholds were tuned with it)."""
    import time
    video, cache = Path(video), Path(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    timing = {}
    ball_track = feed = None
    if ball is not None:
        bcache = ball_cache_path(cache)
        ball_track = _load_ball_cache(bcache)
    t_ = time.time()
    if keep is not None and cache.exists() and load_npz(cache) is not None:
        keep = inits = None                 # the whole window is already posed (an earlier run): reused
    pcache = cache if keep is None else cache.with_name(f"{cache.stem}_r{keep_key(keep)}.npz")
    use_model = "hybrid" if pose_model == "hybrid" and side == "near" and roi != "follow" else "yolo"
    pstats: dict = {"pose_model": use_model}
    if load_npz(pcache) is None:          # missing or damaged (interrupted run): extract again
        from .pose.hybrid import extract_fine
        from .pose.yolo import _fps
        frames = None
        if ball is not None and ball_track is None:      # the ball model reads the same decoded frames
            from .ball import BallFeed
            feed = BallFeed(max(1, round(_fps(video) / 25)))
            frames = _tee(_cv2_frames(video), feed)
        if roi == "follow":            # small far player: crop that follows her, enlarged
            from .pose.yolo import extract_follow
            extract_follow(video, pcache, init_box, max_bottom=max_bottom, frames=frames, prefetch=prefetch,
                           keep=keep, inits=inits, stats=pstats)
        else:
            extract_fine(video, pcache, imgsz=imgsz, progress=False, roi=roi, frames=frames, prefetch=prefetch,
                         keep=keep, stats=pstats, model_name=use_model)
    d = load_npz(pcache)
    if d is None:
        raise RuntimeError(f"no se pudo extraer la pose de {video.name}")
    timing["pose"] = time.time() - t_
    fps, boxes, kps, confs, feats = float(d["fps"]), d["boxes"], d["kps"], d["confs"], d["feats"]
    if use_model != "hybrid":           # the far side's feet are never used (too small): none, by contract
        d = {k: v for k, v in d.items() if k not in ("feet", "feet_confs")}
    sk = Skeleton("coco17", hand)
    T = len(boxes)

    cap = open_capture(video)
    fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    sel = np.full(T, -1)
    found = False
    # each stretch of posed frames is tracked on its own, as a window of its own (the whole clip
    # when every frame was posed)
    split = split and keep is not None
    for a, b in (keep_runs(keep[:T]) if split else [(0, T)]):
        first, init = pick_initial(boxes[a:b], init_mode)
        if init_box is not None:
            init = np.asarray(init_box, float)
            if split:
                ib = (inits or {}).get(a)
                if ib is None:                  # she was not found at the start of this stretch
                    continue
                init = np.asarray(ib, float)
        if init is None:
            continue
        found = True
        # a stretch around a ball hit of hers: she is the person the ball leaves from (the person
        # lowest in the image at the start of a stretch can be a ball kid), followed both ways from there
        anc = None if not split or init_box is not None else _anchor(boxes, [h for h in (anchors or [])
                                                                                if a <= h[0] < b], a, b)
        if anc is not None:
            f, init = anc
        min_bottom = None
        if init_mode == "near" and side == "near":
            # the near player's feet stay below the net, roughly the lower half of the frame;
            # half of the initial feet height keeps her even when she comes to the net
            min_bottom = float(0.5 * init[3])
        if anc is None:
            sel[a:b] = track_target(list(boxes[a:b]), list(feats[a:b]), init, min_bottom=min_bottom, max_bottom=max_bottom)
        else:
            sel[f:b] = track_target(list(boxes[f:b]), list(feats[f:b]), init, min_bottom=min_bottom, max_bottom=max_bottom)
            if f > a:
                sel[a:f] = track_target(list(boxes[a:f + 1][::-1]), list(feats[a:f + 1][::-1]), init,
                                        min_bottom=min_bottom, max_bottom=max_bottom)[::-1][:-1]
    stats = {**pstats, "frames_model": int(pstats.get("frames", 0)), "posed_frames": int(np.sum(keep[:T])) if keep is not None else T, "frames": T}
    if not found:                       # nobody to follow: a run without strokes, not an error
        log("nadie en la ventana: sin golpes")
        fk, fc = tracked_feet(d, sel)
        return ClipRun(fps, sk, np.full((T, len(sk), 2), np.nan), np.zeros((T, len(sk))), [None] * T, 0.0, 0.0,
                       np.zeros(0), [], rackets=[[] for _ in range(T)], timing=timing, stats=stats, feet=fk, feet_conf=fc)
    kp = np.full((T, len(sk), 2), np.nan)
    cf = np.zeros((T, len(sk)))
    boxes_t = [None] * T
    for t, j in enumerate(sel):
        if j >= 0:
            kp[t], cf[t], boxes_t[t] = kps[t][j], confs[t][j], boxes[t][j]

    img = clean(kp, cf)
    pose_h = body_height(img, sk)
    if keep is not None and not np.isfinite(pose_h):
        # her height (the scale of every measure in % of height) comes from the few frames where her
        # face and feet are both seen; none among those posed: the whole window, as without keep
        log("altura no medible en los tramos: ventana entera")
        whole = run_clip(video, cache, hand, height_m, rackets, init_mode, imgsz, log, ball, side,
                         init_box, max_bottom, roi, prefetch, targets, target_tol, pose_model=pose_model,
                         court_H=court_H, height_scale=height_scale, spotted=spotted)
        whole.timing["pose"] = whole.timing.get("pose", 0.0) + timing.get("pose", 0.0)
        whole.stats["posed_frames"] = whole.stats.get("posed_frames", 0) + int(np.sum(keep[:T]))
        whole.stats["whole_window_again"] = 1
        return whole
    img_a = img
    if side == "far":                      # facing the camera: mirror so the analysis sees her from behind
        img_a = img.copy()
        img_a[..., 0] = fw - img_a[..., 0]
    # her height in px per frame, the scale of every measure (body_scale); the swings and the arm's
    # speed at a ball hit are found with the former scale (nose → ankle), as they were tuned and validated
    from .body_scale import height_scale as _height_scale
    height_t, h_src, h_info = _height_scale(img, sk, fps, height_m, court_H, (fh, fw), height_scale)
    height_px = (pose_h if h_src == "pose" else float(np.nanmedian(height_t)))
    det_t = scale_track(img, sk, pose_h, fps) if np.isfinite(pose_h) else height_t
    body = to_body_frame(img_a, sk, det_t)
    swings = swing_peaks(speed(body[:, sk["dom_wrist"]], fps), fps)
    y, sr = load_audio(video)
    onsets = audio_onsets(y, sr)[0] if len(y) else np.zeros(0)
    impacts = fuse(swings, fps, onsets)
    if ball is not None:
        from .ball import ball_hits, clean_track

        if ball_track is None:      # same decoder as the pose extraction, so frame indices match
            t_ = time.time()
            ball_track = (ball.track_feed(feed) if feed is not None
                          else ball.track(_cv2_frames(video), step=max(1, round(fps / 25))))
            save_npy_atomic(bcache, ball_track)
            timing["bola"] = time.time() - t_
        ball_track = clean_track(ball_track, width=fw)
        n = min(T, len(ball_track))
        hits = ball_hits(ball_track[:n], fh, fps)
        impacts = fuse_with_ball(impacts, fps, hits, ~np.isnan(ball_track[:n, 0]), boxes_t,
                                 wrist_speed=speed(body[:, sk["dom_wrist"]], fps), side=side)
        run_hits = hits
        other = "far" if side == "near" else "near"
        far_hits = [h.frame for h in hits if h.side == other]          # the opponent's hits
    if spotted:
        from .impacts import add_spotted
        impacts = add_spotted(impacts, fps, spotted, run_hits if ball is not None else [],
                              speed(body[:, sk["dom_wrist"]], fps), T, target_tol or 0.4, side=side)
    log(f"jugadora seguida en {np.mean(sel >= 0) * 100:.0f} % · altura ≈ {height_px:.0f} px ({h_src}) · {len(impacts)} golpes "
        f"({sum(i.source == 'audio+swing' for i in impacts)} con audio)")
    run = ClipRun(fps, sk, img, cf, boxes_t, float(np.mean(sel >= 0)), height_px, onsets, impacts)
    run.side = side
    run.hits = run_hits if ball is not None else []
    run.ball = ball_track
    run.height_t = height_t
    run.height_source, run.height_info = h_src, h_info

    run.timing = timing
    run.stats = stats
    stats["height_scale"] = h_src
    run.feet, run.feet_conf = tracked_feet(d, sel)
    stats["feet_frames"] = int(np.sum((run.feet_conf > 0).any(1)))
    run.rackets = [[] for _ in range(T)]

    # the strokes that can be kept: impacts within the tolerance of a target (all without targets).
    # A kept stroke reads the racket from its wait (≤ 2.2 s before contact, minus the ±READY_HALF
    # frames searched around it) to 0.8 s after (analyze_stroke, racket_orientation.stroke_faces):
    # every outline the full segmentation has in that reach is still segmented, the others are not
    kept = [imp.frame for imp in impacts
            if targets is None or any(abs(imp.frame - c * fps) <= (target_tol or 0.0) * fps for c in targets)]
    lo, hi = int(round(2.2 * fps)) + READY_HALF + 1, int(round(0.8 * fps)) + 1

    def in_reach(f) -> bool:
        return targets is None or any(i - lo <= f <= i + hi for i in kept)
    run.stats["impacts"], run.stats["kept_impacts"] = len(impacts), len(kept)
    if rackets and impacts and kept:
        rcache = cache.with_name(cache.stem + "_rackets.npz")
        # the racket outline (slow model) from the backswing to the finish, one frame in two at
        # 50-60 fps: the racket keypoints and the face need it there, not all over the window
        step = 2 if fps >= 40 else 1
        need = sorted({f for imp in impacts
                       for f in range(max(0, imp.frame - int(0.7 * fps)), min(T, imp.frame + int(0.5 * fps) + 1), step)
                       if in_reach(f)})
        rd = load_npz(rcache)
        if rd is None or not set(need) <= set(rd["frames"].tolist()):
            from .pose.yolo import extract_rackets
            log(f"segmentando la raqueta en {len(need)} fotogramas")
            t_ = time.time()
            extract_rackets(video, need, rcache, imgsz=imgsz)
            timing["raqueta"] = time.time() - t_
            run.stats["racket_frames"] = len(need)
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
            # how well the ball was followed where its bounce is looked for: with no bounce found, it says
            # whether there was none (a volley) or the tracker lost it (situations.py)
            from .ball import seen_before
            share, gap = seen_before(ball_track[:n], imp.frame, fps, prev_ball[-1] if prev_ball else None)
            if share is not None:
                r.metrics["ball_seen_pre_share"], r.metrics["ball_gap_pre_s"] = share, gap
            if b is not None:
                r.ball = {"bounce_px": [round(b.x, 1), round(b.y, 1)], "bounce_frame": b.frame}
                r.metrics["bounce_to_impact_s"] = round((imp.frame - b.frame) / fps, 3)
                from .technique import half_volley       # the same rule as the class «media volea»
                if half_volley(r.metrics["bounce_to_impact_s"], r.metrics.get("contact_height_pct")):
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
    if rackets and run.strokes:
        _racket_at_ready(run, video, cache, imgsz, height_m, timing, in_reach)
    return run


READY_HALF = 4          # frames either side of the wait searched for the racket (±80 ms at 50 fps)


def _racket_at_ready(run: ClipRun, video: Path, cache: Path, imgsz: int, height_m: float, timing: dict,
                     in_reach=lambda f: True):
    """The racket outline is segmented from the backswing on; the wait (split step) usually comes
    earlier. Only the frames around each stroke's wait are added (±READY_HALF, a separate cache),
    so the racket and its face are known there too without segmenting the whole approach.
    in_reach(frame): frames a stroke that can be kept may read (run_clip's targets)."""
    import time
    from .racket import pick_racket, racket_from_polygon

    T = len(run.img)
    strokes = run.strokes
    want = sorted({f for s in strokes for r0 in [(s.phases.get("ready") or {}).get("frame")] if r0 is not None
                   for f in range(r0 - READY_HALF, r0 + READY_HALF + 1) if 0 <= f < T and not len(run.rackets[f])
                   and in_reach(f)})
    if not want:
        return
    rcache = cache.with_name(cache.stem + "_rackets_ready.npz")
    rd = load_npz(rcache)
    if rd is None or not set(want) <= set(rd["frames"].tolist()):
        from .pose.yolo import extract_rackets
        t_ = time.time()
        old = {} if rd is None else {int(f): p for f, p in zip(rd["frames"], rd["polys"])}
        extract_rackets(video, sorted(set(want) | set(old)), rcache, imgsz=imgsz)
        timing["raqueta"] = timing.get("raqueta", 0.0) + time.time() - t_
        rd = load_npz(rcache)
    if rd is None:
        return
    for f, p in zip(rd["frames"], rd["polys"]):
        if 0 <= int(f) < T and not len(run.rackets[int(f)]):
            run.rackets[int(f)] = p
    dw = run.sk["dom_wrist"]
    for s in strokes:
        f = (s.phases.get("ready") or {}).get("frame")
        if f is None or (s.racket.get("ready") or {}).get("detected"):
            continue
        poly = pick_racket(run.rackets[f], run.img[f, dw], max_dist=0.25 * run.height_px)
        obs = racket_from_polygon(poly, run.img[f, dw]) if poly is not None else None
        if obs is None:
            continue
        h = float(run.height_t[f]) if run.height_t is not None and np.isfinite(run.height_t[f]) else run.height_px
        above = (run.img[f, dw, 1] - obs.head[1]) / h * height_m * 100
        el = obs.elevation_deg
        s.racket["ready"] = dict(detected=True, elevation_deg=round(float(el), 1), head_above_wrist_cm=round(float(above), 1))
        t_rel = round((f - s.impact_frame) / run.fps, 3)
        for e in s.racket_track:
            if e[0] == t_rel and e[1] is None:
                e[1], e[2] = round(float(el), 1), round(float(above), 1)
