"""Side view of her forehand from practice videos on YouTube (separate, marked section of the report).

Runs on the user's PC (YouTube blocks downloads from the cloud) from the quick and medium tests,
incrementally: each video is downloaded and analysed once; a larger --max-videos / --max-seconds
only adds what is missing. For each video: the first --max-seconds are kept (720p, 30 fps), split
into camera shots, the player (the largest person: the camera follows her) is tracked, her strokes
found (wrist swing + sound), the camera angle of each stroke decided and, for the forehands filmed
from the side, the side-view measurements taken (tennisbio.practice). Each stroke keeps a short clip
with the skeleton drawn, for the report.

    python scripts/practice_videos.py --out C:/tenis/output/entrenamiento [--max-videos 2] [--max-seconds 90]

Nothing here is match data: tennisbio.report shows it on its own screen, marked as practice."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import practice  # noqa: E402
from tennisbio.catalog import load_player  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.io.video import open_capture  # noqa: E402
from tennisbio.racket import pick_racket, racket_from_polygon  # noqa: E402
from tennisbio.render import draw_pose, draw_racket  # noqa: E402
from tennisbio.scenes import detect_boundaries, frame_features  # noqa: E402
from tennisbio.skeleton import Skeleton  # noqa: E402

# searches for the player's practice videos ({n}: her surname, from config/players/<id>.yaml)
QUERIES = ["{n} practice", "{n} practice court level", "{n} training forehand",
           "{n} practice session forehand", "{n} forehand side view", "{n} hitting practice"]
EXCLUDE = (" vs ", " vs.", " v ", "highlights", "interview", "press conference", "full match", "match point", "reaction")
FORMAT = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[height<=720]/b"   # as validate_f3set (works on the PC)
MIN_SHOT_S = 2.5
VERSION = 5          # of the analysis: a video analysed by an older version is analysed again (pose kept in cache)
                     # 5: RTMW3D depth decoded with its own bins (pose.wholebody3d): the *_3d_* measures change


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ytdlp(*args, timeout=900):
    return subprocess.run([sys.executable, "-m", "yt_dlp", "--no-warnings", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def search(per_query: int, surname: str) -> list[dict]:
    seen, out = set(), []
    for q in (x.format(n=surname.capitalize()) for x in QUERIES):
        r = ytdlp("--flat-playlist", "--print", "%(id)s\t%(title)s\t%(channel)s\t%(duration)s", f"ytsearch{per_query}:{q}", timeout=300)
        for line in r.stdout.splitlines():
            p = line.split("\t")
            if len(p) < 4 or p[0] in seen:
                continue
            t = f" {p[1].lower()} "
            try:
                dur = float(p[3])
            except ValueError:
                continue
            if surname.lower() in t and not any(x in t for x in EXCLUDE) and 30 <= dur <= 40 * 60:
                seen.add(p[0])
                out.append({"id": p[0], "title": p[1], "channel": p[2], "duration_s": dur, "query": q,
                            "url": f"https://www.youtube.com/watch?v={p[0]}"})
    return out


def curated(player: str) -> list[dict]:
    """The videos chosen by hand for their camera (config/practice_videos.yaml), in order of value."""
    import yaml

    f = Path(__file__).resolve().parents[1] / "config" / "practice_videos.yaml"
    if not f.exists():
        return []
    out = []
    for e in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get(player) or []:
        e = dict(e)
        e["url"] = f"https://www.youtube.com/watch?v={e['id']}"
        e.setdefault("start", 0)
        e["duration_s"] = float(e.get("end", 0) - e["start"]) if e.get("end") else 1e9      # known after the download
        e["query"] = "lista elegida"
        out.append(e)
    return out


def download(v: dict, d: Path, seconds: float) -> Path | None:
    """`seconds` of the video from its start mark, at ≤720p and 30 fps (H.264 + sound); the download is deleted."""
    seg = d / "segmento.mp4"
    if seg.exists() and v.get("seconds_kept", 0) >= min(seconds, v["duration_s"]) - 1:
        return seg
    raw = [Path(v["local"])] if v.get("local") else sorted(d.glob("raw.*"))
    if not raw:
        r = ytdlp("-f", FORMAT, "--merge-output-format", "mp4", "-o", str(d / "raw.%(ext)s"), v["url"])
        raw = sorted(d.glob("raw.*"))
        if not raw:
            v["error"] = (r.stderr or r.stdout or "")[-300:]
            return None
    if v["duration_s"] >= 1e9:              # length known only now
        try:
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw[0])],
                                       capture_output=True, text=True).stdout.strip())
            v["duration_s"] = dur - v.get("start", 0)
        except ValueError:
            v["duration_s"] = seconds
    seconds = min(seconds, v["duration_s"])
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{v.get('start', 0):.2f}", "-i", str(raw[0]), "-t", f"{seconds:.0f}",
                        "-vf", "scale=-2:'min(720,ih)',fps=30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "1", str(seg)], capture_output=True)
    for f in raw if not v.get("local") else []:
        f.unlink(missing_ok=True)
    if r.returncode or not seg.exists():
        v["error"] = r.stderr.decode(errors="replace")[-300:]
        return None
    v["seconds_kept"] = seconds
    return seg


def shots(seg: Path) -> list[tuple[int, int, float]]:
    """Camera shots (start, end frame, fps) of at least MIN_SHOT_S seconds."""
    cap = open_capture(seg)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    hs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        hs.append(frame_features(cv2.resize(f, (160, 90)))[0])
    cap.release()
    if not hs:
        return []
    b = [0] + detect_boundaries(np.array(hs)) + [len(hs)]
    return [(s, e, fps) for s, e in zip(b[:-1], b[1:]) if (e - s) / fps >= MIN_SHOT_S]


def cut(seg: Path, s: int, e: int, fps: float, out: Path) -> Path:
    if not out.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s / fps:.3f}", "-i", str(seg), "-t", f"{(e - s) / fps:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
                       capture_output=True)
    return out


def write_clip(video: Path, run, sk: Skeleton, impact: int, out: Path, thumb: Path, half=1.0):
    """±1 s around the contact with her skeleton and the racket drawn (H.264, plays in any browser)."""
    fps = run.fps
    a, b = max(0, impact - int(half * fps)), min(len(run.img), impact + int(half * fps) + 1)
    cap = open_capture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, a)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w2, h2 = w - w % 2, h - h % 2
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w2}x{h2}", "-r", f"{fps:.3f}",
                          "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                          "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for f in range(a, b):
        ok, img = cap.read()
        if not ok:
            break
        img = draw_pose(img, run.img[f], sk, thickness=3)
        poly = pick_racket(run.rackets[f], run.img[f, sk["dom_wrist"]], 0.25 * run.height_px) if run.rackets else None
        obs = racket_from_polygon(poly, run.img[f, sk["dom_wrist"]]) if poly is not None else None
        if obs is not None:
            draw_racket(img, obs, 3)
        if f == impact:
            cv2.imwrite(str(thumb), cv2.resize(img, (360, int(360 * h / w))), [cv2.IMWRITE_JPEG_QUALITY, 80])
        p.stdin.write(np.ascontiguousarray(img[:h2, :w2]).tobytes())
    cap.release()
    p.stdin.close()
    p.wait()


def heads(run, sk: Skeleton, a: int, b: int) -> dict:
    out = {}
    for f in range(max(0, a), min(len(run.img), b)):
        if not run.rackets or not len(run.rackets[f]):
            continue
        poly = pick_racket(run.rackets[f], run.img[f, sk["dom_wrist"]], 0.25 * run.height_px)
        obs = racket_from_polygon(poly, run.img[f, sk["dom_wrist"]]) if poly is not None else None
        if obs is not None:
            out[f] = (float(obs.head[0]), float(obs.head[1]))
    return out


def frames_3d(video: Path, run, wb3d, loaded: int | None, impact: int) -> dict:
    """3D keypoints (RTMW3D) at the end of the backswing, ~70 ms before contact and at contact."""
    want = {"loaded": loaded, "pre": impact - max(2, int(round(0.07 * run.fps))), "impact": impact}
    out = {}
    cap = open_capture(video)
    for name, f in want.items():
        if f is None or not 0 <= f < len(run.boxes) or run.boxes[f] is None:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if ok:
            k3, sc, _ = wb3d(img, np.asarray(run.boxes[f], float))
            out[name] = (k3, sc)
    cap.release()
    return out


def analyse(v: dict, d: Path, seg: Path, clips: Path, hand: str, height_m: float, wb3d=None) -> list[dict]:
    from tennisbio.clip_pipeline import run_clip

    sk = Skeleton("coco17", hand)
    out = []
    for n, (s, e, fps) in enumerate(shots(seg)):
        shot = cut(seg, s, e, fps, d / f"plano_{n:02d}.mp4")
        try:
            run = run_clip(shot, d / f"plano_{n:02d}.npz", hand=hand, height_m=height_m, rackets=True,
                           init_mode="largest", log=lambda m: None)
        except Exception as ex:                      # one shot never stops the others
            log(f"    plano {n}: {str(ex)[:100]}")
            continue
        if run.tracked_frac < 0.5:
            continue
        if practice.faces_camera(run.conf, sk):
            # she faces the camera: left and right are swapped in the image, so the forehand/backhand
            # vote and the phases are computed on the mirrored image (as for the far player of a match)
            run = run_clip(shot, d / f"plano_{n:02d}.npz", hand=hand, height_m=height_m, rackets=True,
                           init_mode="largest", log=lambda m: None, side="far")
        for k, st in enumerate(run.strokes):
            i = st.impact_frame
            ph = {p: x["frame"] for p, x in st.phases.items()}
            view = practice.camera_view(run.img, run.conf, sk, ph.get("ready"), i, run.fps, ph.get("loaded"))
            rec = {"id": f"{v['id']}_{n:02d}_{k:02d}", "video_id": v["id"], "title": v["title"], "channel": v["channel"],
                   "url": v["url"], "t": round((s + i) / fps, 2), "view": view, "stroke": st.stroke,
                   "source": st.impact_source, "metrics": {}}
            if "audio" not in (st.impact_source or ""):
                # without the impact sound the contact frame is the wrist-speed peak alone, which in practice
                # videos often falls in the backswing (checked on the PC, 13-10): shown, never measured
                rec["unconfirmed"] = True
            elif view == "lateral" and st.stroke == "forehand":
                rec["metrics"] = practice.side_metrics(run.img, run.conf, sk, run.fps, i, ph, run.height_px, height_m,
                                                       heads(run, sk, i - int(0.8 * run.fps), i + 1))
            elif view == "frontal" and st.stroke == "forehand":
                rec["metrics"] = practice.front_metrics(run.img, run.conf, sk, i)
            bad = practice.implausible(rec["metrics"])
            if bad:                                   # contact frame or arm not trustworthy: nothing measured
                rec["discarded"], rec["metrics"] = bad, {}
            elif view in practice.D3_VIEWS and st.stroke == "forehand" and wb3d is not None and not rec.get("unconfirmed"):
                m3 = practice.metrics_3d(frames_3d(shot, run, wb3d, ph.get("loaded"), i), hand, height_m)
                bad3 = practice.implausible(m3)
                if bad3:                              # the 3D estimate of this stroke is not credible
                    rec["discarded_3d"] = bad3
                else:
                    rec["metrics"].update(m3)
            clip, th = clips / f"{rec['id']}.mp4", clips / f"{rec['id']}.jpg"
            try:
                write_clip(shot, run, sk, i, clip, th)
                rec["clip"], rec["thumb"] = clip.name, th.name if th.exists() else None
            except Exception as ex:
                log(f"    clip {rec['id']}: {str(ex)[:100]}")
            out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-videos", type=int, default=2)
    ap.add_argument("--max-seconds", type=float, default=90)
    ap.add_argument("--per-query", type=int, default=6)
    ap.add_argument("--player", default=None, help="id de config/players/<id>.yaml (por defecto `player` de la configuración)")
    ap.add_argument("--file", help="analizar un vídeo local en vez de buscar (pruebas)")
    ap.add_argument("--search", action="store_true", help="buscar en YouTube si no hay lista elegida (config/practice_videos.yaml)")
    args = ap.parse_args()
    if args.player is None:
        from tennisbio.config import default_player
        args.player = default_player()
    out = Path(args.out)
    clips = out / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        log("Falta ffmpeg en el PATH")
        return 1
    cfg = load_config()
    from tennisbio.pose.backend import set_device
    set_device(cfg.get("device"))
    pl = load_player(args.player)
    wb3d = None
    from tennisbio.config import resolve_path
    hp = resolve_path((cfg.get("racket_face") or {}).get("hand3d_onnx"))
    if hp is not None and hp.exists():
        try:
            from tennisbio.pose.wholebody3d import WholeBody3D
            wb3d = WholeBody3D(str(hp), cfg.get("device", "cpu"))
        except Exception as e:                      # no 3D: the side and front views still work
            log(f"AVISO: sin pose 3D ({str(e)[:100]})")
    idx = out / "videos.json"
    vids = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else []
    if args.file and not vids:
        f = Path(args.file)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                   capture_output=True, text=True).stdout.strip() or 0)
        vids = [{"id": "local_" + f.stem[:20].replace(" ", "_"), "title": f.stem, "channel": "local", "duration_s": dur,
                 "url": f.resolve().as_uri(), "local": str(f)}]
        idx.write_text(json.dumps(vids, ensure_ascii=False, indent=1), encoding="utf-8")
    chosen = curated(args.player)
    known = {v["id"] for v in vids}
    if chosen and not args.file:          # the chosen list first (cameras checked by eye), keeping what was analysed
        vids = [v for v in vids if v["id"] in {c["id"] for c in chosen}] + [c for c in chosen if c["id"] not in known]
        vids.sort(key=lambda v: [c["id"] for c in chosen].index(v["id"]))
        idx.write_text(json.dumps(vids, ensure_ascii=False, indent=1), encoding="utf-8")
    if not vids and args.search:
        log("Buscando vídeos de entrenamiento de la jugadora en YouTube…")
        vids = search(args.per_query, pl.name.split()[-1])
        idx.write_text(json.dumps(vids, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"{len(vids)} vídeos candidatos; se analizan {min(args.max_videos, len(vids))} ({args.max_seconds:.0f} s de cada uno)")
    done = 0
    for v in vids:
        if done >= args.max_videos:
            break
        d = out / v["id"]
        d.mkdir(exist_ok=True)
        res = d / "golpes.json"
        if (res.exists() and v.get("analysed_s", 0) >= min(args.max_seconds, v.get("duration_s", 1e9)) - 1
                and v.get("version") == VERSION):
            done += 1
            continue
        log(f"  {v['title'][:70]} ({v['channel']})")
        t0 = time.time()
        before = v.get("seconds_kept")
        seg = download(v, d, args.max_seconds)
        if seg is None:
            log(f"    no se pudo bajar: {v.get('error', '')[:150]}")
            continue
        if before is not None and v.get("seconds_kept") != before:     # a longer segment: the shots change
            for f in d.glob("plano_*"):
                f.unlink(missing_ok=True)
        strokes = analyse(v, d, seg, clips, pl.hand, pl.height_m, wb3d)
        res.write_text(json.dumps(strokes, ensure_ascii=False, indent=1), encoding="utf-8")
        v["analysed_s"] = v["seconds_kept"]
        v["version"] = VERSION
        v["strokes"] = len(strokes)
        v["lateral_forehands"] = sum(1 for s in strokes if s["view"] == "lateral" and s["stroke"] == "forehand" and not s.get("discarded"))
        v["discarded"] = sum(1 for s in strokes if s.get("discarded"))
        idx.write_text(json.dumps(vids, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"    {len(strokes)} golpes, {v['lateral_forehands']} derechas de lado medidas, {v['discarded']} descartadas "
            f"por valores imposibles ({time.time() - t0:.0f} s)")
        done += 1
    allst = []
    for v in vids:
        res = out / v["id"] / "golpes.json"
        if res.exists():
            allst += json.loads(res.read_text(encoding="utf-8"))
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M"), "player": pl.name,
               "videos": [v for v in vids if (out / v["id"] / "golpes.json").exists()],
               "strokes": allst, "views": practice.views_count(allst), "summary": practice.summarize(allst),
               "min_n": practice.MIN_N}
    (out / "entrenamiento.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    nl = sum(1 for s in allst if s["view"] == "lateral" and s["stroke"] == "forehand" and not s.get("discarded"))
    log(f"Hecho: {len(summary['videos'])} vídeos, {len(allst)} golpes, {nl} derechas de lado → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
