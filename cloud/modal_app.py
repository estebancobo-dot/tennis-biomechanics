"""N0 (13-11, #273): the proof of concept in the cloud (Modal). The PC's F3Set validation with the PC's code and
models on an NVIDIA L4, compared stroke by stroke with the PC's result (cloud/nube.py). Deployed and launched by GitHub
Actions (.github/workflows/nube.yml) with the user's Modal key; nothing here runs on the PC.

    modal deploy cloud/modal_app.py
    python cloud/lanzar.py comprobar
    python cloud/lanzar.py f3set --tag nube

Cost: the workspace's usage limit at the monthly free credit (30 $) keeps every month at 0 € (docs/nube_n0.md).
"""
from __future__ import annotations

import sys
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nube  # noqa: E402  (cloud/nube.py: no Modal in it)

PTH = nube.pth_text("/repo")
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
        # 13-11: our folders on the path and the GPU hook through a .pth file (nube.pth_text), never PYTHONPATH:
        # setting it replaced Modal's own («No module named 'grpclib'» in /pkg/modal at start-up)
        f"python -c \"import site, pathlib; pathlib.Path(site.getsitepackages()[0], 'tennisbio_nube.pth')"
        f".write_text({PTH!r})\"",
    )
    # 13-11: no HOME on the volume (it does not exist yet while Modal starts the container: «Failed (runtime
    # initialization)» in a loop); _prepare sets it for the analysis's own processes
    .env({"TENNISBIO_DML_IS_CUDA": "1", "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"})
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


