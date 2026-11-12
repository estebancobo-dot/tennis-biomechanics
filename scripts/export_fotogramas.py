"""Frames of some exported stroke videos, for Claude to look at (12-12, R5: the skeleton colours were not found in some of
them although their series have the pose in every frame). For each name given (a part of the video's file name) the
frames at 30, 60 and 90 % of the video, as JPEG, in <output>/capturas_diag/ (expfoto_*.jpg: the PC uploads that
folder without its sub-folders). Reads only.

    uv run python scripts/export_fotogramas.py 0312430 0221547 0925800"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402


def main() -> None:
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    for part in sys.argv[1:]:
        for v in sorted(root.glob(f"exportar*/golpes/*{part}*.mp4"))[:3]:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                               capture_output=True, text=True, timeout=20)
            dur = float(r.stdout.strip() or 0)
            for f in (0.3, 0.6, 0.9):
                out = dst / f"expfoto_{v.parent.parent.name}_{v.stem[-7:]}_{int(f * 100)}.jpg"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{f * dur:.2f}", "-i", str(v), "-frames:v", "1",
                                "-vf", "scale=640:-2", "-q:v", "4", str(out)], capture_output=True, timeout=30)
                print(out.name, out.exists())


if __name__ == "__main__":
    main()
