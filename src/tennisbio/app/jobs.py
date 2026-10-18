"""The queue and the runner (docs/aplicacion_local.md §4 «Cola», §5 every case, §6 «Monitorizar»).

Three kinds of job:
- partido: the stages of a match for its main player (cheap pass, identity, fine pass). Heavy (iGPU).
- rival:   the fine pass of the other player of an analysed match (reuses the cheap pass). Heavy.
- informe: one analysis (player × stroke): new version, audit, comparison (quality.publish). Light.

The work itself is done by an engine (engine.Engine on the PC; a fake one in the tests): the runner only
decides what runs, in which order, and what to do when something goes wrong:
- iGPU (DirectML) error: retried twice, then on the CPU (slower, same validated result);
- out of memory: retried without the parallel helpers (same result, less memory), then error;
- disk full half-way: the regenerable files are freed and the job retried; else it waits for space;
- video gone, damaged or without what is needed: «con aviso», in Spanish, no useless retries;
- any other exception: «error» with a diagnostic file; the other jobs go on; «lo arregla una actualización».
An interrupted job (PC switched off, suspended, closed) is found «en curso» with a dead process at the next
start and goes back to the queue: the stages resume from their caches."""
import os
import time
import traceback
from pathlib import Path

from ..pipeline import DiskFull, MissingVideo
from . import quality, storage
from .db import DB, Paths, now

HEAVY = {"partido", "rival"}
PRIORITY = {"informe": 3, "partido": 5, "rival": 6}
ACTIVE = ("pendiente", "en curso", "esperando espacio", "por confirmar")
GPU_RETRIES = 2               # on the iGPU before falling back to the CPU
MEMORY_RETRIES = 1
DISK_RETRIES = 1
DEFAULT_S = {"partido": 4.5 * 3600, "rival": 3 * 3600, "informe": 600}
CONFIRM_ABOVE_S = 6 * 3600    # a plan longer than this waits for one click

GPU_MARKERS = ("dmlexecutionprovider", "directml", "d3d12", "dxgi", "887a0005", "887a0006", "dml ")
MEMORY_MARKERS = ("bad allocation", "out of memory", "unable to allocate", "not enough memory", "arraymemoryerror",
                  "std::bad_alloc")
VIDEO_MARKERS = ("moov atom not found", "invalid data found", "no se puede leer", "videoerror", "no tiene vídeo")


class VideoProblem(RuntimeError):
    """The video cannot give what the stage needs (damaged, no audio track, no court): a notice, not an error."""


def enqueue(db: DB, kind: str, match: str | None = None, player: str | None = None, stroke: str | None = None,
            reason: str = "", priority: int | None = None, estimate_s: float = 0.0, confirm: bool = False) -> int:
    """A job, once: the same work already waiting gets the new reason added instead of a second job."""
    same = db.one("SELECT id, reason FROM jobs WHERE kind=? AND IFNULL(match,'')=IFNULL(?,'') AND IFNULL(player,'')=IFNULL(?,'') "
                  "AND IFNULL(stroke,'')=IFNULL(?,'') AND state IN ('pendiente', 'esperando espacio', 'por confirmar')",
                  kind, match, player, stroke)
    if same:
        if reason and reason not in (same["reason"] or ""):
            db.x("UPDATE jobs SET reason=? WHERE id=?", f"{same['reason']}; {reason}" if same["reason"] else reason, same["id"])
        return same["id"]
    return db.x("INSERT INTO jobs (kind, match, player, stroke, reason, priority, state, created, light, estimate_s) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", kind, match, player, stroke, reason,
                PRIORITY.get(kind, 5) if priority is None else priority, "por confirmar" if confirm else "pendiente",
                now(), int(kind not in HEAVY), estimate_s or DEFAULT_S.get(kind, 0))


def _alive(pid) -> bool:
    if not pid:
        return False
    if pid == os.getpid():
        return True
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))    # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return code.value == 259                                             # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, AttributeError):
        return False


def recover(db: DB) -> int:
    """Jobs left «en curso» by a process that no longer exists (PC off or suspended, window closed) go back
    to the queue; their stages resume from what they saved."""
    n = 0
    for j in db.q("SELECT id, pid FROM jobs WHERE state='en curso'"):
        if not _alive(j["pid"]) or j["pid"] == os.getpid():
            db.x("UPDATE jobs SET state='pendiente', pid=NULL, message='reanudado tras un corte' WHERE id=?", j["id"])
            n += 1
    return n


def in_window(db: DB, t: time.struct_time | None = None) -> bool:
    """The optional time band for heavy jobs (e.g. only at night): setting «franja» = ["22:00", "08:00"]."""
    band = db.setting("franja")
    if not band:
        return True
    t = t or time.localtime()
    cur = t.tm_hour * 60 + t.tm_min
    a, b = (int(x.split(":")[0]) * 60 + int(x.split(":")[1]) for x in band)
    return a <= cur < b if a <= b else cur >= a or cur < b


