"""The single worker and the control of the queue (10-11, phase B of docs/orquestador.md).

One worker per PC (an exclusive lock in the data folder) runs every job of the queue (the application's database:
tables `jobs` and `events`), each in a child process of its own, so that a job can be stopped at once (its whole
process tree is killed; the stages resume from their caches) and nothing heavy ever runs twice at the same time.
The window and the PC's cycle (and so Claude, through the cycle's requests) only *ask*: they submit jobs and set
controls; the worker obeys them:

- pause:  no new job starts; with «now» the running one is stopped and goes back to the queue (resumes from caches);
- resume: the queue goes on;
- cancel: a pending job is cancelled; a running one is stopped and cancelled.

Job kinds: the application's («partido», «rival», «informe»: tennisbio.app.jobs.run_one, with its retries) and
«comando»: any `tennisbio …` command line (args, a JSON list), e.g. ["run", "--all"] or ["report", "--stroke",
"forehand"], so that the cycle's actions run through the same queue. Every change is an event; `status` is what
both entry points show (the window's «Cola», estado_trabajos.json in pc-logs)."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

HEARTBEAT_S = 15.0            # the worker says it is alive this often
ALIVE_S = 90.0                # a worker silent longer than this is dead (its lock is gone with its process anyway)
POLL_S = 2.0                  # how often the worker looks at the controls while a job runs
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job INTEGER, at TEXT, kind TEXT, text TEXT);
"""


# --- the database ------------------------------------------------------------------------------------------------
def open_db(cfg: dict):
    from .app.db import DB, Paths
    db = DB(Paths.from_config(cfg).db)
    ensure_schema(db)
    return db


def ensure_schema(db) -> None:
    db.con.executescript(EXTRA_SCHEMA)
    cols = {r[1] for r in db.con.execute("PRAGMA table_info(jobs)")}
    for name, decl in (("args", "TEXT DEFAULT ''"), ("control", "TEXT DEFAULT ''"), ("log", "TEXT DEFAULT ''"),
                       ("source", "TEXT DEFAULT ''"), ("paso", "INTEGER DEFAULT 0"), ("pasos", "INTEGER DEFAULT 0")):
        if name not in cols:
            try:
                db.con.execute(f"ALTER TABLE jobs ADD COLUMN {name} {decl}")
            except sqlite3.OperationalError as e:      # 11-11: another process (the window, the worker) added it first
                if "duplicate column" not in str(e).lower():
                    raise
    db.con.commit()


def event(db, job: int | None, kind: str, text: str = "") -> None:
    from .app.db import now
    db.x("INSERT INTO events (job, at, kind, text) VALUES (?, ?, ?, ?)", job, now(), kind, text[:2000])


