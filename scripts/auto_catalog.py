"""Añade al catálogo (config/matches.yaml) cada vídeo de la carpeta de vídeos que aún no esté.

No hace falta escribir nada a mano: el id sale del nombre del fichero y el rival se lee del
marcador durante el análisis. Las entradas que ya existen no se tocan.

    uv run python scripts/auto_catalog.py --player rybakina
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennisbio.config import CONFIG_DIR, load_config  # noqa: E402

VIDEO_EXT = {".mp4", ".mkv", ".ts", ".mov", ".avi", ".m4v", ".webm"}


def slug(name: str) -> str:
    """ASCII id from the file name (it names the output folder)."""
    from tennisbio.catalog import ascii_id

    return ascii_id(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default="rybakina", help="id de config/players/<id>.yaml")
    args = ap.parse_args()
    cfg = load_config()
    videos = Path(cfg.get("paths", {}).get("videos", "videos"))
    path = CONFIG_DIR / "matches.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    data = data or {"matches": []}
    known = {Path(m["video"]).name.lower() for m in data["matches"]}
    ids = {m["id"] for m in data["matches"]}
    added, renamed = [], []
    # a video renamed by the user (25-10): same content as an entry whose file is gone → that entry, its id and
    # everything already analysed are kept; only the file name changes (no new match, nothing recomputed)
    gone = [m for m in data["matches"] if not (videos / Path(m["video"]).name).exists()]
    pinned = {}
    out_root = Path(cfg.get("paths", {}).get("output", "output"))
    for m in gone:
        try:
            import json
            pinned[json.loads((out_root / m["id"] / "video.json").read_text(encoding="utf-8"))["sample"]] = m
        except (OSError, ValueError, KeyError):
            continue
    for f in sorted(videos.glob("*")) if videos.exists() else []:
        if f.suffix.lower() not in VIDEO_EXT or f.name.lower() in known:
            continue
        if pinned:
            from tennisbio.pipeline import video_sample
            m = pinned.pop(video_sample(f), None)
            if m is not None:
                renamed.append(f"{m['video']} → {f.name}")
                m["video"] = f.name
                known.add(f.name.lower())
                continue
        mid = slug(f.stem)
        while mid in ids:
            mid += "-b"
        ids.add(mid)
        data["matches"].append({"id": mid, "video": f.name, "player": args.player})
        added.append(mid)
    path.write_text("# Generado automáticamente por scripts/auto_catalog.py; se puede editar.\n"
                    + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Vídeos en {videos}: {len(data['matches'])} en el catálogo ({len(added)} nuevos: {', '.join(added) or '—'})"
          + (f"; renombrados (se conserva lo analizado): {'; '.join(renamed)}" if renamed else ""))
    if not data["matches"]:
        print(f"No hay vídeos. Copia los partidos a {videos} y vuelve a ejecutar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
