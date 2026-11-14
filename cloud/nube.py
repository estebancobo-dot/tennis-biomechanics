"""N0 (13-11, #273): the cloud proof of concept, its helpers without Modal (tested on any machine).

The cloud runs the PC's own code unchanged: the same stages and the same configuration, with the device still named
«dml», so that every code path is the PC's (GPU sessions, the half-precision pose model, two fine-pass workers, fixed
ball batches). Only where an ONNX session is placed changes: on CUDA instead of DirectML (cloud/arranque/nube_gpu.py).
It answers two questions before the cloud analyses a match (N1): does it give the same strokes as the PC, and how much
faster is it (k, per stage).

On the Modal volume (/data):
    models/                      the PC's models/ (uploaded once by scripts/subir_nube.py: the very same files)
    datasets/f3set/...           the F3Set compilations (YouTube refuses data centres) and the annotations
    pc/local.yaml                the PC's config/local.yaml (its settings, without its paths)
    pc/reports/...               the PC's F3Set report of the same code (the reference)
    pc/salidas_<tag>/<m>/manifest.json   the PC's stage times
    runs/<tag>/                  each cloud run: estado.json, log.txt, comparacion.json/.md
"""
from __future__ import annotations

import json
import os
import re
import statistics
from pathlib import Path

import yaml

def pth_text(repo: str = "/repo") -> str:
    """The .pth file of the cloud's image: our folders on the path and the line that loads the GPU hook (nube_gpu) in
    every Python process. Never PYTHONPATH (it replaced Modal's own) nor sitecustomize (the image has its own)."""
    return f"{repo}/src\n{repo}/cloud\n{repo}/cloud/arranque\nimport nube_gpu\n"


# keys of the PC's local.yaml that only make sense on Windows (paths) or with its hardware decoder
PC_ONLY = ("paths", "hwaccel")


def local_yaml(data: Path, pc_local: dict | None = None) -> dict:
    """config/local.yaml of the cloud: the PC's own settings (so that both run the same configuration), its paths
    replaced by the volume's and without the Windows hardware decoder."""
    cfg = {k: v for k, v in (pc_local or {}).items() if k not in PC_ONLY}
    cfg["paths"] = {"output": (data / "output").as_posix(), "videos": (data / "videos").as_posix(),
                    "library": (data / "biblioteca").as_posix(),
                    "cloud": data.as_posix()}          # T3: the volume's root (runs/, cola/) for the cloud's audit checks
    cfg["registry"] = {**(cfg.get("registry") or {}), "source": "yaml"}      # the cloud's catalogue (cloud_catalog)
    # T4 (14-11, #289): the device by discovery (CUDA on Kaggle and Modal), no longer the PC's «dml» put on CUDA by
    # cloud/arranque/nube_gpu.py (TENNISBIO_DML_IS_CUDA, no longer set)
    cfg["device"] = "auto"
    return cfg


def library_dir(entry: dict, library: Path) -> Path:
    """Where a match of the PC's list (registro_partidos.json: its folder as a Windows path) lives in the uploaded
    library: the same path from «partidos» on."""
    from pathlib import PureWindowsPath
    parts = PureWindowsPath(str(entry.get("carpeta") or "")).parts
    if "partidos" in parts:
        return library.joinpath(*parts[parts.index("partidos"):])
    return library / "partidos" / (parts[-1] if parts else str(entry.get("id")))


def cloud_catalog(registry: list[dict], library: Path) -> dict:
    """config/matches.yaml of the cloud (13-11, everything in Modal): each match of the PC's list with its video as
    uploaded (/data/videos/<id><ext>, scripts/subir_nube.py) and what its record says (opponent, tournament, date,
    round, surface). The cloud keeps the catalogue alone (registry.source: yaml) and flat output folders."""
    out = []
    for m in registry:
        ext = Path(str(m.get("video") or "").replace("\\", "/")).suffix.lower()
        f = library_dir(m, library) / "partido.json"
        info = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        e = {"id": str(m["id"]), "video": f"{m['id']}{ext}",
             "player": str(m.get("jugador") or info.get("jugadora") or info.get("player") or ""),
             "opponent": str(m.get("rival") or info.get("opponent") or "")}
        for k in ("tournament", "date", "surface", "round"):
            if info.get(k):
                e[k] = str(info[k])
        out.append(e)
    return {"matches": out}


TEST_PREFIX = "_prueba_"


