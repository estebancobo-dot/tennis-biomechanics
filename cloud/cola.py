"""Paso 8 (14-11, #281-#283): the cloud's job queue, run by GitHub Actions every 30 minutes without any chat session.

`config/cola_nube.yaml` (main branch) lists the jobs. The branch `nube-logs` keeps their state (`cola/estado.json`),
the spend (`cola/gasto.json`) and a readable summary (`cola/estado.md`). Each pass:
  1. looks at the jobs that are running and records the finished ones (their estado.json on the Modal volume);
  2. launches the pending jobs whose turn has come on the first free source with room for them: Kaggle (its weekly GPU
     hours) → Modal (its monthly credit, never past CAP_USD) → the PC (when it is on). A job with no room waits for the
     next pass with the reason written; it never stops the queue.
A whole match only runs with `aprobado: true` (#262: the user approves every full analysis). Nothing here deletes
anything. The pure part (what to do) is tested without Modal (tests/test_cola.py); `main` does it.

    python cloud/cola.py --cola config/cola_nube.yaml --logs <nube-logs checkout> [--en-seco]
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

APP = "tennisbio"
VOLUME = "tennisbio-datos"
# Modal: 30 $ of credit a month and the account's limit at 30 $ (the hard stop); the queue stops launching before it
CREDIT_USD = 30.0
CAP_USD = 29.5
# cost estimates (14-11, measured: Osaka 3.8 $ for ~70 min of video, Pegula 7.3 $ / 112 min, Zheng 6.9 $ / 117 min;
# a 10-minute test 0.40-0.60 $; the report 0.03-0.08 $), with margin; the real Usage page was 4 % above our sums
USD_PER_VIDEO_MIN = 0.065
USD = {"prueba": 0.8, "informe": 0.15, "medir": 0.5}
DEFAULT_VIDEO_MIN = 210                     # the longest of the six, when a job does not say its length
ACTIONS = ("prueba", "partido", "informe", "medir", "comparar")
KAGGLE_SESSIONS = 2            # T20 (14-11): Kaggle runs 2 batch GPU sessions at once; one notebook per job
# Kaggle (paso 8b): ~30 GPU hours a week (the figure floats; the account shows it); the queue keeps 2 h of margin. One
# notebook, so one Kaggle job at a time. Hours per job until measured: a test 1 h, a match 3 × its video.
KAGGLE_CAP_H = 28.0
KAGGLE_H = {"prueba": 1.0, "medir": 0.5}
KAGGLE_H_PER_VIDEO_MIN = 3.0 / 60
# 14-11: a session that ends without its job done is launched again, up to KAGGLE_TRIES times; then the job is an error
# with the reason. Queued in Kaggle (its free GPUs busy) it waits: relaunching every 10 minutes (13:48-14:32) sent it to
# the back of Kaggle's queue each time and gave the job up after 4 tries; only after 45 minutes queued is it relaunched.
# 14-11 20:55 (R46): the probe was refused with «Maximum batch GPU session count of 2 reached» while both our jobs
# were «queued»: Kaggle had accepted them (they hold our 2 sessions) and was waiting for free T4s. Relaunching after
# 45 minutes only put them at the back again: now 3 h (a session never started by then is taken as lost)
KAGGLE_QUEUE_MAX_S = 3 * 3600
KAGGLE_TRIES = 4
SOURCES = ("kaggle", "modal", "pc")
FINAL = ("hecho", "error")
# 14-11 (R40: Gauff's test ran «well» with 0 scoreboard readings): a test with a C0 or C1 fault is not passed: «revisar»,
# and the match after it does not start until it is looked at
SERIOUS = ("C0", "C1")


def month(now: float) -> str:
    return time.strftime("%Y-%m", time.gmtime(now))


def estimate_usd(job: dict) -> float:
    """What a job may cost on Modal (an upper estimate)."""
    if job["accion"] == "partido":
        return round(USD_PER_VIDEO_MIN * float(job.get("minutos_video") or DEFAULT_VIDEO_MIN), 2)
    return USD[job["accion"]]


def week(now: float) -> str:
    return time.strftime("%G-W%V", time.gmtime(now))


def estimate_h(job: dict) -> float:
    """Kaggle GPU hours a job may take (an upper estimate until measured)."""
    if job["accion"] == "partido":
        return round(KAGGLE_H_PER_VIDEO_MIN * float(job.get("minutos_video") or DEFAULT_VIDEO_MIN), 2)
    return KAGGLE_H.get(job["accion"], 1.0)


def kaggle_room(spend: dict, now: float) -> float:
    """Kaggle GPU hours left this week (real hours of the finished jobs, estimates of the running ones)."""
    w = spend.get("kaggle", {}).get(week(now), {})
    used = sum(float(r.get("horas", r.get("estimado_h", 0.0))) for r in w.get("trabajos", {}).values())
    return round(KAGGLE_CAP_H - used, 2)


def fresh(result: dict | None, st: dict) -> bool:
    """The estado.json read belongs to this launch (14-11: a match brought up to date has an old «hecho» from its first
    analysis in the same folder; read before the new session writes its own, the job would look finished)."""
    if not result:
        return False
    try:
        started = calendar.timegm(time.strptime(str(result.get("inicio")), "%Y-%m-%d %H:%M:%S"))
    except (TypeError, ValueError):
        return True
    return started >= float(st.get("lanzado_ts", 0.0)) - 300


def kaggle_step(st: dict, kstatus: str, result: dict | None, now: float) -> tuple[str, str]:
    """What to do with a running Kaggle job: («recoger» | «relanzar» | «error» | «nada», reason). Its estado.json on
    Modal decides when it is final; else Kaggle's own status: queued too long, ended with an error, or ended (12 h at
    most) without the job done → launched again (it goes on from what it saved), up to KAGGLE_TRIES."""
    if result and result.get("estado") in FINAL:
        return "recoger", ""
    if kstatus == "queued" and now - float(st.get("lanzado_ts", now)) > KAGGLE_QUEUE_MAX_S:
        why = f"en cola de Kaggle más de {KAGGLE_QUEUE_MAX_S // 60} min sin arrancar"
    elif kstatus == "desconocido" and now - float(st.get("lanzado_ts", now)) > 600:
        # 14-11: a launch Kaggle refused (or a notebook it does not know) left the job «running» with nothing behind it
        why = "Kaggle no tiene ninguna sesión de este trabajo"
    elif kstatus in ("error", "cancelacknowledged"):
        why = f"la sesión de Kaggle acabó con «{kstatus}» sin escribir su estado"
    elif kstatus == "complete":
        why = "la sesión de Kaggle acabó sin terminar el trabajo (dura 12 h como mucho): sigue desde lo guardado"
    else:
        return "nada", ""
    tries = int(st.get("intentos", 1))
    return ("relanzar", why) if tries < KAGGLE_TRIES else ("error", f"{why} ({tries} intentos)")


def run_path(job: dict, source: str = "modal") -> str:
    """Where the job's estado.json goes on the volume (cloud/modal_app.py; a Kaggle test keeps its own folder, so it
    never writes over a test made by Modal: cloud/kaggle/correr.py with --salida-remota)."""
    a = job["accion"]
    if (source == "kaggle" and a == "prueba") or a == "medir":
        return f"/runs/kaggle_{job['id']}/estado.json"
    if a == "partido":
        return f"/runs/partido_{job['partido']}/estado.json"
    if a == "prueba":
        return f"/runs/partido__prueba_{job['partido']}/estado.json"
    return f"/runs/{job.get('tag') or job['id']}/estado.json"


TEST_PREFIX = "_prueba_"           # cloud/nube.py TEST_PREFIX (tests/test_cola.py keeps them equal)


def output_root(job: dict, source: str) -> str:
    """The volume folder that holds the job's match folder. 14-11 (T9): every Kaggle test its own
    (/kaggle_pruebas/<id>/output), so a test with new code never writes over the one it is compared with; before,
    all of them shared /kaggle_pruebas/output."""
    if job["accion"] == "prueba" and source == "kaggle":
        return f"/kaggle_pruebas/{job['id']}/output"
    return "/output"


def output_of(job: dict, source: str) -> str:
    """The job's match folder on the volume (its manifest.json and strokes files)."""
    mid = (TEST_PREFIX if job["accion"] == "prueba" else "") + str(job.get("partido", ""))
    return f"{output_root(job, source)}/{mid}"


