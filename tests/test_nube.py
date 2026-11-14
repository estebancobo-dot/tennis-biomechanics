"""N0 (13-11, #273): the cloud's proof of concept. It must run the PC's code unchanged (the device «dml» with its sessions
on CUDA), upload from the PC only what it needs (never a match video), compare the cloud with the PC stroke by stroke,
and never change anything the PC runs."""
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
sys.path.insert(0, str(ROOT / "scripts"))

import nube  # noqa: E402
import subir_nube  # noqa: E402


def _providers_in_new_process(env_extra: dict, tmp_path: Path) -> str:
    """A new Python process that reads the cloud's .pth file (its paths pointing to this repository), as every process of
    the container does at start-up, then loads the pose module."""
    site_dir = tmp_path / "site"
    site_dir.mkdir(exist_ok=True)
    (site_dir / "tennisbio_nube.pth").write_text(nube.pth_text(ROOT.as_posix()), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("TENNISBIO_DML_IS_CUDA", "PYTHONPATH")}
    env.update(env_extra)
    code = (f"import site; site.addsitedir({str(site_dir)!r}); "
            "from tennisbio.pose import estimator as e; print(e.ORT_PROVIDERS['dml'])")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout.strip().splitlines()[-1]


def test_in_the_cloud_the_pcs_device_puts_its_sessions_on_cuda_also_in_a_new_process(tmp_path):
    out = _providers_in_new_process({"TENNISBIO_DML_IS_CUDA": "1"}, tmp_path)
    assert out == "['CUDAExecutionProvider', 'CPUExecutionProvider']"


def test_without_the_variable_nothing_changes_as_on_the_pc(tmp_path):
    assert _providers_in_new_process({}, tmp_path) == "['DmlExecutionProvider', 'CPUExecutionProvider']"


def test_the_pth_file_puts_the_folders_and_the_hook():
    assert nube.pth_text("/repo").splitlines() == ["/repo/src", "/repo/cloud", "/repo/cloud/arranque", "import nube_gpu"]


def test_the_cloud_runs_the_pcs_settings_with_its_own_paths():
    pc = {"paths": {"output": "C:\\tenis\\output", "videos": "C:\\tenis\\videos"}, "hwaccel": "d3d11va", "device": "dml",
          "fine_pass": {"workers": 2}}
    cfg = nube.local_yaml(Path("/data"), pc)
    assert cfg["paths"] == {"output": "/data/output", "videos": "/data/videos", "library": "/data/biblioteca"}
    assert cfg["registry"]["source"] == "yaml"                     # the cloud's own catalogue
    assert "hwaccel" not in cfg                                     # the Windows decoder
    assert cfg["device"] == "dml" and cfg["fine_pass"] == {"workers": 2}


@pytest.mark.skipif(sys.platform == "win32", reason="only in the cloud's Linux container (Windows symlinks need rights)")
def test_the_volumes_models_replace_the_repositorys(tmp_path):
    repo, data = tmp_path / "repo", tmp_path / "data"
    (repo / "models").mkdir(parents=True)
    (repo / "models" / "spotting.onnx").write_text("repo")
    (data / "models").mkdir(parents=True)
    (data / "models" / "balltrack.onnx").write_text("pc")
    assert nube.use_volume_models(repo, data)
    assert (repo / "models" / "balltrack.onnx").read_text() == "pc" and (repo / "models_repo" / "spotting.onnx").exists()
    assert nube.use_volume_models(repo, data)                      # again: nothing to do