def next_job(db: DB, t: time.struct_time | None = None) -> dict | None:
    heavy_ok = in_window(db, t) and not db.setting("pausa", False)
    for j in db.q("SELECT * FROM jobs WHERE state='pendiente' ORDER BY priority, id"):
        if j["kind"] in HEAVY and not heavy_ok:
            continue
        if j["kind"] not in HEAVY and db.setting("pausa", False):
            continue
        return j
    return None


def _text(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}".lower()


def is_gpu_error(e: BaseException) -> bool:
    t = _text(e)
    return any(m in t for m in GPU_MARKERS)


def is_memory_error(e: BaseException) -> bool:
    return isinstance(e, MemoryError) or any(m in _text(e) for m in MEMORY_MARKERS)


def is_video_problem(e: BaseException) -> bool:
    return isinstance(e, VideoProblem) or type(e).__name__ == "VideoError" or any(m in _text(e) for m in VIDEO_MARKERS)


def job_config(cfg: dict, job: dict) -> dict:
    """The configuration a job runs with: the CPU after the iGPU failed (device), and without the parallel
    helpers after a memory error (light: the same result with less memory at once)."""
    c = dict(cfg)
    if job.get("device"):
        c["device"] = job["device"]
    if job.get("light") and job["kind"] in HEAVY:
        c["pipeline"] = {**(c.get("pipeline") or {}), "parallel": False}
        c["fine_pass"] = {**(c.get("fine_pass") or {}), "ball_ahead": False, "pose_prefetch": False}
    return c


def _finish(db: DB, job: dict, state: str, message: str = "", t0: float | None = None, diag: str = ""):
    db.x("UPDATE jobs SET state=?, message=?, finished=?, pid=NULL, diag=? WHERE id=?", state, message, now(), diag, job["id"])
    if t0 is not None:
        db.x("INSERT INTO runs (job, kind, target, seconds, result, detail, finished) VALUES (?, ?, ?, ?, ?, ?, ?)",
             job["id"], job["kind"], job.get("match") or f"{job.get('player')}_{job.get('stroke')}", round(time.time() - t0, 1),
             state, message[:500], now())


def _retry(db: DB, job: dict, message: str, **set_):
    cols = ", ".join(f"{k}=?" for k in set_)
    db.x(f"UPDATE jobs SET state='pendiente', pid=NULL, attempts=attempts+1, message=?{', ' + cols if cols else ''} WHERE id=?",
         message, *set_.values(), job["id"])


def _diagnostic(paths: Paths, job: dict, err: BaseException) -> Path:
    paths.diag.mkdir(parents=True, exist_ok=True)
    f = paths.diag / f"trabajo-{job['id']}-{time.strftime('%Y%m%d-%H%M%S')}.txt"
    f.write_text(f"trabajo: {job}\nhora: {now()}\n\n" + "".join(traceback.format_exception(type(err), err, err.__traceback__)),
                 encoding="utf-8")
    return f


def _what(db: DB, job: dict) -> str:
    if job["kind"] == "informe":
        return quality.label(db, job["player"], job["stroke"])
    return f"{job['match']}" + (f" ({job['player']})" if job.get("player") else "")


def after_match(db: DB, engine, job: dict):
    """A match finished: its state from what the stages found, and the analyses it feeds go to the queue."""
    from .index import state_from_manifest
    state, note = state_from_manifest(engine.manifest(job["match"]))
    db.x("UPDATE matches SET state=?, note=? WHERE id=?", state, note, job["match"])
    if state in ("excluido", "sin la jugadora"):
        return
    pid = job["player"]
    strokes = {r["stroke"] for r in db.q("SELECT stroke FROM analyses WHERE player=?", pid)} or {"forehand"}
    for st in sorted(strokes):
        enqueue(db, "informe", player=pid, stroke=st, reason=f"partido {job['match']} analizado")


