"""Coach analysis videos from YouTube, to learn how professionals analyse and explain a forehand
(what they look at, in which order, with which words and on-screen graphics) and find what the
application is missing. Only for improving the application: nothing from these videos is ever used
as data of the player or shown in her report (requirement 6).

Runs on the user's PC (YouTube blocks downloads from Claude's cloud), once, from the quick test, or on a
Kaggle CPU session (15-11, #304: queue job «investigar»; YouTube lets Kaggle download). For each video: its
title, channel and length, what is said (automatic subtitles as plain text; with --transcribir, when YouTube
refuses them, the speech transcribed from the audio by Whisper) and a few small frames (one every few
seconds) to see the graphics. The video itself is deleted.

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
    "{n} forehand analysis", "{n} forehand technique breakdown", "{n} forehand slow motion",
    "WTA forehand technique analysis", "pro forehand biomechanics analysis", "modern forehand technique breakdown coach",
    "forehand footwork split step analysis", "forehand racket face lag analysis",
]
MAX_MIN = 25          # longer videos are interviews or whole matches
WHISPER_MODEL = "small"
EVERY_S = 0.0             # --cada: one frame every so many seconds for the chosen videos (0: about 90 per video)   # multilingual (coaches in English or Spanish); int8 on the CPU


YTDLP = [sys.executable, "-m", "yt_dlp"]
# When YouTube changes and the installed yt-dlp gets no formats at all, try other YouTube clients, then the
# newest yt-dlp with its JavaScript runtime (deno, from PyPI), without touching the project's environment.
FALLBACKS = [
    [*YTDLP, "--extractor-args", "youtube:player_client=tv,mweb,android_vr,web_safari"],
    ["uvx", "--from", "yt-dlp[default]@latest", "--with", "deno", "yt-dlp"],
]


def ytdlp(*args, timeout=600, cmd=None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([*(cmd or YTDLP), "--no-warnings", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:   # uvx missing or a download that hangs
        return subprocess.CompletedProcess(args, 1, "", f"ERROR: {e}")


def search(per_query: int) -> list[dict]:
    seen, out = set(), []
    from tennisbio.config import player_surname
    for q in (x.format(n=player_surname()) for x in QUERIES):
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


def stamp(seconds: float) -> str:
    t = int(seconds)
    return f"{t // 60}:{t % 60:02d}"


def segments_to_text(segments) -> str:
    """Whisper's segments in the same form as the subtitles' text: one line per sentence, with its minute."""
    return "\n".join(f"[{stamp(s.start)}] {s.text.strip()}" for s in segments if s.text.strip())


_WHISPER: dict = {}


def transcribe(url: str, vid: str, tmp: Path) -> tuple[str, str]:
    """The speech of a video whose subtitles YouTube refused (429 from Kaggle, 15-11): its audio, transcribed by
    faster-whisper on the CPU. Returns (text, why it failed)."""
    r = ytdlp("-f", "ba/b", "-o", str(tmp / "%(id)s.audio.%(ext)s"), url, timeout=900)
    got = sorted(f for f in tmp.glob(f"{vid}.audio.*") if not f.name.endswith(".part"))
    if not got:
        return "", "audio: " + (r.stderr or "").strip()[-200:]
    try:
        import numpy as np
        # 15-11: the audio decoded by ffmpeg, not by faster-whisper's own PyAV call (Kaggle's newest PyAV refused its
        # «metadata_errors» argument for all 26 videos without subtitles)
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(got[0]), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                             capture_output=True, timeout=900).stdout
        audio = np.frombuffer(pcm, np.float32)
        if not audio.size:
            return "", "audio: ffmpeg no lo pudo leer"
        if "m" not in _WHISPER:
            from faster_whisper import WhisperModel
            _WHISPER["m"] = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        segments, info = _WHISPER["m"].transcribe(audio, vad_filter=True)
        text = segments_to_text(segments)
        return (f"(idioma {info.language})\n{text}" if text else ""), ("" if text else "sin voz")
    except Exception as e:  # esperado: no faster-whisper, or an audio it cannot read: said in the video's info
        return "", f"transcripción: {type(e).__name__}: {str(e)[:200]}"


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


def one(v: dict, dest: Path, tmp: Path, transcribe_speech: bool = False) -> dict:
    d = dest / v["id"]
    d.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={v['id']}"
    sub_args = ("--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*,en,es.*,es", "--sub-format", "vtt",
                "-o", str(tmp / "%(id)s.%(ext)s"), url)
    ytdlp(*sub_args)
    for cmd in FALLBACKS:
        if sorted(tmp.glob(f"{v['id']}*.vtt")):
            break
        ytdlp(*sub_args, cmd=cmd)
    subs = sorted(tmp.glob(f"{v['id']}*.vtt"))
    if subs:
        (d / "dicho.txt").write_text(vtt_to_text(subs[0].read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        v["text_source"] = "subtitulos"
    elif transcribe_speech:
        text, why = transcribe(url, v["id"], tmp)
        if text:
            (d / "dicho.txt").write_text(text, encoding="utf-8")
            v["text_source"] = f"voz transcrita (Whisper {WHISPER_MODEL})"
        else:
            v["transcription_error"] = why
    v["subtitles"] = (d / "dicho.txt").exists()
    # sort instead of filter: the smallest stream near 360p of whatever YouTube offers (video only is enough for
    # frames); a filter such as «worst[ext=mp4]» fails outright when YouTube offers only other containers
    vid_args = ("-f", "bv*/b", "-S", "res:360,+size", "-o", str(tmp / "%(id)s.video.%(ext)s"), url)
    errors = []
    for cmd in [None, *FALLBACKS]:
        r = ytdlp(*vid_args, timeout=900, cmd=cmd)
        vids = sorted(f for f in tmp.glob(f"{v['id']}.video.*") if not f.name.endswith(".part"))
        if vids:
            break
        errors.append((r.stderr or "").strip()[-200:])
    n = 0
    if vids:
        # about 36 frames per video at most; the ones the user chose, about 90 (their graphics matter)
        every = (EVERY_S or max(3.0, v["duration_s"] / 90)) if v.get("chosen_by_user") else max(6.0, v["duration_s"] / 36)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vids[0]), "-vf", f"fps=1/{every:.1f},scale=480:-2", "-q:v", "6",
                        str(d / "f_%03d.jpg")], timeout=900)
        n = len(list(d.glob("f_*.jpg")))
        v["frame_every_s"] = round(every, 1)
    else:
        v["video_error"] = " | ".join(errors)[-700:]
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
    ap.add_argument("--transcribir", action="store_true", help="no subtitles: transcribe the speech (faster-whisper)")
    ap.add_argument("--cada", type=float, default=0.0, help="one frame every so many seconds (to study on-screen graphics)")
    args = ap.parse_args()
    global EVERY_S
    EVERY_S = max(0.0, args.cada)
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
                done.append(one(v, dest, Path(t), args.transcribir))
            except Exception as e:                  # esperado: one video never stops the others
                v["error"] = str(e)[:300]
                done.append(v)
    (dest / "indice.json").write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for v in done if v.get("subtitles") or v.get("frames"))
    print(f"Hecho: {ok} de {len(done)} vídeos con texto o imágenes → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
