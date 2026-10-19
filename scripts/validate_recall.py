"""Stroke recall benchmark (acceptance gate of every detection fix): ALL annotated strokes of the player
in F3Set-Tennis (train + val + test: 4 Rybakina matches, ~370 points, ~670 strokes of hers), followed
through the real match pipeline to the step where each one is lost.

For each match, the annotated points (6 s before, 3 s after) are downloaded from YouTube (only those
seconds), joined into one video (the "compilation") and analysed with the same stages as a full
match (tennisbio.pipeline.run); then tennisbio.validation.recall_eval places every annotated stroke
of hers in the stage outputs. Writes <root>/reports/recall_validation.json and .md.

    uv run python scripts/validate_recall.py --root C:\\tenis\\datasets
    uv run python scripts/validate_recall.py --root C:\\tenis\\datasets --max-points 25     (quick: 25 points per match)
    uv run python scripts/validate_recall.py --root C:\\tenis\\datasets --skip-run          (only re-evaluate)

Runs on the user's PC: YouTube refuses downloads from data centres. The compilations and stage outputs
are cached under <root>/f3set/recall/: re-running after a code change re-runs only what changed.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.validation import recall_eval as R  # noqa: E402
from tennisbio.validation.datasets import f3set_tennis  # noqa: E402


def download(yt_id: str, dest: Path, t0: float, t1: float) -> Path | None:
    """Only [t0, t1] seconds of the YouTube video (720p), cut at those times."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
           "--merge-output-format", "mp4", "-o", str(dest), "--download-sections", f"*{t0:.2f}-{t1:.2f}",
           "--force-keyframes-at-cuts", f"https://www.youtube.com/watch?v={yt_id}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        print(f"  {yt_id} {t0:.0f}-{t1:.0f} s: la descarga no termina en 10 min; se omite")
        return None
    if r.returncode or not dest.exists():
        print(f"  no se pudo descargar {yt_id} {t0:.0f}-{t1:.0f} s: {r.stderr.strip()[-200:]}")
        return None
    return dest


def normalise(src: Path, dest: Path, dur: float, fps: float) -> Path:
    """Same codec, size, frame rate and sound for every piece, so they join without re-encoding."""
    if not (dest.exists() and dest.stat().st_size > 0):
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", f"{dur:.3f}", "-r", f"{fps:.6f}",
                        "-vf", "scale=1280:720,setsar=1", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(dest)], check=True)
    return dest


def build_compilation(root: Path, name: str, yt_id: str, fps: float, segs: list[dict]) -> tuple[Path | None, list[dict]]:
    """The compilation video of one match and its segments with their offset in it (pieces that could not
    be downloaded are left out)."""
    from tennisbio.io.video import probe

    base = root / "f3set" / "recall"
    out = base / "videos" / f"{name}.mp4"
    plan_f = base / "videos" / f"{name}.json"
    key = [(s["src_t0"], s["src_t1"]) for s in segs]
    if out.exists() and plan_f.exists():
        plan = json.loads(plan_f.read_text(encoding="utf-8"))
        if plan.get("key") == key:
            return out, plan["segments"]
    parts, done = [], []
    for i, s in enumerate(segs):
        p = download(yt_id, base / "parts" / f"{name}_{s['src_t0']:.0f}_{s['src_t1']:.0f}.mp4", s["src_t0"], s["src_t1"])
        if p is None:
            continue
        n = normalise(p, base / "norm" / f"{name}_{s['src_t0']:.0f}_{s['src_t1']:.0f}.mp4", s["src_t1"] - s["src_t0"], fps)
        parts.append(n)
        done.append(dict(s))
        if (i + 1) % 10 == 0:
            print(f"  {name}: {i + 1}/{len(segs)} tramos descargados", flush=True)
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
    return out, done


