"""The window checked as the user would see it, with the real index (the same check in the tests and on the
PC): every screen and every match and player page painted in a real browser at 1280 × 900 and on a phone,
no page error, no sideways scroll, nothing empty; a screenshot of each; and whether this PC can open the
window at all (pywebview importable, WebView2 runtime present). Nothing is changed: the page is read-only."""
import json
import sys
from pathlib import Path

from . import window

SCREENS = ["inicio", "analisis", "partidos", "jugadoras", "cola", "calidad", "almacenamiento", "ajustes"]


def window_engine() -> dict:
    """Can this PC open the window? pywebview, and on Windows the WebView2 runtime (part of Windows 11)."""
    out = {"pywebview": False, "webview2": None}
    try:
        import webview  # noqa: F401
        out["pywebview"] = True
    except Exception as e:                       # noqa: BLE001
        out["pywebview_error"] = f"{type(e).__name__}: {e}"[:200]
    try:
        import pystray
        pystray.Icon("tennisbio-comprobacion", window.tray_image(), "Tennisbio")      # built, never shown
        out["bandeja"] = True
    except Exception as e:                       # noqa: BLE001
        out["bandeja"] = f"{type(e).__name__}: {e}"[:200]
    if sys.platform == "win32":
        from . import notify
        out["avisos"] = notify.can_show()
        import winreg
        key = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, key.replace("WOW6432Node\\", "") if root == winreg.HKEY_CURRENT_USER else key) as k:
                    out["webview2"] = winreg.QueryValueEx(k, "pv")[0]
                    break
            except OSError:
                continue
    return out


