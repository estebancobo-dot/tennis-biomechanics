"""Screenshots of the report as the user sees it, for the audit (tennisbio.audit) and for Claude:
the report is opened in a real browser already installed (Brave on the user's PC; nothing is
downloaded),
each screen is shown in turn and photographed, and what the page says is written down: its text,
its videos (loaded or not), its charts, its "no data" messages and every error of the page.

Needs the `playwright` package (extra `validation`) to drive that browser."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TABS = ["modelo", "panel", "videoteca", "golpe", "comparar", "explorador", "comparativas", "pista"]
_JS_SCREEN = """(tab) => {
  const sec = document.getElementById('tab-' + tab);
  if (!sec) return null;
  const vids = [...document.querySelectorAll('video')].filter(v => v.getAttribute('src'));
  return {
    title: (document.querySelector(`.nav button[data-tab="${tab}"]`) || {}).innerText || tab,
    text_chars: (sec.innerText || '').trim().length,
    charts: sec.querySelectorAll('svg[role="img"], canvas').length,
    // the stroke screen draws its video on a canvas from a video element kept off the page
    videos: vids.filter(v => v.readyState >= 2).length + (tab === 'golpe' && typeof video !== 'undefined' && video.readyState >= 2 ? 1 : 0),
    // canvases left black (a phase image, a stroke frame that was never drawn)
    black_canvases: [...sec.querySelectorAll('canvas')].filter(c => c.offsetParent && c.width > 50).filter(c => {
      try { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let m = 0;
            for (let i = 0; i < d.length; i += 4 * 97) m = Math.max(m, d[i] + d[i + 1] + d[i + 2]); return m < 30; }
      catch (e) { return false; } }).length,
    videos_failed: vids.filter(v => v.error).map(v => v.getAttribute('src')).slice(0, 5),
    empty_msgs: [...sec.querySelectorAll('.empty')].filter(e => e.offsetParent).map(e => e.innerText.trim()).slice(0, 8),
    dashes: ((sec.innerText || '').match(/—/g) || []).length,
    // human sense: an opening sentence, no links to outside sources, no visible chart with many lines
    // the per-stroke views and filters asked for (they work from the first stroke)
    ball_moments: sec.querySelectorAll('#bm button').length,
    heights_layer: !!sec.querySelector('#layers button[data-v="heights"]'),
    lib_filters: sec.querySelectorAll('#lib-chips button').length,
    news: !!sec.querySelector('#news'),
    intro: !!(sec.querySelector('.intro') && sec.querySelector('.intro').innerText.trim().length > 20),
    external_links: [...sec.querySelectorAll('a[href^="http"]')].filter(a => a.offsetParent).length,
    many_lines: [...sec.querySelectorAll('svg')].filter(g => g.offsetParent && g.querySelectorAll('polyline').length > 4).length,
  };
}"""


def _browser(p):
    """A browser already installed, never downloaded: Brave (the user's), else Edge or Chrome if they
    are there; on Linux, the machine's Chromium."""
    kw = {"args": ["--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required"]}
    exes = [os.environ.get("TENNISBIO_BROWSER", "")]
    if sys.platform == "win32":
        bases = [os.environ.get(v, "") for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        for rel in (("BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                    ("Microsoft", "Edge", "Application", "msedge.exe"),
                    ("Google", "Chrome", "Application", "chrome.exe")):
            exes += [str(Path(b, *rel)) for b in bases if b]
    exes.append("/opt/pw-browsers/chromium")
    tried = []
    for exe in exes:
        if exe and Path(exe).exists():
            try:
                return p.chromium.launch(executable_path=exe, **kw)
            except Exception as e:
                tried.append(f"{exe}: {str(e).splitlines()[0]}")
    raise RuntimeError("no se encontró Brave (ni Edge ni Chrome) instalado" + (": " + " | ".join(tried) if tried else ""))


def capture(report_html: Path, dest: Path, wait_ms: int = 2500) -> Path:
    """One JPEG per screen plus capturas.json. Returns the json path."""
    from playwright.sync_api import sync_playwright

    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("pantalla_*.jpg"):
        f.unlink()
    meta = {"report": str(report_html), "screens": [], "errors": []}
    with sync_playwright() as p:
        b = _browser(p)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(f"error de la página: {e}"))
        # media requests are aborted and re-issued by range as a normal part of playing a video
        pg.on("requestfailed", lambda r: errs.append(f"no se pudo cargar {'/'.join(r.url.rsplit('/', 2)[-2:])}")
              if r.failure != "net::ERR_ABORTED" else None)
        pg.goto(report_html.resolve().as_uri(), wait_until="load")
        pg.wait_for_timeout(wait_ms)
        meta["errors"] += [e for e in errs if "Failed to load resource" not in e]
        meta["h264"] = bool(pg.evaluate("""() => document.createElement('video').canPlayType('video/mp4; codecs="avc1.640028"')"""))
        meta["browser"] = b.browser_type.name + " " + b.version
        for i, tab in enumerate(TABS):
            errs.clear()
            if not pg.query_selector(f'.nav button[data-tab="{tab}"]'):
                continue
            pg.evaluate(f"document.querySelector('.nav button[data-tab=\"{tab}\"]').click()")
            pg.wait_for_timeout(wait_ms)
            info = pg.evaluate(_JS_SCREEN, tab) or {"title": tab}
            f = f"pantalla_{i + 1}_{tab}.jpg"
            pg.screenshot(path=str(dest / f), full_page=True, type="jpeg", quality=70)
            info.update(tab=tab, file=f, errors=[e for e in errs if "Failed to load resource" not in e])
            meta["screens"].append(info)
        b.close()
    out = dest / "capturas.json"
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
