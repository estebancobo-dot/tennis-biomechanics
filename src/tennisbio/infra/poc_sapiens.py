"""#307 (15-11): Sapiens2 (Meta, 2026; the user allowed its licence) against the fine pass's pose, on the same frames.

The 10-minute test v26 left, for each of her strokes, the window it was posed on (windows/<id>.mp4), her box in every
frame and the hybrid's keypoints (series/<id>.json: the body cleaned and smoothed by kinematics.clean, the six foot
points raw). Here Sapiens2 poses the same crops; its 308 points are taken to the hybrid's (COCO17 body, Halpe26 feet)
and cleaned with the same kinematics.clean, so both are compared as the measures would see them:

- jitter: the median frame-to-frame acceleration of each point over the stroke, in fractions of her box height (both
  models follow the same motion: what one shakes more is noise);
- seen: the share of frames with the point's confidence ≥ 0.3 (the body's 12 joints; the six foot points);
- agreement: the median distance between the two, in fractions of her height;
- time per crop on this GPU (the model alone, and with the crop and post-processing).

Rule written before measuring (docs/registro_decisiones.md, Sapiens2): it goes on to the integrated test (the fine pass
with Sapiens2, strokes compared with v26) if its body shakes at least 10 % less, its feet no more, and it sees the feet
at least as often; the time per crop is what says how many GPU hours a match would cost.

    python -m tennisbio.infra.poc_sapiens --previa <v26 output folder> --modelos facebook/sapiens2-pose-0.4b,... \
        --dispositivo cuda --salida poc.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

MIN_CONF = 0.3
BODY = list(range(5, 17))                      # shoulders to ankles (COCO17)
WRISTS = [9, 10]
# Sapiens2's 308 points (goliath order, sapiens/pose/configs/_base_/keypoints308.py) → COCO17 and the six Halpe26 feet
TO_COCO17 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 62, 41, 9, 10, 11, 12, 13, 14]
TO_FEET = [15, 18, 16, 19, 17, 20]             # left/right big toe, left/right small toe, left/right heel (FOOT_NAMES)
MARGIN_BODY = 0.9


def to_hybrid(kp308: np.ndarray, sc308: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(body 17×2, body conf 17, feet 6×2, feet conf 6) from one person's 308 points and scores."""
    return kp308[TO_COCO17], sc308[TO_COCO17], kp308[TO_FEET], sc308[TO_FEET]


def jitter(kp: np.ndarray, height: float, idx: list[int]) -> float | None:
    """Median |p(t+1) − 2 p(t) + p(t−1)| / height over the points idx and the frames where all three are seen."""
    p = np.asarray(kp, float)[:, idx]
    if len(p) < 3 or not height:
        return None
    a = np.linalg.norm(p[2:] - 2 * p[1:-1] + p[:-2], axis=-1) / height
    a = a[np.isfinite(a)]
    return float(np.median(a)) if len(a) else None


def seen(conf: np.ndarray, idx: list[int], all_of: bool = False) -> float | None:
    c = np.asarray(conf, float)[:, idx]
    if not len(c):
        return None
    ok = (c >= MIN_CONF).all(axis=1) if all_of else (c >= MIN_CONF).mean(axis=1)
    return float(np.mean(ok))


def agreement(a: np.ndarray, b: np.ndarray, height: float, idx: list[int]) -> float | None:
    d = np.linalg.norm(np.asarray(a, float)[:, idx] - np.asarray(b, float)[:, idx], axis=-1) / height
    d = d[np.isfinite(d)]
    return float(np.median(d)) if len(d) and height else None


def _points(rows, k: int) -> np.ndarray:
    """Series rows of points → (n, k, 2), NaN where missing: a flat [x0, y0, x1, y1, …] (the body) or a list of [x, y]
    or None (the feet)."""
    out = np.full((len(rows), k, 2), np.nan)
    for t, r in enumerate(rows):
        if not r:
            continue
        flat = [c for q in r for c in (q if q is not None else (None, None))] if isinstance(r[0], (list, type(None))) else r
        out[t] = np.array([np.nan if v is None else v for v in flat[:2 * k]], float).reshape(k, 2)
    return out


def _confs(rows, k: int) -> np.ndarray:
    out = np.zeros((len(rows), k))
    for t, r in enumerate(rows):
        if r:
            out[t] = [0.0 if v is None else v for v in r[:k]]
    return out