def live_window(app, dest: Path, timeout_s: float = 120.0) -> dict:
    """The real window, minimized and without focus (a few seconds in the taskbar at most): WebView2 opens the
    page, the page finds the bridge, and a call through it comes back with the index. It runs in a separate
    process killed after `timeout_s`: a window engine that never answers can never hang the PC's cycle (it did
    on 18-10: a hidden WebView2 window never loaded and pywebview waits for JavaScript without a limit)."""
    import subprocess
    page = window.write_page(app, dest / "tennisbio_viva.html", with_storage=False)
    res_f = dest / "ventana_viva.json"
    res_f.unlink(missing_ok=True)
    try:
        subprocess.run([sys.executable, "-m", "tennisbio.app.check", "--viva", str(page), str(res_f)], timeout=timeout_s,
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    try:
        out = json.loads(res_f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out = {"opened": False, "ready": False, "bridge": None}
    if timed_out:
        out["error"] = f"sin respuesta en {timeout_s:.0f} s: se cerró a la fuerza (lo último: {out.get('step', 'arrancando')})"
    return out


def _live_child(page: str, res_f: str, wait_s: float = 60.0):
    """In its own process (see live_window): writes how far it got after each step."""
    import threading
    out: dict = {"opened": False, "ready": False, "bridge": None, "step": "importar pywebview"}
    save = lambda: Path(res_f).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    save()
    import webview

    from ..config import load_config
    from .core import App
    app = App(load_config())
    api = window.Api(app)
    loaded = threading.Event()
    w = webview.create_window("Tennisbio (comprobación)", url=str(page), js_api=api, width=480, height=320,
                              minimized=True, focus=False)
    api.window = w
    w.events.loaded += lambda *a: loaded.set()

    def probe():
        out.update(opened=True, step="cargar la página")
        save()
        try:
            if loaded.wait(wait_s):
                out["step"] = "esperar al puente"
                save()
                out["ready"] = bool(w.evaluate_js("window.__tbReady === true && !!(window.pywebview && window.pywebview.api)"))
                if out["ready"]:
                    out["step"] = "llamar al núcleo"
                    save()
                    out["bridge"] = w.evaluate_js(
                        "window.pywebview.api.state().then(function (s) { return s.version + ' · ' + s.matches.length + ' partidos'; })")
            out["step"] = "hecho"
        except Exception as e:                   # noqa: BLE001
            out["error"] = f"{type(e).__name__}: {e}"[:300]
        save()
        w.destroy()
    out["step"] = "abrir la ventana"
    save()
    webview.start(probe)
    save()


def check(app, dest: Path, shots: bool = True, real: bool = False) -> dict:
    """Paints every screen; returns {"problems": [...], "screens": n, "engine": {...}} and writes
    dest/ventana.json, dest/ventana.md and the screenshots."""
    from playwright.sync_api import sync_playwright

    from ..screens import _browser
    dest.mkdir(parents=True, exist_ok=True)
    page = window.write_page(app, dest / "tennisbio.html")
    st = json.loads(page.read_text(encoding="utf-8").split('<script id="tb-state" type="application/json">')[1].split("</script>")[0])
    targets = SCREENS + [f"partido/{m['id']}" for m in st["matches"]] + [f"jugadora/{p['id']}" for p in st["players"]]
    problems, seen = [], 0
    with sync_playwright() as p:
        b = _browser(p)
        for w, h in ((1280, 900), (390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.on("pageerror", lambda e, w=w: problems.append(f"{w}: error de página: {e}"))
            pg.goto(page.resolve().as_uri())
            pg.wait_for_function("window.__tbReady === true", timeout=15000)
            for t in targets:
                pg.evaluate(f"location.hash = {json.dumps('#' + t)}")
                pg.wait_for_timeout(120)
                txt = pg.inner_text(".screen.on") if pg.query_selector(".screen.on") else ""
                if not txt.strip():
                    problems.append(f"{w}: «{t}» vacía")
                over = pg.evaluate("""() => document.documentElement.scrollWidth > innerWidth + 1
                    ? [...document.querySelectorAll('.screen.on *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1)
                        .slice(0, 3).map(e => e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : '')) : null""")
                if over is not None:
                    problems.append(f"{w}: «{t}» se sale por el lado ({', '.join(over)})")
                seen += 1
                if shots and w == 1280 and "/" not in t:
                    pg.screenshot(path=str(dest / f"app_{t}.png"), full_page=True)
        b.close()
    live = live_window(app, dest) if real else None
    if real:
        from . import backup
        try:
            bk = backup.plan(app, dest / "copia_prueba")
            res_backup = {"ficheros": bk["files"], "bytes": bk["bytes"]}
        except Exception as e:                   # noqa: BLE001
            res_backup = {"error": f"{type(e).__name__}: {e}"[:200]}
            problems.append(f"la copia a USB no sabe qué copiar: {res_backup['error']}")
    else:
        res_backup = None
    if live is not None and not (live.get("ready") and live.get("bridge")):
        problems.append(f"la ventana real no funcionó: {live}")
    res = {"problems": problems, "screens": seen, "engine": window_engine(), "live": live, "backup": res_backup,
           "index": {"matches": len(st["matches"]), "players": len(st["players"]), "analyses": len(st["analyses"]),
                     "jobs_pending": len(st["queue"]["pending"]), "notices": len(st["notices"])}}
    (dest / "ventana.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    eng = res["engine"]
    md = [f"# Ventana de Tennisbio: {'OK' if not problems else 'FALLOS'}", "",
          f"{seen} pantallas pintadas (1280 y móvil) · {len(problems)} problemas", "",
          f"- Índice: {res['index']}",
          f"- Motor de la ventana: pywebview {'sí' if eng['pywebview'] else 'NO (' + eng.get('pywebview_error', '') + ')'}"
          + (f" · WebView2 {eng['webview2'] or 'NO encontrado'}" if sys.platform == "win32" else ""),
          f"- Ventana real (oculta): {live}" if live is not None else "- Ventana real: no probada aquí",
          f"- Icono junto al reloj: {eng.get('bandeja')} · avisos de Windows: {eng.get('avisos', 'no es Windows')}",
          f"- Copia a USB (lo que copiaría ahora): {res_backup}" if res_backup is not None else "", ""]
    md += [f"- ✘ {x}" for x in problems]
    (dest / "ventana.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return res


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--viva":
    _live_child(sys.argv[2], sys.argv[3])
