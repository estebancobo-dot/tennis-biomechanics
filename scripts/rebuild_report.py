"""Rebuild the report, the export and the audit from what the PC already analysed, without
analysing any video again (1-2 min): every change of the web can be seen without re-running the
pipeline. Uses the test folder (<output>/_smoke) and the practice videos (<output>/entrenamiento).

    uv run python scripts/rebuild_report.py [--player rybakina]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.catalog import Match, load_player  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default="rybakina")
    args = ap.parse_args()
    t0 = time.time()
    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output")) / "_smoke"
    dirs = [d for d in sorted(out_root.iterdir()) if d.is_dir() and (d / "strokes.json").exists()] if out_root.exists() else []
    if not dirs:
        print(f"No hay nada analizado en {out_root}: lanza antes 2_prueba_rapida.bat")
        return 1
    pl = load_player(args.player)
    matches = []
    for d in dirs:
        sc = d / "score.json"
        opp = (json.loads(sc.read_text(encoding="utf-8")).get("opponent") or "") if sc.exists() else ""
        matches.append(Match(d.name, Path(""), pl, opponent=opp))
        print(f"Partido analizado: {d.name} ({len(json.loads((d / 'strokes.json').read_text(encoding='utf-8')))} golpes)")
    from tennisbio.report import build
    report = build(matches, out_root, out_root / "informe")
    print(f"Informe: {report}")
    from tennisbio.export import export
    exp = export(matches, out_root, out_root / "exportar", strokes_all=True)
    print(f"Vídeos y resumen PDF: {exp}")
    from tennisbio.cli import run_audit
    run_audit(out_root, report.parent, out_root / "auditoria")
    print(f"Hecho en {time.time() - t0:.0f} s, sin volver a analizar vídeo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
