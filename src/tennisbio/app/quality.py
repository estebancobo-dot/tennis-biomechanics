"""Versions of an analysis (player × stroke) and their validation (docs/aplicacion_local.md §6 «Validar»).

Every rebuild goes to <output>/analisis/<id>/nueva, is audited there (the same audit the PC runs today:
requirements, design and real video) and compared with the audit of the version in use (`actual`), with
the same review the automatic cycle uses (scripts/auto_cycle.py: OK / FALLOS / REGRESIÓN / ERROR).

- Nothing got worse: `actual` becomes v<N> (kept), `nueva` becomes `actual`.
- Something got worse: `actual` stays as it is and the new one is kept as `pendiente` («pendiente de
  revisar»), with a red notice saying what got worse. The user always sees the last good version.

Each analysis folder carries analisis.json (player, stroke, version, verdict, counts), so the index can
be rebuilt from the folders."""
import importlib.util
import json
import shutil
from pathlib import Path

from ..config import ROOT
from .db import DB, STROKE_ES, now

_review = None


def review(new_json: Path, old_json: Path) -> tuple[str, str]:
    """The automatic cycle's review (one code for both: the app and the cycle can never disagree)."""
    global _review
    if _review is None:
        spec = importlib.util.spec_from_file_location("_auto_cycle", ROOT / "scripts" / "auto_cycle.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _review = mod.review
    return _review(new_json, old_json, [])


def analysis_id(player: str, stroke: str) -> str:
    return f"{player}_{stroke}"


def label(db: DB, player: str, stroke: str) -> str:
    p = db.one("SELECT name FROM players WHERE id=?", player)
    return f"{STROKE_ES.get(stroke, stroke).capitalize()} de {(p or {}).get('name') or player}"


def _move(src: Path, dst: Path):
    """Rename, or copy and delete when Windows holds a file open (the web of `actual` in a browser)."""
    if dst.exists():
        shutil.rmtree(dst)
    try:
        src.rename(dst)
    except OSError:
        shutil.copytree(src, dst)
        shutil.rmtree(src, ignore_errors=True)


def counts(audit_json: Path) -> dict:
    try:
        items = json.loads(audit_json.read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return {}
    return {s: sum(i.get("status") == s for i in items) for s in ("ok", "falta", "pocos datos", "aviso")}


def publish(db: DB, analyses_root: Path, player: str, stroke: str, build, audit) -> dict:
    """Builds, audits, compares and publishes (or holds) a new version of an analysis.
    build(dest) writes the web into dest (dest/index.html) and returns the number of strokes;
    audit(report_dir, audit_dir) writes audit_dir/auditoria.json."""
    aid = analysis_id(player, stroke)
    base = analyses_root / aid
    new, cur, held = base / "nueva", base / "actual", base / "pendiente"
    if new.exists():                                       # a build interrupted before: start it again
        shutil.rmtree(new)
    new.mkdir(parents=True)
    n = build(new)
    audit(new, new / "auditoria")
    new_json, cur_json = new / "auditoria" / "auditoria.json", cur / "auditoria" / "auditoria.json"
    verdict, md = review(new_json, cur_json)
    (new / "revision.md").write_text(md, encoding="utf-8")
    row = db.one("SELECT version FROM analyses WHERE id=?", aid)
    version = (row or {}).get("version") or 0
    name = label(db, player, stroke)
    c = counts(new_json)
    worse = cur.exists() and verdict in ("REGRESIÓN", "ERROR")
    if worse:
        _move(new, held)
        state = "pendiente de revisar"
        db.notice(f"regression_{aid}", "crit", f"{name} empeoró con la versión nueva: se sigue mostrando la versión {version}. "
                  f"La nueva queda «pendiente de revisar» ({held / 'revision.md'}).")
    else:
        if cur.exists():
            _move(cur, base / f"v{version}")
        _move(new, cur)
        if held.exists():                                  # a good version replaces an older held one
            shutil.rmtree(held, ignore_errors=True)
        version += 1
        state = "al día"
        db.clear_notice(f"regression_{aid}")
        db.notice(f"updated_{aid}", "ok", f"{name} actualizada: {c.get('ok', 0)} ✔, {c.get('falta', 0)} ✘.")
    info = {"id": aid, "player": player, "stroke": stroke, "version": version, "state": state, "verdict": verdict,
            "counts": json.dumps(c), "n_strokes": int(n or 0), "updated": now()}
    db.upsert("analyses", info)
    (base / "analisis.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info
