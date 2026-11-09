"""Saves the user's answer «which photo is her» for a match, without the application (09-11: the user answered «la 2» in
the chat on the photos the app's own code makes, scripts/app_identity_photos.py; the app itself showed two old photos
of Pegula). Writes identidad_clic.json in the folder the analysis reads (layout.dir_of), and prints the click that was
there before (kept in identidad_clic_anterior.json).

    uv run python scripts/save_identity_pick.py --match TEXT --t SECONDS"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--t", type=float, required=True)
    args = ap.parse_args()
    from tennisbio import match_files as mf
    from tennisbio.app import identity_click as ic
    from tennisbio.catalog import load_matches
    from tennisbio.identity import PICK_FILE
    from tennisbio.layout import dir_of
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    ms = [m for m in load_matches(cfg) if args.match in m.id]
    if len(ms) != 1:
        print(f"partidos con «{args.match}»: {[m.id for m in ms]} (hace falta exactamente uno)")
        sys.exit(2)
    d = dir_of(root, ms[0], cfg)
    old = mf.at(d, PICK_FILE)
    if old.exists():
        prev = old.read_text(encoding="utf-8")
        print(f"clic anterior: {prev}")
        (old.parent / "identidad_clic_anterior.json").write_text(prev, encoding="utf-8")
    pick = ic.save_pick(d, args.t, True)
    print(json.dumps({"match": ms[0].id, "dir": str(d), "pick": pick}, ensure_ascii=False))


if __name__ == "__main__":
    main()
