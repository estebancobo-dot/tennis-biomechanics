"""P0.5e (21-11, #301; the user: «sí»): the cloud's results for the PC's application. The report and the audit are made
in the cloud (a Kaggle CPU session or Modal: cloud/kaggle/correr.report), which leaves beside them the list of their
files with their sizes (MANIFEST); the application brings to the PC only what changed, through the storage port (the
Modal volume's adapter given by scripts/aplicacion_nueva.py; the core never imports the cloud's code), and shows them.

    pull(store, <output>/nube)   →   <output>/nube/informe_derecha/…, <output>/nube/auditoria/auditoria.json
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

MANIFEST = "/output/resultados_app.json"      # cloud/kaggle/correr.py APP_MANIFEST (tests/test_p0_nube.py keeps them equal)
LOCAL = "resultados_app.json"
WORKERS = 8                                   # files brought at once


def _safe(rel: str) -> bool:
    """A path of the list inside the results' folder: relative, without «..» (the list comes from the volume)."""
    p = PurePosixPath(rel)
    return bool(rel) and not p.is_absolute() and ".." not in p.parts and "\\" not in rel and ":" not in rel


def pull(store, dest: Path, log=print) -> dict:
    """The cloud's latest results into dest: only the files missing or of another size; each one written whole before
    it replaces the old (never half a video for the window). {ok, motivo | bajados, mb, generado, partidos}."""
    man = store.read_json(MANIFEST)
    if not isinstance(man, dict) or not isinstance(man.get("ficheros"), dict):
        return {"ok": False, "motivo": "la nube aún no tiene resultados para la aplicación (falta su informe)"}
    files = {k: int(v) for k, v in man["ficheros"].items() if _safe(str(k))}
    if len(files) != len(man["ficheros"]):
        return {"ok": False, "motivo": "la lista de resultados de la nube tiene rutas no válidas: no se baja nada"}
    todo = [k for k, size in sorted(files.items()) if not (dest / k).is_file() or (dest / k).stat().st_size != size]

    def one(rel: str) -> int | None:
        data = store.read_bytes(f"/output/{rel}")
        if data is None:
            return None
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(f)
        return len(data)

    # 21-11: one file after another waited ~0.7 s each for the cloud (1759 files, 22 min the first time): WORKERS at once
    from concurrent.futures import ThreadPoolExecutor
    got, done, missing = 0, 0, []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for rel, n in zip(todo, pool.map(one, todo)):
            if n is None:
                missing.append(rel)
                continue
            got, done = got + n, done + 1
            if done % 50 == 0:
                log(f"resultados de la nube: {done} de {len(todo)} ficheros")
    if missing:
        return {"ok": False, "motivo": f"no se pudo bajar {missing[0]} ({done} de {len(todo)} bajados; se sigue la próxima "
                                       "vez por lo que falta)", "bajados": done}
    dest.mkdir(parents=True, exist_ok=True)
    (dest / LOCAL).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "bajados": len(todo), "mb": round(got / 2 ** 20, 1), "generado": str(man.get("generado", "")),
            "partidos": list(man.get("partidos") or [])}


def local_results(dest: Path) -> tuple[Path, Path, dict] | None:
    """The report page, the audit and the list of what was brought, when the cloud's results are on the PC."""
    man_f = dest / LOCAL
    if not man_f.exists():
        return None
    try:
        man = json.loads(man_f.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # esperado: a list cut or unreadable: the results are not taken as there (brought again)
        return None
    pages = sorted(p for p in dest.glob("informe*/index.html"))
    audit = dest / "auditoria" / "auditoria.json"
    if not pages or not audit.exists():
        return None
    main = next((p for p in pages if p.parent.name == "informe_derecha"), pages[0])
    return main, audit, man


def exports(dest: Path) -> list[dict]:
    """21-11 (P0.5e): what the cloud exported with the report (cloud/kaggle/correr.py, `tennisbio export`) and the PC
    brought: the short PDF, the conclusions' montages and the strokes' MP4s, each with its path inside dest (what
    open_result opens) and its size."""
    out = []
    for d in sorted(p for p in dest.glob("exportar*") if p.is_dir()):
        try:                                 # the export's end record: each montage's own title (tennisbio.export)
            titles = json.loads((d / "exportacion.json").read_text(encoding="utf-8")).get("titles") or {}
        except (OSError, ValueError, AttributeError):  # esperado: an older export without it: the file's name is shown
            titles = {}
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in (".pdf", ".mp4"):
                continue
            kind = "pdf" if f.suffix.lower() == ".pdf" else "montaje" if f.parent.name == "montajes" else "golpe"
            out.append({"nombre": f.name, "tipo": kind, "ruta": f.relative_to(dest).as_posix(),
                        "mb": round(f.stat().st_size / 2 ** 20, 1), **({"titulo": str(titles[f.name])}
                                                                        if kind == "montaje" and f.name in titles else {})})
    return out


def disk(dest: Path, base: Path) -> dict:
    """21-11 (P0.5e): the room on the PC's disk and what the cloud's results take there."""
    import shutil
    used = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) if dest.exists() else 0
    probe = base if base.exists() else Path(base.anchor or ".")
    free = shutil.disk_usage(probe).free
    return {"libre_gb": round(free / 1e9, 1), "resultados_gb": round(used / 1e9, 2), "poco": free < LOW_DISK_GB * 1e9}


LOW_DISK_GB = 10                              # under this, the application warns (Ajustes and Inicio)


def open_result(dest: Path, rel: str, opener=None) -> dict:
    """A file or folder of the results brought (dest) opened with the PC's own program (the PDF reader, the video
    player, the file explorer). Only inside dest: the path comes from the page."""
    import os
    import sys
    if not _safe(rel):
        return {"ok": False, "motivo": "ruta no válida"}
    f = (dest / rel).resolve()
    if not f.is_relative_to(dest.resolve()) or not f.exists():
        return {"ok": False, "motivo": f"no está en el PC: {rel} («Traer resultados de la nube» en Inicio)"}
    if opener is None:
        if sys.platform == "win32":
            opener = os.startfile          # noqa: S606 — the user's own file, with its own program
        else:
            import webbrowser
            opener = lambda p: webbrowser.open(Path(p).as_uri())    # noqa: E731
    opener(str(f))
    return {"ok": True}
