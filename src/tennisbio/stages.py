"""Pipeline stages for a full match (see tennisbio.pipeline for the incremental machinery).

probe → scenes (cuts, main camera) → audio (impact transients) → players (cheap pose on main-camera
frames) → candidates (near-player strokes) → fine (full-quality analysis in ±1 s windows).
"""
import hashlib
import json
import os
import shutil
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


@stage("probe", "2", outputs=("probe.json",))
def st_probe(ctx: Context):
    """Metadata of the match video. A video whose clock jumps (recorded .ts broadcasts) or a .ts
    container (imprecise seeking) is first copied once, without re-encoding, into a clean file
    (<match>/source.mkv) that every other stage reads."""
    from .io.video import timeline

    src, meta = ctx.path("source.mkv"), ctx.path("source.json")
    meta.unlink(missing_ok=True)                  # a new or changed video decides again
    src.unlink(missing_ok=True)
    info = probe(ctx.video)
    tl = timeline(ctx.match.video)
    ts = ctx.match.video.suffix.lower() in (".ts", ".m2ts", ".mts", ".trp")
    if tl["jumps"] or ts:
        size = ctx.match.video.stat().st_size
        free = shutil.disk_usage(ctx.dir).free
        if free < size * 1.1 + 2e9:
            ctx.log(f"  AVISO: no hay espacio para limpiar el vídeo ({free / 1e9:.0f} GB libres); "
                    "se usa tal cual (los tiempos pueden fallar tras un salto)")
        else:
            ctx.log("  el vídeo tiene saltos de tiempo o es .ts: se copia una vez a un fichero limpio (sin recodificar)")
            tmp = src.with_name("source.part.mkv")
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ctx.match.video), "-map", "0:v:0", "-map", "0:a?",
                                "-dn", "-sn", "-c", "copy", str(tmp)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0 and _valid_video(tmp):
                os.replace(tmp, src)
                _write(meta, {"from": str(ctx.match.video), "jumps": tl["jumps"], "ts": ts})
                info = probe(src)
            else:
                tmp.unlink(missing_ok=True)
                ctx.log(f"  AVISO: no se pudo limpiar el vídeo ({(r.stderr or '').strip()[-150:]}); se usa tal cual")
    d = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(info).items()}
    d.update(jumps=tl["jumps"], vfr=bool(info.vfr or tl["vfr"]), cleaned=src.exists())
    _write(ctx.path("probe.json"), d)
    return {"duration_min": round(info.duration / 60, 1), "fps": info.fps, "size": f"{info.width}x{info.height}",
            "cleaned": d["cleaned"], "vfr": d["vfr"]}


@stage("scenes", "1", deps=("probe",), settings=lambda c: {"fps": c["cheap_pass"]["fps"]}, outputs=("scenes.json",))
def st_scenes(ctx: Context):
    fps = ctx.cfg["cheap_pass"]["fps"]
    info = probe(ctx.video)
    total = int(info.duration * fps)

    def frames_with_progress():
        for i, fr in enumerate(read_frames(info, width=160, fps=fps, hwaccel=ctx.cfg.get("hwaccel"))):
            ctx.progress(i + 1, total, "fotogramas")
            yield fr
    shots, mask = analyse_video(frames_with_progress())
    _write(ctx.path("scenes.json"), {"fps": fps, "shots": [vars(s) for s in shots]})
    main = [s for s in shots if s.main_camera]
    return {"shots": len(shots), "main_camera_shots": len(main),
            "main_camera_min": round(sum(s.end - s.start for s in main) / fps / 60, 1)}


@stage("audio", "2", deps=("probe",), outputs=("audio_onsets.json",))
def st_audio(ctx: Context, chunk_s=300.0, overlap_s=1.0):
    """Impact-like transients over the whole match, in 5-minute chunks (memory stays small).
    Every audio track is analysed (broadcasts can carry commentary and ambient sound apart); the
    candidates stage keeps the track whose transients coincide with the swings."""
    info = probe(ctx.video)
    sr, tracks = 22050, []
    for k in range(min(info.audio_tracks, 4)):
        times, strengths = [], []
        t = 0.0
        while t < info.duration:
            dur = min(chunk_s + overlap_s, info.duration - t)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-t", f"{dur:.3f}", "-i", str(ctx.video),
                                  "-map", f"0:a:{k}", "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "pipe:1"],
                                 capture_output=True).stdout
            y = np.frombuffer(raw, np.float32)
            if len(y) > sr:
                on, st = audio_onsets(y, sr)
                keep = on < chunk_s if t + chunk_s < info.duration else np.ones(len(on), bool)
                times += list(on[keep] + t)
                strengths += list(st[keep])
            t += chunk_s
            n_tr = min(info.audio_tracks, 4)
            ctx.progress(int(k * info.duration + min(t, info.duration)), int(n_tr * info.duration), "s de sonido")
        tracks.append({"t": times, "strength": strengths})
    if not tracks:
        ctx.log("  AVISO: el vídeo no tiene sonido; los golpes se detectan solo con la imagen (algo peor)")
    first = tracks[0] if tracks else {"t": [], "strength": []}
    _write(ctx.path("audio_onsets.json"), {"t": first["t"], "strength": first["strength"], "track": 0, "tracks": tracks})
    return {"onsets": len(first["t"]), "tracks": len(tracks)}


