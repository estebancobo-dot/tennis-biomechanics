"""Pipeline stages for a full match (see tennisbio.pipeline for the incremental machinery).

probe → scenes (cuts, main camera) → audio (impact transients) → players (cheap pose on main-camera
frames) → candidates (near-player strokes) → fine (full-quality analysis in ±1 s windows).
"""
import json
import subprocess
from pathlib import Path

import numpy as np

from .impacts import audio_onsets, swing_peaks
from .io.video import probe, read_frames
from .kinematics import body_height, clean, speed, to_body_frame
from .pipeline import Context, stage
from .scenes import analyse_video
from .skeleton import Skeleton
from .tracking import track_target


def _write(path: Path, obj):
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=float), encoding="utf-8")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@stage("probe", "1")
def st_probe(ctx: Context):
    info = probe(ctx.match.video)
    d = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(info).items()}
    _write(ctx.path("probe.json"), d)
    return {"duration_min": round(info.duration / 60, 1), "fps": info.fps, "size": f"{info.width}x{info.height}"}


@stage("scenes", "1", deps=("probe",), settings=lambda c: {"fps": c["cheap_pass"]["fps"]})
def st_scenes(ctx: Context):
    fps = ctx.cfg["cheap_pass"]["fps"]
    info = probe(ctx.match.video)
    shots, mask = analyse_video(read_frames(info, width=160, fps=fps, hwaccel=ctx.cfg.get("hwaccel")))
    _write(ctx.path("scenes.json"), {"fps": fps, "shots": [vars(s) for s in shots]})
    main = [s for s in shots if s.main_camera]
    return {"shots": len(shots), "main_camera_shots": len(main),
            "main_camera_min": round(sum(s.end - s.start for s in main) / fps / 60, 1)}


@stage("audio", "1", deps=("probe",))
def st_audio(ctx: Context, chunk_s=300.0, overlap_s=1.0):
    """Impact-like transients over the whole match, in 5-minute chunks (memory stays small)."""
    info = probe(ctx.match.video)
    sr, times, strengths = 22050, [], []
    t = 0.0
    while t < info.duration:
        dur = min(chunk_s + overlap_s, info.duration - t)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-t", f"{dur:.3f}", "-i", str(ctx.match.video),
                              "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "pipe:1"], capture_output=True).stdout
        y = np.frombuffer(raw, np.float32)
        if len(y) > sr:
            on, st = audio_onsets(y, sr)
            keep = on < chunk_s if t + chunk_s < info.duration else np.ones(len(on), bool)
            times += list(on[keep] + t)
            strengths += list(st[keep])
        t += chunk_s
    _write(ctx.path("audio_onsets.json"), {"t": times, "strength": strengths})
    return {"onsets": len(times)}


def _pose_detector(cfg: dict):
    """frame → (boxes (N,4), keypoints (N,17,2), conf (N,17)) with the YOLO pose model."""
    from ultralytics import YOLO

    model = YOLO(cfg.get("yolo_pose", "yolo11m-pose.pt"))
    imgsz = cfg["cheap_pass"].get("imgsz", 960)

    def detect(frame):
        r = model.predict(frame, imgsz=imgsz, conf=0.3, verbose=False)[0]
        if not len(r.boxes):
            return np.zeros((0, 4)), np.zeros((0, 17, 2)), np.zeros((0, 17))
        return r.boxes.xyxy.cpu().numpy(), r.keypoints.xy.cpu().numpy(), r.keypoints.conf.cpu().numpy()
    return detect


