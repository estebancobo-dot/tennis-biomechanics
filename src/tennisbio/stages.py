"""Pipeline stages for a full match (see tennisbio.pipeline for the incremental machinery).

probe → scenes (cuts, main camera) → audio (impact transients) → players (cheap pose on main-camera
frames) → candidates (near-player strokes) → fine (full-quality analysis in ±1 s windows).
views (replays and other cameras linked to the live strokes) → views_link (their links in strokes.json).
"""
import hashlib
import json
import time
import warnings
import os
import shutil
import subprocess
import traceback
from pathlib import Path

import numpy as np

from .impacts import audio_onsets, swing_peaks
from .io.video import frames_at, probe, read_ahead, read_frames
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
            # recorded .ts broadcasts carry packets without a timestamp (18-10: «Can't write packet with unknown
            # timestamp» on the Osaka – Rybakina R4): the second try makes them up from the stream's clock
            for flags in ([], ["-fflags", "+genpts+igndts", "-avoid_negative_ts", "make_zero"]):
                r = subprocess.run(["ffmpeg", "-v", "error", "-y", *flags[:2], "-i", str(ctx.match.video), *flags[2:],
                                    "-map", "0:v:0", "-map", "0:a?", "-dn", "-sn", "-c", "copy", str(tmp)],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
                if r.returncode == 0 and _valid_video(tmp):
                    break
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


def _scenes_settings(c: dict) -> dict:
    sc = c.get("scenes") or {}
    return {"fps": c["cheap_pass"]["fps"], "model": model_state(sc.get("onnx")),
            "threshold": sc.get("threshold", 0.5), "tn_fps": sc.get("fps", 25)}


@stage("scenes", "3", deps=("probe",), settings=_scenes_settings, outputs=("scenes.json",))
def st_scenes(ctx: Context):
    """Shots and main camera. One decoding at 160 px: at ~25 fps for TransNetV2 (cuts), of which the
    frames nearest to the cheap-pass fps give the colour histograms (dissolves) and the court's lines
    (main camera, v3: colour alone took close-ups in front of a wall of the court's colour for the
    main camera). Without the model, or if it fails, the histograms alone give the cuts (as in v1)."""
    from .scenes import CutModel

    fps = ctx.cfg["cheap_pass"]["fps"]
    sc = ctx.cfg.get("scenes") or {}
    info = probe(ctx.video)
    model, why = None, None
    onnx = resolve_path(sc.get("onnx"))
    if onnx is None or not onnx.exists():
        why = f"falta {sc.get('onnx') or 'models/transnetv2.onnx'}"
    else:
        try:
            model = CutModel(onnx, ctx.cfg.get("device", "cpu"))
        except Exception as e:                    # noqa: BLE001 — broken model file: histograms
            why = f"no se pudo cargar TransNetV2 ({str(e)[:150]})"
    read_fps = max(fps, float(sc.get("fps", 25))) if model else fps
    total = int(info.duration * read_fps)

    def frames_with_progress():
        for i, fr in enumerate(read_frames(info, width=160, fps=read_fps, hwaccel=ctx.cfg.get("hwaccel"))):
            ctx.progress(i + 1, total, "fotogramas")
            yield fr
    res: dict = {}
    shots, mask = analyse_video(frames_with_progress(), cut_model=model, fps=fps, fast_fps=read_fps,
                                threshold=float(sc.get("threshold", 0.5)), info=res)
    if res.get("error"):
        why = f"TransNetV2 falló ({res['error']})"
    if why:
        ctx.log(f"  AVISO: cortes de plano solo con histogramas de color: {why}")
    if res.get("main_rule") == "colour" and shots:
        ctx.log("  AVISO: no se ven las líneas de la pista desde el fondo; cámara principal solo por el color")
    _write(ctx.path("scenes.json"), {"fps": fps, "shots": [vars(s) for s in shots], "detector": res.get("detector"),
                                     "main_rule": res.get("main_rule")})
    main = [s for s in shots if s.main_camera]
    out = {"shots": len(shots), "main_camera_shots": len(main), "detector": res.get("detector"),
           "main_camera_min": round(sum(s.end - s.start for s in main) / fps / 60, 1), "main_rule": res.get("main_rule")}
    if "main_frames_colour" in res:
        out["main_camera_min_colour"] = round(res["main_frames_colour"] / fps / 60, 1)    # what v2 gave
        out["main_views"] = res.get("views", 0)
    return out


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
    """The YOLO pose model of the cheap pass: predict(frame, conf, prepared) → (boxes (N,4),
    keypoints (N,17,2), conf (N,17)); prepare(frame) its input, computable ahead in another thread."""
    from .pose.backend import pose_model, set_device, uses_fp16

    set_device(cfg.get("device", "cpu"), uses_fp16(cfg))
    return pose_model(cfg.get("yolo_pose", "yolo11m-pose.pt"), cfg["cheap_pass"].get("imgsz", 960))


def _appearances(frame: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    from .pose.yolo import appearance

    return np.array([appearance(frame, bb) for bb in boxes], np.float32).reshape(len(boxes), 32)


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


def _fp16_setting(c) -> dict:
    """{"fp16": True} only when the half-precision pose model is in use: with the default (off) the
    fingerprints, and so the results already computed, stay as they were."""
    from .pose.backend import uses_fp16
    return {"fp16": True} if uses_fp16(c) else {}


@stage("players", "4", deps=("scenes", "court"),
       settings=lambda c: {"fps": c["cheap_pass"]["fps"], "imgsz": c["cheap_pass"].get("imgsz", 960), **_fp16_setting(c)},
       outputs=("players.npz",), resource=lambda c: "gpu" if c.get("device", "cpu") == "dml" else "cpu")
def st_players(ctx: Context):
    """Cheap pose on match-play frames only (main camera with the court found; cheap fps, full
    width for small players)."""
    from .pose.yolo import _objects

    sc = _read(ctx.path("scenes.json"))
    fps = sc["fps"]
    court = _read(ctx.path("court.json")) if ctx.path("court.json").exists() else None
    main = play_mask(sc, court)
    total_main = sum(s["end"] - s["start"] for s in sc["shots"] if s["main_camera"])
    ctx.log(f"  juego con pista: {main.sum() / fps / 60:.1f} min de {total_main / fps / 60:.1f} min de cámara principal")
    model = _pose_detector(ctx.cfg)
    info = probe(ctx.video)
    # ffmpeg hands over frames already at the model's size (it letterboxes to imgsz anyway): a quarter
    # of the pixels to decode, pipe and resize; points and boxes are scaled back to the full frame
    imgsz = int(ctx.cfg["cheap_pass"].get("imgsz", 960))
    width = imgsz if info.width > imgsz else None
    sx = info.width / width if width else 1.0
    # only the main-camera stretches are decoded (seeking past replays, close-ups and changeovers:
    # a third of a broadcast or more)
    edges = np.flatnonzero(np.diff(np.r_[0, main.astype(int), 0]))

    def frames():
        """(frame index, frame, model input) of every play frame. Runs in a reader thread (read_ahead):
        decoding and the letterbox of the next frames overlap with the model on the current one."""
        for a, b_ in zip(edges[::2], edges[1::2]):
            for k_, frame in enumerate(read_frames(info, start=a / fps, duration=(b_ - a) / fps, fps=fps, width=width,
                                                   hwaccel=ctx.cfg.get("hwaccel"))):
                i = int(a) + k_
                if i >= b_:
                    break
                yield i, frame, model.prepare(frame)

    from concurrent.futures import ThreadPoolExecutor
    from time import perf_counter

    boxes, kps, confs, feats, idx = [], [], [], [], []
    reader: dict = {}
    t_wait = t_model = 0.0
    t_app = [0.0]

    def app(frame, b):              # appearance histograms in a second thread, while the model runs
        t = perf_counter()
        f = _appearances(frame, b)
        t_app[0] += perf_counter() - t
        return f

    t_start = t0 = perf_counter()
    with ThreadPoolExecutor(max_workers=1) as pool:
        for i, frame, prep in read_ahead(frames, prefetch=4, stats=reader):
            t1 = perf_counter()
            t_wait += t1 - t0
            b, k, c = model.predict(frame, conf=0.3, prepared=prep)
            feats.append(pool.submit(app, frame, b))
            boxes.append((b * sx).astype(np.float32)); kps.append((k * sx).astype(np.float32)); confs.append(c.astype(np.float32))
            idx.append(i)
            t0 = perf_counter()
            t_model += t0 - t1
            ctx.progress(len(idx), int(main.sum()), "fotogramas con jugadoras")
        feats = [f.result() for f in feats]
    wall = perf_counter() - t_start
    savez_atomic(ctx.path("players.npz"), fps=fps, frames=np.array(idx), height=info.height,
                        boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs), feats=_objects(feats))
    t_read = reader.get("busy_s", 0.0)
    ctx.log(f"  tiempo: {wall / 60:.1f} min para {len(idx)} fotogramas a {width or info.width} px · modelo {t_model / 60:.1f} min · "
            f"leer vídeo y preparar la entrada {t_read / 60:.1f} min en otro hilo (espera real {t_wait / 60:.1f} min) · "
            f"apariencia {t_app[0] / 60:.1f} min en otro hilo")
    return {"frames": len(idx), "wall_min": round(wall / 60, 1), "model_min": round(t_model / 60, 1),
            "read_min": round(t_read / 60, 1), "wait_min": round(t_wait / 60, 1), "appearance_min": round(t_app[0] / 60, 1)}


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


def _players(ctx) -> dict:
    """players.npz read once into memory: indexing a lazily loaded .npz re-reads and unpickles the whole
    array on every access (with 6000 frames that made identity and candidates take 30 min each)."""
    with np.load(ctx.path("players.npz"), allow_pickle=True) as z:
        return {k: z[k] for k in z.files}


def near_runs(d, sk, court: dict | None = None, with_sel: bool = False):
    """Each continuous run of main-camera frames with the near player tracked (cuts break tracking).
    court: the court stage's output, to start the tracking on the person standing on the court.

    Yields (run indices, cleaned keypoints, confidences, body height px, mean appearance), and with
    with_sel also the index of her detection in each frame of the run (-1 where she was not found)."""
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
        if with_sel:
            yield run, img, cf, body_height(img, sk), np.mean(app, axis=0), np.asarray(sel)
        else:
            yield run, img, cf, body_height(img, sk), np.mean(app, axis=0)


def _far_player(boxes: np.ndarray, H, near: int) -> int | None:
    """Index of the far player among a frame's detections (feet on the far half of the court, the
    tallest such box), or None. H: court→image homography of the shot."""
    from .court_metrics import to_court

    if H is None or len(boxes) < 2:
        return None
    feet = np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, boxes[:, 3]]
    c = to_court(H, feet)
    ok = (np.abs(c[:, 0]) <= 6.5) & (c[:, 1] >= 13.0) & (c[:, 1] <= 31.0)
    ok[near] = False
    if not ok.any():
        return None
    hh = np.where(ok, boxes[:, 3] - boxes[:, 1], -1)
    return int(np.argmax(hh))