def choose_audio_track(tracks: list[dict], peaks: np.ndarray, tol_s: float, span_s: float) -> int:
    """The audio track whose transients coincide with the near player's swings, beyond what its
    rate of transients would give by chance (commentary also has onsets, at random times)."""
    best, best_score, scores = 0, -np.inf, []
    for k, tr in enumerate(tracks):
        on = np.asarray(tr["t"])
        if not len(peaks) or not len(on):
            score = -1.0
        else:
            # swings that have a transient (recall) and transients that fall on a swing
            # (precision), each beyond what chance gives at that density
            rate = len(on) / max(span_s, 1.0)
            recall = np.mean([bool(np.any(np.abs(on - t) <= tol_s)) for t in peaks])
            precision = np.mean([bool(np.any(np.abs(peaks - t) <= tol_s)) for t in on])
            recall_0 = 1 - np.exp(-rate * 2 * tol_s)
            precision_0 = min(1.0, len(peaks) * 2 * tol_s / max(span_s, 1.0))
            score = (recall - recall_0) + (precision - precision_0)
        scores.append(score)
        if score > best_score:
            best, best_score = k, score
    # with few swings (a short clip) chance decides: keep the first track (the broadcast's main mix,
    # which carries the impacts too) unless another one is clearly better
    if len(peaks) < 20 and best != 0 and best_score - scores[0] < 0.3:
        return 0
    return best


def load_onsets(ctx: Context) -> np.ndarray:
    """Audio transients of the chosen track (see choose_audio_track)."""
    if not ctx.path("audio_onsets.json").exists():
        return np.zeros(0)
    a = _read(ctx.path("audio_onsets.json"))
    k = _read(ctx.path("audio_track.json"))["track"] if ctx.path("audio_track.json").exists() else 0
    tracks = a.get("tracks") or [a]
    return np.array(tracks[k]["t"] if k < len(tracks) else a["t"])


def _pose_detector(cfg: dict):
    """frame → (boxes (N,4), keypoints (N,17,2), conf (N,17)) with the YOLO pose model."""
    from .pose.backend import pose_model, set_device

    set_device(cfg.get("device", "cpu"))
    model = pose_model(cfg.get("yolo_pose", "yolo11m-pose.pt"), cfg["cheap_pass"].get("imgsz", 960))

    def detect(frame):
        return model.predict(frame, conf=0.3)
    return detect


def play_mask(sc: dict, court: dict | None) -> np.ndarray:
    """Frames (at the scenes' fps) of match play: main camera AND the court found there. A broadcast
    has long stretches the shot classifier can take for the main camera (anthem, ceremony, practice
    footage, close-ups on a blue background); without the court lines there is nothing to analyse."""
    n = max([s["end"] for s in sc["shots"]] + [0])
    main = np.zeros(n, bool)
    for s in sc["shots"]:
        main[s["start"]:s["end"]] = s["main_camera"]
    if court is None or not court.get("shots"):
        return main
    has = np.zeros(n, bool)
    for o in court["shots"]:
        if o["H"] is not None:
            has[o["start"]:o["end"]] = True
    return main & has


@stage("players", "3", deps=("scenes", "court"), settings=lambda c: {"fps": c["cheap_pass"]["fps"], "imgsz": c["cheap_pass"].get("imgsz", 960)},
       outputs=("players.npz",))
def st_players(ctx: Context):
    """Cheap pose on match-play frames only (main camera with the court found; cheap fps, full
    width for small players)."""
    from .pose.yolo import _objects, appearance

    sc = _read(ctx.path("scenes.json"))
    fps = sc["fps"]
    court = _read(ctx.path("court.json")) if ctx.path("court.json").exists() else None
    main = play_mask(sc, court)
    total_main = sum(s["end"] - s["start"] for s in sc["shots"] if s["main_camera"])
    ctx.log(f"  juego con pista: {main.sum() / fps / 60:.1f} min de {total_main / fps / 60:.1f} min de cámara principal")
    detect = _pose_detector(ctx.cfg)
    info = probe(ctx.video)
    boxes, kps, confs, feats, idx = [], [], [], [], []
    # only the main-camera stretches are decoded (seeking past replays, close-ups and changeovers:
    # a third of a broadcast or more)
    edges = np.flatnonzero(np.diff(np.r_[0, main.astype(int), 0]))
    for a, b_ in zip(edges[::2], edges[1::2]):
        for k_, frame in enumerate(read_frames(info, start=a / fps, duration=(b_ - a) / fps, fps=fps,
                                               hwaccel=ctx.cfg.get("hwaccel"))):
            i = int(a) + k_
            if i >= b_:
                break
            b, k, c = detect(frame)
            boxes.append(b.astype(np.float32)); kps.append(k.astype(np.float32)); confs.append(c.astype(np.float32))
            feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
            idx.append(i)
            ctx.progress(len(idx), int(main.sum()), "fotogramas con jugadoras")
    savez_atomic(ctx.path("players.npz"), fps=fps, frames=np.array(idx), height=info.height,
                        boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs), feats=_objects(feats))
    return {"frames": len(idx)}


