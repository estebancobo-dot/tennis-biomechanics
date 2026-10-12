"""Pipeline stages for a full match (see tennisbio.pipeline for the incremental machinery).

probe → scenes (cuts, main camera) → audio (impact transients) → players (cheap pose on main-camera
frames) → candidates (near-player strokes) → fine (full-quality analysis in ±1 s windows).
"""
import hashlib
import json
import os
import subprocess
import traceback
from pathlib import Path

import numpy as np

from .impacts import audio_onsets, swing_peaks
from .io.video import probe, read_frames
from .kinematics import body_height, clean, speed, to_body_frame
from .config import model_state, resolve_path
from .pipeline import Context, savez_atomic, stage, write_atomic
from .scenes import analyse_video
from .skeleton import Skeleton
from .tracking import track_target


def _write(path: Path, obj):
    write_atomic(path, json.dumps(obj, indent=1, ensure_ascii=False, default=float))


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@stage("probe", "1", outputs=("probe.json",))
def st_probe(ctx: Context):
    info = probe(ctx.match.video)
    d = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(info).items()}
    _write(ctx.path("probe.json"), d)
    return {"duration_min": round(info.duration / 60, 1), "fps": info.fps, "size": f"{info.width}x{info.height}"}


@stage("scenes", "1", deps=("probe",), settings=lambda c: {"fps": c["cheap_pass"]["fps"]}, outputs=("scenes.json",))
def st_scenes(ctx: Context):
    fps = ctx.cfg["cheap_pass"]["fps"]
    info = probe(ctx.match.video)
    shots, mask = analyse_video(read_frames(info, width=160, fps=fps, hwaccel=ctx.cfg.get("hwaccel")))
    _write(ctx.path("scenes.json"), {"fps": fps, "shots": [vars(s) for s in shots]})
    main = [s for s in shots if s.main_camera]
    return {"shots": len(shots), "main_camera_shots": len(main),
            "main_camera_min": round(sum(s.end - s.start for s in main) / fps / 60, 1)}


@stage("audio", "1", deps=("probe",), outputs=("audio_onsets.json",))
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