def run_clothes(ctx: Context, d: dict, tracks: list, court: dict | None, per_run=6, min_far_px=40.0):
    """Clothing code of the near player in each run (and of the far player when the players stage
    saw her in the same frames), from up to `per_run` frames per run spread over it, each the
    stillest one of its stretch with the torso visible (the frame is re-read by its time; a moving
    player would be off her keypoints by the frame's offset).

    tracks: per run (run indices, her detection index per frame, cleaned keypoints).
    Returns (codes (R, CLOTHES_DIM), [(run, far code)]) or (None, []) when the video cannot be read."""
    from .clothes import CLOTHES_DIM, aggregate, clothing_feature

    try:
        video = ctx.video
        if not Path(video).is_file():
            raise FileNotFoundError(str(video))
        info = probe(video)
    except Exception as e:  # noqa: BLE001  (no video: the players stage's whole-box histograms instead)
        ctx.log(f"  ropa: no se puede leer el vídeo ({type(e).__name__}); se usa la apariencia de la caja entera")
        return None, []
    fps, frames = float(d["fps"]), d["frames"]
    want = []                                                    # (time, run, frame index in run)
    for i, (run, sel, img) in enumerate(tracks):
        good = np.array([j >= 0 and bool(np.all(d["confs"][run[t]][j][[5, 6, 11, 12]] > 0.3)) for t, j in enumerate(sel)])
        if not good.any():
            good = sel >= 0
        if not good.any():
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)          # frames without the torso
            ctr = np.nanmean(img[:, [5, 6, 11, 12]], axis=1)
        sp = np.full(len(run), np.inf)
        if len(run) > 2:
            sp[1:-1] = np.linalg.norm(ctr[2:] - ctr[:-2], axis=1)
        sp = np.where(np.isfinite(sp), sp, 1e6)
        cand = np.flatnonzero(good)
        for part in np.array_split(cand, min(per_run, len(cand))):
            t = int(part[np.argmin(sp[part])])
            want.append((frames[run[t]] / fps, i, t))
    want.sort()
    codes = np.full((len(tracks), CLOTHES_DIM), np.nan, np.float32)
    near_c: dict[int, list] = {}
    far_c: dict[int, list] = {}
    # software decoding, as the scoreboard's frames: on the PC (19-10) the iGPU decoder took ~15 s per frame
    # here (98 min for 396 frames of a 35-min test), against ~3.6 s per frame with OCR for the scoreboard
    stream = frames_at(info, [w[0] for w in want]) if want else iter(())
    t_dec = t_feat = 0.0
    t_last = time.perf_counter()
    for k, ((t_s, i, t), (_, frame)) in enumerate(zip(want, stream)):
        t_now = time.perf_counter()
        t_dec += t_now - t_last
        ctx.progress(k + 1, len(want), "fotogramas (ropa)")
        if frame is None:
            t_last = time.perf_counter()
            continue
        run, sel, _ = tracks[i]
        fi, j = run[t], int(sel[t])
        bx, kp, cf = d["boxes"][fi], d["kps"][fi], d["confs"][fi]
        sx = frame.shape[1] / float(info.width)                   # 1 unless the decoder resized it
        near_c.setdefault(i, []).append(clothing_feature(frame, kp[j] * sx, cf[j], bx[j] * sx))
        H = court_at(court, t_s)[0] if court else None
        f = _far_player(bx, H, j)
        if f is not None and (bx[f, 3] - bx[f, 1]) * sx >= min_far_px:
            far_c.setdefault(i, []).append(clothing_feature(frame, kp[f] * sx, cf[f], bx[f] * sx))
        t_last = time.perf_counter()
        t_feat += t_last - t_now
    if want:
        ctx.log(f"  ropa: {len(want)} fotogramas · leerlos {t_dec:.0f} s, medir la ropa {t_feat:.0f} s")
    for i, c in near_c.items():
        codes[i] = aggregate(c)
    far = [(i, aggregate(c)) for i, c in sorted(far_c.items()) if len(c) >= 2]
    return codes, far


@stage("identity", "5", deps=("players", "score", "court", "audio"), outputs=("identity.json",), match_fields=lambda m: {"player": m.player.name})
def st_identity(ctx: Context):
    """Is the near player the target in each run? Two independent cues, fused:
    - the end-change chain: serves + the scoreboard's serve marker name who is near in some runs
      (when the near player serves she is the scoreboard's server; when she waits to return a serve
      she is the other one), and the games read on the scoreboard carry it to every run;
    - her clothes (shirt and shorts/skirt, without the court colours) split the runs into two people.
    Agreement decides with high confidence; a disagreement is won by the stronger evidence or left
    «dudoso» (clothes.fuse)."""
    from .clothes import identity_from_cues
    from .identity import decide_by_ends, end_changes, near_receives, near_serves

    d = _players(ctx)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    score = _read(ctx.path("score.json"))
    court = _read(ctx.path("court.json"))
    onsets = load_onsets(ctx)
    runs, feats, votes, tracks = [], [], [], []
    for run, img, cf, h, app, sel in near_runs(d, sk, court, with_sel=True):
        i = len(runs)
        runs.append({"start": int(frames[run[0]]), "end": int(frames[run[-1]]) + 1})
        feats.append(app)
        tracks.append((run, sel, img))
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
    # end changes from the scoreboard at the middle of each run (and the games read, for the check
    # that the clothes do not change inside a game)
    parities, games = [], []
    for r in runs:
        sr = score_at(score, (r["start"] + r["end"]) / 2 / fps, max_age_s=150.0)
        parities.append(None if sr is None else end_changes(sr.get("games"), sr.get("points"), sr.get("tiebreak", False)))
        games.append(None if sr is None or not sr.get("games") else json.dumps(sr["games"]))
    base = decide_by_ends(parities, votes)
    ends = [None if base is None or p is None else bool(base ^ bool(p % 2)) for p in parities]
    direct = [r.get("serve_vote", r.get("return_vote")) for r in runs]
    codes, far = run_clothes(ctx, d, tracks, court) if runs else (None, [])
    per, summ = identity_from_cues(codes, far, np.array(feats) if feats else None, ends, direct, votes, games)
    for r, p, par, e in zip(runs, per, parities, ends):
        r["end_changes"] = par
        r["cluster"] = p["clothes"]["group"] if p["clothes"] else -1
        r["near_is_target"], r["method"] = p["near_is_target"], p["method"]
        if p["clothes"]:
            r["clothes_margin"], r["clothes_says"] = p["clothes"]["margin"], p["clothes"]["says"]
        if e is not None and e != r["near_is_target"]:
            r["ends_said"] = e                         # what the end-change chain said, overruled or doubtful
    _write(ctx.path("identity.json"), {"fps": fps, "target_cluster": summ["target_cluster"], "confidence": summ["confidence"],
                                       "votes": summ["votes"], "ends_base": base, "clothes": summ["clothes"], "runs": runs})
    ctx.log(f"  identidad: {summ['decided']}/{len(runs)} planos · ropa y cambios de lado de acuerdo en {summ['agree']}, "
            f"solo cambios de lado {summ['ends_only']}, solo ropa {summ['clothes_only']}, la ropa corrige el marcador en "
            f"{summ['clothes_won']}, el saque visto en {summ['ends_won']}, dudosos {summ['doubtful']} · "
            f"ropa: {summ['clothes']['source']}, separación {summ['clothes']['separation']}")
    return {"runs": len(runs), **{k: v for k, v in summ.items() if k != "target_cluster"}}


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


def replay_spans_without_board(score: dict) -> list[tuple[float, float]]:
    """Short main-camera shots where the scoreboard was looked for and never read: replays, in a broadcast
    whose scoreboard is read in most shots. When it is read in few (18-10, Osaka – Rybakina: 21 readings in
    234 samples, a scoreboard the OCR hardly reads), its absence says nothing and no shot is a replay for
    that reason (69 of 148 runs of her were dropped, leaving 3 strokes)."""
    shots = score.get("shots", [])
    tried = [x for x in shots if x["tried"] >= 2]
    if sum(x["read"] for x in shots) < 10 or not tried or sum(x["read"] > 0 for x in tried) < 0.5 * len(tried):
        return []
    return [(x["start"], x["end"]) for x in tried if x["read"] == 0 and x["end"] - x["start"] < 30]