def _on_court(boxes: np.ndarray, H) -> np.ndarray:
    """Which boxes stand where a near player can be (inside the doubles width with a margin,
    from deep behind the baseline to the net): ball kids and line judges at the back corners or
    on the sides are not."""
    from .court_metrics import to_court

    if H is None or not len(boxes):
        return np.ones(len(boxes), bool)
    feet = np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, boxes[:, 3]]
    c = to_court(H, feet)
    return (np.abs(c[:, 0]) <= 5.5) & (c[:, 1] >= -7.0) & (c[:, 1] <= 11.885)


def near_runs(d, sk, court: dict | None = None):
    """Each continuous run of main-camera frames with the near player tracked (cuts break tracking).
    court: the court stage's output, to start the tracking on the person standing on the court.

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
        tall = h0 >= 0.5 * h0.max()
        H = court_at(court, frames[run[first]] / fps)[0] if court else None
        on = tall & _on_court(b0, H)
        cand = np.flatnonzero(on if on.any() else tall)
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


@stage("identity", "4", deps=("players", "score", "court", "audio"), outputs=("identity.json",), match_fields=lambda m: {"player": m.player.name})
def st_identity(ctx: Context):
    """Is the near player the target in each run? Clothing clusters + serves + scoreboard marker:
    when the near player serves she is the scoreboard's server; when she waits to return a serve
    she is the other one."""
    from .identity import assign, cluster_two, decide_by_ends, end_changes, near_receives, near_serves

    d = np.load(ctx.path("players.npz"), allow_pickle=True)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    score = _read(ctx.path("score.json"))
    court = _read(ctx.path("court.json"))
    onsets = load_onsets(ctx)
    runs, feats, votes = [], [], []
    for run, img, cf, h, app in near_runs(d, sk, court):
        i = len(runs)
        runs.append({"start": int(frames[run[0]]), "end": int(frames[run[-1]]) + 1})
        feats.append(app)
        H = court_at(court, frames[run[0]] / fps)[0]
        fy = _feet_court_y(img, H)
        f = near_serves(img, cf, fps, h, feet_y=fy)
        serving = True
        if f is None:                    # the opponent serves from the far end: she returns
            ts = frames[run] / fps
            ks = [int(np.searchsorted(ts, t)) for t in onsets[(onsets >= ts[0]) & (onsets <= ts[-1])]]
            f = near_receives(img, cf, fps, h, ks, feet_y=fy)
            serving = False
        if f is not None:
            sr = score_at(score, frames[run[f]] / fps, max_age_s=25.0)
            if sr is not None and sr.get("server") is not None:
                vote = (sr["server"] == 0) == serving
                votes.append((i, vote))
                runs[i]["serve_vote" if serving else "return_vote"] = vote
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


def _feet_court_y(img: np.ndarray, H) -> np.ndarray | None:
    """Court y (m from the near baseline) of the midpoint of the ankles per frame, or None."""
    from .court_metrics import to_court

    if H is None:
        return None
    a, b = img[:, 15], img[:, 16]
    ank = np.where(np.isfinite(a) & np.isfinite(b), (a + b) / 2, np.where(np.isfinite(a), a, b))
    y = np.full(len(img), np.nan)
    ok = np.isfinite(ank).all(axis=1)
    if ok.any():
        y[ok] = to_court(H, ank[ok])[:, 1]
    return y


def near_is_target(identity: dict, frame: int):
    for r in identity.get("runs", []):
        if r["start"] <= frame < r["end"]:
            return r.get("near_is_target")
    return None


@stage("candidates", "6", deps=("players", "audio", "identity", "court", "score"), outputs=("candidates.json", "audio_track.json"))
def st_candidates(ctx: Context, tol_s=0.35):
    """Near-player stroke candidates: swing peaks of the near player at cheap fps, confirmed by
    an audio transient when one is close. Each candidate records who the near player is
    (identity: True target, False opponent, None undecided); the fine passes pick their own.
    Each candidate is checked again in the fine pass."""
    d = np.load(ctx.path("players.npz"), allow_pickle=True)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    court = _read(ctx.path("court.json"))
    audio = _read(ctx.path("audio_onsets.json"))
    tracks = audio.get("tracks") or [audio]
    track = 0
    if len(tracks) > 1:                    # commentary vs ambient: the one that sounds with her swings
        peaks = [frames[run[p]] / fps for run, img, cf, h, _ in near_runs(d, sk, court)
                 for p in swing_peaks(speed(to_body_frame(img, sk, h)[:, sk["dom_wrist"]], fps), fps,
                                      min_gap=1.0, height=1.5, prominence=1.0)]
        span = float(frames[-1] - frames[0]) / fps if len(frames) else 0.0
        track = choose_audio_track(tracks, np.array(peaks), tol_s, span)
        ctx.log(f"  sonido: pista {track + 1} de {len(tracks)} (la que coincide con los golpes)")
    _write(ctx.path("audio_track.json"), {"track": track, "tracks": len(tracks)})
    onsets = np.array(tracks[track]["t"]) if tracks else np.zeros(0)
    identity = _read(ctx.path("identity.json"))
    # doubles are out of scope: two people inside the near half in most main-camera frames
    from .court_metrics import people_in_near_half
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
    for run, img, cf, h, _ in near_runs(d, sk, court):
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
            "replay_runs_skipped": replays, "audio_track": track}


def grab_frame(video: Path, t: float) -> np.ndarray | None:
    """One full-resolution BGR frame at time t (fast seek)."""
    import cv2

    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "pipe:1"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


@stage("court", "2", deps=("scenes",), outputs=("court.json",))
def st_court(ctx: Context, n_fit=6, min_score=0.5, every_s=8.0):
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
        fr = grab_frame(ctx.video, mid(s))
        fit = fit_court(fr) if fr is not None else None
        if fit is not None and (best is None or fit.score > best[0].score):
            best = (fit, fr.shape)
    out = []
    for i_s, s in enumerate(main):
        ctx.progress(i_s + 1, len(main), "planos")
        # checked every ~every_s seconds, not only once: a zoom or a pan inside the shot gets its
        # own fit (or no court) for that stretch instead of a wrong one
        n = int(np.clip(round((s["end"] - s["start"]) / fps / every_s), 1, 8))
        edges = np.linspace(s["start"], s["end"], n + 1).round().astype(int)
        for a, b in zip(edges[:-1], edges[1:]):
            fr = grab_frame(ctx.video, (a + b) / 2 / fps)
            if fr is None:
                continue
            fit, score = best[0] if best else None, 0.0
            if fit is not None:
                score = score_homography(fit.H, white_lines(fr))
            if score < min_score:
                own = fit_court(fr)
                fit, score = (own, own.score) if own is not None else (None, 0.0)
            seg = {"start": int(a), "end": int(b), "score": round(score, 3),
                   "H": None if fit is None or score < min_score else fit.H.tolist(),
                   "pitch_deg": None if fit is None or score < min_score else round(camera_pitch_deg(fit, fr.shape), 1)}
            if out and out[-1]["end"] == seg["start"] and out[-1]["H"] == seg["H"]:
                out[-1]["end"] = seg["end"]               # same court: one segment
            else:
                out.append(seg)
    _write(ctx.path("court.json"), {"fps": fps, "shots": out})
    ok = [o for o in out if o["H"] is not None]
    return {"segments": len(out), "with_court": len(ok),
            "pitch_deg_median": float(np.median([o["pitch_deg"] for o in ok])) if ok else None}


def _surname(name: str) -> str:
    return name.strip().split()[-1] if name and name.strip() else ""


@stage("score", "4", deps=("scenes", "court"), settings=lambda c: {"every_s": (c.get("score") or {}).get("every_s", 5.0)},
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
    court = _read(ctx.path("court.json")) if ctx.path("court.json").exists() else {}
    # the opponent's name is looked for during match play (court found): before the match a
    # broadcast shows the anthem, other matches' scoreboards and recaps
    play = [o for o in court.get("shots", []) if o["H"] is not None] or mains
    opponent = _surname(ctx.match.opponent)
    if not opponent and play:        # not in matches.yaml: read it from the scoreboard
        times = [((s["start"] + s["end"]) / 2) / fps for s in play[:: max(1, len(play) // 60)]]
        opponent = discover_opponent((f for f in (grab_frame(ctx.video, t) for t in times) if f is not None),
                                     _surname(ctx.match.player.name)) or ""
    names = (_surname(ctx.match.player.name), opponent)
    if not all(names):
        _write(ctx.path("score.json"), {"readings": [], "note": "no se encontró el nombre del rival en el marcador"})
        return {"readings": 0}
    reader, out, shots = ScoreReader(*names), [], []
    for i_s, s in enumerate(sc["shots"]):
        ctx.progress(i_s + 1, len(sc["shots"]), f"planos · {len(out)} lecturas")
        if not s["main_camera"]:
            continue
        t = s["start"] / fps + 0.5
        tried = read = 0
        while t < s["end"] / fps:
            fr = grab_frame(ctx.video, t)
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


def point_won(score: dict, t: float, horizon_s=60.0):
    """Did the target player (scoreboard row 0) win the point being played at time t? From the next
    change of the scoreboard: her points or games go up, or the opponent's. None when unclear."""
    rd = [r for r in score.get("readings", []) if r.get("games")]
    before = None
    for r in rd:
        if r["t"] <= t:
            before = r
        elif before is not None and r["t"] - t <= horizon_s:
            def key(x):
                g = x["games"]
                pts = x.get("points") or [None, None]
                rank = {"0": 0, "15": 1, "30": 2, "40": 3, "AD": 4, "A": 4}
                return [(int(a), int(b)) for a, b in g], [rank.get(str(p_), int(p_) if str(p_).isdigit() else 0) for p_ in pts]
            try:
                (g0, p0), (g1, p1) = key(before), key(r)
            except (TypeError, ValueError):
                return None
            if (g0, p0) == (g1, p1):
                continue
            if len(g1) > len(g0) or g1[-1] != g0[-1]:              # a game (or set) went to someone
                a = (g1[-1][0] - g0[-1][0]) if len(g1) == len(g0) else (g0[-1][0] >= g0[-1][1])
                b = (g1[-1][1] - g0[-1][1]) if len(g1) == len(g0) else (g0[-1][1] > g0[-1][0])
                return None if a == b else bool(a > b)
            if p1[0] > p0[0] and p1[1] <= p0[1]:
                return True
            if p1[1] > p0[1] and p1[0] <= p0[0]:
                return False
            if p1[0] < p0[0] and p0[0] == 4:                       # her advantage lost: deuce
                return False
            if p1[1] < p0[1] and p0[1] == 4:
                return True
            return None
    return None