def stroke_inputs(ser: dict) -> dict:
    """The hybrid's view of one stroke from its series: body (n, K, 2) cleaned, its raw confidences, the feet raw (n,
    6, 2) with theirs, the boxes (x1, y1, x2, y2) and the median box height."""
    n = int(ser["n"])
    k = len(ser["kp"][0]) // 2 if ser["kp"] else 17
    body = _points(ser["kp"], k)
    conf = _confs(ser["conf"], k)
    feet = _points(ser["feet"], 6) if ser.get("feet") else np.full((n, 6, 2), np.nan)
    fconf = _confs(ser["feet_conf"], 6) if ser.get("feet_conf") else np.zeros((n, 6))
    boxes = [None if b is None else [float(v) for v in b[:4]] for b in ser["box"]]
    hs = [b[3] - b[1] for b in boxes if b is not None]
    return {"n": n, "body": body[:, :17], "conf": conf[:, :17], "feet": feet, "feet_conf": fconf, "boxes": boxes,
            "height": float(np.median(hs)) if hs else 0.0}


def window_frames(clip: Path, first: int, n: int) -> list[np.ndarray]:
    import cv2
    cap = cv2.VideoCapture(str(clip))
    frames, i = [], 0
    while len(frames) < n:
        ok, f = cap.read()
        if not ok:
            break
        if i >= first:
            frames.append(f)
        i += 1
    cap.release()
    return frames