def _audio_tracks(ctx: Context, d: dict, sk, court: dict, tol_s=0.35) -> tuple[list, int]:
    """The audio transients' tracks and the one to use: with several (commentary vs ambient), the one
    that sounds with the near player's swings."""
    fps, frames = float(d["fps"]), d["frames"]
    audio = _read(ctx.path("audio_onsets.json"))
    tracks = audio.get("tracks") or [audio]
    track = 0
    if len(tracks) > 1:
        peaks = [frames[run[p]] / fps for run, img, cf, h, _ in near_runs(d, sk, court)
                 for p in swing_peaks(speed(to_body_frame(img, sk, h)[:, sk["dom_wrist"]], fps), fps,
                                      min_gap=1.0, height=1.5, prominence=1.0)]
        span = float(frames[-1] - frames[0]) / fps if len(frames) else 0.0
        track = choose_audio_track(tracks, np.array(peaks), tol_s, span)
    return tracks, track


def _spotter(c: dict) -> dict:
    return c.get("spotter") or {}


def spotter_on(c: dict) -> bool:
    """`spotter.enabled` (default off): the candidates come from the learned spotter (spotting.json)."""
    return bool(_spotter(c).get("enabled", False))


def _spotter_path(c: dict) -> Path | None:
    return resolve_path(_spotter(c).get("onnx") or "models/spotting.onnx")


def _spotting_settings(c: dict) -> dict:
    if not spotter_on(c):
        return {"enabled": False}
    p = _spotter_path(c)
    sp = _spotter(c)
    return {"enabled": True, "onnx": str(sp.get("onnx") or "models/spotting.onnx"), "threshold": sp.get("threshold"),
            # the model itself: retraining it re-runs the spotting and what follows
            "model": model_state(p), "meta": model_state(p.with_suffix(".json")) if p is not None else None}


@stage("spotting", "1", deps=("players", "audio", "court", "scenes", "identity"), settings=_spotting_settings,
       outputs=("spotting.json",))
def st_spotting(ctx: Context):
    """The strokes of both players found by the learned spotter (tennisbio.spotting, docs/plan_maestro.md
    block 1): features of the cheap pass → the ONNX model (CPU, in pieces) → decoded strokes, written to
    spotting.json as [{t, side, kind, score}]. Off unless `spotter.enabled: true` (then nothing is
    computed and the list is empty)."""
    if not spotter_on(ctx.cfg):
        _write(ctx.path("spotting.json"), [])
        return {"enabled": False}
    from .spotting import (CLASSES, FEATURE_DIM, build_features, decode, fit_features, model_meta, predict_onnx,
                           sound_flux_stream)

    onnx = _spotter_path(ctx.cfg)
    if onnx is None or not onnx.exists():
        raise FileNotFoundError(f"falta el detector de golpes entrenado ({onnx}); vuelve a instalar o apaga "
                                "`spotter.enabled` en config/local.yaml")
    meta = model_meta(onnx)
    if list(meta.get("classes") or []) != list(CLASSES):
        raise ValueError(f"el detector entrenado tiene otras clases ({meta.get('classes')}) que el proceso "
                         f"({list(CLASSES)}): hay que volver a entrenarlo")
    F = int(meta.get("feature_dim", FEATURE_DIM))
    d = _players(ctx)
    sk = Skeleton("coco17", ctx.match.player.hand)
    court = _read(ctx.path("court.json")) if ctx.path("court.json").exists() else {}
    tracks, track = _audio_tracks(ctx, d, sk, court)
    onsets = np.array(tracks[track].get("t", [])) if tracks else np.zeros(0)
    del d
    t0 = time.time()
    # the sound flux only for a model trained with it (it reads the whole soundtrack)
    feats = build_features(ctx.dir, ctx.match.player.hand, video=ctx.video if F == FEATURE_DIM else None,
                           onsets=onsets, flux=sound_flux_stream)
    fps = float(feats["fps"])
    mfps = float(meta.get("fps") or fps)
    if abs(fps - mfps) > 1e-6:
        ctx.log(f"  AVISO: el detector se entrenó a {mfps:g} fps y la pasada barata de este partido va a {fps:g} fps "
                f"(cheap_pass.fps): se usa igual, pero encontrará peor los golpes. Pon cheap_pass.fps: {mfps:g} y repite.")
    X = fit_features(feats["X"], F)
    sp = _spotter(ctx.cfg)
    prob = predict_onnx(onnx, X, chunk=int(sp.get("chunk", 4096)), overlap=int(sp.get("overlap", 64)))
    thr = float(sp.get("threshold") or meta.get("threshold", 0.5))
    found = decode(prob, fps, thr)
    # nothing to see outside play (rows of zeros): a stroke there is noise of the model
    play = feats["X"][:, -1] > 0
    pad = int(round(0.5 * fps))

    def in_play(t: float) -> bool:
        f = int(round(t * fps))
        return bool(play[max(0, f - pad):f + pad + 1].any())
    strokes = [e for e in found if in_play(e["t"])]
    _write(ctx.path("spotting.json"), strokes)
    n_near = sum(e["side"] == "near" for e in strokes)
    ctx.log(f"  detector entrenado: {len(strokes)} golpes ({n_near} cercanos, {len(strokes) - n_near} lejanos) en "
            f"{len(X) / fps / 60:.0f} min de vídeo · umbral {thr:g} · {time.time() - t0:.0f} s")
    return {"enabled": True, "strokes": len(strokes), "near": n_near, "far": len(strokes) - n_near,
            "out_of_play": len(found) - len(strokes), "threshold": thr, "fps": fps, "model_fps": mfps,
            "feature_dim": F, "audio_track": track}


def spotter_candidates(spotted: list[dict], identity: dict, fps: float, runs: list[tuple], no_board: list,
                       onsets: np.ndarray, tol_s: float = 0.35) -> tuple[list[dict], dict]:
    """Candidates from the learned spotter's strokes (spotting.json), with the same fields the fine passes
    read from the rules' ones: t, side, audio (an impact sound within tol_s), identity (is the near player
    the target there: True / False / None) and target (whose stroke it is: near → identity, far → its
    opposite, None when undecided, so fine_doubtful keeps it). runs: (t0, t1, replay) of the near player's
    runs; a stroke in a replay run, or outside the runs inside a stretch without the scoreboard (no_board),
    is left out (already counted live). Also the spotter's kind and score, and source "spotter"."""
    ifps = float(identity.get("fps") or fps)
    onsets = np.asarray(onsets, float)
    out, info = [], {"replays": 0}
    for e in spotted:
        t = float(e["t"])
        run = next((r for r in runs if r[0] - 0.5 / fps <= t <= r[1] + 0.5 / fps), None)
        if (run is not None and run[2]) or (run is None and any(a <= t < b for a, b in no_board)):
            info["replays"] += 1
            continue
        who = near_is_target(identity, int(round(t * ifps)))
        near = e["side"] == "near"
        out.append({"t": t, "audio": bool(len(onsets) and np.min(np.abs(onsets - t)) <= tol_s), "side": e["side"],
                    "identity": who, "target": who if near or who is None else not who,
                    "kind": e.get("kind"), "score": e.get("score"), "source": "spotter"})
    return out, info


@stage("candidates", "9", deps=("players", "audio", "identity", "court", "score"), outputs=("candidates.json", "audio_track.json"),
       reviews=("identidad_clic.json",),
       # with the learned spotter (off by default) it reads spotting.json; off, its fingerprint is the one it always was
       settings=lambda c: {"spotter": True} if spotter_on(c) else {},
       cfg_deps=lambda c: ("spotting",) if spotter_on(c) else ())
