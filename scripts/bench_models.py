"""The fine pass's models still in full precision (29-10, B-4): the 3D whole body (RTMW3D, «cuerdas y 3D») and the
racket keypoints (RacketPose), fp32 against fp16 on the iGPU. The test from scratch showed the iGPU is what limits
the first pass (two processes each went half as fast), so the lever is less work per frame, not more processes.
For each model: frames per second and how far fp16's points are from fp32's, on real frames of analysed windows.

    uv run python scripts/bench_models.py [--frames 120]

Writes <output>/bench_models.json and prints it.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def frames_and_boxes(cfg, n: int):
    """n frames of the first analysed windows with the tallest person's box (the pose model of the cheap pass)."""
    from tennisbio import layout
    from tennisbio import match_files as mf
    from tennisbio.catalog import load_matches
    from tennisbio.io.video import probe, read_frames
    from tennisbio.pose.backend import pose_model

    out = Path(cfg["paths"]["output"])
    pm = pose_model("yolo11m-pose", 960, cfg.get("device", "cpu"))
    got = []
    for m in load_matches(cfg):
        wdir = mf.at(layout.dir_of(out, m, cfg), "windows")
        for clip in sorted(wdir.glob("w*.mp4")) if wdir.exists() else []:
            for k, fr in enumerate(read_frames(probe(clip))):
                if k % 5:
                    continue
                b, _, _ = pm.predict(fr, conf=0.3)
                if len(b):
                    box = b[np.argmax((b[:, 3] - b[:, 1]))]
                    got.append((fr, box))
                if len(got) >= n:
                    return got
    return got


def timed(fn, items, warm=3):
    for f, b in items[:warm]:
        fn(f, b)
    t0 = time.time()
    res = [fn(f, b) for f, b in items]
    return res, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=120)
    a = ap.parse_args()
    from tennisbio.config import load_config, resolve_path
    from tennisbio.pose.estimator import _ort_session
    from tennisbio.pose.variants import to_fp16

    cfg = load_config()
    dev = cfg.get("device", "cpu")
    items = frames_and_boxes(cfg, a.frames)
    res = {"device": dev, "frames": len(items)}
    if not items:
        print("No hay ventanas analizadas con personas")
        return 1
    rf = cfg.get("racket_face") or {}
    hp, rp = resolve_path(rf.get("hand3d_onnx")), resolve_path(rf.get("pose_onnx"))
    if hp is not None and hp.exists():
        from tennisbio.pose.wholebody3d import WholeBody3D
        m = WholeBody3D(str(hp), dev)
        r32, t32 = timed(lambda f, b: m(f, b), items)
        m.model.session = _ort_session(str(to_fp16(m.model.onnx_model)), dev)
        r16, t16 = timed(lambda f, b: m(f, b), items)
        k32, k16 = np.stack([r[0] for r in r32]), np.stack([r[0] for r in r16])
        res["rtmw3d"] = {"fp32_fps": round(len(items) / t32, 1), "fp16_fps": round(len(items) / t16, 1),
                         "xy_px_median": round(float(np.median(np.linalg.norm(k32[..., :2] - k16[..., :2], axis=-1))), 2),
                         "xy_px_p95": round(float(np.percentile(np.linalg.norm(k32[..., :2] - k16[..., :2], axis=-1), 95)), 2),
                         "depth_m_p95": round(float(np.percentile(np.abs(k32[..., 2] - k16[..., 2]), 95)), 4)}
        print("rtmw3d", res["rtmw3d"], flush=True)
    if rp is not None and rp.exists():
        from tennisbio.racket_pose import RacketPose
        r = RacketPose(str(rp), dev)
        many = lambda: r.many([(f, b) for f, b in items])
        r.many([(f, b) for f, b in items[:4]])
        t0 = time.time(); k32, _ = many(); t32 = time.time() - t0
        r.sess = _ort_session(str(to_fp16(rp)), dev)
        r.many([(f, b) for f, b in items[:4]])
        t0 = time.time(); k16, _ = many(); t16 = time.time() - t0
        d = np.linalg.norm(k32 - k16, axis=-1)
        res["racketpose"] = {"fp32_fps": round(len(items) / t32, 1), "fp16_fps": round(len(items) / t16, 1),
                             "px_median": round(float(np.median(d)), 2), "px_p95": round(float(np.percentile(d, 95)), 2)}
        print("racketpose", res["racketpose"], flush=True)
    dest = Path(cfg["paths"]["output"]) / "bench_models.json"
    dest.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
