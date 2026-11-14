"""Proof of concept T7 (docs/nube_nativa.md, #288): decoding the fine pass's windows on the CPU (today, in the cloud)
against the GPU's decoder (NVDEC, ffmpeg's «-hwaccel cuda»), with the analysis's own reader
(tennisbio.io.video.read_frames: full resolution, deinterlaced when the broadcast is interlaced). The same windows for
both; for each option the wall time, the CPU seconds ffmpeg used (what the decoder takes away from the rest of the
work) and, frame by frame, how far its pictures are from the CPU's (mean and largest pixel difference, share of
pixels more than 2 levels apart). Read only: it changes nothing of the analysis.

    python -m tennisbio.infra.poc_video --video partido.mp4 --salida poc.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np

OPTIONS = {"cpu": None, "nvdec": "cuda"}


def _child_cpu_s() -> float:
    try:
        import resource

        r = resource.getrusage(resource.RUSAGE_CHILDREN)
        return r.ru_utime + r.ru_stime
    except (ImportError, OSError):  # esperado: no resource module (Windows): CPU seconds not measured
        return float("nan")


def window_times(duration: float, n: int, dur: float) -> list[float]:
    """n window starts spread over the video, away from its first and last minute (titles, closing)."""
    lo, hi = min(60.0, duration * 0.1), max(duration - 60.0 - dur, duration * 0.9 - dur)
    if hi <= lo:
        return [max(0.0, duration / 2 - dur / 2)]
    return [round(lo + (hi - lo) * (i + 0.5) / n, 2) for i in range(n)]


def frame_diff(a: np.ndarray, b: np.ndarray) -> tuple[float, int, float]:
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float(d.mean()), int(d.max()), float((d > 2).mean())


def run(video: str, n: int = 8, dur: float = 2.0) -> dict:
    from ..io.video import probe, read_frames

    info = probe(video)
    hw = subprocess.run(["ffmpeg", "-hide_banner", "-hwaccels"], capture_output=True, text=True, timeout=60).stdout.split()
    out = {"video": Path(video).name, "ancho": info.width, "alto": info.height, "fps": info.fps,
           "entrelazado": bool(info.interlaced), "aceleradores_ffmpeg": [h for h in hw if h.islower()],
           "nucleos": os.cpu_count(), "ventanas": [], "opciones": {k: {"s": 0.0, "cpu_s": 0.0, "fotogramas": 0}
                                                                 for k in OPTIONS}}
    diffs: list[tuple[float, int, float]] = []
    for t in window_times(float(info.duration or 0.0), n, dur):
        got = {}
        for name, hwaccel in OPTIONS.items():
            c0, t0 = _child_cpu_s(), time.perf_counter()
            try:
                frames = list(read_frames(info, start=t, duration=dur, hwaccel=hwaccel))
            except Exception as e:  # esperado: an option this machine cannot run is reported, the others go on  # noqa: BLE001
                out["opciones"][name]["error"] = f"{type(e).__name__}: {str(e)[:300]}"
                frames = []
            o = out["opciones"][name]
            o["s"] += time.perf_counter() - t0
            o["cpu_s"] += _child_cpu_s() - c0
            o["fotogramas"] += len(frames)
            got[name] = frames
        k = min(len(got["cpu"]), len(got["nvdec"]))
        w = [frame_diff(got["cpu"][i], got["nvdec"][i]) for i in range(k)]
        diffs += w
        out["ventanas"].append({"t": t, "cpu": len(got["cpu"]), "nvdec": len(got["nvdec"]),
                                "dif_media": round(float(np.mean([x[0] for x in w])), 3) if w else None})
    for o in out["opciones"].values():
        o["ms_por_fotograma"] = round(1000 * o["s"] / o["fotogramas"], 2) if o["fotogramas"] else None
        o["cpu_ms_por_fotograma"] = round(1000 * o["cpu_s"] / o["fotogramas"], 2) if o["fotogramas"] else None
        o["s"], o["cpu_s"] = round(o["s"], 2), round(o["cpu_s"], 2)
    if diffs:
        out["diferencia"] = {"media": round(float(np.mean([d[0] for d in diffs])), 3),
                             "max": int(max(d[1] for d in diffs)),
                             "pixeles_mas_de_2": round(float(np.mean([d[2] for d in diffs])), 5),
                             "fotogramas_comparados": len(diffs)}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--ventanas", type=int, default=8)
    ap.add_argument("--duracion", type=float, default=2.0)
    a = ap.parse_args(argv)
    res = run(a.video, a.ventanas, a.duracion)
    Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
