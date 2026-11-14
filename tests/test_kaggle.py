"""Paso 8b (14-11, #283, #285): Kaggle as the second free cloud, without Kaggle or Modal (cloud/kaggle/)."""
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
sys.path.insert(0, str(ROOT / "cloud"))

import correr  # noqa: E402
import cuaderno as klanzar  # noqa: E402


def test_job_defaults_put_the_results_where_modal_puts_them():
    j = correr.parse_job('{"accion": "partido", "partido": "gauff"}')
    assert j["salida"] == "/runs/partido_gauff" and j["output_remoto"] == "/output" and j["run_id"] == "gauff"
    t = correr.parse_job('{"accion": "prueba", "partido": "gauff"}')
    assert t["run_id"] == "_prueba_gauff" and t["salida"] == "/runs/partido__prueba_gauff"
    c = correr.parse_job('{"accion": "prueba", "partido": "g", "salida": "/runs/kaggle_prueba_g", '
                         '"output_remoto": "/kaggle_comparar/output"}')
    assert c["salida"] == "/runs/kaggle_prueba_g" and c["output_remoto"] == "/kaggle_comparar/output"
    assert correr.parse_job('{"accion": "comprobar"}')["salida"] == "/runs/kaggle_comprobar"
    for bad in ('{"accion": "borrar"}', '{"accion": "partido"}'):
        with pytest.raises(ValueError):
            correr.parse_job(bad)


