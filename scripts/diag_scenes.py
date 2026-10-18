"""Why a match video gives few main-camera minutes (18-10: Osaka – Rybakina, 18.9 of 62.6 min by colour): contact
sheets of the shots the court's colour takes for play but the lines do not confirm, next to the ones they do,
each labelled with its measures (court_lines, main_view, court_fraction, length), for Claude to look at.

    uv run python scripts/diag_scenes.py OUT_DIR [MATCH_DIR ...]
Without MATCH_DIR: every match folder of <output> with a scenes.json (not the automatic cycle's test runs)."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tennisbio.config import load_config  # noqa: E402
from tennisbio.io.video import frames_at, probe  # noqa: E402

W, H, COLS = 480, 270, 4


def _video(d: Path) -> Path | None:
    for f in (d / "source.mkv", d / "probe.json"):
        if f.name == "source.mkv" and f.exists() and (d / "source.json").exists():
            return f
        if f.name == "probe.json" and f.exists():
            p = json.loads(f.read_text(encoding="utf-8")).get("path")
            return Path(p) if p else None
    return None


def _sheet(items, out: Path, title: str):
    rows = max(1, (len(items) + COLS - 1) // COLS)
    img = np.full((rows * (H + 24) + 30, COLS * W, 3), 24, np.uint8)
    cv2.putText(img, title, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
    for i, (fr, label) in enumerate(items):
        r, c = divmod(i, COLS)
        y, x = 30 + r * (H + 24), c * W
        if fr is not None:
            img[y:y + H, x:x + W] = cv2.resize(fr, (W, H))
        cv2.putText(img, label, (x + 4, y + H + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (210, 230, 120), 1, cv2.LINE_AA)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 80])


def diag(d: Path, out: Path) -> dict:
    sc = json.loads((d / "scenes.json").read_text(encoding="utf-8"))
    fps, shots = float(sc["fps"]), sc["shots"]
    video = _video(d)
    if video is None or not video.exists():
        return {"match": d.name, "error": "sin vídeo"}
    info = probe(video)
    colour_only = sorted([s for s in shots if not s["main_camera"] and s["court_fraction"] >= 0.5],
                         key=lambda s: s["start"] - s["end"])[:16]
    main = sorted([s for s in shots if s["main_camera"]], key=lambda s: s["start"] - s["end"])[:8]
    res = {"match": d.name, "main_rule": sc.get("main_rule"), "fps": fps, "shots": len(shots),
           "main_min": round(sum(s["end"] - s["start"] for s in shots if s["main_camera"]) / fps / 60, 1),
           "colour_not_main_min": round(sum(s["end"] - s["start"] for s in shots if not s["main_camera"]
                                            and s["court_fraction"] >= 0.5) / fps / 60, 1),
           "probe": {k: getattr(info, k) for k in ("width", "height", "fps", "interlaced", "duration")}}
    out.mkdir(parents=True, exist_ok=True)
    for name, group in (("no_principal", colour_only), ("principal", main)):
        times = sorted(((s["start"] + s["end"]) / 2 / fps, s) for s in group)
        frames = dict((round(t, 3), f) for t, f in frames_at(info, [t for t, _ in times]))
        items = [(frames.get(round(t, 3)), f"{t / 60:.1f}min {(s['end'] - s['start']) / fps:.0f}s lines {s['court_lines']:.2f} "
                  f"view {s['main_view']:.2f} col {s['court_fraction']:.2f}") for t, s in times]
        _sheet(items, out / f"{d.name}_{name}.jpg", f"{d.name}: {name} ({len(items)})")
    return res


def main(argv):
    out = Path(argv[0])
    dirs = [Path(a) for a in argv[1:]]
    if not dirs:
        root = Path(load_config()["paths"]["output"])
        dirs = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_") and (p / "scenes.json").exists()]
    res = []
    for d in dirs:
        try:
            res.append(diag(d, out))
        except Exception as e:                   # noqa: BLE001 — one broken folder never stops the others
            res.append({"match": d.name, "error": f"{type(e).__name__}: {e}"[:300]})
        print(json.dumps(res[-1], ensure_ascii=False))
    (out / "diag_scenes.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
