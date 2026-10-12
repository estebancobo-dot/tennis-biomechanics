"""Incremental per-match pipeline.

Each stage writes one output in <output>/<match_id>/ and records in manifest.json the
fingerprint of what it was computed from: the video (size + modification time), the settings
it uses, its own version and the fingerprints of the stages it depends on. `run` executes a
stage only when that fingerprint changed, so adding a match runs everything for it, changing a
metric formula reruns only the metrics, and manual review files are never touched.
"""
import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .catalog import Match


@dataclass
class Stage:
    name: str
    version: str
    deps: tuple[str, ...]
    settings: Callable[[dict], dict]          # the part of the config this stage depends on
    run: Callable[["Context"], dict]          # returns a small summary for the log
    outputs: tuple[str, ...] = ()             # files that must exist for the stage to be up to date
    code: tuple[str, ...] = ()                # modules whose source is part of the fingerprint
    match_fields: Callable | None = None      # the part of the match/player profile it depends on


@dataclass
class Context:
    match: Match
    cfg: dict
    dir: Path
    log: Callable[[str], None] = print
    _prog: dict = field(default_factory=dict, repr=False)

    def path(self, name: str) -> Path:
        return self.dir / name

    def progress(self, done: int, total: int, what: str = "", every_s: float = 30.0):
        """Progress of the running stage: a line with %, elapsed time and the time left, at most every
        `every_s` seconds (and at the end), and the file <output>/progreso.json that the PC uploads
        for Claude with the logs. Nobody has to watch a silent window for hours."""
        now = time.time()
        p = self._prog
        done = min(done, total)
        if p.get("stage") != p.get("_seen"):
            p.update(_seen=p.get("stage"), t0=now, last=0.0, ended=False)
        if p["ended"] or (done < total and now - p["last"] < every_s):
            return
        p["last"], p["ended"] = now, done >= total
        el = now - p["t0"]
        frac = done / total if total else 1.0
        left = el * (1 - frac) / frac if frac > 0 else None
        fmt = lambda s: "?" if s is None else (f"{s / 60:.0f} min" if s >= 90 else f"{s:.0f} s")
        msg = f"  {p.get('stage', '')}: {frac * 100:3.0f} % ({done}/{total}{' ' + what if what else ''}) · {fmt(el)} · quedan ≈ {fmt(left)}"
        self.log(msg)
        try:
            write_atomic(self.dir.parent / "progreso.json", json.dumps({
                "partido": self.match.id, "etapa": p.get("stage"), "hecho": done, "total": total,
                "porcentaje": round(frac * 100, 1), "segundos": round(el), "quedan_s": None if left is None else round(left),
                "hora": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False))
        except OSError:
            pass

    @property
    def video(self) -> Path:
        """The video the stages read: the match video, or its clean copy when the probe stage had
        to rewrite its timeline (see stages.st_probe)."""
        src = self.dir / "source.mkv"
        return src if src.exists() and (self.dir / "source.json").exists() else self.match.video


STAGES: dict[str, Stage] = {}


def stage(name, version, deps=(), settings=lambda cfg: {}, outputs=(), code=(), match_fields=None):
    def register(fn):
        STAGES[name] = Stage(name, version, tuple(deps), settings, fn, tuple(outputs), tuple(code), match_fields)
        return fn
    return register


MIN_FREE_BYTES = 3e9          # below this a stage could fill the disk half-way


class DiskFull(RuntimeError):
    """Not enough free disk to run a stage safely; the message is for the user (Spanish)."""


class MissingVideo(FileNotFoundError):
    """The match video is gone (deleted to free disk): its results are kept, nothing is re-run."""


def video_fingerprint(path: Path) -> str:
    try:
        st = path.stat()
    except (FileNotFoundError, TypeError):
        raise MissingVideo(str(path)) from None
    return f"{st.st_size}-{int(st.st_mtime)}"


_code_cache: dict = {}


def code_fingerprint(modules: tuple[str, ...]) -> str:
    """Hash of the source of the modules a stage runs: changing a formula re-runs that stage."""
    key = tuple(modules)
    if key not in _code_cache:
        root = Path(__file__).resolve().parent
        h = hashlib.sha1()
        for m in modules:
            f = root / (m.replace(".", "/") + ".py")
            if f.exists():
                h.update(f.read_bytes().replace(b"\r\n", b"\n"))
        _code_cache[key] = h.hexdigest()[:16]
    return _code_cache[key]


def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def write_atomic(path: Path, text: str):
    """Write through a temporary file: an interruption never leaves a half-written file behind."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def savez_atomic(path, **arrays):
    """np.savez_compressed through a temporary file (an interrupted run leaves no broken cache)."""
    import numpy as np

    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        np.savez_compressed(f, **arrays)
    os.replace(tmp, path)


def save_npy_atomic(path, arr):
    import numpy as np

    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        np.save(f, arr)
    os.replace(tmp, path)


def load_npz(path):
    """Load a cache; a damaged one is deleted and None returned, so it gets recomputed."""
    import numpy as np

    path = Path(path)
    if not path.exists():
        return None
    try:
        d = np.load(path, allow_pickle=True)
        d = {k: d[k] for k in d.files}
        return d
    except Exception:
        path.unlink(missing_ok=True)
        return None


def load_manifest(d: Path) -> dict:
    p = d / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):     # damaged: start over for this match
        p.replace(p.with_name("manifest.damaged.json"))
        return {}


def save_manifest(d: Path, m: dict):
    write_atomic(d / "manifest.json", json.dumps(m, indent=1, ensure_ascii=False))


def fingerprint(name: str, ctx: Context, manifest: dict) -> str:
    st = STAGES[name]
    return _hash({"stage": name, "version": st.version, "video": video_fingerprint(ctx.match.video),
                  "settings": st.settings(ctx.cfg), "code": code_fingerprint(st.code) if st.code else None,
                  "match": st.match_fields(ctx.match) if st.match_fields else None,
                  "deps": {d: manifest.get(d, {}).get("fingerprint") for d in st.deps}})


def outputs_ok(name: str, ctx: Context) -> bool:
    return all(ctx.path(o).exists() for o in STAGES[name].outputs)


def order(names) -> list[str]:
    """Stages in dependency order (dependencies included)."""
    out, seen = [], set()

    def visit(n):
        if n in seen:
            return
        for d in STAGES[n].deps:
            visit(d)
        seen.add(n)
        out.append(n)
    for n in names:
        visit(n)
    return out


def status(ctx: Context) -> dict[str, str]:
    """'ok' (up to date), 'stale' (inputs changed, also upstream) or 'missing' for every stage."""
    m = load_manifest(ctx.dir)
    expected = {}                      # what each fingerprint would be after re-running upstream
    res = {}
    for n in order(STAGES):
        expected[n] = {"fingerprint": fingerprint(n, ctx, expected)}
        if n not in m:
            res[n] = "missing"
        else:
            res[n] = "ok" if m[n]["fingerprint"] == expected[n]["fingerprint"] and outputs_ok(n, ctx) else "stale"
    return res


def run(ctx: Context, names=None, force=False) -> list[str]:
    """Run the requested stages (default: all) that are missing or stale, plus whatever upstream is
    missing or stale. force re-runs the requested stages only, not their dependencies."""
    ctx.dir.mkdir(parents=True, exist_ok=True)
    m = load_manifest(ctx.dir)
    done = []
    requested = set(names or STAGES)
    for n in order(names or list(STAGES)):
        fp = fingerprint(n, ctx, m)
        if not (force and n in requested) and m.get(n, {}).get("fingerprint") == fp and outputs_ok(n, ctx):
            continue
        free = shutil.disk_usage(ctx.dir).free
        if free < MIN_FREE_BYTES:
            raise DiskFull(f"Queda muy poco espacio en el disco ({free / 1e9:.1f} GB libres en {ctx.dir.anchor or ctx.dir}). "
                           "Libera al menos 5 GB (por ejemplo, borra vídeos ya analizados) y vuelve a ejecutar: "
                           "se sigue donde se quedó.")
        t0 = time.time()
        k = order(names or list(STAGES)).index(n) + 1
        ctx.log(f"[{ctx.match.id}] {n}… ({time.strftime('%H:%M')}, etapa {k} de {len(STAGES)})")
        ctx._prog["stage"] = n
        summary = STAGES[n].run(ctx) or {}
        ctx.log(f"[{ctx.match.id}] {n} terminada en {(time.time() - t0) / 60:.1f} min")
        m[n] = {"fingerprint": fp, "version": STAGES[n].version, "seconds": round(time.time() - t0, 1),
                "finished": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": summary}
        save_manifest(ctx.dir, m)          # after every stage, so an interruption loses little
        done.append(n)
    return done
