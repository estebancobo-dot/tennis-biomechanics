"""Equivalence between two runs of the same clip (#288, #289; tasks T4, T9 of the plan): the same code on two
infrastructures (Kaggle and Modal, CPU and GPU), or two codes that should give the same results (a change of where or
how fast a model runs). Standard library only, so the queue runs it in GitHub Actions on the files it reads from the
volume (manifest.json and the strokes files of both runs).

Verdicts:
- «idéntica»: every stage's output has the same content (`out_hash` of the manifest);
- «equivalente»: the same strokes (each one within TIME_TOL_S, with the same kind) and every measure within its
  tolerance (a GPU may round differently from run to run);
- «distinta»: anything else, with what differs.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

TIME_TOL_S = 0.05                 # one frame at 25 fps, two at 50
REL_TOL = 0.01                    # a measure may differ by 1 % of its value …
ABS_TOL = 0.5                     # … or by half a unit (degrees, cm, px), whichever is larger
STROKE_FILES = ("strokes.json", "strokes_opponent.json", "strokes_doubtful.json")


def _leaves(d, prefix=""):
    """Every numeric leaf of a stroke as («path», value); strings, booleans and lists of numbers are compared too."""
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _leaves(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(d, list) and d and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in d):
        for i, v in enumerate(d):
            yield f"{prefix}[{i}]", v
    elif isinstance(d, list):
        yield prefix, json.dumps(d, sort_keys=True, ensure_ascii=False)
    else:
        yield prefix, d


def _close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return a == b
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def _as_list(x) -> list[dict]:
    if isinstance(x, dict):
        x = x.get("strokes") or []
    return [s for s in (x or []) if isinstance(s, dict)]


def compare_strokes(a: list[dict], b: list[dict], skip=("series", "window", "views", "window_impact_s")) -> dict:
    """Strokes matched by time (nearest within TIME_TOL_S); for each pair, the measures outside their tolerance."""
    a, b = _as_list(a), _as_list(b)
    a = sorted(a, key=lambda s: float(s.get("t", 0)))
    b = sorted(b, key=lambda s: float(s.get("t", 0)))
    used, pairs, only_a = set(), [], []
    for s in a:
        best = min(((abs(float(s.get("t", 0)) - float(x.get("t", 0))), j) for j, x in enumerate(b) if j not in used),
                   default=None)
        if best is None or best[0] > TIME_TOL_S:
            only_a.append(round(float(s.get("t", 0)), 2))
            continue
        used.add(best[1])
        pairs.append((s, b[best[1]]))
    only_b = [round(float(x.get("t", 0)), 2) for j, x in enumerate(b) if j not in used]
    kinds = [round(float(s.get("t", 0)), 2) for s, x in pairs if s.get("stroke") != x.get("stroke")]
    diffs: dict[str, int] = {}
    worst: dict[str, float] = {}
    for s, x in pairs:
        la = dict(_leaves({k: v for k, v in s.items() if k not in skip}))
        lb = dict(_leaves({k: v for k, v in x.items() if k not in skip}))
        for k in set(la) | set(lb):
            if k == "t":
                continue
            va, vb = la.get(k), lb.get(k)
            if not _close(va, vb):
                diffs[k] = diffs.get(k, 0) + 1
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool):
                    worst[k] = max(worst.get(k, 0.0), abs(float(va) - float(vb)))
    return {"a": len(a), "b": len(b), "pares": len(pairs), "solo_a": only_a[:20], "solo_b": only_b[:20],
            "tipo_distinto": kinds[:20], "medidas_distintas": dict(sorted(diffs.items(), key=lambda kv: -kv[1])[:20]),
            "mayor_diferencia": {k: round(v, 4) for k, v in sorted(worst.items(), key=lambda kv: -kv[1])[:20]}}


def compare(man_a: dict, man_b: dict, strokes_a: dict[str, list], strokes_b: dict[str, list]) -> dict:
    """Two runs' manifests and strokes files ({file name: strokes}) → stages compared, strokes compared, verdict."""
    stages = sorted(k for k in set(man_a) | set(man_b) if isinstance(man_a.get(k), dict) or isinstance(man_b.get(k), dict))
    same, differ, missing = [], [], []
    for k in stages:
        ha, hb = (man_a.get(k) or {}).get("out_hash"), (man_b.get(k) or {}).get("out_hash")
        if ha is None or hb is None:
            missing.append(k)
        elif ha == hb:
            same.append(k)
        else:
            differ.append(k)
    files = {f: compare_strokes(strokes_a.get(f) or [], strokes_b.get(f) or [])
             for f in STROKE_FILES if f in strokes_a or f in strokes_b}
    strokes_ok = all(not c["solo_a"] and not c["solo_b"] and not c["tipo_distinto"] and not c["medidas_distintas"]
                     for c in files.values())
    if not differ and not missing and same:
        verdict = "idéntica"
    elif strokes_ok and files:
        verdict = "equivalente"
    else:
        verdict = "distinta"
    return {"veredicto": verdict, "etapas_iguales": same, "etapas_distintas": differ, "etapas_sin_comparar": missing,
            "golpes": files}


def summary(c: dict) -> str:
    """One line for the queue's summary."""
    parts = [c["veredicto"], f"{len(c['etapas_iguales'])} etapas iguales"]
    if c["etapas_distintas"]:
        parts.append("distintas: " + ", ".join(c["etapas_distintas"][:8]))
    for f, g in c["golpes"].items():
        bad = len(g["solo_a"]) + len(g["solo_b"]) + len(g["tipo_distinto"])
        parts.append(f"{f}: {g['pares']} de {g['a']}/{g['b']} golpes emparejados"
                     + (f", {bad} distintos" if bad else "")
                     + (f", medidas fuera de tolerancia: {', '.join(list(g['medidas_distintas'])[:4])}"
                        if g["medidas_distintas"] else ""))
    return "; ".join(parts)


def compare_dirs(a: Path, b: Path) -> dict:
    """The same for two output folders on this machine."""
    def load(d: Path, name: str):
        f = d / name
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    sa = {f: load(a, f) for f in STROKE_FILES if (a / f).exists()}
    sb = {f: load(b, f) for f in STROKE_FILES if (b / f).exists()}
    return compare(load(a, "manifest.json") or {}, load(b, "manifest.json") or {}, sa, sb)


if __name__ == "__main__":
    import sys

    res = compare_dirs(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print(summary(res))
