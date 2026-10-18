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
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.cmd == "rebuild":
        from .db import Paths
        p = Paths.from_config(cfg).db
        if p.exists():
            p.rename(p.with_name(f"tennisbio.anterior-{time.strftime('%Y%m%d-%H%M%S')}.db"))
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
                      + (" — espera confirmación (tennisbio app plan --confirmar)" if r["confirm"] else ""))
        elif args.cmd == "work":
            for jid, st in app.work(once=not args.siempre):
                print(f"trabajo #{jid}: {st}")
            print(app.status())
        elif args.cmd in ("pausa", "seguir"):
            app.db.set_setting("pausa", args.cmd == "pausa")
            print("cola en pausa" if args.cmd == "pausa" else "cola en marcha")
        elif args.cmd == "franja":
            app.db.set_setting("franja", None if args.desde == "no" else [args.desde, args.hasta])
            print("sin franja" if args.desde == "no" else f"trabajos pesados de {args.desde} a {args.hasta}")
    finally:
        app.close()
    return 0
