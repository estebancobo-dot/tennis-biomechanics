"""Download helpers for the public datasets used as ground truth.

- RacketVision (AAAI 2026, MIT): tennis broadcast clips with 5 racket keypoints per racket.
  Hugging Face dataset linfeng302/RacketVision. Keypoint order: 0 head tip, 1 throat,
  2 butt (handle end), 3 and 4 the two sides of the head.
- F3Set-Tennis (ICLR 2025): frame-exact contact events (player side, forehand/backhand,
  shot type, outcome) for 151 broadcast matches. Annotations come from the F3Set GitHub
  repository; the videos must be fetched from YouTube with the ids in videos.csv.
"""
import json
import urllib.request
from pathlib import Path

RV_BASE = "https://huggingface.co/datasets/linfeng302/RacketVision/resolve/main/tennis"
F3_RAW = "https://raw.githubusercontent.com/F3Set/F3Set/main/data/f3set-tennis"


def fetch(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    return dest


def racketvision_split(root: Path, split="test") -> dict:
    """COCO annotations of one split (images + ball/racket annotations with keypoints)."""
    return json.loads(fetch(f"{RV_BASE}/info/{split}_coco.json", root / "rv" / f"{split}_coco.json").read_text())


def racketvision_video(root: Path, match: str, clip: str) -> Path:
    return fetch(f"{RV_BASE}/videos/{match}_{clip}.mp4", root / "rv" / "videos" / f"{match}_{clip}.mp4")


def f3set_tennis(root: Path, split="test") -> tuple[list, list]:
    """(clips with events, video list rows) for F3Set-Tennis."""
    clips = json.loads(fetch(f"{F3_RAW}/{split}.json", root / "f3set" / f"{split}.json").read_text())
    rows = fetch(f"{F3_RAW}/videos.csv", root / "f3set" / "videos.csv").read_text().splitlines()
    head = rows[0].split(",")
    videos = [dict(zip(head, r.split(","))) for r in rows[1:] if r]
    return clips, videos
