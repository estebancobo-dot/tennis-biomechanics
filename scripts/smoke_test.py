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
    report = build([match], out_root, out_root / "informe")
    from tennisbio.export import export
    exp = export([match], out_root, out_root / "exportar", strokes_all=True)
    if done:
        print(f"\nTotal {total / 60:.1f} min para {args.minutes:g} min de vídeo → partido de {full / 60:.0f} min "
              f"≈ {total * full / (args.minutes * 60) / 3600:.1f} h (estimación lineal)")
    print(f"Informe: {report}")
    print(f"Vídeos, montajes y resumen PDF: {exp}")


if __name__ == "__main__":
    main()
