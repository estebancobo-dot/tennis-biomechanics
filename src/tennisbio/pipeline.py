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
import queue
import shutil
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from .catalog import Match
from .match_files import at as _at, is_library


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
    # what the stage mostly keeps busy ("gpu", "cpu"): with `pipeline.parallel`, two ready stages with
    # different resources run at the same time (players on the iGPU while score does OCR on the CPU).
    # None: the stage runs alone, as always. A function of the config can decide it (the pose model
    # is on the CPU too when there is no iGPU: then it is not run beside the OCR).
    resource: str | Callable[[dict], str | None] | None = None
    # the user's own decisions in the match folder (never overwritten): their content is part of the
    # fingerprint, so a new decision re-runs this stage and what follows (19-10: the identity click)
    reviews: tuple[str, ...] = ()
    # dependencies that only apply with some settings (20-10: candidates reads spotting.json only with
    # `spotter.enabled`). Empty: the fingerprint is the one it always was (no new key in its deps).
    cfg_deps: Callable[[dict], tuple] | None = None

    def all_deps(self, cfg: dict | None) -> tuple[str, ...]:
        """deps plus the ones the config adds (cfg None: deps only)."""
        extra = tuple(self.cfg_deps(cfg)) if self.cfg_deps is not None and cfg is not None else ()
        return self.deps + tuple(d for d in extra if d not in self.deps)


