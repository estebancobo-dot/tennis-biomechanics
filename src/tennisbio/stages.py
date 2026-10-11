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


@stage("candidates", "1", deps=("players", "audio"))
def st_candidates(ctx: Context, tol_s=0.35):
    """Near-player stroke candidates: swing peaks of the near player at cheap fps, confirmed by
    an audio transient when one is close. Each candidate is checked again in the fine pass."""
    d = np.load(ctx.path("players.npz"), allow_pickle=True)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    onsets = np.array(_read(ctx.path("audio_onsets.json"))["t"])
    cands = []
    # process each continuous run of main-camera frames separately (cuts break tracking)
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
        sel = track_target(bx, [d["feats"][k] for k in run], init, min_bottom=float(0.5 * init[3]))
        kp = np.full((len(run), 17, 2), np.nan)
        cf = np.zeros((len(run), 17))
        for t, j in enumerate(sel):
            if j >= 0:
                kp[t], cf[t] = d["kps"][run[t]][j], d["confs"][run[t]][j]
        img = clean(kp, cf, max_gap=2, window=5)
        if np.isnan(img).all():
            continue
        h = body_height(img, sk)
        v = speed(to_body_frame(img, sk, h)[:, sk["dom_wrist"]], fps)
        for p in swing_peaks(v, fps, min_gap=1.0, height=1.5, prominence=1.0):
            t = frames[run[p]] / fps
            near = onsets[np.abs(onsets - t) <= tol_s] if len(onsets) else []
            cands.append({"t": float(near[np.argmin(np.abs(near - t))]) if len(near) else float(t),
                          "audio": bool(len(near)), "wrist_peak_t": float(t)})
    _write(ctx.path("candidates.json"), cands)
    return {"candidates": len(cands), "with_audio": sum(c["audio"] for c in cands)}


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
    names = (_surname(ctx.match.player.name), _surname(ctx.match.opponent))
    if not all(names):
        _write(ctx.path("score.json"), {"readings": [], "note": "falta el nombre del rival en matches.yaml"})
        return {"readings": 0}
    try:
        from .scoreboard import ScoreReader
    except ImportError:
        _write(ctx.path("score.json"), {"readings": [], "note": "uv sync --extra ocr"})
        return {"readings": 0, "note": "sin OCR instalado"}
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
    _write(ctx.path("score.json"), {"readings": out, "names": names})
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


def cut_window(video: Path, t0: float, dur: float, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "aac", str(dest)], check=True)
    return dest


@stage("fine", "4", deps=("candidates", "court", "score"),
       settings=lambda c: {"fine": c["fine_pass"], "imgsz": c.get("fine_imgsz", 1280), "ball": c.get("ball"),
                           "racket_face": c.get("racket_face")})
def st_fine(ctx: Context):
    """Full-quality analysis of each candidate in its own window (same code as analyze_clip)."""
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
    if ball is not None:      # reach back to the opponent's hit (time available, split step)
        pre = max(pre, ctx.cfg["fine_pass"].get("ball_lead_s", 2.2))
    p = ctx.match.player
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
        t0 = max(0.0, c["t"] - pre)
        # the name carries the interval, so a different window never reuses an old cut (or its caches)
        clip = cut_window(ctx.match.video, t0, pre + post, ctx.path("windows") / f"w{k:04d}_{int(t0 * 1000)}_{int((pre + post) * 1000)}.mp4")
        run = run_clip(clip, clip.with_suffix(".npz"), p.hand, p.height_m, init_mode="near",
                       imgsz=ctx.cfg.get("fine_imgsz", 1280), log=lambda *_: None, ball=ball)
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
        if H is not None:
            from .court_metrics import court_metrics
            ta = r.metrics.get("time_available_s")
            opp = None if ta is None else r.impact_frame - int(round(ta * run.fps))
            d.update(court_metrics(run.img, run.sk, H, r.stroke, r.impact_frame, opp), camera_pitch_deg=pitch)
        from .series import stroke_series
        ser = stroke_series(run.img, run.conf, run.boxes, run.sk, run.fps, run.height_px, r.impact_frame,
                            r.racket_track, run.ball)
        if fcfg.get("enabled", True):
            from .racket_orientation import stroke_faces
            faces = stroke_faces(clip, run, r, p.height_m, pitch if H is not None else None, rpose, wb3d,
                                 fcfg.get("hand3d_step", 2), p.forehand_grip_close_deg)
            d["face"] = faces["phases"]
            d["metrics"].update(faces["trunk3d"])
            ser["face"] = {key: faces[key] for key in ("first", "tilt", "yaw", "label", "observed", "keypoints", "source", "hand3d", "rot3d")}
        sdir = ctx.path("series")
        sdir.mkdir(exist_ok=True)
        _write(sdir / f"w{k:04d}.json", ser)
        d.update(series=f"series/w{k:04d}.json", window_impact_s=r.impact_frame / run.fps)
        strokes.append(d)
    _write(ctx.path("strokes.json"), strokes)
    return {"candidates": len(cands), "confirmed": len(strokes),
            "forehands": sum(s["stroke"] == "forehand" for s in strokes)}
