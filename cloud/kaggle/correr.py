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
import almacen  # noqa: E402
import nube  # noqa: E402

VOLUME = "tennisbio-datos"
ORT_GPU = "1.24.4"                       # the same as cloud/modal_app.py (= the PC's onnxruntime-directml)
WORK = Path("/kaggle/working")           # what Kaggle keeps after the session: small files only (≤ 500 files)
SCRATCH = ("/kaggle/temp", "/kaggle/tmp", "/tmp")
SYNC_S = 600                             # results to Modal every 10 minutes
TEST_PREFIX = nube.TEST_PREFIX
# proofs of concept (#288, docs/nube_nativa.md): name → the module that measures it (in the analysis's own Python)
POCS = {"raqueta": "tennisbio.infra.poc_raqueta", "video": "tennisbio.infra.poc_video",
        "youtube": "tennisbio.infra.poc_youtube",       # 15-11 (#304): can the cloud download from YouTube?
        "bola": "tennisbio.infra.poc_bola",             # 15-11 (T15): TOTNet against TrackNetV3 on RacketVision
        "sapiens2": "tennisbio.infra.poc_sapiens",      # 15-11 (#307): Sapiens2 against the fine pass's pose
        "sapiens2_rapido": "tennisbio.infra.poc_sapiens",  # 21-11: the 0.4B with smaller inputs (its speed)
        "lejana": "tennisbio.infra.poc_lejana"}         # 21-11 (T25): RF-DETR for the far player, on the GPU
NEEDS_MATCH = ("video",)                 # proofs of concept measured on a match's broadcast (its video from Modal)
NEEDS_RUN = ("sapiens2", "sapiens2_rapido")   # proofs of concept on a reference test's outputs (`base`, of `partido`)
SAPIENS_TRANSFORMERS = "transformers==5.23.0"   # the first with Sapiens2ForPoseEstimation that was checked (15-11)


def parse_job(arg: str) -> dict:
    """The job as the notebook passes it; defaults: the run folder and the outputs where Modal's would go."""
    job = json.loads(arg)
    a = job.get("accion")
    if a not in ("comprobar", "prueba", "partido", "medir", "investigar", "informe"):
        raise ValueError(f"acción {a!r}")
    if a == "investigar" and not str(job.get("urls") or "").strip():
        raise ValueError("investigar necesita los vídeos («urls»)")
    if a in ("prueba", "partido") and not job.get("partido"):
        raise ValueError("falta el partido")
    if a == "medir" and job.get("prueba") not in POCS:
        raise ValueError(f"prueba de concepto {job.get('prueba')!r} (vale {', '.join(POCS)})")
    if a == "medir" and job.get("prueba") in NEEDS_MATCH + NEEDS_RUN and not job.get("partido"):
        raise ValueError(f"la prueba de concepto {job['prueba']} necesita un partido")
    mid = job.get("partido", "")
    run_id = (TEST_PREFIX + mid) if a == "prueba" else mid
    job.setdefault("salida", {"comprobar": "/runs/kaggle_comprobar", "medir": f"/runs/kaggle_medir_{job.get('prueba')}",
                              "investigar": "/runs/kaggle_investigar", "informe": "/runs/informe"}.get(
        a, f"/runs/partido_{run_id}"))
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


def changed(root: Path, seen: dict, mark: bool = True) -> list[Path]:
    """Files under root new or changed since the last upload (size and modification time). `mark`: `seen` is updated
    at once (only for what must never be sent, e.g. what came from Modal); otherwise call mark_sent after the upload
    succeeds (R44, 14-11: marked before an upload that then failed or was cut, a file was never sent again)."""
    out = []
    if not root.exists():
        return out
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        st = f.stat()
        key = (st.st_size, int(st.st_mtime))
        if seen.get(str(f)) != key:
            if mark:
                seen[str(f)] = key
            out.append(f)
    return out


def mark_sent(files: list[Path], seen: dict) -> None:
    for f in files:
        try:
            st = f.stat()
            seen[str(f)] = (st.st_size, int(st.st_mtime))
        except OSError:  # noqa: BLE001 — gone meanwhile: it is looked at again in the next round
            pass


