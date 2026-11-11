"""Command line: `tennisbio run --all`, `tennisbio run --match ID --stages fine`, `tennisbio status`."""
import argparse
import sys
from pathlib import Path

from . import layout
from . import match_files as _mf
from .catalog import load_matches
from .config import load_config
from . import pipeline, stages

assert stages  # importing the module registers the stages


def _out_name(kind: str, pid: str | None, stroke: str, own: str | None) -> str:
    """informe_derecha / exportar_reves for the main player; with the player id for anyone else,
    so reports of different players or strokes never overwrite each other."""
    es = {"forehand": "derecha", "backhand": "reves", "overhead": "saque"}[stroke]
    return f"{kind}_{es}" if pid is None or pid == own else f"{kind}_{pid}_{es}"


def _utf8_streams():
    """10-11: the app's queue runs this in a child whose output goes to a file; on Windows Python then writes in the
    ANSI code page (cp1252) and the first «≈» or «✔» killed the work (the 4 matches «Error: UnicodeEncodeError»)."""
    for s in (sys.stdout, sys.stderr):
        try:
            if s is not None and (getattr(s, "encoding", "") or "").lower().replace("-", "") != "utf8":
                s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _script(name: str, argv: list[str]) -> int:
    """scripts/<name>.py run in this process with its arguments (names: lowercase letters, digits and «_» only)."""
    import re
    import runpy
    root = Path(__file__).resolve().parents[2] / "scripts"
    f = root / f"{name}.py"
    if not re.fullmatch(r"[a-z0-9_]+", name) or not f.exists():
        print(f"script no válido: {name}")
        return 2
    old = sys.argv
    sys.argv = [str(f), *argv]
    try:
        runpy.run_path(str(f), run_name="__main__")
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old
    return 0


