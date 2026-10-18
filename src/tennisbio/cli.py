"""Command line: `tennisbio run --all`, `tennisbio run --match ID --stages fine`, `tennisbio status`."""
import argparse
from pathlib import Path

from .catalog import load_matches
from .config import load_config
from . import pipeline, stages

assert stages  # importing the module registers the stages


def _out_name(kind: str, pid: str | None, stroke: str, own: str | None) -> str:
    """informe_derecha / exportar_reves for the main player; with the player id for anyone else,
    so reports of different players or strokes never overwrite each other."""
    es = {"forehand": "derecha", "backhand": "reves", "overhead": "saque"}[stroke]
    return f"{kind}_{es}" if pid is None or pid == own else f"{kind}_{pid}_{es}"


def main(argv=None):
    try:
        return _main(argv)
    except KeyboardInterrupt:
        print("\nInterrumpido. Al relanzar se continúa donde se quedó.")
        return 130
    except Exception as e:                    # a message the user can act on, the detail in the log
        import traceback
        traceback.print_exc()
        print(f"\nERROR: {e}\nPasa a Claude el fichero de registro (.log) de C:\\tenis\\output.")
        return 1


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="tennisbio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="ejecuta lo que falte o haya cambiado")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--match", nargs="+")
    r.add_argument("--stages", nargs="+", choices=list(pipeline.STAGES))
    r.add_argument("--force", action="store_true", help="repetir aunque esté al día")
    s = sub.add_parser("status", help="estado de cada etapa por partido")
    s.add_argument("--match", nargs="+")
    rp = sub.add_parser("report", help="informe HTML con todos los partidos de un jugador")
    rp.add_argument("--player", help="id del jugador (config/players/<id>.yaml); por defecto, el del primer partido")
    rp.add_argument("--stroke", default="forehand", choices=["forehand", "backhand", "overhead"])
    rp.add_argument("--out", help="carpeta del informe (por defecto <output>/informe)")
    ex = sub.add_parser("export", help="vídeos MP4 por golpe, montajes por conclusión y resumen PDF")
    ex.add_argument("--player", help="id del jugador; por defecto, el del primer partido")
    ex.add_argument("--stroke", default="forehand", choices=["forehand", "backhand", "overhead"])
    ex.add_argument("--out", help="carpeta de salida (por defecto <output>/exportar_<golpe>)")
    ex.add_argument("--solo-montajes", action="store_true", help="exportar solo los golpes que salen en los montajes")
    ex.add_argument("--max", type=int, default=10, help="golpes por montaje")
    au = sub.add_parser("audit", help="comprueba las salidas reales contra los requisitos (capturas del informe incluidas)")
    au.add_argument("--report", help="carpeta del informe (por defecto <output>/informe_derecha)")
    au.add_argument("--stroke", default="forehand", choices=["forehand", "backhand", "overhead"])
    au.add_argument("--root", help="carpeta con las carpetas de los partidos (por defecto <output>)")
    au.add_argument("--out", help="carpeta de la auditoría (por defecto <output>/auditoria)")
    apl = sub.add_parser("app", help="la aplicación local: tennisbio app status|add|also|plan|work|… (ver app/cli.py)")
    apl.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.cmd == "app":                       # its own catalogue (the index): no matches.yaml needed
        from .app.cli import main as app_main
        return app_main(args.rest)

    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output"))
    matches = load_matches(cfg)
    own = matches[0].player.id if matches else None
    if args.cmd == "report":
        from .report import build
        pid = args.player or own
        mine = [m for m in matches if m.player.id == pid or m.extra.get("opponent_id") == pid]
        out = build(mine, out_root, Path(args.out) if args.out else out_root / _out_name("informe", pid, args.stroke, own),
                    args.stroke, player_id=pid)
        print(f"informe: {out}")
        return
    if args.cmd == "audit":
        return run_audit(Path(args.root) if args.root else out_root,
                         Path(args.report) if args.report else out_root / _out_name("informe", own, args.stroke, own),
                         Path(args.out) if args.out else out_root / "auditoria", args.stroke)
    if args.cmd == "export":
        from .export import export
        pid = args.player or own
        mine = [m for m in matches if m.player.id == pid or m.extra.get("opponent_id") == pid]
        out = Path(args.out) if args.out else out_root / _out_name("exportar", pid, args.stroke, own)
        export(mine, out_root, out, args.stroke, player_id=pid, reel_max=args.max, strokes_all=not args.solo_montajes)
        return
    if getattr(args, "match", None):
        unknown = set(args.match) - {m.id for m in matches}
        if unknown:
            print(f"AVISO: no están en config/matches.yaml: {', '.join(sorted(unknown))}")
        matches = [m for m in matches if m.id in args.match]
    failed = []
    for m in matches:
        ctx = pipeline.Context(m, cfg, out_root / m.id, log=_logger(out_root / m.id))
        try:
            if args.cmd == "status":
                st = pipeline.status(ctx)
                print(f"{m.id:20} " + "  ".join(f"{k}:{v}" for k, v in st.items()))
            else:
                done = pipeline.run(ctx, args.stages, force=args.force)
                print(f"{m.id}: {'ejecutado ' + ', '.join(done) if done else 'al día'}")
        except pipeline.MissingVideo:
            print(f"{m.id}: el vídeo ya no está ({m.video}); se conservan sus resultados")
        except pipeline.DiskFull as e:          # every other match would fail the same way
            print(f"{m.id}: {e}")
            return 1
        except KeyboardInterrupt:
            raise
        except Exception as e:                # one bad match never stops the others
            import traceback
            ctx.log(traceback.format_exc())
            print(f"{m.id}: ERROR ({e}); se sigue con los demás. Detalle en {ctx.dir / 'registro.log'}")
            failed.append(m.id)
    if failed:
        print(f"Partidos con error: {', '.join(failed)}")
        return 1