# --- the lock: one worker per PC -----------------------------------------------------------------------------------
class WorkerLock:
    """An exclusive lock on a file, released by the OS when the process ends (crash included)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.f = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            self.f = None
            return False
        self.f.seek(0)
        self.f.truncate()
        self.f.write(str(os.getpid()))
        self.f.flush()
        return True

    def release(self) -> None:
        if self.f is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.f.close()
        self.f = None


def lock_path(cfg: dict) -> Path:
    from .app.db import Paths
    return Paths.from_config(cfg).data / "ejecutor.lock"


# --- asking (the window, the cycle, Claude) ------------------------------------------------------------------------
def submit(db, kind: str, args: list[str] | None = None, source: str = "", reason: str = "", priority: int | None = None,
           **fields) -> int:
    """A new job; «comando» carries its `tennisbio` arguments. Returns its id."""
    from .app import jobs
    from .app.db import now
    if kind in ("comando", "flujo"):   # two commands are two jobs (enqueue merges jobs of the same kind and match)
        if kind == "flujo":
            fl = flows()
            if not args or args[0] not in fl:
                raise ValueError(f"flujo desconocido: {args[0] if args else '(ninguno)'}; hay {', '.join(sorted(fl))}")
            reason = reason or f"flujo «{args[0]}»: {fl[args[0]].get('descripcion', '')}"
            n = len(fl[args[0]].get("pasos") or [])
        else:
            n = 0
        jid = db.x("INSERT INTO jobs (kind, reason, priority, state, created, light, estimate_s, args, source, paso, pasos) "
                   "VALUES (?, ?, ?, 'pendiente', ?, 0, 0, ?, ?, 0, ?)", kind, reason or " ".join(args or []),
                   5 if priority is None else int(priority), now(), json.dumps(args or []), source, n)
        event(db, jid, "enviado", f"{'flujo' if kind == 'flujo' else 'tennisbio'} {' '.join(args or [])} ({source or 'sin origen'})")
        return jid
    jid = jobs.enqueue(db, kind, reason=reason, **fields)
    db.x("UPDATE jobs SET args=?, source=? WHERE id=?", json.dumps(args or []), source, jid)
    if priority is not None:
        db.x("UPDATE jobs SET priority=? WHERE id=?", int(priority), jid)
    event(db, jid, "enviado", f"{kind} {' '.join(args or [])} ({source or 'sin origen'})")
    return jid


def pause(db, now_: bool = False, source: str = "") -> str:
    db.set_setting("pausa", True)
    event(db, None, "pausa", f"{'ya' if now_ else 'al terminar el trabajo en curso'} ({source})")
    if now_:
        for j in db.q("SELECT id FROM jobs WHERE state='en curso'"):
            db.x("UPDATE jobs SET control='pausar' WHERE id=?", j["id"])
    return "cola en pausa" + (": el trabajo en curso se para y vuelve a la cola" if now_ else "")


def restart(db, source: str = "") -> str:
    """The worker ends between two jobs (never in the middle of one) and the cycle starts it again with the new code."""
    db.set_setting("reiniciar_ejecutor", True)
    event(db, None, "reiniciar", source)
    return "el ejecutor se reinicia al acabar el trabajo en curso"


def resume(db, source: str = "") -> str:
    db.set_setting("pausa", False)
    event(db, None, "reanudar", source)
    return "cola en marcha"


def cancel(db, job_id: int | None = None, all_: bool = False, source: str = "") -> int:
    """Cancels pending jobs at once and asks the worker to stop running ones. Returns how many."""
    n = 0
    rows = db.q("SELECT id, state FROM jobs WHERE state IN ('pendiente', 'en curso', 'esperando espacio', 'por confirmar')"
                + ("" if all_ else " AND id=?"), *(() if all_ else (int(job_id),)))
    for j in rows:
        if j["state"] == "en curso":
            db.x("UPDATE jobs SET control='cancelar' WHERE id=?", j["id"])
        else:
            db.x("UPDATE jobs SET state='cancelado', message=? WHERE id=?", f"cancelado ({source})", j["id"])
        event(db, j["id"], "cancelar", source)
        n += 1
    return n


# --- the worker ------------------------------------------------------------------------------------------------------
def _kill_tree(p: subprocess.Popen) -> None:
    if p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, timeout=60)
    else:
        import signal
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
    try:
        p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass


def _spawn(job_id: int, log: Path, extra_env: dict | None = None) -> subprocess.Popen:
    log.parent.mkdir(parents=True, exist_ok=True)
    out = open(log, "a", encoding="utf-8")
    out.write(f"== {time.strftime('%Y-%m-%d %H:%M:%S')} trabajo {job_id}\n")
    out.flush()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **(extra_env or {})}
    kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)} \
        if os.name == "nt" else {"start_new_session": True}
    return subprocess.Popen([sys.executable, "-m", "tennisbio.cli", "jobs", "run-one", str(job_id)],
                            stdout=out, stderr=subprocess.STDOUT, env=env, **kw)


def worker_log(cfg: dict | None = None) -> Path:
    """12-12: the worker's own log (datos/trabajos/ejecutor.log): its successor's output and any error of its loop. On
    12-12 a worker started by its predecessor (output thrown away) died at 11:00 without a trace."""
    from .app.db import Paths
    from .config import load_config
    p = Paths.from_config(cfg if cfg is not None else load_config()).data / "trabajos" / "ejecutor.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _log(cfg: dict | None, msg: str) -> None:
    try:
        with open(worker_log(cfg), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid {os.getpid()} {msg}\n")
    except OSError:
        pass


MAX_LOOP_ERRORS = 10        # consecutive errors of the worker's loop (a locked database...) before it gives up


def _start_successor() -> subprocess.Popen:
    """11-11 (R7 of the review of the Base): a worker that ends for new code starts the next one itself, detached, once
    its lock is released (a fresh interpreter: it imports the new code). Before, it waited for the cycle to start it:
    a cycle from GitHub Actions never does, and on 11-11 the queue had no worker for 18 min (20:54-21:13)."""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
          | getattr(subprocess, "DETACHED_PROCESS", 0)} if os.name == "nt" else {"start_new_session": True}
    out = open(worker_log(), "a", encoding="utf-8")
    return subprocess.Popen([sys.executable, "-m", "tennisbio.cli", "worker"], stdin=subprocess.DEVNULL,
                            stdout=out, stderr=subprocess.STDOUT, env=env, **kw)


def serve(cfg: dict, once: bool = False, idle_s: float = 10.0, stop=lambda: False, status_file: Path | None = None,
          successor=_start_successor) -> int:
    """The worker's loop. Returns 0, or 3 when another worker already runs on this PC (nothing done)."""
    from .app import jobs
    from .app.db import Paths, now
    lock = WorkerLock(lock_path(cfg))
    if not lock.acquire():
        print("ya hay un ejecutor en marcha en este PC: no se arranca otro")
        return 3
    db = open_db(cfg)
    paths = Paths.from_config(cfg)
    renew = False
    try:
        jobs.recover(db)
        event(db, None, "ejecutor", f"arranca (pid {os.getpid()})")
        last_beat = 0.0
        errors = 0
        while not stop():
            try:
                done = _serve_step(db, paths, jobs, now, once, idle_s, stop, status_file, last_beat)
                errors = 0
            except Exception as e:  # noqa: BLE001 — 12-12: an error of the loop (a locked database...) is logged, not fatal
                errors += 1
                import traceback
                _log(cfg, f"error del bucle ({errors}/{MAX_LOOP_ERRORS}): {e}\n{traceback.format_exc()}")
                if errors >= MAX_LOOP_ERRORS:
                    raise
                time.sleep(min(30.0, 2.0 * errors))
                continue
            last_beat = done.get("beat", last_beat)
            if done.get("renew"):
                renew = not once
                break
            if done.get("stop"):
                break
    finally:
        try:
            event(db, None, "ejecutor", "termina")
            db.set_setting("ejecutor", {"pid": None, "at": time.time()})
            write_status(db, status_file)
        except Exception as e:  # noqa: BLE001 — the lock is released and the successor started all the same
            _log(cfg, f"no pudo apuntar su final: {e}")
        lock.release()                     # first: the successor takes the lock (it stops if another worker holds it)
        if renew:
            try:
                p = successor()
                event(db, None, "ejecutor", f"arranca el siguiente con el código nuevo (pid {getattr(p, 'pid', '?')})")
            except Exception as e:  # noqa: BLE001 — the cycle starts one if this failed
                _log(cfg, f"no pudo arrancar el siguiente: {e}")
        db.close()
    return 0