def test_scratch_and_changed_files(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert correr.pick_scratch([str(a), str(b), "/proc/nada/x"]) in (a, b)
    root, seen = tmp_path / "out", {}
    (root / "w").mkdir(parents=True)
    (root / "manifest.json").write_text("{}")
    (root / "w" / "x.npy").write_bytes(b"1")
    assert {f.name for f in correr.changed(root, seen)} == {"manifest.json", "x.npy"}
    assert correr.changed(root, seen) == []                      # nothing new: nothing sent again
    (root / "manifest.json").write_text('{"fine": {}}')
    os.utime(root / "manifest.json", (time.time() + 5, time.time() + 5))
    assert [f.name for f in correr.changed(root, seen)] == ["manifest.json"]
    assert correr.changed(tmp_path / "no_existe", {}) == []


def test_same_environment_as_modal():
    """The same Python, locked dependencies, ONNX Runtime for CUDA and GPU hook as Modal's image."""
    app = (ROOT / "cloud" / "modal_app.py").read_text(encoding="utf-8")
    assert f'ORT_GPU = "{correr.ORT_GPU}"' in app
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    for part in ('"--no-emit-project", "--extra", "ocr", "--extra", "validation"', '"--python", "3.11"',
                 "onnxruntime-gpu[cuda,cudnn]", "nube.pth_text(", '"tennisbio.cli", "run", "--match"'):
        assert part in src, part
    # T4 (14-11): the device by discovery (nube.local_yaml: «device: auto»), no longer «dml» put on CUDA by the hook
    assert '"TENNISBIO_DML_IS_CUDA": "1"' not in src and '"TENNISBIO_DML_IS_CUDA": "1"' not in app
    assert "python_version=\"3.11\"" in app and "--extra ocr --extra validation" in app


def test_notebook_carries_the_job_and_reads_the_keys_from_its_secrets(tmp_path):
    job = {"accion": "prueba", "partido": "gauff", "commit": "abc123", "salida": "/runs/kaggle_prueba_gauff"}
    folder = klanzar.write(tmp_path / "push", "usuaria", job)
    nb = json.loads((folder / "tennisbio-cola.ipynb").read_text(encoding="utf-8"))
    code = "".join(nb["cells"][0]["source"])
    compile(code, "cell", "exec")                                # valid Python
    ns = {"json": json}
    exec(code.split("\n\n\ndef secret")[0].split("\n", 2)[2], ns)   # the JOB line alone
    assert ns["JOB"] == job
    assert 'secret("MODAL_TOKEN_ID")' in code and "cloud/kaggle/correr.py" in code and "--depth" in code
    assert "ak-" in code and "as-" in code and "print(both" not in code     # the key is never printed
    meta = json.loads((folder / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert meta["id"] == "usuaria/tennisbio-cola" and meta["is_private"] is True
    assert meta["enable_gpu"] is True and meta["enable_internet"] is True and meta["kernel_type"] == "notebook"
    assert meta["machine_shape"] == "NvidiaTeslaT4" and meta["code_file"] == "tennisbio-cola.ipynb"
    # 14-11: the notebook's secrets did not reach a run pushed by the API (ConnectionError): the key comes in the
    # user's private dataset, and is read only if the secrets are missing
    assert meta["dataset_sources"] == ["usuaria/tennisbio-clave"]
    assert klanzar.metadata("usuaria", key=False)["dataset_sources"] == []
    assert 'glob.glob("/kaggle/input/**/modal.json", recursive=True)' in code and "print(k" not in code


def test_key_dataset_is_written_and_checked(tmp_path):
    d = klanzar.key_dataset(tmp_path / "k", "usuaria", "ak-abc", "as-def")
    assert json.loads((d / "modal.json").read_text()) == {"id": "ak-abc", "secret": "as-def"}
    meta = json.loads((d / "dataset-metadata.json").read_text())
    assert meta["id"] == "usuaria/tennisbio-clave" and "isPrivate" not in meta or meta.get("isPrivate") is True
    with pytest.raises(SystemExit):
        klanzar.key_dataset(tmp_path / "k2", "usuaria", "", "as-def")
    src = (ROOT / "cloud" / "kaggle" / "cuaderno.py").read_text(encoding="utf-8")
    assert '"--public"' not in src and "-u" not in src.split("def key_dataset")[1].split("def status_of")[0]
    assert '(folder / "modal.json").unlink(missing_ok=True)' in src
    assert "if exists and not a.forzar:" in src                     # 14-11: no new version at every launch


def test_status_text():
    assert klanzar.status_of('usuaria/tennisbio-cola has status "KernelWorkerStatus.COMPLETE"') == "complete"
    assert klanzar.status_of('has status "running"') == "running"
    assert klanzar.status_of("KernelWorkerStatus.ERROR") == "error"
    assert klanzar.status_of("KernelWorkerStatus.CANCEL_ACKNOWLEDGED") == "cancelacknowledged"
    assert klanzar.status_of("403 Forbidden") == "desconocido"


def test_workflow_runs_kaggle_without_deploying_modal():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nube.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    assert {"kaggle_comprobar", "kaggle_prueba"} <= set(on["workflow_dispatch"]["inputs"]["accion"]["options"])
    steps = {s.get("name"): s for s in wf["jobs"]["nube"]["steps"]}
    assert "kaggle" in steps["Desplegar"]["if"] and "cloud/kaggle/cuaderno.py esperar" in steps["Kaggle"]["run"]
    assert "/kaggle_comparar/output" in steps["Kaggle"]["run"]                   # never over Modal's own test
    assert '"kaggle>=1.8" six' in steps["Kaggle"]["run"]                        # the CLI imports six without declaring it
    assert steps["Kaggle"]["run"].index("cuaderno.py clave") < steps["Kaggle"]["run"].index("cuaderno.py lanzar")
    assert "kaggle_prueba_*)" in steps["Recoger"]["run"] and "/kaggle_comparar/output/$d/manifest.json" in steps["Recoger"]["run"]
    env = wf["jobs"]["nube"]["env"]
    assert env["KAGGLE_API_TOKEN"] == "${{ secrets.KAGGLE_API_TOKEN }}" and "KAGGLE_USERNAME" in env
    assert re.search(r"startsWith\(inputs.accion, 'kaggle'\)", steps["Guardar lo recogido"]["if"])


def test_waiting_fails_fast_when_kaggle_leaves_it_queued(monkeypatch):
    """14-11: a session stayed queued for an hour and was waited for: now more than --max-cola minutes queued fails."""
    clock = {"t": 1000.0}
    monkeypatch.setenv("KAGGLE_USERNAME", "u")
    monkeypatch.setattr(klanzar.time, "time", lambda: clock["t"])
    monkeypatch.setattr(klanzar.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(klanzar, "_kaggle", lambda *a: type("R", (), {"stdout": 'has status "KernelWorkerStatus.QUEUED"',
                                                                      "stderr": "", "returncode": 0})())
    assert klanzar.main(["esperar", "--minutos", "60", "--max-cola", "10"]) == 3
    assert clock["t"] - 1000.0 <= 11 * 60


def test_diagnosis_reads_quota_and_versions_and_launches_nothing():
    src = (ROOT / "cloud" / "kaggle" / "diagnostico.py").read_text(encoding="utf-8")
    assert "quota_view()" in src and "get_kernel_session_status" in src and "version_label" in src
    code = src.split('"""', 2)[2]
    assert "push" not in code and "cancel" not in code                            # read only
    wf = (ROOT / ".github" / "workflows" / "nube.yml").read_text(encoding="utf-8")
    assert "python cloud/kaggle/diagnostico.py" in wf


def test_one_notebook_per_job():
    """R42 (14-11): versions of one shared notebook stuck in «Starting…» blocked every later job."""
    assert klanzar.slug_for("prueba_gauff_v16b") == "tennisbio-prueba-gauff-v16b"
    assert klanzar.slug_for("Actualizar Osaka!") == "tennisbio-actualizar-osaka"
    m = klanzar.metadata("u", slug="tennisbio-x")
    assert m["id"] == "u/tennisbio-x" and m["title"] == "tennisbio-x" and m["code_file"] == "tennisbio-x.ipynb"
    src = (ROOT / "cloud" / "cola.py").read_text(encoding="utf-8")
    assert '"--slug", notebook_slug(job["id"])' in src and 'kaggle_status(jid)' in src


def test_only_a_jobs_own_stuck_notebook_is_deleted(monkeypatch):
    """#290 (14-11): the user authorised deleting a job's notebook stuck in Kaggle; never the shared one."""
    monkeypatch.setenv("KAGGLE_USERNAME", "u")
    calls = []
    monkeypatch.setattr(klanzar, "_kaggle", lambda *a: calls.append(a) or type("R", (), {"stdout": "", "stderr": "",
                                                                                      "returncode": 0})())
    assert klanzar.main(["borrar", "--slug", "tennisbio-prueba-gauff-v16b"]) == 0
    assert calls == [("kernels", "delete", "-y", "u/tennisbio-prueba-gauff-v16b")]
    with pytest.raises(SystemExit):
        klanzar.main(["borrar", "--slug", "tennisbio-cola"])
    with pytest.raises(SystemExit):
        klanzar.main(["borrar", "--slug", "otro-cuaderno"])
    src = (ROOT / "cloud" / "cola.py").read_text(encoding="utf-8")
    assert 'if kst == "queued":' in src and '_kaggle(["borrar", "--slug", notebook_slug(jid)])' in src


def test_a_proof_of_concept_job():
    """T6 (#288): «medir» runs a proof of concept on Kaggle (TensorRT installed from pip), no match needed."""
    j = correr.parse_job('{"accion": "medir", "prueba": "raqueta"}')
    assert j["salida"] == "/runs/kaggle_medir_raqueta"
    with pytest.raises(ValueError):
        correr.parse_job('{"accion": "medir", "prueba": "nada"}')
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert '"tensorrt-cu12"' in src and "LD_LIBRARY_PATH" in src and 'models / "racketpose.onnx"' in src


def test_progress_lines_are_picked_up():
    """14-11 (the user: progress and state in real time): a running job reports its stage and % every 2 min."""
    progress_of = correr.nube.progress_of            # the same for Kaggle and Modal (cloud/nube.py)
    assert progress_of("  [g] fine_doubtful:  93 % (51/55 golpes candidatos) · 19 min · quedan ≈ 89 s\n") \
        .startswith("fine_doubtful:  93 % (51/55")
    assert progress_of("[g] spotting terminada a las 13:01:02 en 3.2 min") == "spotting terminada a las 13:01:02 en 3.2 min"
    assert progress_of("/repo/src/tennisbio/technique.py:168: RuntimeWarning: All-NaN axis") == ""
    assert correr.nube.PROGRESS_S <= 120
