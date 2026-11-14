"""Paso 8b (14-11, #283, #285): Kaggle from GitHub Actions. Writes the «tennisbio-cola» notebook for one job (a cell
that takes the Modal key from the notebook's secrets, fetches this repository at the given commit and runs
cloud/kaggle/correr.py), pushes it with Kaggle's API (a new version of the user's notebook, so it keeps its secrets and
its internet), and reads its status and its output.

    python cloud/kaggle/cuaderno.py lanzar --accion comprobar --commit <sha>
    python cloud/kaggle/cuaderno.py esperar [--minutos 50]
    python cloud/kaggle/cuaderno.py salida --dir kaggle-out

Needs KAGGLE_API_TOKEN and KAGGLE_USERNAME (GitHub secrets). The notebook is private and always the same one.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SLUG = "tennisbio-cola"
KEY_SLUG = "tennisbio-clave"            # the user's private dataset with the Modal key (only this notebook reads it)
REPO_URL = "https://github.com/estebancobo-dot/tennis-biomechanics.git"
STATES = ("queued", "running", "complete", "error", "cancelrequested", "cancelacknowledged")

CELL = '''# tennisbio: one job of the cloud queue (written by cloud/kaggle/cuaderno.py; do not edit here)
import json, os, re, subprocess, sys
JOB = json.loads({job!r})


def secret(name):
    try:
        from kaggle_secrets import UserSecretsClient
        return UserSecretsClient().get_secret(name) or ""
    except Exception as e:
        print(f"secreto {{name}}: {{type(e).__name__}}")
        return ""


both = secret("MODAL_TOKEN_ID") + " " + secret("MODAL_TOKEN_SECRET")
if "as-" not in both:
    # 14-11: the notebook's secrets do not reach a run pushed by the API (ConnectionError): the key comes in the
    # user's private dataset «tennisbio-clave» (written by cuaderno.py clave from the GitHub secrets)
    import glob
    for f in glob.glob("/kaggle/input/**/modal.json", recursive=True):
        k = json.load(open(f))
        both = str(k.get("id", "")) + " " + str(k.get("secret", ""))
        break
ids = re.findall(r"ak-[A-Za-z0-9]+", both)[:1] + re.findall(r"as-[A-Za-z0-9]+", both)[:1]
env = dict(os.environ)
if len(ids) == 2:
    env.update(MODAL_TOKEN_ID=ids[0], MODAL_TOKEN_SECRET=ids[1])
print("clave de Modal:", "sí" if len(ids) == 2 else "NO (ni en los secretos ni en el conjunto de datos tennisbio-clave)")
repo = "/tmp/repo"
for cmd in (["git", "init", "-q", repo], ["git", "-C", repo, "remote", "add", "origin", {url!r}],
            ["git", "-C", repo, "fetch", "-q", "--depth", "1", "origin", JOB["commit"]],
            ["git", "-C", repo, "checkout", "-q", "FETCH_HEAD"],
            [sys.executable, "-m", "pip", "install", "-q", "modal>=1.0,<2", "pyyaml"]):
    subprocess.run(cmd, check=True)
rc = subprocess.run([sys.executable, repo + "/cloud/kaggle/correr.py", json.dumps(JOB)], env=env).returncode
if rc:
    raise SystemExit(rc)
'''


def notebook(job: dict) -> dict:
    """The notebook (one code cell) for a job; the job carries the commit of the code to run."""
    src = CELL.format(job=json.dumps(job, ensure_ascii=False), url=REPO_URL)
    return {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                       "source": src.splitlines(keepends=True)}],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def metadata(user: str, key: bool = True) -> dict:
    """kernel-metadata.json: the user's private notebook, on two T4s, with internet (the Kaggle API's documented fields);
    `key`: with the private key dataset (14-11: without it, a diagnosis of a session left queued)."""
    return {"id": f"{user}/{SLUG}", "title": SLUG, "code_file": f"{SLUG}.ipynb", "language": "python",
            "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_internet": True,
            "machine_shape": "NvidiaTeslaT4", "dataset_sources": [f"{user}/{KEY_SLUG}"] if key else [],
            "competition_sources": [], "kernel_sources": []}


def write(folder: Path, user: str, job: dict, key: bool = True) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{SLUG}.ipynb").write_text(json.dumps(notebook(job), ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata(user, key), indent=1), encoding="utf-8")
    return folder


def key_dataset(folder: Path, user: str, token_id: str, token_secret: str) -> Path:
    """The private dataset with the Modal key: modal.json and its metadata (`kaggle datasets create` makes it private
    unless told otherwise; it is never made public here)."""
    if not (token_id.startswith("ak-") and token_secret.startswith("as-")):
        raise SystemExit("la clave de Modal no está en el entorno (MODAL_TOKEN_ID y MODAL_TOKEN_SECRET)")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "modal.json").write_text(json.dumps({"id": token_id, "secret": token_secret}), encoding="utf-8")
    (folder / "dataset-metadata.json").write_text(json.dumps({"title": KEY_SLUG, "id": f"{user}/{KEY_SLUG}",
                                                              "licenses": [{"name": "other"}]}), encoding="utf-8")
    return folder


def status_of(text: str) -> str:
    """The kernel's state from `kaggle kernels status` («... has status "KernelWorkerStatus.COMPLETE"»)."""
    t = text.lower().replace("_", "")
    for s in STATES:
        if re.search(rf"\b{s}\b", t) or f".{s}" in t or f'"{s}"' in t:
            return s
    return "desconocido"


def _user() -> str:
    u = os.environ.get("KAGGLE_USERNAME", "").strip()
    if not u:
        raise SystemExit("falta el secreto KAGGLE_USERNAME")
    return u


