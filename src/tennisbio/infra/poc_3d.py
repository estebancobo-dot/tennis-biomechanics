"""Proof of concept #309 (21-11; the user: «sí, haz eso»): the trunk's turn in 3D, the measure the TV's 2D reads worst
(shoulders, hips and X-factor: «media» in CLAUDE.md). MeTRAbs (one calibrated view, the joints in the camera's frame; no
registration, non-commercial licence) against MotionAGFormer xs, in use since 03-11 (58 % of readings within 15° of the
reference against RTMW3D's 13 %), with the PC's own measure (scripts/bench_candidates.py bench_mag3d): CalTennis' two
calibrated synchronised views give the reference by triangulation, each model is read in one view.

Rule written before measuring: MeTRAbs goes on to the integrated test (the fine pass with it, strokes against v36 and GPU
hours) if, on the same frames, its readings within 15° are at least MotionAGFormer's + 0.05 and its X-factor's median
error is not larger, with at least 200 frames of reference; otherwise it is set aside with this measure as the reason.

    python -m tennisbio.infra.poc_3d --datos <dir> --dispositivo cuda --salida poc.json [--pares 3 --tramos 5 --segundos 4]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

MARGIN = 0.05
ROOT = Path(__file__).resolve().parents[3]
IN_USE, CANDIDATE = "mag3d-xs", "metrabs"


def bench():
    spec = importlib.util.spec_from_file_location("bench_candidates", ROOT / "scripts" / "bench_candidates.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def decide(per: dict, min_frames: int = 200) -> dict:
    a, b = per.get(IN_USE) or {}, per.get(CANDIDATE) or {}
    if min(a.get("frames") or 0, b.get("frames") or 0) < min_frames:
        return {"pasa": False, "motivo": f"pocos fotogramas con referencia ({a.get('frames')} / {b.get('frames')})"}
    w_a, w_b = a.get("within_15deg"), b.get("within_15deg")
    x_a, x_b = a.get("xfactor_median_err_deg"), b.get("xfactor_median_err_deg")
    if None in (w_a, w_b, x_a, x_b):
        return {"pasa": False, "motivo": "sin medida en uno de los dos"}
    ok = w_b >= w_a + MARGIN and x_b <= x_a
    return {"pasa": ok, "motivo": f"a ≤ 15°: {w_b} frente a {w_a} (regla ≥ {w_a + MARGIN:.3f}); error del X-factor "
                                  f"{x_b}° frente a {x_a}° (regla: no mayor)"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, required=True)
    ap.add_argument("--dispositivo", default="cuda")
    ap.add_argument("--pares", type=int, default=3)
    ap.add_argument("--tramos", type=int, default=5)
    ap.add_argument("--segundos", type=float, default=4.0)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    from ..config import load_config

    b = bench()
    res = b.bench_mag3d(a.datos, a.dispositivo, load_config(), a.pares, a.tramos, a.segundos,
                        extra={CANDIDATE: b.metrabs_model()}, lifter_names=("mag3d",))
    out = {"prueba": "3d", "dispositivo": a.dispositivo, **res, "regla": decide(res.get("per_model") or {})}
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: out.get(k) for k in ("per_model", "regla", "notes")}, ensure_ascii=False, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