def check_queue(jobs: list[dict]) -> list[str]:
    """What is wrong in the queue file (a wrong job is never launched; the others go on)."""
    bad, ids = [], set()
    for j in jobs:
        jid = j.get("id")
        if not jid or not re.fullmatch(r"[A-Za-z0-9_.-]+", str(jid)):
            bad.append(f"trabajo sin id válido: {j}")
            continue
        if jid in ids:
            bad.append(f"{jid}: id repetido")
        ids.add(jid)
        if j.get("accion") not in ACTIONS:
            bad.append(f"{jid}: acción {j.get('accion')!r} (vale {', '.join(ACTIONS)})")
        if j.get("accion") in ("prueba", "partido") and not j.get("partido"):
            bad.append(f"{jid}: falta el partido")
        if j.get("accion") == "medir" and not j.get("prueba"):
            bad.append(f"{jid}: falta la prueba de concepto («prueba»)")
        if "config" in j and (not isinstance(j["config"], dict) or j.get("accion") != "prueba"):
            bad.append(f"{jid}: «config» es un diccionario de ajustes y solo vale para una prueba")
        if j.get("accion") == "comparar" and not (j.get("a") and j.get("b")):
            bad.append(f"{jid}: comparar necesita «a» y «b» (dos trabajos de la cola o dos carpetas del volumen)")
        if j.get("donde", "cualquiera") not in ("cualquiera", *SOURCES):
            bad.append(f"{jid}: donde {j.get('donde')!r}")
    for j in jobs:
        if j.get("tras") and j["tras"] not in ids:
            bad.append(f"{j.get('id')}: «tras» {j['tras']} no está en la cola")
    return bad


def modal_room(spend: dict, now: float) -> float:
    """Dollars Modal can still take this month: the cap minus what the month already used (the Usage page figure the
    user gave, `base_usd`, plus every job the queue launched since, at its real cost when known, else its estimate)."""
    m = spend.get("modal", {}).get(month(now), {})
    used = float(m.get("base_usd", 0.0)) + sum(float(r.get("coste_usd", r.get("estimado_usd", 0.0)))
                                               for r in m.get("trabajos", {}).values())
    return round(CAP_USD - used, 2)


def set_base(spend: dict, base: dict):
    """What each month used in Modal before this queue's jobs (the Usage page figure, config/cola_nube.yaml)."""
    for m, usd in base.items():
        spend.setdefault("modal", {}).setdefault(str(m), {"trabajos": {}})["base_usd"] = float(usd)


def note_start(st: dict, kstatus: str, now: float) -> None:
    """R46 (14-11, the user: «¿cuándo hay máquinas?»): when Kaggle first runs the session, and how long it waited in
    Kaggle's queue, to learn its free hours from data (cola/estado.json: «arranco», «espera_min»)."""
    if kstatus == "running" and not st.get("arranco"):
        st["arranco"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(now))
        st["espera_min"] = round((now - float(st.get("lanzado_ts", now))) / 60)


def cancel(state: dict, tokens: list[str], reasons: dict, delete) -> list[str]:
    """Jobs cancelled by the configuration (`cancelar: {id: motivo}`): a running Kaggle job's notebook is deleted (its
    session frees one of our 2), and the job ends as «error» with the reason; a job never launched just ends."""
    done = []
    for jid in tokens:
        st = state.get(jid) or {}
        if st.get("estado") in ("hecho", "error"):
            continue
        if st.get("estado") == "en_marcha" and st.get("donde") == "kaggle":
            delete(st.get("cuaderno") or notebook_slug(jid))
        state[jid] = {**st, "estado": "error", "resultado": {"nota": f"cancelado: {reasons.get(jid, '')}"}}
        done.append(jid)
    return done


def restart(state: dict, spend: dict, tokens: list[str], done: list[str]) -> list[str]:
    """Jobs to start again (config `reiniciar: ["<id>#<n>", ...]`), once per token: its state (not a finished «hecho») and its
    reservation of Kaggle hours are dropped, so the queue plans it again. Returns the tokens applied now."""
    applied = []
    for tok in tokens or []:
        jid = str(tok).split("#")[0]
        if tok in done or state.get(jid, {}).get("estado") == "hecho":
            continue
        state.pop(jid, None)
        for w in spend.get("kaggle", {}).values():
            w.get("trabajos", {}).pop(jid, None)
        applied.append(tok)
    return applied


def plan(jobs: list[dict], state: dict, spend: dict, sources: dict, now: float,
         hold_matches: str = "") -> list[tuple[str, str, str]]:
    """The jobs to launch now: [(id, source, reason)]. `sources`: {name: {"ok": bool, "motivo": str}} (Kaggle and the PC
    say whether they can take work; Modal's room comes from the spend). Pending jobs in queue order; one whose «tras»
    is not done yet waits; a whole match needs `aprobado`; a launched job reserves its estimate at once, so two jobs
    never count the same dollars."""
    out, room, kroom = [], modal_room(spend, now), kaggle_room(spend, now)
    kaggle = dict(sources.get("kaggle", {}))
    for j in jobs:
        st = state.get(j["id"], {})
        if st.get("estado") in ("en_marcha", "revisar", *FINAL):
            continue
        if j.get("tras"):
            dep = state.get(j["tras"], {})
            if dep.get("estado") != "hecho":
                out.append((j["id"], "", f"espera a {j['tras']} ({dep.get('estado', 'pendiente')})"))
                continue
        if j["accion"] == "comparar":                  # T9: no GPU, run by the queue itself in this pass
            waits = [x for x in (j.get("a"), j.get("b")) if not str(x).startswith("/")
                     and state.get(str(x), {}).get("estado") != "hecho"]
            out.append((j["id"], "", f"espera a {', '.join(waits)}") if waits else (j["id"], "github", "se compara en esta vuelta"))
            continue
        if j["accion"] == "partido" and not j.get("aprobado"):
            out.append((j["id"], "", "falta la aprobación del usuario (#262)"))
            continue
        if j["accion"] == "partido" and hold_matches:
            out.append((j["id"], "", hold_matches))
            continue
        where = j.get("donde", "cualquiera")
        why = []
        for src in SOURCES:
            if where not in ("cualquiera", src):
                continue
            if src == "modal" and (j["accion"] == "medir" or j.get("config")):
                why.append("Modal: las pruebas de concepto van en Kaggle por ahora")
                continue
            if src == "modal":
                need = estimate_usd(j)
                if need <= room:
                    room -= need
                    out.append((j["id"], "modal", f"estimado {need:.2f} $, quedan {room:.2f} $ este mes"))
                    break
                why.append(f"Modal: quedan {room:.2f} $ este mes y necesita {need:.2f} $")
            elif src == "kaggle":
                need = estimate_h(j)
                if j["accion"] == "informe":
                    why.append("kaggle: el informe va en Modal")
                elif not kaggle.get("ok"):
                    why.append(f"kaggle: {kaggle.get('motivo', 'no disponible')}")
                elif need > kroom:
                    why.append(f"kaggle: quedan {kroom:.1f} h esta semana y necesita {need:.1f} h")
                else:
                    kroom -= need
                    free = int(kaggle.get("libres", 1)) - 1                       # T20: its 2 sessions at once
                    kaggle = {**kaggle, "libres": free} if free > 0 else \
                        {"ok": False, "motivo": f"sus {KAGGLE_SESSIONS} sesiones ocupadas (la última, {j['id']})"}
                    out.append((j["id"], "kaggle", f"previstas {need:.1f} h, quedan {kroom:.1f} h esta semana"))
                    break
            else:
                s = sources.get(src, {})
                if s.get("ok"):
                    out.append((j["id"], src, s.get("motivo", "")))
                    break
                why.append(f"{src}: {s.get('motivo', 'no disponible')}")
        else:
            out.append((j["id"], "", "sin capacidad: " + "; ".join(why)))
    return out


def record_launch(state: dict, spend: dict, job: dict, source: str, call: str, now: float):
    tries = int(state.get(job["id"], {}).get("intentos", 0)) + 1 if state.get(job["id"], {}).get("estado") == "en_marcha" else 1
    state[job["id"]] = {"estado": "en_marcha", "donde": source, "llamada": call, "intentos": tries, "lanzado_ts": now,
                        "accion": job["accion"], "partido": job.get("partido", ""),
                        "inicio": time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)),
                        "ruta": run_path(job, source)}
    if job.get("partido"):                        # T9: where its outputs are, for «comparar»
        state[job["id"]]["salida"] = output_of(job, source)
    if source == "kaggle":
        w = spend.setdefault("kaggle", {}).setdefault(week(now), {"trabajos": {}})
        w.setdefault("trabajos", {}).setdefault(job["id"], {"estimado_h": estimate_h(job)})
    if source == "modal":
        m = spend.setdefault("modal", {}).setdefault(month(now), {"base_usd": 0.0, "trabajos": {}})
        m.setdefault("trabajos", {})[job["id"]] = {"estimado_usd": estimate_usd(job), "llamada": call}


def record_result(state: dict, spend: dict, job_id: str, result: dict, now: float):
    """A finished run (its estado.json): done or failed, and its real cost in the month it was launched."""
    st = state[job_id]
    st["estado"] = "hecho" if result.get("estado") == "hecho" else "error"
    serious = [f"{stage}: {code} ({(v or {}).get('nivel')})" for stage, fs in (result.get("fallos") or {}).items()
               for code, v in (fs or {}).items() if (v or {}).get("nivel") in SERIOUS]
    if st["estado"] == "hecho" and st.get("accion") == "prueba" and serious:
        st["estado"] = "revisar"
        result = {**result, "nota": "prueba con fallos graves: " + "; ".join(serious)}
    st["fin"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(now))
    st["resultado"] = {k: result.get(k) for k in ("estado", "nota", "coste_usd", "segundos", "codigos", "horas_kaggle")
                       if k in result}
    for m in spend.get("modal", {}).values():
        r = m.get("trabajos", {}).get(job_id)
        if r is not None and result.get("coste_usd") is not None and st.get("donde") != "kaggle":
            r["coste_usd"] = float(result["coste_usd"])
    for w in spend.get("kaggle", {}).values():
        r = w.get("trabajos", {}).get(job_id)
        if r is not None and result.get("horas_kaggle") is not None:
            r["horas"] = float(result["horas_kaggle"])


def summary(jobs: list[dict], state: dict, spend: dict, decisions: list, now: float) -> str:
    waits = {i: why for i, src, why in decisions if not src}
    rows = ["# Cola de la nube", "", f"Última vuelta: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(now))} · "
            f"Modal: quedan {modal_room(spend, now):.2f} $ de {CREDIT_USD:.0f} $ este mes (tope de la cola {CAP_USD} $) · "
            f"Kaggle: quedan {kaggle_room(spend, now):.1f} h de GPU esta semana (tope {KAGGLE_CAP_H:.0f} h)", "",
            "| Trabajo | Acción | Partido | Estado | Dónde | Nota |", "|---|---|---|---|---|---|"]
    for j in jobs:
        st = state.get(j["id"], {})
        note = waits.get(j["id"]) or (st.get("resultado") or {}).get("nota") or ""
        if not st.get("estado") and st.get("aviso"):
            note = f"{st['aviso']} ({note})" if note else st["aviso"]
        if st.get("estado") == "en_marcha" and st.get("kaggle"):
            note = f"Kaggle: {st['kaggle']}, intento {st.get('intentos', 1)}" + (f"; {st['nota']}" if st.get("nota") else "")
        if st.get("estado") == "en_marcha" and st.get("progreso"):
            note = f"{note} · {st['progreso']}" if note else st["progreso"]
        rows.append(f"| {j['id']} | {j['accion']} | {j.get('partido', '')} | {st.get('estado', 'pendiente')} | "
                    f"{st.get('donde', '')} | {note} |")
    return "\n".join(rows) + "\n"


def _read(vol, path: str) -> bytes:
    return b"".join(vol.read_file(path.lstrip("/")))


def matches_on_volume(vol) -> list[dict]:
    """The PC's list of matches as uploaded to the volume (pc/registro_partidos.json): id, opponent, and whether the
    cloud analysed it (its manifest has the fine pass); what the queue's «partido» must name."""
    try:
        registry = json.loads(_read(vol, "pc/registro_partidos.json").decode("utf-8"))
    except Exception as e:                                       # the list is not there: say it, check nothing
        print(f"sin la lista de partidos del PC en el volumen ({type(e).__name__})")
        return []
    out = []
    for m in registry:
        try:
            done = "fine" in json.loads(_read(vol, f"output/{m['id']}/manifest.json").decode("utf-8"))
        except Exception:
            done = False
        out.append({"id": str(m["id"]), "rival": str(m.get("rival") or ""), "analizado": done})
    return out


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _sources(repo: Path, queue: dict | None = None, state: dict | None = None) -> dict:
    """Kaggle and the PC: whether each can take work now. Kaggle: its keys in the environment, switched on in the queue
    (`kaggle_activo`, after its 10-minute test gave the same as Modal's) and a free session of its KAGGLE_SESSIONS;
    the PC: never (#284)."""
    queue, state = queue or {}, state or {}
    busy = [i for i, st in state.items() if st.get("estado") == "en_marcha" and st.get("donde") == "kaggle"]
    if not (os.environ.get("KAGGLE_API_TOKEN") and os.environ.get("KAGGLE_USERNAME")):
        k = {"ok": False, "motivo": "sin sus claves en GitHub"}
    elif not queue.get("kaggle_activo"):
        k = {"ok": False, "motivo": "aún no activado en la cola (antes, su prueba de 10 min frente a la de Modal)"}
    elif len(busy) >= KAGGLE_SESSIONS:
        k = {"ok": False, "motivo": f"ocupado con {', '.join(busy)}"}
    else:
        k = {"ok": True, "motivo": "", "libres": KAGGLE_SESSIONS - len(busy)}
    return {"kaggle": k, "pc": {"ok": False, "motivo": "no se usa (decisión del usuario, 14-11, #284)"}}


def _kaggle(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "cloud/kaggle/cuaderno.py", *args], capture_output=True, text=True)


LAST_REFUSAL = {"text": ""}


def kaggle_launch(job: dict, slug: str | None = None) -> bool:
    """The Modal key into the private dataset, then the notebook with this job (cloud/kaggle/cuaderno.py). A test keeps
    its results apart (/kaggle_pruebas), never over a test made by Modal."""
    extra = (["--salida-remota", run_path(job, "kaggle").rsplit("/", 1)[0], "--output-remoto", output_root(job, "kaggle")]
             if job["accion"] == "prueba" else
             ["--salida-remota", run_path(job, "kaggle").rsplit("/", 1)[0], "--prueba", job.get("prueba", "")]
             if job["accion"] == "medir" else [])
    if job.get("config"):                            # T5: a test of other settings (proof of concept on the whole clip)
        extra += ["--config", json.dumps(job["config"], ensure_ascii=False)]
    for args in (["clave"], ["lanzar", "--accion", job["accion"], "--partido", job.get("partido", ""),
                             "--commit", os.environ.get("GITHUB_SHA", ""), "--slug", slug or notebook_slug(job["id"]), *extra]):
        r = _kaggle(args)
        print(r.stdout[-1500:], r.stderr[-1500:])
        refused = push_refused(r.stdout + r.stderr)
        if r.returncode or refused:
            LAST_REFUSAL["text"] = refused or f"falló «{args[0]}» (código {r.returncode})"
            return False
    return True


def push_refused(text: str) -> str:
    """Kaggle's refusal of a push, which its CLI prints with exit code 0 (14-11: «Kernel push error: Maximum batch GPU
    session count of 2 reached.» was taken for a launch for two hours)."""
    m = re.search(r"(Kernel push error:[^\n]*|push error[^\n]*|Maximum batch GPU session count[^\n]*)", text, re.I)
    return m.group(1).strip() if m else ""


def notebook_slug(job_id: str, attempt: int = 1) -> str:
    """The job's own Kaggle notebook (cloud/kaggle/cuaderno.slug_for). R45 (14-11): a relaunch after a stuck queue
    gets a new notebook (`-2`, `-3`, …): the racket's proof of concept stayed «queued» for 3 relaunches under the same
    name while other jobs started at once (behind the deleted notebook's session, most likely)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "kaggle"))
    import cuaderno

    return cuaderno.slug_for(job_id if attempt <= 1 else f"{job_id}-{attempt}")


def kaggle_status(job_id: str, slug: str | None = None) -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "kaggle"))
    import cuaderno

    r = _kaggle(["estado", "--slug", slug or notebook_slug(job_id)])
    return cuaderno.status_of(r.stdout + r.stderr)


def main(argv: list[str] | None = None) -> int:
    import yaml

    ap = argparse.ArgumentParser(description="la cola de la nube (paso 8)")
    ap.add_argument("--cola", type=Path, default=Path("config/cola_nube.yaml"))
    ap.add_argument("--logs", type=Path, required=True, help="la rama nube-logs, ya descargada")
    ap.add_argument("--en-seco", action="store_true", help="decide y escribe el estado sin lanzar ni consultar nada")
    ap.add_argument("--avisos", type=Path, help="#291: aquí, lo que necesita a Claude (el flujo lo comenta en el PR buzón)")
    a = ap.parse_args(argv)
    now = time.time()
    queue = yaml.safe_load(a.cola.read_text(encoding="utf-8")) or {}
    jobs = queue.get("trabajos") or []
    d = a.logs / "cola"
    d.mkdir(parents=True, exist_ok=True)
    state, spend = _load(d / "estado.json", {}), _load(d / "gasto.json", {})
    before = json.loads(json.dumps(state))             # #291: what changed in this pass wakes Claude (avisos)
    set_base(spend, queue.get("gasto_modal_base") or {})
    done_f = d / "reinicios.json"
    done = _load(done_f, [])
    cancels = queue.get("cancelar") or {}
    for jid in cancel(state, list(cancels), cancels,
                      (lambda slug: print("cola: borrar", slug, _kaggle(["borrar", "--slug", slug]).returncode))
                      if not a.en_seco else (lambda slug: None)):
        print(f"cola: {jid} cancelado ({cancels[jid]})")
    for tok in restart(state, spend, queue.get("reiniciar") or [], done):
        print(f"cola: {tok.split('#')[0]} empieza de nuevo ({tok})")
        done.append(tok)
    done_f.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    bad = check_queue(jobs)
    for b in bad:
        print("cola:", b)
    bad_ids = {b.split(":")[0] for b in bad}
    jobs = [j for j in jobs if j.get("id") and j["id"] not in bad_ids]
    by_id = {j["id"]: j for j in jobs}
    if not a.en_seco:
        import modal

        vol = modal.Volume.from_name(VOLUME)
        catalog = matches_on_volume(vol)                 # the matches the cloud knows, and which are analysed
        (d / "partidos.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
        known = {m["id"] for m in catalog}
        for j in jobs:                                   # a match the cloud does not know is never launched
            if j.get("partido") and known and j["partido"] not in known and state.get(j["id"], {}).get("estado") is None:
                state[j["id"]] = {"estado": "error", "resultado": {"nota": f"{j['partido']} no está en los partidos de la nube"}}
        for jid, st in list(state.items()):              # 1. running jobs: finished, stuck, or going on?
            if st.get("estado") != "en_marcha" or st.get("donde") not in ("modal", "kaggle"):
                continue
            try:
                res = json.loads(b"".join(vol.read_file(st["ruta"].lstrip("/"))).decode("utf-8"))
            except Exception as e:                       # not written yet: still starting
                print(f"{jid}: sin estado todavía ({type(e).__name__})")
                res = None
            if res is not None and not fresh(res, st):      # an older run's estado.json in the same folder
                print(f"{jid}: el estado que hay es de antes de este lanzamiento")
                res = None
            if res and res.get("progreso"):                 # 14-11: where it is now (stage and %), for the summary
                now_used = f"; {res['recursos_ahora']}" if res.get("recursos_ahora") else ""
                st["progreso"] = f"{res['progreso']} ({res.get('actualizado', '')}{now_used})"
            if st["donde"] == "kaggle" and jid in by_id:
                kst = kaggle_status(jid, st.get("cuaderno"))
                st["kaggle"] = f"{kst} ({time.strftime('%H:%M', time.gmtime(now))})"
                note_start(st, kst, now)
                print(f"{jid}: Kaggle dice «{kst}»; lanzado hace {(now - float(st.get('lanzado_ts', now))) / 60:.0f} min, "
                      f"intento {st.get('intentos', 1)}")
                act, why = kaggle_step(st, kst, res, now)
                if act == "relanzar":
                    print(f"{jid}: {why}: se lanza otra vez")
                    if kst == "queued":                  # #290: its stuck notebook is deleted first (frees its session)
                        r = _kaggle(["borrar", "--slug", st.get("cuaderno") or notebook_slug(jid)])
                        print(f"{jid}: cuaderno atascado borrado ({r.returncode}) {r.stdout[-300:]} {r.stderr[-300:]}")
                    new_slug = notebook_slug(jid, int(st.get("intentos", 1)) + 1)       # R45: a new notebook
                    if kaggle_launch(by_id[jid], new_slug):
                        record_launch(state, spend, by_id[jid], "kaggle", "kaggle", now)
                        state[jid]["cuaderno"] = new_slug
                        state[jid]["nota"] = why
                    continue
                if act == "error":
                    record_result(state, spend, jid, {"estado": "error", "nota": why}, now)
                    continue
            if res and res.get("estado") in FINAL:
                record_result(state, spend, jid, res, now)
                print(f"{jid}: {res.get('estado')} ({res.get('coste_usd')} $, {res.get('horas_kaggle')} h de Kaggle)")
    if not a.en_seco:
        copy_poc_results(vol, state, d)
    decisions = plan(jobs, state, spend, _sources(Path.cwd(), queue, state), now, str(queue.get("partidos_en_espera") or ""))
    launched = 0
    for jid, src, why in decisions:
        print(f"{jid}: {'→ ' + src if src else 'espera'} · {why}")
        if not src or a.en_seco:
            continue
        j = by_id[jid]
        if src == "github":                              # T9: a comparison, here and now (no GPU)
            compare_job(vol, j, state, d, now)
            continue
        if src == "kaggle":
            if kaggle_launch(j):
                record_launch(state, spend, j, "kaggle", "kaggle", now)
                state[jid]["cuaderno"] = notebook_slug(jid)
            else:                                        # said in the summary, launched again next pass
                state.setdefault(jid, {})["aviso"] = f"Kaggle no lo aceptó: {LAST_REFUSAL['text']}"
            continue
        if src != "modal":
            continue
        import modal

        if launched == 0:
            import subprocess
            subprocess.run(["modal", "deploy", "cloud/modal_app.py"], check=True)
        if j["accion"] == "informe":
            call = modal.Function.from_name(APP, "informe").spawn(tag=j.get("tag") or j["id"])
        else:
            call = modal.Function.from_name(APP, j["accion"]).spawn(j["partido"])
        record_launch(state, spend, j, "modal", call.object_id, now)
        launched += 1
    for jid, st in state.items():                         # T3: each job's match, for the audit's «Cola de la nube»
        if jid in by_id and isinstance(st, dict):
            st.setdefault("partido", by_id[jid].get("partido", ""))
    (d / "estado.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "gasto.json").write_text(json.dumps(spend, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "estado.md").write_text(summary(jobs, state, spend, decisions, now), encoding="utf-8")
    (d / "vuelta.json").write_text(json.dumps({"ts": now, "hora": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now)),
                                               "trabajos": len(jobs)}, ensure_ascii=False), encoding="utf-8")
    if not a.en_seco:
        upload_state(vol, d)
    if a.avisos:
        msg = wake_message(events(before, state), now)
        a.avisos.write_text(msg, encoding="utf-8")
        print(f"cola: {'avisos para Claude' if msg else 'nada que avisar'}")
    return 0


WAKE_STATES = ("hecho", "error", "revisar")


def events(before: dict, after: dict) -> list[str]:
    """#291 (the user: wake Claude at once, no polling, no tokens while nothing happens): what in this pass needs
    Claude — a job that has just finished, failed or stopped in «revisar», and a launch Kaggle refused (new reason)."""
    out = []
    for jid, st in after.items():
        if not isinstance(st, dict):
            continue
        old = before.get(jid) or {}
        if st.get("estado") in WAKE_STATES and st.get("estado") != old.get("estado"):
            note = (st.get("resultado") or {}).get("nota") or ""
            out.append(f"`{jid}` → **{st['estado']}**" + (f": {note[:300]}" if note else ""))
        elif st.get("aviso") and st.get("aviso") != old.get("aviso"):
            out.append(f"`{jid}` → aviso: {st['aviso'][:300]}")
    return out


def wake_message(lines: list[str], now: float) -> str:
    """The comment on the mailbox pull request ('' when nothing needs Claude: then nothing is posted)."""
    if not lines:
        return ""
    when = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now))
    return (f"Cola de la nube, {when}: {len(lines)} cambio(s) que necesitan a Claude\n\n" + "\n".join(f"- {x}" for x in lines)
            + "\n\nEstado completo: rama `nube-logs`, `cola/estado.md`.\n")


QUEUE_FILES = ("estado.json", "gasto.json", "vuelta.json", "estado.md")


def copy_poc_results(vol, state: dict, logs: Path) -> list[str]:
    """14-11: every finished proof of concept's measurement («poc» of its estado.json on the volume) also in nube-logs
    (cola/pruebas/<id>.json), and every finished test's and match's time and resources by stage
    (cola/ejecuciones/<id>.json), where Claude reads them without Modal's keys; once per job, the finished ones too."""
    out = []
    for jid, st in state.items():
        if not isinstance(st, dict) or st.get("accion") not in ("medir", "prueba", "partido") \
                or st.get("estado") not in (*FINAL, "revisar") or not st.get("ruta"):
            continue
        f = logs / ("pruebas" if st["accion"] == "medir" else "ejecuciones") / f"{jid}.json"
        if f.exists():
            continue
        res = _read_json(vol, st["ruta"])
        if res is None:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        keep = (("estado", "poc", "kaggle", "horas_kaggle", "nota") if st["accion"] == "medir" else
                # phase A (#287): where each second and each resource went, for every test and match
                ("estado", "segundos", "horas_kaggle", "coste_usd", "gpu", "etapas", "recursos", "recursos_por_etapa",
                 "modelos_en_cpu", "fallos", "sin_subir", "config", "kaggle", "nota"))
        f.write_text(json.dumps({k: res.get(k) for k in keep}, ensure_ascii=False, indent=1), encoding="utf-8")
        out.append(jid)
    return out