@pytest.mark.skipif(sys.platform == "win32", reason="only in the cloud's Linux container (Windows symlinks need rights)")
def test_the_models_are_found_when_modal_nested_the_folder(tmp_path):
    """13-11: «modal volume put … models /models/» left the PC's models in /models/models/: the 10-minute test found
    none (no TransNet, no court model, no YOLO ONNX). They are found one level down, also by a warm container whose
    link points at the folder above."""
    repo, data = tmp_path / "repo", tmp_path / "data"
    (repo / "models").mkdir(parents=True)
    (data / "models" / "models").mkdir(parents=True)
    (data / "models" / "models" / "transnetv2.onnx").write_text("pc")
    (repo / "models").rename(repo / "old")
    (repo / "models").symlink_to(data / "models", target_is_directory=True)     # the link of the first version
    assert nube.use_volume_models(repo, data)
    assert (repo / "models" / "transnetv2.onnx").read_text() == "pc"
    flat = tmp_path / "flat" / "models"
    flat.mkdir(parents=True)
    (flat / "a.onnx").write_text("x")
    (flat / "models").mkdir()                                     # a file beside it: the folder is the flat one
    assert nube.unnested(flat) == flat
    assert nube.unnested(data / "models") == data / "models" / "models"


def test_write_local_yaml_reads_the_pcs_file(tmp_path):
    repo, data = tmp_path / "repo", tmp_path / "data"
    (repo / "config").mkdir(parents=True)
    (data / "pc").mkdir(parents=True)
    (data / "pc" / "local.yaml").write_text("paths:\n  output: 'C:\\tenis\\output'\nfp16: true\n", encoding="utf-8")
    nube.write_local_yaml(repo, data)
    got = yaml.safe_load((repo / "config" / "local.yaml").read_text(encoding="utf-8"))
    assert got["fp16"] is True and got["paths"]["output"] == (data / "output").as_posix()


def _report(found, precision, steps, dts=None, minutes=300.0):
    strokes = [{"match": "m", "point": i, "label": "fh", "t_clip": 10.0 + i, "step": s, "dt": (dts or [0.02] * len(steps))[i]}
               for i, s in enumerate(steps)]
    return {"summary": {"total": {"found": found, "gt": 517, "recall": found / 517},
                        "precision": {"precision": precision}, "false": [{}] * 20}, "strokes": strokes, "minutes": minutes}


def test_same_strokes_are_equivalent_and_k_is_per_stage(tmp_path):
    steps = ["encontrado"] * 100
    pc, cl = _report(467, 0.945, steps), _report(466, 0.944, steps, minutes=60.0)
    c = nube.compare(pc, cl, {"fine": 1200.0, "spotting": 300.0, "players": 50.0}, {"fine": 300.0, "spotting": 100.0})
    assert c["verdict"] == "equivalente" and c["same_step"] == 1.0
    assert c["k_stage"] == {"fine": 4.0, "spotting": 3.0} and c["k_fine"] == 4.0
    md = nube.to_markdown(c, "L4", 2.4)
    assert "Veredicto: equivalente" in md and "2.40 $" in md


def test_different_strokes_or_precision_are_not_equivalent():
    pc = _report(467, 0.945, ["encontrado"] * 100)
    other_steps = _report(467, 0.945, ["encontrado"] * 95 + ["sin_candidato"] * 5)
    assert nube.compare(pc, other_steps)["verdict"] == "distinto"
    assert len(nube.compare(pc, other_steps)["differ"]) == 5
    assert nube.compare(pc, _report(460, 0.945, ["encontrado"] * 100))["verdict"] == "distinto"
    assert nube.compare(pc, _report(467, 0.935, ["encontrado"] * 100))["verdict"] == "distinto"


def test_stage_seconds_sum_the_matches_manifests(tmp_path):
    for m, s in (("a", 10.0), ("b", 5.5)):
        (tmp_path / m).mkdir()
        (tmp_path / m / "manifest.json").write_text(json.dumps({"fine": {"seconds": s}, "probe": {"seconds": 1}}))
    assert nube.stage_seconds(tmp_path) == {"fine": 15.5, "probe": 2.0}


def test_the_gpu_modal_gave_is_named_for_its_price():
    assert nube.gpu_key("NVIDIA L4\n") == "L4" and nube.gpu_key("Tesla T4") == "T4"
    assert nube.gpu_key("NVIDIA L40S") == "L40S" and nube.gpu_key("") == "desconocida"


def test_cost_uses_the_container_price():
    # one hour of an L4 with 8 cores and 32 GiB (Modal, 13-11): 0.80 + 0.38 + 0.26
    assert nube.cost(3600, "L4", 8, 32) == 1.43


