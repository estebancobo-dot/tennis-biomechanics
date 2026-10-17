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

TABS = ["aprende", "videoteca", "golpe", "comparar", "conclusiones", "explorador", "lateral", "fiabilidad", "datos"]
# the name of each screen in the audit (stable, whatever the menu says)
TITLES = {"aprende": "Cópiala (Aprende su derecha, con su patrón típico)", "videoteca": "Sus golpes (Videoteca y pista)",
          "golpe": "Análisis de golpe", "comparar": "Comparar dos golpes", "conclusiones": "Conclusiones (Panel y Comparativas)",
          "explorador": "Tabla de golpes (Explorador)", "lateral": "Vista lateral (entreno)", "fiabilidad": "Fiabilidad de las medidas",
          "datos": "Datos del análisis"}
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
    feet_cycle: sec.querySelectorAll('#feet-txt li').length,
    ball_measures: [...sec.querySelectorAll('#bm .mm')].filter(e => /cm|m /.test(e.innerText)).length,
    body_hip: sec.querySelectorAll('#bd-hip button').length + (/Baja \d/.test((sec.querySelector('#bd-hip-t') || {}).innerText || '') ? 1 : 0),
    body_base: sec.querySelectorAll('#bd-base button').length + (/Base de /.test((sec.querySelector('#bd-base-t') || {}).innerText || '') ? 1 : 0),
    body_trunk: sec.querySelectorAll('#bd-trunk button').length + (/tronco queda/.test((sec.querySelector('#bd-trunk-t') || {}).innerText || '') ? 1 : 0),
    heights_layer: !!sec.querySelector('#layers button[data-v="heights"]'),
    lib_filters: sec.querySelectorAll('#lib-chips button').length,
    news: !!sec.querySelector('#news'),
    intro: !!(sec.querySelector('.intro') && sec.querySelector('.intro').innerText.trim().length > 20),
    external_links: [...sec.querySelectorAll('a[href^="http"]')].filter(a => a.offsetParent).length,
    // a table kept as an extra (inside details.extra, below its sentences) is fine; only bare tables count
    tables: [...sec.querySelectorAll('table')].filter(t => t.offsetParent && t.rows.length > 2 && !t.closest('details.extra')).length,
    sentences: [...sec.querySelectorAll('ul.say li')].filter(l => l.offsetParent).length,
    many_lines: [...sec.querySelectorAll('svg')].filter(g => g.offsetParent && g.querySelectorAll('polyline').length > 4).length,
  };
}"""


def _browser(p):
    """A browser already installed, never downloaded: Brave (the user's), else Edge or Chrome if they
    are there; on Linux, the machine's Chromium."""
    # as the user opens it: no special autoplay permission (play must work from the click itself)
    kw = {"args": ["--allow-file-access-from-files"]}
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


# every button that plays strokes, as the user clicks it: the video must advance within ~2 s
_PLAY_BUTTONS = [("modelo", "#m-play", "«Su derecha» → ▶ Ver sus golpes típicos"),
                 ("videoteca", "#lib-play", "Videoteca → ▶ Reproducir todos"),
                 ("golpe", "#play", "Análisis de golpe → ▶"),
                 ("comparar", "#k-play", "Comparar golpes → ▶"),
                 ("panel", "#concl button[data-pl]", "Panel → ▶ vídeos de una conclusión")]


def _test_plays(pg) -> list[dict]:
    out = []
    for tab, sel, name in _PLAY_BUTTONS:
        try:
            pg.evaluate("() => { try { stopPlay(); endPlaylist(); } catch (e) {} }")
            pg.evaluate(f"showTab('{tab}')")
            pg.wait_for_timeout(800)
            btn = pg.query_selector(sel)
            if not btn or not btn.is_visible():
                out.append({"name": name, "present": False})
                continue
            vid = "KA.video" if tab == "comparar" else "video"
            t0 = pg.evaluate(f"{vid}.currentTime")
            btn.click()
            pg.wait_for_timeout(2500)
            t1, paused = pg.evaluate(f"[{vid}.currentTime, {vid}.paused]")
            err, mode = pg.evaluate("[window.__playErr || null, window.__playMode || 'video']")
            if mode == "manual":            # the browser refused play(); the report stepped the video itself
                t1, paused = pg.evaluate("tNow"), False
                t0 = None
            out.append({"name": name, "present": True, "plays": bool(t1 != t0 and not paused), "mode": mode, "play_error": err})
            if tab == "comparar" and not paused:
                btn.click()
        except Exception as e:                    # a broken button is a finding, never a crash
            out.append({"name": name, "present": True, "plays": False, "error": str(e)[:120]})
    return out


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
            if not pg.query_selector(f"#tab-{tab}"):
                continue
            pg.evaluate(f"showTab('{tab}')")             # as the menu does (Análisis de golpe opens from Sus golpes)
            pg.wait_for_timeout(wait_ms)
            info = pg.evaluate(_JS_SCREEN, tab) or {"title": tab}
            info["title"] = TITLES.get(tab, info.get("title") or tab)
            if tab == "golpe" and pg.query_selector("#play"):
                # play as the user does, right away: the video must advance and keep playing
                t0 = pg.evaluate("typeof video !== 'undefined' ? video.currentTime : null")
                pg.click("#play")
                pg.wait_for_timeout(1500)
                t1, paused = pg.evaluate("typeof video !== 'undefined' ? [video.currentTime, video.paused] : [null, true]")
                info["plays"] = bool(t0 is not None and t1 is not None and t1 > t0 + 0.1 and not paused)
                if not paused:
                    pg.click("#play")
            f = f"pantalla_{i + 1}_{tab}.jpg"
            pg.screenshot(path=str(dest / f), full_page=True, type="jpeg", quality=70)
            info.update(tab=tab, file=f, errors=[e for e in errs if "Failed to load resource" not in e])
            meta["screens"].append(info)
        meta["plays"] = _test_plays(pg)
        # and with Windows animations off ("reduce motion"), as on the user's PC: play must still play
        pg.emulate_media(reduced_motion="reduce")
        meta["plays_reduced_motion"] = _test_plays(pg)
        # «Aprende su derecha»: every combination of conditions answers with all it must (learn_check)
        try:
            from .learn_check import check_page
            meta["learn"] = check_page(pg)
        except Exception as e:                    # a broken screen is a finding, never a crash
            meta["learn"] = {"error": str(e)[:300]}
        # the entry screen and every screen against the definitive design (first screen, width, names)
        try:
            from .learn_check import check_entry
            meta["entry"] = check_entry(pg)
        except Exception as e:
            meta["entry"] = {"error": str(e)[:300]}
        # «La lección»: each phase, video first and at most 3 keys with value, drill and check
        try:
            from .learn_check import check_lesson
            pg.emulate_media(reduced_motion="no-preference")
            meta["lesson"] = check_lesson(pg)
        except Exception as e:
            meta["lesson"] = {"error": str(e)[:300]}
        b.close()
    out = dest / "capturas.json"
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