def _beat(db, status_file) -> float:
    db.set_setting("ejecutor", {"pid": os.getpid(), "at": time.time()})
    write_status(db, status_file)
    return time.time()


def _serve_step(db, paths, jobs, now, once: bool, idle_s: float, stop, status_file, last_beat: float) -> dict:
    """One turn of the worker's loop: its heartbeat, a restart asked for, or the next job run to its end. Returns
    {"beat": time of the last heartbeat, "renew": True to restart with new code, "stop": True to end (once)}."""
    out: dict = {"beat": last_beat}
    if time.time() - last_beat > HEARTBEAT_S:
        out["beat"] = _beat(db, status_file)
    if db.setting("reiniciar_ejecutor", False):       # new code arrived: exit between jobs, the next one starts with it
        db.set_setting("reiniciar_ejecutor", False)
        event(db, None, "ejecutor", "se reinicia con el código nuevo")
        out["renew"] = True
        return out
    job = jobs.next_job(db)
    if job is None:
        if once:
            out["stop"] = True
        else:
            time.sleep(idle_s)
        return out
    log = paths.data / "trabajos" / f"trabajo_{job['id']}.log"
    db.x("UPDATE jobs SET state='en curso', started=?, log=?, control='' WHERE id=?", now(), str(log), job["id"])
    event(db, job["id"], "empieza", job.get("reason") or job["kind"])
    write_status(db, status_file)
    p = _spawn(job["id"], log)
    db.x("UPDATE jobs SET pid=? WHERE id=?", p.pid, job["id"])
    stopped = ""
    while p.poll() is None:
        time.sleep(POLL_S)
        try:
            if time.time() - out["beat"] > HEARTBEAT_S:
                out["beat"] = _beat(db, status_file)
            ctl = (db.one("SELECT control FROM jobs WHERE id=?", job["id"]) or {}).get("control") or ""
        except Exception as e:  # noqa: BLE001 — 12-12: a locked database while the job runs never kills the worker
            _log(None, f"latido o control del trabajo {job['id']} no leído: {e}")
            continue
        if ctl in ("cancelar", "pausar") or stop():
            stopped = ctl or "pausar"
            _kill_tree(p)
    row = db.one("SELECT state FROM jobs WHERE id=?", job["id"]) or {}
    if stopped == "cancelar":
        db.x("UPDATE jobs SET state='cancelado', pid=NULL, control='', finished=?, message='cancelado' WHERE id=?",
             now(), job["id"])
        event(db, job["id"], "cancelado")
    elif stopped:
        db.x("UPDATE jobs SET state='pendiente', pid=NULL, control='', message='parado: sigue donde se quedó' "
             "WHERE id=?", job["id"])
        event(db, job["id"], "parado", "vuelve a la cola; reanuda desde las cachés")
    elif row.get("state") == "en curso":           # the child died without saying how it ended
        db.x("UPDATE jobs SET state='error', pid=NULL, finished=?, message=? WHERE id=?", now(),
             f"el proceso terminó con código {p.returncode} sin acabar (ver {log.name})", job["id"])
        event(db, job["id"], "error", f"código {p.returncode}")
    else:
        event(db, job["id"], row.get("state") or "terminado", f"código {p.returncode}")
    write_status(db, status_file)
    return out