def court_at(court: dict, t: float, scale: float = 1.0):
    """(H court→image, pitch) of the main-camera shot containing time t, or (None, None).
    scale: image pixels of the windows per pixel of the match video (window_scale)."""
    f = t * court.get("fps", 1)
    for o in court.get("shots", []):
        if o["start"] <= f < o["end"] and o["H"] is not None:
            H = np.array(o["H"])
            return (np.diag([scale, scale, 1.0]) @ H if scale != 1.0 else H), o["pitch_deg"]
    return None, None


def _check_court(clip: Path, t: float, H, pitch, min_score=0.5):
    """The court of the shot checked on the window's own impact frame (a zoom or a pan the
    sampled frames missed): kept, refitted on that frame, or dropped."""
    from .court import camera_pitch_deg, fit_court, score_homography, white_lines

    fr = grab_frame(clip, t)
    if fr is None:
        return H, pitch, None
    if H is not None and score_homography(H, white_lines(fr)) >= min_score:
        return H, pitch, "ok"
    own = fit_court(fr)
    if own is not None and own.score >= min_score:
        return own.H, round(camera_pitch_deg(own, fr.shape), 1), "refit"
    return None, None, "none"


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


MAX_WINDOW_WIDTH = 1920       # 4K windows would need ~25 MB per frame in memory; pose runs at 1280 anyway


