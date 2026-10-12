"""The technique model of a player's stroke, built from all her analysed strokes.

- typical: for every descriptor at every phase, median and ranges (p25-p75, p10-p90), n.
- adaptations: what changes with each situation (ball speed, height, depth, width, intent,
  movement, stance, side of the court). Each effect is the difference with her usual situation,
  adjusted at the same time for every other factor and for the match (ordinary least squares
  with robust errors), kept only when it is both statistically solid after correcting for the
  number of comparisons (Benjamini-Hochberg, q < 0.05) and larger than a minimum meaningful
  difference for its unit. A fast ball that also forces defence is therefore not counted twice.
- constants: descriptors that no situation changes (her core technique).
- variants: one profile per situation with enough strokes, with its typical strokes (video).
- classes: how often each stance, finish, takeback shape, movement… happens, overall and per
  situation.
- mean skeleton of each moment (overall and per variant), for drawing.

Nothing is invented: a descriptor without enough strokes is left out; every number says on how
many strokes it stands.
"""
import json
import math
import warnings

import numpy as np

from .technique import DESCRIPTORS, PHASES, STROKE_DESCRIPTORS, flatten

FACTORS = {
    "ball_speed": ("Velocidad de la bola", ["lenta", "media", "rápida", "muy rápida"]),
    "ball_height": ("Altura de la bola", ["rodilla", "cadera", "cintura-pecho", "pecho-hombro", "por encima del hombro"]),
    "depth": ("Dónde golpea", ["dentro de la pista", "sobre la línea", "1-2 m detrás", "2-4 m detrás", "muy atrás"]),
    "width": ("Desplazamiento", ["centrada", "abierta", "muy abierta"]),
    "movement": ("Cómo llega", ["parada", "en movimiento", "en carrera", "deslizando", "en el aire"]),
    "intent": ("Intención", ["ataque", "neutra", "defensa"]),
    "stance_impact": ("Apoyo", ["abierto", "semiabierto", "neutro", "cerrado"]),
    "court_side": ("Lado de la pista", ["lado de su derecha", "centro", "lado de su revés"]),
    "swing": ("Efecto", ["liftado (de abajo arriba)", "plano", "cortado (de arriba abajo)"]),
    "play": ("Momento del punto", ["resto", "inicio del punto", "peloteo"]),
}
CLASS_KEYS = ["stance_loaded", "stance_impact", "stance_role", "finish", "finish_3x90", "arm", "takeback", "takeback_face",
              "ready_hands", "movement", "move_direction", "play", "shot_type", "swing",
              "intent", "ball_speed", "ball_height", "depth", "width", "court_side"]
FOOTWORK_KEYS = ["steps_to_impact", "adjustment_steps", "first_step_s", "first_step_length_m", "last_step_length_m",
                 "last_plant_before_impact_s", "speed_at_impact_mps", "path_m", "peak_speed_mps", "direction_changes",
                 "split_takeoff_vs_opp_s", "split_landing_vs_opp_s", "speed_pre_split_mps", "speed_post_split_mps",
                 "recovery_to_centre_m", "off_centre_at_opp_hit_m", "weight_loaded_to_non"]
FOOTWORK_NAMES = {
    "steps_to_impact": ("Pasos hasta el impacto", "", 3), "adjustment_steps": ("Pasos de ajuste (últimos 0,8 s)", "", 2),
    "first_step_s": ("Primer paso tras el split step", "s", 2), "last_plant_before_impact_s": ("Último apoyo antes del impacto", "s", 2),
    "speed_at_impact_mps": ("Velocidad en el impacto", "m/s", 3), "path_m": ("Recorrido hasta la bola", "m", 3),
    "peak_speed_mps": ("Velocidad máxima de desplazamiento", "m/s", 3),
    "recovery_to_centre_m": ("Recuperación hacia el centro (1 s)", "m", 3),
    "weight_loaded_to_non": ("Peso en el armado (0 = pie dominante, 1 = el otro)", "", 2),
    "first_step_length_m": ("Longitud del primer paso", "m", 2), "last_step_length_m": ("Longitud del último paso", "m", 2),
    "direction_changes": ("Cambios de dirección", "", 2),
    "split_takeoff_vs_opp_s": ("Despegue del split step respecto al golpe rival", "s", 2),
    "split_landing_vs_opp_s": ("Aterrizaje del split step respecto al golpe rival", "s", 2),
    "speed_pre_split_mps": ("Velocidad antes del split step", "m/s", 2), "speed_post_split_mps": ("Velocidad después del split step", "m/s", 2),
    "off_centre_at_opp_hit_m": ("Distancia al centro cuando la rival vuelve a golpear", "m", 3),
}
# minimum difference worth telling, by unit (below it, even a solid difference is not technique)
MIN_DIFF = {"°": 4.0, "%": 2.5, "s": 0.04, "": 0.12, "m": 0.2, "m/s": 0.3, "cm": 3.0}
MIN_N = 12