@stage("players", "1", deps=("scenes",), settings=lambda c: {"fps": c["cheap_pass"]["fps"], "imgsz": c["cheap_pass"].get("imgsz", 960)})
def st_players(ctx: Context):
    """Cheap pose on main-camera frames only (cheap fps, full width for small players)."""
    from .pose.yolo import _objects, appearance

    sc = _read(ctx.path("scenes.json"))
    fps = sc["fps"]
    main = np.zeros(max([s["end"] for s in sc["shots"]] + [0]), bool)
    for s in sc["shots"]:
        main[s["start"]:s["end"]] = s["main_camera"]
    detect = _pose_detector(ctx.cfg)
    info = probe(ctx.match.video)
    boxes, kps, confs, feats, idx = [], [], [], [], []
    for i, frame in enumerate(read_frames(info, fps=fps, hwaccel=ctx.cfg.get("hwaccel"))):
        if i >= len(main) or not main[i]:
            continue
        b, k, c = detect(frame)
        boxes.append(b.astype(np.float32)); kps.append(k.astype(np.float32)); confs.append(c.astype(np.float32))
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
        idx.append(i)
    np.savez_compressed(ctx.path("players.npz"), fps=fps, frames=np.array(idx), height=info.height,
                        boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs), feats=_objects(feats))
    return {"frames": len(idx)}


def near_runs(d, sk):
    """Each continuous run of main-camera frames with the near player tracked (cuts break tracking).

    Yields (run indices, cleaned keypoints, confidences, body height px, mean appearance)."""
    fps, frames = float(d["fps"]), d["frames"]
    runs = np.split(np.arange(len(frames)), np.flatnonzero(np.diff(frames) > 1) + 1)
    for run in runs:
        if len(run) < fps:
            continue
        bx = [d["boxes"][k] for k in run]
        first = next((k for k in range(len(bx)) if len(bx[k])), None)
        if first is None:
            continue
        b0 = bx[first]
        h0 = b0[:, 3] - b0[:, 1]
        cand = np.flatnonzero(h0 >= 0.5 * h0.max())
        init = b0[cand[np.argmax(b0[cand, 3])]]
        feats = [d["feats"][k] for k in run]
        sel = track_target(bx, feats, init, min_bottom=float(0.5 * init[3]))
        kp = np.full((len(run), 17, 2), np.nan)
        cf = np.zeros((len(run), 17))
        app = []
        for t, j in enumerate(sel):
            if j >= 0:
                kp[t], cf[t] = d["kps"][run[t]][j], d["confs"][run[t]][j]
                app.append(feats[t][j])
        img = clean(kp, cf, max_gap=2, window=5)
        if np.isnan(img).all() or not app:
            continue
        yield run, img, cf, body_height(img, sk), np.mean(app, axis=0)


@stage("identity", "1", deps=("players", "score"))
def st_identity(ctx: Context):
    """Is the near player the target in each run? Clothing clusters + serves + scoreboard marker."""
    from .identity import assign, cluster_two, near_serves

    d = np.load(ctx.path("players.npz"), allow_pickle=True)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    score = _read(ctx.path("score.json"))
    runs, feats, votes = [], [], []
    for run, img, cf, h, app in near_runs(d, sk):
        i = len(runs)
        runs.append({"start": int(frames[run[0]]), "end": int(frames[run[-1]]) + 1})
        feats.append(app)
        f = near_serves(img, cf, fps, h)
        if f is not None:
            sr = score_at(score, frames[run[f]] / fps, max_age_s=25.0)
            if sr is not None and sr.get("server") is not None:
                votes.append((i, sr["server"] == 0))
                runs[i]["serve_vote"] = sr["server"] == 0
    labels = cluster_two(np.array(feats)) if feats else np.zeros(0, int)
    res = assign(labels, votes)
    for r, lab in zip(runs, labels):
        r["cluster"] = int(lab)
        r["near_is_target"] = None if res["target_cluster"] is None else bool(lab == res["target_cluster"])
    _write(ctx.path("identity.json"), {"fps": fps, **res, "runs": runs})
    return {"runs": len(runs), "votes": res["votes"], "confidence": res["confidence"],
            "decided": res["target_cluster"] is not None}


def near_is_target(identity: dict, frame: int):
    for r in identity.get("runs", []):
        if r["start"] <= frame < r["end"]:
            return r.get("near_is_target")
    return None


