"""Proof of concept P0.5e-D (21-11, #301; the user: «sí»): the PC's application with the cloud's real results, checked
without the PC. The results are brought as the PC brings them (tennisbio.app.p0_nube.pull, by cloud/kaggle/correr.py),
the page is made as the window makes it (p0_ventana.build_data), and a real browser opens it (Google Chrome, which plays
the H.264 of the strokes' windows as the PC's WebView2 does): stroke by stroke, the panel's video must open and its
body layer must be drawn on her points at the impact (their pixels on the layers' canvas). Only numbers leave the
session (the repository and nube-logs are public: no frame of the player).

Rule written before measuring: accepted if, of the strokes probed (the gallery's first ones, up to --golpes), at least
95 % open their video and at least 95 % of those draw the body on her points, with no error of the page. 21-11 (the strobe
image from each stroke's series, ui/src/pantallas/Estroboscopica.tsx), rule written before measuring it: at least 95 % of
the strokes with their video draw it (its silhouettes on her impact frame); its racket points are counted, not required
(the racket model does not see the racket in every frame).

    python -m tennisbio.infra.poc_app --raiz <dir with nube/> --salida poc.json [--golpes 24]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

MIN_SHARE = 0.95

# in the page: the panel's state, its video, and the canvas' alpha at three points of her impact frame (the shoulders'
# and the hips' middles, the dominant forearm's middle), where the body layer draws its lines
PROBE = """() => {
  const R = document.querySelector('[data-reproductor]'), V = R && R.querySelector('video'),
        C = R && R.querySelector('canvas[data-capas]');
  const E = document.querySelector('[data-estrobo]');
  const out = {estado: R ? R.dataset.reproductor : null, ancho: V ? V.videoWidth : 0, listo: V ? V.readyState : 0,
               error: V && V.error ? String(V.error.code) : null, dibujados: 0, puntos: 0,
               estrobo: E ? E.dataset.estrobo : null, estrobo_siluetas: E ? +(E.dataset.siluetas || 0) : 0,
               estrobo_puntos: E ? +(E.dataset.puntos || 0) : 0};
  const S = window.SERIES || {}, id = R ? R.dataset.golpe : null;
  const ser = id ? S[id] : null;
  if (!ser || !C || !C.width) return out;
  const k = ser.kp[ser.impact - ser.first]; if (!k) return out;
  const p = i => (k[2 * i] === null ? null : [k[2 * i], k[2 * i + 1]]);
  const mid = (a, b) => (a && b ? [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] : null);
  const cx = C.getContext('2d');
  for (const q of [mid(p(5), p(6)), mid(p(11), p(12)), mid(p(8), p(10))]) {
    if (!q) continue;
    out.puntos++;
    let hit = 0;
    for (let dx = -2; dx <= 2 && !hit; dx++) for (let dy = -2; dy <= 2 && !hit; dy++)
      if (cx.getImageData(Math.round(q[0]) + dx, Math.round(q[1]) + dy, 1, 1).data[3] > 0) hit = 1;
    out.dibujados += hit;
  }
  return out;
}"""


def make_page(root: Path) -> tuple[Path, dict]:
    """The application's page with the results brought under root/nube, as the PC's window makes it."""
    from ..app import p0_app, p0_ventana

    page_dir = root / "aplicacion_nueva"
    d, src = p0_ventana.build_data(root, None, page_dir / "datos", root / "nube", page_dir)
    page = page_dir / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(p0_app.pagina(d), encoding="utf-8")
    return page, {"origen": src, "golpes_con_video": sum(1 for s in d.get("strokes") or [] if s.get("video")),
                  "golpes": len(d.get("strokes") or []), "medios": d.get("medios")}


def probe(page: Path, n: int, channel: str = "chrome") -> dict:
    from playwright.sync_api import sync_playwright

    rows, errors = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
        p = b.new_page(viewport={"width": 1440, "height": 900})
        p.on("pageerror", lambda e: errors.append(str(e)[:200]))
        p.goto(page.as_uri() + "#visor")
        p.wait_for_timeout(800)
        p.click('[data-tab="golpes"]')
        p.wait_for_timeout(300)
        ids = p.evaluate("() => [...document.querySelectorAll('[data-stroke]')].map(x => x.dataset.stroke)")[:n]
        for sid in ids:
            p.click(f'[data-stroke="{sid}"]')
            t0 = time.time()
            try:
                p.wait_for_function("() => { const R = document.querySelector('[data-reproductor]');"
                                    " return R && R.dataset.reproductor !== 'cargando' &&"
                                    " (R.dataset.reproductor === 'sin-video' || R.querySelector('video').readyState >= 2"
                                    " || R.querySelector('video').error); }", timeout=15000)
                try:                                  # the strobe image draws once its own video is at the impact
                    p.wait_for_function("() => { const E = document.querySelector('[data-estrobo]');"
                                        " return !E || E.dataset.estrobo !== 'cargando' && +(E.dataset.siluetas || 0) > 0"
                                        " || E.dataset.estrobo === 'sin-serie'; }", timeout=8000)
                except Exception:  # esperado: counted below as a strobe not drawn (noqa: BLE001)
                    pass
                if p.query_selector("[data-impacto]:not([disabled])"):
                    p.click("[data-impacto]")
                    p.wait_for_timeout(500)
                r = p.evaluate(PROBE)
            except Exception as e:  # esperado: a stroke whose panel never got ready is counted as such (noqa: BLE001)
                r = {"estado": "no se abrió", "error": f"{type(e).__name__}: {str(e)[:120]}"}
            r.update(id=sid, s=round(time.time() - t0, 1))
            rows.append(r)
            p.keyboard.press("Escape")
            p.wait_for_timeout(200)
        b.close()
    return {"filas": rows, "errores_pagina": errors[:20]}


def summarise(rows: list[dict], errors: list[str]) -> dict:
    with_video = [r for r in rows if (r.get("ancho") or 0) > 0 and not r.get("error")]
    drawn = [r for r in with_video if r.get("puntos") and r.get("dibujados", 0) * 3 >= 2 * r["puntos"]]
    v_share = len(with_video) / len(rows) if rows else 0.0
    d_share = len(drawn) / len(with_video) if with_video else 0.0
    strobe = [r for r in with_video if r.get("estrobo") == "listo" and (r.get("estrobo_siluetas") or 0) > 0]
    s_share = len(strobe) / len(with_video) if with_video else 0.0
    ok = bool(rows) and v_share >= MIN_SHARE and d_share >= MIN_SHARE and s_share >= MIN_SHARE and not errors
    tips = [r.get("estrobo_puntos") or 0 for r in strobe]
    return {"probados": len(rows), "con_video": len(with_video), "cuerpo_en_sus_puntos": len(drawn),
            "parte_con_video": round(v_share, 3), "parte_dibujada": round(d_share, 3), "errores_pagina": len(errors),
            "estroboscopica": len(strobe), "parte_estroboscopica": round(s_share, 3),
            "estroboscopica_con_raqueta": sum(1 for t in tips if t > 0),
            "puntos_raqueta_mediana": sorted(tips)[len(tips) // 2] if tips else None,
            "regla": {"pasa": ok, "motivo": f"vídeo {v_share:.0%}, cuerpo en sus puntos {d_share:.0%} y estroboscópica "
                                            f"{s_share:.0%} (mínimo {MIN_SHARE:.0%} cada uno), {len(errors)} errores de la página"}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=Path, required=True, help="carpeta con nube/ (los resultados traídos)")
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--golpes", type=int, default=24)
    ap.add_argument("--canal", default="chrome", help="chrome (H.264, como WebView2) o vacío (Chromium)")
    a = ap.parse_args(argv)
    page, info = make_page(a.raiz)
    res = probe(page, a.golpes, a.canal)
    out = {"prueba": "app", **info, **summarise(res["filas"], res["errores_pagina"]),
           "filas": [{k: r.get(k) for k in ("estado", "ancho", "puntos", "dibujados", "estrobo", "estrobo_siluetas",
                                            "estrobo_puntos", "error", "s")} for r in res["filas"]],
           "errores": res["errores_pagina"]}
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("filas",)}, ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
