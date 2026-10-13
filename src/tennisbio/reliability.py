"""Is each measure technique or noise? Checked on her own strokes, with no annotation.

The instant of a phase is only known to ±1-2 frames. For every stroke the fine pass also measures each
phase value 1-2 frames either side (technique.stroke_technique, "jitter": median change). If a measure
moves more between neighbouring frames of the same stroke than it differs between her strokes, what
the screen would show is noise from the camera and the pose model, not how she plays: it is not shown
as her value, and the screen says why.

    noise  = median over strokes of the neighbouring-frame change
    spread = robust spread of the value between her strokes (IQR / 1.349)
    fiable  noise ≤ ½ spread (or below a floor too small to matter: 3°, 1.5 % of height, 20 ms)
    dudosa  between the two: shown, marked
    ruido   noise > spread: not shown as her value

Timings, steps and classes are judged the same way with the whole stroke described again with its
phase instants moved (stages: shifted_jitter). For a class or a yes/no the noise is how often it flips:
fiable ≤ 15 %, dudosa ≤ 35 %, ruido above. A measure that never changes when the instants move (it
does not depend on them, e.g. measured at the impact) is "no comprobable" this way, not reliable.

Repeatable is not right: a measure can be stable and biased. Where a second, independent method
exists (the 3D estimate of the trunk, RTMW3D) both must agree: if they differ systematically (median
difference over 8° with the same sign in at least 3 of 4 strokes) the measure is "sesgo" and is not
given as her value either; the screen gives both readings. A measure computed from a biased or noisy
one (DERIVED_FROM: the shoulder brake comes from the 2D shoulder turn) takes its verdict.
"""
from __future__ import annotations

import numpy as np

MIN_STROKES = 5
FLOOR = {"°": 3.0, "%": 1.5, "s": 0.02, "cm": 3.0}
# measure → the same thing from an independent method (stroke_values key)
SECOND_METHOD = {"loaded.x_factor": "metrics.x_factor_3d_deg", "loaded.shoulder_turn": "metrics.shoulder_turn_3d_deg",
                 "loaded.hip_turn": "metrics.hip_turn_3d_deg"}
AGREE_DEG = 8.0
# measures computed from another one: they cannot be better than it (a biased or noisy source makes them so)
DERIVED_FROM = {"stroke.shoulder_brake": "loaded.shoulder_turn", "stroke.shoulders_open_first": "loaded.shoulder_turn"}


def shifted_jitter(base: dict, shifted: list[dict]) -> dict:
    """Median change of each timing/step value, and share of flips of each class, when the stroke is
    described again with its phase instants moved (base and shifted: technique.stroke_technique)."""
    out = {}
    for grp in ("stroke", "footwork", "classes"):
        for k, v in (base.get(grp) or {}).items():
            key = f"class.{k}" if grp == "classes" else f"{grp}.{k}"
            others = [(s.get(grp) or {}).get(k) for s in shifted]
            if isinstance(v, bool) or isinstance(v, str):
                out[key] = round(sum(o != v for o in others) / len(others), 2) if others else None
            elif isinstance(v, (int, float)):
                nums = [o for o in others if isinstance(o, (int, float)) and not isinstance(o, bool)]
                if len(nums) >= 2:
                    out[key] = round(float(np.median(np.abs(np.asarray(nums, float) - v))), 3)
    return {k: v for k, v in out.items() if v is not None}


def _floor(unit: str | None) -> float:
    return FLOOR.get((unit or "").strip(), 0.0)


def assess(raw: list[dict], keys: dict[str, str | None]) -> dict:
    """raw: strokes as in strokes.json; keys: measure key ('phase.name') → unit."""
    from .audit import stroke_values

    vals = [stroke_values(s) for s in raw]
    jit = [((s.get("technique") or {}).get("jitter") or {}) for s in raw]
    out = {}
    for k, unit in keys.items():
        j = [x[k] for x in jit if isinstance(x.get(k), (int, float))]
        cat = [x[k] for x in vals if isinstance(x.get(k), (bool, str))]
        if cat:                                   # a class or a yes/no: how often it flips
            if len(j) < MIN_STROKES:
                if j:
                    out[k] = {"n": len(j), "flip": round(float(np.mean(j)), 2), "verdict": "sin juzgar"}
                continue
            flip = float(np.mean(j))
            out[k] = {"n": len(j), "flip": round(flip, 2),
                      "verdict": "fiable" if flip <= 0.15 else "dudosa" if flip <= 0.35 else "ruido"}
            continue
        v = [x[k] for x in vals if isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool)]
        if len(j) < MIN_STROKES or len(v) < MIN_STROKES:
            if j:
                out[k] = {"n": len(j), "noise": round(float(np.median(j)), 2), "spread": None, "verdict": "sin juzgar"}
            continue
        noise = float(np.median(j))
        if max(j) == 0:
            out[k] = {"n": len(j), "noise": 0.0, "spread": None, "verdict": "no comprobable"}
            continue
        q1, q3 = np.percentile(v, [25, 75])
        spread = float(q3 - q1) / 1.349
        if noise <= max(0.5 * spread, _floor(unit)):
            verdict = "fiable"
        elif noise <= spread:
            verdict = "dudosa"
        else:
            verdict = "ruido"
        out[k] = {"n": len(j), "noise": round(noise, 2), "spread": round(spread, 2), "verdict": verdict}
        other = SECOND_METHOD.get(k)
        pairs = [(x[k], x[other]) for x in vals if other and isinstance(x.get(k), (int, float)) and isinstance(x.get(other), (int, float))]
        if len(pairs) >= MIN_STROKES and verdict != "ruido":
            d = np.array([a - b for a, b in pairs])
            bias = float(np.median(d))
            same = max(np.mean(d > 0), np.mean(d < 0))
            out[k].update(n2=len(pairs), med2d=round(float(np.median([a for a, _ in pairs])), 1),
                          med3d=round(float(np.median([b for _, b in pairs])), 1), bias=round(bias, 1))
            if abs(bias) > max(AGREE_DEG, 2 * noise) and same >= 0.75:
                out[k]["verdict"] = "sesgo"
    for k, src in DERIVED_FROM.items():
        if k in keys and (out.get(src) or {}).get("verdict") in ("sesgo", "ruido"):
            s = out[src]
            out[k] = {**out.get(k, {"n": s.get("n")}), "verdict": s["verdict"], "from": src,
                      **{x: s[x] for x in ("med2d", "med3d", "n2", "noise", "spread") if x in s}}
    return out


def summary(rel: dict) -> dict:
    c = {}
    for v in rel.values():
        c[v["verdict"]] = c.get(v["verdict"], 0) + 1
    return c