def run_pipeline(video: Path, mid: str, player_id: str, opponent: str, out_dir: Path, force_fine: bool) -> list[str]:
    """All stages on the compilation, as for a full match; the fine pass's window lines are kept in
    ventanas_fine.log (the benchmark reads where each window went)."""
    from tennisbio import pipeline, stages  # noqa: F401  (registers the stages)
    from tennisbio.catalog import Match, load_player, surface_of
    from tennisbio.config import load_config

    cfg = load_config()
    match = Match(mid, video, load_player(player_id), opponent=opponent, surface=surface_of(mid.replace("_", " ")) or "dura")
    lines = []

    def log(msg):
        lines.append(str(msg))
        print(msg, flush=True)
    ctx = pipeline.Context(match, cfg, out_dir / mid, log=log)
    done = pipeline.run(ctx)
    if "fine" not in done and (force_fine or not (ctx.dir / "ventanas_fine.log").exists()):
        done += pipeline.run(ctx, names=["fine"], force=True)
    if "fine" in done:
        (ctx.dir / "ventanas_fine.log").write_text("\n".join(lines), encoding="utf-8")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--player", default="Rybakina", help="nombre tal como lo escribe F3Set")
    ap.add_argument("--player-id", default="rybakina", help="config/players/<id>.yaml")
    ap.add_argument("--splits", default="train,val,test")
    ap.add_argument("--matches", default="", help="solo los vídeos cuyo nombre contenga esto")
    ap.add_argument("--max-points", type=int, default=0, help="puntos por partido (0 = todos), repartidos por el partido")
    ap.add_argument("--pre", type=float, default=6.0)
    ap.add_argument("--post", type=float, default=3.0)
    ap.add_argument("--tol", type=float, default=0.2, help="tolerancia (s) para casar un golpe con el anotado")
    ap.add_argument("--skip-run", action="store_true", help="no ejecutar el pipeline: evaluar lo que ya hay")
    ap.add_argument("--force-fine", action="store_true")
    ap.add_argument("--no-click", dest="click", action="store_false",
                    help="sin el clic de identidad simulado (19-10: por defecto se simula, como en la aplicación)")
    args = ap.parse_args()
    root = Path(args.root)
    t_start = time.time()

    clips, videos = [], []
    for sp in args.splits.split(","):
        c, videos = f3set_tennis(root, sp.strip())
        clips += c
    yt = {v["video_name"]: v for v in videos}
    pts = R.player_points(clips, args.player)
    by_video = {}
    for p in pts:
        if args.matches.lower() in p["video"].lower():
            by_video.setdefault(p["video"], []).append(p)
    print(f"{sum(len(v) for v in by_video.values())} puntos anotados de {args.player} en {len(by_video)} partidos; "
          f"{sum(e['who'] == 'target' for v in by_video.values() for p in v for e in p['events'])} golpes suyos")

    out_dir = root / "f3set" / "recall" / "salidas"
    all_attr, all_ev, all_strokes, all_spans, all_runs, all_pspans, per_match, notes = [], [], [], [], [], [], [], []
    for k, (name, ps) in enumerate(sorted(by_video.items())):
        if args.max_points and len(ps) > args.max_points:
            ps = ps[:: max(1, len(ps) // args.max_points)][:args.max_points]
        if name not in yt:
            notes.append(f"{name}: sin identificador de YouTube en videos.csv")
            continue
        fps = float(yt[name].get("fps") or ps[0]["fps"])
        segs = R.plan_segments(ps, args.pre, args.post)
        mid = "recall_" + name.lower().replace("-", "_")[:60]
        vid = root / "f3set" / "recall" / "videos" / f"{name}.mp4"
        plan_f = vid.with_suffix(".json")
        if args.skip_run:
            if not plan_f.exists():
                notes.append(f"{name}: sin compilación (ejecutar sin --skip-run)")
                continue
            done_segs = json.loads(plan_f.read_text(encoding="utf-8"))["segments"]
        else:
            print(f"\n[{name}] {len(ps)} puntos en {len(segs)} tramos ({sum(s['src_t1'] - s['src_t0'] for s in segs) / 60:.0f} min)")
            vid, done_segs = build_compilation(root, name, yt[name]["yt_id"], fps, segs)
            if vid is None:
                notes.append(f"{name}: no se pudo descargar ningún tramo")
                continue
            if args.click:                # the user's one click per match, simulated from the annotations
                pick = R.simulated_pick(ps, done_segs)
                if pick:
                    from tennisbio.identity import PICK_FILE
                    (out_dir / mid).mkdir(parents=True, exist_ok=True)
                    (out_dir / mid / PICK_FILE).write_text(json.dumps(pick), encoding="utf-8")
            run_pipeline(vid, mid, args.player_id, ps[0]["opponent"], out_dir, args.force_fine)
        got = {pid for s in done_segs for pid in s["points"]}
        ps = [p for p in ps if p["id"] in got]
        if len(got) < sum(len(s["points"]) for s in segs):
            notes.append(f"{name}: {len(got)} de {sum(len(s['points']) for s in segs)} puntos descargados")
        events, spans = R.place_events(ps, done_segs)
        mdir = out_dir / mid
        if not (mdir / "manifest.json").exists():
            notes.append(f"{name}: el pipeline no dejó salidas")
            continue
        o = R.load_outputs(mdir)
        notes += [f"{name}: {n}" for n in o.notes]
        attr = R.attribute(events, o, args.tol)
        by_id = {p["id"]: p for p in ps}
        pspans = []
        for s in done_segs:
            for pid in s["points"]:
                p = by_id.get(pid)
                if p:
                    pspans.append({"t0": s["offset"] + p["a"] / p["fps"] - s["src_t0"],
                                   "t1": s["offset"] + p["b"] / p["fps"] - s["src_t0"], "near_is_target": p["near_is_target"]})
        sm = R.summarize(attr, events, o.strokes, spans, args.tol, o.runs, pspans)
        per_match.append({"match": name, "points": len(ps), "summary": sm})
        print(f"[{name}] recall {sm['total']['found']}/{sm['total']['gt']}; pérdidas: "
              + ", ".join(f"{R.STEPS[s]} {n}" for s, n in sm["steps"].items() if n and s not in R.FOUND))
        # all matches in one timeline (each match shifted 1e6 s)
        sh = 1e6 * k
        all_attr += [{**a, "t": a["t"] + sh, "match": name} for a in attr]
        all_ev += [{**e, "t": e["t"] + sh} for e in events]
        all_strokes += [{**s, "t": s["t"] + sh} for s in o.strokes]
        all_spans += [(a + sh, b + sh) for a, b in spans]
        all_runs += [{**r, "t0": r["t0"] + sh, "t1": r["t1"] + sh} for r in o.runs]
        all_pspans += [{**p, "t0": p["t0"] + sh, "t1": p["t1"] + sh} for p in pspans]

    total = R.summarize(all_attr, all_ev, all_strokes, all_spans, args.tol, all_runs, all_pspans) if all_attr else None
    res = {"player": args.player, "tol_s": args.tol, "points": sum(m["points"] for m in per_match),
           "matches": [m["match"] for m in per_match], "summary": total, "per_match": per_match, "notes": notes,
           "strokes": [{k: a.get(k) for k in ("match", "point", "label", "side", "kind", "step", "run_method", "identity_ok",
                                               "ball_seen", "pred_stroke", "dt")} for a in all_attr],
           "minutes": round((time.time() - t_start) / 60, 1)}
    rep = root / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "recall_validation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if total is None:
        print("Sin resultados: " + "; ".join(notes))
        return 1
    md = R.to_markdown(res)
    (rep / "recall_validation.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