def run_audit(root: Path, report: Path, dest: Path, stroke: str = "forehand", dirs: list[Path] | None = None) -> int:
    """Screenshots of the report (if the browser can be driven) and the audit of every match folder
    under root (or only `dirs`: the matches of one analysis); prints the summary and what is not met."""
    from .audit import audit, write

    shots = dest / "capturas"
    try:
        from .screens import capture
        capture(report / "index.html", shots)
    except Exception as e:                    # no browser: the audit goes on without the screens
        print(f"AVISO: no se pudieron hacer las capturas del informe ({e})")
        shots = None
    if dirs is None:
        dirs = [d for d in sorted(root.iterdir()) if d.is_dir() and (d / "manifest.json").exists()] if root.exists() else []
    res = audit(dirs, report, stroke, shots)
    # the PDF summary: exists, how many pages, and a copy for Claude to read (uploaded with the logs)
    es = {"forehand": "derecha", "backhand": "reves", "overhead": "saque"}[stroke]
    pdf = next((p for p in (report.parent / "exportar" / "resumen.pdf", report.parent / f"exportar_{es}" / "resumen.pdf") if p.exists()), None)
    if pdf is None:
        res["items"].append({"req": 2, "area": "PDF", "name": "Resumen PDF", "status": "aviso", "detail": "no se encontró resumen.pdf"})
    else:
        import re as _re
        import shutil as _sh
        pages = len(_re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
        res["items"].append({"req": 2, "area": "PDF", "name": "Resumen PDF", "status": "ok" if pages else "falta",
                             "detail": f"{pages} páginas, {pdf.stat().st_size / 1e6:.1f} MB"})
        if shots is not None and pdf.stat().st_size < 15e6:
            _sh.copy2(pdf, shots / "resumen.pdf")
    from .audit import file_tree_items, petition_items, side_checks
    res["items"] += side_checks(root)
    res["items"] += file_tree_items(dirs, report, root)
    res["items"] += petition_items(res["items"])
    res["summary"] = {st: sum(i["status"] == st for i in res["items"]) for st in ("ok", "falta", "pocos datos", "aviso")}
    md = write(res, dest)
    s = res["summary"]
    print(f"Auditoría: {s['ok']} cumplidos, {s['falta']} no cumplidos, {s['pocos datos']} sin golpes suficientes, "
          f"{s['aviso']} avisos → {md}")
    for i in res["items"]:
        if i["status"] == "falta":
            print(f"  ✘ {i['name']}: {i['detail']}")
    return 0


def _logger(d: Path):
    """Print and append to <output>/<match>/registro.log (UTF-8, survives the console)."""
    import time

    def log(msg: str):
        print(msg, flush=True)
        try:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "registro.log", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass
    return log


if __name__ == "__main__":
    raise SystemExit(main())
