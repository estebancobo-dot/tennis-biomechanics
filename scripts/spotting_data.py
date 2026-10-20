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


BOT = ("confirm you", "cookies", "Sign in", "429", "Too Many Requests")


def full_video(root: Path, yt_id: str, t_end: float) -> Path | None:
    """The whole match once (480p, a few hundred MB), not one download per point: YouTube blocked the PC after
    ~1200 short downloads (20-10, «Sign in to confirm you're not a bot»). Pauses between requests; on that block,
    the browser's own YouTube session is tried (cookies of Firefox, Edge or Chrome, read by yt-dlp) and then it
    waits 30 min and tries again, while time is left."""
    import subprocess

    dest = root / "f3set" / "spotting" / "full" / f"{yt_id}.mp4"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]",
            "--merge-output-format", "mp4", "--sleep-requests", "2", "--retries", "5", "-o", str(dest),
            f"https://www.youtube.com/watch?v={yt_id}"]
    while time.time() < t_end:
        for extra in ([], ["--cookies-from-browser", "firefox"], ["--cookies-from-browser", "edge"],
                      ["--cookies-from-browser", "chrome"]):
            try:
                r = subprocess.run(base[:4] + extra + base[4:], capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=3600)
            except subprocess.TimeoutExpired:
                print(f"  {yt_id}: la descarga no termina en 1 h", flush=True)
                return None
            if r.returncode == 0 and dest.exists():
                print(f"  {yt_id}: vídeo descargado ({dest.stat().st_size / 1e6:.0f} MB)" + (f" con {extra[-1]}" if extra else ""), flush=True)
                return dest
            err = (r.stderr or "").strip()[-300:]
            if not any(b in err for b in BOT):
                print(f"  {yt_id}: no se pudo descargar: {err}", flush=True)
                return None
        print(f"  {yt_id}: YouTube bloquea las descargas; espero 30 min y lo intento otra vez", flush=True)
        time.sleep(1800)
    return None


