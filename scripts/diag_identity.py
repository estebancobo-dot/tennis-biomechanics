"""Why a match's identity decides nothing (09-11: Rybakina-Pegula, 0 of 148 runs decided in the full analysis): for
runs spread over the match, the whole frame at the middle of the run (both players and the scoreboard are seen, so
whoever looks can tell who is near) with what the identity stage used there: the games read, the end changes they
give, the clothes group and its margin, the serve/return vote and the final answer. Sheets of 12 frames,
identidad_<match>_<k>.jpg, and diag_identidad.json with the counts. For Claude to look at; nothing is recomputed.

    uv run python scripts/diag_identity.py [OUT_DIR] [--match TEXT ...] [--n 24]
--match keeps the matches whose id contains any of the texts (default: every match).
Default OUT_DIR: <output>/capturas_diag (uploaded to pc-logs/capturas_diag)."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402

W, H_IMG = 480, 270


def label(r: dict, games) -> list[str]:
    vote = r.get("serve_vote", r.get("return_vote"))
    kind = "saque" if "serve_vote" in r else "resto" if "return_vote" in r else "-"
    return [f"t={r['start'] / r['_fps']:.0f}s juegos={games} cambios={r.get('end_changes')}",
            f"ropa g={r.get('cluster')} m={r.get('clothes_margin')} voto {kind}={vote}",
            f"cerca es ella={r.get('near_is_target')} ({r.get('method')}) fin={r.get('ends_said')}"]


def tile(frame, lines) -> np.ndarray:
    img = np.full((H_IMG + 64, W, 3), 20, np.uint8)
    if frame is not None:
        img[:H_IMG] = cv2.resize(frame, (W, H_IMG))
    for i, ln in enumerate(lines):
        cv2.putText(img, ln, (4, H_IMG + 18 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 230, 140), 1, cv2.LINE_AA)
    return img


def diag(m, cfg, root: Path, out: Path, n: int) -> dict:
    from tennisbio import layout
    from tennisbio import match_files as mf

    d = layout.dir_of(root, m, cfg)
    f = mf.at(d, "identity.json")
    if not f.exists():
        return {"match": m.id, "error": f"sin identity.json en {d}"}
    ident = json.loads(f.read_text(encoding="utf-8"))
    sf = mf.at(d, "score.json")
    score = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {}
    fps = float(ident.get("fps") or 1.0)
    runs = ident.get("runs", [])
    res = {"match": m.id, "dir": str(d), "runs": len(runs), "ends_base": ident.get("ends_base"),
           "click_by": ident.get("click_by"), "target_cluster": ident.get("target_cluster"),
           "votes": ident.get("votes"), "clothes": ident.get("clothes"),
           "decided": sum(r.get("near_is_target") is not None for r in runs),
           "methods": dict(Counter(str(r.get("method")) for r in runs)),
           "parity_by_cluster": {}, "votes_by_parity": {}}
    for r in runs:
        p = r.get("end_changes")
        if p is not None and r.get("cluster", -1) >= 0:
            k = f"g{r['cluster']}_par{p % 2}"
            res["parity_by_cluster"][k] = res["parity_by_cluster"].get(k, 0) + 1
        v = r.get("serve_vote", r.get("return_vote"))
        if p is not None and v is not None:
            k = f"par{p % 2}_voto{v}"
            res["votes_by_parity"][k] = res["votes_by_parity"].get(k, 0) + 1
    # the games read along the match (to see a misread set or games column)
    rd = score.get("readings", [])
    res["games_sequence"] = []
    last = None
    for x in rd:
        g = json.dumps(x.get("games"))
        if g != last:
            res["games_sequence"].append([round(float(x["t"])), x.get("games"), x.get("server")])
            last = g
    res["games_sequence"] = res["games_sequence"][:120]
    video = pipeline.Context(m, cfg, d).video
    if not Path(video).exists() or not runs:
        return {**res, "error": "sin vídeo" if runs else "sin planos"}
    idx = sorted({int(i) for i in np.linspace(0, len(runs) - 1, min(n, len(runs)))})
    tiles = []
    for i in idx:
        r = {**runs[i], "_fps": fps}
        t = (r["start"] + r["end"]) / 2 / fps
        sr = stages.score_at(score, t, max_age_s=150.0) if score else None
        tiles.append(tile(stages.grab_frame(Path(video), t), label(r, None if sr is None else sr.get("games"))))
    saved = []
    for k in range(0, len(tiles), 12):
        part = tiles[k:k + 12]
        while len(part) % 3:
            part.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(part[j:j + 3]) for j in range(0, len(part), 3)]
        p = out / f"identidad_{m.id[:40]}_{k // 12}.jpg"
        cv2.imwrite(str(p), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
        saved.append(p.name)
    return {**res, "images": saved}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--match", nargs="+")
    ap.add_argument("--n", type=int, default=24)
    args = ap.parse_args()
    cfg = load_config()
    root = Path(cfg.get("paths", {}).get("output", "output"))
    out = Path(args.out) if args.out else root / "capturas_diag"
    out.mkdir(parents=True, exist_ok=True)
    rep = []
    for m in load_matches(cfg):
        if args.match and not any(s in m.id for s in args.match):
            continue
        try:
            r = diag(m, cfg, root, out, args.n)
        except Exception as e:  # noqa: BLE001 — one broken match never stops the others
            r = {"match": m.id, "error": f"{type(e).__name__}: {e}"[:300]}
        print(json.dumps({k: v for k, v in r.items() if k != "games_sequence"}, ensure_ascii=False), flush=True)
        rep.append(r)
    (out / "diag_identidad.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