def sync(vol, out_dir: Path, seen: dict, remote: str, lock: threading.Lock) -> list[Path]:
    """R44 (14-11, v17's strokes.json never reached Modal): what changed, uploaded under a lock (the periodic upload
    and the final one never overlap) and marked as sent only once the upload has succeeded."""
    with lock:
        files = changed(out_dir, seen, mark=False)
        modal_put(vol, files, out_dir, remote)
        mark_sent(files, seen)
        return files


def _run(cmd, **kw):
    print("$", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def modal_get(remote: str, local_dir: Path):
    """A file or a folder of the volume into local_dir (the storage port's Modal adapter, cloud/almacen.py)."""
    almacen.ModalStorage(None, VOLUME).get(remote, local_dir)


def modal_put(vol, files: list[Path], local_root: Path, remote_root: str):
    almacen.ModalStorage(vol, VOLUME).put_files(files, local_root, remote_root)


SAPIENS2_ONNX = "sapiens2_pose_0.4b_512x384.onnx"
RFDETR_ONNX = "rfdetr_medium_1152.onnx"           # scripts/bench_candidates.py EXPORTS["rfdetr"]


def ensure_sapiens2(py: Path, data: Path, models: Path, vol, est: dict) -> str:
    """#307: when this run's settings ask for Sapiens2 as the fine pass's refiner (fine_pass.refine: sapiens2) and the
    volume has no ONNX of it yet, export it here with this session's PyTorch (scripts/export_sapiens2.py) and keep it on
    the volume (/models) for the next sessions. Returns what was done ('' when Sapiens2 is not asked for)."""
    r = subprocess.run([str(py), "-c", "from tennisbio.config import load_config; "
                        "print((load_config().get('fine_pass') or {}).get('refine', ''))"],
                       cwd=REPO, env=env_for(data), capture_output=True, text=True)
    if r.stdout.strip().lower() != "sapiens2":
        return ""
    dst = REPO / "models" / SAPIENS2_ONNX
    if dst.exists():
        return "ya estaba en el volumen"
    t = time.time()
    _run([sys.executable, "-m", "pip", "install", "-q", SAPIENS_TRANSFORMERS, "safetensors", "onnx", "onnxscript"])
    _run([sys.executable, str(REPO / "scripts" / "export_sapiens2.py"), "--salida", str(dst)],
         env={**os.environ, "HF_HOME": str(data / "hf")})
    # into the folder that holds the other models (/models/models: nube.unnested), not beside it (21-11, v34)
    modal_put(vol, [dst], dst.parent, "/" + models.relative_to(data).as_posix())
    est["sapiens2"] = f"exportado y subido al volumen en {time.time() - t:.0f} s"
    return est["sapiens2"]


def wants_rfdetr(job: dict) -> bool:
    """21-11 (T25): a test or match whose settings find the far player with RF-DETR (fine_pass.far_detector)."""
    return str(((job.get("config") or {}).get("fine_pass") or {}).get("far_detector") or "").lower() == "rfdetr"


def ensure_rfdetr(data: Path, models: Path, vol, est: dict) -> str:
    """RF-DETR Medium's ONNX (scripts/export_rfdetr.py, its own pinned rfdetr) when the volume has none yet; kept in the
    volume's models folder, beside the others (nube.unnested), for the next sessions."""
    if (models / RFDETR_ONNX).exists():
        return "ya estaba en el volumen"
    t = time.time()
    _run(["uv", "run", "--with", "rfdetr==1.11.2", "python", str(REPO / "scripts" / "export_rfdetr.py"),
          "--out", str(models / RFDETR_ONNX), "--ckpt", str(models.parent / "rf-detr-medium.pth")], cwd=REPO)
    modal_put(vol, [models / RFDETR_ONNX], models, "/" + models.relative_to(data).as_posix())
    est["rfdetr"] = f"exportado y subido al volumen en {time.time() - t:.0f} s"
    return est["rfdetr"]


def setup_env(repo: Path, venv: Path, gpu: bool = True) -> Path:
    """Python 3.11 with the repository's locked dependencies, ONNX Runtime for CUDA and the GPU hook, as Modal's image
    (cloud/modal_app.py). Returns the venv's python. `gpu` False (T24, a CPU part): the locked ONNX Runtime for the CPU
    stays, as on any machine without a GPU."""
    t0 = time.time()
    _run([sys.executable, "-m", "pip", "install", "-q", "uv"])
    req = venv.parent / "requirements.txt"
    _run(["uv", "export", "--frozen", "--no-hashes", "--no-emit-project", "--extra", "ocr", "--extra", "validation",
          "-o", str(req)], cwd=repo)
    _run(["uv", "venv", "-q", "--python", "3.11", str(venv)])
    py = venv / "bin" / "python"
    _run(["uv", "pip", "install", "-q", "--python", str(py), "-r", str(req), "onnx"])
    if gpu:
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
    # T4 (14-11): no TENNISBIO_DML_IS_CUDA: the configuration says «device: auto» (nube.local_yaml)
    return {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1",
            "PYTHONFAULTHANDLER": "1", "HOME": str(data / "home")}


def prepare(repo: Path, data: Path, registry: list[dict], overrides: dict | None = None) -> list[dict]:
    """As modal_app._prepare and _catalog: the volume's models, the PC's settings (with a test's `overrides`, T5), the
    catalogue and the clicks."""
    import yaml

    nube.use_volume_models(repo, data)
    nube.write_app_players(repo, data)            # P0.5d: the people added in the application
    (data / "home").mkdir(parents=True, exist_ok=True)
    nube.write_local_yaml(repo, data, overrides)
    cat = nube.cloud_catalog(registry, data / "biblioteca")
    cat["matches"] += nube.test_entries(cat["matches"], data / "videos")
    (repo / "config" / "matches.yaml").write_text(yaml.safe_dump(cat, allow_unicode=True, sort_keys=False), encoding="utf-8")
    nube.place_clicks(registry, data / "biblioteca", data / "output")
    return cat["matches"]


def poc_args(job: dict, models: Path, video: Path | None) -> list[str]:
    """The measuring module's arguments: the model it times, or the broadcast it decodes."""
    if job["prueba"] == "raqueta":
        return ["--modelo", str(models / "racketpose.onnx")]
    if job["prueba"] == "youtube":
        return ["--urls", str(job.get("urls") or "")]
    if job["prueba"] in ("sapiens2", "sapiens2_rapido"):
        fast = ["--modelos", "facebook/sapiens2-pose-0.4b", "--tamanos", "768x576,512x384"] \
            if job["prueba"] == "sapiens2_rapido" else []
        return ["--previa", str(models.parent / "previa"), "--dispositivo", "cpu" if job.get("cpu") else "cuda", *fast]
    if job["prueba"] == "lejana":
        return ["--datos", str(models.parent / "datasets"), "--dispositivo", "cpu" if job.get("cpu") else "cuda"]
    if job["prueba"] == "bola":
        return ["--modelo", str(models / "balltrack.onnx"), "--totnet", str(models / "totnet_tennis.onnx"),
                "--datos", str(models.parent / "datasets"), "--dispositivo", "cpu" if job.get("cpu") else "cuda"]
    return ["--video", str(video)]


def measure(job: dict, py: Path, models: Path, data: Path, run: Path, vol, est: dict, video: Path | None = None) -> int:
    """A proof of concept (#288): the measuring module (TensorRT for ONNX Runtime from its pip wheels when it times a
    model), whose result goes into the job's state on Modal."""
    env = env_for(data)
    if job["prueba"] == "raqueta":
        _run(["uv", "pip", "install", "-q", "--python", str(py), "tensorrt-cu12"])
        libs = subprocess.run([str(py), "-c", "import tensorrt_libs, os; print(os.path.dirname(tensorrt_libs.__file__))"],
                              capture_output=True, text=True).stdout.strip()
        env["LD_LIBRARY_PATH"] = ":".join(x for x in (libs, env.get("LD_LIBRARY_PATH", "")) if x)
    if job["prueba"] == "bola":                    # T15: TOTNet exported here with this session's own PyTorch
        _run([sys.executable, "-m", "pip", "install", "-q", "einops", "onnx", "onnxruntime"])
        _run([sys.executable, str(REPO / "scripts" / "export_totnet.py"), "--salida", str(models / "totnet_tennis.onnx"),
              "--repo", str(models.parent / "totnet")])
    if job["prueba"] == "lejana":
        ensure_rfdetr(data, models, vol, est)
    if job["prueba"] == "youtube":                 # the newest yt-dlp, as the PC's fallback uses
        subprocess.run(["uv", "pip", "install", "-q", "--python", str(py), "-U", "yt-dlp[default]"])
    runner = str(py)
    if job["prueba"] in ("sapiens2", "sapiens2_rapido"):    # #307: Kaggle's own Python (PyTorch with CUDA), pinned
        _run([sys.executable, "-m", "pip", "install", "-q", SAPIENS_TRANSFORMERS, "safetensors"])
        base = f"/kaggle_pruebas/{job.get('base') or 'prueba_gauff_v26'}/output/{TEST_PREFIX}{job['partido']}"
        modal_get(base, models.parent / "previa")          # its windows, series and strokes, as that test left them
        runner = sys.executable
        env = {**env, "PYTHONPATH": str(REPO / "src"), "HF_HOME": str(models.parent / "hf"),
               "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}     # 15-11: it ran out of the T4's memory
    out = run / "poc.json"
    p = subprocess.run([runner, "-m", POCS[job["prueba"]], *poc_args(job, models, video), "--salida", str(out)],
                       cwd=REPO, env=env, capture_output=True, text=True)
    print(p.stdout[-6000:], p.stderr[-3000:], flush=True)
    est["poc"] = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"error": p.stderr[-800:]}
    est["estado"] = "hecho" if p.returncode == 0 and out.exists() else "error"
    if out.exists():
        modal_put(vol, [out], run, job["salida"])
    return p.returncode


def run_stages(job: dict) -> list[str]:
    """T24: the stages of this part of a test or a match (`tennisbio run --stages`); none: the whole analysis. A part
    that follows another (`sobre_lo_hecho`) runs only its stages, on what the earlier part made (`--no-upstream`):
    v31_c (15-11) on the CPU saw the GPU part's stages as stale (the fp16 setting enters a fingerprint only on a GPU)
    and ran them again; the earlier stages keep their own manifest entries."""
    if not job.get("etapas"):
        return []
    return ["--stages", *job["etapas"], *(["--no-upstream"] if job.get("sobre_lo_hecho") else [])]


REPORT_PAGE_MAX = 15 * 1024 * 1024          # nube.PAGE_MAX_BYTES: a larger page stays only on the volume
APP_MANIFEST = "resultados_app.json"        # tennisbio.app.p0_nube.MANIFEST (/output/…): what the PC's application brings


def report_files(out: Path) -> list[Path]:
    """The report's folders (each «informe*» of the outputs with its index.html) and the audit's, every file in them."""
    dirs = [d for d in sorted(out.glob("informe*")) if d.is_dir() and (d / "index.html").exists()]
    dirs += [out / "auditoria"] if (out / "auditoria").is_dir() else []
    return [f for d in dirs for f in sorted(d.rglob("*")) if f.is_file()]


def linked_videos(out: Path) -> list[Path]:
    """The strokes' videos each report page links (tennisbio.report: «video» relative to the page, in each match's
    windows folder, ../<match>/windows/<clip>): already on the volume, so not uploaded again, but in the application's
    list, so the PC brings them beside the page and its links still work there."""
    import re

    found: set[Path] = set()
    for page in sorted(out.glob("informe*/index.html")):
        for rel in re.findall(r'"video":\s*"([^"]+)"', page.read_text(encoding="utf-8", errors="replace")):
            f = (page.parent / rel).resolve()
            if f.is_file() and f.is_relative_to(out.resolve()):
                found.add(f)
    return sorted(found)


def report(job: dict, py: Path, data: Path, run: Path, vol, est: dict, registry: list[dict]) -> int:
    """21-11 (P0.5e, #301; the user: «sí»): the report of the player's forehand and the Base audit on a Kaggle CPU
    session, as cloud/modal_app.informe does on Modal (out of credit until the month turns): the analysed matches'
    outputs from the volume (never a 10-minute test), `tennisbio report` and `tennisbio audit`, and the report's
    folders with their videos and the audit back to the volume (/output/...), where the PC's application downloads
    them; the audit (and the page, when small) also in the run's folder, for the queue's nube-logs."""
    import yaml

    cat = nube.cloud_catalog(registry, data / "biblioteca")
    for m in cat["matches"]:
        try:
            modal_get(f"/output/{m['id']}", data / "output")
        except subprocess.CalledProcessError:
            print(f"{m['id']}: sin resultados en el volumen", flush=True)
    done = nube.analysed_matches(cat["matches"], data / "output")
    (REPO / "config" / "matches.yaml").write_text(yaml.safe_dump({"matches": done}, allow_unicode=True, sort_keys=False),
                                                  encoding="utf-8")
    root = data / "partidos"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    for m in done:
        (root / m["id"]).symlink_to(data / "output" / m["id"], target_is_directory=True)
    est["partidos"] = [m["id"] for m in done]
    t0, rc = time.time(), {}
    with open(run / "log.txt", "a", encoding="utf-8") as lg:
        for name, args in (("informe", ["report"]),
                           ("auditoria", ["audit", "--root", str(root), "--out", str(data / "output" / "auditoria")])):
            p = subprocess.run([str(py), "-m", "tennisbio.cli", *args], cwd=REPO, env=env_for(data), capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            lg.write(f"===== {name} (código {p.returncode})\n{p.stdout}\n{p.stderr[-4000:]}\n")
            rc[name] = p.returncode
    files = report_files(data / "output")
    modal_put(vol, files, data / "output", "/output")
    if files and not any(rc.values()):           # the list last: the application sees it only with every file up
        man = data / "output" / APP_MANIFEST
        out = (data / "output").resolve()
        listed = [f.resolve() for f in files] + linked_videos(data / "output")
        man.write_text(json.dumps({"generado": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "partidos":
                                   est["partidos"], "ficheros": {f.relative_to(out).as_posix(): f.stat().st_size
                                                                 for f in listed}}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        est["videos_enlazados"] = len(listed) - len(files)
        modal_put(vol, [man], data / "output", "/output")
    aud = data / "output" / "auditoria"
    for f in ("auditoria.md", "auditoria.json"):
        if (aud / f).exists():
            shutil.copy(aud / f, run / f)
    pages = [d / "index.html" for d in sorted((data / "output").glob("informe*")) if (d / "index.html").exists()]
    if pages and pages[0].stat().st_size < REPORT_PAGE_MAX:
        shutil.copy(pages[0], run / "informe.html")
    modal_put(vol, [f for f in run.iterdir() if f.is_file()], run, job["salida"])
    est.update(estado="hecho" if not any(rc.values()) and files else "error", codigos=rc,
               segundos=round(time.time() - t0), ficheros=len(files),
               subido_mb=round(sum(f.stat().st_size for f in files) / 2 ** 20, 1), coste_usd=0.0)
    return 0 if est["estado"] == "hecho" else 1


def research_summary(index: list[dict]) -> dict:
    """What the coaches' videos gave (#304): how many have text (and from where) and frames, and which failed."""
    src: dict = {}
    for v in index:
        if v.get("subtitles"):
            k = v.get("text_source", "subtitulos")
            src[k] = src.get(k, 0) + 1
    return {"videos": len(index), "con_texto": sum(1 for v in index if v.get("subtitles")), "texto_de": src,
            "con_fotogramas": sum(1 for v in index if v.get("frames")),
            "fallan": [{"id": v.get("id"), "error": str(v.get("video_error") or v.get("error") or "")[:200]}
                       for v in index if not v.get("frames")][:20]}


def research(job: dict, run: Path, vol, est: dict, save) -> int:
    """#304: the coaches' videos (scripts/youtube_research.py, the PC's own script) on this CPU session, with the
    speech transcribed when YouTube refuses the subtitles (429 from Kaggle, 15-11); the folder goes to Modal (the queue
    copies it to nube-logs). No models, no GPU: nothing else of the volume is needed."""
    _run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default]", "uv", "faster-whisper"])
    if not shutil.which("ffmpeg"):
        _run(["bash", "-c", "apt-get update -qq && apt-get install -y -qq ffmpeg"])
    out = run / "investigacion"
    t1, last = time.time(), time.time()
    with open(run / "log.txt", "a", encoding="utf-8") as lg:
        p = subprocess.Popen([sys.executable, str(REPO / "scripts" / "youtube_research.py"), "--out", str(out),
                              "--urls", str(job["urls"]), "--transcribir",
                              *(["--cada", str(job["cada"])] if job.get("cada") else [])], cwd=REPO, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        for line in p.stdout:
            lg.write(line)
            lg.flush()
            print(line, end="", flush=True)
            if line.strip()[:1].isdigit() and "/" in line.split()[0]:
                est["progreso"] = line.strip()[:120]
            if time.time() - last > nube.PROGRESS_S:
                est["actualizado"] = time.strftime("%H:%M:%S")
                save()
                last = time.time()
        rc = p.wait()
    idx = out / "indice.json"
    index = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else []
    files = [f for f in sorted(out.rglob("*")) if f.is_file()] if out.exists() else []
    for attempt in range(3):
        try:
            modal_put(vol, files, run, job["salida"])
            break
        except Exception as e:  # noqa: BLE001 — retried; the third failure is raised (the job ends in error)
            print(f"AVISO: subida a Modal, intento {attempt + 1} ({e})", flush=True)
            if attempt == 2:
                raise
            time.sleep(30)
    modal_put(vol, [run / "log.txt"], run, job["salida"])
    est.update(estado="hecho" if rc == 0 and idx.exists() else "error", codigo=rc, segundos=round(time.time() - t1),
               investigacion=research_summary(index), ficheros=len(files))
    est.pop("progreso", None)
    return rc


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
           "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "kaggle": info(), "config": job.get("config") or {}}
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
        if job["accion"] == "investigar":          # #304: a CPU session that needs nothing of the volume
            return research(job, run, vol, est, save)
        for d in ("/pc", "/biblioteca", "/home") + (() if job["accion"] == "informe" else ("/models",)):
            modal_get(d, data)
        for f in ("registro_partidos.json", "personas.json"):   # P0.5d: what was added in the application, if anything
            try:
                modal_get(f"/app/{f}", data / "app")
            except subprocess.CalledProcessError:
                print(f"sin {f} de la aplicación", flush=True)
        models = nube.unnested(data / "models")
        est["descarga_s"] = round(time.time() - t0)
        py = setup_env(REPO, scratch / "venv", gpu=not job.get("cpu"))
        est["entorno_s"] = round(time.time() - t0) - est["descarga_s"]
        registry = nube.read_registry(data)        # the PC's list and the application's (P0.5d)
        prepare(REPO, data, registry, job.get("config"))
        try:                                      # 14-11 (the user: nothing decided by the PC's old settings): the
            import yaml                           # settings this run really uses, without paths, in its state

            eff = yaml.safe_load((REPO / "config" / "local.yaml").read_text(encoding="utf-8")) or {}
            est["config_local"] = {k: v for k, v in eff.items() if k not in ("paths",)}
        except Exception as e:  # noqa: BLE001 — said in the state; the run goes on
            est["config_local"] = {"error": str(e)[:200]}
        if job["accion"] == "informe":             # 21-11 (P0.5e): the report and the audit, CPU only
            return report(job, py, data, run, vol, est, registry)
        if job["accion"] == "medir":               # a proof of concept: the GPU and the models (and a broadcast)
            video = None
            if job["prueba"] in NEEDS_MATCH:
                src = {m["id"]: m for m in prepare(REPO, data, registry, job.get("config"))}.get(job["partido"])
                if src is None:
                    est.update(estado="error", nota=f"{job['partido']} no está en la lista de partidos del PC")
                    return 1
                modal_get(f"/videos/{src['video']}", data / "videos")
                video = data / "videos" / src["video"]
            return measure(job, py, models, data, run, vol, est, video)
        if job["accion"] == "comprobar":
            prepare(REPO, data, registry, job.get("config"))
            probe = subprocess.run([str(py), "-c", "import onnxruntime as o, nube_gpu; print(o.get_available_providers())"],
                                   capture_output=True, text=True, env=env_for(data), cwd=REPO)
            disc = subprocess.run([str(py), "-m", "tennisbio.infra.discovery"], capture_output=True, text=True,
                                  env=env_for(data), cwd=REPO)
            est.update(estado="hecho", proveedores=probe.stdout.strip() or probe.stderr[-500:],
                       modelos=sum(1 for _ in models.rglob("*") if _.is_file()),
                       descubrimiento=disc.stdout.strip()[-3000:] or disc.stderr[-500:])   # #289: what Kaggle has
            return 0
        matches = {m["id"]: m for m in prepare(REPO, data, registry, job.get("config"))}
        ensure_sapiens2(py, data, models, vol, est)        # #307: only when the settings ask for it
        if wants_rfdetr(job):                              # T25: the far player by RF-DETR
            ensure_rfdetr(data, models, vol, est)
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
            nube.cut_clip(video, clip, job.get("inicio_s", 600), job.get("duracion_s", 600))
            prepare(REPO, data, registry, job.get("config"))
            if job.get("previa"):                         # T24: what this test's earlier part left (same clip, cut again)
                try:
                    modal_get(f"{job['output_remoto'].rstrip('/')}/{job['run_id']}", data / "output")
                except subprocess.CalledProcessError:
                    est.update(estado="error", nota="no está lo que dejó la parte anterior de esta prueba")
                    return 1
        else:
            try:                                          # what an earlier session (or Modal) already made
                modal_get(f"{job['output_remoto'].rstrip('/')}/{job['run_id']}", data / "output")
            except subprocess.CalledProcessError:
                print("sin resultados anteriores: desde cero", flush=True)
        out_dir, seen, stop, lock = data / "output" / job["run_id"], {}, threading.Event(), threading.Lock()
        remote = f"{job['output_remoto'].rstrip('/')}/{job['run_id']}"
        if job["accion"] == "partido" or job.get("previa"):
            changed(out_dir, seen)                        # what came from Modal is not sent back

        def syncer():
            while not stop.wait(SYNC_S):
                try:
                    sync(vol, out_dir, seen, remote, lock)
                    est["subido"] = time.strftime("%H:%M:%S")
                    save()
                except Exception as e:  # noqa: BLE001 — not marked as sent: the next round sends it
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
        uploader = threading.Thread(target=syncer, daemon=True)
        uploader.start()
        threading.Thread(target=sampler, daemon=True).start()
        t1, last_save = time.time(), time.time()
        with open(run / "log.txt", "a", encoding="utf-8") as lg:
            p = subprocess.Popen([str(py), "-m", "tennisbio.cli", "run", "--match", job["run_id"], *run_stages(job)], cwd=REPO,
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
            if rc == 0 and job["accion"] == "partido" and "identity" in (job.get("etapas") or []):
                ph = subprocess.run([str(py), "-c", nube.CLICK_PHOTOS, str(out_dir), str(data / "videos" / src["video"])],
                                    cwd=REPO, env=env_for(data), capture_output=True, text=True, timeout=1800)
                est["fotos_clic"] = (ph.stdout.strip() or ph.stderr.strip())[-300:]   # P0.5d: for the application
                lg.write(f"fotos del clic: {est['fotos_clic']}\n")
        stop.set()
        uploader.join(timeout=SYNC_S)                    # R44: a periodic upload in flight ends before the last one
        for attempt in range(3):                         # the last upload: everything not yet sent, retried
            try:
                sync(vol, out_dir, seen, remote, lock)
                break
            except Exception as e:  # noqa: BLE001 — retried; the third failure is raised (the job ends in error)
                print(f"AVISO: subida final a Modal, intento {attempt + 1} ({e})", flush=True)
                if attempt == 2:
                    raise
                time.sleep(30)
        est["sin_subir"] = [f.relative_to(out_dir).as_posix() for f in changed(out_dir, seen, mark=False)][:20]
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
