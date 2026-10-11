"""Command line: `tennisbio run --all`, `tennisbio run --match ID --stages fine`, `tennisbio status`."""
import argparse
from pathlib import Path

from .catalog import load_matches
from .config import load_config
from . import pipeline, stages

assert stages  # importing the module registers the stages


def main(argv=None):
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
    args = ap.parse_args(argv)

    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output"))
    matches = load_matches(cfg)
    if getattr(args, "match", None):
        matches = [m for m in matches if m.id in args.match]
    for m in matches:
        ctx = pipeline.Context(m, cfg, out_root / m.id)
        if args.cmd == "status":
            st = pipeline.status(ctx)
            print(f"{m.id:20} " + "  ".join(f"{k}:{v}" for k, v in st.items()))
        else:
            done = pipeline.run(ctx, args.stages, force=args.force)
            print(f"{m.id}: {'ejecutado ' + ', '.join(done) if done else 'al día'}")


if __name__ == "__main__":
    main()