def window_scale(width: int) -> float:
    """Factor from the match video's pixels to its windows' pixels."""
    return min(1.0, MAX_WINDOW_WIDTH / width) if width else 1.0


def cut_window(video: Path, t0: float, dur: float, dest: Path, interlaced: bool = False, audio_track: int = 0,
               width: int = 0, cfr_fps: float | None = None) -> Path:
    """Re-encoded window of the match. Interlaced broadcasts (1080i) are deinterlaced to one frame
    per field (yadif=1): 50 sharp frames per second instead of 25 combed ones. Larger than 1080p is
    scaled down (window_scale), a variable frame rate is made constant (frame index = time), and
    the chosen audio track is kept. Written through a temporary file and checked, so an
    interrupted cut is never reused."""
    if dest.exists() and _valid_video(dest):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".part" + dest.suffix)
    filters = ["yadif=1"] if interlaced else []
    f = window_scale(width)
    if f < 1.0:
        filters.append(f"scale={MAX_WINDOW_WIDTH}:-2")
    if cfr_fps:
        filters.append(f"fps={cfr_fps * (2 if interlaced else 1):.6f}")
    vf = ["-vf", ",".join(filters)] if filters else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                        "-map", "0:v:0", "-map", f"0:a:{audio_track}?", *vf,
                        # a keyframe every 8 frames: frame-by-frame scrubbing in the report stays instant;
                        # yuv420p: the only chroma format every browser plays (broadcasts can be 4:2:2)
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-g", "8", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", "-c:a", "aac", "-ac", "2", str(tmp)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not _valid_video(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"no se pudo recortar {dur:.1f} s en {t0:.1f} s del vídeo ({(r.stderr or '').strip()[-200:]})")
    os.replace(tmp, dest)
    return dest


def _fine_settings(c):
    rf = c.get("racket_face") or {}
    return {"fine": c["fine_pass"], "imgsz": c.get("fine_imgsz", 960), "ball": c.get("ball"),
            "racket_face": rf, "include_undecided": c.get("include_undecided", False),
            # the models themselves: adding or replacing one re-runs the fine pass
            "models": {"ball": model_state((c.get("ball") or {}).get("onnx")), "racket": model_state(rf.get("pose_onnx")),
                       "hand3d": model_state(rf.get("hand3d_onnx")), "pose": c.get("yolo_pose", "yolo11m-pose.pt")}}


FINE_CODE = ("stages", "clip_pipeline", "stroke_analysis", "phases", "kinematics", "impacts", "ball", "court_metrics",
             "outcome", "series", "racket", "racket3d", "racket_face", "racket_orientation", "tracking", "technique",
             "footwork", "pose.yolo", "pose.yolo_onnx", "pose.backend", "ball3d", "limits")


def _player_fields(p) -> dict:
    return {"hand": p.hand, "height_m": p.height_m, "backhand": getattr(p, "backhand", None),
            "grip": [getattr(p, "forehand_grip_close_deg", None), getattr(p, "backhand_grip_close_deg", None)]}


