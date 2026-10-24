"""Which folder a match uses (docs/almacenamiento.md, block 4 connection, 24-10).

Until the library is switched on, a match lives in <output>/<id>/ as always. The switch is the file
biblioteca/datos/activa.json, written only by `activate` after the old folders were copied and verified
(library.migrate with no problems): from then on the matches of the catalogue live in
biblioteca/partidos/<año>/<partido>/ (found by their video's content, so a renamed or moved video is the same
match). Test runs and validations under other roots keep their own flat folders."""
import json
import time
from pathlib import Path

ACTIVE = "activa.json"


def _cfg() -> dict:
    from .config import load_config
    return load_config()


def library_active(cfg: dict | None = None) -> Path | None:
    """The library root when it is switched on, else None."""
    from .library import library_root
    root = library_root(cfg if cfg is not None else _cfg())
    return root if (root / "datos" / ACTIVE).exists() else None


def activate(root: Path, stats: dict) -> bool:
    """Switch the library on after a migration without problems (stats of library.migrate)."""
    if stats.get("problemas"):
        return False
    from .pipeline import write_atomic
    (Path(root) / "datos").mkdir(parents=True, exist_ok=True)
    write_atomic(Path(root) / "datos" / ACTIVE, json.dumps({"desde": time.strftime("%Y-%m-%d %H:%M"),
                                                           "copias": stats.get("copied", stats.get("copiados"))}))
    return True


def _player_slug(match) -> str:
    from .library import player_slug
    return player_slug(getattr(match.player, "name", "") or match.player.id)


def _by_origin(lib, match_id: str) -> str | None:
    for slug in lib.matches():
        if lib.match(slug).get("origen") == match_id:
            return slug
    return None


def dir_of(out_root: Path, match, cfg: dict | None = None) -> Path:
    """The folder of `match` for results under `out_root`."""
    cfg = cfg if cfg is not None else _cfg()
    root = library_active(cfg)
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    if root is None or Path(out_root).resolve() != out.resolve():
        return Path(out_root) / match.id
    from .library import Library, LibraryError
    with Library(root) as lib:
        slug = None
        try:
            added = lib.add_video(Path(match.video), date=match.date or None, tournament=match.tournament,
                                  round=match.round, players=[getattr(match.player, "name", match.player.id), match.opponent],
                                  surface=match.surface)
            slug = added.slug
        except LibraryError:                         # the video is gone: its results stay where they are
            slug = _by_origin(lib, match.id)
        if slug is None:
            return Path(out_root) / match.id
        d = lib.dir_of(slug)
    (d / "etapas").mkdir(parents=True, exist_ok=True)
    p = d / "partido.json"
    info = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if not info.get("jugadora"):
        from .pipeline import write_atomic
        info["jugadora"] = _player_slug(match)
        write_atomic(p, json.dumps(info, ensure_ascii=False, indent=1))
    return d