@stage("candidates", "4", deps=("players", "audio", "identity"))
def st_candidates(ctx: Context, tol_s=0.35):
    """Near-player stroke candidates: swing peaks of the near player at cheap fps, confirmed by
    an audio transient when one is close. Each candidate records who the near player is
    (identity: True target, False opponent, None undecided); the fine passes pick their own.
    Each candidate is checked again in the fine pass."""
    d = np.load(ctx.path("players.npz"), allow_pickle=True)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    onsets = np.array(_read(ctx.path("audio_onsets.json"))["t"])
    identity = _read(ctx.path("identity.json"))
    cands, skipped = [], 0
    for run, img, cf, h, _ in near_runs(d, sk):
        who = near_is_target(identity, int(frames[run[0]]))
        skipped += who is False
        v = speed(to_body_frame(img, sk, h)[:, sk["dom_wrist"]], fps)
        near_t = []
        for p in swing_peaks(v, fps, min_gap=1.0, height=1.5, prominence=1.0):
            t = frames[run[p]] / fps
            near = onsets[np.abs(onsets - t) <= tol_s] if len(onsets) else []
            near_t.append(t)
            cands.append({"t": float(near[np.argmin(np.abs(near - t))]) if len(near) else float(t),
                          "audio": bool(len(near)), "wrist_peak_t": float(t), "side": "near",
                          "identity": who, "target": who})
        if who is None or not len(onsets):
            continue
        # the far player's hits: impact sounds of this run that are not the near player's; the
        # fine pass keeps only those confirmed by the ball turning at the far player
        t0, t1 = frames[run[0]] / fps, frames[run[-1]] / fps
        last = -9.0
        for t in onsets[(onsets >= t0 + 0.5) & (onsets <= t1 - 0.5)]:
            if any(abs(t - x) <= 0.5 for x in near_t) or t - last < 1.0:
                continue
            last = t
            cands.append({"t": float(t), "audio": True, "side": "far", "identity": who, "target": not who})
    _write(ctx.path("candidates.json"), cands)
    return {"candidates": len(cands), "far": sum(c["side"] == "far" for c in cands),
            "with_audio": sum(c["audio"] for c in cands),
            "opponent_runs": skipped, "identity_unknown": sum(c["identity"] is None for c in cands)}


def grab_frame(video: Path, t: float) -> np.ndarray | None:
    """One full-resolution BGR frame at time t (fast seek)."""
    import cv2

    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "pipe:1"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


@stage("court", "1", deps=("scenes",))
def st_court(ctx: Context, n_fit=6, min_score=0.5):
    """Court homography of the main camera: fitted on a few long main-camera shots, the best one
    is checked on every main-camera shot (the broadcast camera barely moves); shots where it does
    not fit get their own fit."""
    from .court import CourtFit, camera_pitch_deg, fit_court, score_homography, white_lines

    sc = _read(ctx.path("scenes.json"))
    fps = sc["fps"]
    main = [s for s in sc["shots"] if s["main_camera"]]
    if not main:
        _write(ctx.path("court.json"), {"shots": []})
        return {"main_camera_shots": 0}
    mid = lambda s: (s["start"] + s["end"]) / 2 / fps
    best = None
    for s in sorted(main, key=lambda s: s["start"] - s["end"])[:n_fit]:          # longest first
        fr = grab_frame(ctx.match.video, mid(s))
        fit = fit_court(fr) if fr is not None else None
        if fit is not None and (best is None or fit.score > best[0].score):
            best = (fit, fr.shape)
    out = []
    for s in main:
        fr = grab_frame(ctx.match.video, mid(s))
        if fr is None:
            continue
        fit, score = best[0] if best else None, 0.0
        if fit is not None:
            score = score_homography(fit.H, white_lines(fr))
        if score < min_score:
            own = fit_court(fr)
            fit, score = (own, own.score) if own is not None else (None, 0.0)
        out.append({"start": s["start"], "end": s["end"], "score": round(score, 3),
                    "H": None if fit is None or score < min_score else fit.H.tolist(),
                    "pitch_deg": None if fit is None or score < min_score else round(camera_pitch_deg(fit, fr.shape), 1)})
    _write(ctx.path("court.json"), {"fps": fps, "shots": out})
    ok = [o for o in out if o["H"] is not None]
    return {"main_camera_shots": len(out), "with_court": len(ok),
            "pitch_deg_median": float(np.median([o["pitch_deg"] for o in ok])) if ok else None}


