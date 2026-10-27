"""Rebuild the report, the export and the audit from what the PC already analysed, without
analysing any video again (1-2 min): every change of the web can be seen without re-running the
pipeline. Uses the test folder (<output>/_smoke) and the practice videos (<output>/entrenamiento).

    uv run python scripts/rebuild_report.py [--player <id>] [--out-name _smoke]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.catalog import load_player, trial_match  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default=None, help="id de config/players/<id>.yaml (por defecto `player` de la configuración)")
    ap.add_argument("--out-name", default="_smoke", help="carpeta de la salida (p. ej. _poc9_largo)")
    args = ap.parse_args()
    if args.player is None:
        from tennisbio.config import default_player
        args.player = default_player()
    t0 = time.time()
    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output")) / args.out_name
    return rebuild(out_root, args.player, t0)


def rebuild(out_root: Path, player: str | None = None, t0: float | None = None,
            done: str = "sin volver a analizar vídeo") -> int:
    """Report, export and audit of every analysed match folder in out_root (also used by
    scripts/recompute_measures.py after recomputing the measurements)."""
    t0 = time.time() if t0 is None else t0
    dirs = [d for d in sorted(out_root.iterdir()) if d.is_dir() and (d / "strokes.json").exists()] if out_root.exists() else []
    if not dirs:
        print(f"No hay nada analizado en {out_root}: lanza antes 2_prueba_rapida.bat")
        return 1
    if player is None:
        from tennisbio.config import default_player
        player = default_player()
    pl = load_player(player)
    from tennisbio.config import load_config
    cfg = load_config()
    matches = []
    for d in dirs:
        sc = d / "score.json"
        opp = (json.loads(sc.read_text(encoding="utf-8")).get("opponent") or "") if sc.exists() else ""
        matches.append(trial_match(d.name, Path(""), pl, cfg, match_dir=d, opponent=opp))
        print(f"Partido analizado: {d.name} ({len(json.loads((d / 'strokes.json').read_text(encoding='utf-8')))} golpes)")
    from tennisbio.report import build
    report = build(matches, out_root, out_root / "informe")
    print(f"Informe: {report}")
    from tennisbio.export import export
    exp = export(matches, out_root, out_root / "exportar", strokes_all=True)
    print(f"Vídeos y resumen PDF: {exp}")
    from tennisbio.cli import run_audit
    run_audit(out_root, report.parent, out_root / "auditoria")
    print(f"Hecho en {time.time() - t0:.0f} s, {done}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