def run_one(db: DB, paths: Paths, engine, cfg: dict, job: dict) -> str:
    """Runs one job and returns its final state ('hecho', 'pendiente' when retried, 'aviso', 'error',
    'esperando espacio')."""
    if job["kind"] in HEAVY:
        size = engine.video_size(job["match"])
        ok, why = storage.can_start_match(paths.output, size) if size else (True, "")
        if not ok:
            db.x("UPDATE jobs SET state='esperando espacio', message=? WHERE id=?", why, job["id"])
            db.notice("disk_wait", "aviso", f"{_what(db, job)}: {why}")
            return "esperando espacio"
    db.x("UPDATE jobs SET state='en curso', started=?, pid=?, message='' WHERE id=?", now(), os.getpid(), job["id"])
    t0 = time.time()
    c = job_config(cfg, job)
    try:
        if job["kind"] == "partido":
            engine.run_match(job["match"], job["player"], c)
            after_match(db, engine, job)
        elif job["kind"] == "rival":
            engine.run_opponent(job["match"], job["player"], c)
            enqueue(db, "informe", player=job["player"], stroke=job.get("stroke") or "forehand",
                    reason=f"sus golpes de {job['match']}")
        elif job["kind"] == "informe":
            info = quality.publish(db, paths.analyses, job["player"], job["stroke"],
                                   lambda dest: engine.build_report(job["player"], job["stroke"], dest, c),
                                   lambda rep, dest: engine.audit(job["player"], job["stroke"], rep, dest, c))
            _finish(db, job, "hecho", f"{info['verdict']} · versión {info['version']} · {info['state']}", t0)
            return "hecho"
        else:
            raise ValueError(f"tipo de trabajo desconocido: {job['kind']}")
        _finish(db, job, "hecho", "", t0)
        db.clear_notice("disk_wait")
        return "hecho"
    except KeyboardInterrupt:
        db.x("UPDATE jobs SET state='pendiente', pid=NULL, message='interrumpido: sigue donde se quedó' WHERE id=?", job["id"])
        raise
    except MissingVideo:
        if job.get("match"):
            db.x("UPDATE matches SET state='con aviso', note=? WHERE id=?",
                 "El vídeo ya no está: se conservan sus resultados; para recalcularlo hace falta el vídeo.", job["match"])
        _finish(db, job, "aviso", "el vídeo ya no está; se conservan sus resultados", t0)
        return "aviso"
    except DiskFull as e:
        freed = storage.free_regenerable(paths.output)
        if job["attempts"] < DISK_RETRIES and freed > 1e9:
            _retry(db, job, f"disco lleno: liberados {storage._gb(freed)} GB regenerables; se reanuda")
            return "pendiente"
        db.x("UPDATE jobs SET state='esperando espacio', pid=NULL, message=? WHERE id=?", str(e), job["id"])
        db.notice("disk_wait", "aviso", f"{_what(db, job)}: {e}")
        return "esperando espacio"
    except Exception as e:                       # noqa: BLE001 — every error has its answer and the queue goes on
        if is_gpu_error(e) and job.get("device") != "cpu":
            n = job["attempts"] + 1
            if n >= GPU_RETRIES:
                _retry(db, job, "la iGPU falló dos veces: sigue en la CPU (más lento, mismo resultado)", device="cpu")
                db.notice(f"gpu_{job['id']}", "info", f"{_what(db, job)}: la iGPU falló; sigue en la CPU, más lento.")
            else:
                _retry(db, job, f"fallo de la iGPU ({str(e)[:120]}): reintento")
            return "pendiente"
        if is_memory_error(e) and job["attempts"] < MEMORY_RETRIES and not job.get("light"):
            _retry(db, job, "falta de memoria: reintento con menos trabajo a la vez", light=1)
            return "pendiente"
        if is_video_problem(e):
            msg = f"El vídeo no da lo que hace falta: {str(e)[:200]}"
            if job.get("match"):
                db.x("UPDATE matches SET state='con aviso', note=? WHERE id=?", msg, job["match"])
            _finish(db, job, "aviso", msg, t0)
            return "aviso"
        f = _diagnostic(paths, job, e)
        _finish(db, job, "error", f"{type(e).__name__}: {str(e)[:300]}", t0, str(f))
        db.notice(f"error_{job['id']}", "crit", f"{_what(db, job)}: error del programa ({type(e).__name__}). "
                  f"Guardado el diagnóstico ({f.name}). Los demás trabajos siguen; lo arregla una actualización.")
        return "error"


def wake_waiting(db: DB, paths: Paths, engine) -> int:
    """Jobs waiting for disk space go back to the queue as soon as their match fits."""
    n = 0
    for j in db.q("SELECT * FROM jobs WHERE state='esperando espacio'"):
        size = engine.video_size(j["match"]) if j.get("match") else 0
        if not size or storage.can_start_match(paths.output, size)[0]:
            db.x("UPDATE jobs SET state='pendiente', message='ya hay espacio' WHERE id=?", j["id"])
            n += 1
    if n and not db.q("SELECT id FROM jobs WHERE state='esperando espacio'"):
        db.clear_notice("disk_wait")
    return n


def work(db: DB, paths: Paths, engine, cfg: dict, once: bool = False, max_jobs: int | None = None,
         idle_s: float = 60.0, stop=lambda: False) -> list[tuple[int, str]]:
    """The queue's loop: resumes what was cut, guards the disk, runs the next job; with once=True it stops
    when nothing can run now. Returns (job id, final state) of what ran."""
    recover(db)
    done = []
    while not stop() and (max_jobs is None or len(done) < max_jobs):
        storage.guard(db, paths.output)
        wake_waiting(db, paths, engine)
        job = next_job(db)
        if job is None:
            if once:
                break
            time.sleep(idle_s)
            continue
        done.append((job["id"], run_one(db, paths, engine, cfg, job)))
    return done


def eta(db: DB) -> dict:
    """Estimated seconds of what is waiting, with the times measured on this PC when there are any."""
    rate = {r["kind"]: r["s"] for r in db.q("SELECT kind, AVG(seconds) AS s FROM runs WHERE result='hecho' GROUP BY kind")}
    left = 0.0
    for j in db.q("SELECT kind, estimate_s FROM jobs WHERE state IN ('pendiente', 'en curso', 'esperando espacio')"):
        left += rate.get(j["kind"]) or j["estimate_s"] or DEFAULT_S.get(j["kind"], 0)
    return {"seconds": left, "ends": time.strftime("%H:%M", time.localtime(time.time() + left)) if left else ""}


def fmt_duration(s: float) -> str:
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"