def st_candidates(ctx: Context, tol_s=0.35):
    """Near-player stroke candidates: swing peaks of the near player at cheap fps, confirmed by
    an audio transient when one is close. Each candidate records who the near player is
    (identity: True target, False opponent, None undecided); the fine passes pick their own.
    Each candidate is checked again in the fine pass. With `spotter.enabled`, the candidates of both
    ends are the learned spotter's strokes instead (spotter_candidates), with the same identity."""
    d = _players(ctx)
    fps, frames = float(d["fps"]), d["frames"]
    sk = Skeleton("coco17", ctx.match.player.hand)
    court = _read(ctx.path("court.json"))
    tracks, track = _audio_tracks(ctx, d, sk, court, tol_s)
    if len(tracks) > 1:                    # commentary vs ambient: the one that sounds with her swings
        ctx.log(f"  sonido: pista {track + 1} de {len(tracks)} (la que coincide con los golpes)")
    _write(ctx.path("audio_track.json"), {"track": track, "tracks": len(tracks)})
    onsets = np.array(tracks[track]["t"]) if tracks else np.zeros(0)
    identity = _read(ctx.path("identity.json"))
    from .identity import PICK_FILE, apply_pick
    if ctx.path(PICK_FILE).exists():          # the user's click: which of the two is her (19-10)
        identity, why = apply_pick(identity, _read(ctx.path(PICK_FILE)))
        ctx.log(f"  identidad con el clic: {why}")
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
    no_board = replay_spans_without_board(score)
    board_works = bool(no_board)
    # replays from the main camera with the scoreboard still on: her feet retrace a path of the last
    # seconds, slower (slow motion) or without impact sounds (tennisbio.replays)
    from .court_metrics import to_court
    from .replays import Run, find_replays
    runs_all, paths = list(near_runs(d, sk, court)), []
    for run, img, cf, h, _ in runs_all:
        t0, t1 = frames[run[0]] / fps, frames[run[-1]] / fps
        H = court_at(court, t0)[0]
        with warnings.catch_warnings():          # an ankle unseen in a frame stays NaN
            warnings.simplefilter("ignore", RuntimeWarning)
            feet = np.nanmean(img[:, [sk["left_ankle"], sk["right_ankle"]]], axis=1) if H is not None else None
        path = to_court(H, np.nan_to_num(feet, nan=-1e6)) if feet is not None else np.full((len(run), 2), np.nan)
        if feet is not None:
            path[~np.isfinite(feet).all(1)] = np.nan
        paths.append(Run(t0, t1, path, fps, int(np.sum((onsets >= t0) & (onsets <= t1))) if len(onsets) else 0))
    slow_replays = set(find_replays(paths))
    if spotter_on(ctx.cfg):
        spans = []
        for k, (run, img, cf, h, _) in enumerate(runs_all):
            t_mid = frames[run[len(run) // 2]] / fps
            spans.append((frames[run[0]] / fps, frames[run[-1]] / fps,
                          bool((board_works and any(a <= t_mid < b for a, b in no_board)) or k in slow_replays)))
        cands, info = spotter_candidates(_read(ctx.path("spotting.json")), identity, fps, spans,
                                         no_board if board_works else [], onsets, tol_s)
        _write(ctx.path("candidates.json"), cands)
        ctx.log(f"  candidatos del detector entrenado: {len(cands)} ({sum(c['side'] == 'far' for c in cands)} lejanos; "
                f"{info['replays']} en repeticiones, fuera)")
        return {"candidates": len(cands), "far": sum(c["side"] == "far" for c in cands),
                "with_audio": sum(c["audio"] for c in cands), "source": "spotter",
                "opponent_strokes": sum(c["target"] is False for c in cands),
                "identity_unknown": sum(c["identity"] is None for c in cands),
                "replay_strokes_skipped": info["replays"], "replay_runs": sum(r[2] for r in spans), "audio_track": track}
    for k, (run, img, cf, h, _) in enumerate(runs_all):
        t_mid = frames[run[len(run) // 2]] / fps
        if (board_works and any(a <= t_mid < b for a, b in no_board)) or k in slow_replays:
            replays += 1                  # a replay: its strokes were already counted live
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
        if not len(onsets):
            continue
        # the far player's hits: impact sounds of this run that are not the near player's; the
        # fine pass keeps only those confirmed by the ball turning at the far player. In a run whose
        # identity is undecided they are kept too, with target None (fine_doubtful): never lost
        t0, t1 = frames[run[0]] / fps, frames[run[-1]] / fps
        last = -9.0
        for t in onsets[(onsets >= t0 + 0.5) & (onsets <= t1 - 0.5)]:
            if any(abs(t - x) <= 0.5 for x in near_t) or t - last < 1.0:
                continue
            last = t
            cands.append({"t": float(t), "audio": True, "side": "far", "identity": who,
                          "target": None if who is None else not who})
    _write(ctx.path("candidates.json"), cands)
    return {"candidates": len(cands), "far": sum(c["side"] == "far" for c in cands),
            "with_audio": sum(c["audio"] for c in cands),
            "opponent_runs": skipped, "identity_unknown": sum(c["identity"] is None for c in cands),
            "replay_runs_skipped": replays, "replays_by_path": len(slow_replays), "audio_track": track}


def _near_paths(d: dict, sk: Skeleton, court: dict, onsets: np.ndarray) -> list:
    """Her runs on the main camera with her feet path on the court (replays.Run), built as in the
    candidates stage (which keeps its own copy: its output must not change)."""
    from .court_metrics import to_court
    from .replays import Run

    fps, frames = float(d["fps"]), d["frames"]
    out = []
    for run, img, cf, h, _ in near_runs(d, sk, court):
        t0, t1 = frames[run[0]] / fps, frames[run[-1]] / fps
        H = court_at(court, t0)[0]
        with warnings.catch_warnings():          # an ankle unseen in a frame stays NaN
            warnings.simplefilter("ignore", RuntimeWarning)
            feet = np.nanmean(img[:, [sk["left_ankle"], sk["right_ankle"]]], axis=1) if H is not None else None
        path = to_court(H, np.nan_to_num(feet, nan=-1e6)) if feet is not None else np.full((len(run), 2), np.nan)
        if feet is not None:
            path[~np.isfinite(feet).all(1)] = np.nan
        out.append(Run(t0, t1, path, fps, int(np.sum((onsets >= t0) & (onsets <= t1))) if len(onsets) else 0))
    return out


def _views_settings(c: dict) -> dict:
    v = c.get("views") or {}
    return {"people": bool(v.get("people", True)), "max_fits": int(v.get("max_fits", 80)),
            "samples": int(v.get("samples", 3))}


def _sample_views(ctx: Context, scenes: dict, shots: list[int], main_pitch) -> dict[int, dict]:
    """Evidence of the non-live shots from 1-3 frames each (one ffmpeg pass over the sampled times):
    lines, the tallest person (the cheap pass's pose model, when it loads) and, where the court is seen
    from an end, the camera tilt of a fitted court (at most `views.max_fits` fits per match)."""
    from .court import camera_pitch_deg, fit_court
    from .views import frame_evidence, merge_evidence, sample_times

    if not shots:
        return {}
    st = _views_settings(ctx.cfg)
    model = None
    if st["people"]:
        try:
            model = _pose_detector(ctx.cfg)
        except Exception as e:                   # noqa: BLE001 — without it: no people size, lower confidence
            ctx.log(f"  AVISO: tomas sin tamaño de las personas (no se pudo cargar el modelo: {str(e)[:150]})")
    items = sorted((t, i) for i in shots for t in sample_times(scenes, i, st["samples"]))
    per: dict[int, list] = {}
    fits = 0
    info = probe(ctx.video)
    for n, ((t, i), (_, fr)) in enumerate(zip(items, frames_at(info, [t for t, _ in items], hwaccel=ctx.cfg.get("hwaccel")))):
        ctx.progress(n + 1, len(items), "fotogramas de otras tomas")
        if fr is None:
            continue
        ph = None
        if model is not None:
            try:
                b, _, _ = model.predict(fr, conf=0.3)
                ph = float(((b[:, 3] - b[:, 1]).max() / fr.shape[0])) if len(b) else 0.0
            except Exception:                    # noqa: BLE001 — one frame without people size
                ph = None
        ev = frame_evidence(fr, ph)
        if ev["lines_behind"] >= 1 and fits < st["max_fits"]:
            fits += 1
            try:
                fit = fit_court(fr)
                if fit is not None:
                    ev["pitch_deg"] = round(camera_pitch_deg(fit, fr.shape), 1)
            except Exception:                    # noqa: BLE001 — no tilt for this frame
                pass
        per.setdefault(i, []).append(ev)
    return {i: merge_evidence(v) for i, v in per.items()}


@stage("views", "1", deps=("scenes", "court", "players", "score", "audio", "candidates"), settings=_views_settings,
       outputs=("views.json",))
def st_views(ctx: Context):
    """Replays and the other cameras, used and linked to the live stroke they show (tennisbio.views,
    #218): every non-live stretch classified (main-camera replay, side, front, close-up, other) with its
    evidence, and linked by her feet path (main-camera replays, with the slow-motion factor) or by time
    order and the impacts heard. Only a few frames of the non-live shots are decoded."""
    from .views import build_views, main_pitch_of, views_to_sample

    sc = _read(ctx.path("scenes.json"))
    court = _read(ctx.path("court.json")) if ctx.path("court.json").exists() else None
    if court is not None and not any(o.get("H") is not None for o in court.get("shots", [])):
        court = None
    score = _read(ctx.path("score.json")) if ctx.path("score.json").exists() else {}
    onsets = load_onsets(ctx)
    cands = _read(ctx.path("candidates.json")) if ctx.path("candidates.json").exists() else []
    runs = []
    if court is not None and ctx.path("players.npz").exists():
        d = _players(ctx)
        if len(d.get("frames", [])):
            runs = _near_paths(d, Skeleton("coco17", ctx.match.player.hand), court, onsets)
    if court is None:
        ctx.log("  AVISO: sin pista en ningún plano: no se distingue el juego de las repeticiones; todas las tomas se clasifican por su aspecto")
    no_board = replay_spans_without_board(score)
    replay_spans = list(no_board)
    from .replays import find_replays
    replay_spans += [(runs[i].t0, runs[i].t1) for i in find_replays(runs)] if runs else []
    shots = views_to_sample(sc, court, replay_spans)
    evidence = _sample_views(ctx, sc, shots, main_pitch_of(court))
    doc = build_views(sc, court, runs, no_board, onsets, [c for c in cands if c.get("t") is not None], evidence)
    _write(ctx.path("views.json"), doc)
    return doc["summary"]


@stage("views_link", "1", deps=("views", "fine"), outputs=("views_link.json",))
def st_views_link(ctx: Context):
    """Her strokes (strokes.json) get an optional `views` list: the replays and other cameras that show
    each one, and `slowmo_view` when one is a main-camera slow-motion replay. Only those two keys are
    added (tennisbio.views.attach); every other field of the fine pass stays as it was. Re-runs when the
    fine pass or the views change."""
    from .views import attach, coverage

    f = ctx.path("strokes.json")
    strokes = _read(f) if f.exists() else []
    doc = _read(ctx.path("views.json")) if ctx.path("views.json").exists() else None
    if strokes:
        strokes = attach(strokes, doc)
        _write(f, strokes)
    cov = coverage(strokes)
    _write(ctx.path("views_link.json"), cov)
    return cov


def grab_frame(video: Path, t: float) -> np.ndarray | None:
    """One full-resolution BGR frame at time t (fast seek). Piped as BMP: the same pixels as PNG
    without compressing and decompressing every frame."""
    import cv2

    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "bmp", "pipe:1"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


def _prefetch(fn, items, ahead=4):
    """Yield (item, fn(item)) in order while the next `ahead` calls already run in threads (each
    grab_frame is its own ffmpeg process: the seeks overlap with the court fitting). At most
    ahead + 1 results are held in memory."""
    from collections import deque
    from concurrent.futures import ThreadPoolExecutor

    items = list(items)
    with ThreadPoolExecutor(max_workers=max(1, ahead)) as ex:
        q = deque()
        it = iter(items)
        for x in it:
            q.append((x, ex.submit(fn, x)))
            if len(q) > ahead:
                break
        while q:
            x, f = q.popleft()
            nxt = next(it, None)
            if nxt is not None:
                q.append((nxt, ex.submit(fn, nxt)))
            yield x, f.result()


def _same_court(H1, H2, tol_px=1.0) -> bool:
    from .court import _CORNERS

    p1, p2 = _CORNERS @ np.asarray(H1).T, _CORNERS @ np.asarray(H2).T
    return bool(np.abs(p1[:, :2] / p1[:, 2:] - p2[:, :2] / p2[:, 2:]).max() <= tol_px)


def _thumb(frame: np.ndarray) -> np.ndarray:
    """Tiny grey version of a frame (64×36), minus its mean brightness (a cloud or the camera's
    exposure changes it all), to tell whether the camera kept the same view."""
    import cv2

    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    th = cv2.resize(g, (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
    return th - th.mean()


def _same_view(a, b, tol=12.0) -> bool:
    """Same camera view (no cut, no big pan or zoom): the thumbnails differ little on average
    (players, ball and graphics are small at 64×36; a cut to a close-up changes most of it)."""
    return a is not None and b is not None and float(np.abs(a - b).mean()) <= tol


@stage("court", "4", deps=("scenes",), outputs=("court.json",))
def st_court(ctx: Context, n_fit=6, min_score=0.5, every_s=8.0, step_s=2.0, refine_s=0.5, fill_score=0.3,
             max_known=64):
    """Court homography of the main camera, decided on frames sampled every `step_s` seconds of
    every main-camera shot (not one per shot: the shot classifier misses many cuts between the
    main camera and close-ups with the same colours, so one "shot" often holds a rally AND the
    close-up that follows; one frame per stretch threw away the rally whenever it fell on the
    close-up). Each frame first tries the courts already found in this match (a broadcast uses a
    few camera presets: the best one that scores ≥ min_score, the same bar as a fresh fit); a full
    search runs at most every `every_s` seconds of a shot (it is the slow part, and on close-ups
    it finds nothing). Where two neighbouring frames disagree (court / no court / another preset)
    the change is located by bisection to `refine_s`. A frame where the court is not found but
    the camera has not moved since a neighbouring frame with the court (same view: a player or a
    shadow hides lines) keeps that court if it still scores ≥ fill_score there. Every frame of a
    shot takes the result of its nearest sample."""
    from bisect import bisect_left, insort

    from .court import CourtFit, LineMasks, camera_pitch_deg, fit_court, match_known, score_many

    sc = _read(ctx.path("scenes.json"))
    fps = sc["fps"]
    main = [s for s in sc["shots"] if s["main_camera"]]
    if not main:
        _write(ctx.path("court.json"), {"shots": []})
        return {"main_camera_shots": 0}
    grab = lambda t: grab_frame(ctx.video, t)
    mid = lambda s: (s["start"] + s["end"]) / 2 / fps
    known = []                       # courts found in this match, the best of the long shots first

    def remember(fit):
        if not any(_same_court(fit.H, k.H) for k in known) and len(known) < max_known:
            known.append(fit)

    first = []
    for _, fr in _prefetch(grab, [mid(s) for s in sorted(main, key=lambda s: s["start"] - s["end"])[:n_fit]]):  # longest first
        fit = fit_court(fr, min_score=min_score) if fr is not None else None
        if fit is not None:
            first.append(fit)
    for fit in sorted(first, key=lambda f: -f.score):
        remember(fit)

    samples = {}                     # (shot, t) → {"H", "score", "pitch", "thumb", "searched", "n_known", "tried"}
    times = {i: [] for i in range(len(main))}
    last_search = {}
    cnt = {"known": 0, "search": 0, "filled": 0}

    def same(a, b):
        return (a is None) == (b is None) and (a is None or _same_court(a, b))

    def neighbours(i_s, t):
        """Times of the evaluated samples just before and just after t in the same shot."""
        ts = times[i_s]
        k = bisect_left(ts, t)
        nxt = k + 1 if k < len(ts) and ts[k] == t else k
        return [ts[j] for j in (k - 1, nxt) if 0 <= j < len(ts)]

    def evaluate(items, may_search):
        for (i_s, t), fr in _prefetch(lambda x: grab(x[1]), items):
            if fr is None:
                continue
            masks, th = LineMasks(fr), _thumb(fr)
            fit, searched = match_known(fr, known, min_score, masks), False
            if fit is not None:
                cnt["known"] += 1
            elif may_search and t - last_search.get(i_s, -np.inf) >= every_s - 1e-6:
                searched, last_search[i_s] = True, t
                cnt["search"] += 1
                fit = fit_court(fr, min_score=min_score, masks=masks)
                if fit is not None:
                    remember(fit)
            tried = set()
            if fit is None:          # the camera has not moved since a neighbour with the court
                for tn in neighbours(i_s, t):
                    nb = samples[(i_s, tn)]
                    if nb["H"] is None or not _same_view(th, nb["thumb"]):
                        continue
                    tried.add(tn)
                    s = max(float(score_many(nb["H"][None], masks[m][1], masks[m][2])[0]) for m in range(len(masks)))
                    if s >= fill_score and (fit is None or s > fit.score):
                        fit = CourtFit(nb["H"].copy(), s)
                if fit is not None:
                    cnt["filled"] += 1
            samples[(i_s, t)] = {"H": None if fit is None else np.asarray(fit.H, float), "score": 0.0 if fit is None else fit.score,
                                 "pitch": None if fit is None else round(camera_pitch_deg(fit, fr.shape), 1),
                                 "thumb": th, "searched": searched, "n_known": len(known), "tried": tried}
            k = bisect_left(times[i_s], t)
            if k == len(times[i_s]) or times[i_s][k] != t:
                insort(times[i_s], t)

    # 1) every step_s seconds of every main-camera shot
    grid = []
    for i_s, s in enumerate(main):
        n = max(1, int(np.ceil((s["end"] - s["start"]) / fps / step_s - 1e-9)))
        edges = np.linspace(s["start"], s["end"], n + 1) / fps
        grid += [(i_s, float((a + b) / 2)) for a, b in zip(edges[:-1], edges[1:])]
    for k in range(0, len(grid), 64):
        evaluate(grid[k:k + 64], True)
        ctx.progress(min(len(grid), k + 64), len(grid), "fotogramas")
    # 2) a second look at frames without court: a preset found later in the match, or a neighbour
    # with the court in the same view that was evaluated after them
    again = []
    for (i_s, t), d in samples.items():
        if d["H"] is not None:
            continue
        later_preset = not d["searched"] and d["n_known"] < len(known)
        if later_preset or any(samples[(i_s, tn)]["H"] is not None and tn not in d["tried"]
                               and _same_view(d["thumb"], samples[(i_s, tn)]["thumb"]) for tn in neighbours(i_s, t)):
            again.append((i_s, t))
    evaluate(sorted(again), False)
    # 3) where neighbouring frames disagree, the change is located by bisection
    for _ in range(8):
        new = []
        for i_s, ts in times.items():
            for t0, t1 in zip(ts[:-1], ts[1:]):
                if t1 - t0 > refine_s + 1e-6 and not same(samples[(i_s, t0)]["H"], samples[(i_s, t1)]["H"]):
                    new.append((i_s, (t0 + t1) / 2))
        if not new:
            break
        evaluate(new, False)

    # every frame of a shot takes its nearest sample; same court in a row → one segment
    out = []
    for i_s, s in enumerate(main):
        ts = times[i_s]
        if not ts:
            continue
        cuts = [s["start"]] + [int(np.clip(round((a + b) / 2 * fps), s["start"], s["end"])) for a, b in zip(ts[:-1], ts[1:])] + [s["end"]]
        for t, a, b in zip(ts, cuts[:-1], cuts[1:]):
            if b <= a:
                continue
            d = samples[(i_s, t)]
            seg = {"start": a, "end": b, "score": round(d["score"], 3),
                   "H": None if d["H"] is None else d["H"].tolist(), "pitch_deg": d["pitch"]}
            if out and out[-1]["end"] == seg["start"] and out[-1]["H"] == seg["H"]:
                out[-1]["end"] = seg["end"]           # same court: one segment
            else:
                out.append(seg)
    _write(ctx.path("court.json"), {"fps": fps, "shots": out})
    ok = [o for o in out if o["H"] is not None]
    main_f = sum(s["end"] - s["start"] for s in main)
    court_f = sum(o["end"] - o["start"] for o in ok)
    return {"segments": len(out), "with_court": len(ok), "known_court_reused": cnt["known"], "searched": cnt["search"],
            "filled_same_view": cnt["filled"], "samples": len(samples), "court_presets": len(known),
            "main_camera_min": round(main_f / fps / 60, 1), "court_min": round(court_f / fps / 60, 1),
            "court_share": round(court_f / max(main_f, 1), 3),
            "pitch_deg_median": float(np.median([o["pitch_deg"] for o in ok])) if ok else None}


def _surname(name: str) -> str:
    return name.strip().split()[-1] if name and name.strip() else ""


@stage("score", "6", deps=("scenes", "court"), settings=lambda c: {"every_s": (c.get("score") or {}).get("every_s", 5.0)},
       outputs=("score.json",), match_fields=lambda m: {"player": m.player.name, "opponent": m.opponent}, resource="cpu")
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
    # OCR of the scoreboard region is repeated at least every 30 s even when its pixels look unchanged
    reader = ScoreReader(*names, max_reuse=max(0, int(30.0 / every + 1e-9) - 1))
    out, shots, samples, by_shot = [], [], [], {}
    # only match play is sampled (main camera with the court found, as the players stage): in the rest
    # of the "main camera" (close-ups, crowd, graphics) there is often no scoreboard, and every miss
    # there is an OCR of the whole frame (~2.5 s): it was two thirds of the stage for nothing
    play_m = play_mask(sc, court or None)
    for i_s, s in enumerate(sc["shots"]):
        if not s["main_camera"]:
            continue
        t = s["start"] / fps + 0.5
        while t < s["end"] / fps:
            if int(t * fps) < len(play_m) and play_m[int(t * fps)]:
                samples.append((i_s, t))
            t += every
        by_shot[i_s] = len(shots)
        shots.append({"start": s["start"] / fps, "end": s["end"] / fps, "tried": 0, "read": 0})
    # the same frames as one grab_frame per sample (first frame at or after each time), raw (no PNG
    # in between), fetched ahead in the background while the OCR runs; samples closer than 1.5 s
    # (every_s < 1.5) are decoded sequentially by one ffmpeg process instead of a seek each
    stream = frames_at(probe(ctx.video), [t for _, t in samples]) if samples else iter(())
    for n, ((i_s, t), (_, fr)) in enumerate(zip(samples, stream)):
        ctx.progress(n + 1, len(samples), f"muestras · {len(out)} lecturas · {reader.ocr_calls} OCR")
        st = reader.read(fr) if fr is not None else None
        # in live play the scoreboard is on screen; a main-camera-looking shot without it is
        # usually a replay (used later to drop duplicated strokes)
        sh = shots[by_shot[i_s]]
        sh["tried"] += 1
        if st is not None:
            sh["read"] += 1
            out.append({"t": round(t, 2), **st.to_dict()})
    _write(ctx.path("score.json"), {"readings": out, "names": names, "opponent": opponent, "shots": shots})
    if not out:
        ctx.log(f"  AVISO: no se pudo leer el marcador con «{names[0]}» y «{names[1]}»: sin marcador no se sabe "
                f"quién está en cada lado; compruebe que el partido es de {ctx.match.player.name}")
    ctx.log(f"  marcador: {len(samples)} muestras en juego, {reader.ocr_calls} OCR ({len(out)} lecturas)")
    return {"readings": len(out), "pressure": sum(r["pressure"] for r in out), "samples": len(samples), "ocr_calls": reader.ocr_calls}


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
    from .court import LineMasks, camera_pitch_deg, fit_court, score_homography

    fr = grab_frame(clip, t)
    if fr is None:
        return H, pitch, None
    masks = LineMasks(fr)                 # computed once, shared with the refit
    if H is not None and score_homography(H, *masks[0]) >= min_score:
        return H, pitch, "ok"
    own = fit_court(fr, masks=masks)
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
                       "hand3d": model_state(rf.get("hand3d_onnx")), "pose": c.get("yolo_pose", "yolo11m-pose.pt")},
            **_fp16_setting(c)}


FINE_CODE = ("stages", "clip_pipeline", "stroke_analysis", "phases", "kinematics", "impacts", "ball", "court_metrics",
             "outcome", "series", "racket", "racket3d", "racket_face", "racket_orientation", "tracking", "technique",
             "footwork", "pose.yolo", "pose.yolo_onnx", "pose.backend", "ball3d", "limits", "fine_gate", "pose.hybrid",
             "footpoints", "pose.wholebody3d", "body_scale", "fine_ahead", "situations", "returns")


def _player_fields(p) -> dict:
    return {"hand": p.hand, "height_m": p.height_m, "backhand": getattr(p, "backhand", None),
            "grip": [getattr(p, "forehand_grip_close_deg", None), getattr(p, "backhand_grip_close_deg", None)]}


@stage("fine", "16", deps=("candidates", "court", "score"), settings=_fine_settings, outputs=("strokes.json",),
       code=FINE_CODE, match_fields=lambda m: {**_player_fields(m.player), "surface": m.surface})
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


@stage("fine_opponent", "9", deps=("candidates", "court", "score"),
       settings=lambda c: {**_fine_settings(c), "enabled": c.get("analyze_opponent", False)},
       outputs=("strokes_opponent.json",), code=FINE_CODE,
       match_fields=lambda m: {**_player_fields(opponent_profile(m)), "opponent": m.opponent, "surface": m.surface})
def st_fine_opponent(ctx: Context):
    """The opponent's strokes from the same video (runs where the near player is the opponent).
    Off unless `analyze_opponent: true` in the config."""
    if not ctx.cfg.get("analyze_opponent", False):
        _write(ctx.path("strokes_opponent.json"), [])
        return {"enabled": False}
    return _fine(ctx, opponent_profile(ctx.match), lambda c: c.get("target", c.get("identity")) is False,
                 "strokes_opponent.json")


@stage("fine_doubtful", "1", deps=("candidates", "court", "score"), settings=_fine_settings,
       outputs=("strokes_doubtful.json",), code=FINE_CODE,
       match_fields=lambda m: {**_player_fields(m.player), "surface": m.surface})
def st_fine_doubtful(ctx: Context):
    """The strokes of runs whose identity is undecided (19-10: a stroke is never lost for not knowing whose
    it is). Analysed in full with the target's profile and kept apart, in strokes_doubtful.json: they count
    as found strokes, but stay out of her measures and comparisons until the identity is decided. Already
    in strokes.json when `include_undecided: true` (then nothing here)."""
    if ctx.cfg.get("include_undecided", False):
        _write(ctx.path("strokes_doubtful.json"), [])
        return {"enabled": False}
    return _fine(ctx, ctx.match.player, lambda c: c.get("target", c.get("identity")) is None, "strokes_doubtful.json")


def window_cache_key(cfg: dict) -> str:
    """Key of the caches of the pose, ball and racket of each window (`ph`): the models and settings that
    made them. The hybrid pose adds its tag (pose.hybrid.pose_cache_tag): a YOLO-only cache has no feet
    and is not reused for it; with YOLO the key is the one it always was."""
    from .pose.hybrid import pose_cache_tag

    bcfg = cfg.get("ball") or {}
    return hashlib.sha1(json.dumps([cfg.get("yolo_pose", "yolo11m-pose.pt"), cfg.get("fine_imgsz", 960),
                                    model_state(bcfg.get("onnx")), "v2"]
                                   + (["fp16"] if _fp16_setting(cfg) else [])
                                   + pose_cache_tag(cfg)).encode()).hexdigest()[:8]


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
        # on the iGPU the ball model runs with a fixed batch (ball.static_batch): DirectML compiles it once
        ball = BallTracker(str(bpath), ctx.cfg.get("device", "cpu"), bcfg.get("threshold", 0.5),
                           static_batch=bool(bcfg.get("static_batch", True)) and ctx.cfg.get("device", "cpu") == "dml")
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
    ph = window_cache_key(ctx.cfg)
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
    _COUNTS.clear()
    _GATE.clear()
    _GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0)
    _BALL_AHEAD.clear()
    # seconds of video in more than one window of the same end (a rally longer than a window's 10 s is
    # cut in two): their frames are posed and tracked twice (docs/pruebas_velocidad.md)
    _COUNTS["overlap_s"] = round(window_overlap_s([_window_of(g, pre, post)[:2] + (g[0].get("side", "near"),)
                                                   for g in groups]), 1)
    # the ball of the windows from the last one backwards on the CPU while the pose runs on the iGPU
    from .fine_ahead import BallAhead, ahead_enabled
    ahead = None
    if ahead_enabled(ctx.cfg, len(groups), ball is not None):
        ahead = BallAhead(len(groups), _ahead_job(ctx, groups, pre, post, interlaced, ph, bpath),
                          gap=int((ctx.cfg.get("fine_speed") or {}).get("ball_ahead_gap", 1))).start()
    try:
        for i, g in enumerate(groups):
            if ahead is not None:
                ahead.claim(i)
            try:
                strokes += _fine_one(ctx, p, g, pre, post, interlaced, ph, court, score, onsets, scenes, ball, rpose,
                                     wb3d, fcfg)
            except Exception as e:                    # one bad window never stops the match
                for c in g:
                    errors.append({"t": c["t"], "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]})
            done += len(g)
            ctx.progress(done, len(kept), f"golpes candidatos · {len(strokes)} confirmados · "
                                          f"{_GATE['gated']} ventanas descartadas sin pose")
    finally:
        if ahead is not None:
            ahead.close()
            # at the same time as the rest (not part of the wall time): the worker's ball, and the main
            # thread's waits for it
            _TIMES["bola_en_paralelo_cpu"] = sum(_BALL_AHEAD.values())
            _TIMES["espera_bola_en_paralelo"] = ahead.waited
            _COUNTS["windows_ball_ahead"] = len(ahead.done)
            if ahead.errors:
                warnings.append(f"bola en paralelo: falló en {len(ahead.errors)} ventanas (hechas en la iGPU): "
                                + next(iter(ahead.errors.values()))[:200])
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
            # the cascade: windows the ball alone ruled out (no pose run) and windows analysed in full
            "gate": {"windows_gated": _GATE["gated"], "windows_passed": _GATE["passed"], "windows_ungated": _GATE["off"],
                     "reasons": dict(_GATE["reasons"]), "seconds_in_gated_windows": round(_GATE["seconds_gated"], 1)},
            # where the time goes (seconds; only what was computed now, not read from the caches)
            "seconds": {k: round(v, 1) for k, v in sorted(_TIMES.items(), key=lambda kv: -kv[1])},
            # how much of it: frames of the analysed windows and those posed (pose_ranges), impacts found and
            # those that can become a stroke (the racket only around these), frames segmented for the racket
            "counts": dict(_COUNTS)}


_TIMES: dict = {}
_GATE: dict = {}
_COUNTS: dict = {}       # frames posed / in the windows, impacts and racket frames of the fine pass
_BALL_AHEAD: dict = {}   # window id → seconds of its ball computed in the background (fine_ahead)


def window_overlap_s(windows) -> float:
    """Seconds of video covered by more than one window of the same end: [(t0, dur, side)]."""
    total = 0.0
    for side in {w[2] for w in windows}:
        end = None
        for a, b in sorted((a, a + d) for a, d, s in windows if s == side):
            if end is not None and a < end:
                total += min(b, end) - a
            end = b if end is None else max(end, b)
    return total


def _cut_args(ctx: Context) -> dict:
    """How the windows of this match are cut (cut_window's arguments besides the times)."""
    pr = _read(ctx.path("probe.json")) if ctx.path("probe.json").exists() else {}
    track = _read(ctx.path("audio_track.json"))["track"] if ctx.path("audio_track.json").exists() else 0
    return {"audio_track": track, "width": pr.get("width", 0), "cfr_fps": pr.get("fps") if pr.get("vfr") else None}


def _ahead_job(ctx: Context, groups: list, pre: float, post: float, interlaced: bool, ph: str, bpath):
    """job(i) of fine_ahead.BallAhead: cut window i and cache its ball track, with the ball model on the
    CPU (its own session, `fine_speed.ball_ahead_threads` threads), exactly where the fine pass reads it."""
    from .ball import BallTracker
    from .clip_pipeline import window_ball

    fs = ctx.cfg.get("fine_speed") or {}
    bcfg = ctx.cfg.get("ball") or {}
    args = _cut_args(ctx)
    model: list = []

    def job(i: int):
        if not model:                        # created in the worker thread, the first time it is needed
            # batch 1: on the CPU a batch is not faster, and a batch of 8 holds ≈ 3 GB (1: ≈ 0.5 GB)
            model.append(BallTracker(str(bpath), "cpu", bcfg.get("threshold", 0.5),
                                     batch=max(1, int(fs.get("ball_ahead_batch", 1) or 1)),
                                     threads=int(fs.get("ball_ahead_threads", 4) or 0) or None))
        t0, dur, wid = _window_of(groups[i], pre, post)
        clip = cut_window(ctx.video, t0, dur, ctx.path("windows") / f"{wid}.mp4", interlaced, **args)
        took = window_ball(clip, clip.with_name(f"{clip.stem}_{ph}.npz"), model[0])[1]
        if took:
            _BALL_AHEAD[wid] = took
    return job


def _took(key: str, t0: float):
    import time
    _TIMES[key] = _TIMES.get(key, 0.0) + time.time() - t0


def _rally_position(strokes: list[dict], cands: list[dict], scenes: dict) -> None:
    """Her shot number within the point and her shots in the whole point, counted from the hits of
    the cheap pass on her side of the same main-camera shot. Only when the shot starts at least
    1.5 s before its first hit (the point is seen from its start). The point's moment class
    (return / start of the point / rally) is refined with it, and the return's variants (returns.py)."""
    from . import returns as _returns
    sfps = scenes.get("fps") or 1
    for d in strokes:
        t, side = d["match_time_s"], d.get("side", "near")
        sh = next((x for x in scenes.get("shots", []) if x["main_camera"] and x["start"] / sfps <= t < x["end"] / sfps), None)
        if sh is None:
            _returns.apply(d, None, None, cands)
            continue
        a, b = sh["start"] / sfps, sh["end"] / sfps
        hits = sorted(c["t"] for c in cands if c.get("side", "near") == side and a <= c["t"] < b)
        if not hits or hits[0] - a < 1.5:
            _returns.apply(d, None, (a, b), cands)
            continue
        k = sum(h <= t + 0.3 for h in hits)
        d["shot_in_point"], d["shots_in_point"] = k, len(hits)
        cl = (d.get("technique") or {}).get("classes")
        if cl is not None and not d.get("is_return"):
            cl["play"] = "inicio del punto" if k <= 2 else "peloteo"
        # the return of serve and its variants (scoreboard server + her first hit of the point)
        _returns.apply(d, k, (a, b), cands)


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
    from .pose.backend import set_device, uses_fp16

    set_device(ctx.cfg.get("device", "cpu"), uses_fp16(ctx.cfg))

    c = group[0]
    t0, dur, wid = _window_of(group, pre, post)
    args = _cut_args(ctx)
    import time
    t_ = time.time()
    clip = cut_window(ctx.video, t0, dur, ctx.path("windows") / f"{wid}.mp4", interlaced, **args)
    _took("recorte", t_)
    ws = window_scale(args["width"])
    side = c.get("side", "near")
    extra, cache = {}, clip.with_name(f"{clip.stem}_{ph}.npz")
    cut_s = time.time() - t_
    fp = ctx.cfg.get("fine_pass") or {}
    H_far = None
    if side == "far":
        t_ = time.time()
        H_far = court_at(court, c["t"], ws)[0]
        fi = far_start(clip, H_far)
        _took("jugadora_lejana", t_)
        if fi is None:
            return []                         # no court or no far player found: nothing reliable
        extra, cache = dict(side="far", **fi), clip.with_name(f"{clip.stem}_{ph}_far.npz")
    # cascade: the ball alone rules out windows without a possible stroke before any pose is run
    dec = _gate_passes(ctx, group, t0, wid, clip, cache, side, ball, cut_s)
    if not dec:
        return []
    # the pose only where a possible stroke can use it (fine_pass.pose_ranges): frames around the
    # impacts the gate still allows, each stretch tracked on its own as a window of its own
    keep = _pose_keep(ctx, dec, side)
    fill = int(fp.get("pose_fill_every", 5) or 0) > 1
    if keep is not None and fill:
        extra = {**extra, "split": False}     # followed through the whole window, as before
    if keep is not None and side == "far" and not fill:
        from .clip_pipeline import keep_runs
        from .pose.yolo import find_far_players
        t_ = time.time()
        inits = find_far_players(clip, H_far, [a for a, _ in keep_runs(keep)])
        _took("jugadora_lejana", t_)
        if any(v is None for v in inits.values()):
            keep = None                      # not found at the start of a stretch: the whole window, as before
        else:
            extra = {**extra, "inits": inits}
    # the racket outline only where a stroke of these candidates can be (fine_pass.racket_near_candidates)
    targets = [x["t"] - t0 for x in group] if fp.get("racket_near_candidates", True) else None
    if keep is not None and side == "near" and not fill:     # each stretch starts from the person the ball leaves
        extra = {**extra, "anchors": [(p_[0], p_[3], p_[4]) for p_ in dec.get("possible", []) if len(p_) >= 5]}
    from .fine_gate import CONFIRM_TOL_S
    from .pose.hybrid import fine_pose_model
    # her height in px (the scale of every measure in % of height or in cm) from the court and her
    # real height (body_scale): the court of the shot, checked on the window's first candidate frame
    hmode = fp.get("height_scale", "court")
    H_win = None
    if hmode == "court" and court:
        t_ = time.time()
        H_win = H_far if side == "far" else court_at(court, c["t"], ws)[0]
        if H_win is not None:
            H_win = _check_court(clip, c["t"] - t0, H_win, None)[0]
        _took("pista_ventana", t_)
    t_ = time.time()
    run = run_clip(clip, cache, p.hand, p.height_m, init_mode="near", rackets=side == "near",
                   imgsz=ctx.cfg.get("fine_imgsz", 960), log=lambda *_: None, ball=ball,
                   prefetch=fp.get("pose_prefetch", True), targets=targets,
                   target_tol=CONFIRM_TOL_S, keep=keep, pose_model=fine_pose_model(ctx.cfg),
                   court_H=H_win, height_scale=hmode, **extra)
    for k, v in run.timing.items():
        _TIMES[k] = _TIMES.get(k, 0.0) + v
    _took("analisis_ventana", t_ + sum(run.timing.values()))         # the rest of run_clip
    st = getattr(run, "stats", None) or {}
    for k in ("frames", "posed_frames", "impacts", "kept_impacts", "racket_frames", "whole_window_again"):
        _COUNTS[k] = _COUNTS.get(k, 0) + int(st.get(k) or 0)
    _COUNTS["frames_960_far"] = _COUNTS.get("frames_960_far", 0) + int(st.get("frames_960") or 0)
    pm = st.get("pose_model", "yolo")
    if st.get("model_s"):        # seconds inside the pose model (part of "pose"), per model: yolo / hybrid
        _TIMES[f"pose_modelo_{pm}"] = _TIMES.get(f"pose_modelo_{pm}", 0.0) + float(st["model_s"])
        _COUNTS[f"frames_modelo_{pm}"] = _COUNTS.get(f"frames_modelo_{pm}", 0) + int(st.get("frames_model") or 0)
    ctx.log(f"  ventana {wid}: pose {pm} en {st.get('posed_frames', '?')} de {st.get('frames', '?')} fotogramas"
            f" ({run.timing.get('pose', 0):.0f} s; modelo {st.get('model_s', 0):.0f} s"
            + (f"; pies en {st['feet_frames']}" if pm == "hybrid" and "feet_frames" in st else "")
            + (f", {st['frames_960']} a 960 px por perderla" if st.get("frames_960") else "")
            + f") · bola {_ball_said(dec, wid)} · raqueta {run.timing.get('raqueta', 0):.0f} s"
            f" ({st.get('kept_impacts', 0)} de {st.get('impacts', 0)} impactos) · {len(run.strokes)} golpes posibles"
            + (f" · altura {run.height_px:.0f} px ({st['height_scale']})" if st.get("height_scale") else ""))
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


def _ball_said(dec: dict, wid: str) -> str:
    """The ball's time in a window's log line: computed now on the iGPU, or ahead on the CPU."""
    if not dec.get("ball_s") and wid in _BALL_AHEAD:
        return f"{_BALL_AHEAD[wid]:.0f} s en paralelo (CPU)"
    return f"{dec.get('ball_s', 0):.0f} s"


def _pose_keep(ctx, dec: dict, side: str):
    """Frames to run the pose on (fine_gate.pose_keep) when fine_pass.pose_ranges is on for this end
    (true: both, "far": the far end only) and the gate says where the possible impacts are; None:
    the whole window."""
    fp = ctx.cfg.get("fine_pass") or {}
    on = fp.get("pose_ranges", False)
    if not (on is True or on == side) or not dec.get("possible") or not dec.get("n_frames"):
        return None
    from .fine_gate import pose_keep
    return pose_keep(dec["n_frames"], dec["possible"], dec["fps"], fp.get("pose_pre_s", 2.8), fp.get("pose_post_s", 2.0),
                     fp.get("pose_join_s", 1.0), fp.get("pose_full_frac", 0.85), int(fp.get("pose_fill_every", 5) or 0))


def _gate_passes(ctx, group, t0, wid, clip, cache, side, ball, cut_s: float) -> dict:
    """Stage A of the cascade (fine_gate): the ball track of the window alone (cached for the full
    pass) says whether it can hold a confirmed stroke of the target; if not, no pose is run.
    Without the ball model, or with `fine_pass.gate: false`, every window passes.
    Returns the gate's decision when it passes (with "possible", "fps", "n_frames", "ball_s"), or {}
    when the window is ruled out."""
    import time
    fp = ctx.cfg.get("fine_pass") or {}
    if ball is None or not fp.get("gate", True):
        _GATE["off"] = _GATE.get("off", 0) + 1
        return {"passed": True, "reason": "sin_cribado"}
    from .clip_pipeline import window_ball
    from .fine_gate import CONFIRM_TOL_S, gate_window

    t_ = time.time()
    track, took, fw, fh, fps = window_ball(clip, cache, ball)
    if took:
        _TIMES["bola"] = _TIMES.get("bola", 0.0) + took
    dec = gate_window(track, fw, fh, fps, [(c["t"] - t0) * fps for c in group], side, fp.get("gate_margin_s", 0.1))
    dec.update(fps=fps, n_frames=len(track) if track is not None else 0, ball_s=took)
    _took("cribado", t_ + took)
    _GATE["reasons"][dec["reason"]] = _GATE["reasons"].get(dec["reason"], 0) + 1
    what = {"golpe_de_bola": f"golpe de bola en su lado a {dec.get('hit_s')} s",
            "bola_no_vista": f"bola no vista cerca de un candidato ({dec.get('at_s')} s): puede haber golpe",
            "sin_datos_de_bola": "sin datos de bola",
            "sin_golpe": f"ningún golpe de bola en su lado a ±{CONFIRM_TOL_S} s de los candidatos"
                         + (" y la bola bien vista ahí" if side == "near" else "")}[dec["reason"]]
    if dec["passed"]:
        _GATE["passed"] += 1
        ctx.log(f"  ventana {wid} ({side}, {len(group)} candidatos): pasa · {what}")
        return dec
    _GATE["gated"] += 1
    _GATE["seconds_gated"] += cut_s + time.time() - t_
    ctx.log(f"  ventana {wid} ({side}, {len(group)} candidatos): descartada sin pose · {what}")
    return {}


def _fine_stroke(ctx, p, c, t0, wid, clip, side, run, used, court, score, onsets, scenes, rpose, wb3d, fcfg):
    """One confirmed stroke of an analysed window, or None."""
    target = (c["t"] - t0) * run.fps
    free = [s for s in run.strokes if s.impact_frame not in used]
    if not free:
        return None
    r = min(free, key=lambda s: abs(s.impact_frame - target))
    from .fine_gate import CONFIRM_TOL_S
    if abs(r.impact_frame - target) > CONFIRM_TOL_S * run.fps:
        return None                           # the fine pass did not confirm this candidate
    used.add(r.impact_frame)
    from .limits import sanitize
    r.review += [f"impossible:{k}" for k in sanitize(r.metrics)]      # measurement errors, never shown
    d = r.to_dict()
    t_imp = t0 + r.impact_frame / run.fps
    d.update(window=str(clip.name), window_start_s=t0, match_time_s=t_imp, candidate_audio=c.get("audio"),
             identity=c.get("identity"), target=c.get("target"), stroke_id=f"{ctx.match.id}-{int(round(t_imp * 100)):07d}")
    if ctx.match.surface:                     # the court of the match (catalogue, tournament or file name)
        d["surface"] = ctx.match.surface
    sr = score_at(score, t_imp)
    if sr is not None:
        d["score"] = {k: sr.get(k) for k in ("games", "points", "banner", "set", "sets_won", "tiebreak", "pressure", "server")}
    pr = _read(ctx.path("probe.json")) if ctx.path("probe.json").exists() else {}
    H, pitch = court_at(court, t_imp, window_scale(pr.get("width", 0)))
    H, pitch, d["court_check"] = _check_court(clip, r.impact_frame / run.fps, H, pitch)
    d["side"] = side
    # how her height in px was estimated (body_scale): court | segments | pose, and its checks
    if getattr(run, "height_source", None):
        d["height_scale"] = {"source": run.height_source, "px": round(float(run.height_px), 1),
                             **(getattr(run, "height_info", None) or {})}
    H_img = H
    if H is not None:
        from .court_metrics import player_frame_H
        H = player_frame_H(H, side)            # her own court frame at either end
    if H is not None:
        from .court_metrics import court_metrics
        ta = r.metrics.get("time_available_s")
        opp = None if ta is None else r.impact_frame - int(round(ta * run.fps))
        cm = court_metrics(run.img, run.sk, H, r.stroke, r.impact_frame, opp,
                           feet=getattr(run, "feet", None), feet_conf=getattr(run, "feet_conf", None))
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
    from .footpoints import series_feet
    ser.update(series_feet(getattr(run, "feet", None), getattr(run, "feet_conf", None), ser["first"], ser["n"]))
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
        # the court direction of her shot (contact → bounce), for the face at contact
        sdir = None
        if d.get("shot_bounce_m") and d.get("court_pos_m"):
            dx, dy = d["shot_bounce_m"][0] - d["court_pos_m"][0], d["shot_bounce_m"][1] - d["court_pos_m"][1]
            if dy > 3:
                sdir = [dx, dy, 0.15 * float(np.hypot(dx, dy))]
        faces = stroke_faces(clip, run, r, p.height_m, pitch if H_img is not None else None, rpose, wb3d,
                             step3d, grip, shot_dir=sdir)
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
    def tech(frames):
        return stroke_technique(
            run.img, run.conf, run.sk, run.fps, run.height_t if run.height_t is not None else np.full(len(run.img), run.height_px),
            r.impact_frame, frames, r.stroke, H if side == "near" else None, opp_f, (r.ball or {}).get("bounce_frame"),
            ser.get("face"), None,
            {"court_pos": d.get("court_pos_m"), "displacement": d.get("displacement_m"), "t_avail": ta,
             "contact_h": r.metrics.get("contact_height_pct"), "shot_direction": d.get("shot_direction"),
             "split": (r.phases.get("ready") or {}).get("method") == "split_step_landing",
             "surface": ctx.match.surface or "", "next_opp": ret, "return": is_return, "ball": ball_m,
             "head_motion_cm": r.metrics.get("head_motion_impact_cm"),
             "bounce_to_impact": r.metrics.get("bounce_to_impact_s"), "ball_hit": "ball" in (r.impact_source or ""),
             "ball_gap_pre": r.metrics.get("ball_gap_pre_s"), "ball_seen_pre": r.metrics.get("ball_seen_pre_share"),
             "height_m": p.height_m},
            feet=getattr(run, "feet", None), feet_conf=getattr(run, "feet_conf", None))
    d["technique"] = tech(ph_frames)
    if side == "near":
        # repeatability of the whole stroke: its phase instants are known to ±1-2 frames, so the stroke
        # is described again with them all moved; timings, steps and classes that change with that are
        # noise (reliability.py). Kept next to the per-phase ones that technique computes itself.
        from .reliability import merge_jitter, shifted_jitter
        T = len(run.img)
        shifted = [tech({k: (None if v is None else min(T - 1, max(0, v + s))) for k, v in ph_frames.items()})
                   for s in (-2, -1, 1, 2)]
        merge_jitter(d["technique"], shifted_jitter(d["technique"], shifted))
    if side == "far":                       # 70 px player: only position-level classes are kept
        d["technique"] = {"classes": {k: v for k, v in d["technique"]["classes"].items()
                                      if k in ("ball_speed", "ball_height", "depth", "court_side", "width", "intent", "shot_type",
                                               "contact_type")},
                          "phases": {}, "stroke": {}, "footwork": {}}
    # the situations the user named (angled shot, short ball near the net): from position, bounce and height,
    # which the far side also has (situations.py)
    from .situations import apply as _situations
    _situations(d)
    sdir = ctx.path("series")
    sdir.mkdir(exist_ok=True)
    sname = f"{wid}_{side}_{r.impact_frame}.json"
    _write(sdir / sname, ser)
    d.update(series=f"series/{sname}", window_impact_s=r.impact_frame / run.fps)
    return d
