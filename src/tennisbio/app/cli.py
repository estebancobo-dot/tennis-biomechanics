"""`tennisbio app …`: the application's core from the command line (until the window, part 2).

    tennisbio app status                     what is running, the queue, matches, analyses and notices
    tennisbio app add VIDEO [--si] [--jugadora ID] [--rival ID] [--usar nuevo|existente]
                                             proposes its data; with --si it registers it and queues its work
    tennisbio app also JUGADORA [--golpe forehand|backhand|overhead]   «Analizar también…»
    tennisbio app plan [--confirmar]         after an update: what to recompute and its cost
    tennisbio app work [--siempre]           runs the queue (by default until nothing can run now)
    tennisbio app pausa | seguir             pause or resume the queue
    tennisbio app franja 22:00 08:00 | franja no   heavy jobs only in that band
    tennisbio app rebuild                    rebuilds the index from the folders (the old one is kept aside)
    tennisbio app ventana [--sin-cola]       the window (the queue runs inside while it is open)
    tennisbio app pagina [DEST]              the screens as a read-only page (for screenshots and checks)
    tennisbio app comprobar DEST             every screen painted in a browser with the real index: problems,
                                             screenshots, and whether this PC can open the window
    tennisbio app movil JUGADORA [--golpe G] the copy for the phone (movil\\<jugadora>_<golpe>\\ and its .zip)
    tennisbio app comprobar-movil DEST       the phone copy of every analysis, checked in the PC's browser, and the shortcut
    tennisbio app acceso [--si-falta]        the desktop shortcut «Tennisbio» (the installer and the cycle make it)
"""
import argparse
import time