def local_compilation(root: Path, name: str, src: Path, fps: float, segs: list[dict]):
    """The same compilation as validate_recall.build_compilation, cut from the local whole video."""
    import subprocess

    from tennisbio.io.video import probe

    base = root / "f3set" / "spotting"
    out, plan_f = base / "videos" / f"{name}.mp4", base / "videos" / f"{name}.json"
    key = [(s["src_t0"], s["src_t1"]) for s in segs]
    if out.exists() and plan_f.exists() and json.loads(plan_f.read_text(encoding="utf-8")).get("key") == key:
        return out, json.loads(plan_f.read_text(encoding="utf-8"))["segments"]
    parts, done = [], []
    for s in segs:
        n = base / "norm" / f"{name}_{s['src_t0']:.0f}_{s['src_t1']:.0f}.mp4"
        n.parent.mkdir(parents=True, exist_ok=True)
        if not (n.exists() and n.stat().st_size > 0):
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['src_t0']:.3f}", "-i", str(src),
                                "-t", f"{s['src_t1'] - s['src_t0']:.3f}", "-r", f"{fps:.6f}", "-vf", "scale=1280:720,setsar=1",
                                "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac",
                                "-ar", "48000", "-ac", "2", str(n)], capture_output=True)
            if r.returncode or not n.exists():
                continue
        parts.append(n)
        done.append(dict(s))
    if not parts:
        return None, []
    off = 0.0
    for s, n in zip(done, parts):
        s["offset"] = round(off, 4)
        off += probe(n).duration
    lst = base / "videos" / f"{name}.txt"
    lst.parent.mkdir(parents=True, exist_ok=True)
    lst.write_text("".join(f"file '{n.resolve().as_posix()}'\n" for n in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    plan_f.write_text(json.dumps({"key": key, "segments": done}, indent=1), encoding="utf-8")
    for n in parts:                          # the pieces are in the compilation now
        n.unlink(missing_ok=True)
    return out, done


def cheap_pass(video: Path, mid: str, out_dir: Path, fps: float | None = None) -> Path:
    from tennisbio import pipeline, stages  # noqa: F401  (registers the stages)
    from tennisbio.catalog import Match, load_player
    from tennisbio.config import load_config

    cfg = load_config()
    if fps:                               # the spotter's own frame rate (a swing lasts 2-3 frames at 10 fps)
        cfg = {**cfg, "cheap_pass": {**cfg["cheap_pass"], "fps": fps}}
    ctx = pipeline.Context(Match(mid, video, load_player("rybakina")), cfg, out_dir / mid, log=lambda m: print(m, flush=True))
    pipeline.run(ctx, names=CHEAP)
    return out_dir / mid


def export(dest: Path, mdir: Path, events: list[dict], spans: list, name: str, split: str, video: Path | None = None):
    f = S.build_features(mdir, video=video)
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
    ap.add_argument("--fps", type=float, default=0, help="fps de la pasada barata para el detector (0 = la de la configuración); "
                                                            "con otro valor, carpetas y ficheros aparte (sufijo _<fps>fps)")
    args = ap.parse_args()
    if not args.fps:     # the cycle script that launched this may predate its `fps:` line (it is read once per run)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from pc_requests import param             # the request file may hold a queue of blocks («---»)
        args.fps = float(param("fps", "entreno") or 0)
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
    tag = f"_{int(args.fps)}fps" if args.fps else ""
    dest = root / f"spotting{tag}"
    dest.mkdir(parents=True, exist_ok=True)
    done = []
    for name in test + train:
        if time.time() > t_end:
            print(f"Tiempo agotado: quedan partidos para la próxima vez", flush=True)
            break
        split = "test" if name in test else "train"
        out = dest / f"{name}.npz"
        if out.exists():
            with np.load(out) as z:
                ok = len(z["ev_t"]) >= 20
            if ok:
                done.append(name)
                continue
            out.unlink()                  # a failed download left an almost empty match: again
        ps = by_video[name]
        if split == "train" and len(ps) > args.points:
            ps = ps[:: max(1, len(ps) // args.points)][:args.points]
        fps = float(yt[name].get("fps") or ps[0]["fps"])
        segs = R.plan_segments(ps, 6.0, 3.0)
        print(f"\n[{name}] ({split}) {len(ps)} puntos en {len(segs)} tramos", flush=True)
        try:
            if split == "test":           # Rybakina's: already compiled by the recall benchmark (cached)
                vid, segs_done = V.build_compilation(root, name, yt[name]["yt_id"], fps, segs)
            else:
                src = full_video(root, yt[name]["yt_id"], t_end)
                vid, segs_done = local_compilation(root, name, src, fps, segs) if src else (None, [])
            if vid is None:
                print(f"[{name}] sin vídeo", flush=True)
                continue
            if split == "test":
                mid = "recall_" + name.lower().replace("-", "_")[:60] + tag
                mdir = cheap_pass(vid, mid, root / "f3set" / "recall" / "salidas", args.fps or None)
            else:
                mid = "spot_" + name.lower().replace("-", "_")[:60] + tag
                mdir = cheap_pass(vid, mid, root / "f3set" / "spotting" / "salidas", args.fps or None)
            got = {pid for s in segs_done for pid in s["points"]}
            events, spans = R.place_events([p for p in ps if p["id"] in got], segs_done)
            n_ev, n_fr = export(out, mdir, events, spans, name, split, vid)
            print(f"[{name}] {n_ev} golpes anotados, {n_fr} fotogramas → {out.name}", flush=True)
            if split == "train":          # the whole video is not needed any more (disk)
                (root / "f3set" / "spotting" / "full" / f"{yt[name]['yt_id']}.mp4").unlink(missing_ok=True)
            done.append(name)
        except Exception as e:  # noqa: BLE001 — one broken match never stops the others
            print(f"[{name}] error: {type(e).__name__}: {e}"[:400], flush=True)
    (dest / "indice.json").write_text(json.dumps({"test": test, "train": train, "done": done}, indent=1), encoding="utf-8")
    print(f"\nHechos {len(done)} de {len(test) + len(train)} partidos ({len(test)} de prueba).", flush=True)


if __name__ == "__main__":
    main()
