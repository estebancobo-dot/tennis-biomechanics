"""Backup to a USB drive (docs/aplicacion_local.md §4 «Almacenamiento», part 3).

What hours of work produced goes to <drive>\\tennisbio_copia\\: the index, the players' files and the
catalogue, every match folder (results, caches and the clips the web plays) and the analyses in use.
Older analysis versions and temporary files are left out (they are regenerable); the match videos only when
asked (they are large and the user usually still has them). Incremental: a file already there with the same
size and date is not copied again. Nothing is ever deleted, neither on the PC nor on the drive."""
import shutil
import sqlite3
import sys
import time
from pathlib import Path

from ..config import CONFIG_DIR
from . import storage
from .db import now

FOLDER = "tennisbio_copia"


def removable_drives() -> list[dict]:
    """USB drives and memory cards connected now (Windows: drive type «removable»), with their free space."""
    out = []
    if sys.platform != "win32":
        return out
    import ctypes
    import string
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask >> i & 1:
            continue
        root = f"{letter}:\\"
        if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 2:          # DRIVE_REMOVABLE
            try:
                du = shutil.disk_usage(root)
                out.append({"root": root, "free": du.free, "total": du.total})
            except OSError:
                continue
    return out


def _files(app, videos: bool) -> list[tuple[Path, Path]]:
    """(source, path inside the copy) of everything that goes."""
    regen = {str(p) for p in storage.regenerable(app.paths.output)}
    skip = lambda f: any(str(f).startswith(r) for r in regen)
    out: list[tuple[Path, Path]] = []
    cdir = getattr(app, "config_dir", CONFIG_DIR)
    for f in sorted((cdir / "players").glob("*.yaml")):
        out.append((f, Path("config") / "players" / f.name))
    for name in ("matches.yaml", "local.yaml"):
        if (cdir / name).exists():
            out.append((cdir / name, Path("config") / name))
    for m in app.db.q("SELECT id FROM matches WHERE state <> 'archivado' OR state IS NULL"):
        d = app.engine.dir(m["id"])
        if d.exists():
            rel = d.relative_to(app.paths.output)
            out += [(f, Path("output") / rel / f.relative_to(d)) for f in d.rglob("*") if f.is_file() and not skip(f)]
    for a in sorted(app.paths.analyses.glob("*")) if app.paths.analyses.exists() else []:
        for sub in ("actual",):
            if (a / sub).exists():
                out += [(f, Path("output") / "analisis" / a.name / f.relative_to(a)) for f in (a / sub).rglob("*")
                        if f.is_file() and not skip(f)]
        if (a / "analisis.json").exists():
            out.append((a / "analisis.json", Path("output") / "analisis" / a.name / "analisis.json"))
    if videos:
        for r in app.db.q("SELECT DISTINCT v.path FROM videos v JOIN matches m ON m.video = v.sample WHERE v.path <> ''"):
            p = Path(r["path"])
            if p.is_file():
                out.append((p, Path("videos") / p.name))
    return out


def _same(src: Path, dst: Path) -> bool:
    try:
        a, b = src.stat(), dst.stat()
    except OSError:
        return False
    return a.st_size == b.st_size and abs(a.st_mtime - b.st_mtime) < 2.5        # FAT keeps 2 s


def plan(app, dest_root: Path, videos: bool = False) -> dict:
    """What a copy would do now: files and bytes to copy, and whether they fit on the drive."""
    base = Path(dest_root) / FOLDER
    todo = [(s, base / r) for s, r in _files(app, videos) if not _same(s, base / r)]
    need = sum(s.stat().st_size for s, _ in todo)
    free = storage.free_bytes(Path(dest_root))
    return {"files": len(todo), "bytes": need, "free": free, "fits": need + 50e6 <= free, "todo": todo, "dest": str(base)}


def run(app, dest_root: Path, videos: bool = False, progress=None) -> dict:
    """Copies what changed since the last copy. Returns {copied, bytes, errors, seconds, dest}; refuses
    (without copying anything) when it does not fit."""
    t0 = time.time()
    p = plan(app, dest_root, videos)
    if not p["fits"]:
        raise RuntimeError(f"No cabe en el USB: hacen falta {storage._gb(p['bytes'])} GB y tiene {storage._gb(p['free'])} GB libres.")
    base = Path(p["dest"])
    base.mkdir(parents=True, exist_ok=True)
    copied, done_b, errors = 0, 0, []
    for i, (src, dst) in enumerate(p["todo"]):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".part")
            shutil.copy2(src, tmp)
            tmp.replace(dst)                         # a pulled-out drive never leaves a half file under the real name
            copied += 1
            done_b += src.stat().st_size
        except OSError as e:
            errors.append(f"{src.name}: {e}")
        if progress:
            progress(i + 1, len(p["todo"]), done_b)
    # the index, consistent even while the queue writes to it
    try:
        (base / "datos").mkdir(exist_ok=True)
        dst = sqlite3.connect(str(base / "datos" / "tennisbio.db"))
        with app.db.lock:
            app.db.con.backup(dst)
        dst.close()
    except (sqlite3.Error, OSError) as e:
        errors.append(f"índice: {e}")
    res = {"when": now(), "dest": str(base), "copied": copied, "bytes": done_b, "errors": errors[:20],
           "seconds": round(time.time() - t0, 1), "videos": videos}
    app.db.set_setting("copia", res)
    return res
