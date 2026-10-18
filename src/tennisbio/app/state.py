"""What the window shows, read from the index and the folders in one call (docs/aplicacion_local.md §4).

`snapshot(app)` returns a plain dict (JSON) with everything the 8 screens paint: what is running and when
it ends, notices, analyses, matches with their stages, players, the queue, quality, storage and settings.
The window asks for it every few seconds; storage (walking the folders) is only computed on demand."""
import json
import re
import shutil
import time
from pathlib import Path

from .. import pipeline
from . import jobs, storage
from .db import STROKE_ES
from .engine import MAIN_STAGES, USABLE

STAGE_ES = {"probe": "Lectura", "scenes": "Planos", "audio": "Audio", "court": "Pista", "players": "Jugadoras",
            "score": "Marcador", "identity": "Identidad", "candidates": "Candidatos", "fine": "Pasada fina"}
KIND_ES = {"partido": "todo el partido", "rival": "pasada fina de la rival", "informe": "informe y auditoría"}


def _order() -> list[str]:
    return [n for n in pipeline.order(list(MAIN_STAGES)) if n in MAIN_STAGES]


def _version() -> str:
    try:
        from importlib.metadata import version
        v = version("tennisbio")
    except Exception:                     # noqa: BLE001 — running from the source tree
        v = "0"
    try:
        from ..config import ROOT
        head = (ROOT / ".git" / "HEAD").read_text().strip()
        ref = ROOT / ".git" / head[5:] if head.startswith("ref: ") else None
        h = (ref.read_text().strip() if ref and ref.exists() else head)[:7]
        return f"{v} · {h}"
    except OSError:
        return v


def match_label(m: dict) -> str:
    """«US Open 2024 · F» from its data; the folder name when it has none."""
    t = " ".join(x for x in (m.get("tournament") or "", (m.get("date") or "")[:4]) if x)
    if t and m.get("round"):
        t += f" · {m['round']}"
    if not t:
        t = re.sub(r"^(smoke|poc\w*):", "", m["id"]).replace("smoke_", "").replace("-", " ")[:48]
    return t


