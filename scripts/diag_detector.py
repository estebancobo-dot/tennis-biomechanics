"""What the learned stroke detector saw around given moments of a match (12-11, B4: on Osaka three near serves of
Rybakina were missed, all 1.5-2.5 s after the main camera came back, while F3Set's near serves are found at 97 %).
Recomputes the detector's inputs and probabilities exactly as the spotting stage does (no file of the match is
written), and for each time t: every 0.1 s from t-4 to t+2, the play flag (main camera and court), whether the near
and the far player are present in the features, the near and far serve probabilities and the strongest class; plus
the main-camera shot and the court segment around t. Writes <output>/capturas_diag/diag_detector_<match>.json.

    uv run python scripts/diag_detector.py --match f43dd2 --t 2096.0 1984.0 3856.8"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import layout, pipeline, stages  # noqa: E402
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--t", type=float, nargs="+", required=True)
    a = ap.parse_args()
    cfg = load_config()
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    rep = {}
    for m in load_matches(cfg):
        d = layout.dir_of(out, m, cfg)
        if a.match.lower() not in str(d).lower() and a.match.lower() not in m.id.lower():
            continue
        from tennisbio.skeleton import Skeleton
        from tennisbio.spotting import (CLASSES, FEATURE_DIM, PERSON_DIM, build_features, fit_features, model_meta,
                                        predict_onnx, sound_flux_stream)
        ctx = pipeline.Context(m, cfg, d, log=lambda *_: None)
        onnx = stages._spotter_path(cfg)
        meta = model_meta(onnx)
        F = int(meta.get("feature_dim", FEATURE_DIM))
        dd = stages._players(ctx)
        sk = Skeleton("coco17", m.player.hand)
        court = stages._read(ctx.path("court.json")) if ctx.path("court.json").exists() else {}
        tracks, track = stages._audio_tracks(ctx, dd, sk, court)
        onsets = np.array(tracks[track].get("t", [])) if tracks else np.zeros(0)
        feats = build_features(ctx.dir, m.player.hand, video=ctx.video if F >= FEATURE_DIM else None, onsets=onsets,
                               flux=sound_flux_stream)
        fps = float(feats["fps"])
        X = feats["X"]
        play = X[:, -1] > 0
        from tennisbio.ball_features import BALL_DIM
        ball = bool(meta.get("ball")) or F == FEATURE_DIM + BALL_DIM
        if ball:
            from tennisbio.ball_features import cached_track, features as ball_feats
            tr = cached_track(ctx.dir, ctx.video, lambda: stages._ball_tracker(ctx), key=stages.ball_track_key(cfg))
            X = np.concatenate([X, ball_feats(tr, len(X), fps)], axis=1)
        X = fit_features(X, F) if not ball else X
        sp = stages._spotter(cfg)
        prob = predict_onnx(onnx, X, chunk=int(sp.get("chunk", 4096)), overlap=int(sp.get("overlap", 64)))
        ci = {c: i for i, c in enumerate(CLASSES)}
        present = [54, PERSON_DIM + 54]          # the «seen» flag of the near and the far player (spotting._person)
        sc = stages._read(ctx.path("scenes.json")) or {}
        sfps = float(sc.get("fps") or 1.0)
        rows = {}
        for t in a.t:
            f0 = int(round(t * fps))
            line = []
            for f in range(max(0, f0 - int(4 * fps)), min(len(X), f0 + int(2 * fps) + 1)):
                p = prob[f]
                feet = X[f, 52:54] * np.array([6.0, 24.0])          # spotting._person: feet on the court / (6, 24) m
                line.append({"t": round(f / fps, 1), "juego": bool(play[f]),
                             "presentes": [round(float(X[f, i]), 2) for i in present],
                             # 12-11: who the «near player» is: feet on the court (m), height over the frame, mean
                             # keypoint confidence (a ball kid at the back wall is near too)
                             "cerca_pies_m": [round(float(v), 1) for v in feet], "cerca_altura": round(float(X[f, 51]), 3),
                             "cerca_conf": round(float(X[f, 34:51].mean()), 2),
                             "saque_cerca": round(float(p[ci["near_serve"]]), 3), "saque_lejos": round(float(p[ci["far_serve"]]), 3),
                             "clase": CLASSES[int(np.argmax(p))], "p": round(float(np.max(p)), 3)})
            shot = [[round(s["start"] / sfps, 1), round(s["end"] / sfps, 1), s.get("main_camera")]
                    for s in sc.get("shots", []) if s["start"] / sfps <= t + 2 and s["end"] / sfps >= t - 4]
            segs = [[round(o["start"] / sfps, 1), round(o["end"] / sfps, 1), o.get("H") is not None]
                    for o in (court or {}).get("shots", []) if o["start"] / sfps <= t + 2 and o["end"] / sfps >= t - 4]
            rows[str(t)] = {"planos": shot, "pista": segs, "linea": line}
        rep[m.id] = {"fps": fps, "rasgos": int(X.shape[1]), "presentes": ["cerca", "lejos"], "momentos": rows}
        break
    dst = out / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / f"diag_detector_{a.match}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
