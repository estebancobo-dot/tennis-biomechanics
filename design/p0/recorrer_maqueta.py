"""#305 (15-11): walks every screen of the built mockup (design/p0/build_app.py) in a real browser and keeps what each one
shows: its visible text, the JavaScript errors and whether the page overflows sideways, at the desktop widths the
application is made for (#301: 1920, 1280 and 1024 px) and at a phone's (390 px, only so the review can be read on
a phone). design/p0/validar_maqueta.py checks every requirement against this.

    uv run python design/p0/recorrer_maqueta.py <built mockup .html> <out .json>

The built mockup holds real data: it and its walk stay outside the repository (it is public).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MANAGEMENT = ("inicio", "analisis", "partidos", "personas", "cola", "calidad", "almacen", "ajustes")
MORE = ("comparar", "conclusiones", "situaciones", "pista", "tabla", "lateral", "fiabilidad", "datos", "exportar")
OPTIONAL_MORE = ("tactica", "medidas")        # P0.5c (design changes 2 and 1)
WIDTHS = ((1920, 1080), (1280, 800), (1024, 768), (390, 844))


def walk(html: str, width: int, height: int) -> dict:
    from playwright.sync_api import sync_playwright

    out = {"estados": {}, "a_la_vista": {}, "errores": [], "desborde": {}, "medios": {}}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page(viewport={"width": width, "height": height})
        p.on("pageerror", lambda e: out["errores"].append(str(e)))
        p.on("console", lambda m: out["errores"].append("console: " + m.text) if m.type == "error" else None)
        p.set_content('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
                      'content="width=device-width,initial-scale=1"></head><body>' + html + "</body></html>",
                      wait_until="load")

        def keep(name: str):
            o = p.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            if o > 0:
                out["desborde"][name] = o
            # real media on the screen (a video or a drawn canvas), not a marked placeholder
            out["medios"][name] = p.evaluate("() => document.querySelectorAll('video, canvas').length")
            # what is on screen as it opens, and what is one click away (every collapsed section opened)
            out["a_la_vista"][name] = p.evaluate("() => document.body.innerText")
            out["estados"][name] = p.evaluate(
                "() => { const c = [...document.querySelectorAll('details:not([open])')]; c.forEach(d => d.open = true);"
                " const t = document.body.innerText; c.forEach(d => d.open = false); return t; }")

        def click(sel: str) -> bool:
            loc = p.locator(sel)
            if loc.count() == 0:
                out["errores"].append(f"no está: {sel}")
                return False
            loc.first.click()
            p.wait_for_timeout(120)
            return True

        def close():
            p.keyboard.press("Escape")
            p.wait_for_timeout(80)

        for s in MANAGEMENT:
            p.evaluate(f"() => location.hash = '{s}'")
            p.wait_for_timeout(150)
            keep(s)
        p.evaluate("() => location.hash = 'partidos'")
        p.wait_for_timeout(120)
        if click("[data-match]"):
            keep("partido_ficha")
            close()
        if click("[data-add]"):
            keep("anadir_1")
            for k in range(2, 6):
                if p.locator('[data-step="1"]').count():
                    click('[data-step="1"]')
                    keep(f"anadir_{k}")
            close()
        p.evaluate("() => location.hash = 'visor'")
        p.wait_for_timeout(200)
        n = p.locator(".strip [data-ph]").count()
        for i in range(n):
            click(f'.strip [data-ph="{i}"]')
            keep(f"leccion_fase_{i}")
        if click('[data-tab="golpes"]'):
            keep("golpes")
            if click("[data-stroke]"):
                keep("golpe")
                close()
        if click('[data-tab="mas"]'):
            for sb in MORE:
                if click(f'[data-sub="{sb}"]'):
                    keep(f"mas_{sb}")
            for sb in OPTIONAL_MORE:                  # sections the mockup did not have (no error when absent)
                if p.locator(f'[data-sub="{sb}"]').count():
                    click(f'[data-sub="{sb}"]')
                    keep(f"mas_{sb}")
            if click('[data-sub="situaciones"]') and click("[data-cell]"):
                keep("situacion_celda")
        b.close()
    return out


def main(argv: list[str]) -> int:
    html = Path(argv[1]).read_text(encoding="utf-8")
    res = {f"{w}": walk(html, w, h) for w, h in WIDTHS}
    Path(argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for w, r in res.items():
        print(w, "px:", len(r["estados"]), "pantallas;", len(r["errores"]), "errores;", len(r["desborde"]), "con desborde")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