def test_the_upload_plan_takes_only_what_the_cloud_needs_never_a_match_video(tmp_path):
    repo, ds = tmp_path / "repo", tmp_path / "datasets"
    for d in (repo / "models", repo / "config", ds / "f3set" / "recall" / "videos", ds / "reports",
              ds / "f3set" / "recall" / "salidas_v17" / "recall_x", tmp_path / "videos"):
        d.mkdir(parents=True)
    (repo / "models" / "balltrack.onnx").write_text("m")
    (repo / "config" / "local.yaml").write_text("device: dml\n")
    (ds / "f3set" / "recall" / "videos" / "A.mp4").write_text("v")
    (ds / "f3set" / "recall" / "videos" / "A.json").write_text("{}")
    (ds / "f3set" / "recall" / "videos" / "A.txt").write_text("file 'C:/x'")
    (ds / "f3set" / "train.json").write_text("[]")
    (ds / "f3set" / "videos.csv").write_text("video_name,yt_id")
    (ds / "reports" / "recall_validation_detector_v17.json").write_text("{}")
    (ds / "reports" / "recall_validation_detector_v16.json").write_text("{}")
    (ds / "f3set" / "recall" / "salidas_v17" / "recall_x" / "manifest.json").write_text("{}")
    (tmp_path / "videos" / "Osaka - Rybakina.ts").write_text("match")
    plan = {r for _, r in subir_nube.upload_plan(repo, ds, "v17")}
    assert plan == {"/models", "/datasets/f3set/recall/videos/A.mp4", "/datasets/f3set/recall/videos/A.json",
                    "/datasets/f3set/train.json", "/datasets/f3set/videos.csv",
                    "/pc/reports/recall_validation_detector_v17.json", "/pc/salidas_v17/recall_x/manifest.json",
                    "/pc/local.yaml"}


def test_without_the_key_nothing_is_uploaded_and_it_says_what_to_do(tmp_path):
    assert subir_nube.read_key(tmp_path / "modal.env") == {}
    (tmp_path / "modal.env").write_text("MODAL_TOKEN_ID=ak-1\n", encoding="utf-8")
    assert subir_nube.read_key(tmp_path / "modal.env") == {}          # incomplete
    (tmp_path / "modal.env").write_text("MODAL_TOKEN_ID=ak-1\nMODAL_TOKEN_SECRET=as-2\n", encoding="utf-8")
    assert subir_nube.read_key(tmp_path / "modal.env") == {"MODAL_TOKEN_ID": "ak-1", "MODAL_TOKEN_SECRET": "as-2"}
    assert subir_nube.secrets_file(Path("C:/tenis/output")).as_posix().endswith("tenis/secretos/modal.env")


def test_the_cloud_uses_the_pcs_onnx_runtime_version():
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    dml = re.search(r'name = "onnxruntime-directml"\nversion = "([^"]+)"', lock).group(1)
    tree = ast.parse((ROOT / "cloud" / "modal_app.py").read_text(encoding="utf-8"))
    ort = next(n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(getattr(t, "id", "") == "ORT_GPU" for t in n.targets))
    assert ort == dml


def test_the_workflow_only_runs_by_hand_with_the_users_key():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nube.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    assert list(on) == ["workflow_dispatch"]                       # never by a push
    assert set(on["workflow_dispatch"]["inputs"]["accion"]["options"]) == {"comprobar", "f3set", "prueba", "partidos",
                                                                      "diagnostico", "parar", "recoger"}
    job = wf["jobs"]["nube"]
    assert job["if"] == "github.repository_owner == 'estebancobo-dot'"
    assert job["env"]["CLAVE_MODAL_1"] == "${{ secrets.MODAL_TOKEN_ID }}"
    assert job["env"]["CLAVE_MODAL_2"] == "${{ secrets.MODAL_TOKEN_SECRET }}"
    assert wf["permissions"] == {"contents": "read"}
    first = job["steps"][0]
    assert first["name"] == "Clave de Modal" and "::add-mask::" in first["run"]     # masked before any use


