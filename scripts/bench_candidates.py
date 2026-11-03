"""Paso 2 de la Base (docs/plan_maestro.md, "Plan a corto plazo (02-11)"): each candidate model of the reference
project (tennisbio.candidates), measured on this PC against the model it would replace, on annotated data, in
accuracy and in speed on the configured device (the iGPU, `dml`).

    candidate  ours                                annotated data (downloaded on first use, then cached)
    wasb       TrackNetV3 (ball.onnx, fp16 on iGPU) RacketVision test clips: annotated ball positions
    rtmw       YOLO11m-pose + RTMPose-x (hybrid)    RacketVision test clips: strokes from the annotated ball turns
    court14    tennisbio.court.fit_court (lines)    TennisCourtDetector's val split: 14 annotated points per frame
    rfdetr     YOLO11m-pose on the far half         RacketVision test frames: the far player's annotated racket
    f3ed       our learned spotter (spotting.json)  F3Set compilations of scripts/validate_recall.py (YouTube)
    ocr5       rapidocr-onnxruntime 1.4 (PP-OCRv4)  no annotated scoreboards: the frames our `score` stage read in the
               (score stage)                        analysed matches; agreement and consistency, NOT accuracy (#201)
    mag3d      RTMW3D (trunk turn in 3D)            CalTennis: two calibrated synchronised views of the same player;
                                                    the shoulder/hip line triangulated from both (#203, #206)
    bounce     the bounce rule (sharpest ball turn  TrackNet dataset: every frame's ball and status (2 = bounce);
               between two hits, tennisbio.ball)    on its annotated ball and on our ball tracker's (#199)

Rule to adopt a candidate, written in the output for each one: accuracy equal or better AND not slower for the
whole pass of a new match (the same work, on this PC). A candidate that wins only one of the two is not adopted;
nothing here changes the pipeline: adopting one is a change of its own.

The missing ONNX files are made first with their export scripts (scripts/export_*.py; RF-DETR with
`uv run --with rfdetr==1.11.2`, the bounce model with `--with catboost==1.2.10`). PP-OCRv5 runs in its own
environment (`uv run --with rapidocr==3.10.0`, scripts/bench_ocr.py). Every candidate's result is saved as soon as it
is measured; a later run measures only what is missing (--force to repeat). With no arguments (a "medir" request of
the PC: script bench_candidates) it measures everything with the configured device and datasets next to the output
folder. One candidate alone:

    uv run python scripts/bench_candidates.py --only ocr5      (also mag3d, bounce; or several: --only mag3d,bounce)
    uv run python scripts/bench_candidates.py [--only wasb,court14] [--device dml] [--root C:\\tenis\\datasets]

Writes <root>/reports/bench_candidates.json and .md, and copies both to <output>/.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

VERSION = 1
CANDIDATES = ("wasb", "rtmw", "court14", "rfdetr", "f3ed", "ocr5", "mag3d", "bounce")
MODELS = ROOT / "models"
# candidate → (ONNX file, export script and its arguments, packages the export needs on top of the project's)
EXPORTS = {
    "wasb": (MODELS / "wasb_tennis.onnx", ["export_wasb.py"], ()),
    "rtmw": (MODELS / "rtmw-x_384x288.onnx", ["export_rtmw.py"], ()),
    "court14": (MODELS / "court_tcd.onnx", ["export_court_tcd.py"], ()),
    "rfdetr": (MODELS / "rfdetr_medium_1152.onnx", ["export_rfdetr.py"], ("rfdetr==1.11.2",)),
    "f3ed": (MODELS / "f3ed.onnx", ["export_f3ed.py"], ()),
    "ocr5": (MODELS / "ppocrv5" / "ch_PP-OCRv5_rec_mobile.onnx", ["export_ppocrv5.py"], ()),
    "mag3d": (MODELS / "motionagformer_xs.onnx", ["export_motionagformer.py", "--size", "xs"], ()),
    "mag3d-s": (MODELS / "motionagformer_s.onnx", ["export_motionagformer.py", "--size", "s"], ()),
    "bounce": (MODELS / "bounce_ctb.onnx", ["export_bounce_ctb.py"], ("catboost==1.2.10",)),
}
EXPORT_TIMEOUT_S = 3600
TCD_DATASET = "https://drive.usercontent.google.com/download?id=1lhAaeQCmk2y440PmagA0KmIVBIysVMwu&export=download&confirm=t"
BALL_TOL_PX = 10          # as scripts/model_trials.py
COURT_TOL_PX = 7          # TennisCourtDetector's own measure (1280x720 frames)
SPOT_TOL_S = 0.2          # as scripts/validate_recall.py
MIN_STROKES = 5           # fewer annotated strokes than this: no verdict on stroke accuracy (as model_trials.py)


# ---------------------------------------------------------------- rule and report

def verdict(acc_c, acc_b, speed_c, speed_b, acc_name: str, speed_name: str, higher_is_faster: bool = True) -> dict:
    """The adoption rule: accuracy ≥ ours and not slower. speed: frames/s (higher_is_faster) or minutes."""
    if None in (acc_c, acc_b, speed_c, speed_b):
        return {"adopt": False, "insufficient": True,
                "reason": "sin medida completa (falta la precisión o la velocidad de alguno)"}
    acc_ok = acc_c >= acc_b
    fast_ok = speed_c >= speed_b if higher_is_faster else speed_c <= speed_b
    why = (f"{acc_name} {acc_c} frente a {acc_b} ({'igual o mejor' if acc_ok else 'peor'}); "
           f"{speed_name} {speed_c} frente a {speed_b} ({'no más lento' if fast_ok else 'más lento'})")
    return {"adopt": bool(acc_ok and fast_ok), "reason": why}


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    rd = lambda x: None if x is None else round(x, 3)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": rd(p), "recall": rd(r), "f1": rd(f)}


def to_markdown(rep: dict) -> str:
    lines = [f"# Modelos candidatos frente a los actuales ({rep['generated']}, {rep['device']})", "",
             "Regla: se adopta si su precisión es igual o mejor **y** no es más lento en la pasada completa de un partido "
             "nuevo. Nada de esto cambia el análisis: adoptar uno es un cambio aparte.", "",
             "| Candidato | Frente a | Precisión (candidato / actual) | Velocidad (candidato / actual) | ¿Se adopta? |",
             "|---|---|---|---|---|"]
    for name in CANDIDATES:
        r = rep["results"].get(name)
        if not r:
            lines.append(f"| {name} | | sin medir | | |")
            continue
        if r.get("error"):
            lines.append(f"| {name} | | error: {r['error'][:120]} | | no |")
            continue
        v = r.get("verdict") or {}
        lines.append(f"| {name} | {r.get('baseline', '')} | {r.get('accuracy', '')} | {r.get('speed', '')} | "
                     f"{'**sí**' if v.get('adopt') else 'no'}: {v.get('reason', '')} |")
    for name in CANDIDATES:
        r = rep["results"].get(name)
        if r and r.get("notes"):
            lines += ["", f"- {name}: " + " ".join(r["notes"])]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- models

def ensure_model(name: str) -> Path:
    """The candidate's ONNX file, made with its export script when missing."""
    path, script, extra = EXPORTS[name]
    if path.exists():
        return path
    cmd = ([shutil.which("uv") or "uv", "run", *[a for p in extra for a in ("--with", p)], "python"] if extra
           else [sys.executable])
    cmd += [str(ROOT / "scripts" / script[0]), *script[1:], "--out", str(path)]
    print(f"  exportando {name}: {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, timeout=EXPORT_TIMEOUT_S, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print(r.stdout[-600:], flush=True)
    if r.returncode or not path.exists():
        raise RuntimeError(f"no se pudo exportar {name}: {r.stderr.strip()[-400:]}")
    return path


def read_video(path: Path, limit: int | None = None) -> tuple[list[np.ndarray], float]:
    from tennisbio.io.video import open_capture

    cap = open_capture(path)
    fps = cap.get(5) or 25.0
    frames = []
    while limit is None or len(frames) < limit:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    return frames, float(fps)


def timed(fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return out, time.perf_counter() - t0


# ---------------------------------------------------------------- ball: WASB vs TrackNetV3

def read_ball_rows(path: Path) -> list[tuple[int, int, float, float]]:
    """(frame, visible, x, y) of every annotated frame (annotations are sparse: only these frames count)."""
    with open(path, newline="") as f:
        return [(int(r["Frame"]), int(r["Visibility"]), float(r["X"]), float(r["Y"])) for r in csv.DictReader(f)]


def score_ball(track: np.ndarray, rows, tol: float = BALL_TOL_PX) -> dict:
    """Frame-level ball detection on the annotated frames: a prediction within tol px of a visible ball is right;
    a prediction elsewhere (or where the ball is not visible) is a false one; a visible ball without a right
    prediction is missed."""
    tp = fp = fn = 0
    errs = []
    for f, vis, x, y in rows:
        if f >= len(track):
            continue
        seen = bool(np.isfinite(track[f, 0]))
        d = float(np.hypot(track[f, 0] - x, track[f, 1] - y)) if seen else np.inf
        if vis and d <= tol:
            tp += 1
            errs.append(d)
        else:
            fp += seen
            fn += bool(vis)
    out = prf(tp, fp, fn)
    out["median_err_px"] = round(float(np.median(errs)), 2) if errs else None
    return out


def bench_ball(root: Path, device: str, cfg: dict, n_clips: int) -> dict:
    from tennisbio.ball import BallTracker
    from tennisbio.candidates.wasb import WasbTracker
    from tennisbio.config import resolve_path
    from tennisbio.validation.datasets import RV_BASE, fetch, racketvision_video

    ours_path = resolve_path((cfg.get("ball") or {}).get("onnx") or "models/balltrack.onnx")
    if ours_path is None or not ours_path.exists():
        raise FileNotFoundError(f"falta nuestro modelo de bola ({ours_path}): ejecuta scripts/setup_models.py")
    fp16 = bool((cfg.get("ball") or {}).get("fp16", True)) and device != "cpu"
    models = {"ours (TrackNetV3" + (", fp16)" if fp16 else ")"): BallTracker(str(ours_path), device, fp16=fp16),
              "wasb": WasbTracker(ensure_model("wasb"), device),
              "wasb-fp16": WasbTracker(ensure_model("wasb"), device, fp16=True) if device != "cpu" else None}
    models = {k: v for k, v in models.items() if v is not None}
    split = json.loads(fetch(f"{RV_BASE}/info/test.json", root / "rv" / "test.json").read_text())
    sel = split[:: max(1, len(split) // 12)][:n_clips]
    acc = {k: [0, 0, 0] for k in models}
    errs = {k: [] for k in models}
    secs = {k: 0.0 for k in models}
    nframes = 0
    for match_id, clip in sel:
        rows = read_ball_rows(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv", root / "rv" / "ball" / f"{match_id}_{clip}.csv"))
        frames, fps = read_video(racketvision_video(root, match_id, clip))
        step = max(1, int(round(fps / 30)))            # as the fine pass: the ball at 25-30 fps
        nframes += len(frames)
        for k, m in models.items():
            m.track(frames[:3 * step], step=step)      # warm-up (DirectML compiles on the first run)
            tr, dt = timed(m.track, frames, step=step)
            secs[k] += dt
            s = score_ball(tr, rows)
            acc[k] = [a + b for a, b in zip(acc[k], (s["tp"], s["fp"], s["fn"]))]
            if s["median_err_px"] is not None:
                errs[k].append(s["median_err_px"])
        print(f"  bola {match_id}_{clip}: {len(frames)} fotogramas", flush=True)
    per = {k: {**prf(*acc[k]), "median_err_px": round(float(np.median(errs[k])), 2) if errs[k] else None,
               "fps": round(nframes / secs[k], 1) if secs[k] else None} for k in models}
    base = next(iter(per))
    cand = max((k for k in per if k.startswith("wasb")), key=lambda k: ((per[k]["f1"] or 0), per[k]["fps"] or 0))
    v = verdict(per[cand]["f1"], per[base]["f1"], per[cand]["fps"], per[base]["fps"], "F1 bola a 10 px",
                "fotogramas/s")
    return {"baseline": base, "candidate": cand, "clips": len(sel), "frames": nframes, "per_model": per,
            "accuracy": f"F1 {per[cand]['f1']} / {per[base]['f1']}", "speed": f"{per[cand]['fps']} / {per[base]['fps']} fps",
            "verdict": v, "notes": ["La bola corre sobre todo el juego de un partido nuevo (detector de golpes): su "
                                    "velocidad por fotograma es la de esa parte de la pasada."]}


# ---------------------------------------------------------------- pose: RTMW-x vs YOLO + RTMPose-x

def extract_with(model, video: Path, out: Path) -> dict:
    """tennisbio.pose.variants.extract_variant with a model object (the candidate is not a registered variant)."""
    from tennisbio.io.video import open_capture
    from tennisbio.pipeline import savez_atomic
    from tennisbio.pose.yolo import _objects, appearance

    cap = open_capture(video)
    fps = cap.get(5)
    boxes, kps, confs, feats, feet, feet_c = [], [], [], [], [], []
    t_inf = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        b, k, c, fk, fc = model(frame)
        t_inf += time.perf_counter() - t0
        boxes.append(b); kps.append(k); confs.append(c); feet.append(fk); feet_c.append(fc)
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
    cap.release()
    savez_atomic(Path(out), fps=fps, n=len(boxes), boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                 feats=_objects(feats), feet=_objects(feet), feet_confs=_objects(feet_c))
    return {"frames": len(boxes), "ms_per_frame": round(1000 * t_inf / max(1, len(boxes)), 1)}


def bench_pose(root: Path, device: str, n_clips: int) -> dict:
    from model_trials import feet_seen, jerk
    from validate_rv_strokes import is_doubles

    from tennisbio.ball import BallTracker
    from tennisbio.candidates.rtmw import HybridRtmw
    from tennisbio.clip_pipeline import run_clip
    from tennisbio.pose.backend import set_device
    from tennisbio.pose.variants import extract_variant
    from tennisbio.validation.ball_hits import hits_from_ball, read_ball_csv
    from tennisbio.validation.datasets import RV_BASE, fetch, racketvision_video
    from tennisbio.validation.impact_eval import GTEvent, Pred, match, summarize

    set_device(device)
    base_name, cand_name = "hybrid-x", "candidate_hybrid-rtmw-x"
    work = root / "rv" / "trials"                  # the same caches as scripts/model_trials.py
    ball = MODELS / "balltrack.onnx"
    tracker = BallTracker(str(ball), device) if ball.exists() else None
    split = json.loads(fetch(f"{RV_BASE}/info/test.json", root / "rv" / "test.json").read_text())
    sel = split[:: max(1, len(split) // 12)][:n_clips]
    model = None
    res = {}
    for name in (base_name, cand_name):
        vdir = work / name
        vdir.mkdir(parents=True, exist_ok=True)
        pairs_all, fp_all, fn_all, ms, jk, ft = [], [], [], [], [], []
        for match_id, clip in sel:
            video = racketvision_video(root, match_id, clip)
            cache = vdir / f"{match_id}_{clip}.npz"
            msf = vdir / f"{match_id}_{clip}_ms.json"
            if not cache.exists():
                if name == base_name:
                    info = extract_variant(video, cache, base_name, device)
                else:
                    model = model or HybridRtmw(ensure_model("rtmw"), device)
                    info = extract_with(model, video, cache)
                msf.write_text(json.dumps(info["ms_per_frame"]))
            if msf.exists():
                ms.append(json.loads(msf.read_text()))
            if is_doubles(work / base_name / cache.name, video):
                continue
            gt = hits_from_ball(read_ball_csv(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv",
                                                    root / "rv" / "ball" / f"{match_id}_{clip}.csv")), 1080)["near"]
            run = run_clip(video, cache, rackets=False, init_mode="near", log=lambda *_: None, ball=tracker)
            preds = [Pred(r.impact_frame, "fh" if r.stroke == "forehand" else "bh") for r in run.strokes]
            pairs, fp, fn = match(preds, [GTEvent(g, "near", "stroke", "-", "-") for g in gt], 6)
            pairs_all += pairs; fp_all += fp; fn_all += fn
            jk.append(jerk(run)); ft.append(feet_seen(cache, run))
            print(f"  pose {name} {match_id}_{clip}", flush=True)
        s = summarize(pairs_all, fp_all, fn_all)
        num = [x for x in jk if x is not None]
        fnum = [x for x in ft if x is not None]
        res[name] = {"f1": s["f1"], "precision": s["precision"], "recall": s["recall"], "gt": s["gt"],
                     "ms_per_frame": round(float(np.median(ms)), 1) if ms else None,
                     "jerk_pct": round(float(np.median(num)), 3) if num else None,
                     "feet_seen": round(float(np.mean(fnum)), 3) if fnum else None}
    b, c = res[base_name], res[cand_name]
    fps = lambda r: round(1000 / r["ms_per_frame"], 1) if r["ms_per_frame"] else None
    v = verdict(c["f1"], b["f1"], fps(c), fps(b), "F1 golpes", "fotogramas/s")
    if (b["gt"] or 0) < MIN_STROKES:                   # as scripts/model_trials.py: too few to compare anything
        v = {"adopt": False, "insufficient": True, "reason": f"solo {b['gt']} golpes anotados en los clips medidos (hacen falta {MIN_STROKES})"}
    steady = c["jerk_pct"] is not None and b["jerk_pct"] is not None and c["jerk_pct"] <= b["jerk_pct"] * 1.05
    if v["adopt"] and not steady:
        v = {"adopt": False, "reason": v["reason"] + f"; pero tiembla más ({c['jerk_pct']} frente a {b['jerk_pct']} % de la altura)"}
    return {"baseline": "YOLO11m-pose + RTMPose-x (hybrid-x)", "candidate": "YOLO11m-pose + RTMW-x", "per_model": res,
            "accuracy": f"F1 {c['f1']} / {b['f1']}; temblor {c['jerk_pct']} / {b['jerk_pct']} %; pies {c['feet_seen']} / {b['feet_seen']}",
            "speed": f"{fps(c)} / {fps(b)} fps", "verdict": v,
            "notes": ["Sin esqueletos anotados en nuestros datos: la precisión es la de la tarea (golpes encontrados frente "
                      "a los giros de bola anotados de RacketVision), más el temblor de los puntos y los pies vistos."]}


# ---------------------------------------------------------------- court: TennisCourtDetector vs line fit

class HttpFile(io.RawIOBase):
    """A remote file read by HTTP ranges (1 MB blocks, kept): zipfile reads the TennisCourtDetector dataset's
    index and only the members asked for, not its 7.7 GB."""

    def __init__(self, url: str, block: int = 1 << 20, timeout: float = 120):
        self.url, self.block, self.pos, self.cache, self.timeout = url, block, 0, {}, timeout
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-0"}), timeout=timeout) as r:
            rng = r.headers.get("Content-Range") or ""
            if "/" not in rng:
                raise RuntimeError(f"{url} no admite lecturas por partes")
            self.size = int(rng.split("/")[1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _blk(self, i):
        if i not in self.cache:
            a = i * self.block
            b = min(self.size, a + self.block) - 1
            req = urllib.request.Request(self.url, headers={"Range": f"bytes={a}-{b}"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                self.cache[i] = r.read()
            if len(self.cache) > 64:                   # keep memory bounded
                self.cache.pop(next(iter(self.cache)))
        return self.cache[i]

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        got = bytearray()
        p = self.pos
        while len(got) < n:
            i = p // self.block
            d = self._blk(i)[p - i * self.block:][: n - len(got)]
            if not d:
                break
            got += d
            p += len(d)
        buf[:len(got)] = got
        self.pos += len(got)
        return len(got)


def tcd_val(root: Path, n: int) -> list[tuple[Path, np.ndarray]]:
    """n frames of TennisCourtDetector's val split (evenly spread) with their 14 annotated points, cached in
    <root>/tcd/val/."""
    d = root / "tcd" / "val"
    d.mkdir(parents=True, exist_ok=True)
    ann = d / "data_val.json"
    z = None
    if not ann.exists():
        z = zipfile.ZipFile(io.BufferedReader(HttpFile(TCD_DATASET), 1 << 16))
        ann.write_bytes(z.read("data/data_val.json"))
    data = json.loads(ann.read_text())
    pick = data[:: max(1, len(data) // n)][:n]
    out = []
    for e in pick:
        img = d / f"{e['id']}.png"
        if not img.exists():
            z = z or zipfile.ZipFile(io.BufferedReader(HttpFile(TCD_DATASET), 1 << 16))
            img.write_bytes(z.read(f"data/images/{e['id']}.png"))
        out.append((img, np.asarray(e["kps"], float)))
    return out


def score_court(pred: np.ndarray | None, gt: np.ndarray, shape, tol: float = COURT_TOL_PX) -> tuple[int, int, list]:
    """(points within tol, annotated points inside the frame, their errors) for one frame; pred None = no court."""
    h, w = shape[:2]
    inside = (gt[:, 0] >= 0) & (gt[:, 0] < w) & (gt[:, 1] >= 0) & (gt[:, 1] < h)
    if pred is None:
        return 0, int(inside.sum()), []
    d = np.linalg.norm(pred[inside] - gt[inside], axis=1)
    return int((d <= tol).sum()), int(inside.sum()), [float(x) for x in d]


def bench_court(root: Path, device: str, n_images: int) -> dict:
    import cv2

    from tennisbio.candidates.court14 import REF, CourtTcd
    from tennisbio.court import fit_court

    items = tcd_val(root, n_images)
    tcd = CourtTcd(ensure_model("court14"), device)
    tcd.fit(cv2.imread(str(items[0][0])))                  # warm-up
    per = {}
    for name, fn in (("ours (líneas)", fit_court), ("court14", tcd.fit)):
        ok = tot = found = 0
        errs, secs = [], 0.0
        for img_path, gt in items:
            img = cv2.imread(str(img_path))
            fit, dt = timed(fn, img)
            secs += dt
            found += fit is not None
            a, b, e = score_court(None if fit is None else fit.to_image(REF), gt, img.shape)
            ok, tot, errs = ok + a, tot + b, errs + e
        per[name] = {"images": len(items), "court_found": round(found / len(items), 3) if items else None,
                     "points_within_7px": round(ok / tot, 3) if tot else None,
                     "median_err_px": round(float(np.median(errs)), 2) if errs else None,
                     "fps": round(len(items) / secs, 1) if secs else None}
        print(f"  pista {name}: {per[name]}", flush=True)
    b, c = per["ours (líneas)"], per["court14"]
    return {"baseline": "tennisbio.court.fit_court", "candidate": "TennisCourtDetector", "per_model": per,
            "accuracy": f"puntos a ≤7 px {c['points_within_7px']} / {b['points_within_7px']}; pista hallada {c['court_found']} / {b['court_found']}",
            "speed": f"{c['fps']} / {b['fps']} fotogramas/s",
            "verdict": verdict(c["points_within_7px"], b["points_within_7px"], c["fps"], b["fps"],
                               "puntos a ≤7 px", "fotogramas/s"),
            "notes": [f"Conjunto de validación de TennisCourtDetector ({len(items)} fotogramas 1280x720; ese modelo eligió "
                      "sus pesos con él, así que su cifra es algo optimista)."]}


# ---------------------------------------------------------------- far player: RF-DETR vs YOLO11m-pose

def covers(box, racket_xywh, margin: float = 0.5) -> bool:
    """The racket's centre inside the person box enlarged by `margin` of its size on each side."""
    x0, y0, x1, y1 = box[:4]
    mx, my = margin * (x1 - x0), margin * (y1 - y0)
    cx, cy = racket_xywh[0] + racket_xywh[2] / 2, racket_xywh[1] + racket_xywh[3] / 2
    return x0 - mx <= cx <= x1 + mx and y0 - my <= cy <= y1 + my


def bench_far(root: Path, device: str, n_images: int) -> dict:
    import cv2
    from collections import defaultdict

    from tennisbio.candidates.rfdetr import RfDetrPeople
    from tennisbio.court import fit_court
    from tennisbio.court_metrics import far_roi
    from tennisbio.pose.backend import set_device
    from tennisbio.pose.yolo import detect_people
    from tennisbio.validation.datasets import racketvision_split, racketvision_video

    set_device(device)
    coco = racketvision_split(root, "test")
    by_img = defaultdict(list)
    for a in coco["annotations"]:
        if a["category_id"] == 2 and a.get("bbox"):
            by_img[a["image_id"]].append(a)
    images = [im for im in coco["images"] if any(a["bbox"][1] + a["bbox"][3] / 2 < 0.5 * im.get("height", 1080)
                                                 for a in by_img.get(im["id"], []))]
    images = images[:: max(1, len(images) // n_images)][:n_images]
    rf = RfDetrPeople(ensure_model("rfdetr"), device)

    def ours(frame):
        fit = fit_court(frame)
        h, w = frame.shape[:2]
        roi = far_roi(fit.H, frame.shape) if fit is not None else (0, 0, w, int(0.55 * h))
        return detect_people(frame, roi)
    models = {"ours (YOLO11m-pose, mitad lejana)": ours, "rfdetr": lambda f: rf.people([f])[0]}
    hit = {k: 0 for k in models}
    secs = {k: 0.0 for k in models}
    total = 0
    caps = {}
    for im in images:
        match, _, clip, name = im["file_name"].split("/")
        cap = caps.get((match, clip)) or cv2.VideoCapture(str(racketvision_video(root, match, clip)))
        caps[(match, clip)] = cap
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(Path(name).stem))
        ok, frame = cap.read()
        if not ok:
            continue
        far = [a for a in by_img[im["id"]] if a["bbox"][1] + a["bbox"][3] / 2 < 0.5 * frame.shape[0]]
        if total == 0:
            for fn in models.values():
                fn(frame)                                   # warm-up
        total += len(far)
        for k, fn in models.items():
            boxes, dt = timed(fn, frame)
            secs[k] += dt
            bx = np.asarray(boxes, float).reshape(len(boxes), -1) if len(boxes) else np.zeros((0, 4))
            hit[k] += sum(any(covers(b, a["bbox"]) for b in bx) for a in far)
    for c in caps.values():
        c.release()
    per = {k: {"far_found": round(hit[k] / total, 3) if total else None,
               "fps": round(len(images) / secs[k], 1) if secs[k] else None} for k in models}
    b, c = per["ours (YOLO11m-pose, mitad lejana)"], per["rfdetr"]
    return {"baseline": "YOLO11m-pose en la mitad lejana", "candidate": "RF-DETR Medium 1152", "per_model": per,
            "far_rackets": total, "accuracy": f"jugadora lejana hallada {c['far_found']} / {b['far_found']}",
            "speed": f"{c['fps']} / {b['fps']} fotogramas/s",
            "verdict": verdict(c["far_found"], b["far_found"], c["fps"], b["fps"], "lejana hallada", "fotogramas/s"),
            "notes": ["Referencia: la raqueta anotada del jugador lejano en los fotogramas de prueba de RacketVision "
                      "(la persona hallada la contiene, con un margen de media caja)."]}


# ---------------------------------------------------------------- strokes: F3ED vs our learned spotter

def bench_f3ed(root: Path, device: str, cfg: dict) -> dict:
    from tennisbio import match_files as mf
    from tennisbio import spotting as S
    from tennisbio.candidates.f3ed import F3edSpotter
    from tennisbio.config import default_player, player_surname
    from tennisbio.io.video import probe
    from tennisbio.validation import recall_eval as R
    from tennisbio.validation.datasets import f3set_tennis

    player = player_surname(default_player())
    base = root / "f3set" / "recall"
    ids_by_split, clips = {}, []
    for sp in ("train", "val", "test"):
        c, _ = f3set_tennis(root, sp)
        clips += c
        ids_by_split[sp] = {x["video"] for x in c}
    pts = R.player_points(clips, player)
    by_video = {}
    for p in pts:
        by_video.setdefault(p["video"], []).append(p)
    spot = F3edSpotter(ensure_model("f3ed"), device)
    rows = {"f3ed": {"all": ([], []), "test": ([], [])}, "ours": {"all": ([], []), "test": ([], [])}}
    secs = {"f3ed": 0.0, "ours": 0.0}
    minutes, used, notes = 0.0, [], []
    for name, ps in sorted(by_video.items()):
        vid, plan_f = base / "videos" / f"{name}.mp4", base / "videos" / f"{name}.json"
        mdir = base / "salidas" / ("recall_" + name.lower().replace("-", "_")[:60])
        ours_f = mf.at(mdir, "spotting.json")
        if not (vid.exists() and plan_f.exists()):
            notes.append(f"{name}: sin compilación (ejecutar scripts/validate_recall.py --spotter)")
            continue
        segs = json.loads(plan_f.read_text(encoding="utf-8"))["segments"]
        got = {pid for s in segs for pid in s["points"]}
        ps = [p for p in ps if p["id"] in got]
        events, spans = R.place_events(ps, segs)
        test_ids = {p["id"] for p in ps if p["id"] in ids_by_split["test"]}
        test_spans = R.place_events([p for p in ps if p["id"] in test_ids], segs)[1] if test_ids else []
        info = probe(vid)
        from tennisbio.io.video import open_capture
        cap = open_capture(vid)

        def frames():
            while True:
                ok, f = cap.read()
                if not ok:
                    return
                yield f
        pred, dt = timed(spot.spot, frames(), info.fps)
        cap.release()
        secs["f3ed"] += dt
        minutes += info.duration / 60
        ours = json.loads(ours_f.read_text(encoding="utf-8")) if ours_f.exists() else None
        if ours is None:
            notes.append(f"{name}: sin spotting.json del detector propio (ejecutar scripts/validate_recall.py --spotter)")
        else:
            man = json.loads(mf.at(mdir, "manifest.json").read_text(encoding="utf-8")) if mf.at(mdir, "manifest.json").exists() else {}
            secs["ours"] += float((man.get("spotting") or {}).get("seconds") or 0)
        inside = lambda e, sp: any(a - 0.5 <= e["t"] <= b + 0.5 for a, b in sp)
        for key, sp in (("all", spans), ("test", test_spans)):
            gt = [e for e in events if inside(e, sp)]
            rows["f3ed"][key][0].extend([{**e, "t": e["t"] + 1e6 * len(used)} for e in pred if inside(e, sp)])
            rows["f3ed"][key][1].extend([{**e, "t": e["t"] + 1e6 * len(used)} for e in gt])
            if ours is not None:
                rows["ours"][key][0].extend([{**e, "t": e["t"] + 1e6 * len(used)} for e in ours if inside(e, sp)])
                rows["ours"][key][1].extend([{**e, "t": e["t"] + 1e6 * len(used)} for e in gt])
        used.append(name)
        print(f"  golpes {name}: F3ED {len(pred)} golpes en {dt:.0f} s", flush=True)
    per = {}
    for k in rows:
        per[k] = {key: (S.evaluate(*rows[k][key], tol=SPOT_TOL_S) if rows[k][key][1] else None) for key in ("all", "test")}
        per[k]["min_per_video_min"] = round(secs[k] / 60 / minutes, 3) if minutes and secs[k] else None
    f1 = lambda r: None if not r or r.get("recall") is None or r.get("precision") is None else (
        round(2 * r["recall"] * r["precision"] / (r["recall"] + r["precision"]), 3) if r["recall"] + r["precision"] else 0.0)
    key = "test" if per["f3ed"]["test"] else "all"
    c, b = f1(per["f3ed"][key]), f1(per["ours"][key])
    notes.append("F3ED se entrenó con la parte «train» de F3Set: la comparación justa es la de los puntos de «test»"
                 + ("" if key == "test" else " (no hay: se usan todos, a favor de F3ED)") + ".")
    notes.append("Velocidad: minutos de cálculo por minuto de vídeo; el propio es el tiempo de la etapa spotting "
                 "(sin la pasada barata que también usan otras etapas).")
    v = verdict(c, b, per["f3ed"]["min_per_video_min"], per["ours"]["min_per_video_min"], "F1 golpes",
                "min por min de vídeo", higher_is_faster=False)
    n_gt = (per["f3ed"][key] or {}).get("gt") or 0
    if n_gt < MIN_STROKES:
        v = {"adopt": False, "insufficient": True, "reason": f"solo {n_gt} golpes anotados medidos (hacen falta {MIN_STROKES})"}
    return {"baseline": "detector propio (spotting)", "candidate": "F3ED", "matches": used, "per_model": per,
            "accuracy": f"F1 golpes ({key}) {c} / {b}",
            "speed": f"{per['f3ed']['min_per_video_min']} / {per['ours']['min_per_video_min']} min por min de vídeo",
            "verdict": v, "notes": notes}


# ---------------------------------------------------------------- scoreboard: PP-OCRv5 vs our rapidocr

OCR_TIMEOUT_S = 4 * 3600


def ocr_samples(score: dict, n: int, every_s: float) -> tuple[list[float], list[float]]:
    """(up to n times our `score` stage read the scoreboard at, evenly spread; up to n/2 times it tried and read
    nothing, in shots of the main camera where it failed at least once). The second set is approximate: score.json
    keeps each shot's tries, not their times, so they are re-made as the stage makes them (start + 0.5 s, every_s)."""
    import bisect

    read = sorted(float(r["t"]) for r in score.get("readings") or [] if r.get("t") is not None)
    pick = read[:: max(1, len(read) // max(1, n))][:n] if read else []
    missed = []
    for sh in score.get("shots") or []:
        if (sh.get("tried") or 0) <= (sh.get("read") or 0):
            continue
        t = float(sh["start"]) + 0.5
        while t < float(sh["end"]):
            k = bisect.bisect_left(read, t - 0.05)
            if not (k < len(read) and abs(read[k] - t) <= 0.05):
                missed.append(round(t, 2))
            t += every_s
    m = max(1, n // 2)
    return pick, missed[:: max(1, len(missed) // m)][:m]


def ocr_plan(cfg: dict, n: int) -> tuple[list[dict], list[str]]:
    """The analysed matches of the catalogue with a score.json and their video still on disk."""
    from tennisbio import layout
    from tennisbio import match_files as mf
    from tennisbio.catalog import load_matches

    out_root = Path((cfg.get("paths") or {}).get("output") or "output")
    every = float((cfg.get("score") or {}).get("every_s", 5.0))
    plan, notes = [], []
    for m in load_matches(cfg):
        d = layout.dir_of(out_root, m, cfg)
        sc = mf.at(d, "score.json")
        if not sc.exists():
            continue
        score = json.loads(sc.read_text(encoding="utf-8"))
        names = score.get("names") or []
        if not score.get("readings") or len(names) != 2 or not all(names):
            notes.append(f"{m.id}: score.json sin lecturas")
            continue
        src = mf.at(d, "source.mkv")                     # the copy the stages read when the timeline was rewritten
        video = src if src.exists() and mf.at(d, "source.json").exists() else Path(m.video)
        if not video.exists():
            notes.append(f"{m.id}: falta el vídeo ({video})")
            continue
        read_t, miss_t = ocr_samples(score, n, every)
        stored = {round(float(r["t"]), 2): r for r in score["readings"]}
        plan.append({"id": m.id, "video": str(video), "names": names, "times": sorted(read_t + miss_t),
                     "stored": {f"{t:.2f}": stored.get(round(t, 2)) for t in read_t}})
    return plan, notes


def bench_ocr5(root: Path, device: str, cfg: dict, n: int) -> dict:
    from tennisbio.candidates.ocr5 import RAPIDOCR3, agreement, consistent, state_key

    plan, notes = ocr_plan(cfg, n)
    if not plan:
        raise RuntimeError("no hay partidos analizados con score.json y su vídeo: " + "; ".join(notes))
    ensure_model("ocr5")
    work = root / "ocr5"
    work.mkdir(parents=True, exist_ok=True)
    pf = work / "plan.json"
    pf.write_text(json.dumps({"matches": plan}, ensure_ascii=False), encoding="utf-8")
    uv = shutil.which("uv") or "uv"
    runs = {}
    for eng, py in (("ours", [sys.executable]), ("ppocrv5", [uv, "run", "--with", RAPIDOCR3, "python"])):
        out = work / f"lecturas_{eng}.json"
        # both on the CPU: the score stage runs there, next to the iGPU work of the rest of the pass
        cmd = py + [str(ROOT / "scripts" / "bench_ocr.py"), "--engine", eng, "--plan", str(pf), "--out", str(out),
                    "--device", "cpu"]
        print(f"  marcador {eng}: {' '.join(cmd)}", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, timeout=OCR_TIMEOUT_S, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        print(r.stdout[-1500:], flush=True)
        if r.returncode or not out.exists():
            raise RuntimeError(f"la lectura con {eng} falló: {r.stderr.strip()[-600:]}")
        runs[eng] = {m["id"]: m for m in json.loads(out.read_text(encoding="utf-8"))["matches"]}
    per, agree_now, agree_stored = {}, ([], []), {"ours": ([], []), "ppocrv5": ([], [])}
    for eng in runs:
        n_s = n_read = n_ok = 0
        secs = 0.0
        read_known = [0, 0]                     # read where our stage read; read where it had not
        for m in plan:
            got = runs[eng][m["id"]]
            rs = [None if r is None else {**r, "t": t} for t, r in zip(got["times"], got["readings"])]
            ok = consistent([r or {} for r in rs])
            n_s += len(rs)
            n_read += sum(state_key(r) is not None for r in rs)
            n_ok += sum(ok)
            secs += got["seconds"]
            for t, r in zip(got["times"], rs):
                hit = state_key(r) is not None
                if f"{t:.2f}" in m["stored"]:
                    read_known[0] += hit
                    agree_stored[eng][0].append(m["stored"][f"{t:.2f}"])
                    agree_stored[eng][1].append(r)
                else:
                    read_known[1] += hit
        n_known = sum(len(m["stored"]) for m in plan)
        per[eng] = {"samples": n_s, "read": round(n_read / n_s, 3) if n_s else None,
                    "consistent_per_sample": round(n_ok / n_s, 3) if n_s else None,
                    "consistent_of_read": round(n_ok / n_read, 3) if n_read else None,
                    "read_where_stage_read": round(read_known[0] / n_known, 3) if n_known else None,
                    "read_where_stage_missed": round(read_known[1] / (n_s - n_known), 3) if n_s > n_known else None,
                    "s_per_sample": round(secs / n_s, 3) if n_s else None}
    for m in plan:
        agree_now[0].extend(runs["ours"][m["id"]]["readings"])
        agree_now[1].extend(runs["ppocrv5"][m["id"]]["readings"])
    b, c = per["ours"], per["ppocrv5"]
    v = verdict(c["consistent_per_sample"], b["consistent_per_sample"], c["s_per_sample"], b["s_per_sample"],
                "lecturas coherentes por muestra", "s por muestra", higher_is_faster=False)
    return {"baseline": "rapidocr-onnxruntime 1.4 (PP-OCRv4)", "candidate": "rapidocr 3.10 + PP-OCRv5 mobile",
            "matches": [m["id"] for m in plan], "per_model": per,
            "agreement_ours_vs_candidate": agreement(*agree_now),
            "agreement_with_score_json": {k: agreement(*v_) for k, v_ in agree_stored.items()},
            "accuracy": f"lecturas coherentes por muestra {c['consistent_per_sample']} / {b['consistent_per_sample']}; "
                        f"leídas {c['read']} / {b['read']}",
            "speed": f"{c['s_per_sample']} / {b['s_per_sample']} s por muestra (CPU)", "verdict": v,
            "notes": notes + [
                "Sin marcadores anotados: no es una precisión frente a la verdad, sino acuerdo entre motores y "
                "coherencia (una lectura cuenta si encaja con la secuencia del partido según las reglas del tenis: "
                "juegos que solo crecen, el marcador de juegos más leído para cada total, puntos que no retroceden "
                "dentro de un juego; tennisbio.point_count). Un error que dé otra puntuación posible no se detecta.",
                "Muestras: instantes en que nuestra etapa leyó el marcador (score.json) y, aproximados, instantes en "
                "que lo intentó sin leerlo; los dos motores leen exactamente los mismos fotogramas, sin reutilizar "
                "lecturas, en la CPU (donde corre la etapa)."]}


# ---------------------------------------------------------------- 3D trunk: MotionAGFormer vs RTMW3D (CalTennis)

CAL_MARGIN_S = 1.2              # each segment is cut this much wider: the views are synchronised only to ±1 s
SYNC_MAX_PX = 8.0               # a segment whose two views never triangulate better than this is not used
REF_MAX_PX = 10.0               # a frame's trunk reference: its 4 points reproject within this in both views
MIN_REF_FRAMES = 200


def pose_track(video: Path, pose2d) -> dict:
    """2D pose of every person in every frame of a segment (our hybrid model): boxes, COCO keypoints, scores."""
    from tennisbio.io.video import open_capture

    cap = open_capture(video)
    fps = cap.get(5) or 60.0
    boxes, kps, confs, size = [], [], [], None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        size = (fr.shape[1], fr.shape[0])
        b, k, c, _, _ = pose2d(fr)
        boxes.append(np.asarray(b, float).reshape(len(b), -1)[:, :4])
        kps.append(np.asarray(k, float).reshape(len(b), 17, 2))
        confs.append(np.asarray(c, float).reshape(len(b), 17))
    cap.release()
    return {"fps": float(fps), "size": size, "boxes": boxes, "kps": kps, "confs": confs}


def follow(p: dict, start: int, idx: int) -> tuple[np.ndarray, np.ndarray, list]:
    """(keypoints (T, 17, 2) NaN where lost, scores (T, 17), boxes) of one person tracked from `idx` at `start`."""
    from tennisbio.candidates.caltennis import track

    ids = track(p["boxes"], start, idx)
    T = len(p["boxes"])
    k, c, b = np.full((T, 17, 2), np.nan), np.zeros((T, 17)), [None] * T
    for f, i in enumerate(ids):
        if i is not None:
            k[f], c[f], b[f] = p["kps"][f][i], p["confs"][f][i], p["boxes"][f][i]
    return k, c, b


def pair_person(ca, cb, pa: dict, pb: dict):
    """(frame of a, person in a, frame of b, person in b) of the same player in both views, around the middle of the
    segment (b searched over ±1 s, as the clocks may be that far apart); None when no pair triangulates."""
    from tennisbio.candidates.caltennis import match_people

    ia = len(pa["kps"]) // 2
    best = None
    for jb in range(max(0, ia - int(pb["fps"])), min(len(pb["kps"]), ia + int(pb["fps"]) + 1), 6):
        if not len(pa["kps"][ia]) or not len(pb["kps"][jb]):
            continue
        m = match_people(ca, cb, pa["kps"][ia], pa["confs"][ia], pb["kps"][jb], pb["confs"][jb])
        if m is not None and (best is None or m[2] < best[4]):
            best = (ia, m[0], jb, m[1], m[2])
    return None if best is None else best[:4]


def trunk_reference(c1, c2, k1, s1, t1, k2, s2, t2, off):
    """(T1, 2) shoulder/hip line directions at view 1's frames triangulated with view 2 (its clock + off = view 1's),
    NaN where the 4 trunk points are not seen in both or reproject worse than REF_MAX_PX; and the pelvis (T1, 3)."""
    from tennisbio.candidates.caltennis import COCO_TRUNK, interp, reproj_error, triangulate, trunk_yaw_from_world

    j = list(COCO_TRUNK)
    k2i, s2i = interp(t2 + off, k2[:, j], t1), interp(t2 + off, s2[:, j], t1)
    X = triangulate(c1.P, c2.P, k1[:, j], k2i)
    err = reproj_error(c1, c2, k1[:, j], k2i, X)
    good = (s1[:, j] >= 0.5).all(1) & (np.nan_to_num(s2i) >= 0.5).all(1) & (np.nan_to_num(err, nan=1e9) <= REF_MAX_PX).all(1)
    yaw = trunk_yaw_from_world(X)
    yaw[~good] = np.nan
    pelvis = X[:, 2:4].mean(1)
    pelvis[~good] = np.nan
    return yaw, pelvis


def rtmw3d_yaw(video: Path, boxes: list, cam, pelvis: np.ndarray, wb3d) -> tuple[np.ndarray, list]:
    """(T, 2) shoulder/hip directions in the world from RTMW3D in one view, and the ms of each call. Its image points
    are put at the true depth of the pelvis (from the reference: the best case for it; in a match the depth comes from
    her height) and its own depth offsets are added along the viewing axis (+ away from the camera)."""
    from tennisbio.candidates.caltennis import trunk_yaw_from_world
    from tennisbio.io.video import open_capture

    out, ms = np.full((len(boxes), 2), np.nan), []
    fx, fy, cx, cy = cam.K[0, 0], cam.K[1, 1], cam.K[0, 2], cam.K[1, 2]
    cap = open_capture(video)
    for f in range(len(boxes)):
        ok, fr = cap.read()
        if not ok:
            break
        if boxes[f] is None or not np.isfinite(pelvis[f]).all():
            continue
        t0 = time.perf_counter()
        k3, _, k2 = wb3d(fr, np.asarray(boxes[f], float))
        ms.append(1000 * (time.perf_counter() - t0))
        Z = float(cam.to_cam(pelvis[f])[2])
        idx = [5, 6, 11, 12]                               # COCO-WholeBody: shoulders and hips, as COCO
        z = k3[idx, 2] - k3[idx[2:], 2].mean()
        pc = np.stack([(k2[idx, 0] - cx) * Z / fx, (k2[idx, 1] - cy) * Z / fy, Z + z], 1)
        out[f] = trunk_yaw_from_world((pc @ cam.R_c2w.T)[None])[0]
    cap.release()
    return out, ms


def bench_mag3d(root: Path, device: str, cfg: dict, n_pairs: int, n_segments: int, seg_s: float) -> dict:
    from tennisbio.candidates import caltennis as C
    from tennisbio.candidates.motionagformer import (H36M_L_HIP, H36M_L_SH, H36M_R_HIP, H36M_R_SH, MotionAGFormerLifter,
                                                     line_yaw_world)
    from tennisbio.config import resolve_path
    from tennisbio.pose.backend import set_device
    from tennisbio.pose.variants import model as pose_model
    from tennisbio.pose.wholebody3d import WholeBody3D

    set_device(device)
    fcfg = cfg.get("fine_pass") or {}
    hp = resolve_path(fcfg.get("hand3d_onnx") or "models/rtmw3d-x.onnx")
    if hp is None or not hp.exists():
        raise FileNotFoundError(f"falta nuestro modelo 3D ({hp}): ejecuta scripts/setup_models.py")
    wb3d = WholeBody3D(str(hp), device, fp16=bool(fcfg.get("fp16", True)) and device != "cpu")
    lifters = {"mag3d-xs": MotionAGFormerLifter(ensure_model("mag3d"), device),
               "mag3d-s": MotionAGFormerLifter(ensure_model("mag3d-s"), device)}
    base = "ours (RTMW3D)"
    pose2d = pose_model("hybrid-x", device)
    prs = C.pairs(root, C.metadata(root))[:n_pairs]
    if not prs:
        raise RuntimeError("CalTennis: ningún par de vistas calibradas del mismo lado de la pista")
    mono = {k: [] for k in (base, *lifters)}
    refs = {k: [] for k in mono}
    ms = {k: [] for k in mono}
    used, notes = [], []
    work = root / "caltennis" / "segmentos"
    for p in prs:
        cam = {"a": C.camera(root, p["a"]), "b": C.camera(root, p["b"])}
        st = {"a": C.start_time(p["a"]["video_id"]), "b": C.start_time(p["b"]["video_id"])}
        lo, hi = p["overlap"][0] + 60, p["overlap"][1] - 60 - seg_s
        for k, g in enumerate(np.linspace(lo, max(lo, hi), n_segments)):
            vids, pt = {}, {}
            for v in ("a", "b"):
                vids[v] = C.fetch_segment(p[v], g - st[v] - CAL_MARGIN_S, seg_s + 2 * CAL_MARGIN_S,
                                          work / f"{p['session']}_{k}_{v}.mp4")
                pt[v] = pose_track(vids[v], pose2d)
            pair = pair_person(cam["a"], cam["b"], pt["a"], pt["b"])
            if pair is None:
                notes.append(f"{p['session']} tramo {k}: la misma persona no se encuentra en las dos vistas")
                continue
            ka, sa, ba = follow(pt["a"], pair[0], pair[1])
            kb, sb, bb = follow(pt["b"], pair[2], pair[3])
            ta, tb = np.arange(len(ka)) / pt["a"]["fps"], np.arange(len(kb)) / pt["b"]["fps"]
            off, err = C.best_offset(cam["a"], cam["b"], ta, ka, sa, tb, kb, sb,
                                     np.arange(-1.5, 1.5, 1 / (2 * pt["a"]["fps"])))
            if off is None or err > SYNC_MAX_PX:
                notes.append(f"{p['session']} tramo {k}: no se sincroniza (error {err:.1f} px)")
                continue
            for v, (c1, c2, k1, s1, t1, b1, k2, s2, t2, o) in {
                    "a": (cam["a"], cam["b"], ka, sa, ta, ba, kb, sb, tb, off),
                    "b": (cam["b"], cam["a"], kb, sb, tb, bb, ka, sa, ta, -off)}.items():
                ref, pelvis = trunk_reference(c1, c2, k1, s1, t1, k2, s2, t2, o)
                inner = (t1 >= CAL_MARGIN_S) & (t1 <= CAL_MARGIN_S + seg_s)        # the segment proper
                ref[~inner] = np.nan
                y, t_ms = rtmw3d_yaw(vids[v], b1, c1, pelvis, wb3d)
                mono[base].append(y)
                refs[base].append(ref)
                ms[base] += t_ms
                w, h = pt[v]["size"]
                for name, lf in lifters.items():
                    t0 = time.perf_counter()
                    X = lf.lift(k1, s1, w, h)
                    ms[name].append(1000 * (time.perf_counter() - t0) / max(1, len(k1)))
                    yl = np.stack([line_yaw_world(X, H36M_L_SH, H36M_R_SH, c1.R_c2w),
                                   line_yaw_world(X, H36M_L_HIP, H36M_R_HIP, c1.R_c2w)], 1)
                    yl[~(s1[:, [5, 6, 11, 12]] >= 0.5).all(1)] = np.nan
                    mono[name].append(yl)
                    refs[name].append(ref)
            used.append({"session": p["session"], "segment": k, "angle": p["angle"], "sync_s": round(off, 3),
                         "sync_px": round(err, 2)})
            print(f"  3D {p['session']} tramo {k}: desfase {off:+.3f} s, {err:.1f} px", flush=True)
    per = {}
    for name in mono:
        e = C.angle_errors(np.concatenate(mono[name]) if mono[name] else np.zeros((0, 2)),
                           np.concatenate(refs[name]) if refs[name] else np.zeros((0, 2)))
        e["ms_per_frame"] = round(float(np.median(ms[name])), 2) if ms[name] else None
        e["fps"] = round(1000 / e["ms_per_frame"], 1) if e["ms_per_frame"] else None
        per[name] = e
    b = per[base]
    cand = max(lifters, key=lambda k: ((per[k]["within_15deg"] or 0), per[k]["fps"] or 0))
    c = per[cand]
    v = verdict(c["within_15deg"], b["within_15deg"], c["fps"], b["fps"], "giro del tronco a ≤15° de la referencia",
                "fotogramas/s")
    if (b["frames"] or 0) < MIN_REF_FRAMES or (c["frames"] or 0) < MIN_REF_FRAMES:
        v = {"adopt": False, "insufficient": True,
             "reason": f"solo {min(b['frames'], c['frames'])} fotogramas con referencia (hacen falta {MIN_REF_FRAMES})"}
    return {"baseline": "RTMW3D (tennisbio.pose.wholebody3d)", "candidate": f"MotionAGFormer ({cand})", "per_model": per,
            "segments": used, "accuracy": f"a ≤15° {c['within_15deg']} / {b['within_15deg']}; mediana "
                                          f"{c['median_err_deg']} / {b['median_err_deg']}°; X-factor "
                                          f"{c['xfactor_median_err_deg']} / {b['xfactor_median_err_deg']}°",
            "speed": f"{c['fps']} / {b['fps']} fotogramas/s (el candidato usa la pose 2D que ya tiene la pasada fina)",
            "verdict": v, "notes": notes + [
                "Referencia: la línea de hombros y la de caderas triangulada desde dos vistas calibradas y sincronizadas "
                "de CalTennis (nuestra pose 2D en las dos; no depende de ninguna profundidad estimada). Cada modelo 3D "
                "se lee en una sola vista; error = diferencia de su dirección alrededor de la vertical.",
                "Las cámaras de CalTennis están a ~1,7 m de altura, a un lado o detrás de la pista; la de la tele está "
                "más alta. Un modelo que falla aquí no sirve; uno que acierta aquí no queda probado para la vista de "
                "la tele (allí RTMW3D aplanaba la profundidad: tennisbio.reliability).",
                "RTMW3D se sitúa a la profundidad real de la pelvis (sacada de la referencia): es su mejor caso."]}


# ---------------------------------------------------------------- bounce: CatBoost vs our rule (TrackNet dataset)

TRACKNET_ZIP = "https://drive.usercontent.google.com/download?id=1DQ3ZbvokTsgOq6x-ay6O8U2W4a8e3LFw&export=download&confirm=t"
TRACKNET_FPS = 30.0
BOUNCE_TOL_F = 3                # frames (0.1 s at 30 fps): a predicted bounce this close to an annotated one is right
MIN_BOUNCES = 20


def tracknet_index(root: Path) -> dict[str, str]:
    """clip key (game_clip) → its folder inside the TrackNet dataset's zip; the 95 Label.csv files are read by HTTP
    ranges once (not the 2.6 GB of images) and kept in <root>/tracknet/labels/."""
    d = root / "tracknet" / "labels"
    idx = d / "index.json"
    if not idx.exists():
        z = zipfile.ZipFile(io.BufferedReader(HttpFile(TRACKNET_ZIP), 1 << 16))
        d.mkdir(parents=True, exist_ok=True)
        folders = {}
        for name in z.namelist():
            if name.endswith("/Label.csv"):
                game, clip = name.split("/")[-3:-1]
                (d / f"{game}_{clip}.csv").write_bytes(z.read(name))
                folders[f"{game}_{clip}"] = name[: -len("Label.csv")]
        idx.write_text(json.dumps(folders, indent=1), encoding="utf-8")
    return json.loads(idx.read_text(encoding="utf-8"))


def read_tracknet(path: Path) -> tuple[list[str], np.ndarray, np.ndarray]:
    """(image names, ball (T, 2) with NaN where not visible, status (T,): 0 flying, 1 hit, 2 bounce, -1 unknown)."""
    names, xy, st = [], [], []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            names.append(r["file name"])
            x, y = (r.get("x-coordinate") or "").strip(), (r.get("y-coordinate") or "").strip()
            vis = (r.get("visibility") or "0").strip() not in ("", "0")
            xy.append((float(x), float(y)) if vis and x and y else (np.nan, np.nan))
            s = (r.get("status") or "").strip()
            st.append(int(float(s)) if s else -1)
    return names, np.asarray(xy, float).reshape(-1, 2), np.asarray(st, int)


def tracknet_frames(root: Path, key: str, folder: str, names: list[str]) -> list[np.ndarray]:
    import cv2

    d = root / "tracknet" / "images" / key
    d.mkdir(parents=True, exist_ok=True)
    z = None
    out = []
    for n in names:
        p = d / n
        if not p.exists():
            z = z or zipfile.ZipFile(io.BufferedReader(HttpFile(TRACKNET_ZIP), 1 << 16))
            p.write_bytes(z.read(folder + n))
        out.append(cv2.imread(str(p)))
    return out


def rule_bounces(track: np.ndarray, hits: list[int], fps: float) -> list[int]:
    """Our rule as the stages use it: the bounce of each shot is the sharpest turn of the ball path between its hit
    and the next (tennisbio.ball.bounce_before of the next hit), and after the last hit the first turn
    (bounce_after). No image band here: the dataset has both halves of the court."""
    from tennisbio.ball import bounce_after, bounce_before

    hits = sorted(int(h) for h in hits)
    out = set()
    for prev, h in zip(hits, hits[1:]):
        b = bounce_before(track, h, fps, prev_hit=prev)
        if b is not None:
            out.add(b.frame)
    if hits:
        a = bounce_after(track, hits[-1], fps)
        if a:
            out.add(a[0].frame)
    return sorted(out)


def match_events(pred: list[int], gt: list[int], tol: int) -> tuple[int, int, int, list[int]]:
    """(right, false, missed, frame errors of the right ones): each annotated event takes the closest free
    prediction within tol frames (closest pairs first)."""
    pairs = sorted((abs(p - g), i, j) for i, p in enumerate(pred) for j, g in enumerate(gt) if abs(p - g) <= tol)
    used_p, used_g, errs = set(), set(), []
    for d, i, j in pairs:
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        errs.append(d)
    return len(errs), len(pred) - len(errs), len(gt) - len(errs), errs


def bench_bounce(root: Path, device: str, cfg: dict, n_clips: int) -> dict:
    import math

    from tennisbio.ball import BallTracker, ball_hits
    from tennisbio.candidates.bounce_ctb import CatBoostBounce
    from tennisbio.config import resolve_path

    folders = tracknet_index(root)
    lab = root / "tracknet" / "labels"
    ctb = CatBoostBounce(ensure_model("bounce"), device)
    names = ("ours (regla)", "bounce")
    acc = {m: {k: [0, 0, 0, []] for k in names} for m in ("annotated", "tracked")}
    secs, frames_timed, n_gt = {k: 0.0 for k in names}, 0, {"annotated": 0, "tracked": 0}

    def add(mode, preds, gt):
        n_gt[mode] += len(gt)
        for k, p in preds.items():
            tp, fp, fn, e = match_events(p, list(gt), BOUNCE_TOL_F)
            a = acc[mode][k]
            a[0] += tp
            a[1] += fp
            a[2] += fn
            a[3] += e
    keys = sorted(folders)
    for key in keys:                                     # the annotated ball: the bounce models alone
        _, tr, st = read_tracknet(lab / f"{key}.csv")
        add("annotated", {"ours (regla)": rule_bounces(tr, list(np.flatnonzero(st == 1)), TRACKNET_FPS),
                          "bounce": ctb.bounces(tr)}, np.flatnonzero(st == 2))
    ours_path = resolve_path((cfg.get("ball") or {}).get("onnx") or "models/balltrack.onnx")
    if ours_path is None or not ours_path.exists():
        raise FileNotFoundError(f"falta nuestro modelo de bola ({ours_path}): ejecuta scripts/setup_models.py")
    tracker = BallTracker(str(ours_path), device, fp16=bool((cfg.get("ball") or {}).get("fp16", True)) and device != "cpu")
    sel = keys[:: max(1, len(keys) // max(1, n_clips))][:n_clips]
    for key in sel:                                      # our ball tracker's path: the task in a match
        nm, _, st = read_tracknet(lab / f"{key}.csv")
        frames = tracknet_frames(root, key, folders[key], nm)
        tr = tracker.track(frames, step=1)               # 30 fps: as the fine pass reads the ball
        hits = [h.frame for h in ball_hits(tr, frames[0].shape[0], TRACKNET_FPS)]
        rb, dt_r = timed(rule_bounces, tr, hits, TRACKNET_FPS)
        cb, dt_c = timed(ctb.bounces, tr)
        secs["ours (regla)"] += dt_r
        secs["bounce"] += dt_c
        frames_timed += len(tr)
        add("tracked", {"ours (regla)": rb, "bounce": cb}, np.flatnonzero(st == 2))
        print(f"  bote {key}: {len(frames)} fotogramas", flush=True)
    per = {}
    for mode in acc:
        per[mode] = {k: {**prf(*a[:3]), "median_err_f": float(np.median(a[3])) if a[3] else None}
                     for k, a in acc[mode].items()}
    # what each adds to the full pass: seconds per hour of 30 fps video, and minutes rounded up to 0.1 (the full pass
    # takes ~75 min per hour of video and varies by minutes between runs: less than 6 s per hour cannot change it)
    sph = {k: (round(secs[k] / frames_timed * TRACKNET_FPS * 3600, 1) if frames_timed else None) for k in names}
    mph = {k: (None if s is None else math.ceil(s / 6) / 10) for k, s in sph.items()}
    b, c = per["tracked"]["ours (regla)"], per["tracked"]["bounce"]
    v = verdict(c["f1"], b["f1"], mph["bounce"], mph["ours (regla)"], "F1 botes (bola de nuestro detector)",
                "min añadidos a la pasada por hora de vídeo", higher_is_faster=False)
    if n_gt["tracked"] < MIN_BOUNCES:
        v = {"adopt": False, "insufficient": True, "reason": f"solo {n_gt['tracked']} botes anotados en los clips medidos "
                                                             f"(hacen falta {MIN_BOUNCES})"}
    ca, ba = per["annotated"]["bounce"], per["annotated"]["ours (regla)"]
    return {"baseline": "regla del giro más brusco (tennisbio.ball)", "candidate": "CatBoost (TennisProject)",
            "per_model": per, "seconds_per_hour": sph, "minutes_per_hour": mph,
            "clips": {"annotated": len(keys), "tracked": len(sel)}, "bounces": n_gt,
            "accuracy": f"F1 botes con nuestra bola {c['f1']} / {b['f1']}; con la bola anotada {ca['f1']} / {ba['f1']}",
            "speed": f"{mph['bounce']} / {mph['ours (regla)']} min por hora de vídeo "
                     f"({sph['bounce']} / {sph['ours (regla)']} s)", "verdict": v,
            "notes": [f"Bote acertado si está a ≤{BOUNCE_TOL_F} fotogramas (0,1 s) de uno anotado.",
                      "El modelo CatBoost se entrenó con este mismo conjunto (10 partidos, 75 % de sus fotogramas al azar): "
                      "su cifra es optimista; no hay otro conjunto público con botes anotados. Con la bola de nuestro "
                      "detector las entradas ya no son las de su entrenamiento.",
                      "Con la bola anotada la regla recibe los golpes anotados; con la de nuestro detector, los golpes "
                      "que saca tennisbio.ball.ball_hits, como en un partido.",
                      "Las dos son pasos sobre la trayectoria de la bola ya calculada. Velocidad: lo que cada una añade a "
                      "la pasada completa, en minutos por hora de vídeo redondeados hacia arriba a 0,1 (la pasada dura "
                      "~75 min por hora de vídeo y varía minutos entre ejecuciones; menos de 6 s por hora no la cambia); "
                      "entre paréntesis, los segundos medidos."]}


# ---------------------------------------------------------------- main

def default_root(cfg: dict) -> Path:
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    near = out.parent / "datasets"
    return near if near.exists() else Path("datasets")


def main(argv=None):
    from tennisbio.config import load_config

    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="carpeta de datos anotados (por defecto <salidas>/../datasets)")
    ap.add_argument("--device", default=None, help="dml, cpu… (por defecto el de la configuración)")
    ap.add_argument("--only", default="", help="candidatos separados por comas: " + ",".join(CANDIDATES))
    ap.add_argument("--force", action="store_true", help="repetir también los ya medidos")
    ap.add_argument("--clips", type=int, default=8, help="clips de RacketVision (bola y pose)")
    ap.add_argument("--court-images", type=int, default=300)
    ap.add_argument("--far-images", type=int, default=300)
    ap.add_argument("--ocr-samples", type=int, default=150, help="marcador: muestras leídas por partido (+ la mitad sin leer)")
    ap.add_argument("--cal-pairs", type=int, default=3, help="3D: pares de vistas de CalTennis")
    ap.add_argument("--cal-segments", type=int, default=5, help="3D: tramos por par")
    ap.add_argument("--cal-seconds", type=float, default=4.0, help="3D: segundos por tramo")
    ap.add_argument("--bounce-clips", type=int, default=24, help="bote: clips del conjunto TrackNet con nuestra bola")
    ap.add_argument("--budget-min", type=float, default=0, help="no empezar otro candidato pasado este tiempo (0 = sin límite)")
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else default_root(cfg)
    device = a.device or cfg.get("device", "cpu")
    todo = [c for c in (a.only.split(",") if a.only else CANDIDATES) if c]
    bad = [c for c in todo if c not in CANDIDATES]
    if bad:
        sys.exit(f"candidatos desconocidos: {bad}")
    rep_dir = root / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    jf = rep_dir / "bench_candidates.json"
    rep = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
    if rep.get("version") != VERSION or rep.get("device") != device:
        rep = {"version": VERSION, "device": device, "results": {}}
    runs = {"wasb": lambda: bench_ball(root, device, cfg, a.clips), "rtmw": lambda: bench_pose(root, device, a.clips),
            "court14": lambda: bench_court(root, device, a.court_images),
            "rfdetr": lambda: bench_far(root, device, a.far_images), "f3ed": lambda: bench_f3ed(root, device, cfg),
            "ocr5": lambda: bench_ocr5(root, device, cfg, a.ocr_samples),
            "mag3d": lambda: bench_mag3d(root, device, cfg, a.cal_pairs, a.cal_segments, a.cal_seconds),
            "bounce": lambda: bench_bounce(root, device, cfg, a.bounce_clips)}
    t0 = time.time()
    for name in todo:
        done = (rep["results"].get(name) or {}).get("verdict") or {}
        if not a.force and done and not done.get("insufficient"):      # too little data: measured again next time
            print(f"== {name}: ya medido (--force para repetir)")
            continue
        if a.budget_min and (time.time() - t0) / 60 > a.budget_min:
            print(f"== {name}: sin tiempo en este tramo; sigue en la próxima ejecución")
            break
        print(f"== {name}", flush=True)
        try:
            r, dt = timed(runs[name])
            r["minutes"] = round(dt / 60, 1)
        except Exception as e:                    # one candidate that fails never stops the others
            import traceback
            r = {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]}
        rep["results"][name] = r
        rep["generated"] = time.strftime("%Y-%m-%d %H:%M")
        jf.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"   {r.get('verdict') or r.get('error')}", flush=True)
    rep.setdefault("generated", time.strftime("%Y-%m-%d %H:%M"))
    md = to_markdown(rep)
    (rep_dir / "bench_candidates.md").write_text(md, encoding="utf-8")
    out_cfg = (cfg.get("paths") or {}).get("output")
    out = Path(out_cfg) if out_cfg else None             # never the current folder (the repository) by default
    if out is not None and out.is_dir() and out.resolve() != rep_dir.resolve():
        for f in ("bench_candidates.json", "bench_candidates.md"):
            shutil.copy(rep_dir / f, out / f)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