def describe(key: str) -> tuple[str, str, int, str]:
    """(name, unit, reliability, description) of a flattened key like 'loaded.shoulder_turn'."""
    grp, k = key.split(".", 1)
    if grp == "stroke":
        g, n, u, r, d = STROKE_DESCRIPTORS.get(k, ("", k, "", 1, ""))
        return n, u, r, d
    if grp == "footwork":
        n, u, r = FOOTWORK_NAMES.get(k, (k, "", 1))
        return n, u, r, ""
    g, n, u, r, d = DESCRIPTORS.get(k, ("", k, "", 1, ""))
    if k in ("stance_angle",):
        return "Ángulo del apoyo", "°", 3, "0 = abierto, 90 = neutro"
    if k == "base_m":
        return "Anchura de la base", "m", 3, "en la pista"
    return n, u, r, d


def _stats(v: np.ndarray) -> dict:
    q = np.quantile(v, [.1, .25, .5, .75, .9])
    return {"n": int(len(v)), "p10": float(q[0]), "p25": float(q[1]), "median": float(q[2]), "p75": float(q[3]), "p90": float(q[4])}


def _bh(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values."""
    n = len(p)
    if not n:
        return p
    o = np.argsort(p)
    q = p[o] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[o] = np.minimum(q, 1.0)
    return out


def _ols(y: np.ndarray, X: np.ndarray):
    """Coefficients and robust (HC1) standard errors."""
    n, p = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    meat = (X * (e ** 2)[:, None]).T @ X
    V = XtX_inv @ meat @ XtX_inv * n / max(1, n - p)
    return b, np.sqrt(np.maximum(np.diag(V), 0))


def _r2_each(X: np.ndarray, names: list) -> np.ndarray:
    """R² of each situation column explained by all the other columns (collinearity)."""
    r2 = np.zeros(X.shape[1])
    for j, nm in enumerate(names):
        if nm is None:
            continue
        others = np.delete(X, j, axis=1)
        fit = others @ np.linalg.lstsq(others, X[:, j], rcond=None)[0]
        r2[j] = 1 - np.sum((X[:, j] - fit) ** 2) / max(np.sum((X[:, j] - X[:, j].mean()) ** 2), 1e-12)
    return r2


def _norm_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


def build_model(strokes: list[dict], min_n: int = MIN_N) -> dict:
    """strokes: rows of strokes.json of one player and one stroke type (with 'technique')."""
    near = [s for s in strokes if s.get("technique") and s.get("side", "near") == "near"]
    allc = [s for s in strokes if s.get("technique")]
    flat = [flatten(s["technique"]) for s in near]
    cls = [s["technique"].get("classes") or {} for s in near]
    match = [str(s.get("match_id") or s.get("stroke_id", "").rsplit("-", 1)[0]) for s in near]
    keys = sorted({k for f in flat for k in f})
    out = {"n_strokes": len(allc), "n_near": len(near), "typical": {}, "effects": [], "constants": [], "variants": {},
           "classes": {}, "footwork": {}, "skeleton": {}, "factors": {k: v[0] for k, v in FACTORS.items()}}
    # 1. typical values
    for k in keys:
        v = np.array([f[k] for f in flat if k in f], float)
        v = v[np.isfinite(v)]
        if len(v) >= min_n:
            name, unit, rel, desc = describe(k)
            out["typical"][k] = {**_stats(v), "name": name, "unit": unit, "rel": rel, "desc": desc}
    # 2. class frequencies (all strokes, near and far, for the situation classes)
    for ck in CLASS_KEYS:
        src = cls if ck not in ("intent", "ball_speed", "ball_height", "depth", "width", "court_side", "shot_type") else \
            [s["technique"].get("classes") or {} for s in allc]
        vals = [c[ck] for c in src if c.get(ck) is not None]
        if vals:
            out["classes"][ck] = {"n": len(vals), "counts": {v: vals.count(v) for v in sorted(set(vals), key=vals.count, reverse=True)}}
    # 3. adjusted effects of each situation
    levels = {}
    for fk, (_, order) in FACTORS.items():
        vals = [c.get(fk) for c in cls]
        ok = [lv for lv in order if vals.count(lv) >= min_n]
        if len(ok) >= 2:
            ref = max(ok, key=vals.count)                     # her usual situation is the reference
            levels[fk] = (ref, [lv for lv in ok if lv != ref])
    matches = sorted(set(match))
    tests, r2_cache = [], {}
    for k, t in out["typical"].items():
        rows = [i for i, f in enumerate(flat) if k in f and np.isfinite(f[k])]
        if len(rows) < 2 * min_n:
            continue
        y = np.array([flat[i][k] for i in rows], float)
        cols, names = [np.ones(len(rows))], [None]
        for fk, (ref, lvs) in levels.items():
            for lv in lvs:
                cols.append(np.array([1.0 if cls[i].get(fk) == lv else 0.0 for i in rows]))
                names.append((fk, lv, ref))
            # strokes without this class: a separate column so they do not count as the reference
            miss = np.array([1.0 if cls[i].get(fk) is None or (cls[i].get(fk) not in lvs and cls[i].get(fk) != ref) else 0.0 for i in rows])
            if miss.any():
                cols.append(miss)
                names.append(None)
        for m in matches[1:]:
            cols.append(np.array([1.0 if match[i] == m else 0.0 for i in rows]))
            names.append(None)
        X = np.column_stack(cols)
        keep = X.std(axis=0) > 0
        keep[0] = True
        X, names = X[:, keep], [nm for nm, kp in zip(names, keep) if kp]
        if X.shape[0] <= X.shape[1] + 5:
            continue
        b, se = _ols(y, X)
        # most measures share the same strokes, hence the same design: its collinearity is computed once
        hx = hash(X.tobytes())
        if hx not in r2_cache:
            r2_cache[hx] = _r2_each(X, names)
        r2s = r2_cache[hx]
        for j, nm in enumerate(names):
            if nm is None or se[j] <= 0:
                continue
            # a situation almost fully determined by the others (e.g. "defence" and "very fast
            # ball") cannot be separated from them: no effect is claimed for it
            if r2s[j] > 0.8:
                continue
            fk, lv, ref = nm
            n_lv = int(X[:, j].sum())
            if n_lv < min_n:
                continue
            tests.append({"key": k, "factor": fk, "level": lv, "ref": ref, "diff": float(b[j]), "se": float(se[j]),
                          "p": _norm_p(b[j] / se[j]), "n": n_lv})
    if tests:
        q = _bh(np.array([t["p"] for t in tests]))
        for t, qq in zip(tests, q):
            unit = out["typical"][t["key"]]["unit"]
            t["q"] = float(qq)
            t["meaningful"] = abs(t["diff"]) >= MIN_DIFF.get(unit, 0.0)
            t["solid"] = t["q"] < 0.05 and t["meaningful"]
        out["effects"] = sorted([t for t in tests if t["solid"]], key=lambda t: -abs(t["diff"] / t["se"]))
    changed = {t["key"] for t in out["effects"]}
    tested = {t["key"] for t in tests}
    out["constants"] = [k for k in out["typical"] if k in tested and k not in changed]
    # 4. variants: each situation level with enough strokes
    for fk, (ref, lvs) in levels.items():
        for lv in [ref] + lvs:
            idx = [i for i, c in enumerate(cls) if c.get(fk) == lv]
            eff = [t for t in out["effects"] if t["factor"] == fk and t["level"] == lv]
            out["variants"].setdefault(fk, {})[lv] = {
                "n": len(idx), "share": round(len(idx) / max(1, len(near)), 3), "usual": lv == ref,
                "effects": eff, "strokes": _typical_ids([near[i] for i in idx], [flat[i] for i in idx], out["typical"]),
                "classes": {ck: _counts([cls[i].get(ck) for i in idx]) for ck in ("stance_impact", "finish", "takeback", "movement")},
                "skeleton": _mean_skeleton([near[i] for i in idx]),
            }
    # 5. footwork summary and the overall mean skeleton
    out["footwork"] = {k: out["typical"].get(f"footwork.{k}") for k in FOOTWORK_KEYS if out["typical"].get(f"footwork.{k}")}
    out["footwork"]["first_step_type"] = _counts([(s["technique"].get("footwork") or {}).get("first_step_type") for s in near])
    out["footwork"]["last_plant_foot"] = _counts([(s["technique"].get("footwork") or {}).get("last_plant_foot") for s in near])
    out["footwork"]["move_direction"] = _counts([(s["technique"].get("classes") or {}).get("move_direction") for s in near])
    out["footwork"]["rear_leg_step_after"] = _counts([(s["technique"].get("footwork") or {}).get("rear_leg_step_after") for s in near])
    out["skeleton"] = _mean_skeleton(near)
    # points won by the phase of play of her last stroke in each point (TennisViz "conversion"
    # in attack, "steal" in defence): one stroke per point
    last = {}
    for s_ in allc:
        sc = s_.get("score") or {}
        if s_.get("point_won") is None or not sc:
            continue
        key = (s_.get("match_id"), json.dumps(sc.get("games")), json.dumps(sc.get("points")))
        if key not in last or s_.get("match_time_s", 0) > last[key].get("match_time_s", 0):
            last[key] = s_
    pts = {}
    for s_ in last.values():
        it = (s_["technique"].get("classes") or {}).get("intent")
        if it:
            w, n = pts.get(it, (0, 0))
            pts[it] = (w + bool(s_["point_won"]), n + 1)
    out["points_by_intent"] = {k: {"won": w, "n": n} for k, (w, n) in pts.items()}
    out["typical_strokes"] = _typical_ids(near, flat, out["typical"])
    return out


def _counts(vals) -> dict:
    v = [x for x in vals if x is not None]
    return {"n": len(v), "counts": {x: v.count(x) for x in sorted(set(v), key=v.count, reverse=True)}}


def _typical_ids(rows: list, flat: list, typical: dict, k: int = 8) -> list[str]:
    """Strokes closest to the median in most descriptors (scaled by their spread), best first."""
    if not rows:
        return []
    keys = [key for key, t in typical.items() if t["rel"] >= 2 and t["p75"] > t["p25"]]
    scores = []
    for s, f in zip(rows, flat):
        z = [((f[key] - typical[key]["median"]) / (typical[key]["p75"] - typical[key]["p25"])) ** 2 for key in keys if key in f]
        cover = len(z) / max(1, len(keys))
        if not z or cover < 0.6:
            continue
        scores.append((math.sqrt(sum(z) / len(z)) - 0.5 * cover, s.get("stroke_id")))
    return [sid for _, sid in sorted(scores)[:k] if sid]


def _mean_skeleton(rows: list) -> dict:
    """Median pose of each moment (17 joints, hip-centred, body heights, dominant side +x)."""
    out = {}
    for p in PHASES:
        poses = [s["technique"].get("pose", {}).get(p) for s in rows]
        poses = [np.array([[np.nan, np.nan] if v is None else v for v in q], float) for q in poses if q]
        if len(poses) >= 5:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)       # joints never seen
                m = np.nanmedian(np.stack(poses), axis=0)
            out[p] = [None if not np.isfinite(v).all() else [round(float(v[0]), 3), round(float(v[1]), 3)] for v in m]
    return out