def test_the_key_step_finds_both_keys_however_they_were_pasted(tmp_path):
    """13-11: the user's first secret had spaces around it («Token ID is malformed»); also the whole command Modal shows
    pasted in one secret, or the two swapped."""
    import shutil
    if not shutil.which("bash"):
        import pytest
        pytest.skip("sin bash")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nube.yml").read_text(encoding="utf-8"))
    script = wf["jobs"]["nube"]["steps"][0]["run"]
    cases = [(" ak-ABC123 ", "as-XYZ789\n"), ("modal token set --token-id ak-ABC123 --token-secret as-XYZ789", ""),
             ("as-XYZ789", "ak-ABC123")]
    for one, two in cases:
        env_file = tmp_path / "env"
        env_file.write_text("")
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                           env={"PATH": os.environ.get("PATH", ""), "CLAVE_MODAL_1": one, "CLAVE_MODAL_2": two,
                                "GITHUB_ENV": str(env_file)})
        assert r.returncode == 0, r.stdout + r.stderr
        assert env_file.read_text().splitlines() == ["MODAL_TOKEN_ID=ak-ABC123", "MODAL_TOKEN_SECRET=as-XYZ789"]
    env_file.write_text("")
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": os.environ.get("PATH", ""), "CLAVE_MODAL_1": "hola", "CLAVE_MODAL_2": "",
                            "GITHUB_ENV": str(env_file)})
    assert r.returncode == 1 and env_file.read_text() == ""


def test_nothing_the_pc_runs_knows_about_the_cloud():
    """The PC's code (its stages, fingerprints and caches) does not change with N0: no module of the package imports
    the cloud's code or Modal."""
    bad = []
    for f in (ROOT / "src" / "tennisbio").rglob("*.py"):
        txt = f.read_text(encoding="utf-8")
        if re.search(r"^\s*(import|from)\s+(modal|nube|cloud)\b", txt, re.M) or "TENNISBIO_DML_IS_CUDA" in txt:
            bad.append(f.name)
    assert not bad, bad


def test_the_matches_upload_takes_each_video_and_its_record_never_the_results(tmp_path):
    lib, vids = tmp_path / "biblioteca", tmp_path / "videos"
    d = lib / "partidos" / "sin-fecha" / "sin-fecha_580c6f_rybakina"
    (d / "etapas").mkdir(parents=True)
    (lib / "jugadoras" / "rybakina").mkdir(parents=True)
    vids.mkdir()
    v = vids / "Теннис.ЮСИПОПЕН.Полуфинал.Гауфф—Рыбакина.mkv"
    v.write_text("video")
    for f in ("partido.json", "etapas/identidad_clic.json", "etapas/source.json"):
        (d / f).write_text("{}")
    (d / "etapas" / "players.npz").write_text("result")                 # a result: never uploaded
    reg = [{"id": "tennis-yusipopen-polufinal-gauff-rybakina", "video": str(v), "carpeta": str(d)},
           {"id": "sin-video", "video": str(vids / "falta.mkv"), "carpeta": str(lib / "partidos" / "x")}]
    plan = {r for _, r in subir_nube.partidos_plan(reg, lib)}
    assert plan == {"/videos/tennis-yusipopen-polufinal-gauff-rybakina.mkv",
                    "/biblioteca/partidos/sin-fecha/sin-fecha_580c6f_rybakina/partido.json",
                    "/biblioteca/partidos/sin-fecha/sin-fecha_580c6f_rybakina/etapas/identidad_clic.json",
                    "/biblioteca/partidos/sin-fecha/sin-fecha_580c6f_rybakina/etapas/source.json",
                    "/biblioteca/jugadoras"}
    without = {r for _, r in subir_nube.partidos_plan(reg, lib, videos=False)}
    assert without == plan - {"/videos/tennis-yusipopen-polufinal-gauff-rybakina.mkv"}
    from tennisbio.fresh import KEEP_LIBRARY                  # the same files «desde cero» keeps (but the video)
    assert set(subir_nube.MATCH_FILES) == {k for k in KEEP_LIBRARY if not k.endswith(".mkv")}


