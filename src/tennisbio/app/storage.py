"""Disk: how much is free, what each match and analysis takes, and what can be freed without losing
anything (docs/aplicacion_local.md §5.2 «Poco espacio en disco» and §5.4 «Disco lleno a mitad»).

Three kinds of files:
- imprescindible: what took hours (manifests, results, pose/ball caches, the clips the web plays);
- regenerable: rebuilt in minutes from the above (older versions of an analysis beyond the last two,
  exports to PDF/MP4, audit screenshots);
- temporal: half-written files and temporary folders.
Only the last two are ever freed automatically. The match video is never deleted by the application:
freeing it is the user's choice, from the Storage screen."""
import shutil
from pathlib import Path

GB = 1e9
WARN_FREE = 40 * GB           # below this, a notice
AUTO_FREE = 20 * GB           # below this, the regenerable and temporary files are freed
MATCH_MARGIN = 6 * GB         # a match needs its video × 1.1 + this to start
KEEP_VERSIONS = 2             # previous versions of an analysis kept besides the current one

TEMP_SUFFIXES = (".tmp", ".part", ".partial")
TEMP_DIRS = ("tmp", "_tmp", "temp")


def _gb(b: float) -> str:
    return f"{b / GB:.1f}".replace(".", ",")


def free_bytes(path: Path) -> float:
    """Free bytes on the disk of `path` (its nearest existing parent). Tests replace this function."""
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return float(shutil.disk_usage(p).free)


def size_of(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


def need_for_match(video_size: float) -> float:
    return video_size * 1.1 + MATCH_MARGIN


def can_start_match(output: Path, video_size: float) -> tuple[bool, str]:
    """Never start a match that does not fit: the message says how much is missing."""
    free, need = free_bytes(output), need_for_match(video_size)
    if free >= need:
        return True, ""
    return False, (f"No cabe: hacen falta {need / GB:.0f} GB y quedan {free / GB:.0f} GB libres. "
                   "Libera espacio en «Almacenamiento» (por ejemplo, vídeos ya analizados); el partido sigue en la cola.")


def regenerable(output: Path) -> list[Path]:
    """What can go without losing anything: temporary files anywhere, older analysis versions beyond the
    last KEEP_VERSIONS, exports and audit screenshots of each analysis version."""
    out: list[Path] = []
    if not output.exists():
        return out
    for f in output.rglob("*"):
        if f.is_file() and f.name.endswith(TEMP_SUFFIXES):
            out.append(f)
        elif f.is_dir() and f.name in TEMP_DIRS:
            out.append(f)
    an = output / "analisis"
    for a in sorted(an.iterdir()) if an.exists() else []:
        vers = sorted((v for v in a.glob("v*") if v.is_dir() and v.name[1:].isdigit()), key=lambda v: int(v.name[1:]))
        out += vers[:-KEEP_VERSIONS] if len(vers) > KEEP_VERSIONS else []
        for v in [a / "actual", *vers[-KEEP_VERSIONS:]]:
            out += [p for p in (v / "exportar", v / "auditoria" / "capturas") if p.exists()]
    return out


def free_regenerable(output: Path) -> float:
    """Frees the regenerable and temporary files; returns the bytes freed."""
    freed = 0.0
    for p in regenerable(output):
        try:
            n = size_of(p)
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            freed += n
        except OSError:
            pass                                   # in use or already gone: the rest still goes
    return freed


def guard(db, output: Path) -> str:
    """Run before each job and every few minutes: notice below 40 GB, automatic freeing below 20 GB.
    Returns 'ok', 'aviso' or 'liberado'."""
    free = free_bytes(output)
    if free >= WARN_FREE:
        db.clear_notice("disk_low")
        return "ok"
    if free < AUTO_FREE:
        freed = free_regenerable(output)
        free = free_bytes(output)
        db.notice("disk_low", "aviso", f"Poco disco: quedan {free / GB:.0f} GB. Liberados {_gb(freed)} GB de archivos "
                  "regenerables sin perder nada." + (" Sigue por debajo de 20 GB: libera vídeos ya analizados en «Almacenamiento»."
                                                       if free < AUTO_FREE else ""))
        return "liberado"
    reg = sum(size_of(p) for p in regenerable(output))
    db.notice("disk_low", "aviso", f"Poco disco: quedan {free / GB:.0f} GB. Por debajo de 40 GB aviso; no empiezo un partido "
              f"que no quepa. Se pueden liberar {_gb(reg)} GB regenerables sin perder nada.")
    return "aviso"