@app.function(image=image, cpu=4.0, memory=8 * 1024, volumes={str(DATA): vol}, timeout=2 * 3600)
def diag_ts(match_id: str) -> dict:
    """13-11: the cloud's ffmpeg (Debian's 7.1) could not clean Osaka's whole .ts with either of the probe stage's
    tries; the PC's (Gyan's build) could since 18-10. CPU only, cents: each ffmpeg (the system's and the static builds
    of the newest versions) with the probe's tries and a few variants on the whole .ts; which ones work, how long, and
    the clean file's duration. Decides which ffmpeg the image takes; nothing changes in the analysis."""
    import json
    import re
    import subprocess
    import time
    import urllib.request

    import nube
    _prepare()
    matches = {m["id"]: m for m in _catalog()}
    run = DATA / "runs" / "diag_ts"
    res: dict = {"partido": match_id, "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "pruebas": []}
    if match_id not in matches:
        res["nota"] = "no está en la lista"
        _save(run, res)
        vol.commit()
        return res
    video = DATA / "videos" / matches[match_id]["video"]
    res["video_gb"] = round(video.stat().st_size / 1e9, 2)
    bins = {"sistema": "ffmpeg"}
    try:                                          # the newest static builds (BtbN), kept on the volume
        rel = json.loads(urllib.request.urlopen("https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest",
                                                timeout=60).read())
        names = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        vers = sorted({m.group(1) for n in names if (m := re.fullmatch(r"ffmpeg-n(\d+\.\d+)-latest-linux64-gpl-\1\.tar\.xz", n))},
                      key=lambda v: tuple(int(x) for x in v.split(".")))[-2:]
        for v in vers:
            dest = DATA / "home" / "ffmpeg" / v
            exe = next(dest.rglob("bin/ffmpeg"), None) if dest.exists() else None
            if exe is None:
                dest.mkdir(parents=True, exist_ok=True)
                tar = dest / "f.tar.xz"
                urllib.request.urlretrieve(names[f"ffmpeg-n{v}-latest-linux64-gpl-{v}.tar.xz"], tar)
                import tarfile                    # Python's own xz (the slim image may have no xz tool)
                with tarfile.open(tar, "r:xz") as tf:
                    tf.extractall(dest, filter="data")
                tar.unlink()
                exe = next(dest.rglob("bin/ffmpeg"))
                exe.chmod(0o755)
            bins[f"estatico {v}"] = str(exe)
        vol.commit()
    except Exception as e:  # noqa: BLE001 — the system's ffmpeg is still tried
        res["aviso_estaticos"] = f"{type(e).__name__}: {e}"
    variants = {"probe 1 (tal cual)": ([], []),
                "probe 2 (genpts+igndts)": (nube.CLEAN_TRIES[1][:2], nube.CLEAN_TRIES[1][2:]),
                "genpts": (["-fflags", "+genpts"], ["-avoid_negative_ts", "make_zero"]),
                "genpts+discardcorrupt": (["-fflags", "+genpts+discardcorrupt"], ["-avoid_negative_ts", "make_zero"])}
    for bname, exe in bins.items():
        ver = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=60).stdout.splitlines()[:1]
        for vname, (fin, fout) in variants.items():
            out = Path("/tmp") / "limpio.mkv"
            out.unlink(missing_ok=True)
            t0 = time.time()
            r = subprocess.run([exe, "-v", "error", "-y", *fin, "-i", str(video), *fout, "-map", "0:v:0", "-map", "0:a?",
                                "-dn", "-sn", "-c", "copy", str(out)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=3600)
            ok = r.returncode == 0 and out.exists() and out.stat().st_size > 0
            dur = None
            if ok:
                pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(out)], capture_output=True, text=True, timeout=300)
                dur = pr.stdout.strip()
            res["pruebas"].append({"ffmpeg": bname, "version": ver[0] if ver else "", "variante": vname, "bien": ok,
                                   "segundos": round(time.time() - t0), "gb": round(out.stat().st_size / 1e9, 2)
                                   if out.exists() else 0, "duracion_s": dur,
                                   "error": "" if ok else (r.stderr or "").strip()[-300:]})
            print(json.dumps(res["pruebas"][-1], ensure_ascii=False), flush=True)
            _save(run, res)
            vol.commit()
    (Path("/tmp") / "limpio.mkv").unlink(missing_ok=True)
    res["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save(run, res)
    vol.commit()
    return res


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


def _catalog() -> list[dict]:
    """The cloud's config/matches.yaml from the PC's list of matches, and each match's click in its folder."""
    import json

    import yaml

    import nube
    reg_f = DATA / "pc" / "registro_partidos.json"
    registry = json.loads(reg_f.read_text(encoding="utf-8")) if reg_f.exists() else []
    cat = nube.cloud_catalog(registry, DATA / "biblioteca")
    cat["matches"] += nube.test_entries(cat["matches"], DATA / "videos")     # the 10-minute tests (prueba)
    Path("/repo/config/matches.yaml").write_text(yaml.safe_dump(cat, allow_unicode=True, sort_keys=False),
                                                 encoding="utf-8")
    nube.place_clicks(registry, DATA / "biblioteca", DATA / "output")
    return cat["matches"]


@app.function(**SPEC, timeout=24 * 3600, retries=modal.Retries(max_retries=1))
def partido(match_id: str) -> dict:
    """13-11 (night, the user's decision: everything in Modal): one match from scratch with the PC's code
    (`tennisbio run --match`), in its own container, so the matches of a batch run side by side. Its state, log and
    stage times in /data/runs/partido_<id>/; a retry after a lost GPU goes on from the stages already done."""
    import json
    import subprocess
    import sys
    import threading
    import time

    import nube

    _prepare()
    matches = {m["id"]: m for m in _catalog()}
    run = DATA / "runs" / f"partido_{match_id}"
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True,
                         timeout=60)
    gpu = nube.gpu_key(smi.stdout)
    est = {"partido": match_id, "estado": "en curso", "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "gpu": gpu,
           "cores": CORES, "gib": GIB, "en_catalogo": match_id in matches,
           "clic": (DATA / "output" / match_id / "identidad_clic.json").exists()}
    _save(run, est)
    vol.commit()
    if match_id not in matches:
        est.update(estado="error", nota=f"{match_id} no está en la lista de partidos del PC")
        _save(run, est)
        vol.commit()
        return est
    stop = threading.Event()

    def committer():
        while not stop.wait(120):
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001 — the next one commits
                print(f"AVISO nube: commit ({e})")
    samples: list[dict] = []

    def sampler():                            # 13-11: what the container uses, every minute (recursos.jsonl)
        while not stop.wait(60):
            try:
                samples.append(nube.sample_resources())
                with open(run / "recursos.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(samples[-1]) + "\n")
            except Exception as e:  # noqa: BLE001 — a missed sample, never the match
                print(f"AVISO nube: muestra de recursos ({e})")
    threading.Thread(target=committer, daemon=True).start()
    threading.Thread(target=sampler, daemon=True).start()
    t0 = time.time()
    with open(run / "log.txt", "a", encoding="utf-8") as lg:
        p = subprocess.Popen([sys.executable, "-m", "tennisbio.cli", "run", "--match", match_id], cwd="/repo",
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            lg.write(line)
            lg.flush()
            print(line, end="")
        rc = p.wait()
    secs = time.time() - t0
    man_f = DATA / "output" / match_id / "manifest.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
    est.update(estado="hecho" if rc == 0 else "error", codigo=rc, segundos=round(secs),
               coste_usd=nube.cost(secs, gpu, CORES, GIB), fin=time.strftime("%Y-%m-%d %H:%M:%S"),
               etapas={k: v.get("seconds") for k, v in man.items() if isinstance(v, dict) and "seconds" in v},
               fallos={k: v.get("faults") for k, v in man.items() if isinstance(v, dict) and v.get("faults")},
               recursos=nube.summarize_resources(samples),
               modelos_en_cpu=nube.gpu_fallbacks((run / "log.txt").read_text(encoding="utf-8", errors="replace")))
    _save(run, est)
    stop.set()
    vol.commit()
    return est


@app.function(**SPEC, timeout=3 * 3600)
def prueba(match_id: str, inicio_s: int = 600, duracion_s: int = 600) -> dict:
    """13-11 (the user: «¿un smoke test antes que un partido entero?»): `duracion_s` of a match from `inicio_s`, cut
    without re-encoding, analysed as a match of its own (`_prueba_<id>`, no identity click: the click is for the whole
    match) with the same code: the whole chain in the cloud in minutes and cents before a match takes GPU hours."""
    import shutil
    import subprocess
    import time

    _prepare()
    matches = {m["id"]: m for m in _catalog()}
    if match_id not in matches:
        return {"estado": "error", "nota": f"{match_id} no está en la lista de partidos del PC"}
    src = matches[match_id]
    pid = f"_prueba_{match_id}"
    run = DATA / "runs" / f"partido_{pid}"
    # 13-11: a test always from scratch: the earlier clip and outputs go to the archive (never deleted)
    arch = DATA / "archivo" / time.strftime("%Y%m%d_%H%M%S")
    for old in [*(DATA / "videos").glob(f"{pid}.*"), DATA / "output" / pid, run]:
        if old.exists():
            arch.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(arch / old.name))
    video = DATA / "videos" / src["video"]
    limpieza = "no hace falta"
    if nube.needs_clean_copy(video):
        # 13-11: the clip cut straight from the .ts had packets without a time and the probe could not clean it; the
        # whole .ts is cleaned first with the probe's own command (the step the whole match takes), then cut
        full = Path("/tmp") / f"{pid}_limpio.mkv"
        err = nube.clean_copy(video, full)
        # 13-11: Osaka's .ts cannot be cleaned by any ffmpeg (7.1, 9.0; diag_ts) and neither could the PC's
        # (probe «cleaned: false» since 18-10): the match is analysed from the .ts as it is, as on the PC
        limpieza = (f"no se puede (como en el PC desde el 18-10): se usa el .ts tal cual ({err[-120:]})" if err
                    else "bien (el .ts entero, como en el partido)")
        if not err:
            video = full
    clip = DATA / "videos" / f"{pid}{video.suffix.lower()}"     # a .ts stays a .ts (the probe then tries, as on the PC)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(inicio_s), "-i", str(video), "-t", str(duracion_s),
                    "-map", "0:v:0", "-map", "0:a?", "-c", "copy", str(clip)], check=True, timeout=1800)
    vol.commit()
    est = partido.local(pid)                  # its catalogue entry comes from the clip (nube.test_entries)
    est["limpieza"] = limpieza
    _save(run, est)
    vol.commit()
    return est
