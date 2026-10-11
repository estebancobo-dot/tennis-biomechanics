"""Fase 0: mide en este equipo la velocidad real de decodificación, detección y pose.

Uso:
    uv run python scripts/benchmark.py "C:\\tenis\\videos\\partido1.mp4" --start 1800

--start debe caer en un punto con la cámara principal (no en descanso ni repetición).
Guarda en <output>/benchmark/: results.json y fotogramas con el esqueleto dibujado.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rtmlib import draw_bbox, draw_skeleton  # noqa: E402

from tennisbio.config import load_config  # noqa: E402
from tennisbio.io.video import probe, read_frames  # noqa: E402
from tennisbio.pose.estimator import Detector, PoseEstimator  # noqa: E402
from tennisbio.render import draw_pose  # noqa: E402
from tennisbio.skeleton import Skeleton  # noqa: E402

WARMUP = 3


def time_decode(info, start, seconds, **kwargs):
    t0 = time.perf_counter()
    n = sum(1 for _ in read_frames(info, start=start, duration=seconds, **kwargs))
    elapsed = time.perf_counter() - t0
    return {"frames": n, "fps": n / elapsed, "realtime_x": seconds / elapsed}


def time_calls(fn, inputs):
    for x in inputs[:WARMUP]:
        fn(x)
    t0 = time.perf_counter()
    for x in inputs:
        fn(x)
    return (time.perf_counter() - t0) / len(inputs) * 1000


def largest(boxes, k=2):
    if len(boxes) == 0:
        return boxes
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return boxes[np.argsort(area)[::-1][:k]]


def bench_yolo(specs, devices, frames, out):
    """Export each YOLO model to ONNX once and time it on every device. Needs the 'yolo' extra to export."""
    from tennisbio.pose.yolo_onnx import YoloOnnx, export_onnx, letterbox

    res = {}
    if not specs:
        return res
    print("\n== YOLO (ONNX) ==")
    sk = Skeleton("coco17", "right")
    for spec in specs:
        name, size = spec.split(":")
        try:
            path = export_onnx(name, int(size))
        except Exception as e:
            print(f"  {spec}: no se pudo exportar ({e}). ¿Falta `uv sync --extra yolo`?")
            res[spec] = {"error": str(e)}
            continue
        for device in devices:
            key = f"{spec}@{device}"
            try:
                model = YoloOnnx(path, device)
            except Exception as e:
                print(f"  {key:28} no disponible: {e}")
                res[key] = {"error": str(e)}
                continue
            if "pose" in name:
                ms = time_calls(model.pose, frames)
                boxes, _, kps, kc = model.pose(frames[len(frames) // 2])
                res[key] = {"ms": ms, "persons": int(len(boxes))}
                img = frames[len(frames) // 2].copy()
                for k, c in zip(kps, kc):
                    draw_pose(img, np.where(c[:, None] > 0.3, k, np.nan), sk)
                cv2.imwrite(str(out / f"yolo_{name}_{size}_{device}.jpg"), img)
            else:
                ms = time_calls(lambda f: model.infer(letterbox(f, model.size)[0]), frames)
                res[key] = {"ms": ms}
            print(f"  {key:28} {ms:8.1f} ms/fotograma")
    return res


def bench_extra(devices, frames) -> dict:
    """ms por llamada de: bola (lote de 8 fotogramas a 25 fps), raqueta 5 puntos, OCR del marcador."""
    from tennisbio.ball import BallTracker
    from tennisbio.racket_pose import RacketPose

    models = Path(__file__).resolve().parents[1] / "models"
    out = {}
    for device in devices:
        r = {}
        try:
            if (models / "balltrack.onnx").exists():
                bt = BallTracker(models / "balltrack.onnx", device)
                t0 = time.perf_counter()
                bt.track(frames[:24])
                r["ball_ms_per_frame"] = (time.perf_counter() - t0) * 1000 / len(frames[:24])
            if (models / "racketpose.onnx").exists():
                rp = RacketPose(models / "racketpose.onnx", device)
                h, w = frames[0].shape[:2]
                box = [[w * .45, h * .55, w * .55, h * .7]]
                r["racket_pose_ms"] = time_calls(lambda f: rp(f, box), frames[:20])
        except Exception as e:
            r["error"] = str(e)
        out[device] = r
        for k, v in r.items():
            print(f"  [{device}] {k:24} {v:8.1f}" if isinstance(v, float) else f"  [{device}] {k}: {v}")
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        h, w = frames[0].shape[:2]
        out["ocr_roi_ms"] = time_calls(lambda f: ocr(f[int(h * .75):, :w // 2]), frames[:5])
        print(f"  OCR (zona del marcador)     {out['ocr_roi_ms']:8.1f} ms")
    except ImportError:
        out["ocr_roi_ms"] = None
    return out


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=1800, help="segundo de inicio de la muestra")
    ap.add_argument("--seconds", type=float, default=20, help="duración de la muestra para decodificar")
    ap.add_argument("--frames", type=int, default=40, help="fotogramas para medir los modelos")
    ap.add_argument("--devices", nargs="+", default=["dml", "cpu"], help="dml, cpu, openvino")
    ap.add_argument("--strokes", type=int, default=400, help="golpes estimados de la jugadora por partido")
    ap.add_argument("--yolo", nargs="*", default=["yolo11m-pose:640", "yolo11m-pose:960", "yolo11m-seg:960"],
                    help="modelos YOLO a medir como nombre:tamaño (vacío para omitir)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = Path(args.out or Path(cfg.get("paths", {}).get("output", "output")) / "benchmark")
    out.mkdir(parents=True, exist_ok=True)
    info = probe(args.video)
    print(f"Vídeo: {info.width}x{info.height} @ {info.fps:.3f} fps, {info.codec}, "
          f"{'entrelazado' if info.interlaced else 'progresivo'}, {info.duration / 60:.0f} min")
    results = {"video": {k: str(v) if isinstance(v, Path) else v for k, v in vars(info).items()}}

    # 1. Decodificación
    cheap = cfg["cheap_pass"]
    decode = {
        "full": time_decode(info, args.start, args.seconds),
        "cheap": time_decode(info, args.start, args.seconds, width=cheap["width"], fps=cheap["fps"]),
    }
    if sys.platform == "win32":
        try:
            decode["full_d3d11va"] = time_decode(info, args.start, args.seconds, hwaccel="d3d11va")
        except RuntimeError as e:
            decode["full_d3d11va"] = {"error": str(e)}
    results["decode"] = decode
    for k, v in decode.items():
        print(f"Decodificar {k:13}: " + (f"{v['fps']:6.1f} fps  ({v['realtime_x']:.1f}x tiempo real)"
                                          if "fps" in v else v["error"]))

    # 2. Fotogramas de muestra, repartidos por el intervalo
    step = max(1, int(info.fps * args.seconds / args.frames))
    full = [f.copy() for i, f in enumerate(read_frames(info, args.start, args.seconds)) if i % step == 0][:args.frames]
    small = [cv2.resize(f, (cheap["width"], round(f.shape[0] * cheap["width"] / f.shape[1]))) for f in full]

    # 3. Modelos en cada dispositivo
    det_cfg, pose_cfg = cfg["models"]["detectors"], cfg["models"]["poses"]
    results["models"] = {}
    for device in args.devices:
        print(f"\n== {device} ==")
        try:
            det_light = Detector(det_cfg["lightweight"]["url"], det_cfg["lightweight"]["input_size"], device)
            det_bal = Detector(det_cfg["balanced"]["url"], det_cfg["balanced"]["input_size"], device)
            poses = {name: PoseEstimator(c["url"], c["input_size"], device) for name, c in pose_cfg.items()}
        except Exception as e:  # provider ausente, modelo no descargado...
            print(f"  no disponible: {e}")
            results["models"][device] = {"error": str(e)}
            continue

        r = {
            "det_lightweight_small_ms": time_calls(det_light, small),
            "det_balanced_full_ms": time_calls(det_bal, full),
        }
        boxes = [largest(det_bal(f)) for f in full]
        r["persons_per_frame"] = float(np.mean([len(b) for b in boxes]))
        crops = [(f, b[:1]) for f, b in zip(full, boxes) if len(b)]
        for name, pose in poses.items():
            r[f"pose_{name}_ms_per_person"] = time_calls(lambda fb: pose(*fb), crops) if crops else None
        results["models"][device] = r
        for k, v in r.items():
            print(f"  {k:32} {v:8.1f}" if v is not None else f"  {k:32} -")

        # Fotogramas de control con el esqueleto (modelo de máxima calidad)
        for i in (0, len(full) // 2, len(full) - 1):
            kpts, scores = poses["performance"](full[i], boxes[i])
            img = draw_bbox(full[i].copy(), boxes[i])
            img = draw_skeleton(img, kpts, scores, kpt_thr=0.3)
            cv2.imwrite(str(out / f"skeleton_{device}_{i:03d}.jpg"), img)

    # 3b. YOLO exportado a ONNX (personas + pose en una sola pasada; seg = silueta de la raqueta)
    results["yolo"] = bench_yolo(args.yolo, args.devices, full, out)

    # 3c. Bola, raqueta de 5 puntos y marcador (si los modelos están en models/: setup_models.py)
    results["extra"] = bench_extra(args.devices, full)

    # 4. Proyección por partido con el mejor dispositivo
    ok = {d: r for d, r in results["models"].items() if "error" not in r and r["pose_performance_ms_per_person"]}
    yolo_ok = {k: v for k, v in results["yolo"].items() if "ms" in v and ":" in k and "pose" in k}
    if yolo_ok:
        k, v = min(yolo_ok.items(), key=lambda kv: kv[1]["ms"])
        fine_frames = args.strokes * 2 * cfg["fine_pass"]["window_s"] * info.fps * (2 if info.interlaced else 1)
        results["projection_yolo"] = {"model_device": k, "fine_pass_min": fine_frames * v["ms"] / 1000 / 60}
        print(f"\nProyección YOLO ({k}): pasada fina ({args.strokes} golpes) ≈ {fine_frames * v['ms'] / 1000 / 60:.0f} min")
    if ok:
        best = min(ok, key=lambda d: ok[d]["det_balanced_full_ms"] + ok[d]["pose_performance_ms_per_person"])
        r = ok[best]
        n_cheap = info.duration * cheap["fps"]
        cheap_s = info.duration / decode["cheap"]["realtime_x"] + n_cheap * r["det_lightweight_small_ms"] / 1000
        fine_frames = args.strokes * 2 * cfg["fine_pass"]["window_s"] * info.fps * (2 if info.interlaced else 1)
        fine_s = fine_frames * (r["det_balanced_full_ms"] + r["pose_performance_ms_per_person"]) / 1000
        results["projection"] = {"device": best, "cheap_pass_min": cheap_s / 60, "fine_pass_min": fine_s / 60}
        print(f"\nProyección por partido ({best}): pasada barata ≈ {cheap_s / 60:.0f} min, "
              f"pasada fina ({args.strokes} golpes) ≈ {fine_s / 60:.0f} min")

    (out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResultados en {out}")


if __name__ == "__main__":
    main()
