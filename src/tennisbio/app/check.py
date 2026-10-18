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
    if sys.platform == "win32":
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


def live_window(app, dest: Path, timeout_s: float = 60.0) -> dict:
    """The real window, hidden (the user sees nothing): WebView2 opens the page, the page finds the bridge, and
    a call through it comes back with the index (the version and the number of matches). Then it closes."""
    import threading
    import time
    out: dict = {"opened": False, "ready": False, "bridge": None}
    try:
        import webview
    except Exception as e:                       # noqa: BLE001
        return {**out, "error": f"pywebview: {type(e).__name__}: {e}"[:200]}
    page = window.write_page(app, dest / "tennisbio_viva.html", with_storage=False)
    api = window.Api(app)
    w = webview.create_window("Tennisbio (comprobación)", url=str(page), js_api=api, hidden=True)
    api.window = w

    def probe():
        t0 = time.time()
        try:
            out["opened"] = True
            while time.time() - t0 < timeout_s and not out["ready"]:
                out["ready"] = bool(w.evaluate_js("window.__tbReady === true && !!(window.pywebview && window.pywebview.api)"))
                time.sleep(0.5)
            if out["ready"]:
                out["bridge"] = w.evaluate_js("window.pywebview.api.state().then(function (s) { return s.version + ' · ' + s.matches.length + ' partidos'; })")
        except Exception as e:                   # noqa: BLE001
            out["error"] = f"{type(e).__name__}: {e}"[:300]
        finally:
            out["seconds"] = round(time.time() - t0, 1)
            w.destroy()
    guard = threading.Timer(timeout_s + 30, lambda: w.destroy())
    guard.daemon = True
    guard.start()
    try:
        webview.start(probe)
    except Exception as e:                       # noqa: BLE001 — no WebView2, no desktop session…
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    guard.cancel()
    return out


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
    if live is not None and not (live.get("ready") and live.get("bridge")):
        problems.append(f"la ventana real no funcionó: {live}")
    res = {"problems": problems, "screens": seen, "engine": window_engine(), "live": live,
           "index": {"matches": len(st["matches"]), "players": len(st["players"]), "analyses": len(st["analyses"]),
                     "jobs_pending": len(st["queue"]["pending"]), "notices": len(st["notices"])}}
    (dest / "ventana.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    eng = res["engine"]
    md = [f"# Ventana de Tennisbio: {'OK' if not problems else 'FALLOS'}", "",
          f"{seen} pantallas pintadas (1280 y móvil) · {len(problems)} problemas", "",
          f"- Índice: {res['index']}",
          f"- Motor de la ventana: pywebview {'sí' if eng['pywebview'] else 'NO (' + eng.get('pywebview_error', '') + ')'}"
          + (f" · WebView2 {eng['webview2'] or 'NO encontrado'}" if sys.platform == "win32" else ""),
          f"- Ventana real (oculta): {live}" if live is not None else "- Ventana real: no probada aquí", ""]
    md += [f"- ✘ {x}" for x in problems]
    (dest / "ventana.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return res
