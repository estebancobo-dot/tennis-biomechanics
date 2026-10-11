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


def cut_window(video: Path, t0: float, dur: float, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "aac", str(dest)], check=True)
    return dest


@stage("fine", "1", deps=("candidates",), settings=lambda c: {"fine": c["fine_pass"], "imgsz": c.get("fine_imgsz", 1280)})
def st_fine(ctx: Context):
    """Full-quality analysis of each candidate in its own window (same code as analyze_clip)."""
    from .clip_pipeline import run_clip

    cands = _read(ctx.path("candidates.json"))
    pre, post = ctx.cfg["fine_pass"]["window_s"] + 0.3, ctx.cfg["fine_pass"]["window_s"]
    p = ctx.match.player
    strokes = []
    for k, c in enumerate(cands):
        t0 = max(0.0, c["t"] - pre)
        clip = cut_window(ctx.match.video, t0, pre + post, ctx.path("windows") / f"w{k:04d}.mp4")
        run = run_clip(clip, clip.with_suffix(".npz"), p.hand, p.height_m, init_mode="near",
                       imgsz=ctx.cfg.get("fine_imgsz", 1280), log=lambda *_: None)
        if not run.strokes:
            continue
        target = (c["t"] - t0) * run.fps
        r = min(run.strokes, key=lambda s: abs(s.impact_frame - target))
        if abs(r.impact_frame - target) > 0.4 * run.fps:
            continue                              # the fine pass did not confirm this candidate
        d = r.to_dict()
        d.update(window=str(clip.name), window_start_s=t0, match_time_s=t0 + r.impact_frame / run.fps,
                 candidate_audio=c["audio"])
        strokes.append(d)
    _write(ctx.path("strokes.json"), strokes)
    return {"candidates": len(cands), "confirmed": len(strokes),
            "forehands": sum(s["stroke"] == "forehand" for s in strokes)}
