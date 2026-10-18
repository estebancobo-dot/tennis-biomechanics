"""Filling the index: from the current catalogue (config/matches.yaml, config/players/*.yaml) and from the
folders themselves (the source of truth). Also the way back: the players' files the stages still read
(config/players/<id>.yaml) are written for players created in the application.

Rebuilding reads, for every <output>/<match>/ with a manifest: partido.json (its data), video.json (the
video's identity), the manifest (what is done); and every <output>/analisis/<id>/analisis.json."""
import json
from pathlib import Path

import yaml

from ..catalog import Player, ascii_id
from ..config import CONFIG_DIR
from ..pipeline import load_manifest, video_sample
from .db import DB, Paths, now

DEFAULT_HEIGHT = 1.80
IDENTITY_MIN = 0.6         # below this the identity is doubtful: analysed, kept out of comparisons
SKIP_DIRS = {"analisis", "_app", "datos"}


def import_players(db: DB, config_dir: Path = CONFIG_DIR):
    for f in sorted((config_dir / "players").glob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8-sig")) or {}
        except (OSError, yaml.YAMLError):
            continue
        known = db.one("SELECT aliases FROM players WHERE id=?", f.stem)
        db.upsert("players", {"id": f.stem, "name": d.get("name", f.stem), "hand": d.get("hand", "right"),
                              "backhand": d.get("backhand", "two_handed"),
                              "height_m": float(d.get("height_m") or DEFAULT_HEIGHT), "height_known": int(bool(d.get("height_m"))),
                              "aliases": (known or {}).get("aliases") or json.dumps(d.get("aliases", []))})


def import_catalog(db: DB, cfg: dict, config_dir: Path = CONFIG_DIR):
    """config/matches.yaml → matches and videos. Idempotent; never overwrites what the application learnt
    (states, notes) about a match it already has."""
    import_players(db, config_dir)
    path = config_dir / "matches.yaml"
    if not path.exists():
        return
    try:
        entries = (yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}).get("matches") or []
    except (OSError, yaml.YAMLError):
        return
    videos = Path(cfg.get("paths", {}).get("videos", "."))
    for e in entries:
        mid = str(e.get("id"))
        if not mid or db.one("SELECT id FROM matches WHERE id=?", mid):
            continue
        vpath = videos / str(e.get("video", ""))
        sample = ""
        if vpath.is_file():
            sample = video_sample(vpath)
            db.upsert("videos", {"sample": sample, "size": vpath.stat().st_size, "path": str(vpath), "added": now()}, "sample")
        db.upsert("matches", {"id": mid, "video": sample, "tournament": str(e.get("tournament", "")),
                              "date": str(e.get("date", "")), "round": str(e.get("round", "")), "surface": str(e.get("surface", "")),
                              "player": str(e.get("player", "")), "opponent": str(e.get("opponent", "")),
                              "opponent_id": str(e.get("opponent_id", "") or ""), "state": "nuevo", "created": now()})


def state_from_manifest(man: dict) -> tuple[str, str]:
    """What a match's manifest says about it, in the application's words (state, note)."""
    if not man:
        return "nuevo", ""
    s = lambda n: (man.get(n) or {}).get("summary") or {}
    if s("candidates").get("doubles"):
        return "excluido", "Partido de dobles (dos personas en la mitad cercana): fuera de alcance."
    if "fine" not in man:
        return "en curso", ""
    if not s("fine").get("confirmed") and not s("candidates").get("candidates"):
        return "sin la jugadora", "La identidad no la encuentra en el vídeo; no se analiza a otra persona."
    notes = []
    conf = s("identity").get("confidence")
    if isinstance(conf, (int, float)) and conf < IDENTITY_MIN:
        notes.append(f"Identidad dudosa (confianza {conf:.2f}): se analiza, pero no entra en las comparativas.".replace("0.", "0,"))
    if "audio" in man and not s("audio").get("onsets"):
        notes.append("Sin sonido: los golpes salen solo de la bola y la pose.")
    if "court" in man and s("court").get("with_court") == 0:
        notes.append("No se ve la pista: sin posiciones en metros.")
    if notes:
        return ("identidad dudosa" if conf is not None and conf < IDENTITY_MIN else "con aviso"), " ".join(notes)
    return "analizado", ""