# TENNISBIO_FLUJOS: another flows file (the tests; the worker's job children inherit it)
FLOWS_FILE = Path(os.environ.get("TENNISBIO_FLUJOS") or Path(__file__).resolve().parents[2] / "config" / "flujos.yaml")


def flows(path: Path | None = None) -> dict:
    """The flows of config/flujos.yaml: name → {descripcion, pasos: [{nombre, tennisbio | script, si_falla, limite_min}]}."""
    import yaml
    f = Path(path) if path else FLOWS_FILE
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


def _step_argv(step: dict, out: Path) -> list[str]:
    sub = lambda a: str(a).replace("{salida}", str(out))
    if step.get("tennisbio"):
        return [sys.executable, "-m", "tennisbio.cli", *[sub(a) for a in step["tennisbio"]]]
    if step.get("script"):
        sc = [sub(a) for a in step["script"]]
        return [sys.executable, str(Path(__file__).resolve().parents[2] / sc[0]), *sc[1:]]
    raise ValueError(f"paso sin «tennisbio» ni «script»: {step}")


def run_flow(db, job: dict, cfg: dict) -> int:
    """A «flujo» job: its steps in order from the one it reached (a paused or cut flow goes on where it was; each step
    is idempotent). Each step is a process of its own with an optional time limit; its output goes to the job's log."""
    from .app import jobs
    name = (json.loads(job.get("args") or "[]") or [""])[0]
    fl = flows().get(name)
    t0 = time.time()
    if fl is None:
        jobs._finish(db, job, "error", f"flujo desconocido: {name}", t0)
        return 1
    steps = fl.get("pasos") or []
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    start = int(job.get("paso") or 0)
    failed = []
    for i in range(start, len(steps)):
        st = steps[i]
        db.x("UPDATE jobs SET paso=?, pasos=?, message=? WHERE id=?", i, len(steps), f"paso {i + 1}/{len(steps)}: {st.get('nombre', '')}",
             job["id"])
        event(db, job["id"], "paso", f"{i + 1}/{len(steps)} {st.get('nombre', '')}")
        print(f"== paso {i + 1}/{len(steps)}: {st.get('nombre', '')} ({time.strftime('%Y-%m-%d %H:%M:%S')})", flush=True)
        lim = float(st.get("limite_min") or 0) * 60 or None
        ok = True
        try:
            r = subprocess.run(_step_argv(st, out), timeout=lim, env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
            ok = r.returncode == 0
            why = f"código {r.returncode}"
        except subprocess.TimeoutExpired:
            ok, why = False, f"más de {st.get('limite_min')} min"
        except Exception as e:  # noqa: BLE001 — said in the job
            ok, why = False, f"{type(e).__name__}: {e}"
        if not ok:
            event(db, job["id"], "paso fallido", f"{i + 1} {st.get('nombre', '')}: {why}")
            failed.append(f"{st.get('nombre', '')} ({why})")
            if (st.get("si_falla") or "parar") != "seguir":
                db.x("UPDATE jobs SET paso=? WHERE id=?", i, job["id"])
                jobs._finish(db, job, "error", f"paso {i + 1}/{len(steps)} {st.get('nombre', '')}: {why}", t0)
                return 1
        db.x("UPDATE jobs SET paso=? WHERE id=?", i + 1, job["id"])
    jobs._finish(db, job, "hecho", f"{len(steps)} pasos" + (f"; con fallos que no paran: {'; '.join(failed)}" if failed else ""), t0)
    return 0


def run_command(db, job: dict) -> int:
    """A «comando» job: `tennisbio <args>` in this process; its end said in the job."""
    from .app import jobs
    from .cli import main as cli_main
    args = json.loads(job.get("args") or "[]")
    t0 = time.time()
    try:
        rc = cli_main(args)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:  # noqa: BLE001 — said in the job, the queue goes on
        import traceback
        traceback.print_exc()
        jobs._finish(db, job, "error", f"{type(e).__name__}: {str(e)[:300]}", t0)
        return 1
    jobs._finish(db, job, "hecho" if not rc else "error", "" if not rc else f"código {rc}", t0)
    return 0 if not rc else 1


def run_one(cfg: dict, job_id: int) -> int:
    """In the child: one job, with the application's runner (its retries and notices) or a `tennisbio` command."""
    from .app import jobs
    from .app.db import now
    db = open_db(cfg)
    try:
        job = db.one("SELECT * FROM jobs WHERE id=?", int(job_id))
        if job is None:
            print(f"no existe el trabajo {job_id}")
            return 2
        if job["kind"] == "comando":
            return run_command(db, job)
        if job["kind"] == "flujo":
            return run_flow(db, job, cfg)
        from .app.core import App
        app = App(cfg)
        try:
            state = jobs.run_one(app.db, app.paths, app.engine, cfg, {**job, "state": "en curso", "started": now()})
        finally:
            app.close()
        return 0 if state in ("hecho", "pendiente", "aviso", "esperando espacio") else 1
    finally:
        db.close()


# --- what both entry points show ----------------------------------------------------------------------------------
def status(db, events: int = 30, output: Path | None = None) -> dict:
    w = db.setting("ejecutor", None) or {}
    alive = bool(w.get("pid")) and time.time() - float(w.get("at") or 0) < ALIVE_S
    rows = db.q("SELECT id, kind, match, player, stroke, reason, state, message, created, started, finished, args, "
                "source, log, paso, pasos FROM jobs ORDER BY id DESC LIMIT 60")
    running = [r for r in rows if r["state"] == "en curso"]
    prog = None
    pf = Path(output) / "progreso.json" if output else None
    if pf is not None and pf.exists():
        try:
            prog = json.loads(pf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prog = None
    import hashlib
    firma = hashlib.sha1(json.dumps([alive, bool(db.setting("pausa", False)),
                                     [(r["id"], r["state"], r.get("message")) for r in rows]], default=str).encode()).hexdigest()[:12]
    return {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "firma": firma,
            "ejecutor": {"vivo": alive, **w}, "pausa": bool(db.setting("pausa", False)),
            "en_curso": running, "progreso": prog,
            "pendientes": [r for r in rows if r["state"] in ("pendiente", "esperando espacio", "por confirmar")],
            "recientes": [r for r in rows if r["state"] not in ("pendiente", "en curso", "esperando espacio", "por confirmar")][:15],
            "eventos": db.q("SELECT * FROM events ORDER BY id DESC LIMIT ?", int(events))}


def write_status(db, f: Path | None) -> None:
    """estado_trabajos.json next to the outputs (uploaded to pc-logs): the progress file is in the same folder."""
    if f is None:
        return
    try:
        from .pipeline import write_atomic
        Path(f).parent.mkdir(parents=True, exist_ok=True)
        write_atomic(Path(f), json.dumps(status(db, output=Path(f).parent), ensure_ascii=False, indent=1, default=str))
    except OSError:
        pass
