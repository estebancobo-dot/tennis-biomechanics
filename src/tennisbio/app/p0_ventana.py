"""P0.5e (15-11): the new application in a window of the PC (pywebview over WebView2, as the current one), with its
management connected to the cloud's queue through the storage port: the script outside the package gives the Modal
volume's adapter (cloud/almacen.py), as the core never imports the cloud's code.

    6_aplicacion_nueva.bat  →  scripts/windows/aplicacion_nueva.ps1  →  scripts/aplicacion_nueva.py  →  main(store)

What it shows: the PC's latest report and audit (<output>/informe/index.html, <output>/auditoria/auditoria.json),
read as the validated mockup reads them (p0_app.datos_beta), with the queue's state and its answer to the application
from the volume (/cola/); without a report, the made-up example, said on screen. What it does: each management action is
a request on the volume (p0_api.Gestion), with the key 5_conectar_nube.bat saved (<base>\\secretos\\modal.env); without
it, every action says so instead of failing. The page goes to a file next to the outputs (WebView2 refuses pages of more
than 2 MB given as text).
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def cloud_matches(store) -> list[dict]:
    """The cloud's list of matches (the PC's and the application's) with whether each one's analysis reached the fine
    pass, as the queue reads it (cola.matches_on_volume)."""
    pc = store.read_json("/pc/registro_partidos.json") or []
    app = store.read_json("/app/registro_partidos.json") or []
    have = {str(m.get("id")) for m in pc}
    out = []
    for m in list(pc) + [m for m in app if str(m.get("id")) not in have]:
        man = store.read_json(f"/output/{m['id']}/manifest.json") or {}
        out.append({"id": str(m["id"]), "rival": str(m.get("rival") or ""), "analizado": "fine" in man})
    return out


def build_data(out_root: Path, store, work: Path, cloud_dir: Path | None = None) -> tuple[dict, str]:
    """The page's data and where they come from: the cloud's results brought to the PC (cloud_dir, P0.5e: the analysis
    lives in the cloud, #301), else the PC's latest report and audit, else the made-up example (said on screen)."""
    from . import p0_app, p0_nube
    cloud = p0_nube.local_results(cloud_dir) if cloud_dir else None
    report = cloud[0] if cloud else out_root / "informe" / "index.html"
    audit = cloud[1] if cloud else next((p for p in (out_root / "auditoria" / "auditoria.json",
                                                     out_root / "auditoria_partidos.json") if p.exists()), None)
    estado = (store.read_bytes("/cola/estado.md") if store else None) or b""
    matches = cloud_matches(store) if store else []
    if report.exists() and audit is not None:
        work.mkdir(parents=True, exist_ok=True)
        (work / "estado.md").write_bytes(estado)
        (work / "partidos.json").write_text(json.dumps(matches, ensure_ascii=False), encoding="utf-8")
        try:
            d = p0_app.datos_beta(report, audit, work / "estado.md", work / "partidos.json")
            src = (f"el informe de la nube (hecho el {cloud[2].get('generado') or '?'})" if cloud else
                   f"el informe del PC ({time.strftime('%d-%m %H:%M', time.localtime(report.stat().st_mtime))})")
        except Exception as e:  # esperado: a report the builder cannot read: the example, said on screen and logged
            where = "de la nube" if cloud else "del PC"
            log(f"no se pudo leer el informe {where}: {type(e).__name__}: {e}")
            d, src = p0_app.ejemplo(), f"ejemplo (el informe {where} no se pudo leer: {type(e).__name__})"
    else:
        d, src = p0_app.ejemplo(), "ejemplo (no hay informe ni auditoría, ni de la nube ni del PC)"
    d["origen"] = src
    if store:
        d.setdefault("queue", {})["app"] = store.read_json("/cola/app.json")
    return d, src


def output_root() -> Path:
    from ..config import load_config
    return Path((load_config().get("paths") or {}).get("output", "output"))


def main(store=None, why: str = "sin la nube", out_root: Path | None = None) -> int:
    """The window. `store`: the cloud's storage (the Modal volume's adapter, given by scripts/aplicacion_nueva.py), or
    None with `why` (every management button says it)."""
    from . import p0_api, p0_app

    from . import p0_nube

    out_root = out_root or output_root()
    work, cloud_dir = out_root / "aplicacion_nueva", out_root / "nube"
    page = (work / "index.html").resolve()
    log(f"nube: {'conectada' if store else why}")

    def make_page() -> dict:
        d, src = build_data(out_root, store, work / "datos", cloud_dir)
        log(f"datos: {src}")
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(p0_app.pagina(d), encoding="utf-8")
        log(f"página: {page} ({page.stat().st_size / 1e6:.1f} MB)")
        return d

    def pull() -> dict:
        try:
            r = p0_nube.pull(store, cloud_dir, log)
        except Exception as e:  # esperado: no connection or a refused read: said in the window and logged
            r = {"ok": False, "motivo": f"no se pudo hablar con la nube: {type(e).__name__}: {e}"}
        log(f"resultados de la nube: {r}")
        return r

    def traer() -> dict:                 # the button «Traer resultados de la nube»
        r = pull()
        if r.get("ok") and r.get("bajados"):
            make_page()
            r["recargar"] = True
        return r

    if store:                            # on opening, the latest results first
        pull()
    datos = make_page()
    try:
        import webview
    except ImportError:  # esperado: without the window engine, the page opens in the browser (read-only)
        import webbrowser
        log("sin pywebview: se abre en el navegador, solo para mirar")
        webbrowser.open(page.as_uri())
        return 0
    holder: dict = {}

    def choose():
        r = holder["w"].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False,
                                           file_types=("Vídeos (*.mp4;*.mkv;*.ts;*.mov;*.avi;*.webm)",
                                                       "Todos los ficheros (*.*)"))
        return str(r[0]) if r else None

    api = p0_api.ApiVentana(p0_api.Gestion(store, work / "subida"), datos["player"]["name"], choose, traer) if store \
        else p0_api.SinNube(why)
    try:
        holder["w"] = webview.create_window("TennisBio (nueva)", url=str(page), js_api=api, width=1440, height=900,
                                            min_size=(1000, 650))
        log("ventana abierta")
        webview.start()
    except Exception as e:  # esperado: no window engine (WebView2): the page in the browser, read-only, logged
        import webbrowser
        log(f"la ventana no se pudo abrir ({type(e).__name__}: {e}); se abre en el navegador, solo para mirar")
        webbrowser.open(page.as_uri())
        return 1
    log("ventana cerrada")
    return 0


if __name__ == "__main__":                 # without the cloud (the script scripts/aplicacion_nueva.py connects it)
    raise SystemExit(main())
