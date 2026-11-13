"""N0 (13-11, #273): uploads ONCE, from the PC, what the cloud's proof of concept needs and only the PC has: its model
files, the F3Set compilations (YouTube refuses downloads from data centres), its configuration settings and its F3Set
report of the same code (the reference the cloud is compared with). To the user's own Modal volume, with the key saved
by 5_conectar_nube.bat (<base>\\secretos\\modal.env, never in the repository). A job of the single queue:

    accion: medir / script: subir_nube / argumentos: --pc-tag v17

The match videos are NOT uploaded here (the matches go to the cloud only in N1, after the 6 matches, decision 13-11).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

VOLUME = "tennisbio-datos"
CLIENT = "modal>=1.0,<2"                  # the same client as the cloud (cloud/modal_app.py), run by uv on its own


def secrets_file(out_root: Path) -> Path:
    return out_root.parent / "secretos" / "modal.env"


def read_key(path: Path) -> dict:
    """MODAL_TOKEN_ID and MODAL_TOKEN_SECRET from the file the double-click script wrote; {} if missing or incomplete."""
    if not path.exists():
        return {}
    env = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        k, _, v = line.partition("=")
        if k.strip() in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET") and v.strip():
            env[k.strip()] = v.strip()
    return env if len(env) == 2 else {}


def upload_plan(repo: Path, datasets: Path, pc_tag: str) -> list[tuple[Path, str]]:
    """(local path, path in the volume) of everything the cloud needs; only what exists."""
    rec = datasets / "f3set" / "recall"
    plan: list[tuple[Path, str]] = [(repo / "models", "/models/")]
    for f in sorted((rec / "videos").glob("*")):
        if f.suffix in (".mp4", ".json"):
            plan.append((f, f"/datasets/f3set/recall/videos/{f.name}"))
    for f in sorted((datasets / "f3set").glob("*")):
        if f.is_file() and f.suffix in (".json", ".csv"):
            plan.append((f, f"/datasets/f3set/{f.name}"))
    for f in sorted((datasets / "reports").glob(f"recall_validation_detector_{pc_tag}.*")):
        plan.append((f, f"/pc/reports/{f.name}"))
    for mf in sorted((rec / f"salidas_{pc_tag}").glob("*/manifest.json")):
        plan.append((mf, f"/pc/salidas_{pc_tag}/{mf.parent.name}/manifest.json"))
    if (repo / "config" / "local.yaml").exists():
        plan.append((repo / "config" / "local.yaml", "/pc/local.yaml"))
    return [(p, r) for p, r in plan if p.exists()]


def _modal(args: list[str], env: dict, timeout: int = 7200) -> subprocess.CompletedProcess:
    cmd = ["uv", "tool", "run", "--from", CLIENT, "modal", *args]
    return subprocess.run(cmd, env={**os.environ, **env}, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def _size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc-tag", default="v17", help="la ejecución de F3Set del PC con la que se compara la nube")
    ap.add_argument("--solo-plan", action="store_true", help="solo dice qué subiría")
    a = ap.parse_args()
    from tennisbio.config import load_config
    out = Path((load_config().get("paths") or {}).get("output") or "output")
    datasets = out.parent / "datasets"
    plan = upload_plan(ROOT, datasets, a.pc_tag)
    total = sum(_size(p) for p, _ in plan)
    print(f"Subir a la nube (volumen {VOLUME}): {len(plan)} ficheros o carpetas, {total / 1e9:.2f} GB")
    for p, r in plan:
        print(f"  {p} -> {r}")
    if a.solo_plan:
        return 0
    key = read_key(secrets_file(out))
    if not key:
        print(f"FALTA LA CLAVE DE MODAL: doble clic en 5_conectar_nube.bat (se guarda en {secrets_file(out)})")
        return 2
    if not any(r.startswith("/datasets/f3set/recall/videos/") for _, r in plan):
        print(f"FALTAN LAS COMPILACIONES DE F3SET en {datasets / 'f3set' / 'recall' / 'videos'}")
        return 2
    t0 = time.time()
    r = _modal(["volume", "create", VOLUME], key, 300)
    if r.returncode and "already exists" not in (r.stdout + r.stderr).lower():
        print(f"no se pudo crear el volumen: {(r.stdout + r.stderr).strip()[-400:]}")
        return 1
    done, failed = [], []
    for p, remote in plan:
        r = _modal(["volume", "put", "--force", VOLUME, str(p), remote], key)
        (done if r.returncode == 0 else failed).append(remote)
        print(f"  {'bien' if r.returncode == 0 else 'FALLO'} {remote}"
              + ("" if r.returncode == 0 else f": {(r.stdout + r.stderr).strip()[-300:]}"), flush=True)
    res = {"fecha": time.strftime("%Y-%m-%dT%H:%M:%S"), "pc_tag": a.pc_tag, "gb": round(total / 1e9, 2),
           "minutos": round((time.time() - t0) / 60, 1), "subidos": done, "fallidos": failed}
    cd = out / "capturas_diag"                     # goes to pc-logs with the rest of the diagnoses
    cd.mkdir(parents=True, exist_ok=True)
    (cd / "subir_nube.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Subido en {res['minutos']} min: {len(done)} bien, {len(failed)} con fallo")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
