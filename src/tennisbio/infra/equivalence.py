"""Equivalence between two runs of the same clip (#288, #289; tasks T4, T9 of the plan): the same code on two
infrastructures (Kaggle and Modal, CPU and GPU), or two codes that should give the same results (a change of where or
how fast a model runs). Standard library only, so the queue runs it in GitHub Actions on the files it reads from the
volume (manifest.json and the strokes files of both runs).

Verdicts:
- «idéntica»: every stage's output has the same content (`out_hash` of the manifest);
- «equivalente»: the same strokes (each one within TIME_TOL_S, with the same kind) and every measure within its
  tolerance (a GPU may round differently from run to run);
- «distinta»: anything else, with what differs;
- «incompleta»: a strokes file could be read on one side only (14-11: the first comparison said «idéntica» with the
  new run's strokes.json unread).
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

TIME_TOL_S = 0.05                 # one frame at 25 fps, two at 50
REL_TOL = 0.01                    # a measure may differ by 1 % of its value …
ABS_TOL = 0.5                     # … or by half a unit (degrees, cm, px), whichever is larger
STROKE_FILES = ("strokes.json", "strokes_opponent.json", "strokes_doubtful.json")
TIME_KEYS = ("match_time_s", "t")         # 14-11: a stroke's time in the match is «match_time_s» (views.stroke_key)


def stroke_time(s: dict) -> float:
    for k in TIME_KEYS:
        if s.get(k) is not None:
            return float(s[k])
    return float("nan")


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


ANGLE_HINTS = ("_deg", "yaw", "tilt", "angle", "turn", "x_factor")
JUMP_DEG = 90.0                  # an angle that changes more than this between two runs has jumped (R50)


def is_angle(key: str) -> bool:
    """A measure in degrees, compared on the circle (R50, 15-11: a stance angle of 340° against 29° is 49° apart, not
    311°)."""
    k = key.lower()
    return any(h in k for h in ANGLE_HINTS)


def _diff(a: float, b: float, key: str = "") -> float:
    d = abs(a - b)
    return min(d, 360.0 - d % 360.0) if is_angle(key) and d > 180.0 else d


def _close(a, b, key: str = "") -> bool:
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return a == b
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return _diff(a, b, key) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def _as_list(x) -> list[dict]:
    if isinstance(x, dict):
        x = x.get("strokes") or []
    return [s for s in (x or []) if isinstance(s, dict)]


def compare_strokes(a: list[dict], b: list[dict], skip=("series", "window", "views", "window_impact_s")) -> dict:
    """Strokes matched by time (nearest within TIME_TOL_S); for each pair, the measures outside their tolerance."""
    a, b = _as_list(a), _as_list(b)
    a = sorted(a, key=lambda s: stroke_time(s))
    b = sorted(b, key=lambda s: stroke_time(s))
    used, pairs, only_a = set(), [], []
    for s in a:
        best = min(((abs(stroke_time(s) - stroke_time(x)), j) for j, x in enumerate(b) if j not in used),
                   default=None)
        if best is None or best[0] > TIME_TOL_S:
            only_a.append(round(stroke_time(s), 2))
            continue
        used.add(best[1])
        pairs.append((s, b[best[1]]))
    only_b = [round(stroke_time(x), 2) for j, x in enumerate(b) if j not in used]
    kinds = [round(stroke_time(s), 2) for s, x in pairs if s.get("stroke") != x.get("stroke")]
    diffs: dict[str, int] = {}
    worst: dict[str, float] = {}
    jumps: list = []
    shake: list[tuple[float, float]] = []
    by_family: dict[str, list[tuple[float, float]]] = {}
    for s, x in pairs:
        la = dict(_leaves({k: v for k, v in s.items() if k not in skip}))
        lb = dict(_leaves({k: v for k, v in x.items() if k not in skip}))
        for k, va, vb in _shake_items(la, lb):
            shake.append((va, vb))
            by_family.setdefault(shake_family(k), []).append((va, vb))
        for k in set(la) | set(lb):
            if k in TIME_KEYS:
                continue
            va, vb = la.get(k), lb.get(k)
            if not _close(va, vb, k):
                diffs[k] = diffs.get(k, 0) + 1
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool):
                    worst[k] = max(worst.get(k, 0.0), _diff(float(va), float(vb), k))
                    if is_angle(k) and _diff(float(va), float(vb), k) > JUMP_DEG:
                        # R50: an angle that jumps, with the «ambiguous» flag of its phase on each side if it has one
                        base = k.rsplit(".", 1)[0]
                        amb, hand = base + ".ambiguous", base + ".hand_evidence"
                        jumps.append({"t": round(stroke_time(s), 2), "medida": k, "a": round(float(va), 1),
                                      "b": round(float(vb), 1), "ambigua_a": la.get(amb), "ambigua_b": lb.get(amb),
                                      "mano_a": la.get(hand), "mano_b": lb.get(hand)})
    return {"a": len(a), "b": len(b), "pares": len(pairs), "solo_a": only_a[:20], "solo_b": only_b[:20],
            "tipo_distinto": kinds[:20], "medidas_distintas": dict(sorted(diffs.items(), key=lambda kv: -kv[1])[:20]),
            "saltos": jumps[:400], "golpes_con_saltos": len({j["t"] for j in jumps}),
            "mayor_diferencia": {k: round(v, 4) for k, v in sorted(worst.items(), key=lambda kv: -kv[1])[:20]},
            "temblor": shake_summary(shake),
            "temblor_por_familia": {f: shake_summary(v) for f, v in sorted(by_family.items())},
            "tronco_3d": {"a": trunk3d_summary(a), "b": trunk3d_summary(b)}}


SHAKE_PREFIX = "technique.jitter."


# 21-11 (#307, Sapiens2 in the fine pass: −36 % on the body's points, ×1.00 over all measures): the shake also by
# family of measure, by its name (in this order: «racket_tip_height» is the racket's, «wrist_dom_height» the wrists')
SHAKE_FAMILIES = [("raqueta", ("racket",)), ("pies", ("base_width", "foot", "heel", "toe", "com_over_feet")),
                  ("muñecas", ("wrist", "hands_apart")), ("brazos", ("elbow", "shoulder_abd", "arm_extension")),
                  ("tronco", ("turn", "x_factor", "tilt", "head")), ("piernas", ("knee", "height"))]


def shake_family(key: str) -> str:
    m = key.rsplit(".", 1)[-1]
    return next((f for f, toks in SHAKE_FAMILIES if any(t in m for t in toks)), "otras")


def _shake_items(la: dict, lb: dict) -> list[tuple[str, float, float]]:
    """15-11 (T25, a model against another): the frame-to-frame shake of each measure on both sides, the same measure
    of the same stroke, with its key. The racket face is left out: its sign flips (R50) would be counted as shake."""
    out = []
    for k in la.keys() & lb.keys():
        va, vb = la[k], lb[k]
        if (k.startswith(SHAKE_PREFIX) and "face" not in k and isinstance(va, (int, float))
                and isinstance(vb, (int, float)) and not isinstance(va, bool) and not isinstance(vb, bool)):
            out.append((k, abs(float(va)), abs(float(vb))))
    return out


def _shake_pairs(la: dict, lb: dict) -> list[tuple[float, float]]:
    return [(a, b) for _, a, b in _shake_items(la, lb)]


TRUNK3D_KEYS = ("x_factor_3d_deg", "shoulder_turn_3d_deg", "hip_turn_3d_deg")


def trunk3d_summary(strokes: list[dict]) -> dict:
    """21-11 (#309, a 3D model against another on the same strokes): how many strokes have each trunk 3D value and their
    spread across strokes (median absolute deviation, deg): with the same strokes, more values and less spread is a
    reading with less noise (there is no 3D reference from the TV's view)."""
    out = {}
    for k in TRUNK3D_KEYS:
        v = [float((s.get("metrics") or {}).get(k)) for s in strokes
             if isinstance((s.get("metrics") or {}).get(k), (int, float))]
        md = statistics.median(v) if v else None
        out[k] = {"golpes": len(v), "mad": round(statistics.median([abs(x - md) for x in v]), 2) if v else None}
    return out


def shake_summary(shake: list[tuple[float, float]]) -> dict:
    """The shake of b against a over the same measures: the median ratio and how often b shakes less (a model that
    measures better shakes less on the same strokes; −35 % was how RTMPose-x won in the PC, with 13 strokes)."""
    both = [(a, b) for a, b in shake if a > 0]
    if not both:
        return {"n": 0}
    ratios = sorted(b / a for a, b in both)
    mid = len(ratios) // 2
    med = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    return {"n": len(both), "cociente_mediano_b_a": round(med, 3),
            "b_tiembla_menos": round(sum(b < a for a, b in both) / len(both), 3),
            "b_tiembla_mas": round(sum(b > a for a, b in both) / len(both), 3)}


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
    # 14-11 (the first comparison): a strokes file read on one side only is a comparison not made, never «same»
    one_side = sorted(f for f in files if (f in strokes_a) != (f in strokes_b))
    strokes_ok = not one_side and all(not c["solo_a"] and not c["solo_b"] and not c["tipo_distinto"]
                                      and not c["medidas_distintas"] for c in files.values())
    if one_side:
        verdict = "incompleta"
    elif not differ and not missing and same and strokes_ok:
        verdict = "idéntica"
    elif strokes_ok and files:
        verdict = "equivalente"
    else:
        verdict = "distinta"
    return {"veredicto": verdict, "etapas_iguales": same, "etapas_distintas": differ, "etapas_sin_comparar": missing,
            "golpes": files, "ficheros_de_un_solo_lado": one_side}


def summary(c: dict) -> str:
    """One line for the queue's summary."""
    parts = [c["veredicto"], f"{len(c['etapas_iguales'])} etapas iguales"]
    if c.get("ficheros_de_un_solo_lado"):
        parts.append("leídos en un solo lado: " + ", ".join(c["ficheros_de_un_solo_lado"]))
    if c["etapas_distintas"]:
        parts.append("distintas: " + ", ".join(c["etapas_distintas"][:8]))
    for f, g in c["golpes"].items():
        bad = len(g["solo_a"]) + len(g["solo_b"]) + len(g["tipo_distinto"])
        parts.append(f"{f}: {g['pares']} de {g['a']}/{g['b']} golpes emparejados"
                     + (f", {bad} distintos" if bad else "")
                     + (f", medidas fuera de tolerancia: {', '.join(list(g['medidas_distintas'])[:4])}"
                        if g["medidas_distintas"] else ""))
        sh = g.get("temblor") or {}
        if sh.get("n") and g["medidas_distintas"]:
            parts.append(f"{f}: temblor de b frente a a ×{sh['cociente_mediano_b_a']:.2f} (mediana de {sh['n']} medidas;"
                         f" b tiembla menos en el {100 * sh['b_tiembla_menos']:.0f} %)")
            fam = {k: v for k, v in (g.get("temblor_por_familia") or {}).items() if v.get("n")}
            if fam:
                parts.append(f"{f}: temblor por familias: " + ", ".join(
                    f"{k} ×{v['cociente_mediano_b_a']:.2f}" for k, v in fam.items()))
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
