"""Paso 8b (14-11, #283, #285): what runs inside a Kaggle session (the «tennisbio-cola» notebook pushed by
cloud/kaggle/cuaderno.py). The same code and models as Modal: Python 3.11 with the repository's locked dependencies, ONNX
Runtime for CUDA and the same GPU hook (cloud/arranque/nube_gpu.py), `tennisbio run --match`. Modal's volume stays
the only store: the session takes its match from it and puts what it makes back, as it goes (a session cut at 12 h is
followed by the next one from there).

    python cloud/kaggle/correr.py '{"accion": "comprobar"}'
    python cloud/kaggle/correr.py '{"accion": "prueba", "partido": "<id>", "salida": "/runs/<tag>",
                                    "output_remoto": "/output"}'
    python cloud/kaggle/correr.py '{"accion": "partido", "partido": "<id>"}'

Its pure helpers are tested without Kaggle or Modal (tests/test_kaggle.py).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "cloud"))
import nube  # noqa: E402

VOLUME = "tennisbio-datos"
ORT_GPU = "1.24.4"                       # the same as cloud/modal_app.py (= the PC's onnxruntime-directml)
WORK = Path("/kaggle/working")           # what Kaggle keeps after the session: small files only (≤ 500 files)
SCRATCH = ("/kaggle/temp", "/kaggle/tmp", "/tmp")
SYNC_S = 600                             # results to Modal every 10 minutes
TEST_PREFIX = nube.TEST_PREFIX
# proofs of concept (#288, docs/nube_nativa.md): name → the module that measures it (in the analysis's own Python)
POCS = {"raqueta": "tennisbio.infra.poc_raqueta"}


def parse_job(arg: str) -> dict:
    """The job as the notebook passes it; defaults: the run folder and the outputs where Modal's would go."""
    job = json.loads(arg)
    a = job.get("accion")
    if a not in ("comprobar", "prueba", "partido", "medir"):
        raise ValueError(f"acción {a!r}")
    if a in ("prueba", "partido") and not job.get("partido"):
        raise ValueError("falta el partido")
    if a == "medir" and job.get("prueba") not in POCS:
        raise ValueError(f"prueba de concepto {job.get('prueba')!r} (vale {', '.join(POCS)})")
    mid = job.get("partido", "")
    run_id = (TEST_PREFIX + mid) if a == "prueba" else mid
    job.setdefault("salida", {"comprobar": "/runs/kaggle_comprobar", "medir": f"/runs/kaggle_medir_{job.get('prueba')}"}
                   .get(a, f"/runs/partido_{run_id}"))
    job.setdefault("output_remoto", "/output")
    job["run_id"] = run_id
    return job


def pick_scratch(candidates=SCRATCH) -> Path:
    """The candidate folder with the most free disk (Kaggle's disks change; each session says what it found)."""
    best, free = None, -1
    for c in candidates:
        p = Path(c)
        try:
            p.mkdir(parents=True, exist_ok=True)
            f = shutil.disk_usage(p).free
        except OSError:
            continue
        if f > free:
            best, free = p, f
    return best or Path("/tmp")


def changed(root: Path, seen: dict) -> list[Path]:
    """Files under root new or changed since the last upload (size and modification time); `seen` is updated."""
    out = []
    if not root.exists():
        return out
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        st = f.stat()
        key = (st.st_size, int(st.st_mtime))
        if seen.get(str(f)) != key:
            seen[str(f)] = key
            out.append(f)
    return out


