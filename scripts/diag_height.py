"""Can the near player's height tell the two players apart when their clothes cannot? (11-11: Rybakina 1.84 m and
Pegula 1.70 m, both in white; 62 of 320 runs undecided where the scoreboard was not read.)

For each main-camera run of the cheap pass: her standing height estimated from the pose against the court (the
court's vertical scale at her feet: body_scale.court_height_track with a nominal 1.80 m, times the pose's height
ratio), labelled with the identity (user's click applied): hers, the rival's, undecided. Writes
<output>/capturas_diag/diag_estatura.json: per match the medians, spreads, how well a threshold between the two
separates the decided runs (cross-checked), and what it would say of the undecided runs. Nothing is changed.

    uv run python scripts/diag_height.py [--match TEXT ...]"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402

NOMINAL_M = 1.80


def run_heights(d: Path, hand: str) -> list[dict]:
    from tennisbio import match_files as mf
    from tennisbio.ball3d import camera
    from tennisbio.body_scale import court_height_track
    from tennisbio.identity import PICK_FILE, apply_pick
    from tennisbio.kinematics import body_height
    from tennisbio.skeleton import Skeleton
    from tennisbio.stages import court_at, near_runs

    ident = json.loads(mf.at(d, "identity.json").read_text(encoding="utf-8"))
    pf = mf.at(d, PICK_FILE)
    if pf.exists():
        ident, _ = apply_pick(ident, json.loads(pf.read_text(encoding="utf-8")))
    by_start = {int(r["start"]): r for r in ident.get("runs", [])}
    probe = json.loads(mf.at(d, "probe.json").read_text(encoding="utf-8"))
    shape = (int(probe.get("height") or 1080), int(probe.get("width") or 1920))
    court = json.loads(mf.at(d, "court.json").read_text(encoding="utf-8"))
    with np.load(mf.at(d, "players.npz"), allow_pickle=True) as z:
        pl = {k: z[k] for k in z.files}
    fps, frames = float(pl["fps"]), pl["frames"]
    sk = Skeleton("coco17", hand)
    out = []
    for run, img, cf, h, app, sel in near_runs(pl, sk, court, with_sel=True):
        r = by_start.get(int(frames[run[0]]))
        if r is None:
            continue
        t = float(frames[run[len(run) // 2]]) / fps
        H, _ = court_at(court, t)
        est = None
        if H is not None:
            P = camera(np.asarray(H, float), shape)
            if P is not None:
                ht = court_height_track(img, sk, P, NOMINAL_M, fps)
                with np.errstate(all="ignore"):
                    ph = body_height(img, sk)
                if ht is not None and np.isfinite(ph) and np.median(ht) > 0:
                    est = round(float(NOMINAL_M * ph / np.median(ht)), 3)
        lab = r.get("near_is_target")
        out.append({"t": round(t), "m": est, "who": "ella" if lab is True else "rival" if lab is False else "sin decidir"})
    return out


def separation(rows: list[dict]) -> dict:
    a = np.array([r["m"] for r in rows if r["who"] == "ella" and r["m"]])
    b = np.array([r["m"] for r in rows if r["who"] == "rival" and r["m"]])
    if len(a) < 5 or len(b) < 5:
        return {"ella": len(a), "rival": len(b), "nota": "pocos planos con estatura"}
    thr = (np.median(a) + np.median(b)) / 2
    taller_is_her = np.median(a) > np.median(b)
    ok = np.sum((a > thr) == taller_is_her) + np.sum((b > thr) != taller_is_her)
    und = [r for r in rows if r["who"] == "sin decidir" and r["m"]]
    return {"ella_mediana": round(float(np.median(a)), 3), "rival_mediana": round(float(np.median(b)), 3),
            "ella_iqr": [round(float(x), 3) for x in np.percentile(a, [25, 75])],
            "rival_iqr": [round(float(x), 3) for x in np.percentile(b, [25, 75])],
            "umbral": round(float(thr), 3), "acierto_en_decididos": round(float(ok / (len(a) + len(b))), 3),
            "n": [len(a), len(b)], "sin_decidir_con_estatura": len(und),
            "sin_decidir_ella": int(sum((r["m"] > thr) == taller_is_her for r in und))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", nargs="+")
    args = ap.parse_args()
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    from tennisbio.layout import dir_of
    rep = []
    for m in load_matches(cfg):
        if args.match and not any(s in m.id for s in args.match):
            continue
        try:
            rows = run_heights(dir_of(root, m, cfg), m.player.hand)
            r = {"match": m.id, **separation(rows), "planos": rows}
        except Exception as e:  # noqa: BLE001 — one match never stops the others
            r = {"match": m.id, "error": f"{type(e).__name__}: {e}"[:300]}
        print(json.dumps({k: v for k, v in r.items() if k != "planos"}, ensure_ascii=False), flush=True)
        rep.append(r)
    out = root / "capturas_diag"
    out.mkdir(parents=True, exist_ok=True)
    (out / "diag_estatura.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
