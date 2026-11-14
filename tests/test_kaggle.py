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
                 "onnxruntime-gpu[cuda,cudnn]", "nube.pth_text(", '"TENNISBIO_DML_IS_CUDA": "1"', '"tennisbio.cli", "run", "--match"'):
        assert part in src, part
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
    env = wf["jobs"]["nube"]["env"]
    assert env["KAGGLE_API_TOKEN"] == "${{ secrets.KAGGLE_API_TOKEN }}" and "KAGGLE_USERNAME" in env
    assert re.search(r"startsWith\(inputs.accion, 'kaggle'\)", steps["Guardar lo recogido"]["if"])
