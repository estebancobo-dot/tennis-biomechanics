"""The one registry of matches (10-11, phase A of the single orchestrator, docs/orquestador.md).

Before, the PC's cycle read config/matches.yaml and the application kept its own index (datos/tennisbio.db): two
lists that drifted apart (Rybakina-Pegula twice in the app, its photos from an old folder, a click saved in one
folder and the analysis reading another). Now the application's database is the registry every entry point reads:
the cycle, the command line, the audit and the window. config/matches.yaml (written by hand or by
scripts/auto_catalog.py) and the match folders are only *sources* that `sync` brings into it.

A match of the registry is the catalogue's entry (its metadata, as before) with the folder the registry knows for it
(Match.extra["match_dir"]: layout.dir_of uses it as it is); a match added only in the application comes from its row.
Test runs (ids «group:match») and archived matches are not matches of the registry."""
from __future__ import annotations

from pathlib import Path

from .catalog import CONFIG_DIR, Match, load_player


def enabled(cfg: dict) -> bool:
    """config `registry.source`: «db» (the registry, the default) or «yaml» (config/matches.yaml alone, as before)."""
    return str(((cfg.get("registry") or {}).get("source") or "db")).lower() == "db"


def _paths(cfg: dict):
    from .app.db import Paths
    return Paths.from_config(cfg)


def open_db(cfg: dict, create: bool = False):
    """The registry's database, or None when it does not exist yet (and create is False)."""
    from .app.db import DB
    p = _paths(cfg)
    if not create and not p.db.exists():
        return None
    return DB(p.db)


def sync(cfg: dict, config_dir: Path = CONFIG_DIR) -> dict:
    """Bring the sources into the registry: the catalogue (config/matches.yaml) and the match folders (output and
    library). Idempotent; what only the application decided (archived, a notice about the video) is kept."""
    from .app.index import rebuild
    db = open_db(cfg, create=True)
    try:
        rebuild(db, _paths(cfg), cfg, config_dir, fresh=False)
        rows = db.q("SELECT id, state, dir FROM matches")
    finally:
        db.close()
    return {"matches": len([r for r in rows if ":" not in r["id"]]), "tests": len([r for r in rows if ":" in r["id"]])}


def _abs_dir(cfg: dict, d: str) -> str:
    if not d:
        return ""
    p = Path(d)
    return str(p if p.is_absolute() else _paths(cfg).output / p)


def matches(cfg: dict, yaml_matches: list[Match], config_dir: Path = CONFIG_DIR) -> list[Match]:
    """The registry's matches: each catalogue entry with the registry's folder, then the matches the application
    added (rows not in the catalogue). Without the database: the catalogue as it is."""
    db = open_db(cfg)
    if db is None:
        return yaml_matches
    try:
        rows = {r["id"]: r for r in db.q("SELECT * FROM matches")}
        vids = {v["sample"]: v for v in db.q("SELECT sample, path FROM videos")}
    finally:
        db.close()
    out = []
    for m in yaml_matches:
        r = rows.get(m.id)
        if r is not None and r.get("state") == "archivado":
            continue
        d = _abs_dir(cfg, (r or {}).get("dir") or "")
        out.append(Match(id=m.id, video=m.video, player=m.player, opponent=m.opponent, tournament=m.tournament,
                         date=m.date, surface=m.surface, round=m.round,
                         extra={**(m.extra or {}), **({"match_dir": d} if d else {})}))
    known = {m.id for m in yaml_matches}
    for mid, r in sorted(rows.items()):
        if mid in known or ":" in mid or r.get("state") == "archivado" or not r.get("player"):
            continue
        v = vids.get(r.get("video") or "") or {}
        if not v.get("path"):
            continue
        try:
            player = load_player(r["player"], config_dir)
        except (OSError, ValueError, TypeError):
            continue
        d = _abs_dir(cfg, r.get("dir") or "")
        out.append(Match(id=mid, video=Path(v["path"]), player=player, opponent=r.get("opponent") or "",
                         tournament=r.get("tournament") or "", date=r.get("date") or "", surface=r.get("surface") or "",
                         round=r.get("round") or "",
                         extra={**({"opponent_id": r["opponent_id"]} if r.get("opponent_id") else {}),
                                **({"match_dir": d} if d else {})}))
    return out
