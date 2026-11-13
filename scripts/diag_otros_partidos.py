"""R30 (13-11): the broadcasts show other matches now and then (Zheng – Rybakina at 77 min: Shelton – Alcaraz; the end of
the final: a doubles match, the Williams against Chan and Joint; a studio with the match in a small window), and the
identity decided runs there as if they were her match (diagnosis 286). How much of each match that is, and whether any of
her strokes come from it: the main-camera shots in play where the scoreboard was tried and never read with the two
players' names (score.json), the identity runs and her strokes (strokes.json) inside them, around the given seconds
what each stage left, and the runs whose clothes are far from both players' (another match's people). Writes <output>/capturas_diag/diag_otros_partidos.json. Reads only.

    uv run python scripts/diag_otros_partidos.py --match osaka pegula zheng gauff sobolenko --t 4628 11586 12203 12217
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def _read(d: Path, name: str):
    f = mf.at(d, name)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _strokes(d: Path) -> list[dict]:
    s = _read(d, "strokes.json")
    if isinstance(s, dict):
        s = s.get("strokes") or []
    return [x for x in (s or []) if isinstance(x, dict)]


def unread_shots(score: dict | None, min_tries: int = 2) -> list[dict]:
    """Main-camera shots in play where the scoreboard was tried at least min_tries times and never read with the two
    players' names: replays without a scoreboard, and other matches (their scoreboard shows other names)."""
    return [s for s in (score or {}).get("shots") or [] if s.get("tried", 0) >= min_tries and not s.get("read")]


def inside(t: float, shots: list[dict]) -> dict | None:
    return next((s for s in shots if s["start"] <= t < s["end"]), None)


def clothes_outliers(ident: dict | None, top: int = 15) -> dict:
    """How far each run's clothes are from the two players' typical clothes (clothes.group_centroids of the identity's
    own groups): a person of another match is far from both. The distances of the clear runs (margin ≥ 0.3) to their
    own group give the usual spread; the farthest runs are listed with their time, group, margin and decision."""
    import numpy as np

    from tennisbio.clothes import CLOTHES_DIM, clothes_distances, group_centroids
    runs = [r for r in (ident or {}).get("runs") or [] if r.get("clothes_code") is not None]
    if len(runs) < 4:
        return {"runs_with_code": len(runs)}
    fps = float(ident.get("fps") or 1.0)
    X = np.array([[np.nan if v is None else v for v in r["clothes_code"]] for r in runs], np.float32).reshape(-1, CLOTHES_DIM)
    lab = np.array([r.get("cluster", -1) if r.get("cluster") is not None else -1 for r in runs])
    mar = np.array([float(r.get("clothes_margin") or 0) for r in runs])
    cents = group_centroids(X, lab, mar)
    if any(c is None for c in cents):
        return {"runs_with_code": len(runs), "note": "un grupo sin código"}
    D = clothes_distances(X, np.stack(cents))                # (runs, 2)
    dmin = np.nanmin(D, axis=1)
    own = np.array([D[i, lab[i]] if lab[i] in (0, 1) else np.nan for i in range(len(runs))])
    clear = own[(mar >= 0.3) & np.isfinite(own)]
    q = {f"p{k}": round(float(np.quantile(clear, k / 100)), 3) for k in (50, 90, 95, 99)} if len(clear) else {}
    order = np.argsort(-np.nan_to_num(dmin, nan=-1))[:top]
    far = [{"t0": round(float(runs[i].get("start", 0)) / fps, 1), "t1": round(float(runs[i].get("end", 0)) / fps, 1),
            "d_min": round(float(dmin[i]), 3), "d0": round(float(D[i, 0]), 3), "d1": round(float(D[i, 1]), 3),
            "cluster": int(lab[i]), "margin": round(float(mar[i]), 2), "near_is_target": runs[i].get("near_is_target"),
            "method": runs[i].get("method")} for i in order if np.isfinite(dmin[i])]
    return {"runs_with_code": len(runs), "own_distance_clear_runs": q, "farthest": far}


def report(d: Path, probes: list[float]) -> dict:
    score, ident = _read(d, "score.json"), _read(d, "identity.json")
    if score is None:
        return {"error": f"sin score.json en {d}"}
    un = unread_shots(score)
    strokes = _strokes(d)
    in_un = [{"t": round(float(s.get("t", 0)), 2), "side": s.get("side"), "stroke": s.get("stroke")}
             for s in strokes if inside(float(s.get("t", 0)), un)]
    runs = []
    if ident:
        fps = float(ident.get("fps") or 1.0)
        for r in ident.get("runs") or []:
            a, b = float(r.get("start", 0)) / fps, float(r.get("end", 0)) / fps
            if any(s["start"] < b and s["end"] > a for s in un):
                runs.append({"t0": round(a, 1), "t1": round(b, 1), "near_is_target": r.get("near_is_target"),
                             "method": r.get("method"), "clothes_margin": r.get("clothes_margin")})
    pr = []
    for t in probes:
        near = [s for s in strokes if abs(float(s.get("t", 0)) - t) <= 15]
        sh = next((s for s in score.get("shots") or [] if s["start"] <= t < s["end"]), None)
        pr.append({"t": t, "shot": sh, "strokes_within_15s": [{"t": round(float(s.get("t", 0)), 2),
                                                               "side": s.get("side"), "stroke": s.get("stroke")}
                                                              for s in near]})
    return {"unread_shots": len(un), "unread_min": round(sum(s["end"] - s["start"] for s in un) / 60, 1),
            "strokes": len(strokes), "strokes_in_unread": in_un, "runs_in_unread": runs, "probes": pr,
            "names": score.get("names"), "clothes": clothes_outliers(ident)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", nargs="+", required=True)
    ap.add_argument("--t", nargs="*", type=float, default=[], help="segundos a mirar (en todos los partidos)")
    a = ap.parse_args()
    cfg = load_config()
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    from tennisbio import layout
    from tennisbio.catalog import load_matches
    rep = {}
    for m in load_matches(cfg):
        if any(s.lower() in m.id.lower() for s in a.match):
            rep[m.id] = report(layout.dir_of(out, m, cfg), a.t)
            r = rep[m.id]
            print(m.id, json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in r.items()
                                    if k != "probes"}, ensure_ascii=False), flush=True)
    cd = out / "capturas_diag"
    cd.mkdir(parents=True, exist_ok=True)
    (cd / "diag_otros_partidos.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