def _run(cmd, **kw):
    print("$", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def modal_get(remote: str, local_dir: Path):
    """A file or a folder of the volume into local_dir (the CLI keeps the last name: /models → local_dir/models)."""
    local_dir.mkdir(parents=True, exist_ok=True)
    _run(["modal", "volume", "get", "--force", VOLUME, remote, str(local_dir) + "/"])


def modal_put(vol, files: list[Path], local_root: Path, remote_root: str):
    if not files:
        return
    with vol.batch_upload(force=True) as b:
        for f in files:
            b.put_file(str(f), f"{remote_root.rstrip('/')}/{f.relative_to(local_root).as_posix()}")


def setup_env(repo: Path, venv: Path) -> Path:
    """Python 3.11 with the repository's locked dependencies, ONNX Runtime for CUDA and the GPU hook, as Modal's image
    (cloud/modal_app.py). Returns the venv's python."""
    t0 = time.time()
    _run([sys.executable, "-m", "pip", "install", "-q", "uv"])
    req = venv.parent / "requirements.txt"
    _run(["uv", "export", "--frozen", "--no-hashes", "--no-emit-project", "--extra", "ocr", "--extra", "validation",
          "-o", str(req)], cwd=repo)
    _run(["uv", "venv", "-q", "--python", "3.11", str(venv)])
    py = venv / "bin" / "python"
    _run(["uv", "pip", "install", "-q", "--python", str(py), "-r", str(req), "onnx"])
    _run(["uv", "pip", "uninstall", "-q", "--python", str(py), "onnxruntime"])
    _run(["uv", "pip", "install", "-q", "--python", str(py), f"onnxruntime-gpu[cuda,cudnn]=={ORT_GPU}"])
    site = subprocess.run([str(py), "-c", "import site; print(site.getsitepackages()[0])"], capture_output=True,
                          text=True, check=True).stdout.strip()
    Path(site, "tennisbio_nube.pth").write_text(nube.pth_text(str(repo)), encoding="utf-8")
    if not shutil.which("ffmpeg"):
        _run(["bash", "-c", "apt-get update -qq && apt-get install -y -qq ffmpeg"])
    print(f"entorno listo en {time.time() - t0:.0f} s", flush=True)
    return py


def env_for(data: Path) -> dict:
    return {**os.environ, "TENNISBIO_DML_IS_CUDA": "1", "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1",
            "PYTHONFAULTHANDLER": "1", "HOME": str(data / "home")}


def prepare(repo: Path, data: Path, registry: list[dict]) -> list[dict]:
    """As modal_app._prepare and _catalog: the volume's models, the PC's settings, the catalogue and the clicks."""
    import yaml

    nube.use_volume_models(repo, data)
    (data / "home").mkdir(parents=True, exist_ok=True)
    nube.write_local_yaml(repo, data)
    cat = nube.cloud_catalog(registry, data / "biblioteca")
    cat["matches"] += nube.test_entries(cat["matches"], data / "videos")
    (repo / "config" / "matches.yaml").write_text(yaml.safe_dump(cat, allow_unicode=True, sort_keys=False), encoding="utf-8")
    nube.place_clicks(registry, data / "biblioteca", data / "output")
    return cat["matches"]


def measure(job: dict, py: Path, models: Path, data: Path, run: Path, vol, est: dict) -> int:
    """A proof of concept (#288): TensorRT for ONNX Runtime from its pip wheels, then the measuring module, whose
    result goes into the job's state on Modal."""
    _run(["uv", "pip", "install", "-q", "--python", str(py), "tensorrt-cu12"])
    libs = subprocess.run([str(py), "-c", "import tensorrt_libs, os; print(os.path.dirname(tensorrt_libs.__file__))"],
                          capture_output=True, text=True).stdout.strip()
    env = env_for(data)
    env["LD_LIBRARY_PATH"] = ":".join(x for x in (libs, env.get("LD_LIBRARY_PATH", "")) if x)
    out = run / "poc.json"
    p = subprocess.run([str(py), "-m", POCS[job["prueba"]], "--modelo", str(models / "racketpose.onnx"),
                        "--salida", str(out)], cwd=REPO, env=env, capture_output=True, text=True)
    print(p.stdout[-6000:], p.stderr[-3000:], flush=True)
    est["poc"] = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"error": p.stderr[-800:]}
    est["estado"] = "hecho" if p.returncode == 0 and out.exists() else "error"
    if out.exists():
        modal_put(vol, [out], run, job["salida"])
    return p.returncode


