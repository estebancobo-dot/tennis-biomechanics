"""Stage times read from the manifests (11-11, request #259 and R2 of the review of the Base).

Every stage writes in its match's manifest how long its last run took («seconds») and, for the fine passes and the
detector, how long each part took («summary.seconds», only what was computed then). A stage that only re-read its caches
also writes its seconds: summing those gave «1,2-2,1 h por partido» while a run from scratch took 7,6 h. Here a run
counts as *from scratch* only when its heavy stages really computed (`stage_real`)."""
from __future__ import annotations

import json
from pathlib import Path

from .budget import REAL_RUN_S
from .faults import fault

HEAVY = ("scenes", "players", "spotting", "fine")
POSE_SHARE = 0.35        # a fine pass that computed: its pose takes most of it (0.49-1.0 measured; 0.26 re-reading)
# the real matches live in the library (biblioteca/partidos/<año>/<partido>/etapas/manifest.json), the application's
# test in <output>/_app_nuevo (with its own library inside): both are searched
SKIP = {"windows", "series", "clips", "informe", "capturas_diag", "videos", "datos", "golpes", "identidad_fotos"}


def manifests(root: Path, depth: int = 7) -> list[Path]:
    out, todo = [], [(Path(root), 0)]
    while todo:
        d, k = todo.pop()
        f = d / "manifest.json"
        if f.exists():
            out.append(f)
        if k < depth:
            try:
                todo += [(c, k + 1) for c in d.iterdir() if c.is_dir() and c.name not in SKIP]
            except OSError:  # esperado: a folder that cannot be listed is not walked
                pass
    return sorted(out)


def duration_min(man: dict) -> float | None:
    return ((man.get("probe") or {}).get("summary") or {}).get("duration_min")


def stage_real(name: str, e: dict, dur_min: float | None) -> bool:
    """Did this stage compute on its last run (not only re-read its caches)?"""
    s = float(e.get("seconds") or 0)
    thr = min(REAL_RUN_S, 2.0 * (dur_min or 30.0))
    if s < thr:
        return False
    parts = (e.get("summary") or {}).get("seconds")
    if isinstance(parts, dict):
        if name.startswith("fine"):
            pose = float(parts.get("pose") or 0)
            return pose >= thr and pose >= POSE_SHARE * s
        if name == "spotting" and "bola" in parts:
            return float(parts.get("bola") or 0) >= thr
    return True


def not_real(man: dict) -> list[str]:
    """The heavy stages of a manifest that did not compute on their last run (empty: the run counts from scratch)."""
    dur = duration_min(man)
    return [n for n in HEAVY if isinstance(man.get(n), dict) and not stage_real(n, man[n], dur)]


def _parts(e: dict) -> dict:
    """Inside a stage (the fine passes write it in their summary): seconds per part (pose, racket, ball, cut...) and
    the counts (windows, frames posed...), only what was computed then, not read from the caches."""
    sm = e.get("summary") or {}
    out = {}
    if isinstance(sm.get("seconds"), dict):
        out["partes_s"] = sm["seconds"]
    if isinstance(sm.get("counts"), dict):
        out["cuentas"] = sm["counts"]
    for k in ("windows", "confirmed", "candidates", "gate"):
        if k in sm:
            out.setdefault("resumen", {})[k] = sm[k]
    return out


def table(f: Path) -> dict | None:
    try:
        man = json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fault("lectura.opcional_danada", str(f), exc=e)
        return None
    dur = duration_min(man)
    st = {n: e for n, e in man.items() if isinstance(e, dict) and "seconds" in e}
    if not st:
        return None
    rows = sorted(({"etapa": n, "s": float(e.get("seconds") or 0), "a_la_vez_s": float(e.get("overlap_s") or 0),
                    "terminada": e.get("finished"), **_parts(e)} for n, e in st.items()), key=lambda r: -r["s"])
    wall = sum(r["s"] - r["a_la_vez_s"] for r in rows)
    for r in rows:
        r["s_por_min_video"] = round(r["s"] / dur, 2) if dur else None
        r["parte"] = round(r["s"] / sum(x["s"] for x in rows), 3) if rows else None
    f = Path(f)
    d = f.parent.parent if f.parent.name == "etapas" else f.parent
    return {"carpeta": str(d), "minutos_video": dur, "total_min": round(wall / 60, 1),
            "veces_el_video": round(wall / 60 / dur, 2) if dur else None, "etapas": rows,
            "desde_cero": not not_real(man), "releidas": not_real(man),
            "fecha": max((r["terminada"] or "") for r in rows) or None}


def roots_of(cfg: dict) -> list[Path]:
    """The output folder and, when it is elsewhere, the library."""
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    roots = [root]
    try:
        from .library import library_root
        lib = library_root(cfg)
        if lib.exists() and not str(lib.resolve()).startswith(str(root.resolve())):
            roots.append(lib)
    except Exception:  # noqa: BLE001  # esperado: without a library only the output is read
        pass
    return roots


def all_tables(roots: list[Path]) -> list[dict]:
    seen, res = set(), []
    for r in roots:
        for f in manifests(r):
            if f.resolve() not in seen and (t := table(f)):
                seen.add(f.resolve())
                res.append(t)
    return res


def latest_from_scratch(tables: list[dict], min_video_min: float = 20.0, since: str | None = None) -> dict | None:
    """The run from scratch of at least `min_video_min` minutes of video that counts: the slowest per minute of video of
    those since `since` (a date; 11-11: the same code took 1.41 times the video on the 50 fps final and 2.17 on the
    60 fps Pegula clip, and «a 3.5 h match in one night» must hold for every video), else the most recent one."""
    ok = [t for t in tables if t["desde_cero"] and (t["minutos_video"] or 0) >= min_video_min and t.get("fecha")]
    if not ok:
        return None
    recent = [t for t in ok if since and t["fecha"][:10] >= since]
    if recent:
        return max(recent, key=lambda t: t["total_min"] / t["minutos_video"])
    return max(ok, key=lambda t: t["fecha"])