class Sapiens2:
    """The model on this device in half precision (a T4 has no bfloat16), with its own crop and post-processing.

    medir_sapiens2 (15-11) ran out of the T4's memory with 16 crops at once (attention over 3072 tokens per crop asked
    for 9 GB): batches of 4, and a batch that still does not fit is halved and tried again (down to one crop)."""

    def __init__(self, name: str, device: str = "cuda", batch: int = 4):
        import torch
        from transformers import AutoImageProcessor, Sapiens2ForPoseEstimation
        self.torch, self.batch = torch, batch
        self.dev = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
        self.proc = AutoImageProcessor.from_pretrained(name)
        self.model = Sapiens2ForPoseEstimation.from_pretrained(name).eval().to(self.dev)
        if self.dev == "cuda":
            self.model = self.model.half()
        self.t_model = self.t_all = 0.0
        self.crops = self.nan_batches = self.oom = 0

    def pose(self, frames: list[np.ndarray], boxes: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
        """(len, 308, 2), (len, 308) for each BGR frame and its box (x1, y1, x2, y2)."""
        kps, scs = [], []
        s = 0
        while s < len(frames):
            n = self.batch
            try:
                k, c = self._batch(frames[s:s + n], boxes[s:s + n])
            except Exception as e:  # esperado: out of the GPU's memory: the batch halved and tried again, counted
                if "OutOfMemory" not in type(e).__name__ or n == 1:
                    raise
                self.batch, self.oom = max(1, n // 2), self.oom + 1
                if self.dev == "cuda":
                    self.torch.cuda.empty_cache()
                continue
            kps += k
            scs += c
            s += n
        return np.array(kps), np.array(scs)

    def _batch(self, fr: list[np.ndarray], bx: list[list[float]]) -> tuple[list, list]:
        torch = self.torch
        kps, scs = [], []
        t0 = time.perf_counter()
        xywh = [[[b[0], b[1], b[2] - b[0], b[3] - b[1]]] for b in bx]
        inp = self.proc(images=[f[:, :, ::-1].copy() for f in fr], boxes=xywh, return_tensors="pt")
        x = inp["pixel_values"].to(self.dev)
        if self.dev == "cuda":
            x = x.half()
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        with torch.no_grad():
            out = self.model(pixel_values=x)
            if not torch.isfinite(out.heatmaps).all():          # half precision overflowed: this batch in full
                self.nan_batches += 1
                out = self.model.float()(pixel_values=x.float())
                self.model.half()
        if self.dev == "cuda":
            torch.cuda.synchronize()
        self.t_model += time.perf_counter() - t1
        res = self.proc.post_process_pose_estimation(out, boxes=xywh)
        for r in res:
            kps.append(r[0]["keypoints"].float().cpu().numpy())
            scs.append(r[0]["scores"].float().cpu().numpy())
        self.t_all += time.perf_counter() - t0
        self.crops += len(fr)
        return kps, scs


def compare(series_dir: Path, windows_dir: Path, models: dict, max_strokes: int = 0, log=print) -> dict:
    """Per model: jitter, seen and agreement against the hybrid over her near-side strokes, and the time per crop."""
    from ..kinematics import clean

    files = sorted(series_dir.glob("*_near_*.json"))[: max_strokes or None]
    rows = {name: [] for name in models}
    hyb = []
    for f in files:
        ser = json.loads(f.read_text(encoding="utf-8"))
        wid = f.stem.rsplit("_", 2)[0]
        clips = sorted((p for p in windows_dir.glob(f"{wid}*.mp4") if ".part" not in p.name), key=lambda p: len(p.name))
        if not clips:
            log(f"{f.name}: sin su ventana")
            continue
        s = stroke_inputs(ser)
        frames = window_frames(clips[0], int(ser["first"]), s["n"])
        idx = [t for t in range(min(len(frames), s["n"])) if s["boxes"][t] is not None]
        if len(idx) < 10 or not s["height"]:
            continue
        H = s["height"]
        cur_feet = clean(s["feet"], s["feet_conf"])
        hyb.append({"body": jitter(s["body"], H, BODY), "wrists": jitter(s["body"], H, WRISTS),
                    "feet": jitter(cur_feet, H, list(range(6))), "body_seen": seen(s["conf"][idx], BODY),
                    "feet_seen": seen(s["feet_conf"][idx], list(range(6)), all_of=True)})
        for name, m in models.items():
            kp, sc = m.pose([frames[t] for t in idx], [s["boxes"][t] for t in idx])
            body = np.full((s["n"], 17, 2), np.nan)
            bconf = np.zeros((s["n"], 17))
            feet = np.full((s["n"], 6, 2), np.nan)
            fconf = np.zeros((s["n"], 6))
            for j, t in enumerate(idx):
                body[t], bconf[t], feet[t], fconf[t] = to_hybrid(kp[j], sc[j])
            body_c, feet_c = clean(body, bconf), clean(feet, fconf)
            rows[name].append({"body": jitter(body_c, H, BODY), "wrists": jitter(body_c, H, WRISTS),
                               "feet": jitter(feet_c, H, list(range(6))), "body_seen": seen(bconf[idx], BODY),
                               "feet_seen": seen(fconf[idx], list(range(6)), all_of=True),
                               "agree_body": agreement(body_c, s["body"], H, BODY),
                               "agree_feet": agreement(feet_c, cur_feet, H, list(range(6)))})
        log(f"{f.name}: {len(idx)} fotogramas")
    med = lambda xs, k: (round(float(np.median([x[k] for x in xs if x.get(k) is not None])), 5)  # noqa: E731
                         if any(x.get(k) is not None for x in xs) else None)
    out = {"golpes": len(hyb), "hibrido": {k: med(hyb, k) for k in ("body", "wrists", "feet", "body_seen", "feet_seen")},
           "modelos": {}}
    for name, m in models.items():
        r = {k: med(rows[name], k) for k in ("body", "wrists", "feet", "body_seen", "feet_seen", "agree_body", "agree_feet")}
        r["ms_por_recorte_modelo"] = round(1000 * m.t_model / max(1, m.crops), 1)
        r["ms_por_recorte_total"] = round(1000 * m.t_all / max(1, m.crops), 1)
        r["recortes"], r["lotes_en_precision_completa"] = m.crops, m.nan_batches
        r["lote_final"], r["lotes_partidos_por_memoria"] = m.batch, m.oom
        h = out["hibrido"]
        r["sigue"] = bool(r["body"] is not None and h["body"] and r["body"] <= MARGIN_BODY * h["body"]
                          and (h["feet"] is None or (r["feet"] is not None and r["feet"] <= h["feet"]))
                          and (r["feet_seen"] or 0) >= (h["feet_seen"] or 0))
        out["modelos"][name] = r
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previa", type=Path, required=True, help="la carpeta de salida de la prueba de referencia (v26)")
    ap.add_argument("--modelos", default="facebook/sapiens2-pose-0.4b,facebook/sapiens2-pose-1b")
    ap.add_argument("--dispositivo", default="cuda")
    ap.add_argument("--max-golpes", type=int, default=0)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    sdir = next((p for p in sorted(a.previa.rglob("series")) if p.is_dir()), None)
    wdir = next((p for p in sorted(a.previa.rglob("windows")) if p.is_dir()), None)
    if sdir is None or wdir is None:
        print(f"sin series/ o windows/ en {a.previa}", file=sys.stderr)
        return 1
    import torch
    out = {"prueba": "sapiens2", "dispositivo": a.dispositivo,
           "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    models = {}
    for name in [m for m in a.modelos.split(",") if m]:
        t = time.time()
        models[name] = Sapiens2(name, a.dispositivo)
        print(f"{name}: cargado en {time.time() - t:.0f} s", flush=True)
    out.update(compare(sdir, wdir, models, a.max_golpes, log=lambda s: print(s, flush=True)))
    best = [n for n, r in out["modelos"].items() if r["sigue"]]
    out["conclusion"] = (f"{', '.join(best)} pasa a la prueba integrada (la pasada fina con Sapiens2 frente a la v26)" if best
                         else "ninguno tiembla al menos un 10 % menos en el cuerpo sin empeorar los pies: se queda el híbrido")
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
