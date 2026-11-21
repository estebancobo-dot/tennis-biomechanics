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
    got = 0
    for i, rel in enumerate(todo, 1):
        data = store.read_bytes(f"/output/{rel}")
        if data is None:
            return {"ok": False, "motivo": f"no se pudo bajar {rel} ({i - 1} de {len(todo)} bajados)",
                    "bajados": i - 1}
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(f)
        got += len(data)
        if i % 50 == 0:
            log(f"resultados de la nube: {i} de {len(todo)} ficheros")
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
