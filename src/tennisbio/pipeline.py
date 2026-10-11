"""Incremental per-match pipeline.

Each stage writes one output in <output>/<match_id>/ and records in manifest.json the
fingerprint of what it was computed from: the video (size + modification time), the settings
it uses, its own version and the fingerprints of the stages it depends on. `run` executes a
stage only when that fingerprint changed, so adding a match runs everything for it, changing a
metric formula reruns only the metrics, and manual review files are never touched.
"""
import hashlib
import json
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


@dataclass
class Context:
    match: Match
    cfg: dict
    dir: Path
    log: Callable[[str], None] = print

    def path(self, name: str) -> Path:
        return self.dir / name


STAGES: dict[str, Stage] = {}


def stage(name, version, deps=(), settings=lambda cfg: {}):
    def register(fn):
        STAGES[name] = Stage(name, version, tuple(deps), settings, fn)
        return fn
    return register


def video_fingerprint(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def load_manifest(d: Path) -> dict:
    p = d / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_manifest(d: Path, m: dict):
    (d / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")


def fingerprint(name: str, ctx: Context, manifest: dict) -> str:
    st = STAGES[name]
    return _hash({"stage": name, "version": st.version, "video": video_fingerprint(ctx.match.video),
                  "settings": st.settings(ctx.cfg), "deps": {d: manifest.get(d, {}).get("fingerprint") for d in st.deps}})


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
            res[n] = "ok" if m[n]["fingerprint"] == expected[n]["fingerprint"] else "stale"
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
        if not (force and n in requested) and m.get(n, {}).get("fingerprint") == fp:
            continue
        t0 = time.time()
        ctx.log(f"[{ctx.match.id}] {n}…")
        summary = STAGES[n].run(ctx) or {}
        m[n] = {"fingerprint": fp, "version": STAGES[n].version, "seconds": round(time.time() - t0, 1),
                "finished": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": summary}
        save_manifest(ctx.dir, m)          # after every stage, so an interruption loses little
        done.append(n)
    return done