@dataclass
class Context:
    match: Match
    cfg: dict
    dir: Path
    log: Callable[[str], None] = print
    _prog: dict = field(default_factory=dict, repr=False)

    def path(self, name: str) -> Path:
        """A file of this match: in the folder itself, or in the library's etapas/ or golpes/<jugadora>/
        (tennisbio.match_files)."""
        return _at(self.dir, name)

    def progress(self, done: int, total: int, what: str = "", every_s: float = 30.0):
        """Progress of the running stage: a line with %, elapsed time and the time left, at most every
        `every_s` seconds (and at the end), and the file <output>/progreso.json that the PC uploads
        for Claude with the logs. Nobody has to watch a silent window for hours."""
        now = time.time()
        p = self._prog
        done = min(done, total)
        if p.get("stage") != p.get("_seen"):
            p.update(_seen=p.get("stage"), t0=now, last=0.0, ended=False, alarmed=False)
        if p["ended"] or (done < total and now - p["last"] < every_s):
            return
        p["last"], p["ended"] = now, done >= total
        el = now - p["t0"]
        frac = done / total if total else 1.0
        left = el * (1 - frac) / frac if frac > 0 else None
        fmt = lambda s: "?" if s is None else (f"{s / 60:.0f} min" if s >= 90 else f"{s:.0f} s")
        msg = f"  {p.get('stage', '')}: {frac * 100:3.0f} % ({done}/{total}{' ' + what if what else ''}) · {fmt(el)} · quedan ≈ {fmt(left)}"
        self.log(msg)
        # time budget (tennisbio.budget, 03-11): an alarm as soon as the stage runs far slower than it should, and
        # the finished stage's rate per unit for the next runs; never stops the stage
        try:
            from . import budget
            out = self.progress_file().parent
            if p["ended"]:
                if el >= budget.REAL_RUN_S:
                    budget.record_unit(out, p.get("stage", ""), el / max(1, total), total, self.match.id)
            elif not p.get("alarmed"):
                al = budget.check(self.cfg, out, p.get("stage", ""), el, done, total)
                if al:
                    p["alarmed"] = True
                    self.log(f"  ALARMA de tiempo: {al}")
                    budget.raise_alarm(out, self.match.id, p.get("stage", ""), al)
        except Exception:  # noqa: BLE001 — the budget never breaks a stage
            pass
        try:
            with _PROGRESS_LOCK:            # two stages at once write the same file
                write_atomic(self.progress_file(), json.dumps({
                    "partido": self.match.id, "etapa": p.get("stage"), "hecho": done, "total": total,
                    "porcentaje": round(frac * 100, 1), "segundos": round(el), "quedan_s": None if left is None else round(left),
                    "hora": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False))
        except OSError:
            pass

    def progress_file(self) -> Path:
        """<output>/progreso.json (the PC uploads it); beside the match folder before the library."""
        out = (self.cfg.get("paths") or {}).get("output") if is_library(self.dir) else None
        return Path(out) / "progreso.json" if out else self.dir.parent / "progreso.json"

    @property
    def video(self) -> Path:
        """The video the stages read: the match video, or its clean copy when the probe stage had
        to rewrite its timeline (see stages.st_probe)."""
        src = self.path("source.mkv")
        return src if src.exists() and self.path("source.json").exists() else self.match.video


_PROGRESS_LOCK = threading.Lock()

STAGES: dict[str, Stage] = {}


def stage(name, version, deps=(), settings=lambda cfg: {}, outputs=(), code=(), match_fields=None, resource=None,
          reviews=(), cfg_deps=None):
    def register(fn):
        STAGES[name] = Stage(name, version, tuple(deps), settings, fn, tuple(outputs), tuple(code), match_fields, resource,
                             tuple(reviews), cfg_deps)
        return fn
    return register


MIN_FREE_BYTES = 3e9          # below this a stage could fill the disk half-way


class DiskFull(RuntimeError):
    """Not enough free disk to run a stage safely; the message is for the user (Spanish)."""


class MissingVideo(FileNotFoundError):
    """The match video is gone (deleted to free disk): its results are kept, nothing is re-run."""


def video_sample(path: Path, chunks: int = 8, size: int = 1 << 20) -> str:
    """Hash of 8 pieces of 1 MB spread over the file (the first and the last included): tells two
    videos apart in a fraction of a second, without reading 5 GB."""
    n = path.stat().st_size
    h = hashlib.sha1(str(n).encode())
    with open(path, "rb") as f:
        for i in range(chunks):
            f.seek(max(0, (n - size) * i // max(1, chunks - 1)))
            h.update(f.read(size))
    return h.hexdigest()[:16]


def video_fingerprint(path: Path, d: Path | None = None) -> str:
    """Identity of a match's video. Size and modification date, pinned in <match>/video.json the first
    time: moving or copying the same video (new date) keeps the identity when its content (size and
    sampled pieces) is the same, so nothing is recomputed; a different video gets a new identity. The
    identity of folders analysed before stays the same as before (no recomputation on adoption)."""
    try:
        st = path.stat()
    except (FileNotFoundError, TypeError):
        raise MissingVideo(str(path)) from None
    legacy = f"{st.st_size}-{int(st.st_mtime)}"
    if d is None:
        return legacy
    p = _at(d, "video.json")
    try:
        rec = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        rec = None
    if rec and rec.get("size") == st.st_size:
        if rec.get("mtime") == int(st.st_mtime):
            return rec["fp"]
        if rec.get("sample") == video_sample(path):          # the same video, moved or copied
            rec["mtime"] = int(st.st_mtime)
            write_atomic(p, json.dumps(rec))
            return rec["fp"]
    rec = {"fp": legacy, "size": st.st_size, "mtime": int(st.st_mtime), "sample": video_sample(path)}
    p.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(p, json.dumps(rec))
    return legacy


_code_cache: dict = {}


def _norm_src(src: str) -> str:
    """Source as syntax: comments, docstrings and formatting do not count (a comment never re-runs hours of work)."""
    import ast
    tree = ast.parse(src)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            body.pop(0)
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


def _reachable_src(src: str, entry: str) -> str:
    """The part of a module a stage runs: its function and every top-level function, class or constant of the same
    module it reaches by name (transitively), as normalised syntax. Editing another stage in stages.py no longer
    changes this stage's fingerprint (10-11: identity v10 re-ran the fine pass of every match for hours)."""
    import ast
    tree = ast.parse(src)
    defs: dict[str, list] = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.setdefault(n.name, []).append(n)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        defs.setdefault(x.id, []).append(n)
    if entry not in defs:
        return _norm_src(src)
    seen, todo = set(), [entry]
    while todo:
        k = todo.pop()
        if k in seen or k not in defs:
            continue
        seen.add(k)
        for node in defs[k]:
            todo += [x.id for x in ast.walk(node) if isinstance(x, ast.Name) and x.id in defs]
    parts = []
    for k in sorted(seen):
        for node in defs[k]:
            parts.append(_norm_src(ast.unparse(node)))
    return "\n".join(dict.fromkeys(parts))


def code_fingerprint(modules: tuple[str, ...], entry: str | None = None) -> str:
    """Hash of the code a stage runs: changing a formula re-runs that stage, a comment or another stage does not.
    Each module counts as normalised syntax; the module that defines the stage (stages.py, view_stages.py) counts
    only by what its function reaches (entry: the stage function's name)."""
    key = (tuple(modules), entry)
    if key not in _code_cache:
        root = Path(__file__).resolve().parent
        h = hashlib.sha1(b"code2")
        for m in modules:
            f = root / (m.replace(".", "/") + ".py")
            if f.exists():
                src = f.read_text(encoding="utf-8")
                h.update(m.encode())
                h.update((_reachable_src(src, entry) if entry and m in ("stages", "view_stages") else _norm_src(src)).encode())
        _code_cache[key] = h.hexdigest()[:16]
    return _code_cache[key]


def function_fingerprint(module: str, entry: str) -> str:
    """Hash of one function of a module and everything of that module it reaches by name (12-11, for caches made by
    one function of a large module: the match's ball track by ball_features.track_play)."""
    key = ((module,), "fn:" + entry)
    if key not in _code_cache:
        f = Path(__file__).resolve().parent / (module.replace(".", "/") + ".py")
        src = f.read_text(encoding="utf-8") if f.exists() else ""
        _code_cache[key] = hashlib.sha1((module + _reachable_src(src, entry)).encode()).hexdigest()[:16] if src else ""
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
    p = _at(d, "manifest.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):     # damaged: start over for this match
        p.replace(p.with_name("manifest.damaged.json"))
        return {}


def save_manifest(d: Path, m: dict):
    write_atomic(_at(d, "manifest.json"), json.dumps(m, indent=1, ensure_ascii=False))


# Volatile keys of a stage's JSON outputs (times, dates): they change at every run without changing the result, so
# they are left out of the content hash that the next stages depend on
VOLATILE = {"took", "seconds", "elapsed", "finished", "started", "created", "date", "fecha", "hora", "timing", "times",
            "minutes", "duration_s", "wall_s"}


def _stable(o):
    if isinstance(o, dict):
        return {k: _stable(v) for k, v in sorted(o.items()) if k not in VOLATILE}
    if isinstance(o, list):
        return [_stable(v) for v in o]
    return o


def output_hash(name: str, ctx: Context) -> str | None:
    """Hash of the CONTENT of a stage's outputs (04-11, docs/plan_corto_plazo.md 1.7): what the next stages depend
    on, instead of the stage's own fingerprint, so a change upstream that leaves an output as it was re-runs nothing
    below it. JSON is hashed without its volatile keys (times, dates); other files byte for byte. None when the
    stage declares no outputs (then the next stages depend on its fingerprint, as before)."""
    outs = STAGES[name].outputs
    if not outs:
        return None
    h = hashlib.sha1()
    for o in sorted(outs):
        p = ctx.path(o)
        h.update(o.encode())
        if not p.exists():
            h.update(b"<missing>")
            continue
        if p.suffix == ".json":
            try:
                h.update(json.dumps(_stable(json.loads(p.read_text(encoding="utf-8"))), sort_keys=True,
                                    ensure_ascii=False).encode())
                continue
            except (ValueError, UnicodeDecodeError):
                pass
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()[:20]


def _dep_key(manifest: dict, d: str):
    e = manifest.get(d, {})
    return e.get("out_hash") or e.get("fingerprint")


def fingerprint(name: str, ctx: Context, manifest: dict, by_content: bool = True) -> str:
    """by_content (scheme 2, 04-11): a dependency counts by the content of its outputs (out_hash); False: by its
    fingerprint, the former scheme (only to recognise manifests written before, see _migrate)."""
    st = STAGES[name]
    key = {"stage": name, "version": st.version, "video": video_fingerprint(ctx.match.video, ctx.dir),
           "settings": st.settings(ctx.cfg), "code": code_fingerprint(st.code, st.run.__name__) if st.code else None,
           "match": st.match_fields(ctx.match) if st.match_fields else None,
           "deps": {d: (_dep_key(manifest, d) if by_content else manifest.get(d, {}).get("fingerprint"))
                    for d in st.all_deps(ctx.cfg)}}
    if st.reviews:                    # only stages that have them: the others keep their fingerprints
        key["reviews"] = {f: (hashlib.sha1(ctx.path(f).read_bytes()).hexdigest()[:16] if ctx.path(f).exists() else None)
                          for f in st.reviews}
    return _hash(key)


def outputs_ok(name: str, ctx: Context) -> bool:
    return all(ctx.path(o).exists() for o in STAGES[name].outputs)


# A stage may add to an output of one of its dependencies in place (views_link writes the `views` of each stroke
# into fine's strokes.json). When that dependency runs again and writes the same content as before, its out_hash
# does not change, so the stage that wrote into it looked up to date while its additions were gone (#218, 08-11:
# 0 strokes with replays in Osaka and Gauff, whose fine pass re-ran after views_link with the same result). The
# stage records what it left in those files (`rewrote`: dependency → hash of its outputs after the stage) and is
# stale while they no longer hold it.
REWROTE = "rewrote"
LEGACY_CHEAP_S = 10.0     # entries written before `rewrote` existed: a stage this fast whose dependency ran after it


def _json_outputs_hash(name: str, ctx: Context) -> str | None:
    """output_hash of a stage whose outputs are all JSON (the only ones a later stage rewrites in place, and cheap
    to hash before and after every stage); None for the others."""
    outs = STAGES[name].outputs
    if not outs or not all(o.endswith(".json") for o in outs):
        return None
    return output_hash(name, ctx)


def rewrites_lost(name: str, ctx: Context, m: dict) -> bool:
    """Whether a stage's additions to its dependencies' outputs are gone (the dependency re-ran after it). Entries
    written before `rewrote` existed: re-run once when they are cheap (≤ LEGACY_CHEAP_S) and a dependency finished
    after them (possibly overwriting what they wrote), which also records their `rewrote` from then on."""
    e = m.get(name) or {}
    if REWROTE in e:
        return any(_json_outputs_hash(d, ctx) != h for d, h in (e[REWROTE] or {}).items())
    if not e or float(e.get("seconds") or 0) > LEGACY_CHEAP_S or not e.get("finished"):
        return False
    return any(str((m.get(d) or {}).get("finished") or "") > e["finished"] for d in STAGES[name].all_deps(ctx.cfg))


def order(names, cfg: dict | None = None) -> list[str]:
    """Stages in dependency order (dependencies included; with cfg, also those the config adds)."""
    out, seen = [], set()

    def visit(n):
        if n in seen:
            return
        for d in STAGES[n].all_deps(cfg):
            visit(d)
        seen.add(n)
        out.append(n)
    for n in names:
        visit(n)
    return out


SCHEME = 2


def _migrate(ctx: Context, m: dict) -> bool:
    """A manifest written with the former scheme (dependencies by fingerprint) moves to the content scheme without
    re-running anything: every stage still up to date by the former rule gets the hash of its outputs and its
    fingerprint in the new scheme; the others stay as they were (stale either way). Returns whether it changed."""
    old = {n: dict(e) for n, e in m.items() if isinstance(e, dict) and "fingerprint" in e}
    if not old or all(e.get("scheme") == SCHEME for e in old.values()):
        return False
    for n in order(STAGES, ctx.cfg):
        if n not in old or old[n].get("scheme") == SCHEME:
            continue
        if old[n]["fingerprint"] == fingerprint(n, ctx, old, by_content=False) and outputs_ok(n, ctx):
            m[n]["out_hash"] = output_hash(n, ctx)
            m[n]["fingerprint"] = fingerprint(n, ctx, m)
        m[n]["scheme"] = SCHEME                  # moved over (or stale either way): never looked at again
    return True


def status(ctx: Context) -> dict[str, str]:
    """'ok' (up to date), 'stale' (its own inputs changed), 'upstream' (only a stage above will re-run: this one
    re-runs only if that one's outputs come out different) or 'missing', for every stage."""
    m = load_manifest(ctx.dir)
    if _migrate(ctx, m):
        save_manifest(ctx.dir, m)
    res = {}
    for n in order(STAGES, ctx.cfg):
        if n not in m:
            res[n] = "missing"
            continue
        ok_own = m[n]["fingerprint"] == fingerprint(n, ctx, m) and outputs_ok(n, ctx) and not rewrites_lost(n, ctx, m)
        above = [d for d in STAGES[n].all_deps(ctx.cfg) if res.get(d) in ("stale", "missing", "upstream")]
        res[n] = "stale" if not ok_own else ("upstream" if above else "ok")
    return res


def parallel_enabled(cfg: dict) -> bool:
    """`pipeline.parallel` in the config (default on): stages with different resources at once."""
    return bool((cfg.get("pipeline") or {}).get("parallel", True))


def resource(name: str, cfg: dict) -> str | None:
    r = STAGES[name].resource
    return r(cfg) if callable(r) else r


def total_seconds(manifest: dict) -> float:
    """Wall time of the stages in a manifest: the sum of their seconds minus what ran at the same time
    as another stage (`overlap_s`, recorded once per overlapping pair)."""
    return sum(e.get("seconds", 0) - e.get("overlap_s", 0) for e in manifest.values() if isinstance(e, dict))


def _overlap(a: tuple[float, float], spans: list[tuple[float, float]]) -> float:
    """Seconds of the interval a covered by the union of spans."""
    cut = sorted((max(a[0], s0), min(a[1], s1)) for s0, s1 in spans if min(a[1], s1) > max(a[0], s0))
    tot, end = 0.0, -float("inf")
    for s0, s1 in cut:
        s0 = max(s0, end)
        if s1 > s0:
            tot += s1 - s0
        end = max(end, s1)
    return tot


def _fmt_dt(dt: float) -> str:
    return f"{dt / 60:.1f} min" if dt >= 60 else f"{dt:.0f} s"


def run(ctx: Context, names=None, force=False, upstream=True, parallel: bool | None = None) -> list[str]:
    """Run the requested stages (default: all) that are missing or stale, plus whatever upstream is
    missing or stale. force re-runs the requested stages only, not their dependencies.
    upstream=False runs the requested stages only, on the outputs already there of their
    dependencies even when those are stale (scripts/recompute_measures.py: new measurements without
    repeating the expensive passes); the dependencies keep their own manifest entry, so a later
    normal run still re-runs them.

    parallel (default: `pipeline.parallel` in the config, on): a stage with a `resource` runs in a
    thread while another ready stage with a different resource runs too (players on the iGPU, score
    with OCR on the CPU: both only need scenes and court). Stages without a resource always run alone,
    in the calling thread, in the same order as before; with parallel off every stage does. The
    decisions (what is up to date) and the manifest stay in the calling thread; the lines of a stage
    running in a thread carry its name. If a stage fails, no other one starts, the ones running finish
    (and are recorded) and the first error is raised."""
    ctx.dir.mkdir(parents=True, exist_ok=True)
    for sub in ("manifest.json", "strokes.json"):          # etapas/ and golpes/<jugadora>/ in the library
        ctx.path(sub).parent.mkdir(parents=True, exist_ok=True)
    if parallel is None:
        parallel = parallel_enabled(ctx.cfg)
    m = load_manifest(ctx.dir)
    if _migrate(ctx, m):
        save_manifest(ctx.dir, m)
    done: list[str] = []
    requested = set(names or STAGES)
    full = order(names or list(STAGES), ctx.cfg)
    plan = [n for n in full if upstream or n in requested]
    in_plan = set(plan)
    lock = threading.Lock()
    base_log = ctx.log

    def log(msg: str):
        with lock:
            base_log(msg)

    pending = list(plan)
    running: dict[str, float] = {}               # stage → start time
    spans: list[tuple[float, float]] = []        # (start, end) of the stages finished in this run
    events: queue.Queue = queue.Queue()
    errors: list[BaseException] = []

    def check_disk():
        free = shutil.disk_usage(ctx.dir).free
        if free < MIN_FREE_BYTES:
            raise DiskFull(f"Queda muy poco espacio en el disco ({free / 1e9:.1f} GB libres en {ctx.dir.anchor or ctx.dir}). "
                           "Libera al menos 5 GB (por ejemplo, borra vídeos ya analizados) y vuelve a ejecutar: "
                           "se sigue donde se quedó.")

    def snapshot(n: str) -> dict:
        """Hashes of the JSON outputs of n's dependencies before it runs (to see which ones it rewrites)."""
        return {d: _json_outputs_hash(d, ctx) for d in STAGES[n].all_deps(ctx.cfg)}

    def finish(n: str, fp: str, summary: dict, t0: float, t1: float, before: dict | None = None):
        dt = t1 - t0
        ov = _overlap((t0, t1), spans)
        spans.append((t0, t1))
        log(f"[{ctx.match.id}] {n} terminada a las {time.strftime('%H:%M:%S')} en {_fmt_dt(dt)}"
            + (f" ({_fmt_dt(ov)} a la vez que otra etapa)" if ov >= 1 else ""))
        if (summary or {}).get("incomplete"):  # e.g. the iGPU was lost: the next run repeats it (from the caches)
            fp += "#incompleta"
            log(f"[{ctx.match.id}] {n} incompleta ({summary['incomplete']}): se repetirá en la próxima ejecución")
        m[n] = {"fingerprint": fp, "version": STAGES[n].version, "seconds": round(dt, 1),
                "finished": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": summary,
                "out_hash": output_hash(n, ctx), "scheme": SCHEME}
        after = {d: _json_outputs_hash(d, ctx) for d in (before or {})}
        m[n][REWROTE] = {d: h for d, h in after.items() if h is not None and h != before[d]}
        if ov > 0:
            m[n]["overlap_s"] = round(ov, 1)
        save_manifest(ctx.dir, m)          # after every stage, so an interruption loses little
        done.append(n)
        try:                               # its rate per minute of video on this machine (tennisbio.budget)
            from . import budget
            info = json.loads(ctx.path("probe.json").read_text(encoding="utf-8")) if ctx.path("probe.json").exists() else {}
            budget.record_stage(ctx.progress_file().parent, n, dt, (info.get("duration") or 0) / 60, ctx.match.id)
        except Exception:  # noqa: BLE001 — never breaks the run
            pass

    def worker(n: str, sub: Context):
        t0 = time.time()
        try:
            res, err = STAGES[n].run(sub) or {}, None
        except BaseException as e:          # handed to the calling thread
            res, err = None, e
        events.put((n, res, err, t0, time.time()))

    fps: dict[str, str] = {}
    befores: dict[str, dict] = {}
    while pending or running:
        started = False
        for n in list(pending) if not errors else []:
            st = STAGES[n]
            if any(d in in_plan and (d in pending or d in running) for d in st.all_deps(ctx.cfg)):
                continue                                     # a dependency is not finished yet
            fp = fingerprint(n, ctx, m)
            if not (force and n in requested) and m.get(n, {}).get("fingerprint") == fp and outputs_ok(n, ctx) \
                    and not rewrites_lost(n, ctx, m):
                pending.remove(n)
                continue
            res_n = resource(n, ctx.cfg) if parallel else None
            threaded = res_n is not None
            if running and not (threaded and all(resource(r, ctx.cfg) not in (None, res_n) for r in running)):
                continue                                     # waits for the running stages
            try:
                check_disk()
            except DiskFull as e:
                if not running:
                    raise
                errors.append(e)
                break
            pending.remove(n)
            before = snapshot(n)
            k = full.index(n) + 1
            others = f", a la vez que {', '.join(running)}" if running else ""
            log(f"[{ctx.match.id}] {n}… ({time.strftime('%Y-%m-%d %H:%M:%S')}, etapa {k} de {len(STAGES)}{others})")
            if not threaded:                                 # alone, in this thread, as always
                ctx._prog["stage"] = n
                t0 = time.time()
                summary = st.run(ctx) or {}
                finish(n, fp, summary, t0, time.time(), before)
                started = True
                break                                        # rescan: what depends on it may be ready
            fps[n] = fp
            befores[n] = before
            pre = f"[{n}] "
            sub = replace(ctx, log=lambda msg, pre=pre: log(pre + msg if not msg.startswith("  ") else "  " + pre + msg[2:]),
                          _prog={"stage": n})
            running[n] = time.time()
            threading.Thread(target=worker, args=(n, sub), name=f"etapa-{n}", daemon=True).start()
            started = True
        if started:
            continue
        if not running:
            break                                            # nothing left that can start (after an error)
        try:
            n, res, err, t0, t1 = events.get(timeout=0.5)    # a timeout keeps Ctrl+C working on Windows
        except queue.Empty:
            continue
        running.pop(n, None)
        if err is not None:
            log(f"[{ctx.match.id}] {n} falló: {type(err).__name__}: {err}")
            errors.append(err)
        else:
            finish(n, fps[n], res, t0, t1, befores.get(n))
    if errors:
        raise errors[0]
    return done


# the stages that show and measure the replays linked to her strokes (#218, 09-11) live in their own module, so that
# adding them does not change stages.py (part of the fine pass's code fingerprint); imported here, they are always
# registered with the others
from . import view_stages  # noqa: E402,F401