def _kaggle(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["kaggle", *args], capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("orden", choices=("clave", "lanzar", "estado", "esperar", "salida", "sonda"))
    ap.add_argument("--accion", default="comprobar")
    ap.add_argument("--partido", default="")
    ap.add_argument("--salida-remota", default="", help="la carpeta de la ejecución en Modal (/runs/<tag>)")
    ap.add_argument("--output-remoto", default="", help="dónde van sus resultados en Modal (por defecto /output)")
    ap.add_argument("--commit", default="")
    ap.add_argument("--minutos", type=float, default=50)
    ap.add_argument("--max-cola", type=float, default=10, help="minutos en cola de Kaggle que se aceptan antes de fallar")
    ap.add_argument("--dir", type=Path, default=Path("kaggle-out"))
    ap.add_argument("--sin-clave", action="store_true", help="sin el conjunto de datos de la clave (diagnóstico)")
    ap.add_argument("--forzar", action="store_true", help="clave: una versión nueva aunque ya exista (clave cambiada)")
    a = ap.parse_args(argv)
    kid = f"{_user()}/{SLUG}"
    if a.orden == "sonda":                    # 14-11: does Kaggle start any GPU session at all? (a new, tiny notebook)
        folder = Path("kaggle-sonda")
        folder.mkdir(parents=True, exist_ok=True)
        nb = notebook({"accion": "sonda"})
        nb["cells"][0]["source"] = ["import subprocess\n", "print(subprocess.run(['nvidia-smi'], capture_output=True, text=True).stdout)\n"]
        (folder / "tennisbio-sonda.ipynb").write_text(json.dumps(nb), encoding="utf-8")
        meta = {**metadata(_user(), key=False), "id": f"{_user()}/tennisbio-sonda", "title": "tennisbio-sonda",
                "code_file": "tennisbio-sonda.ipynb", "enable_internet": False}
        (folder / "kernel-metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        r = _kaggle("kernels", "push", "-p", str(folder))
        print(r.stdout, r.stderr)
        end = time.time() + a.minutos * 60
        while time.time() < end:
            st = _kaggle("kernels", "status", f"{_user()}/tennisbio-sonda")
            print(time.strftime("%H:%M:%S"), status_of(st.stdout + st.stderr), flush=True)
            if status_of(st.stdout + st.stderr) in ("running", "complete", "error"):
                return 0
            time.sleep(20)
        return 3
    if a.orden == "clave":                    # the key dataset, created once and then a new version each time
        folder = key_dataset(Path("kaggle-clave"), _user(), os.environ.get("MODAL_TOKEN_ID", ""),
                             os.environ.get("MODAL_TOKEN_SECRET", ""))
        try:
            exists = _kaggle("datasets", "status", f"{_user()}/{KEY_SLUG}").returncode == 0
            if exists and not a.forzar:
                # 14-11: not a new version at every launch (the key does not change; a dataset version still being
                # processed may keep the notebook queued)
                print("conjunto de datos de la clave: ya está")
                return 0
            r = (_kaggle("datasets", "version", "-p", str(folder), "-m", "clave") if exists
                 else _kaggle("datasets", "create", "-p", str(folder)))
            print(r.stdout, r.stderr)
            for _ in range(30):               # until Kaggle has it ready for the notebook
                st = _kaggle("datasets", "status", f"{_user()}/{KEY_SLUG}")
                print("conjunto de datos:", (st.stdout + st.stderr).strip(), flush=True)
                if "ready" in (st.stdout + st.stderr).lower():
                    return 0
                time.sleep(10)
            return 1
        finally:
            (folder / "modal.json").unlink(missing_ok=True)      # never left on the runner's disk
    if a.orden == "lanzar":
        job = {"accion": a.accion, "commit": a.commit}
        if a.partido:
            job["partido"] = a.partido
        if a.salida_remota:
            job["salida"] = a.salida_remota
        if a.output_remoto:
            job["output_remoto"] = a.output_remoto
        folder = write(Path("kaggle-push"), _user(), job, key=not a.sin_clave)
        r = _kaggle("kernels", "push", "-p", str(folder))
        print(r.stdout, r.stderr)
        # 14-11: the CLI prints «Kernel push error: …» and still exits 0
        return r.returncode or (4 if "push error" in (r.stdout + r.stderr).lower() else 0)
    if a.orden == "estado":
        r = _kaggle("kernels", "status", kid)
        print(status_of(r.stdout + r.stderr), "|", (r.stdout + r.stderr).strip())
        return 0
    if a.orden == "esperar":
        end, queued_since = time.time() + a.minutos * 60, None
        while True:
            r = _kaggle("kernels", "status", kid)
            st = status_of(r.stdout + r.stderr)
            print(time.strftime("%H:%M:%S"), st, "|", (r.stdout + r.stderr).strip()[-200:], flush=True)
            if st in ("complete", "error", "cancelacknowledged") or time.time() > end:
                return 0 if st == "complete" else 1
            # 14-11 (the user: react in seconds, not in an hour): queued longer than --max-cola is a failure
            queued_since = (queued_since or time.time()) if st == "queued" else None
            if queued_since and time.time() - queued_since > a.max_cola * 60:
                print(f"FALLO: en cola de Kaggle más de {a.max_cola:g} min sin arrancar", flush=True)
                return 3
            time.sleep(30)
    a.dir.mkdir(parents=True, exist_ok=True)
    r = _kaggle("kernels", "output", kid, "-p", str(a.dir), "-o")
    print(r.stdout, r.stderr)
    for f in sorted(a.dir.glob("*")):
        print(f"===== {f.name}")
        txt = f.read_text(encoding="utf-8", errors="replace") if f.stat().st_size < 2_000_000 else "(grande)"
        print(txt[-12000:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
