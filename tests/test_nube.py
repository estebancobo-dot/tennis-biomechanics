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
    assert cfg["paths"] == {"output": "/data/output", "videos": "/data/videos"}
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
    assert plan == {"/models/", "/datasets/f3set/recall/videos/A.mp4", "/datasets/f3set/recall/videos/A.json",
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
    assert set(on["workflow_dispatch"]["inputs"]["accion"]["options"]) == {"comprobar", "f3set", "recoger"}
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