def info() -> dict:
    """What the session has: CPU, memory, disks, GPU, ffmpeg, the Modal key."""
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                mem[k] = round(int(v.split()[0]) / 2 ** 20, 1)
    except OSError:
        pass
    disks = {}
    for c in (*SCRATCH, str(WORK)):
        try:
            disks[c] = round(shutil.disk_usage(c).free / 2 ** 30, 1)
        except OSError:
            pass
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True,
                         text=True).stdout.strip() if shutil.which("nvidia-smi") else ""
    return {"python": sys.version.split()[0], "nucleos": os.cpu_count(), "memoria_gib": mem, "disco_libre_gib": disks,
            "gpu": smi, "ffmpeg": shutil.which("ffmpeg") or "", "clave_modal": bool(os.environ.get("MODAL_TOKEN_ID"))}


def main(argv: list[str]) -> int:
    job = parse_job(argv[1])
    WORK.mkdir(parents=True, exist_ok=True)
    est = {"accion": job["accion"], "partido": job.get("partido", ""), "donde": "kaggle", "estado": "en curso",
           "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "kaggle": info()}
    print(json.dumps(est, ensure_ascii=False, indent=1), flush=True)
    import modal

    vol = modal.Volume.from_name(VOLUME)
    scratch = pick_scratch()
    data, run = scratch / "data", scratch / "data" / "runs" / Path(job["salida"]).name
    run.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def save(final=False):
        # a copy: the sampler and the uploader threads change est while the job's own loop saves it
        (run / "estado.json").write_text(json.dumps(est.copy(), ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy(run / "estado.json", WORK / "estado.json")
        try:
            modal_put(vol, [run / "estado.json"], run, job["salida"])
        except Exception as e:  # noqa: BLE001 — the next save tries again
            print(f"AVISO: estado a Modal ({e})", flush=True)

    save()
    try:
        for d in ("/pc", "/biblioteca", "/home", "/models"):
            modal_get(d, data)
        models = nube.unnested(data / "models")
        est["descarga_s"] = round(time.time() - t0)
        py = setup_env(REPO, scratch / "venv")
        est["entorno_s"] = round(time.time() - t0) - est["descarga_s"]
        if job["accion"] == "medir":               # a proof of concept: the GPU and the models, no match
            return measure(job, py, models, data, run, vol, est)
        registry = json.loads((data / "pc" / "registro_partidos.json").read_text(encoding="utf-8"))
        if job["accion"] == "comprobar":
            prepare(REPO, data, registry)
            probe = subprocess.run([str(py), "-c", "import onnxruntime as o, nube_gpu; print(o.get_available_providers())"],
                                   capture_output=True, text=True, env=env_for(data), cwd=REPO)
            disc = subprocess.run([str(py), "-m", "tennisbio.infra.discovery"], capture_output=True, text=True,
                                  env=env_for(data), cwd=REPO)
            est.update(estado="hecho", proveedores=probe.stdout.strip() or probe.stderr[-500:],
                       modelos=sum(1 for _ in models.rglob("*") if _.is_file()),
                       descubrimiento=disc.stdout.strip()[-3000:] or disc.stderr[-500:])   # #289: what Kaggle has
            return 0
        matches = {m["id"]: m for m in prepare(REPO, data, registry)}
        src = matches.get(job["partido"])
        if src is None:
            est.update(estado="error", nota=f"{job['partido']} no está en la lista de partidos del PC")
            return 1
        modal_get(f"/videos/{src['video']}", data / "videos")
        if job["accion"] == "prueba":
            video, clip = data / "videos" / src["video"], None
            if nube.needs_clean_copy(video):
                full = scratch / f"{job['run_id']}_limpio.mkv"
                err = nube.clean_copy(video, full)
                est["limpieza"] = f"no se puede: se usa el .ts tal cual ({err[-120:]})" if err else "bien"
                video = full if not err else video
            clip = data / "videos" / f"{job['run_id']}{video.suffix.lower()}"
            _run(["ffmpeg", "-v", "error", "-y", "-ss", str(job.get("inicio_s", 600)), "-i", str(video), "-t",
                  str(job.get("duracion_s", 600)), "-map", "0:v:0", "-map", "0:a?", "-c", "copy", str(clip)])
            prepare(REPO, data, registry)
        else:
            try:                                          # what an earlier session (or Modal) already made
                modal_get(f"{job['output_remoto'].rstrip('/')}/{job['run_id']}", data / "output")
            except subprocess.CalledProcessError:
                print("sin resultados anteriores: desde cero", flush=True)
        out_dir, seen, stop = data / "output" / job["run_id"], {}, threading.Event()
        if job["accion"] == "partido":
            changed(out_dir, seen)                        # what came from Modal is not sent back

        def syncer():
            while not stop.wait(SYNC_S):
                try:
                    modal_put(vol, changed(out_dir, seen), out_dir, f"{job['output_remoto'].rstrip('/')}/{job['run_id']}")
                    est["subido"] = time.strftime("%H:%M:%S")
                    save()
                except Exception as e:  # noqa: BLE001 — the next round sends it
                    print(f"AVISO: subida a Modal ({e})", flush=True)
        samples: list[dict] = []

        def sampler():                            # T2 (14-11): what Kaggle's machine uses, every minute, as on Modal
            while not stop.wait(60):
                try:
                    samples.append(nube.sample_resources())
                    with open(run / "recursos.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps(samples[-1]) + "\n")
                    est["recursos_ahora"] = nube.resources_now(samples[-1])
                except Exception as e:  # noqa: BLE001 — a missed sample, never the match
                    print(f"AVISO: muestra de recursos ({e})", flush=True)
        threading.Thread(target=syncer, daemon=True).start()
        threading.Thread(target=sampler, daemon=True).start()
        t1, last_save = time.time(), time.time()
        with open(run / "log.txt", "a", encoding="utf-8") as lg:
            p = subprocess.Popen([str(py), "-m", "tennisbio.cli", "run", "--match", job["run_id"]], cwd=REPO,
                                 env=env_for(data), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                lg.write(line)
                lg.flush()
                print(line, end="", flush=True)
                prog = nube.progress_of(line)
                if prog:
                    est["progreso"] = prog
                if time.time() - last_save > nube.PROGRESS_S:     # 14-11: progress while it runs, for the queue's summary
                    est["actualizado"] = time.strftime("%H:%M:%S")
                    save()
                    last_save = time.time()
            rc = p.wait()
        stop.set()
        modal_put(vol, changed(out_dir, seen), out_dir, f"{job['output_remoto'].rstrip('/')}/{job['run_id']}")
        man_f = out_dir / "manifest.json"
        man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
        est.update(estado="hecho" if rc == 0 else "error", codigo=rc, segundos=round(time.time() - t1), coste_usd=0.0,
                   etapas={k: v.get("seconds") for k, v in man.items() if isinstance(v, dict) and "seconds" in v},
                   fallos={k: v.get("faults") for k, v in man.items() if isinstance(v, dict) and v.get("faults")},
                   modelos_en_cpu=nube.gpu_fallbacks((run / "log.txt").read_text(encoding="utf-8", errors="replace")),
                   recursos=nube.summarize_resources(samples), recursos_por_etapa=nube.per_stage(samples, man))
        est.pop("recursos_ahora", None)
        modal_put(vol, [f for f in (run / "log.txt", run / "recursos.jsonl") if f.exists()], run, job["salida"])
        return rc
    except Exception as e:  # noqa: BLE001 — written down, never silent
        est.update(estado="error", nota=f"{type(e).__name__}: {e}"[-600:])
        raise
    finally:
        est["horas_kaggle"] = round((time.time() - t0) / 3600, 2)
        est["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save(final=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
