"""F3Set validation on Kaggle (21-11; native cloud's closure, #295): the strokes F3Set annotates in the player's matches
found by today's whole analysis, with everything adopted in the cloud (the ball decoding in a thread, the scoreboard on
CUDA, the far player by RF-DETR…), against the cloud's reference run (nube2, 14-11 on Modal: 469 of 517, precision
0.94), with the same script as Modal's (scripts/validate_recall.py --spotter).

Rule written before measuring: today's code is accepted if it is not worse than the reference by more than what a
different device can move (cloud/nube.py: MAX_FOUND_DIFF 2 strokes found, MAX_PRECISION_DIFF 0.005 of precision);
better is said as better. Its time per stage is recorded for the cost of a match.

    python -m tennisbio.infra.poc_f3set --raiz <datasets> --referencia <report.json> --tag kaggle_f3 --salida poc.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX_FOUND_DIFF = 2            # cloud/nube.py (tests/test_poc_f3set.py keeps them equal)
MAX_PRECISION_DIFF = 0.005
TIMEOUT_S = 10 * 3600


def totals(rep: dict) -> dict:
    """The report's totals, as cloud/nube.py _totals reads them."""
    sm = rep.get("summary") or {}
    tot, pre = sm.get("total") or {}, sm.get("precision") or {}
    dts = [abs(float(s["dt"])) for s in rep.get("strokes", []) if s.get("dt") is not None]
    return {"found": tot.get("found"), "gt": tot.get("gt"), "recall": tot.get("recall"),
            "precision": pre.get("precision"), "false": len(sm.get("false") or []),
            "dt_median_s": round(statistics.median(dts), 3) if dts else None, "minutes": rep.get("minutes")}


def decide(ref: dict, new: dict) -> dict:
    a, b = totals(ref), totals(new)
    if None in (a["found"], b["found"], a["precision"], b["precision"]):
        return {"pasa": False, "motivo": "sin totales en uno de los dos informes", "referencia": a, "hoy": b}
    df, dp = b["found"] - a["found"], round(b["precision"] - a["precision"], 4)
    ok = df >= -MAX_FOUND_DIFF and dp >= -MAX_PRECISION_DIFF
    how = "mejor" if (df > MAX_FOUND_DIFF or dp > MAX_PRECISION_DIFF) and ok else "igual" if ok else "peor"
    return {"pasa": ok, "resultado": how, "motivo": f"encontrados {b['found']} frente a {a['found']} ({df:+d}), precisión "
            f"{b['precision']} frente a {a['precision']} ({dp:+.4f})", "referencia": a, "hoy": b}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=Path, required=True, help="la carpeta de los datos anotados (con f3set/)")
    ap.add_argument("--referencia", type=Path, required=True, help="el informe de referencia (nube2)")
    ap.add_argument("--tag", default="kaggle_f3")
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    t0 = time.time()
    try:                                         # under a Kaggle session's 12 h, with the upload after it
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_recall.py"), "--root", str(a.raiz),
                             "--spotter", "--tag", a.tag], cwd=ROOT, timeout=TIMEOUT_S).returncode
    except subprocess.TimeoutExpired:  # esperado: said in the result, as a validation that did not end
        rc = -1
    rep_f = a.raiz / "reports" / "recall_validation_detector.json"
    tagged = a.raiz / "reports" / f"recall_validation_detector_{a.tag}.json"
    rep_f = tagged if tagged.exists() else rep_f
    out = {"prueba": "f3set", "codigo": rc, "horas": round((time.time() - t0) / 3600, 2), "informe": rep_f.name}
    if rc == 0 and rep_f.exists() and a.referencia.exists():
        out["regla"] = decide(json.loads(a.referencia.read_text(encoding="utf-8")),
                              json.loads(rep_f.read_text(encoding="utf-8")))
    else:
        out["regla"] = {"pasa": False, "motivo": f"la validación no terminó (código {rc}) o falta un informe"}
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:2000])
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
