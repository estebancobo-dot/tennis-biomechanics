"""Training data for the learned stroke spotter (tennisbio.spotting), made on the PC: F3Set matches turned into
numbers, never frames (19-10, hybrid plan: the PC sees the video, the cloud session trains).

For each match: its annotated points are downloaded from YouTube (only those seconds), joined into one video
(the same compilation as scripts/validate_recall.py), the cheap pass runs on it (scenes, audio, court,
players), and <root>/spotting/<match>.npz keeps the features frame by frame and every annotated stroke of both
players (time, side, kind). Rybakina's 4 matches are the test split (never used to train); the others train.

    uv run python scripts/spotting_data.py --root C:\\tenis\\datasets [--matches 16] [--points 90] [--hours 10]

Stops cleanly after --hours (what is done stays; the next run goes on with the rest)."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import validate_recall as V  # noqa: E402
from tennisbio import spotting as S  # noqa: E402
from tennisbio.validation import recall_eval as R  # noqa: E402
from tennisbio.validation.datasets import f3set_tennis  # noqa: E402

CHEAP = ["probe", "scenes", "audio", "court", "players"]


def cheap_pass(video: Path, mid: str, out_dir: Path) -> Path:
    from tennisbio import pipeline, stages  # noqa: F401  (registers the stages)
    from tennisbio.catalog import Match, load_player
    from tennisbio.config import load_config

    ctx = pipeline.Context(Match(mid, video, load_player("rybakina")), load_config(), out_dir / mid, log=lambda m: print(m, flush=True))
    pipeline.run(ctx, names=CHEAP)
    return out_dir / mid


def export(dest: Path, mdir: Path, events: list[dict], spans: list, name: str, split: str):
    f = S.build_features(mdir)
    ev = [e for e in events if e.get("side") in S.SIDES]
    np.savez_compressed(dest, X=f["X"].astype(np.float16), fps=f["fps"], name=name, split=split,
                        ev_t=np.array([e["t"] for e in ev], np.float32),
                        ev_side=np.array([S.SIDES.index(e["side"]) for e in ev], np.int8),
                        ev_kind=np.array([S.KINDS.index(S.KIND_OF.get(e["kind"], "other")) for e in ev], np.int8),
                        spans=np.array(spans, np.float32).reshape(-1, 2))
    return len(ev), len(f["X"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--test-player", default="Rybakina")
    ap.add_argument("--matches", type=int, default=16, help="partidos de entrenamiento (sin la jugadora de prueba)")
    ap.add_argument("--points", type=int, default=90, help="puntos por partido de entrenamiento, repartidos")
    ap.add_argument("--hours", type=float, default=10.0)
    args = ap.parse_args()
    root = Path(args.root)
    t_end = time.time() + args.hours * 3600
    clips, videos = [], []
    for sp in ("train", "val", "test"):
        c, videos = f3set_tennis(root, sp)
        clips += c
    yt = {v["video_name"]: v for v in videos}
    by_video = {}
    for p in R.all_points(clips):
        by_video.setdefault(p["video"], []).append(p)
    pl = args.test_player.lower()
    test = sorted(v for v, ps in by_video.items() if pl in (ps[0]["near_name"] + ps[0]["far_name"]).lower())
    train = sorted((v for v in by_video if v not in test and v in yt), key=lambda v: -len(by_video[v]))[:args.matches]
    dest = root / "spotting"
    dest.mkdir(parents=True, exist_ok=True)
    done = []
    for name in test + train:
        if time.time() > t_end:
            print(f"Tiempo agotado: quedan partidos para la próxima vez", flush=True)
            break
        split = "test" if name in test else "train"
        out = dest / f"{name}.npz"
        if out.exists():
            done.append(name)
            continue
        ps = by_video[name]
        if split == "train" and len(ps) > args.points:
            ps = ps[:: max(1, len(ps) // args.points)][:args.points]
        fps = float(yt[name].get("fps") or ps[0]["fps"])
        segs = R.plan_segments(ps, 6.0, 3.0)
        print(f"\n[{name}] ({split}) {len(ps)} puntos en {len(segs)} tramos", flush=True)
        try:
            vid, segs_done = V.build_compilation(root, name, yt[name]["yt_id"], fps, segs)
            if vid is None:
                print(f"[{name}] sin vídeo", flush=True)
                continue
            if split == "test":
                mid = "recall_" + name.lower().replace("-", "_")[:60]
                mdir = cheap_pass(vid, mid, root / "f3set" / "recall" / "salidas")
            else:
                mid = "spot_" + name.lower().replace("-", "_")[:60]
                mdir = cheap_pass(vid, mid, root / "f3set" / "spotting" / "salidas")
            got = {pid for s in segs_done for pid in s["points"]}
            events, spans = R.place_events([p for p in ps if p["id"] in got], segs_done)
            n_ev, n_fr = export(out, mdir, events, spans, name, split)
            print(f"[{name}] {n_ev} golpes anotados, {n_fr} fotogramas → {out.name}", flush=True)
            done.append(name)
        except Exception as e:  # noqa: BLE001 — one broken match never stops the others
            print(f"[{name}] error: {type(e).__name__}: {e}"[:400], flush=True)
    (dest / "indice.json").write_text(json.dumps({"test": test, "train": train, "done": done}, indent=1), encoding="utf-8")
    print(f"\nHechos {len(done)} de {len(test) + len(train)} partidos ({len(test)} de prueba).", flush=True)


if __name__ == "__main__":
    main()