def test_the_cloud_catalogue_and_clicks_come_from_the_pcs_list(tmp_path):
    lib, out = tmp_path / "biblioteca", tmp_path / "output"
    d = lib / "partidos" / "sin-fecha" / "sin-fecha_f43dd2_rybakina"
    (d / "etapas").mkdir(parents=True)
    (d / "partido.json").write_text(json.dumps({"tournament": "US Open", "round": "R4", "date": "2026-09-01"}))
    (d / "etapas" / "identidad_clic.json").write_text('{"near_is_target": true}')
    reg = [{"id": "us-open-2026-r4-naomi-osaka-elena-rybakina", "jugador": "rybakina", "rival": "Naomi Osaka",
            "video": "C:\\tenis\\videos\\US Open 2026.R4.Naomi Osaka - Elena Rybakina.ts",
            "carpeta": "C:\\tenis\\biblioteca\\partidos\\sin-fecha\\sin-fecha_f43dd2_rybakina"}]
    cat = nube.cloud_catalog(reg, lib)
    assert cat == {"matches": [{"id": "us-open-2026-r4-naomi-osaka-elena-rybakina",
                                "video": "us-open-2026-r4-naomi-osaka-elena-rybakina.ts", "player": "rybakina",
                                "opponent": "Naomi Osaka", "tournament": "US Open", "date": "2026-09-01", "round": "R4"}]}
    assert nube.place_clicks(reg, lib, out) == ["us-open-2026-r4-naomi-osaka-elena-rybakina"]
    click = out / "us-open-2026-r4-naomi-osaka-elena-rybakina" / "identidad_clic.json"
    assert json.loads(click.read_text()) == {"near_is_target": True}
    click.write_text('{"kept": 1}')                                  # never over one already there
    nube.place_clicks(reg, lib, out)
    assert json.loads(click.read_text()) == {"kept": 1}


def test_the_cloud_catalogue_loads_as_the_pcs_matches_yaml(tmp_path):
    """The catalogue written in the cloud is read by tennisbio.catalog as config/matches.yaml (the video under
    paths.videos, the player's config)."""
    import shutil

    import yaml

    from tennisbio import catalog
    cfgdir = tmp_path / "config"
    shutil.copytree(ROOT / "config" / "players", cfgdir / "players")
    cat = {"matches": [{"id": "m1", "video": "m1.mkv", "player": "rybakina", "opponent": "Jessica Pegula"}]}
    (cfgdir / "matches.yaml").write_text(yaml.safe_dump(cat), encoding="utf-8")
    (ms,) = catalog.load_matches({"paths": {"videos": "/data/videos"}, "registry": {"source": "yaml"}}, cfgdir)
    assert ms.id == "m1" and ms.video == Path("/data/videos/m1.mkv") and ms.opponent == "Jessica Pegula"


def test_a_10_minute_test_clip_is_a_match_of_its_own(tmp_path):
    (tmp_path / "_prueba_m1.ts").write_text("clip")
    (tmp_path / "_prueba_otro.ts").write_text("clip")               # its source is not in the list: ignored
    ms = [{"id": "m1", "video": "m1.ts", "player": "rybakina", "opponent": "Naomi Osaka"}]
    assert nube.test_entries(ms, tmp_path) == [{"id": "_prueba_m1", "video": "_prueba_m1.ts", "player": "rybakina",
                                               "opponent": "Naomi Osaka"}]
    assert nube.test_entries(ms, tmp_path / "no") == []


def test_the_cloud_cleans_a_ts_with_the_probes_own_command(tmp_path):
    """13-11: the 10-minute test cleans the whole .ts as the probe stage does (the step the whole match takes) and only
    then cuts its clip; the tries are the probe's, word for word."""
    import inspect
    import shutil
    import subprocess

    from tennisbio import stages
    src = inspect.getsource(stages.st_probe)
    assert '"-fflags", "+genpts+igndts", "-avoid_negative_ts", "make_zero"' in src
    assert nube.CLEAN_TRIES[0] == [] and nube.CLEAN_TRIES[1] == ["-fflags", "+genpts+igndts", "-avoid_negative_ts",
                                                                 "make_zero"]
    assert '"-map", "0:v:0", "-map", "0:a?", "-dn", "-sn", "-c", "copy"' in src
    assert nube.needs_clean_copy(Path("a.TS")) and not nube.needs_clean_copy(Path("a.mkv"))
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    ts = tmp_path / "a.ts"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x48:rate=25:duration=1",
                    "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "mpeg2video", "-c:a", "mp2", str(ts)], check=True)
    assert nube.clean_copy(ts, tmp_path / "a.mkv") == "" and (tmp_path / "a.mkv").stat().st_size > 0
    assert nube.clean_copy(tmp_path / "no.ts", tmp_path / "b.mkv") != ""