def test_entries(matches: list[dict], videos: Path) -> list[dict]:
    """The catalogue entries of the 10-minute tests (modal_app.prueba): a clip `_prueba_<id><ext>` in the videos folder
    is a match of its own with its source match's data (and no identity click)."""
    by_id = {m["id"]: m for m in matches}
    out = []
    for f in sorted(videos.glob(f"{TEST_PREFIX}*")) if videos.is_dir() else []:
        src = by_id.get(f.stem[len(TEST_PREFIX):])
        if src is not None:
            out.append({**src, "id": f.stem, "video": f.name})
    return out


_LAST_CPU: list[float] = []


def _cpu_times() -> tuple[float, float]:
    """(busy, total) jiffies of all cores from /proc/stat."""
    f = [float(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    idle = f[3] + (f[4] if len(f) > 4 else 0)
    return sum(f) - idle, sum(f)


def sample_resources() -> dict:
    """13-11: one sample of what the container uses (GPU %, GPU memory, CPU % of the visible cores, RAM), every minute
    of a match: whether the reserved cores, memory and GPU are used, to size them by what was measured."""
    import subprocess
    import time
    s: dict = {"t": round(time.time()), "cores": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity")
               else os.cpu_count()}
    try:                                       # /proc, not psutil (only ultralytics brings it; not in the image)
        busy, total = _cpu_times()
        pb, pt = _LAST_CPU or (busy, total)
        _LAST_CPU[:] = [busy, total]
        s["cpu_pct"] = round(100 * (busy - pb) / (total - pt), 1) if total > pt else None
        mem = dict(ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines() if ":" in ln)
        kb = lambda k: float(mem[k].split()[0])  # noqa: E731
        s["ram_gb"] = round((kb("MemTotal") - kb("MemAvailable")) * 1024 / 1e9, 2)
    except (OSError, KeyError, ValueError):
        pass
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=30)
        s.update(gpu_fields(r.stdout))
    except Exception:  # noqa: BLE001 — no GPU (a CPU-only function) or nvidia-smi busy: the CPU sample stays
        pass
    return s


def gpu_fields(text: str) -> dict:
    """`nvidia-smi --query-gpu=utilization.gpu,memory.used` → gpu_pct/gpu_mem_gb of the first GPU and gpu1_pct/
    gpu1_mem_gb, … of the others (14-11, T2: Kaggle gives two T4s; whether the second one works is measured)."""
    out: dict = {}
    for i, line in enumerate(ln for ln in text.strip().splitlines() if ln.strip()):
        try:
            pct, mem = (float(x) for x in line.split(",")[:2])
        except ValueError:  # esperado: «[N/A]» or a line nvidia-smi could not fill
            continue
        p = "gpu" if i == 0 else f"gpu{i}"
        out.update({f"{p}_pct": pct, f"{p}_mem_gb": round(mem / 1024, 2)})
    return out


def resources_now(s: dict) -> str:
    """One sample in a few words for the queue's summary: «GPU 85 %·0 %, CPU 60 %, 9.1 GB»."""
    others = sorted((int(k[3:-4]), k) for k in s if re.fullmatch(r"gpu\d+_pct", k))
    gpus = [s[k] for k in ["gpu_pct", *(k for _, k in others)] if s.get(k) is not None]
    parts = ["GPU " + "·".join(f"{g:.0f} %" for g in gpus)] if gpus else []
    if s.get("cpu_pct") is not None:
        parts.append(f"CPU {s['cpu_pct']:.0f} %")
    if s.get("ram_gb") is not None:
        parts.append(f"{s['ram_gb']:.1f} GB")
    return ", ".join(parts)


GPU_FALLBACK = "falló al cargar"          # tennisbio.pose.estimator._new_session: a model the GPU could not take
PAGE_MAX_BYTES = 80 * 1024 * 1024       # the report page copied to runs/<tag> (informe): its data inside, no videos


# R47 (14-11): ONNX Runtime's own words when it cannot start CUDA and quietly puts the session on the CPU (the racket's
# proof of concept ran every option on the CPU with no error): counted as well
ORT_FALLBACK = ("Failed to create CUDAExecutionProvider", "Failed to load library libonnxruntime_providers_cuda",
                "Falling back to ['CPUExecutionProvider']", "Failed to create TensorrtExecutionProvider")


def gpu_fallbacks(log: str) -> int:
    """How many model sessions went to the CPU because the GPU could not load them (13-11: silent until Pegula's
    test; the same points, many times slower and dearer), also when ONNX Runtime did it without an error (R47)."""
    return sum(1 for ln in log.splitlines() if GPU_FALLBACK in ln or any(k in ln for k in ORT_FALLBACK))


def summarize_resources(rows: list[dict]) -> dict:
    """Mean and peak of each measure over a run's samples."""
    out: dict = {"muestras": len(rows)}
    keys = ["gpu_pct", "gpu_mem_gb", "cpu_pct", "ram_gb"]
    keys += sorted({k for r in rows for k in r if k.startswith("gpu") and k[3:4].isdigit()})   # the other GPUs
    for k in keys:
        v = [float(r[k]) for r in rows if r.get(k) is not None]
        if v:
            out[k] = {"media": round(statistics.fmean(v), 1), "max": round(max(v), 1)}
    return out


def per_stage(samples: list[dict], manifest: dict) -> dict:
    """T3 (B1, «Uso de la nube por etapa»): what each stage of a run used (CPU, every GPU, memory): the samples taken
    between its start (finished − seconds) and its end. A stage shorter than a sample interval has none."""
    import time as _t
    out: dict = {}
    for name, e in (manifest or {}).items():
        if not isinstance(e, dict) or not e.get("finished") or e.get("seconds") is None:
            continue
        try:
            end = _t.mktime(_t.strptime(str(e["finished"]), "%Y-%m-%d %H:%M:%S"))
        except ValueError:  # esperado: a manifest from an older scheme without a parseable end
            continue
        start = end - float(e["seconds"])
        rows = [s for s in samples if s.get("t") is not None and start <= float(s["t"]) <= end]
        out[name] = {"s": round(float(e["seconds"])), **summarize_resources(rows)}
    return out


TS_SUFFIXES = (".ts", ".m2ts", ".mts", ".trp")
# the probe stage's two tries (tennisbio.stages.st_probe; tests/test_nube.py keeps them equal)
CLEAN_TRIES = ([], ["-fflags", "+genpts+igndts", "-avoid_negative_ts", "make_zero"])


def needs_clean_copy(video: Path) -> bool:
    return video.suffix.lower() in TS_SUFFIXES


def clean_copy(src: Path, dst: Path, timeout: int = 3600) -> str:
    """The probe stage's clean copy of a .ts broadcast (no re-encoding): '' when it worked, else ffmpeg's last words."""
    import subprocess
    err = ""
    for flags in CLEAN_TRIES:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *flags[:2], "-i", str(src), *flags[2:], "-map", "0:v:0",
                            "-map", "0:a?", "-dn", "-sn", "-c", "copy", str(dst)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return ""
        err = (r.stderr or f"código {r.returncode}").strip()[-300:]
    return err or "sin salida"


def analysed_matches(matches: list[dict], out_root: Path) -> list[dict]:
    """14-11: the catalogue entries whose analysis reached the fine pass (manifest with «fine»), without the 10-minute
    tests: what the report and the Base audit read in the cloud (a test or a match not yet analysed would be counted)."""
    out = []
    for m in matches:
        if str(m.get("id", "")).startswith(TEST_PREFIX):
            continue
        man = out_root / str(m["id"]) / "manifest.json"
        try:
            ok = man.exists() and "fine" in json.loads(man.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ok = False
        if ok:
            out.append(m)
    return out


def place_clicks(registry: list[dict], library: Path, out_root: Path) -> list[str]:
    """The user's identity click of each match (etapas/identidad_clic.json in the library) in its flat output folder,
    where the identity stage reads it; never over one already there. Returns the matches that have it."""
    import shutil
    done = []
    for m in registry:
        src = library_dir(m, library) / "etapas" / "identidad_clic.json"
        dst = out_root / str(m["id"]) / "identidad_clic.json"
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copyfile(src, dst)
            done.append(str(m["id"]))
    return done


def merged(base: dict, extra: dict | None) -> dict:
    """base with extra on top, key by key inside nested dictionaries (the configuration's own merge)."""
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = merged(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def write_local_yaml(repo: Path, data: Path, overrides: dict | None = None) -> dict:
    """config/local.yaml of the cloud; `overrides` (T5, a test job's «config»): the settings a proof of concept tries
    on top, for that run only (e.g. {"hwaccel": "cuda"} or {"inference_preference": ["tensorrt", "cuda", "cpu"]})."""
    pc = data / "pc" / "local.yaml"
    pc_local = yaml.safe_load(pc.read_text(encoding="utf-8-sig")) if pc.exists() else {}
    cfg = merged(local_yaml(data, pc_local or {}), overrides)
    (repo / "config" / "local.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                                                encoding="utf-8")
    return cfg


def unnested(d: Path) -> Path:
    """The folder that holds a directory uploaded as «put <dir> /<name>/»: Modal puts it one level down
    (/models/models/…; 13-11, the 10-minute test found no model at all), so its files are in d/<name> when d holds
    nothing else."""
    inner = d / d.name
    if inner.is_dir() and not any(p.is_file() for p in d.iterdir()):
        return inner
    return d


def use_volume_models(repo: Path, data: Path) -> bool:
    """The repository's models/ replaced by the PC's (on the volume): the same model files on both machines."""
    src, dst = unnested(data / "models") if (data / "models").is_dir() else data / "models", repo / "models"
    if not src.is_dir():
        return False
    if dst.is_symlink():
        if Path(os.readlink(dst)) == src:
            return True
        dst.unlink()                              # a warm container's link to the folder above the models
    elif dst.exists():
        dst.rename(repo / "models_repo")
    dst.symlink_to(src, target_is_directory=True)
    return True


def stage_seconds(salidas: Path) -> dict[str, float]:
    """Seconds of each stage summed over the matches of one F3Set run (from their manifests)."""
    tot: dict[str, float] = {}
    for mf in sorted(salidas.glob("*/manifest.json")):
        m = json.loads(mf.read_text(encoding="utf-8"))
        for stage, rec in m.items():
            if isinstance(rec, dict) and isinstance(rec.get("seconds"), (int, float)):
                tot[stage] = round(tot.get(stage, 0.0) + float(rec["seconds"]), 1)
    return tot


def _key(s: dict) -> tuple:
    return (s.get("match"), s.get("point"), s.get("label"), round(float(s.get("t_clip") or 0), 1))


def _totals(rep: dict) -> dict:
    sm = rep.get("summary") or {}
    tot, pre = sm.get("total") or {}, sm.get("precision") or {}
    dts = [abs(float(s["dt"])) for s in rep.get("strokes", []) if s.get("dt") is not None]
    return {"found": tot.get("found"), "gt": tot.get("gt"), "recall": tot.get("recall"),
            "precision": pre.get("precision"), "false": len(sm.get("false") or []),
            "dt_median_s": round(statistics.median(dts), 3) if dts else None, "minutes": rep.get("minutes")}


# equivalence: the cloud gives the PC's result within what a different device can move (decimals of the models)
MAX_FOUND_DIFF = 2            # annotated strokes found (of ~517)
MAX_PRECISION_DIFF = 0.005
MIN_SAME_STEP = 0.98          # share of annotated strokes placed at the same step of the pipeline


def compare(pc: dict, cloud: dict, pc_times: dict | None = None, cloud_times: dict | None = None) -> dict:
    """The cloud's F3Set report against the PC's of the same code: totals, stroke by stroke, and k per stage."""
    a, b = _totals(pc), _totals(cloud)
    pcs = {_key(s): s for s in pc.get("strokes", [])}
    cls = {_key(s): s for s in cloud.get("strokes", [])}
    both = sorted(set(pcs) & set(cls), key=str)
    differ = [{"match": k[0], "point": k[1], "label": k[2], "t_clip": k[3], "pc": pcs[k].get("step"),
               "nube": cls[k].get("step")} for k in both if pcs[k].get("step") != cls[k].get("step")]
    same = (len(both) - len(differ)) / len(both) if both else None
    k_stage = {}
    for st in sorted(set(pc_times or {}) & set(cloud_times or {})):
        p, c = float(pc_times[st]), float(cloud_times[st])
        if p > 0 and c > 0:
            k_stage[st] = round(p / c, 2)
    fine = ("fine", "fine_doubtful", "fine_opponent")
    k_fine = (round(sum(pc_times[s] for s in fine if s in k_stage) / sum(cloud_times[s] for s in fine if s in k_stage), 2)
              if any(s in k_stage for s in fine) else None)
    ok = (a["found"] is not None and b["found"] is not None and abs(a["found"] - b["found"]) <= MAX_FOUND_DIFF
          and a["precision"] is not None and b["precision"] is not None
          and abs(a["precision"] - b["precision"]) <= MAX_PRECISION_DIFF
          and same is not None and same >= MIN_SAME_STEP)
    return {"pc": a, "nube": b, "strokes_both": len(both), "only_pc": len(set(pcs) - set(cls)),
            "only_nube": len(set(cls) - set(pcs)), "same_step": round(same, 4) if same is not None else None,
            "differ": differ[:40], "k_stage": k_stage, "k_fine": k_fine,
            "verdict": "equivalente" if ok else "distinto",
            "criteria": {"found": MAX_FOUND_DIFF, "precision": MAX_PRECISION_DIFF, "same_step": MIN_SAME_STEP}}


def to_markdown(c: dict, gpu: str = "", cost_usd: float | None = None) -> str:
    a, b = c["pc"], c["nube"]
    rows = [("Golpes anotados encontrados", f"{a['found']} de {a['gt']}", f"{b['found']} de {b['gt']}"),
            ("Precisión", a["precision"], b["precision"]),
            ("Golpes falsos", a["false"], b["false"]),
            ("Error de instante (mediana, s)", a["dt_median_s"], b["dt_median_s"]),
            ("Minutos de la ejecución", a["minutes"], b["minutes"])]
    out = [f"# Prueba de la nube (N0): F3Set en el PC y en la nube{(' (' + gpu + ')') if gpu else ''}", "",
           f"**Veredicto: {c['verdict']}** (criterio: ±{c['criteria']['found']} golpes encontrados, ±"
           f"{c['criteria']['precision']} de precisión, ≥ {c['criteria']['same_step']:.0%} de golpes en el mismo paso).",
           "", "| | PC | Nube |", "|---|---|---|"]
    out += [f"| {n} | {x} | {y} |" for n, x, y in rows]
    out += ["", f"Golpes anotados comparados: {c['strokes_both']} (mismo paso: "
                f"{c['same_step'] if c['same_step'] is None else format(c['same_step'], '.1%')}; solo en el PC "
                f"{c['only_pc']}, solo en la nube {c['only_nube']})."]
    if c["k_stage"]:
        out += ["", "**Cuánto más rápida es la nube por etapa (k = segundos del PC / segundos de la nube):** "
                + ", ".join(f"{s} {k}" for s, k in c["k_stage"].items())
                + (f"; pasada fina {c['k_fine']}" if c["k_fine"] else "") + "."]
    if cost_usd is not None:
        out += ["", f"Coste de la ejecución: {cost_usd:.2f} $ (dentro del crédito mensual: 0 €)."]
    if c["differ"]:
        out += ["", "Golpes en otro paso (los primeros):", ""]
        out += [f"- {d['match']} punto {d['point']} ({d['label']}, {d['t_clip']} s): PC {d['pc']}, nube {d['nube']}"
                for d in c["differ"][:20]]
    return "\n".join(out) + "\n"


# the price of the container (Modal, seen 13-11-2026 on modal.com/pricing): GPU, physical cores and memory per second
PRICE_S = {"L4": 0.000222, "T4": 0.000164, "A10": 0.000306, "L40S": 0.000542}
CORE_S, GIB_S = 0.0000131, 0.00000222


def gpu_key(nvidia_smi_name: str) -> str:
    """«NVIDIA L4» / «Tesla T4» (nvidia-smi) → the price key; the text itself when unknown."""
    name = (nvidia_smi_name or "").strip().splitlines()[0] if (nvidia_smi_name or "").strip() else ""
    for k in sorted(PRICE_S, key=len, reverse=True):
        if k.lower() in name.lower().split():
            return k
    return name or "desconocida"


def cost(seconds: float, gpu: str, cores: float, gib: float) -> float:
    return round(seconds * (PRICE_S.get(gpu, 0.0) + cores * CORE_S + gib * GIB_S), 2)


def used(rows: list[dict], cores: float, gib: float) -> tuple[float, float]:
    """(cores, GiB) Modal bills: the greater of what was reserved and what was used on average (13-11: Osaka's test
    reserved 8 cores and used about 18 of the 24 the container sees; the estimate from the reservation was too low)."""
    c = [float(r["cpu_pct"]) / 100 * float(r.get("cores") or 0) for r in rows if r.get("cpu_pct") is not None]
    m = [float(r["ram_gb"]) * 1e9 / 2 ** 30 for r in rows if r.get("ram_gb") is not None]
    return (round(max(cores, statistics.fmean(c)), 1) if c else cores,
            round(max(gib, statistics.fmean(m)), 1) if m else gib)


PROGRESS_S = 120          # 14-11 (the user: progress in real time): a running job's state every 2 minutes


def progress_of(line: str) -> str:
    """A stage's progress line of the analysis («[id] fine: 93 % (51/55 …) · 19 min · quedan ≈ 89 s», or «… terminada
    a las …»), shortened; '' for any other line."""
    t = line.strip()
    if re.search(r"\b\d{1,3} % \(", t) or " terminada a las " in t or t.startswith("====="):
        return re.sub(r"^\[[^\]]+\]\s*", "", t)[:160]
    return ""
