"""Añade al catálogo (config/matches.yaml) cada vídeo de la carpeta de vídeos que aún no esté.

No hace falta escribir nada a mano: el id sale del nombre del fichero y el rival se lee del
marcador durante el análisis. Las entradas que ya existen no se tocan.

    uv run python scripts/auto_catalog.py --player <id>
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


def player_of(file_name: str, default: str, config_dir: Path) -> str:
    """The player of a new video (07-11, a match of Sinner next to Rybakina's): the default player when the file name
    names her or names no configured player; else the one configured player it names (ids of config/players/*.yaml
    and their surnames, compared as ASCII words)."""
    words = set(slug(file_name).replace("_", "-").split("-"))
    named = []
    for f in sorted((config_dir / "players").glob("*.yaml")):
        try:
            name = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("name") or ""
        except (OSError, yaml.YAMLError):
            name = ""
        keys = {f.stem.lower()} | ({slug(name.split()[-1])} if name.strip() else set())
        if keys & words:
            named.append(f.stem)
    if default in named or len(named) != 1:
        return default
    return named[0]


FROM_NAME = ("opponent", "tournament", "date", "round")


def fill_from_names(entries: list[dict], config_dir: Path) -> list[str]:
    """11-11 (R6, #226): the rival, tournament, date and round that the video's name says (tennisbio.match_name), only
    where the entry has none: what is written is never replaced. Returns «id: campos» of the entries filled."""
    from tennisbio.match_name import parse
    out = []
    for m in entries:
        try:
            name = (yaml.safe_load((config_dir / "players" / f"{m.get('player')}.yaml").read_text(encoding="utf-8")) or {}).get("name", "")
        except (OSError, yaml.YAMLError):
            name = ""
        got = parse(Path(str(m.get("video", ""))).stem, name, str(m.get("player") or ""))
        new = [k for k in FROM_NAME if not str(m.get(k) or "").strip() and got.get(k)]
        for k in new:
            m[k] = got[k]
        if new:
            out.append(f"{m.get('id')}: {', '.join(new)}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default=None, help="id de config/players/<id>.yaml (por defecto `player` de la configuración)")
    args = ap.parse_args()
    if args.player is None:
        from tennisbio.config import default_player
        args.player = default_player()
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
    # videos the user already copied for the final test, held until the Base is closed (07-11: «prefiero acabar la
    # base completa y al final los vídeos nuevos»); config `catalog.hold`: their file names
    hold = {str(x).lower() for x in ((cfg.get("catalog") or {}).get("hold") or [])}
    held = []
    for f in sorted(videos.glob("*")) if videos.exists() else []:
        if f.suffix.lower() not in VIDEO_EXT or f.name.lower() in known:
            continue
        if f.name.lower() in hold:
            held.append(f.name)
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
        data["matches"].append({"id": mid, "video": f.name, "player": player_of(f.stem, args.player, CONFIG_DIR)})
        added.append(mid)
    filled = fill_from_names(data["matches"], CONFIG_DIR)
    path.write_text("# Generado automáticamente por scripts/auto_catalog.py; se puede editar.\n"
                    + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Vídeos en {videos}: {len(data['matches'])} en el catálogo ({len(added)} nuevos: {', '.join(added) or '—'})"
          + (f"; renombrados (se conserva lo analizado): {'; '.join(renamed)}" if renamed else "")
          + (f"; en espera hasta cerrar la Base (catalog.hold): {', '.join(held)}" if held else "")
          + (f"; datos leídos del nombre del vídeo: {'; '.join(filled)}" if filled else ""))
    if not data["matches"]:
        print(f"No hay vídeos. Copia los partidos a {videos} y vuelve a ejecutar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
