"""Proof of concept (15-11, #304): can a cloud session download coaches' videos from YouTube?

YouTube refused this cloud's downloads («Sign in to confirm you're not a bot»), so the coaches' shorts needed the PC.
This tries, from wherever it runs (a Kaggle session), the three things scripts/youtube_research.py needs for each
video: its title and length, its subtitles and a small video stream for frames. It reports each one, with the first
line of the error when it fails. Nothing of the videos is kept.

    python -m tennisbio.infra.poc_youtube --urls "https://youtu.be/ID1 https://youtu.be/ID2" --salida poc.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings"]


def _run(args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    try:
        p = subprocess.run([*YTDLP, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:  # esperado: a download that cannot start or hangs is a result
        return 1, "", f"ERROR: {e}"


def first_error(err: str) -> str:
    lines = [l for l in err.splitlines() if "ERROR" in l] or err.strip().splitlines()[-1:]
    return (lines[0] if lines else "")[:300]


def video_id(url: str) -> str | None:
    m = re.search(r"(?:youtu\.be/|v=|shorts/)([\w-]{11})", url)
    return m.group(1) if m else None


def try_one(url: str, tmp: Path) -> dict:
    vid = video_id(url) or url
    out: dict = {"id": vid}
    t0 = time.time()
    rc, so, se = _run(["--skip-download", "--print", "%(title)s\t%(duration)s", url])
    out["metadata"] = rc == 0 and bool(so.strip())
    if not out["metadata"]:
        out["metadata_error"] = first_error(se)
    rc, so, se = _run(["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*,en", "--sub-format",
                       "vtt", "-o", str(tmp / "%(id)s.%(ext)s"), url])
    out["subtitles"] = bool(list(tmp.glob(f"{vid}*.vtt")))
    if not out["subtitles"] and rc != 0:
        out["subtitles_error"] = first_error(se)
    rc, so, se = _run(["-f", "bv*/b", "-S", "res:360,+size", "-o", str(tmp / "%(id)s.video.%(ext)s"), url], timeout=600)
    got = [f for f in tmp.glob(f"{vid}.video.*") if not f.name.endswith(".part")]
    out["video"] = bool(got)
    out["video_mb"] = round(got[0].stat().st_size / 2 ** 20, 2) if got else 0.0
    if not got:
        out["video_error"] = first_error(se)
    for f in tmp.glob(f"{vid}*"):
        f.unlink(missing_ok=True)
    out["seconds"] = round(time.time() - t0, 1)
    return out


def run(urls: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        rows = [try_one(u, Path(d)) for u in urls]
    rc, so, _ = _run(["--version"])
    ok = [r for r in rows if r["metadata"] and r["video"]]
    return {"prueba": "youtube", "yt_dlp": so.strip(), "videos": rows,
            "conclusion": (f"YouTube deja descargar desde aquí: {len(ok)} de {len(rows)} vídeos" if ok else
                           "YouTube no deja descargar desde aquí (hace falta el PC)")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args(argv)
    res = run([u for u in re.split(r"[\s,]+", a.urls.strip()) if u])
    Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(res["conclusion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