def _jobs(args) -> int:
    import json
    from . import orchestrator as O
    cfg = load_config()
    out = Path(cfg.get("paths", {}).get("output", "output"))
    status_file = out / "estado_trabajos.json"
    if args.cmd == "worker":
        return O.serve(cfg, once=args.once, status_file=status_file)
    # the options can come before or after the action's own words (argparse.REMAINDER keeps them all): parsed here;
    # what follows «--» is the tennisbio command of «submit» (its own options are never read as ours)
    # 11-11: PowerShell eats «--» when the cycle calls this through a function (request 189: «unrecognized arguments:
    # --match …»), so only our two options are taken out, wherever they are, and every other word, options included, is
    # the action's (the tennisbio command of «submit»)
    rest = list(args.rest or [])
    cmd_args: list[str] = []
    if "--" in rest:
        i = rest.index("--")
        rest, cmd_args = rest[:i], rest[i + 1:]
    words: list[str] = []
    k = 0
    while k < len(rest):
        if rest[k] in ("--source", "--json") and k + 1 < len(rest):
            setattr(args, rest[k][2:], rest[k + 1])
            k += 2
            continue
        words.append(rest[k])
        k += 1
    rest = words
    if args.action == "run-one":
        return O.run_one(cfg, int(rest[0]))
    db = O.open_db(cfg)
    try:
        if args.action == "submit":
            what = cmd_args or rest
            if not what:
                print("falta qué hacer: tennisbio jobs submit -- run --all | tennisbio jobs submit flujo completo")
                return 2
            if what[0] == "flujo":       # «submit flujo NOMBRE» (also after «--»: no tennisbio command is called «flujo»)
                jid = O.submit(db, "flujo", args=what[1:2], source=args.source)
                print(f"trabajo {jid} en la cola: flujo {what[1] if len(what) > 1 else ''}")
            else:
                jid = O.submit(db, "comando", args=what, source=args.source)
                print(f"trabajo {jid} en la cola: tennisbio {' '.join(what)}")
        elif args.action == "pause":
            print(O.pause(db, now_=bool(rest and rest[0] == "now"), source=args.source))
        elif args.action == "resume":
            print(O.resume(db, source=args.source))
        elif args.action == "restart":
            print(O.restart(db, source=args.source))
        elif args.action == "cancel":
            n = O.cancel(db, None if rest and rest[0] == "all" else int(rest[0]), all_=bool(rest and rest[0] == "all"),
                         source=args.source)
            print(f"{n} trabajos cancelados o parándose")
        st = O.status(db, output=out)
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(st, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        O.write_status(db, status_file)
        if args.action == "status":
            w = st["ejecutor"]
            print(f"ejecutor: {'en marcha' if w.get('vivo') else 'parado'} · cola {'en pausa' if st['pausa'] else 'activa'}"
                  f" · firma {st['firma']}")
            for r in st["en_curso"]:
                print(f"  en curso  #{r['id']} {r['kind']} {r.get('reason') or ''}")
            for r in st["pendientes"]:
                print(f"  pendiente #{r['id']} {r['kind']} {r.get('reason') or ''}")
            for r in st["recientes"][:5]:
                print(f"  {r['state']:<9} #{r['id']} {r['kind']} {r.get('reason') or ''} {r.get('message') or ''}")
    finally:
        db.close()
    return 0


def _registry(args) -> int:
    import json
    from . import registry
    cfg = load_config()
    if args.action == "sync":
        print(f"registro de partidos: {registry.sync(cfg)}")
        return 0
    rows = [{"id": m.id, "jugador": m.player.id, "rival": m.opponent, "video": str(m.video),
             "carpeta": str(layout.dir_of(Path(cfg.get("paths", {}).get("output", "output")), m, cfg))}
            for m in load_matches(cfg)]
    for r in rows:
        print(f"{r['id']:<62} {r['jugador']:<10} {r['carpeta']}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main(argv=None):
    _utf8_streams()
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
    cal = sub.add_parser("calidad", help="modelo de calidad (el «cubo», config/calidad.yaml) desde la última auditoría")
    cal.add_argument("--audit", default=None, help="auditoría JSON (por defecto <salida>/auditoria/auditoria.json)")
    cal.add_argument("--out", default=None, help="carpeta de calidad.md y calidad.json (por defecto <salida>)")
    scp = sub.add_parser("script", help="un script del repositorio (scripts/NOMBRE.py) con sus argumentos, como trabajo de la cola")
    scp.add_argument("name")
    scp.add_argument("rest", nargs=argparse.REMAINDER)
    wk = sub.add_parser("worker", help="el ejecutor único de la cola (uno por PC): ejecuta los trabajos y obedece pausar/parar")
    wk.add_argument("--once", action="store_true", help="sale cuando no queda nada que hacer")
    jb = sub.add_parser("jobs", help="la cola: submit | status | pause | resume | cancel | run-one (docs/orquestador.md)")
    jb.add_argument("action", choices=("submit", "status", "pause", "resume", "cancel", "restart", "run-one"))
    jb.add_argument("rest", nargs=argparse.REMAINDER,
                    help="submit: -- <argumentos de tennisbio> | cancel: ID o all | run-one: ID | pause: now")
    jb.add_argument("--source", default="cli", help="quién lo pide (app, ciclo, claude…), para el registro de eventos")
    jb.add_argument("--json", default=None, help="status: escribe el estado en este fichero")
    rg = sub.add_parser("registry", help="registro único de partidos: sync (catálogo y carpetas) | list [--json FICHERO]")
    rg.add_argument("action", choices=("sync", "list"))
    rg.add_argument("--json", default=None, help="list: escribe también la lista en este fichero (para pc-logs)")
    apl = sub.add_parser("app", help="la aplicación local: tennisbio app status|add|also|plan|work|… (ver app/cli.py)")
    apl.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.cmd == "calidad":                   # 11-11 (#256): the quality model's score from the latest audit
        from .quality_model import run as _q
        cfg = load_config()
        out = Path(cfg.get("paths", {}).get("output", "output"))
        aud = Path(args.audit) if args.audit else next((p for p in (out / "auditoria" / "auditoria.json",
                                                                    out / "auditoria_partidos.json") if p.exists()), None)
        if aud is None or not aud.exists():
            print("no hay auditoría que puntuar")
            return 2
        r = _q(aud, Path(args.out) if args.out else out)
        t = r["total"]
        print(f"calidad: {t['ok']}/{t['n']} comprobaciones, casillas aceptadas {t['accepted']}/{t['cells']}, sin medir {t['unmeasured']}")
        return 0
    if args.cmd == "script":                    # 11-11: a repository script as a job of the single queue («medir»)
        return _script(args.name, [a for a in (args.rest or []) if a != "--"])
    if args.cmd in ("worker", "jobs"):          # 10-11: the single worker and the queue's controls
        return _jobs(args)
    if args.cmd == "registry":                  # 10-11: the one registry of matches (tennisbio.registry)
        return _registry(args)
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
        lib_dirs = None
        if not args.root and layout.library_active(cfg):     # the matches live in the library, not in <output>
            # 10-11: only the matches of the report's player (the audit of Rybakina's report counted Sinner's strokes
            # and looked for his replays in her report)
            lib_dirs = [layout.dir_of(out_root, m, cfg) for m in matches if m.player.id == own]
        return run_audit(Path(args.root) if args.root else out_root,
                         Path(args.report) if args.report else out_root / _out_name("informe", own, args.stroke, own),
                         Path(args.out) if args.out else out_root / "auditoria", args.stroke, dirs=lib_dirs)
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
        d = layout.dir_of(out_root, m, cfg)        # <output>/<id>, or its library folder once switched on
        ctx = pipeline.Context(m, cfg, d, log=_logger(d))
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
        dirs = [d for d in sorted(root.iterdir()) if d.is_dir() and (_mf.at(d, "manifest.json")).exists()] if root.exists() else []
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
    from .audit import base_items, file_tree_items, petition_items, side_checks
    res["items"] += side_checks(root)
    res["items"] += file_tree_items(dirs, report, root)
    res["items"] += base_items(dirs, root)          # Base packages B1 and B3: models, stage times, PC use, Actions (04-11)
    res["items"] += petition_items(res["items"])
    res["summary"] = {st: sum(i["status"] == st for i in res["items"]) for st in ("ok", "falta", "pocos datos", "aviso")}
    md = write(res, dest)
    try:                                       # the honest status of every request, per plan package (02-11)
        from .real_status import render
        txt, counts = render(res)
        (Path(dest) / "estado_real_peticiones.md").write_text(txt, encoding="utf-8")
        print("Peticiones: " + " · ".join(f"{v} {k}" for k, v in counts.items()))
    except Exception as e:                     # noqa: BLE001 — never stops the audit
        print(f"AVISO: no se pudo calcular el estado real de las peticiones ({e})")
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
            with open(_mf.at(d, "registro.log"), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass
    return log


if __name__ == "__main__":
    raise SystemExit(main())