def _surname(name: str) -> str:
    return name.strip().split()[-1] if name and name.strip() else ""


@stage("score", "1", deps=("scenes",), settings=lambda c: {"every_s": (c.get("score") or {}).get("every_s", 5.0)})
def st_score(ctx: Context):
    """TV scoreboard every few seconds of main camera (sets, games, points, pressure)."""
    sc = _read(ctx.path("scenes.json"))
    fps, every = sc["fps"], (ctx.cfg.get("score") or {}).get("every_s", 5.0)
    try:
        from .scoreboard import ScoreReader, discover_opponent
    except ImportError:
        _write(ctx.path("score.json"), {"readings": [], "note": "uv sync --extra ocr"})
        return {"readings": 0, "note": "sin OCR instalado"}
    mains = [s for s in sc["shots"] if s["main_camera"]]
    opponent = _surname(ctx.match.opponent)
    if not opponent and mains:       # not in matches.yaml: read it from the scoreboard
        times = [((s["start"] + s["end"]) / 2) / fps for s in mains[:: max(1, len(mains) // 40)]]
        opponent = discover_opponent((f for f in (grab_frame(ctx.match.video, t) for t in times) if f is not None),
                                     _surname(ctx.match.player.name)) or ""
    names = (_surname(ctx.match.player.name), opponent)
    if not all(names):
        _write(ctx.path("score.json"), {"readings": [], "note": "no se encontró el nombre del rival en el marcador"})
        return {"readings": 0}
    reader, out = ScoreReader(*names), []
    for s in sc["shots"]:
        if not s["main_camera"]:
            continue
        t = s["start"] / fps + 0.5
        while t < s["end"] / fps:
            fr = grab_frame(ctx.match.video, t)
            st = reader.read(fr) if fr is not None else None
            if st is not None:
                out.append({"t": round(t, 2), **st.to_dict()})
            t += every
    _write(ctx.path("score.json"), {"readings": out, "names": names, "opponent": opponent})
    return {"readings": len(out), "pressure": sum(r["pressure"] for r in out)}


def score_at(score: dict, t: float, max_age_s=40.0):
    """The latest scoreboard reading before time t (within max_age_s), or None."""
    best = None
    for r in score.get("readings", []):
        if r["t"] <= t + 1.0 and t - r["t"] <= max_age_s:
            best = r
    return best


def court_at(court: dict, t: float):
    """(H court→image, pitch) of the main-camera shot containing time t, or (None, None)."""
    f = t * court.get("fps", 1)
    for o in court.get("shots", []):
        if o["start"] <= f < o["end"] and o["H"] is not None:
            return np.array(o["H"]), o["pitch_deg"]
    return None, None


def far_start(clip: Path, H, search_s=2.0, step=5) -> dict | None:
    """Where the far player is near the start of a window: people found in the far half of the
    court (enlarged region) in the first frames (she may be blurred in a serve jump), the one
    standing in it; plus the net row that she never crosses."""
    if H is None:
        return None
    from .court_metrics import net_row
    from .pose.yolo import find_far_player

    found = find_far_player(clip, H, search_s, step)
    return None if found is None else dict(roi="follow", init_box=found, max_bottom=net_row(H))


def cut_window(video: Path, t0: float, dur: float, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "aac", str(dest)], check=True)
    return dest


def _fine_settings(c):
    return {"fine": c["fine_pass"], "imgsz": c.get("fine_imgsz", 1280), "ball": c.get("ball"),
            "racket_face": c.get("racket_face")}


@stage("fine", "6", deps=("candidates", "court", "score"), settings=_fine_settings)
def st_fine(ctx: Context):
    """Full-quality analysis of the target player's candidates (and undecided ones)."""
    # near strokes of the target and undecided runs; far strokes only when she is known to be far
    return _fine(ctx, ctx.match.player, lambda c: c.get("target", c.get("identity")) is not False
                 and (c.get("side", "near") == "near" or c.get("target") is True), "strokes.json")


def opponent_profile(match):
    """The opponent's profile: config/players/<opponent_id>.yaml when given in matches.yaml."""
    from .catalog import Player, load_player

    oid = match.extra.get("opponent_id")
    if oid:
        return load_player(oid)
    return Player(id="opponent", name=match.opponent or "Rival", hand=match.extra.get("opponent_hand", "right"))


@stage("fine_opponent", "2", deps=("candidates", "court", "score"),
       settings=lambda c: {**_fine_settings(c), "enabled": c.get("analyze_opponent", False)})
def st_fine_opponent(ctx: Context):
    """The opponent's strokes from the same video (runs where the near player is the opponent).
    Off unless `analyze_opponent: true` in the config."""
    if not ctx.cfg.get("analyze_opponent", False):
        _write(ctx.path("strokes_opponent.json"), [])
        return {"enabled": False}
    return _fine(ctx, opponent_profile(ctx.match), lambda c: c.get("target", c.get("identity")) is False,
                 "strokes_opponent.json")


def _fine(ctx: Context, p, keep, out_name: str):
    """Full-quality analysis of each kept candidate in its own window (same code as analyze_clip)."""
    from .clip_pipeline import run_clip

    cands = _read(ctx.path("candidates.json"))
    court = _read(ctx.path("court.json"))
    score = _read(ctx.path("score.json"))
    ball = None
    bcfg = ctx.cfg.get("ball") or {}
    if bcfg.get("onnx") and Path(bcfg["onnx"]).exists():
        from .ball import BallTracker
        ball = BallTracker(bcfg["onnx"], ctx.cfg.get("device", "cpu"), bcfg.get("threshold", 0.5))
    pre, post = ctx.cfg["fine_pass"]["window_s"] + 0.3, ctx.cfg["fine_pass"]["window_s"]
    if ball is not None:      # reach back to the opponent's hit (time available, split step) and
        pre = max(pre, ctx.cfg["fine_pass"].get("ball_lead_s", 2.2))       # forward to where her shot lands
        post = max(post, ctx.cfg["fine_pass"].get("ball_tail_s", 1.4))
    fcfg = ctx.cfg.get("racket_face") or {}
    rpose = wb3d = None
    if fcfg.get("enabled", True):
        if fcfg.get("pose_onnx") and Path(fcfg["pose_onnx"]).exists():
            from .racket_pose import RacketPose
            rpose = RacketPose(fcfg["pose_onnx"], ctx.cfg.get("device", "cpu"))
        if fcfg.get("hand3d_onnx") and Path(fcfg["hand3d_onnx"]).exists():
            from .pose.wholebody3d import WholeBody3D
            wb3d = WholeBody3D(fcfg["hand3d_onnx"], ctx.cfg.get("device", "cpu"))
    strokes = []
    for k, c in enumerate(cands):
        if not keep(c):
            continue
        t0 = max(0.0, c["t"] - pre)
        # the name carries the interval, so a different window never reuses an old cut (or its caches)
        clip = cut_window(ctx.match.video, t0, pre + post, ctx.path("windows") / f"w{k:04d}_{int(t0 * 1000)}_{int((pre + post) * 1000)}.mp4")
        side = c.get("side", "near")
        extra, cache = {}, clip.with_suffix(".npz")
        if side == "far":
            fi = far_start(clip, court_at(court, c["t"])[0])
            if fi is None:
                continue                          # no court or no far player found: nothing reliable
            extra, cache = dict(side="far", **fi), clip.with_name(clip.stem + "_far.npz")
        run = run_clip(clip, cache, p.hand, p.height_m, init_mode="near", rackets=side == "near",
                       imgsz=ctx.cfg.get("fine_imgsz", 1280), log=lambda *_: None, ball=ball, **extra)
        if side == "far":                         # far strokes count only when the ball confirms them
            run.strokes = [s for s in run.strokes if "ball" in s.impact_source]
        if not run.strokes:
            continue
        target = (c["t"] - t0) * run.fps
        r = min(run.strokes, key=lambda s: abs(s.impact_frame - target))
        if abs(r.impact_frame - target) > 0.4 * run.fps:
            continue                              # the fine pass did not confirm this candidate
        d = r.to_dict()
        t_imp = t0 + r.impact_frame / run.fps
        d.update(window=str(clip.name), window_start_s=t0, match_time_s=t_imp, candidate_audio=c["audio"])
        sr = score_at(score, t_imp)
        if sr is not None:
            d["score"] = {k: sr[k] for k in ("games", "points", "banner", "set", "sets_won", "tiebreak", "pressure")}
        H, pitch = court_at(court, t_imp)
        d["side"] = side
        H_img = H
        if H is not None:
            from .court_metrics import player_frame_H
            H = player_frame_H(H, side)            # her own court frame at either end
        if H is not None:
            from .court_metrics import court_metrics
            ta = r.metrics.get("time_available_s")
            opp = None if ta is None else r.impact_frame - int(round(ta * run.fps))
            d.update(court_metrics(run.img, run.sk, H, r.stroke, r.impact_frame, opp), camera_pitch_deg=pitch)
            if r.stroke == "overhead":                  # landing after the serve: how far into the court
                from .court_metrics import feet_on_court
                ft = feet_on_court(run.img, min(len(run.img) - 1, r.impact_frame + int(0.4 * run.fps)), run.sk, H)
                if ft is not None:
                    d["landing_inside_m"] = round(float((ft[0][1] + ft[1][1]) / 2), 2)
            if r.ball.get("shot_bounce_candidates"):   # where her shot landed on the far court
                from .court_metrics import shot_landing
                d.update(shot_landing(H, r.ball["shot_bounce_candidates"], (d.get("court_pos_m") or [None])[0],
                                      run.fps, r.impact_frame))
            if r.ball.get("bounce_px"):          # on the ground: the homography is exact there
                from .court_metrics import to_court
                bx, by = to_court(H, np.array([r.ball["bounce_px"]]))[0]
                if -1.5 <= by <= 11.885 and abs(bx) <= 6.5:
                    d["bounce_court_m"] = [round(float(bx), 2), round(float(by), 2)]
        from .series import stroke_series
        ser = stroke_series(run.img, run.conf, run.boxes, run.sk, run.fps, run.height_px, r.impact_frame,
                            r.racket_track, run.ball)
        if fcfg.get("enabled", True) and side == "near":      # strings: not measurable at the far end
            from .racket_orientation import stroke_faces
            grip = p.backhand_grip_close_deg if r.stroke == "backhand" else p.forehand_grip_close_deg
            faces = stroke_faces(clip, run, r, p.height_m, pitch if H_img is not None else None, rpose, wb3d,
                                 fcfg.get("hand3d_step", 2), grip)
            d["face"] = faces["phases"]
            d["metrics"].update(faces["trunk3d"])
            ser["face"] = {key: faces[key] for key in ("first", "tilt", "yaw", "label", "observed", "keypoints", "source", "hand3d", "rot3d")}
        sdir = ctx.path("series")
        sdir.mkdir(exist_ok=True)
        _write(sdir / f"w{k:04d}.json", ser)
        d.update(series=f"series/w{k:04d}.json", window_impact_s=r.impact_frame / run.fps)
        strokes.append(d)
    _write(ctx.path(out_name), strokes)
    return {"candidates": sum(map(keep, cands)), "confirmed": len(strokes),
            "forehands": sum(s["stroke"] == "forehand" for s in strokes)}