def test_the_10_minute_test_archives_its_earlier_run_and_reports_the_cleaning():
    src = (ROOT / "cloud" / "modal_app.py").read_text(encoding="utf-8")
    body = src[src.index("def prueba("):]
    assert '"archivo"' in body and "shutil.move" in body and "rmtree" not in body      # never deleted
    assert "nube.clean_copy(" in body and '"limpieza"' in body


def test_a_match_run_samples_what_the_container_uses():
    """13-11: GPU, CPU and memory every minute of a match, to size the container by what was measured (cost)."""
    nube.sample_resources()                                         # the CPU % is between two samples
    s = nube.sample_resources()
    assert {"t", "cpu_pct", "cores", "ram_gb"} <= set(s) and s["ram_gb"] > 0
    rows = [{"gpu_pct": 40, "cpu_pct": 90, "ram_gb": 10}, {"gpu_pct": 60, "cpu_pct": 70, "ram_gb": 12},
            {"cpu_pct": 80, "ram_gb": 11}]
    out = nube.summarize_resources(rows)
    assert out["muestras"] == 3 and out["gpu_pct"] == {"media": 50.0, "max": 60.0}
    assert out["cpu_pct"] == {"media": 80.0, "max": 90.0} and "gpu_mem_gb" not in out
    src = (ROOT / "cloud" / "modal_app.py").read_text(encoding="utf-8")
    body = src[src.index("def partido("):src.index("def prueba(")]
    assert "nube.sample_resources()" in body and "recursos=nube.summarize_resources(samples)" in body


def test_cuda_sessions_take_only_what_they_ask_for_and_fallbacks_are_counted():
    """13-11: Pegula's test filled the T4 (two fine workers, several sessions each, ONNX Runtime's defaults) and models
    went silently to the CPU. CUDA sessions get a growing-as-asked arena and a small cuDNN workspace; each run counts
    the models that still went to the CPU."""
    sys.path.insert(0, str(ROOT / "cloud" / "arranque"))
    import nube_gpu
    opts = nube_gpu.provider_options(["CUDAExecutionProvider", "CPUExecutionProvider"])
    assert opts == [nube_gpu.CUDA_OPTIONS, {}]
    assert nube_gpu.CUDA_OPTIONS["arena_extend_strategy"] == "kSameAsRequested"
    assert nube_gpu.CUDA_OPTIONS["cudnn_conv_use_max_workspace"] == "0"
    assert nube_gpu.provider_options(["CPUExecutionProvider"]) is None
    assert nube_gpu.provider_options([("CUDAExecutionProvider", {"device_id": 0})]) is None   # its own options stay
    log = "x\nAVISO: la iGPU falló al cargar /repo/models/a.onnx (CUBLAS); se usa la CPU\ny\n"
    assert nube.gpu_fallbacks(log) == 1 and nube.gpu_fallbacks("nada") == 0
    from tennisbio.pose import estimator
    assert nube.GPU_FALLBACK in Path(estimator.__file__).read_text(encoding="utf-8")        # the PC's own words


def test_in_the_cloud_sessions_are_made_with_the_cuda_options(tmp_path):
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "nube.pth").write_text(f"{ROOT / 'src'}\n{ROOT / 'cloud' / 'arranque'}\nimport nube_gpu\n")
    code = (f"import site; site.addsitedir({str(site_dir)!r}); "
            "from tennisbio.pose import estimator as e; import onnxruntime as o; "
            "print(getattr(o.InferenceSession, '_nube', False), o.InferenceSession is e.ort.InferenceSession)")
    env = {**os.environ, "TENNISBIO_DML_IS_CUDA": "1"}
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.strip().splitlines()[-1] == "True True"


