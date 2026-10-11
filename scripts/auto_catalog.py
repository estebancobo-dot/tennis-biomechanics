"""Añade al catálogo (config/matches.yaml) cada vídeo de la carpeta de vídeos que aún no esté.

No hace falta escribir nada a mano: el id sale del nombre del fichero y el rival se lee del
marcador durante el análisis. Las entradas que ya existen no se tocan.

    uv run python scripts/auto_catalog.py --player rybakina
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennisbio.config import CONFIG_DIR, load_config  # noqa: E402

VIDEO_EXT = {".mp4", ".mkv", ".ts", ".mov", ".avi", ".m4v", ".webm"}


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "partido"


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
    added = []
    for f in sorted(videos.glob("*")) if videos.exists() else []:
        if f.suffix.lower() not in VIDEO_EXT or f.name.lower() in known:
            continue
        mid = slug(f.stem)
        while mid in ids:
            mid += "-b"
        ids.add(mid)
        data["matches"].append({"id": mid, "video": f.name, "player": args.player})
        added.append(mid)
    path.write_text("# Generado automáticamente por scripts/auto_catalog.py; se puede editar.\n"
                    + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Vídeos en {videos}: {len(data['matches'])} en el catálogo ({len(added)} nuevos: {', '.join(added) or '—'})")
    if not data["matches"]:
        print(f"No hay vídeos. Copia los partidos a {videos} y vuelve a ejecutar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