@stage("fine", "8", deps=("candidates", "court", "score"), settings=_fine_settings, outputs=("strokes.json",),
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
    """Full-quality analysis of the kept candidates, one window per stretch of play."""
    cands = _read(ctx.path("candidates.json"))
    court = _read(ctx.path("court.json"))
    score = _read(ctx.path("score.json"))
    onsets = load_onsets(ctx)
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
    ph = hashlib.sha1(json.dumps([ctx.cfg.get("yolo_pose", "yolo11m-pose.pt"), ctx.cfg.get("fine_imgsz", 960),
                                  model_state(bcfg.get("onnx")), "v2"]).encode()).hexdigest()[:8]
    strokes, errors = [], []
    kept = sorted((c for c in cands if keep(c)), key=lambda c: (c.get("side", "near"), c["t"]))
    # candidates whose windows overlap (strokes of the same rally) share one window: the pose,
    # ball and racket of those frames are computed once
    groups = []
    for c in kept:
        g = groups[-1] if groups else None
        if (g and g[-1].get("side", "near") == c.get("side", "near") and c["t"] - g[-1]["t"] < pre + post
                and c["t"] - g[0]["t"] < 10.0):
            g.append(c)
        else:
            groups.append([c])
    done = 0
    _TIMES.clear()
    for g in groups:
        try:
            strokes += _fine_one(ctx, p, g, pre, post, interlaced, ph, court, score, onsets, scenes, ball, rpose, wb3d, fcfg)
        except Exception as e:                    # one bad window never stops the match
            for c in g:
                errors.append({"t": c["t"], "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]})
        done += len(g)
        ctx.progress(done, len(kept), f"golpes candidatos · {len(strokes)} confirmados")
    strokes.sort(key=lambda d: d["match_time_s"])
    _rally_position(strokes, cands, scenes)
    _write(ctx.path(out_name), strokes)
    other = ctx.path("strokes_opponent.json" if out_name == "strokes.json" else "strokes.json")
    _drop_orphans(ctx, cands, strokes, _read(other) if other.exists() else [],
                  {_window_of(g, pre, post)[2] for g in groups}, kept)
    _write(ctx.path(out_name.replace(".json", "_errores.json")), errors)
    if errors:
        ctx.log(f"  {len(errors)} golpes no se pudieron analizar (detalle en {out_name.replace('.json', '_errores.json')})")
    return {"candidates": len(kept), "confirmed": len(strokes), "errors": len(errors), "warnings": warnings,
            "forehands": sum(s["stroke"] == "forehand" for s in strokes), "windows": len(groups),
            # where the time goes (seconds; only what was computed now, not read from the caches)
            "seconds": {k: round(v, 1) for k, v in sorted(_TIMES.items(), key=lambda kv: -kv[1])}}


_TIMES: dict = {}


def _took(key: str, t0: float):
    import time
    _TIMES[key] = _TIMES.get(key, 0.0) + time.time() - t0


def _rally_position(strokes: list[dict], cands: list[dict], scenes: dict) -> None:
    """Her shot number within the point and her shots in the whole point, counted from the hits of
    the cheap pass on her side of the same main-camera shot. Only when the shot starts at least
    1.5 s before its first hit (the point is seen from its start). The point's moment class
    (return / start of the point / rally) is refined with it."""
    sfps = scenes.get("fps") or 1
    for d in strokes:
        t, side = d["match_time_s"], d.get("side", "near")
        sh = next((x for x in scenes.get("shots", []) if x["main_camera"] and x["start"] / sfps <= t < x["end"] / sfps), None)
        if sh is None:
            continue
        a, b = sh["start"] / sfps, sh["end"] / sfps
        hits = sorted(c["t"] for c in cands if c.get("side", "near") == side and a <= c["t"] < b)
        if not hits or hits[0] - a < 1.5:
            continue
        k = sum(h <= t + 0.3 for h in hits)
        d["shot_in_point"], d["shots_in_point"] = k, len(hits)
        cl = (d.get("technique") or {}).get("classes")
        if cl is not None and not d.get("is_return"):
            cl["play"] = "inicio del punto" if k <= 2 else "peloteo"


def _window_of(group: list[dict], pre: float, post: float) -> tuple[float, float, str]:
    """Start, duration and name of the window of a group of candidates. Named by its interval (not
    by its position in the list): a new candidate elsewhere never renames, and so never
    re-analyses, the existing windows."""
    t0 = max(0.0, group[0]["t"] - pre)
    dur = group[-1]["t"] + post - t0
    return t0, dur, f"w{int(round(t0 * 1000)):09d}_{int(round(dur * 1000))}"


def _drop_orphans(ctx: Context, cands: list[dict], strokes: list[dict], others: list[dict],
                  wids: set | None = None, kept: list | None = None):
    """Windows (and their caches) no fine pass uses any more, and series of strokes that no longer
    exist, are deleted: re-runs never fill the disk. A window is kept when it is one of this pass
    (wids) or holds a candidate this pass does not analyse (the other pass's: target / opponent).
    others: the strokes of the other fine pass, whose files share the folders."""
    keep_series = {Path(d["series"]).name for d in strokes + others if d.get("series")}
    for f in ctx.path("series").glob("*.json") if ctx.path("series").exists() else []:
        if f.name not in keep_series:
            f.unlink(missing_ok=True)
    mine = {c["t"] for c in (kept or [])}
    foreign = np.array(sorted(c["t"] for c in cands if c["t"] not in mine)) if wids is not None else \
        np.array(sorted(c["t"] for c in cands))
    for f in ctx.path("windows").glob("w*") if ctx.path("windows").exists() else []:
        parts = f.name.split(".")[0].split("_")
        try:
            t0, dur = int(parts[0][1:]) / 1000, int(parts[1]) / 1000
        except (IndexError, ValueError):
            continue
        if wids is not None and f"{parts[0]}_{parts[1]}" in wids:
            continue
        if not np.any((foreign >= t0) & (foreign <= t0 + dur)):
            f.unlink(missing_ok=True)


def _fine_one(ctx, p, group, pre, post, interlaced, ph, court, score, onsets, scenes, ball, rpose, wb3d, fcfg):
    """Candidates of one stretch of play (overlapping windows): one window is cut and analysed once
    (pose, ball, rackets), then each candidate gets its phases, metrics, court, outcome, racket and
    technique. Returns the confirmed strokes."""
    from .clip_pipeline import run_clip
    from .pose.backend import set_device

    set_device(ctx.cfg.get("device", "cpu"))

    c = group[0]
    t0, dur, wid = _window_of(group, pre, post)
    pr = _read(ctx.path("probe.json")) if ctx.path("probe.json").exists() else {}
    track = _read(ctx.path("audio_track.json"))["track"] if ctx.path("audio_track.json").exists() else 0
    import time
    t_ = time.time()
    clip = cut_window(ctx.video, t0, dur, ctx.path("windows") / f"{wid}.mp4", interlaced, track,
                      pr.get("width", 0), pr.get("fps") if pr.get("vfr") else None)
    _took("recorte", t_)
    ws = window_scale(pr.get("width", 0))
    side = c.get("side", "near")
    extra, cache = {}, clip.with_name(f"{clip.stem}_{ph}.npz")
    if side == "far":
        fi = far_start(clip, court_at(court, c["t"], ws)[0])
        if fi is None:
            return []                         # no court or no far player found: nothing reliable
        extra, cache = dict(side="far", **fi), clip.with_name(f"{clip.stem}_{ph}_far.npz")
    t_ = time.time()
    run = run_clip(clip, cache, p.hand, p.height_m, init_mode="near", rackets=side == "near",
                   imgsz=ctx.cfg.get("fine_imgsz", 960), log=lambda *_: None, ball=ball, **extra)
    for k, v in run.timing.items():
        _TIMES[k] = _TIMES.get(k, 0.0) + v
    _took("analisis_ventana", t_ + sum(run.timing.values()))         # the rest of run_clip
    if side == "far":                         # far strokes count only when the ball confirms them
        run.strokes = [s for s in run.strokes if "ball" in s.impact_source]
    if not run.strokes:
        return []
    out, used = [], set()
    for c in group:
        d = _fine_stroke(ctx, p, c, t0, wid, clip, side, run, used, court, score, onsets, scenes, rpose, wb3d, fcfg)
        if d is not None:
            out.append(d)
    return out


def _fine_stroke(ctx, p, c, t0, wid, clip, side, run, used, court, score, onsets, scenes, rpose, wb3d, fcfg):
    """One confirmed stroke of an analysed window, or None."""
    target = (c["t"] - t0) * run.fps
    free = [s for s in run.strokes if s.impact_frame not in used]
    if not free:
        return None
    r = min(free, key=lambda s: abs(s.impact_frame - target))
    if abs(r.impact_frame - target) > 0.4 * run.fps:
        return None                           # the fine pass did not confirm this candidate
    used.add(r.impact_frame)
    from .limits import sanitize
    r.review += [f"impossible:{k}" for k in sanitize(r.metrics)]      # measurement errors, never shown
    d = r.to_dict()
    t_imp = t0 + r.impact_frame / run.fps
    d.update(window=str(clip.name), window_start_s=t0, match_time_s=t_imp, candidate_audio=c.get("audio"),
             identity=c.get("identity"), target=c.get("target"), stroke_id=f"{ctx.match.id}-{int(round(t_imp * 100)):07d}")
    sr = score_at(score, t_imp)
    if sr is not None:
        d["score"] = {k: sr[k] for k in ("games", "points", "banner", "set", "sets_won", "tiebreak", "pressure")}
    pr = _read(ctx.path("probe.json")) if ctx.path("probe.json").exists() else {}
    H, pitch = court_at(court, t_imp, window_scale(pr.get("width", 0)))
    H, pitch, d["court_check"] = _check_court(clip, r.impact_frame / run.fps, H, pitch)
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
        import time
        t_ = time.time()
        # the 3D hand model is slow: about 12 frames per second of play whatever the broadcast rate
        step3d = max(int(fcfg.get("hand3d_step", 2)), int(round(run.fps / 12.5)))
        faces = stroke_faces(clip, run, r, p.height_m, pitch if H_img is not None else None, rpose, wb3d,
                             step3d, grip)
        _took("cuerdas_y_3d", t_)
        d["face"] = faces["phases"]
        d["metrics"].update(faces["trunk3d"])
        ser["face"] = {key: faces[key] for key in ("first", "tilt", "yaw", "label", "observed", "keypoints", "source", "hand3d", "rot3d")}
    # who won the point (from the next change of the scoreboard); target = row 0 of the scoreboard
    pw = point_won(score, t_imp)
    if pw is not None:
        d["point_won"] = pw if p.id == ctx.match.player.id else (not pw)
    # her ball: average horizontal speed from contact to bounce, and a shot-quality indicator
    # (deep, wide, fast): our own proxy of the pro systems' "shot quality", not theirs
    if d.get("shot_bounce_m") and d.get("court_pos_m") and d.get("impact_to_shot_bounce_s"):
        dist = float(np.hypot(d["shot_bounce_m"][0] - d["court_pos_m"][0], d["shot_bounce_m"][1] - d["court_pos_m"][1]))
        tt = d["impact_to_shot_bounce_s"]
        if tt > 0.2:
            d["ball_speed_avg_kmh"] = round(dist / tt * 3.6, 1)
    if d.get("shot_bounce_m") and d.get("shot_in") is not False:
        depth = float(np.clip(1 - (d.get("shot_depth_m") or 6) / 6.4, 0, 1))          # 1 = on the baseline
        width = float(np.clip(abs(d["shot_bounce_m"][0]) / 4.115, 0, 1))              # 1 = on the sideline
        speed = float(np.clip((d.get("ball_speed_avg_kmh") or 60) / 110, 0, 1))
        d["shot_quality_proxy"] = round(100 * (0.45 * depth + 0.25 * width + 0.30 * speed), 0)
    # return of serve: the opponent's hit was the first sound of the main-camera shot (her serve)
    is_return = None
    ta_ = r.metrics.get("time_available_s")
    shot_start = next((sh["start"] / sfps for sh in scenes["shots"]
                       if sh["main_camera"] and sh["start"] / sfps <= t_imp < sh["end"] / sfps), None)
    if ta_ is not None and shot_start is not None and len(onsets):
        t_opp = t_imp - ta_
        before = onsets[(onsets > shot_start + 0.3) & (onsets < t_opp - 0.3)]
        # a shot that starts less than 1.5 s before the opponent's hit may begin mid-rally: unknown
        if t_opp - shot_start >= 1.5:
            is_return = bool(len(before) == 0 and t_opp - shot_start < 8.0)
            d["is_return"] = is_return
    # the technique model of this stroke: every body part and the racket at each phase, footwork,
    # timing and the classes of its variant
    from .technique import stroke_technique
    ph_frames = {k: v.get("frame") for k, v in r.phases.items()}
    ta = r.metrics.get("time_available_s")
    opp_f = None if ta is None else r.impact_frame - int(round(ta * run.fps))
    # the ball's flight around the stroke (ball3d): net crossing, top of the bounce, rising/dropping
    ball_m, cam = {}, None
    if side == "near" and H_img is not None:
        from .ball3d import camera
        from .io.video import probe as _probe
        ci = _probe(clip)
        cam = camera(H_img, (ci.height, ci.width))
    if cam is not None and run.ball is not None and (r.ball or {}).get("bounce_frame") is not None:
        from .ball3d import flights
        cz = r.metrics.get("contact_height_pct")
        ball_m = flights(run.ball, run.fps, H_img, (ci.height, ci.width), r.ball["bounce_frame"], r.impact_frame, opp_f,
                         None if cz is None else cz / 100 * p.height_m + 0.08,         # the ankle is ~8 cm above the ground
                         (d.get("court_pos_m") or [None, None])[1])
        if ball_m:
            d["ball_flight"] = ball_m
    d["technique"] = stroke_technique(
        run.img, run.conf, run.sk, run.fps, run.height_t if run.height_t is not None else np.full(len(run.img), run.height_px),
        r.impact_frame, ph_frames, r.stroke, H if side == "near" else None, opp_f, (r.ball or {}).get("bounce_frame"),
        ser.get("face"), None,
        {"court_pos": d.get("court_pos_m"), "displacement": d.get("displacement_m"), "t_avail": ta,
         "contact_h": r.metrics.get("contact_height_pct"), "shot_direction": d.get("shot_direction"),
         "split": (r.phases.get("ready") or {}).get("method") == "split_step_landing",
         "surface": ctx.match.surface or "", "next_opp": ret, "return": is_return, "ball": ball_m})
    if side == "far":                       # 70 px player: only position-level classes are kept
        d["technique"] = {"classes": {k: v for k, v in d["technique"]["classes"].items()
                                      if k in ("ball_speed", "ball_height", "depth", "court_side", "width", "intent", "shot_type")},
                          "phases": {}, "stroke": {}, "footwork": {}}
    sdir = ctx.path("series")
    sdir.mkdir(exist_ok=True)
    sname = f"{wid}_{side}_{r.impact_frame}.json"
    _write(sdir / sname, ser)
    d.update(series=f"series/{sname}", window_impact_s=r.impact_frame / run.fps)
    return d
