"""Proof of concept T25 (21-11): RF-DETR Medium (Apache 2.0; scripts/export_rfdetr.py) for the far player, against
what runs today (YOLO11m-pose on the far half of the court), on a T4.

Measured on the PC on 07-11 (scripts/bench_candidates.py «rfdetr», pc-logs:bench_candidates.md): on 300 RacketVision
test frames it found the far player in 100 % of them against YOLO's 90.3 %, but at 0.5 frames/s against 1.3 on the
iGPU, so it was set aside for the PC's time (B in docs/registro_decisiones.md). Here the PC's own measure
(bench_candidates.bench_far: the far player's annotated racket inside a person box, with half a box of margin) on the
cloud's GPU, so its quality is checked again and its cost is known.

Rule written before measuring: RF-DETR goes on to the integrated test (the cheap pass's far search with it, strokes
against v26 and GPU hours) if, on the same frames, it finds the far player in at least YOLO's share + 0.05; otherwise
it is set aside with this measure as the reason. Its frames/s on the T4 are recorded for the cost per match.

    python -m tennisbio.infra.poc_lejana --datos /tmp/datasets --dispositivo cuda --salida poc.json [--imagenes 300]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

MARGIN = 0.05
ROOT = Path(__file__).resolve().parents[3]


def bench():
    """The PC's candidate bench (a script, not a package module), loaded by its path."""
    spec = importlib.util.spec_from_file_location("bench_candidates", ROOT / "scripts" / "bench_candidates.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def decide(res: dict) -> dict:
    per = res.get("per_model") or {}
    base = (per.get("ours (YOLO11m-pose, mitad lejana)") or {}).get("far_found")
    cand = (per.get("rfdetr") or {}).get("far_found")
    if base is None or cand is None:
        return {"pasa": False, "motivo": "sin medida"}
    ok = cand >= base + MARGIN
    return {"pasa": ok, "motivo": f"lejana hallada {cand} frente a {base} (regla: ≥ {base + MARGIN:.3f})"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, default=Path("/tmp/datasets"))
    ap.add_argument("--dispositivo", default="cuda")
    ap.add_argument("--imagenes", type=int, default=300)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    res = bench().bench_far(a.datos, a.dispositivo, a.imagenes)
    out = {"prueba": "lejana", "dispositivo": a.dispositivo, "imagenes": a.imagenes, **res, "regla": decide(res)}
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