def rebuild(db: DB, paths: Paths, cfg: dict, config_dir: Path = CONFIG_DIR, fresh: bool = True):
    """The whole index from the folders (and the catalogue, for what the folders do not say).
    fresh=False (every start of the application): adds the matches that appeared meanwhile (a test run of
    the cycle, a folder copied in) and updates the ones still «nuevo» or «en curso»; what the application
    decided about the others (archived, notices) is kept."""
    import_catalog(db, cfg, config_dir)
    for mid, d in match_dirs(paths.output):
        man = load_manifest(d)
        info = {}
        if (d / "partido.json").exists():
            try:
                info = json.loads((d / "partido.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                info = {}
        sample = ""
        try:
            v = json.loads((d / "video.json").read_text(encoding="utf-8"))
            sample = v.get("sample", "")
            if sample and not db.one("SELECT sample FROM videos WHERE sample=?", sample):
                db.upsert("videos", {"sample": sample, "size": v.get("size", 0), "path": _find_video(paths.videos, v),
                                     "added": now()}, "sample")
        except (OSError, ValueError):
            pass
        state, note = state_from_manifest(man)
        rel = d.relative_to(paths.output).as_posix()
        row = db.one("SELECT * FROM matches WHERE id=?", mid)
        if row and (fresh or row["state"] in ("nuevo", "en curso")):
            db.x("UPDATE matches SET state=?, note=?, dir=?, video=COALESCE(NULLIF(video, ''), ?) WHERE id=?",
                 state, note, rel, sample, mid)
        elif row:
            db.x("UPDATE matches SET dir=? WHERE id=? AND IFNULL(dir, '')=''", rel, mid)
        else:
            from .videos import find_players
            who = info.get("player") or next(iter(find_players(db, d.name)), "")
            if who and not info.get("player"):
                note = (note + " " if note else "") + "Jugadora deducida del nombre de la carpeta."
            db.upsert("matches", {"id": mid, "video": sample, "tournament": info.get("tournament", ""),
                                  "date": info.get("date", ""), "round": info.get("round", ""), "surface": info.get("surface", ""),
                                  "player": who, "opponent": info.get("opponent", ""),
                                  "opponent_id": info.get("opponent_id", ""), "state": state, "note": note, "created": now(),
                                  "dir": rel})
    for f in sorted(paths.analyses.glob("*/analisis.json")) if paths.analyses.exists() else []:
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
            db.upsert("analyses", {k: a[k] for k in ("id", "player", "stroke", "version", "state", "verdict", "counts",
                                                      "n_strokes", "updated") if k in a})
        except (OSError, ValueError, KeyError):
            continue


def match_dirs(out: Path) -> list[tuple[str, Path]]:
    """Every match folder (with a manifest) under the output: <output>/<match> and, one level down, the
    test runs (<output>/_smoke/<match>, <output>/_poc9_largo/<match>). The id of a nested one carries its
    group («smoke:…», «poc9_largo:…»): the same video in two runs stays two matches."""
    res = []
    for d in sorted(out.iterdir()) if out.exists() else []:
        if not d.is_dir() or d.name in SKIP_DIRS:
            continue
        if (d / "manifest.json").exists():
            res.append((d.name, d))
            continue
        for sub in sorted(d.iterdir()):
            if sub.is_dir() and (sub / "manifest.json").exists():
                res.append((f"{d.name.lstrip('_')}:{sub.name}", sub))
    return res


def _find_video(videos: Path, rec: dict) -> str:
    """Where the video of a pinned identity is now: a file of the same size whose sampled pieces match."""
    if not videos.exists():
        return ""
    for f in videos.rglob("*"):
        if f.is_file() and f.stat().st_size == rec.get("size") and video_sample(f) == rec.get("sample"):
            return str(f)
    return ""


def player(db: DB, pid: str) -> Player:
    """The stages' Player from the index. Without a known height: 1.80 m (marked in the index and noticed)."""
    r = db.one("SELECT * FROM players WHERE id=?", pid) or {"id": pid, "name": pid}
    h = r.get("height_m") or DEFAULT_HEIGHT
    if not r.get("height_known", 1) or not r.get("height_m"):
        db.notice(f"height_{pid}", "aviso", f"Falta la altura de {r.get('name') or pid}: uso {DEFAULT_HEIGHT:.2f} m (±5 %)".replace(".", ",")
                  + " y lo marco. Pon su altura en su ficha.")
    return Player(id=pid, name=r.get("name") or pid, hand=r.get("hand") or "right",
                  backhand=r.get("backhand") or "two_handed", height_m=float(h))


def add_player(db: DB, name: str, hand: str = "right", backhand: str = "two_handed", height_m: float | None = None,
               aliases: list | None = None, config_dir: Path = CONFIG_DIR) -> str:
    """A new player file: in the index and as config/players/<id>.yaml (what the stages read). An existing
    file is never overwritten."""
    pid = ascii_id(name.split()[-1] if name.split() else name, 30)
    db.upsert("players", {"id": pid, "name": name, "hand": hand, "backhand": backhand,
                          "height_m": float(height_m or DEFAULT_HEIGHT), "height_known": int(bool(height_m)),
                          "aliases": json.dumps(aliases or [])})
    f = config_dir / "players" / f"{pid}.yaml"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        d = {"name": name, "hand": hand, "backhand": backhand}
        if height_m:
            d["height_m"] = float(height_m)
        f.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return pid


def add_alias(db: DB, pid: str, alias: str):
    """A name the scoreboard shows for her (OCR): kept in her file so the next video is recognised."""
    r = db.one("SELECT aliases FROM players WHERE id=?", pid)
    if not r:
        return
    al = json.loads(r["aliases"] or "[]")
    if alias and alias not in al:
        al.append(alias)
        db.x("UPDATE players SET aliases=? WHERE id=?", json.dumps(al, ensure_ascii=False), pid)
