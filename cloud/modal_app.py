"""N0 (13-11, #273): the proof of concept in the cloud (Modal). The PC's F3Set validation with the PC's code and
models on an NVIDIA L4, compared stroke by stroke with the PC's result (cloud/nube.py). Deployed and launched by GitHub
Actions (.github/workflows/nube.yml) with the user's Modal key; nothing here runs on the PC.

    modal deploy cloud/modal_app.py
    python cloud/lanzar.py comprobar
    python cloud/lanzar.py f3set --tag nube

Cost: the workspace's usage limit at the monthly free credit (30 $) keeps every month at 0 € (docs/nube_n0.md).
"""
from __future__ import annotations

from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[1]
APP, VOLUME = "tennisbio", "tennisbio-datos"
GPU, CORES, GIB = "L4", 8.0, 32           # like the PC: 8 cores; memory above its 20 GB (the fine pass used 18)
GPUS = ["L4", "T4"]                       # 13-11: «waiting to be scheduled on a GPU_L4 worker»: a T4 when no L4 is free
ORT_GPU = "1.24.4"                        # = onnxruntime-directml in uv.lock (the PC's): same version, other device
MODAL_CLIENT = "modal>=1.0,<2"
DATA = Path("/data")
IGNORE = [".git", ".venv", "output", "**/__pycache__", ".pytest_cache", "*.pt"]

app = modal.App(APP)
vol = modal.Volume.from_name(VOLUME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install("uv")
    .add_local_file(REPO / "pyproject.toml", "/build/pyproject.toml", copy=True)
    .add_local_file(REPO / "uv.lock", "/build/uv.lock", copy=True)
    .run_commands(
        # the PC's locked dependencies (Linux side), then ONNX Runtime for CUDA in place of the CPU one
        "cd /build && uv export --frozen --no-hashes --no-emit-project --extra ocr --extra validation "
        "-o /build/requirements.txt",
        "uv pip install --system -r /build/requirements.txt onnx",
        "uv pip uninstall --system onnxruntime",
        f"uv pip install --system 'onnxruntime-gpu[cuda,cudnn]=={ORT_GPU}'",
    )
    # 13-11: no HOME on the volume (it does not exist yet while Modal starts the container: «Failed (runtime
    # initialization)» in a loop); _prepare sets it for the analysis's own processes
    .env({"TENNISBIO_DML_IS_CUDA": "1", "PYTHONPATH": "/repo/src:/repo/cloud:/repo/cloud/arranque",
          "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"})
    .add_local_dir(REPO, "/repo", ignore=IGNORE)
)

SPEC = dict(image=image, gpu=GPUS, cpu=CORES, memory=GIB * 1024, volumes={str(DATA): vol})


def _prepare() -> dict:
    import os

    import nube
    nube.use_volume_models(Path("/repo"), DATA)
    (DATA / "home").mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(DATA / "home")       # model downloads (rtmlib) kept on the volume, for the children too
    return nube.write_local_yaml(Path("/repo"), DATA)


def _save(run: Path, est: dict) -> None:
    import json
    run.mkdir(parents=True, exist_ok=True)
    (run / "estado.json").write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


@app.function(image=image, cpu=0.25, memory=512, volumes={str(DATA): vol}, timeout=120)
def ping() -> dict:
    """13-11: the GPU check waited 10 min without its container starting. The same image and volume without a GPU (a
    fraction of a cent): if this starts and the check does not, the wait is for the GPU, not the image or the account."""
    import platform
    import sys
    (DATA / "home").mkdir(parents=True, exist_ok=True)
    return {"python": sys.version.split()[0], "plataforma": platform.platform(), "volumen": sorted(p.name for p in DATA.iterdir())}


