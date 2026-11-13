"""The matches analysed again from scratch (12-11, requests #262-#263: «no quiero usar nada desactualizado o datos
anteriores»). Everything an analysis computed in a match folder is moved to an archive with the date (never deleted:
it can be compared or brought back), and the folder keeps only what is not computed: the match's own record
(partido.json), the user's click of who she is (identidad_clic.json, her decision, 19-10) and the video when it lives
in the folder (source.mkv and its source.json). Then `run --all` finds nothing to reuse: every stage, and every cache
inside the fine pass (pose, ball and racket of each window, the match's ball track), is computed by the code of now.

    tennisbio desde-cero              # what would move, nothing moved (also <output>/capturas_diag/desde_cero.json)
    tennisbio desde-cero --ejecutar   # moves it (the PC's flow «desde_cero», only with the user's approval, #262)
    tennisbio desde-cero --ejecutar --match osaka pegula   # a batch of matches (then run --match with the same ones)
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from . import match_files as _mf

# relative to a library match folder (etapas/ holds the cheap pass); a flat folder has them at its root
KEEP_LIBRARY = ("partido.json", "etapas/identidad_clic.json", "etapas/source.mkv", "etapas/source.json")
KEEP_FLAT = ("identidad_clic.json", "source.mkv", "source.json", "partido.json")


def select(matches: list, wanted: list[str] | None) -> list:
    """The matches whose id contains any of `wanted` (all of them without it)."""
    if not wanted:
        return list(matches)
    w = [x.lower() for x in wanted]
    return [m for m in matches if any(x in m.id.lower() for x in w)]


def keep_of(d: Path) -> set[str]:
    return set(KEEP_LIBRARY if _mf.is_library(d) else KEEP_FLAT)


def plan(d: Path) -> dict:
    """What moves out of one match folder: {"move": [relative paths], "keep": [...], "bytes": n}. Only whole entries:
    a top-level file or folder, or inside etapas/ of a library folder (where the kept files live)."""
    d = Path(d)
    keep = keep_of(d)
    move, kept, size = [], [], 0
    if not d.is_dir():
        return {"move": [], "keep": [], "bytes": 0}
    entries = []
    for p in sorted(d.iterdir()):
        if p.is_dir() and any(k.startswith(p.name + "/") for k in keep):
            entries += sorted(p.iterdir())          # etapas/: entry by entry, the kept ones stay
        else:
            entries.append(p)
    for p in entries:
        rel = p.relative_to(d).as_posix()
        if rel in keep:
            kept.append(rel)
            continue
        move.append(rel)
        size += sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
    return {"move": move, "keep": kept, "bytes": size}


def archive(d: Path, dest: Path, moves: list[str]) -> int:
    """Moves each relative path of `moves` from d to dest (same relative path). Same drive: a rename, no copy."""
    n = 0
    for rel in moves:
        src, dst = Path(d) / rel, Path(dest) / rel
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dst)
        except OSError:  # esperado: another drive: moved by copying
            shutil.move(str(src), str(dst))
        n += 1
    return n


def archive_root(d: Path, cfg: dict, out_root: Path, stamp: str) -> Path:
    """Where a match folder's analysis goes: <library>/archivo/desde_cero_<stamp>/<its path in the library> for a
    library folder, <output>/archivo/desde_cero_<stamp>/<folder> for a flat one."""
    from .library import library_root
    d = Path(d).resolve()
    lib = library_root(cfg)
    if lib is not None:
        try:
            return Path(lib) / "archivo" / f"desde_cero_{stamp}" / d.relative_to(Path(lib).resolve())
        except ValueError:  # esperado: not in the library: the output's archive
            pass
    return Path(out_root) / "archivo" / f"desde_cero_{stamp}" / d.name


def run(cfg: dict, out_root: Path, dirs: list[Path], execute: bool = False, stamp: str | None = None) -> dict:
    """The plan for every match folder and, with execute, the moves. Returns the report also written to
    <output>/capturas_diag/desde_cero.json."""
    stamp = stamp or time.strftime("%Y%m%d_%H%M")
    rep = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "ejecutado": execute, "partidos": []}
    for d in dirs:
        p = plan(d)
        row = {"carpeta": str(d), "mueve": len(p["move"]), "conserva": p["keep"], "gb": round(p["bytes"] / 1e9, 2),
               "archivo": str(archive_root(d, cfg, out_root, stamp)), "ejemplos": p["move"][:12]}
        if not p["keep"] or not any(k.endswith("identidad_clic.json") for k in p["keep"]):
            row["aviso"] = "sin clic de identidad guardado: la identidad será la automática"
        if execute:
            row["movidos"] = archive(d, Path(row["archivo"]), p["move"])
        rep["partidos"].append(row)
    dst = Path(out_root) / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "desde_cero.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep
