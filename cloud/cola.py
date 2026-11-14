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
import json
import re
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
USD = {"prueba": 0.8, "informe": 0.15}
DEFAULT_VIDEO_MIN = 210                     # the longest of the six, when a job does not say its length
ACTIONS = ("prueba", "partido", "informe")
SOURCES = ("kaggle", "modal", "pc")
FINAL = ("hecho", "error")


def month(now: float) -> str:
    return time.strftime("%Y-%m", time.gmtime(now))


def estimate_usd(job: dict) -> float:
    """What a job may cost on Modal (an upper estimate)."""
    if job["accion"] == "partido":
        return round(USD_PER_VIDEO_MIN * float(job.get("minutos_video") or DEFAULT_VIDEO_MIN), 2)
    return USD[job["accion"]]


def run_path(job: dict) -> str:
    """Where the cloud function writes the job's estado.json on the volume (cloud/modal_app.py)."""
    a = job["accion"]
    if a == "partido":
        return f"/runs/partido_{job['partido']}/estado.json"
    if a == "prueba":
        return f"/runs/partido__prueba_{job['partido']}/estado.json"
    return f"/runs/{job.get('tag') or job['id']}/estado.json"


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


def plan(jobs: list[dict], state: dict, spend: dict, sources: dict, now: float) -> list[tuple[str, str, str]]:
    """The jobs to launch now: [(id, source, reason)]. `sources`: {name: {"ok": bool, "motivo": str}} (Kaggle and the PC
    say whether they can take work; Modal's room comes from the spend). Pending jobs in queue order; one whose «tras»
    is not done yet waits; a whole match needs `aprobado`; a launched job reserves its estimate at once, so two jobs
    never count the same dollars."""
    out, room = [], modal_room(spend, now)
    for j in jobs:
        st = state.get(j["id"], {})
        if st.get("estado") in ("en_marcha", *FINAL):
            continue
        if j.get("tras"):
            dep = state.get(j["tras"], {})
            if dep.get("estado") != "hecho":
                out.append((j["id"], "", f"espera a {j['tras']} ({dep.get('estado', 'pendiente')})"))
                continue
        if j["accion"] == "partido" and not j.get("aprobado"):
            out.append((j["id"], "", "falta la aprobación del usuario (#262)"))
            continue
        where = j.get("donde", "cualquiera")
        why = []
        for src in SOURCES:
            if where not in ("cualquiera", src):
                continue
            if src == "modal":
                need = estimate_usd(j)
                if need <= room:
                    room -= need
                    out.append((j["id"], "modal", f"estimado {need:.2f} $, quedan {room:.2f} $ este mes"))
                    break
                why.append(f"Modal: quedan {room:.2f} $ este mes y necesita {need:.2f} $")
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
    state[job["id"]] = {"estado": "en_marcha", "donde": source, "llamada": call,
                        "inicio": time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)), "ruta": run_path(job)}
    if source == "modal":
        m = spend.setdefault("modal", {}).setdefault(month(now), {"base_usd": 0.0, "trabajos": {}})
        m.setdefault("trabajos", {})[job["id"]] = {"estimado_usd": estimate_usd(job), "llamada": call}


def record_result(state: dict, spend: dict, job_id: str, result: dict, now: float):
    """A finished run (its estado.json): done or failed, and its real cost in the month it was launched."""
    st = state[job_id]
    st["estado"] = "hecho" if result.get("estado") == "hecho" else "error"
    st["fin"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(now))
    st["resultado"] = {k: result.get(k) for k in ("estado", "nota", "coste_usd", "segundos", "codigos") if k in result}
    for m in spend.get("modal", {}).values():
        r = m.get("trabajos", {}).get(job_id)
        if r is not None and result.get("coste_usd") is not None:
            r["coste_usd"] = float(result["coste_usd"])


def summary(jobs: list[dict], state: dict, spend: dict, decisions: list, now: float) -> str:
    waits = {i: why for i, src, why in decisions if not src}
    rows = ["# Cola de la nube", "", f"Última vuelta: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(now))} · "
            f"Modal: quedan {modal_room(spend, now):.2f} $ de {CREDIT_USD:.0f} $ este mes (tope de la cola {CAP_USD} $)", "",
            "| Trabajo | Acción | Partido | Estado | Dónde | Nota |", "|---|---|---|---|---|---|"]
    for j in jobs:
        st = state.get(j["id"], {})
        note = waits.get(j["id"]) or (st.get("resultado") or {}).get("nota") or ""
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


def _sources(repo: Path) -> dict:
    """Kaggle and the PC: whether each can take work now (Kaggle: not connected yet; the PC: its pause file)."""
    pause = (repo / "config" / "pausa_pc.txt")
    paused = not pause.exists() or re.search(r"^pausa:\s*si\b", pause.read_text(encoding="utf-8"), re.M) is not None
    return {"kaggle": {"ok": False, "motivo": "sin cuenta conectada todavía"},
            "pc": {"ok": False, "motivo": "en pausa (config/pausa_pc.txt)" if paused else "su cola aún no está unida a esta"}}


def main(argv: list[str] | None = None) -> int:
    import yaml

    ap = argparse.ArgumentParser(description="la cola de la nube (paso 8)")
    ap.add_argument("--cola", type=Path, default=Path("config/cola_nube.yaml"))
    ap.add_argument("--logs", type=Path, required=True, help="la rama nube-logs, ya descargada")
    ap.add_argument("--en-seco", action="store_true", help="decide y escribe el estado sin lanzar ni consultar nada")
    a = ap.parse_args(argv)
    now = time.time()
    queue = yaml.safe_load(a.cola.read_text(encoding="utf-8")) or {}
    jobs = queue.get("trabajos") or []
    d = a.logs / "cola"
    d.mkdir(parents=True, exist_ok=True)
    state, spend = _load(d / "estado.json", {}), _load(d / "gasto.json", {})
    set_base(spend, queue.get("gasto_modal_base") or {})
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
        for jid, st in state.items():                    # 1. running jobs: finished?
            if st.get("estado") != "en_marcha" or st.get("donde") != "modal":
                continue
            try:
                res = json.loads(b"".join(vol.read_file(st["ruta"].lstrip("/"))).decode("utf-8"))
            except Exception as e:                       # not written yet: still starting
                print(f"{jid}: sin estado todavía ({type(e).__name__})")
                continue
            if res.get("estado") in FINAL:
                record_result(state, spend, jid, res, now)
                print(f"{jid}: {res.get('estado')} ({res.get('coste_usd')} $)")
    decisions = plan(jobs, state, spend, _sources(Path.cwd()), now)
    launched = 0
    for jid, src, why in decisions:
        print(f"{jid}: {'→ ' + src if src else 'espera'} · {why}")
        if not src or a.en_seco:
            continue
        j = by_id[jid]
        if src != "modal":                               # Kaggle and the PC take work once connected (paso 8b/8c)
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
    (d / "estado.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "gasto.json").write_text(json.dumps(spend, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "estado.md").write_text(summary(jobs, state, spend, decisions, now), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
