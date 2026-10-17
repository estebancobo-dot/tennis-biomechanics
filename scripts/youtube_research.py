"""Coach analysis videos from YouTube, to learn how professionals analyse and explain a forehand
(what they look at, in which order, with which words and on-screen graphics) and find what the
application is missing. Only for improving the application: nothing from these videos is ever used
as data of the player or shown in her report (requirement 6).

Runs on the user's PC (YouTube blocks downloads from the cloud), once, from the quick test. For
each video: its title, channel and length, what is said (automatic subtitles as plain text) and a
few small frames (one every few seconds) to see the graphics. The video itself is deleted.

    python scripts/youtube_research.py --out C:/tenis/output/investigacion [--max 24]
    python scripts/youtube_research.py --out C:/tenis/output/investigacion_14 --urls "https://youtu.be/A5jgd_CPohM ..."
        (videos the user chose: those only, no search)
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QUERIES = [
    "Rybakina forehand analysis", "Rybakina forehand technique breakdown", "Rybakina forehand slow motion",
    "WTA forehand technique analysis", "pro forehand biomechanics analysis", "modern forehand technique breakdown coach",
    "forehand footwork split step analysis", "forehand racket face lag analysis",
]
MAX_MIN = 25          # longer videos are interviews or whole matches


def ytdlp(*args, timeout=600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "yt_dlp", "--no-warnings", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def search(per_query: int) -> list[dict]:
    seen, out = set(), []
    for q in QUERIES:
        r = ytdlp("--flat-playlist", "--print", "%(id)s\t%(title)s\t%(channel)s\t%(duration)s", f"ytsearch{per_query}:{q}")
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 4 or parts[0] in seen:
                continue
            try:
                dur = float(parts[3])
            except ValueError:
                continue
            if 20 <= dur <= MAX_MIN * 60:
                seen.add(parts[0])
                out.append({"id": parts[0], "title": parts[1], "channel": parts[2], "duration_s": dur, "query": q})
    return out


def vtt_to_text(vtt: str) -> str:
    """Automatic subtitles repeat each line while it scrolls: keep each sentence once, with its minute."""
    out, last, t = [], "", "0:00"
    for line in vtt.splitlines():
        m = re.match(r"(\d+):(\d+):(\d+)\.\d+ -->", line)
        if m:
            h, mi, s = map(int, m.groups())
            t = f"{h * 60 + mi}:{s:02d}"
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:")) or line == last:
            continue
        out.append(f"[{t}] {line}")
        last = line
    return "\n".join(out)


def video_id(s: str) -> str | None:
    m = re.search(r"(?:youtu\.be/|v=|shorts/)([\w-]{11})", s) or re.fullmatch(r"([\w-]{11})", s.strip())
    return m.group(1) if m else None


def chosen(urls: str) -> list[dict]:
    """The videos the user chose, with their title, channel and length (no length limit: they asked for them)."""
    out = []
    for u in re.split(r"[\s,]+", urls.strip()):
        vid = video_id(u)
        if not vid or any(v["id"] == vid for v in out):
            continue
        r = ytdlp("--print", "%(id)s\t%(title)s\t%(channel)s\t%(duration)s", "--skip-download", f"https://www.youtube.com/watch?v={vid}")
        parts = (r.stdout.strip().splitlines() or [""])[0].split("\t")
        dur = float(parts[3]) if len(parts) >= 4 and parts[3].replace(".", "", 1).isdigit() else 0.0
        out.append({"id": vid, "title": parts[1] if len(parts) > 1 else vid, "channel": parts[2] if len(parts) > 2 else "",
                    "duration_s": dur, "chosen_by_user": True})
    return out


def one(v: dict, dest: Path, tmp: Path) -> dict:
    d = dest / v["id"]
    d.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={v['id']}"
    r = ytdlp("--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*,en,es.*,es", "--sub-format", "vtt",
              "-o", str(tmp / "%(id)s.%(ext)s"), url)
    subs = sorted(tmp.glob(f"{v['id']}*.vtt"))
    if subs:
        (d / "dicho.txt").write_text(vtt_to_text(subs[0].read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    v["subtitles"] = bool(subs)
    r = ytdlp("-f", "worst[height>=240][ext=mp4]/worst[ext=mp4]/worst", "-o", str(tmp / "%(id)s.video.%(ext)s"), url, timeout=900)
    vids = sorted(tmp.glob(f"{v['id']}.video.*"))
    n = 0
    if vids:
        # about 36 frames per video at most; the ones the user chose, about 90 (their graphics matter)
        every = max(3.0, v["duration_s"] / 90) if v.get("chosen_by_user") else max(6.0, v["duration_s"] / 36)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vids[0]), "-vf", f"fps=1/{every:.1f},scale=480:-2", "-q:v", "6",
                        str(d / "f_%03d.jpg")], timeout=900)
        n = len(list(d.glob("f_*.jpg")))
        v["frame_every_s"] = round(every, 1)
    else:
        v["video_error"] = (r.stderr or "")[-300:]
    v["frames"] = n
    for f in tmp.glob(f"{v['id']}*"):
        f.unlink(missing_ok=True)
    (d / "info.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=24)
    ap.add_argument("--per-query", type=int, default=6)
    ap.add_argument("--urls", default="", help="videos chosen by the user (YouTube links or ids, separated by spaces or commas)")
    args = ap.parse_args()
    dest = Path(args.out)
    dest.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        print("Falta ffmpeg en el PATH")
        return 1
    if args.urls.strip():
        vids = chosen(args.urls)
    else:
        print("Buscando vídeos de análisis de la derecha…", flush=True)
        vids = search(args.per_query)[: args.max]
    print(f"{len(vids)} vídeos encontrados", flush=True)
    done = []
    with tempfile.TemporaryDirectory() as t:
        for i, v in enumerate(vids, 1):
            print(f"  {i}/{len(vids)} {v['title'][:70]}", flush=True)
            try:
                done.append(one(v, dest, Path(t)))
            except Exception as e:                  # one video never stops the others
                v["error"] = str(e)[:300]
                done.append(v)
    (dest / "indice.json").write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for v in done if v.get("subtitles") or v.get("frames"))
    print(f"Hecho: {ok} de {len(done)} vídeos con texto o imágenes → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