@app.function(**SPEC, timeout=600)
def comprobar() -> dict:
    """Before spending GPU hours: the GPU, ONNX Runtime with CUDA (also in a new process, as the fine pass's workers),
    a session of a real model on CUDA, the models and the data uploaded from the PC, and the configuration in use."""
    import subprocess
    import sys

    print("comprobar: preparar", flush=True)
    _prepare()
    out: dict = {}
    print("comprobar: GPU", flush=True)
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                         capture_output=True, text=True, timeout=60)
    out["gpu"] = (smi.stdout or smi.stderr).strip()
    code = ("import onnxruntime as o; from tennisbio.pose import estimator as e; "
            "print(o.__version__); print(o.get_available_providers()); print(e.ORT_PROVIDERS['dml'])")
    print("comprobar: ONNX Runtime en un proceso nuevo", flush=True)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd="/repo", timeout=300)
    out["proceso_nuevo"] = (r.stdout + r.stderr).strip().splitlines()[-3:]
    models = Path("/repo/models")
    out["modelos"] = sorted(p.name for p in models.glob("*") if p.is_file())
    probe = models / "balltrack.onnx"
    if probe.exists():
        from tennisbio.pose.estimator import _new_session
        out["sesion_balltrack"] = _new_session(str(probe), "dml").get_providers()
    rec = DATA / "datasets" / "f3set" / "recall"
    out["compilaciones"] = sorted(p.name for p in (rec / "videos").glob("*.mp4"))
    out["anotaciones"] = sorted(p.name for p in (DATA / "datasets" / "f3set").glob("*.json"))
    out["pc"] = sorted(str(p.relative_to(DATA / "pc")) for p in (DATA / "pc").rglob("*") if p.is_file())[:40]
    from tennisbio.config import load_config
    cfg = load_config()
    out["config"] = {"device": cfg.get("device"), "fp16": cfg.get("fp16"), "paths": cfg.get("paths"),
                     "local_del_pc": (DATA / "pc" / "local.yaml").exists()}
    ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=60)
    out["ffmpeg"] = ff.stdout.splitlines()[0] if ff.stdout else ff.stderr.strip()[:200]
    _save(DATA / "runs" / "comprobar", out)
    vol.commit()
    return out


@app.function(**SPEC, timeout=24 * 3600, retries=modal.Retries(max_retries=1))
def f3set(tag: str = "nube", max_points: int = 0, matches: str = "", pc_tag: str = "v17") -> dict:
    """The F3Set validation (scripts/validate_recall.py --spotter) from scratch on the volume, then the comparison with
    the PC's report of the same code (pc_tag). A retry after a lost GPU goes on from the cached stages."""
    import json
    import subprocess
    import sys
    import threading
    import time

    import nube

    _prepare()
    run = DATA / "runs" / tag
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True,
                         timeout=60)
    gpu = nube.gpu_key(smi.stdout)               # the one Modal gave (L4, or T4 when no L4 was free)
    est = {"tag": tag, "estado": "en curso", "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "gpu": gpu,
           "cores": CORES, "gib": GIB, "pc_tag": pc_tag, "max_points": max_points, "matches": matches}
    _save(run, est)
    vol.commit()
    stop = threading.Event()

    def committer():                       # the log and the status visible from outside while it runs
        while not stop.wait(120):
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001 — the next one commits
                print(f"AVISO nube: commit ({e})")
    threading.Thread(target=committer, daemon=True).start()

    cmd = [sys.executable, "/repo/scripts/validate_recall.py", "--root", str(DATA / "datasets"), "--spotter",
           "--tag", tag]
    if max_points:
        cmd += ["--max-points", str(max_points)]
    if matches:
        cmd += ["--matches", matches]
    t0 = time.time()
    with open(run / "log.txt", "a", encoding="utf-8") as lg:
        p = subprocess.Popen(cmd, cwd="/repo", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            lg.write(line)
            lg.flush()
            print(line, end="")
        rc = p.wait()
    secs = time.time() - t0
    est.update(estado="hecho" if rc == 0 else "error", codigo=rc, segundos=round(secs),
               coste_usd=nube.cost(secs, gpu, CORES, GIB), fin=time.strftime("%Y-%m-%d %H:%M:%S"))
    reports = DATA / "datasets" / "reports"
    cloud_rep = reports / f"recall_validation_detector_{tag}.json"
    pc_rep = DATA / "pc" / "reports" / f"recall_validation_detector_{pc_tag}.json"
    for f in (cloud_rep, cloud_rep.with_suffix(".md")):
        if f.exists():
            (run / f.name).write_bytes(f.read_bytes())
    if cloud_rep.exists() and pc_rep.exists():
        c = nube.compare(json.loads(pc_rep.read_text(encoding="utf-8")), json.loads(cloud_rep.read_text(encoding="utf-8")),
                         nube.stage_seconds(DATA / "pc" / f"salidas_{pc_tag}"),
                         nube.stage_seconds(DATA / "datasets" / "f3set" / "recall" / f"salidas_{tag}"))
        (run / "comparacion.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        (run / "comparacion.md").write_text(nube.to_markdown(c, gpu, est["coste_usd"]), encoding="utf-8")
        est.update(veredicto=c["verdict"], k_fine=c["k_fine"])
    else:
        est["nota"] = f"sin comparación: falta {'el informe de la nube' if not cloud_rep.exists() else pc_rep.name}"
    _save(run, est)
    stop.set()
    vol.commit()
    return est
