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
import time
from dataclasses import dataclass
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

    def path(self, name: str) -> Path:
        return self.dir / name


STAGES: dict[str, Stage] = {}


def stage(name, version, deps=(), settings=lambda cfg: {}, outputs=(), code=(), match_fields=None):
    def register(fn):
        STAGES[name] = Stage(name, version, tuple(deps), settings, fn, tuple(outputs), tuple(code), match_fields)
        return fn
    return register


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
        t0 = time.time()
        ctx.log(f"[{ctx.match.id}] {n}…")
        summary = STAGES[n].run(ctx) or {}
        m[n] = {"fingerprint": fp, "version": STAGES[n].version, "seconds": round(time.time() - t0, 1),
                "finished": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": summary}
        save_manifest(ctx.dir, m)          # after every stage, so an interruption loses little
        done.append(n)
    return done
