"""Paso 2 de la Base (docs/plan_maestro.md, "Plan a corto plazo (02-11)"): each candidate model of the reference
project (tennisbio.candidates), measured on this PC against the model it would replace, on annotated data, in
accuracy and in speed on the configured device (the iGPU, `dml`).

    candidate  ours                                annotated data (downloaded on first use, then cached)
    wasb       TrackNetV3 (ball.onnx, fp16 on iGPU) RacketVision test clips: annotated ball positions
    rtmw       YOLO11m-pose + RTMPose-x (hybrid)    RacketVision test clips: strokes from the annotated ball turns
    court14    tennisbio.court.fit_court (lines)    TennisCourtDetector's val split: 14 annotated points per frame
    rfdetr     YOLO11m-pose on the far half         RacketVision test frames: the far player's annotated racket
    f3ed       our learned spotter (spotting.json)  F3Set compilations of scripts/validate_recall.py (YouTube)

Rule to adopt a candidate, written in the output for each one: accuracy equal or better AND not slower for the
whole pass of a new match (the same work, on this PC). A candidate that wins only one of the two is not adopted;
nothing here changes the pipeline: adopting one is a change of its own.

The missing ONNX files are made first with their export scripts (scripts/export_*.py; RF-DETR with
`uv run --with rfdetr==1.11.2`). Every candidate's result is saved as soon as it is measured; a later run measures
only what is missing (--force to repeat). With no arguments (a "medir" request of the PC: script bench_candidates)
it measures everything with the configured device and datasets next to the output folder.

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
CANDIDATES = ("wasb", "rtmw", "court14", "rfdetr", "f3ed")
MODELS = ROOT / "models"
EXPORTS = {
    "wasb": (MODELS / "wasb_tennis.onnx", ["export_wasb.py"], False),
    "rtmw": (MODELS / "rtmw-x_384x288.onnx", ["export_rtmw.py"], False),
    "court14": (MODELS / "court_tcd.onnx", ["export_court_tcd.py"], False),
    "rfdetr": (MODELS / "rfdetr_medium_1152.onnx", ["export_rfdetr.py"], True),
    "f3ed": (MODELS / "f3ed.onnx", ["export_f3ed.py"], False),
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
    path, script, with_rfdetr = EXPORTS[name]
    if path.exists():
        return path
    cmd = ([shutil.which("uv") or "uv", "run", "--with", "rfdetr==1.11.2", "python"] if with_rfdetr else [sys.executable])
    cmd += [str(ROOT / "scripts" / script[0]), "--out", str(path)]
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
            "rfdetr": lambda: bench_far(root, device, a.far_images), "f3ed": lambda: bench_f3ed(root, device, cfg)}
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
