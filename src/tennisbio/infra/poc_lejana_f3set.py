"""Proof of concept (22-11, #312 point 3): does RF-DETR find the far player in F3Set's broadcasts? F3Set today
(medir_f3set_hoy_d) found 466 annotated strokes against 471 of the reference (nube2, 14-11): 8 lost and 3 gained on the
far side, 2 and 2 on the near side; 2 lost as «far player not found». The one far-side change since the reference is
RF-DETR as the far player's detector (fine_pass.far_detector, adopted 21-11 on 300 RacketVision US Open frames); F3Set's
compilations are other, older broadcasts (Dubai 2020, Australian Open 2023).

The measure: at each far stroke F3Set annotates (the far player hits: she is there), the frame 0.3 s before and the
contact frame, the fine pass's own far search (pose.yolo.far_people with each detector, then court_metrics.
pick_far_player with the frame's court) — does it find her?

Rule written before measuring: RF-DETR stays if it finds her in at least YOLO's share − 0.02 of those frames; else the
far player goes back to YOLO (fine_pass.far_detector: yolo) before the next matches' GPU parts.

    python -m tennisbio.infra.poc_lejana_f3set --raiz <datasets> --referencia <report.json> --salida poc.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

MARGIN = 0.02
BEFORE_S = 0.3


def far_strokes(report: dict, limit: int) -> list[dict]:
    """The far strokes F3Set annotates (side «far»), spread evenly over the compilations, up to `limit`."""
    rows = [s for s in report.get("strokes") or [] if s.get("side") == "far" and s.get("t_clip") is not None]
    step = max(1, len(rows) // max(1, limit))
    return rows[::step][:limit]


def decide(per: dict) -> dict:
    y, r = (per.get("yolo") or {}).get("share"), (per.get("rfdetr") or {}).get("share")
    if y is None or r is None:
        return {"pasa": False, "motivo": "sin medida"}
    ok = r >= y - MARGIN
    return {"pasa": ok, "resultado": "se queda RF-DETR" if ok else "vuelve YOLO",
            "motivo": f"jugadora lejana hallada: RF-DETR {r} frente a YOLO {y} (regla: RF-DETR ≥ {y - MARGIN:.3f})"}


def measure(root: Path, rows: list[dict]) -> dict:
    import cv2
    import numpy as np

    from ..court import fit_court
    from ..court_metrics import pick_far_player
    from ..pose import yolo

    caps: dict = {}
    found = {"yolo": [], "rfdetr": []}
    secs = {"yolo": 0.0, "rfdetr": 0.0}
    by_match: dict = {}
    frames = 0
    for s in rows:
        m = s["match"]
        cap = caps.get(m) or cv2.VideoCapture(str(root / "f3set" / "recall" / "videos" / f"{m}.mp4"))
        caps[m] = cap
        for dt in (-BEFORE_S, 0.0):
            cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * max(0.0, float(s["t_clip"]) + dt))
            ok, frame = cap.read()
            if not ok:
                continue
            fit = fit_court(frame)
            if fit is None:
                continue
            frames += 1
            for name in found:
                yolo._far_name.cache_clear()
                orig = yolo._far_name
                yolo._far_name = lambda n=name: n           # the fine pass's own search, with this detector
                try:
                    t0 = time.time()
                    box = pick_far_player(np.asarray(yolo.far_people(frame, fit.H)), fit.H)
                    secs[name] += time.time() - t0
                finally:
                    yolo._far_name = orig
                hit = box is not None
                found[name].append(hit)
                by_match.setdefault(m, {"yolo": [], "rfdetr": []})[name].append(hit)
    per = {k: {"share": round(float(np.mean(v)), 3) if v else None, "frames": len(v),
               "s_per_frame": round(secs[k] / len(v), 3) if v else None} for k, v in found.items()}
    return {"strokes": len(rows), "frames": frames, "per_model": per,
            "per_match": {m: {k: round(float(np.mean(v)), 3) if v else None for k, v in d.items()} for m, d in by_match.items()}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=Path, required=True)
    ap.add_argument("--referencia", type=Path, required=True)
    ap.add_argument("--golpes", type=int, default=240)
    ap.add_argument("--dispositivo", default="cuda")
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    from ..pose.backend import set_device
    set_device(a.dispositivo)
    rows = far_strokes(json.loads(a.referencia.read_text(encoding="utf-8")), a.golpes)
    res = measure(a.raiz, rows)
    out = {"prueba": "lejana_f3set", **res, "regla": decide(res["per_model"])}
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
