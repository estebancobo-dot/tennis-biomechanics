"""Prueba rápida de todo el pipeline con unos minutos de un partido real (antes de los 20 GB).

Corta un trozo del vídeo sin recodificar, ejecuta todas las etapas, genera el informe y estima
cuánto tardaría el partido entero.

    uv run python scripts/smoke_test.py "C:\\tenis\\videos\\partido1.mp4" --player rybakina --opponent "Aryna Sabalenka" --start 1800 --minutes 4
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import Match, load_player  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.io.video import probe  # noqa: E402
from tennisbio.report import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--player", default="rybakina")
    ap.add_argument("--opponent", default="", help="nombre del rival tal como sale en el marcador (para el OCR)")
    ap.add_argument("--start", type=float, default=1800, help="segundo de inicio del trozo")
    ap.add_argument("--minutes", type=float, default=4)
    args = ap.parse_args()

    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output")) / "_smoke"
    out_root.mkdir(parents=True, exist_ok=True)
    src = Path(args.video)
    full = probe(src).duration
    if args.start + args.minutes * 60 > full:          # short video: take the piece from its first third
        args.start = max(0.0, min(full * 0.3, full - args.minutes * 60))
    from tennisbio.catalog import ascii_id
    clip = out_root / f"{ascii_id(src.stem, 40)}_{int(args.start)}_{int(args.minutes)}m{src.suffix}"
    if not clip.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(args.start), "-i", str(src), "-t", str(args.minutes * 60),
                        "-c", "copy", str(clip)], check=True)
    match = Match(f"smoke_{ascii_id(src.stem, 40)}", clip, load_player(args.player), opponent=args.opponent)
    ctx = pipeline.Context(match, cfg, out_root / match.id)
    t0 = time.time()
    done = pipeline.run(ctx)
    total = time.time() - t0
    manifest = json.loads((ctx.dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"\nEtapas ejecutadas: {', '.join(done) or 'ninguna (ya estaba al día)'}")
    for name, m in manifest.items():
        print(f"  {name:11} {m['seconds']:7.1f} s  {m['summary']}")
    diagnostics(ctx, out_root / "diag")
    report = build([match], out_root, out_root / "informe")
    from tennisbio.export import export
    exp = export([match], out_root, out_root / "exportar", strokes_all=True)
    if done:
        print(f"\nTotal {total / 60:.1f} min para {args.minutes:g} min de vídeo → partido de {full / 60:.0f} min "
              f"≈ {total * full / (args.minutes * 60) / 3600:.1f} h (estimación lineal)")
    print(f"Informe: {report}")
    print(f"Vídeos, montajes y resumen PDF: {exp}")


def diagnostics(ctx, dest: Path, n_frames=8):
    """Small images and texts for Claude (uploaded with the logs; the video never is): the middle
    frame of a few main-camera shots with the fitted court drawn, and what the OCR reads there."""
    import cv2
    import numpy as np
    from tennisbio.court import LINES
    from tennisbio.stages import court_at, grab_frame

    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("*"):
        f.unlink()
    sc = json.loads(ctx.path("scenes.json").read_text(encoding="utf-8"))
    court = json.loads(ctx.path("court.json").read_text(encoding="utf-8")) if ctx.path("court.json").exists() else {}
    fps = sc["fps"]
    shots = [x for x in sc["shots"] if x["main_camera"]] or sc["shots"]
    shots = shots[:: max(1, len(shots) // n_frames)][:n_frames]
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except ImportError:
        ocr = None
    lines = []
    for k, x in enumerate(shots):
        t = (x["start"] + x["end"]) / 2 / fps
        fr = grab_frame(ctx.video, t)
        if fr is None:
            continue
        H, _ = court_at(court, t)
        img = fr.copy()
        if H is not None:
            for a, b in LINES.values():
                p = np.array([[*a, 1.0], [*b, 1.0]]) @ np.asarray(H).T
                p = p[:, :2] / p[:, 2:]
                cv2.line(img, tuple(int(v) for v in p[0]), tuple(int(v) for v in p[1]), (0, 255, 255), 2)
        cv2.putText(img, f"t={t:.1f}s main={x['main_camera']} court={'si' if H is not None else 'no'}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        small = cv2.resize(img, (960, int(960 * img.shape[0] / img.shape[1])))
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            (dest / f"plano_{k:02d}.jpg").write_bytes(buf.tobytes())
        if ocr is not None:
            res, _ = ocr(fr)
            lines.append(f"t={t:.1f}s: " + " | ".join(
                f"{txt} @({int(np.asarray(b)[:, 0].min())},{int(np.asarray(b)[:, 1].min())})" for b, txt, _ in (res or [])))
    # a few frames of every shot type (main camera or not) to see why shots are rejected
    for k, x in enumerate([x for x in sc["shots"] if not x["main_camera"]][:4]):
        fr = grab_frame(ctx.video, (x["start"] + x["end"]) / 2 / fps)
        if fr is not None:
            small = cv2.resize(fr, (640, int(640 * fr.shape[0] / fr.shape[1])))
            ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                (dest / f"otro_plano_{k:02d}.jpg").write_bytes(buf.tobytes())
    (dest / "ocr.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