def test_a_run_that_goes_wrong_can_be_stopped_alone():
    """13-11: Pegula's test with the code before the GPU fix kept failing windows: «parar» cancels the given runs by
    their id (fc-..., printed by every launch), the others go on; the ids reach the shell as data, never as code."""
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nube.yml").read_text(encoding="utf-8"))
    step = next(s for s in wf["jobs"]["nube"]["steps"] if s.get("name") == "Parar trabajos")
    assert step["env"] == {"LLAMADAS": "${{ inputs.llamadas }}"} and "${{" not in step["run"]
    deploy = next(s for s in wf["jobs"]["nube"]["steps"] if s.get("name") == "Desplegar")
    assert "parar" in deploy["if"]
    src = (ROOT / "cloud" / "lanzar.py").read_text(encoding="utf-8")
    assert 'r"fc-[A-Za-z0-9]+"' in src and "FunctionCall.from_id(fc).cancel()" in src


def test_cuda_sessions_give_back_the_memory_a_run_no_longer_needs():
    """13-11: Osaka's 4th test filled the T4 (14.6 of 15 GB) and 14 of 58 windows failed: every CUDA session shrinks
    its arena after each run (idle sessions keep only their weights); a session that ended on the CPU runs as is."""
    sys.path.insert(0, str(ROOT / "cloud" / "arranque"))
    import nube_gpu
    assert nube_gpu.SHRINK is True
    src = (ROOT / "cloud" / "arranque" / "nube_gpu.py").read_text(encoding="utf-8")
    assert 'add_run_config_entry("memory.enable_memory_arena_shrinkage", "gpu:0")' in src
    assert '"CUDAExecutionProvider" in self.get_providers()' in src           # never on a CPU-only session


def test_the_cost_counts_the_cores_used_when_more_than_reserved():
    """13-11: Modal bills the greater of the reserved and the used CPU; Osaka's test used ~18 cores of 24 visible."""
    rows = [{"cpu_pct": 75.0, "cores": 24, "ram_gb": 18.0}, {"cpu_pct": 75.0, "cores": 24, "ram_gb": 18.0}]
    assert nube.used(rows, 8.0, 32) == (18.0, 32)
    assert nube.used([{"cpu_pct": 10.0, "cores": 24}], 8.0, 32) == (8.0, 32)
    assert nube.used([], 8.0, 32) == (8.0, 32)
    assert nube.cost(3600, "T4", *nube.used(rows, 8.0, 32)) > nube.cost(3600, "T4", 8.0, 32)


def test_a_native_crash_in_the_cloud_prints_the_python_stack():
    """13-11: Osaka's whole match ended with -11 (SIGSEGV) in the fine pass, with no trace; every Python process of the
    image (the fine pass's spawned workers too) prints its stack on such a crash."""
    src = (ROOT / "cloud" / "modal_app.py").read_text(encoding="utf-8")
    assert '"PYTHONFAULTHANDLER": "1"' in src


def test_recoger_shows_each_stage_summary_of_a_match(tmp_path):
    """14-11: for a match, «recoger» also prints its manifest's summaries (strokes, forehands, faults)."""
    wf = (ROOT / ".github" / "workflows" / "nube.yml").read_text(encoding="utf-8")
    assert "python cloud/resumen.py nube-out/manifest.json" in wf and 'TAG: ${{ inputs.tag }}' in wf
    sys.path.insert(0, str(ROOT / "cloud"))
    import resumen
    out = resumen.lines({"fine": {"seconds": 12.5, "summary": {"strokes": 3}, "faults": {"x": 1}}, "v": 2})
    assert out[0].startswith("fine (12.5 s): ") and '"strokes": 3' in out[0] and "fallos" in out[1]
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"probe": {"seconds": 1, "summary": {}}}), encoding="utf-8")
    assert resumen.main(str(f)) == 0 and resumen.main(str(tmp_path / "no.json")) == 1
