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
"""
from __future__ import annotations

import numpy as np

MIN_STROKES = 5
FLOOR = {"°": 3.0, "%": 1.5, "s": 0.02, "cm": 3.0}


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
        v = [x[k] for x in vals if isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool)]
        if len(j) < MIN_STROKES or len(v) < MIN_STROKES:
            if j:
                out[k] = {"n": len(j), "noise": round(float(np.median(j)), 2), "spread": None, "verdict": "sin juzgar"}
            continue
        noise = float(np.median(j))
        q1, q3 = np.percentile(v, [25, 75])
        spread = float(q3 - q1) / 1.349
        if noise <= max(0.5 * spread, _floor(unit)):
            verdict = "fiable"
        elif noise <= spread:
            verdict = "dudosa"
        else:
            verdict = "ruido"
        out[k] = {"n": len(j), "noise": round(noise, 2), "spread": round(spread, 2), "verdict": verdict}
    return out


def summary(rel: dict) -> dict:
    c = {}
    for v in rel.values():
        c[v["verdict"]] = c.get(v["verdict"], 0) + 1
    return c