from ..config import load_config
from .core import App


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tennisbio app")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    a = sub.add_parser("add")
    a.add_argument("video")
    a.add_argument("--si", action="store_true", help="confirmar y encolar")
    a.add_argument("--jugadora")
    a.add_argument("--rival")
    a.add_argument("--usar", choices=["nuevo", "existente"], default="nuevo")
    al = sub.add_parser("also")
    al.add_argument("jugadora")
    al.add_argument("--golpe", default="forehand", choices=["forehand", "backhand", "overhead"])
    pl = sub.add_parser("plan")
    pl.add_argument("--confirmar", action="store_true")
    w = sub.add_parser("work")
    w.add_argument("--siempre", action="store_true")
    sub.add_parser("pausa")
    sub.add_parser("seguir")
    fr = sub.add_parser("franja")
    fr.add_argument("desde")
    fr.add_argument("hasta", nargs="?")
    sub.add_parser("rebuild")
    ve = sub.add_parser("ventana")
    ve.add_argument("--sin-cola", action="store_true")
    pg = sub.add_parser("pagina")
    pg.add_argument("dest", nargs="?")
    co = sub.add_parser("comprobar")
    co.add_argument("dest")
    co.add_argument("--real", action="store_true", help="abrir también la ventana real, oculta, y probar su puente")
    cm = sub.add_parser("comprobar-movil")
    cm.add_argument("dest")
    mv = sub.add_parser("movil")
    mv.add_argument("jugadora")
    mv.add_argument("--golpe", default="forehand", choices=["forehand", "backhand", "overhead"])
    mv.add_argument("--sin-zip", action="store_true")
    ac = sub.add_parser("acceso")
    ac.add_argument("--si-falta", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.cmd == "rebuild":
        from .db import Paths
        p = Paths.from_config(cfg).db
        if p.exists():
            p.rename(p.with_name(f"tennisbio.anterior-{time.strftime('%Y%m%d-%H%M%S')}.db"))
    if args.cmd == "acceso":
        from .db import Paths
        from .shortcut import create
        r = create(Paths.from_config(cfg).data, only_if_missing=args.si_falta)
        print(f"Acceso directo: {r.get('link')} ({'hecho' if r['made'] else 'ya estaba' if not r.get('error') else r['error']})")
        return 0 if not r.get("error") or r["error"] == "no es Windows" else 1
    if args.cmd == "ventana":
        from .window import run
        return run(cfg, with_queue=not args.sin_cola)
    app = App(cfg)
    try:
        if args.cmd == "status" or args.cmd == "rebuild":
            print(app.status())
        elif args.cmd == "add":
            prop = app.propose(args.video)
            print(f"{prop.path.name}: {prop.duration / 60:.0f} min, {prop.fps:.0f} fps"
                  + (", entrelazado" if prop.interlaced else "")
                  + f"\n  propuesta: {prop.tournament or '¿torneo?'} {prop.year} · {prop.surface or '¿superficie?'} · "
                  + (" – ".join(prop.players) or "¿jugadoras?") + f" → {prop.match_id}")
            for k, v in prop.flags.items():
                print(f"  [{k}] {v}")
            if args.si:
                from .videos import confirm
                mid = confirm(app.db, prop, args.jugadora, args.rival, choose=args.usar)
                print(f"  {'añadido: ' + mid + ' (en la cola)' if mid else 'no se añade nada'}")
            else:
                print("  (añade --si para confirmarlo)")
        elif args.cmd == "also":
            print(app.analyze_also(args.jugadora, args.golpe))
        elif args.cmd == "plan":
            if args.confirmar:
                print(f"{app.confirm_plan()} trabajos confirmados")
            else:
                r = app.plan_updates()
                print(f"{r['matches']} partido(s) a recalcular, {r['reports']} informe(s)"
                      + (f"; {r['no_video']} partido(s) sin su vídeo localizado (no se pueden comprobar)" if r["no_video"] else "")
                      + (f"; {r['test_runs']} prueba(s) del ciclo automático: las mantiene el ciclo" if r.get("test_runs") else "")
                      + (" — espera confirmación (tennisbio app plan --confirmar)" if r["confirm"] else ""))
        elif args.cmd == "work":
            for jid, st in app.work(once=not args.siempre):
                print(f"trabajo #{jid}: {st}")
            print(app.status())
        elif args.cmd in ("pausa", "seguir"):
            app.db.set_setting("pausa", args.cmd == "pausa")
            print("cola en pausa" if args.cmd == "pausa" else "cola en marcha")
        elif args.cmd == "comprobar":
            from pathlib import Path
            from .check import check
            r = check(app, Path(args.dest), real=args.real)
            print((Path(args.dest) / "ventana.md").read_text(encoding="utf-8"))
            return 1 if r["problems"] else 0
        elif args.cmd == "comprobar-movil":
            from pathlib import Path
            from .check import check_mobile
            r = check_mobile(app, Path(args.dest))
            print((Path(args.dest) / "movil.md").read_text(encoding="utf-8"))
            return 1 if r["problems"] else 0
        elif args.cmd == "pagina":
            from pathlib import Path
            from .window import write_page
            print(write_page(app, Path(args.dest) if args.dest else None))
        elif args.cmd == "movil":
            from .mobile import make
            r = make(app.paths, args.jugadora, args.golpe, zip_it=not args.sin_zip,
                     progress=lambda i, n: print(f"\r  vídeos {i}/{n}", end="", flush=True))
            print(f"\nCopia para el móvil: {r.get('zip') or r['dest']} · {r['with_video']}/{r['strokes']} golpes con vídeo · "
                  f"{r['bytes'] / 1e9:.2f} GB · {r['encoded']} convertidos, {r['kept']} ya estaban"
                  + (f" · {len(r['failed'])} fallaron" if r["failed"] else "") + (f" · {r['missing']} sin clip" if r["missing"] else ""))
        elif args.cmd == "franja":
            app.db.set_setting("franja", None if args.desde == "no" else [args.desde, args.hasta])
            print("sin franja" if args.desde == "no" else f"trabajos pesados de {args.desde} a {args.hasta}")
    finally:
        app.close()
    return 0