SAME = ("idéntica", "equivalente")


READ_ERRORS: dict = {}


def _read_json(vol, path: str):
    """A JSON file of the volume (the storage port's Modal adapter, cloud/almacen.py); None, with why in READ_ERRORS,
    when it is not there or is not JSON."""
    import almacen

    st = almacen.ModalStorage(vol, VOLUME)
    data = st.read_json(path)
    if data is None:
        READ_ERRORS[path] = getattr(st, "last_error", "no es JSON")
    return data


def compare_job(vol, job: dict, state: dict, logs: Path, now: float) -> dict:
    """T9 (#288, #289): job «comparar» — two runs of the same clip (`a`, `b`: queue jobs, by the folder recorded at
    their launch, or volume folders) compared with tennisbio.infra.equivalence; «hecho» when identical or equivalent,
    «revisar» otherwise (Claude looks at what differs: nothing that depends on it goes on). The whole comparison
    goes to nube-logs (cola/comparaciones/<id>.json)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from tennisbio.infra.equivalence import STROKE_FILES, compare, summary as eq_summary

    def folder(x):
        return str(x) if str(x).startswith("/") else (state.get(str(x)) or {}).get("salida")
    fa, fb = folder(job["a"]), folder(job["b"])
    st = {"estado": "error", "accion": "comparar", "donde": "github", "fin": time.strftime("%Y-%m-%d %H:%M", time.gmtime(now))}
    if not fa or not fb:
        st["resultado"] = {"nota": f"no se sabe dónde están las salidas de {job['a'] if not fa else job['b']}"}
    else:
        ma, mb = _read_json(vol, f"{fa}/manifest.json"), _read_json(vol, f"{fb}/manifest.json")
        if ma is None or mb is None:
            st["resultado"] = {"nota": f"sin manifest.json en {fa if ma is None else fb}"}
        else:
            sa = {f: v for f in STROKE_FILES if (v := _read_json(vol, f"{fa}/{f}")) is not None}
            sb = {f: v for f in STROKE_FILES if (v := _read_json(vol, f"{fb}/{f}")) is not None}
            res = compare(ma, mb, sa, sb)
            (logs / "comparaciones").mkdir(parents=True, exist_ok=True)
            unread = {p: e for p, e in READ_ERRORS.items() if p.startswith((fa, fb))}
            (logs / "comparaciones" / f"{job['id']}.json").write_text(
                json.dumps({"a": fa, "b": fb, **res, "no_leidos": unread}, ensure_ascii=False, indent=1), encoding="utf-8")
            st["estado"] = "hecho" if res["veredicto"] in SAME else "revisar"
            st["resultado"] = {"estado": st["estado"], "veredicto": res["veredicto"], "nota": eq_summary(res)[:600]}
    state[job["id"]] = st
    print(f"{job['id']}: {st['estado']} · {st['resultado'].get('nota', '')}")
    return st


def upload_state(vol, d: Path) -> bool:
    """T3: the queue's state also on the volume (/cola/), where the cloud's audit reads it («Cola de la nube», B7/B8)."""
    import almacen

    files = [d / f for f in QUEUE_FILES if (d / f).exists()]
    files += sorted((d / "comparaciones").glob("*.json"))              # T3: «Equivalencia entre infraestructuras»
    try:
        almacen.ModalStorage(vol, VOLUME).put_files(files, d, "/cola")
        return True
    except Exception as e:  # noqa: BLE001 — the next pass uploads it again; nube-logs has it meanwhile
        print(f"cola: estado al volumen ({type(e).__name__}: {e})")
        return False


if __name__ == "__main__":
    raise SystemExit(main())