@stage("players", "1", deps=("scenes",), settings=lambda c: {"fps": c["cheap_pass"]["fps"], "imgsz": c["cheap_pass"].get("imgsz", 960)},
       outputs=("players.npz",))
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
    savez_atomic(ctx.path("players.npz"), fps=fps, frames=np.array(idx), height=info.height,
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


@stage("identity", "2", deps=("players", "score"), outputs=("identity.json",), match_fields=lambda m: {"player": m.player.name})
def st_identity(ctx: Context):
    """Is the near player the target in each run? Clothing clusters + serves + scoreboard marker."""
    from .identity import assign, cluster_two, decide_by_ends, end_changes, near_serves

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
    # end changes from the scoreboard at the middle of each run
    parities = []
    for r in runs:
        sr = score_at(score, (r["start"] + r["end"]) / 2 / fps, max_age_s=150.0)
        parities.append(None if sr is None else end_changes(sr.get("games"), sr.get("points"), sr.get("tiebreak", False)))
    base = decide_by_ends(parities, votes)
    by_ends = by_clothes = conflicts = 0
    for r, lab, par in zip(runs, labels, parities):
        r["cluster"] = int(lab)
        r["end_changes"] = par
        a_cl = None if res["target_cluster"] is None else bool(lab == res["target_cluster"])
        a_end = None if base is None or par is None else bool(base ^ bool(par % 2))
        if a_cl is not None and a_end is not None and a_cl != a_end:
            r["near_is_target"], r["method"] = None, "conflicto"
            conflicts += 1
        elif a_end is not None:
            r["near_is_target"], r["method"] = a_end, "cambios de lado"
            by_ends += 1
        else:
            r["near_is_target"], r["method"] = a_cl, None if a_cl is None else "ropa"
            by_clothes += a_cl is not None
    _write(ctx.path("identity.json"), {"fps": fps, **res, "ends_base": base, "runs": runs})
    return {"runs": len(runs), "votes": res["votes"], "confidence": res["confidence"],
            "by_end_changes": by_ends, "by_clothes": by_clothes, "conflicts": conflicts,
            "decided": sum(r["near_is_target"] is not None for r in runs)}


def near_is_target(identity: dict, frame: int):
    for r in identity.get("runs", []):
        if r["start"] <= frame < r["end"]:
            return r.get("near_is_target")
    return None


@stage("candidates", "5", deps=("players", "audio", "identity", "court", "score"), outputs=("candidates.json",))
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
    # doubles are out of scope: two people inside the near half in most main-camera frames
    from .court_metrics import people_in_near_half
    court = _read(ctx.path("court.json"))
    counts = []
    for i in range(0, len(frames), 10):
        H, _ = court_at(court, frames[i] / fps)
        if H is not None:
            counts.append(people_in_near_half(d["boxes"][i], H))
    if counts and np.mean(np.array(counts) >= 2) >= 0.5:
        _write(ctx.path("candidates.json"), [])
        ctx.log("  AVISO: parece un partido de dobles (dos jugadores en la mitad cercana); no se analiza")
        return {"candidates": 0, "doubles": True}
    cands, skipped, replays = [], 0, 0
    score = _read(ctx.path("score.json")) if ctx.path("score.json").exists() else {}
    no_board = [(x["start"], x["end"]) for x in score.get("shots", [])
                if x["tried"] >= 2 and x["read"] == 0 and x["end"] - x["start"] < 30]
    board_works = sum(x["read"] for x in score.get("shots", [])) >= 10
    for run, img, cf, h, _ in near_runs(d, sk):
        t_mid = frames[run[len(run) // 2]] / fps
        if board_works and any(a <= t_mid < b for a, b in no_board):
            replays += 1                  # probably a replay: its strokes were already counted live
            continue
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
            "opponent_runs": skipped, "identity_unknown": sum(c["identity"] is None for c in cands),
            "replay_runs_skipped": replays}


def grab_frame(video: Path, t: float) -> np.ndarray | None:
    """One full-resolution BGR frame at time t (fast seek)."""
    import cv2

    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "pipe:1"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


@stage("court", "1", deps=("scenes",), outputs=("court.json",))
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


@stage("score", "3", deps=("scenes",), settings=lambda c: {"every_s": (c.get("score") or {}).get("every_s", 5.0)},
       outputs=("score.json",), match_fields=lambda m: {"player": m.player.name, "opponent": m.opponent})
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
    reader, out, shots = ScoreReader(*names), [], []
    for s in sc["shots"]:
        if not s["main_camera"]:
            continue
        t = s["start"] / fps + 0.5
        tried = read = 0
        while t < s["end"] / fps:
            fr = grab_frame(ctx.match.video, t)
            st = reader.read(fr) if fr is not None else None
            tried += 1
            if st is not None:
                read += 1
                out.append({"t": round(t, 2), **st.to_dict()})
            t += every
        # in live play the scoreboard is on screen; a main-camera-looking shot without it is
        # usually a replay (used later to drop duplicated strokes)
        shots.append({"start": s["start"] / fps, "end": s["end"] / fps, "tried": tried, "read": read})
    _write(ctx.path("score.json"), {"readings": out, "names": names, "opponent": opponent, "shots": shots})
    if not out:
        ctx.log(f"  AVISO: no se pudo leer el marcador con «{names[0]}» y «{names[1]}»: sin marcador no se sabe "
                f"quién está en cada lado; compruebe que el partido es de {ctx.match.player.name}")
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


def _valid_video(p: Path) -> bool:
    try:
        return probe(p).duration > 0.2
    except Exception:
        return False


def cut_window(video: Path, t0: float, dur: float, dest: Path, interlaced: bool = False) -> Path:
    """Re-encoded window of the match. Interlaced broadcasts (1080i) are deinterlaced to one frame
    per field (yadif=1): 50 sharp frames per second instead of 25 combed ones. Written through a
    temporary file and checked, so an interrupted cut is never reused."""
    if dest.exists() and _valid_video(dest):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".part" + dest.suffix)
    vf = ["-vf", "yadif=1"] if interlaced else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-i", str(video), "-t", f"{dur:.3f}", *vf,
                        # a keyframe every 8 frames: frame-by-frame scrubbing in the report stays instant;
                        # yuv420p: the only chroma format every browser plays (broadcasts can be 4:2:2)
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-g", "8", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", "-c:a", "aac", str(tmp)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not _valid_video(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"no se pudo recortar {dur:.1f} s en {t0:.1f} s del vídeo ({(r.stderr or '').strip()[-200:]})")
    os.replace(tmp, dest)
    return dest


def _fine_settings(c):
    rf = c.get("racket_face") or {}
    return {"fine": c["fine_pass"], "imgsz": c.get("fine_imgsz", 1280), "ball": c.get("ball"),
            "racket_face": rf, "include_undecided": c.get("include_undecided", False),
            # the models themselves: adding or replacing one re-runs the fine pass
            "models": {"ball": model_state((c.get("ball") or {}).get("onnx")), "racket": model_state(rf.get("pose_onnx")),
                       "hand3d": model_state(rf.get("hand3d_onnx")), "pose": c.get("yolo_pose", "yolo11m-pose.pt")}}


FINE_CODE = ("stages", "clip_pipeline", "stroke_analysis", "phases", "kinematics", "impacts", "ball", "court_metrics",
             "outcome", "series", "racket", "racket3d", "racket_face", "racket_orientation", "tracking", "technique",
             "footwork")


def _player_fields(p) -> dict:
    return {"hand": p.hand, "height_m": p.height_m, "backhand": getattr(p, "backhand", None),
            "grip": [getattr(p, "forehand_grip_close_deg", None), getattr(p, "backhand_grip_close_deg", None)]}


@stage("fine", "7", deps=("candidates", "court", "score"), settings=_fine_settings, outputs=("strokes.json",),
       code=FINE_CODE, match_fields=lambda m: _player_fields(m.player))
def st_fine(ctx: Context):
    """Full-quality analysis of the target player's candidates. Runs whose identity could not be
    decided are left out (they could be the opponent), unless `include_undecided: true`."""
    undecided = ctx.cfg.get("include_undecided", False)

    def keep(c):
        who = c.get("target", c.get("identity"))
        if c.get("side", "near") == "far":
            return who is True                    # far strokes only when she is known to be far
        return who is True or (undecided and who is None)
    return _fine(ctx, ctx.match.player, keep, "strokes.json")


def opponent_profile(match):
    """The opponent's profile: config/players/<opponent_id>.yaml when given in matches.yaml."""
    from .catalog import Player, load_player

    oid = match.extra.get("opponent_id")
    if oid:
        try:
            return load_player(oid)
        except FileNotFoundError:           # no profile yet: right-handed by default, named as in the catalog
            pass
    return Player(id="opponent", name=match.opponent or "Rival", hand=match.extra.get("opponent_hand", "right"))


@stage("fine_opponent", "3", deps=("candidates", "court", "score"),
       settings=lambda c: {**_fine_settings(c), "enabled": c.get("analyze_opponent", False)},
       outputs=("strokes_opponent.json",), code=FINE_CODE,
       match_fields=lambda m: {**_player_fields(opponent_profile(m)), "opponent": m.opponent})
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
    onsets = np.array(_read(ctx.path("audio_onsets.json"))["t"]) if ctx.path("audio_onsets.json").exists() else np.zeros(0)
    scenes = _read(ctx.path("scenes.json")) if ctx.path("scenes.json").exists() else {"fps": 1, "shots": []}
    ball, warnings = None, []
    bcfg = ctx.cfg.get("ball") or {}
    bpath = resolve_path(bcfg.get("onnx"))
    if bpath is not None and bpath.exists():
        from .ball import BallTracker
        ball = BallTracker(str(bpath), ctx.cfg.get("device", "cpu"), bcfg.get("threshold", 0.5))
    else:
        warnings.append("falta el modelo de bola (models/balltrack.onnx): la detección de golpes será mucho peor; "
                        "ejecuta 1_instalar.bat")
    pre, post = ctx.cfg["fine_pass"]["window_s"] + 0.3, ctx.cfg["fine_pass"]["window_s"]
    if ball is not None:      # reach back to the opponent's hit (time available, split step) and
        pre = max(pre, ctx.cfg["fine_pass"].get("ball_lead_s", 2.2))       # forward to where her shot lands
        post = max(post, ctx.cfg["fine_pass"].get("ball_tail_s", 1.4))
    fcfg = ctx.cfg.get("racket_face") or {}
    rpose = wb3d = None
    if fcfg.get("enabled", True):
        rp, hp = resolve_path(fcfg.get("pose_onnx")), resolve_path(fcfg.get("hand3d_onnx"))
        if rp is not None and rp.exists():
            from .racket_pose import RacketPose
            rpose = RacketPose(str(rp), ctx.cfg.get("device", "cpu"))
        else:
            warnings.append("falta el modelo de raqueta (models/racketpose.onnx): sin orientación de las cuerdas")
        if hp is not None and hp.exists():
            from .pose.wholebody3d import WholeBody3D
            wb3d = WholeBody3D(str(hp), ctx.cfg.get("device", "cpu"))
        else:
            warnings.append("falta el modelo 3D (models/rtmw3d-x.onnx): cuerdas y rotaciones sin 3D")
    for w in warnings:
        ctx.log(f"  AVISO: {w}")
    interlaced = bool(_read(ctx.path("probe.json")).get("interlaced")) if ctx.path("probe.json").exists() else False
    # caches of the pose, ball and racket of each window carry the models and settings that made them
    ph = hashlib.sha1(json.dumps([ctx.cfg.get("yolo_pose", "yolo11m-pose.pt"), ctx.cfg.get("fine_imgsz", 1280),
                                  model_state(bcfg.get("onnx")), "v2"]).encode()).hexdigest()[:8]
    strokes, errors = [], []
    kept = [(k, c) for k, c in enumerate(cands) if keep(c)]
    for n, (k, c) in enumerate(kept):
        if n and n % 20 == 0:
            ctx.log(f"  {n}/{len(kept)} golpes candidatos")
        try:
            d = _fine_one(ctx, p, c, pre, post, interlaced, ph, court, score, onsets, scenes, ball, rpose, wb3d, fcfg)
        except Exception as e:                    # one bad window never stops the match
            errors.append({"t": c["t"], "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]})
            continue
        if d is not None:
            strokes.append(d)
    _write(ctx.path(out_name), strokes)
    _write(ctx.path(out_name.replace(".json", "_errores.json")), errors)
    if errors:
        ctx.log(f"  {len(errors)} golpes no se pudieron analizar (detalle en {out_name.replace('.json', '_errores.json')})")
    return {"candidates": len(kept), "confirmed": len(strokes), "errors": len(errors), "warnings": warnings,
            "forehands": sum(s["stroke"] == "forehand" for s in strokes)}


def _fine_one(ctx, p, c, pre, post, interlaced, ph, court, score, onsets, scenes, ball, rpose, wb3d, fcfg):
    """One candidate: cut its window, pose, ball, phases, metrics, court, outcome, racket, series."""
    from .clip_pipeline import run_clip

    t0 = max(0.0, c["t"] - pre)
    # named by its interval (not by its position in the list): a new candidate elsewhere never
    # renames, and so never re-analyses, the existing windows
    wid = f"w{int(round(t0 * 1000)):09d}_{int((pre + post) * 1000)}"
    clip = cut_window(ctx.match.video, t0, pre + post, ctx.path("windows") / f"{wid}.mp4", interlaced)
    side = c.get("side", "near")
    extra, cache = {}, clip.with_name(f"{clip.stem}_{ph}.npz")
    if side == "far":
        fi = far_start(clip, court_at(court, c["t"])[0])
        if fi is None:
            return None                       # no court or no far player found: nothing reliable
        extra, cache = dict(side="far", **fi), clip.with_name(f"{clip.stem}_{ph}_far.npz")
    run = run_clip(clip, cache, p.hand, p.height_m, init_mode="near", rackets=side == "near",
                   imgsz=ctx.cfg.get("fine_imgsz", 1280), log=lambda *_: None, ball=ball, **extra)
    if side == "far":                         # far strokes count only when the ball confirms them
        run.strokes = [s for s in run.strokes if "ball" in s.impact_source]
    if not run.strokes:
        return None
    target = (c["t"] - t0) * run.fps
    r = min(run.strokes, key=lambda s: abs(s.impact_frame - target))
    if abs(r.impact_frame - target) > 0.4 * run.fps:
        return None                           # the fine pass did not confirm this candidate
    d = r.to_dict()
    t_imp = t0 + r.impact_frame / run.fps
    d.update(window=str(clip.name), window_start_s=t0, match_time_s=t_imp, candidate_audio=c.get("audio"),
             identity=c.get("identity"), target=c.get("target"), stroke_id=f"{ctx.match.id}-{int(round(t_imp * 100)):07d}")
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
        cm = court_metrics(run.img, run.sk, H, r.stroke, r.impact_frame, opp)
        if side == "far":       # ankles of a ~70 px player are too rough for stance and base width
            for k in ("stance", "stance_angle_deg", "stance_width_m"):
                cm.pop(k, None)
        d.update(cm, camera_pitch_deg=pitch)
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
    # what happened with the shot (out / net / probable winner / rally)
    from .outcome import crossed_net, shot_outcome
    sfps = scenes["fps"]
    shot_end = next((sh["end"] / sfps for sh in scenes["shots"]
                     if sh["main_camera"] and sh["start"] / sfps <= t_imp < sh["end"] / sfps), None)
    other = "far" if side == "near" else "near"
    ret = next((h.frame for h in getattr(run, "hits", []) if h.side == other and h.frame > r.impact_frame + 0.3 * run.fps), None)
    net_y = None
    if H_img is not None:
        from .court_metrics import net_row
        net_y = net_row(H_img)
    crossed = crossed_net(run.ball, r.impact_frame, run.fps, net_y, side) if net_y is not None else None
    b_t = None if d.get("impact_to_shot_bounce_s") is None else t_imp + d["impact_to_shot_bounce_s"]
    oc = shot_outcome(t_imp, d.get("shot_in"), b_t, None if ret is None else t0 + ret / run.fps,
                      onsets, shot_end, crossed)
    if oc is not None:
        d["outcome"] = oc
    from .series import stroke_series
    ser = stroke_series(run.img, run.conf, run.boxes, run.sk, run.fps, run.height_px, r.impact_frame,
                        r.racket_track, run.ball, scale=run.height_t)
    ser["side"] = side
    if H is not None:          # player-frame court → image, for the court minimap of the report
        ser["H"] = np.round(H, 8).tolist()
    ser["shot_bounce_m"] = d.get("shot_bounce_m")
    ser["bounce_court_m"] = d.get("bounce_court_m")
    if fcfg.get("enabled", True) and side == "near":      # strings: not measurable at the far end
        from .racket_orientation import stroke_faces
        grip = p.backhand_grip_close_deg if r.stroke == "backhand" else p.forehand_grip_close_deg
        faces = stroke_faces(clip, run, r, p.height_m, pitch if H_img is not None else None, rpose, wb3d,
                             fcfg.get("hand3d_step", 2), grip)
        d["face"] = faces["phases"]
        d["metrics"].update(faces["trunk3d"])
        ser["face"] = {key: faces[key] for key in ("first", "tilt", "yaw", "label", "observed", "keypoints", "source", "hand3d", "rot3d")}
    # the technique model of this stroke: every body part and the racket at each phase, footwork,
    # timing and the classes of its variant
    from .technique import stroke_technique
    ph_frames = {k: v.get("frame") for k, v in r.phases.items()}
    ta = r.metrics.get("time_available_s")
    opp_f = None if ta is None else r.impact_frame - int(round(ta * run.fps))
    d["technique"] = stroke_technique(
        run.img, run.conf, run.sk, run.fps, run.height_t if run.height_t is not None else np.full(len(run.img), run.height_px),
        r.impact_frame, ph_frames, r.stroke, H if side == "near" else None, opp_f, (r.ball or {}).get("bounce_frame"),
        ser.get("face"), None,
        {"court_pos": d.get("court_pos_m"), "displacement": d.get("displacement_m"), "t_avail": ta,
         "contact_h": r.metrics.get("contact_height_pct"), "shot_direction": d.get("shot_direction"),
         "split": (r.phases.get("ready") or {}).get("method") == "split_step_landing"})
    if side == "far":                       # 70 px player: only position-level classes are kept
        d["technique"] = {"classes": {k: v for k, v in d["technique"]["classes"].items()
                                      if k in ("ball_speed", "ball_height", "depth", "court_side", "width", "intent", "shot_type")},
                          "phases": {}, "stroke": {}, "footwork": {}}
    sdir = ctx.path("series")
    sdir.mkdir(exist_ok=True)
    sname = f"{wid}_{side}.json"
    _write(sdir / sname, ser)
    d.update(series=f"series/{sname}", window_impact_s=r.impact_frame / run.fps)
    return d