def _progress(app) -> dict | None:
    for p in (app.paths.output / "progreso.json", *app.paths.output.glob("*/progreso.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - time.mktime(time.strptime(d.get("hora", ""), "%Y-%m-%d %H:%M:%S")) < 3600:
                return d
        except (OSError, ValueError, OverflowError):
            continue
    return None


def _match_rows(app, running: dict | None, prog: dict | None) -> list[dict]:
    db, eng = app.db, app.engine
    names = {p["id"]: p["name"] for p in db.q("SELECT id, name FROM players")}
    order = _order()
    out = []
    for m in db.q("SELECT m.*, v.path AS vpath, v.size AS vsize, v.duration AS vdur, v.fps AS vfps, v.interlaced AS vint "
                  "FROM matches m LEFT JOIN videos v ON v.sample = m.video ORDER BY m.date DESC, m.id"):
        d = eng.dir(m["id"])
        man = pipeline.load_manifest(d) if d.exists() else {}
        is_run = bool(running and running.get("match") == m["id"])
        err = db.one("SELECT message FROM jobs WHERE match=? AND state='error' ORDER BY id DESC LIMIT 1", m["id"])
        stages = []
        for n in order:
            st = "done" if n in man else ""
            if is_run and prog and prog.get("etapa") == n:
                st = "run"
            elif not st and m["state"] in ("excluido", "sin la jugadora"):
                st = "skip"
            elif not st and err and not any(s["st"] == "err" for s in stages):
                st = "err"
            stages.append({"k": n, "n": STAGE_ES.get(n, n), "st": st,
                           "min": round((man.get(n) or {}).get("seconds", 0) / 60, 1) if n in man else None})
        pl = [x for x in (m["player"], m["opponent_id"]) if x]
        out.append({
            "id": m["id"], "label": match_label(m), "state": m["state"], "note": m["note"] or "",
            "players": " – ".join(names.get(x, x) for x in pl) or (m["opponent"] or ""),
            "player": m["player"], "player_name": names.get(m["player"], m["player"]),
            "opponent_id": m["opponent_id"] or "", "opponent": m["opponent"] or names.get(m["opponent_id"] or "", ""),
            "surface": m["surface"] or "", "tournament": m["tournament"] or "", "round": m["round"] or "", "date": m["date"] or "",
            "duration_min": round((m["vdur"] or 0) / 60) or None, "fps": m["vfps"], "interlaced": bool(m["vint"]),
            "video": m["vpath"] or "", "video_gb": round((m["vsize"] or 0) / 1e9, 1),
            "test_run": "/" in (m["dir"] or ""), "dir": str(d), "stages": stages,
            "running": is_run, "progress": prog if is_run else None, "error": (err or {}).get("message", ""),
            "rival_done": (d / "strokes_opponent.json").exists(),
        })
    return out


def _analyses(app) -> list[dict]:
    db = app.db
    names = {p["id"]: p["name"] for p in db.q("SELECT id, name FROM players")}
    out = []
    for a in db.q("SELECT * FROM analyses ORDER BY player, stroke"):
        base = app.paths.analyses / a["id"]
        counts = json.loads(a["counts"] or "{}")
        worse = []
        rev = base / "pendiente" / "revision.md"
        if a["state"] == "pendiente de revisar" and rev.exists():
            txt = rev.read_text(encoding="utf-8")
            sec = txt.split("## Empeora respecto a la ejecución anterior")[1].split("\n## ")[0] if "## Empeora" in txt else ""
            worse = [ln[2:].strip().replace("**", "") for ln in sec.splitlines() if ln.startswith("- ")][:6]
        n_matches = len(db.q("SELECT id FROM matches WHERE (player=? OR opponent_id=?) AND state IN (%s)"
                             % ",".join("?" * len(USABLE)), a["player"], a["player"], *USABLE))
        versions = sorted((int(v.name[1:]) for v in base.glob("v*") if v.is_dir() and v.name[1:].isdigit()), reverse=True)
        out.append({"id": a["id"], "player": a["player"], "player_name": names.get(a["player"], a["player"]),
                    "stroke": a["stroke"], "stroke_es": STROKE_ES.get(a["stroke"], a["stroke"]),
                    "title": f"{STROKE_ES.get(a['stroke'], a['stroke']).capitalize()} de {names.get(a['player'], a['player'])}",
                    "version": a["version"], "state": a["state"], "verdict": a["verdict"], "counts": counts,
                    "n_strokes": a["n_strokes"], "updated": a["updated"], "matches": n_matches,
                    "web": str(base / "actual" / "index.html") if (base / "actual" / "index.html").exists() else "",
                    "provisional": 0 < (a["n_strokes"] or 0) < 12, "worse": worse, "old_versions": versions})
    return out


def _players(app) -> list[dict]:
    db = app.db
    out = []
    for p in db.q("SELECT * FROM players ORDER BY name"):
        ms = db.q("SELECT id, state, player FROM matches WHERE player=? OR opponent_id=?", p["id"], p["id"])
        an = db.q("SELECT stroke, n_strokes, state FROM analyses WHERE player=?", p["id"])
        out.append({"id": p["id"], "name": p["name"], "hand": p["hand"], "backhand": p["backhand"],
                    "height_m": p["height_m"], "height_known": bool(p["height_known"]),
                    "aliases": json.loads(p["aliases"] or "[]"), "matches": [m["id"] for m in ms],
                    "as_main": sum(m["player"] == p["id"] for m in ms),
                    "analyses": [{"stroke": a["stroke"], "stroke_es": STROKE_ES.get(a["stroke"], a["stroke"]),
                                  "n": a["n_strokes"], "state": a["state"]} for a in an]})
    return out


def _queue(app, labels: dict) -> dict:
    db = app.db
    names = {p["id"]: p["name"] for p in db.q("SELECT id, name FROM players")}

    def row(j):
        what = (f"Informe · {STROKE_ES.get(j['stroke'], j['stroke']).capitalize()} de {names.get(j['player'], j['player'])}"
                if j["kind"] == "informe"
                else f"{labels.get(j['match'], j['match'])} · {KIND_ES.get(j['kind'], j['kind'])}")
        return {"id": j["id"], "kind": j["kind"], "what": what, "state": j["state"], "reason": j["reason"] or "",
                "message": j["message"] or "", "device": j["device"] or "", "diag": j["diag"] or "",
                "estimate_s": j["estimate_s"], "finished": j["finished"] or "", "started": j["started"] or "",
                "attempts": j["attempts"]}
    return {
        "running": [row(j) for j in db.q("SELECT * FROM jobs WHERE state='en curso' ORDER BY id")],
        "pending": [row(j) for j in db.q("SELECT * FROM jobs WHERE state IN ('pendiente', 'esperando espacio', 'por confirmar', 'error') "
                                         "ORDER BY state='error' DESC, priority, id")],
        "done": [row(j) for j in db.q("SELECT * FROM jobs WHERE state IN ('hecho', 'aviso', 'cancelado') "
                                      "AND finished >= datetime('now', '-7 days', 'localtime') ORDER BY finished DESC LIMIT 30")],
    }


def storage_info(app) -> dict:
    """Disk use: free/total, per match by kind (imprescindible / regenerable / temporal), what can be freed."""
    out = app.paths.output
    try:
        du = shutil.disk_usage(out if out.exists() else out.anchor or ".")
        total, free = du.total, storage.free_bytes(out)
    except OSError:
        total, free = 0, 0
    regen = storage.regenerable(out)
    reg_set = {str(p) for p in regen}
    rows = []
    for m in app.db.q("SELECT id, dir, tournament, date, round FROM matches ORDER BY date DESC, id"):
        d = app.engine.dir(m["id"])
        if not d.exists():
            continue
        tmp = sum(storage.size_of(p) for p in regen if str(p).startswith(str(d)))
        allb = storage.size_of(d)
        rows.append({"id": m["id"], "label": match_label(m), "imp": allb - tmp, "reg": 0, "tmp": tmp, "total": allb})
    an = app.paths.analyses
    if an.exists():
        a_all = storage.size_of(an)
        a_reg = sum(storage.size_of(p) for p in regen if str(p).startswith(str(an)))
        rows.append({"id": "_analisis", "label": "Análisis (versiones, auditorías)", "imp": a_all - a_reg, "reg": a_reg, "tmp": 0,
                     "total": a_all})
    ours = sum(r["total"] for r in rows)
    return {"total": total, "free": free, "ours": ours, "regenerable": sum(storage.size_of(Path(p)) for p in reg_set),
            "rows": rows, "warn_below": storage.WARN_FREE, "auto_below": storage.AUTO_FREE}


def snapshot(app, with_storage: bool = False) -> dict:
    db = app.db
    running = db.one("SELECT * FROM jobs WHERE state='en curso' ORDER BY id LIMIT 1")
    prog = _progress(app) if running else None
    matches = _match_rows(app, running, prog)
    labels = {m["id"]: m["label"] for m in matches}
    e = jobs.eta(db)
    analyses = _analyses(app)
    notices = db.q("SELECT key, level, text, created FROM notices ORDER BY CASE level WHEN 'crit' THEN 0 WHEN 'aviso' THEN 1 "
                   "WHEN 'info' THEN 2 ELSE 3 END, id DESC")
    names = {p["id"]: p["name"] for p in db.q("SELECT id, name FROM players")}
    last = db.q("SELECT r.*, j.player, j.stroke FROM runs r JOIN jobs j ON j.id = r.job ORDER BY r.id DESC LIMIT 6")
    for r in last:
        r["label"] = (f"{STROKE_ES.get(r['stroke'], r['stroke']).capitalize()} de {names.get(r['player'], r['player'])}"
                      if r["kind"] == "informe" else labels.get(r["target"], r["target"]))
    st = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "version": _version(),
        "paths": {"output": str(app.paths.output), "videos": str(app.paths.videos), "data": str(app.paths.data)},
        "now": None, "eta": {"seconds": e["seconds"], "ends": e["ends"], "text": jobs.fmt_duration(e["seconds"]) if e["seconds"] else ""},
        "notices": notices, "analyses": analyses, "matches": matches, "players": _players(app),
        "queue": _queue(app, labels), "last": last,
        "settings": {"franja": db.setting("franja"), "pausa": bool(db.setting("pausa", False))},
        "rebuilt": bool(getattr(app, "rebuilt", False)),
    }
    if running:
        q = st["queue"]["running"][0]
        st["now"] = {**q, "progress": prog, "match": running.get("match")}
    if with_storage:
        st["storage"] = storage_info(app)
    return st
