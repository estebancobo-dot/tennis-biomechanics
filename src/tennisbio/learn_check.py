"""Automatic check of «Aprende su derecha» in a real browser, for every combination asked.

For each combination of conditions (none, each level alone, every pair of conditions, the user's
example of five, and any others given) the screen must say how many of her strokes match (and, if it
widens, which conditions it drops), show its 9 cards (8 phases + feet), give for every checkpoint
either her value with how many strokes back it or why it is missing, her own pattern when there is a
value, the cue, the typical mistake and the drill, and explain what changes for every chosen
condition. Used by the audit (the report the user opens) and by the tests (a large dataset)."""
from __future__ import annotations

from itertools import combinations

USER_EXAMPLE = {"shot_type": "paralela", "stance_impact": "cerrado", "movement": "parada", "swing": "plano",
                "court_side": "lado de su derecha"}

_JS_CHECK = r"""([sel, expect]) => {
  aSel = Object.assign({}, sel); renderLearn();
  const bad = [];
  const res = document.getElementById('a-res').innerText;
  if (!/golpes exactos/.test(res)) bad.push('sin recuento de golpes');
  const R = aResolve();
  if (R.dropped.length && !/se amplía quitando|Los más parecidos cumplen|no cumple ninguna/.test(res)) bad.push('amplía sin decir qué quita ni cuáles son los más parecidos');
  // compared with what the code says the screen must have (not with the page itself)
  const cards = [...document.querySelectorAll('#a-phases .lcard')];
  const ids = cards.map(c => c.dataset.phase);
  if (JSON.stringify(ids) !== JSON.stringify(expect.phases.map(p => p.id))) bad.push(`fichas ${ids.join(',')} en vez de ${expect.phases.map(p => p.id).join(',')}`);
  let rows = 0, valued = 0, targeted = 0;
  expect.phases.forEach(ph => {
    const cd = cards.find(c => c.dataset.phase === ph.id); if (!cd) return;
    const keys = [...cd.querySelectorAll('.cpk')].map(r => r.dataset.key);
    ph.keys.forEach(k => { if (!keys.includes(k)) bad.push(`${ph.id}: falta ${k}`); });
    cd.querySelectorAll('.cpk').forEach(r => {
      rows++; if (r.querySelector('.v')) valued++;
      const v = r.children[1].innerText.trim(), how = r.querySelector('.how').textContent;   // folded parts too
      if (!v || v === '—' || /^—\s*$/.test(v)) bad.push(`${r.dataset.key}: sin valor ni motivo`);
      const LABS = ['Cómo hacerlo tú:', 'Error típico y ejercicio', 'Error típico:', 'Ejercicio:'];
      for (const lab of ['Cómo hacerlo tú:', 'Error típico:', 'Ejercicio:']) {
        const i = how.indexOf(lab);
        let m = i < 0 ? null : how.slice(i + lab.length);
        if (m !== null) LABS.forEach(o => { const j = m.indexOf(o); if (j >= 0) m = m.slice(0, j); });
        if (!m || m.trim().length < 3) bad.push(`${r.dataset.key}: «${lab}» vacío`);
      }
      if (r.querySelector('.v') && !/Ella:/.test(how)) bad.push(`${r.dataset.key}: con valor pero sin su patrón`);
      if (r.querySelector('.v') && (LEARN.targets || {})[r.dataset.key]) {
        targeted++;
        const mine = r.querySelector('.mine');
        if (!mine) bad.push(`${r.dataset.key}: con valor pero sin «Tu objetivo» con su número`);
        else if (/[{}]/.test(mine.textContent) || !/\d/.test(mine.textContent)) bad.push(`${r.dataset.key}: «Tu objetivo» sin su número`);
      }
    });
    if (!cd.querySelector('button[data-open]') && document.querySelectorAll('#a-res .athumbs button').length) bad.push(`${ph.id}: sin «Ver en vídeo»`);
  });
  const sit = [...document.querySelectorAll('#a-sit li')].map(li => li.innerText);
  Object.values(sel).forEach(l => { const li = sit.find(t => t.startsWith(l + ':')); if (!li || li.length < l.length + 15) bad.push(`qué cambia: falta «${l}»`); });
  if (!/Estilo de su derecha:/.test(document.getElementById('a-sig').innerText)) bad.push('sin estilo ni firma');
  const sig = document.querySelectorAll('#a-sig li').length;
  if (!document.querySelectorAll('#a-plan li').length || !document.querySelectorAll('#a-plan-all li').length) bad.push('sin plan');
  if (document.querySelectorAll('#a-plan li b').length > 3) bad.push('más de 3 prioridades en el plan');
  cards.forEach(cd => { const ph = expect.phases.find(p => p.id === cd.dataset.phase); if (ph && ph.focus && !cd.querySelector('.focus')) bad.push(`${ph.id}: sin foco`); });
  if (!document.querySelectorAll('#a-nottv li').length) bad.push('sin lo no medible');
  if (!document.getElementById('a-guide') || !/Empieza aquí/.test(document.getElementById('a-guide').textContent)) bad.push('sin guía de primer uso');
  if (document.querySelectorAll('#a-gloss dt').length < 20) bad.push('glosario incompleto');
  return {bad, rows, valued, targeted, gloss: document.querySelectorAll('#a-phases abbr.gl').length, sig, style: document.getElementById('a-sig').querySelector('p').innerText, exact: R.exact.length, wider: R.wider.length, near: document.querySelectorAll('#a-res .athumbs button').length};
}"""


def combos(conditions: dict, extra: list[dict] | None = None, pairs: bool = True) -> list[dict]:
    """The combinations to check: none, each level, every pair of conditions, the user's example."""
    out = [{}]
    for d, levels in conditions.items():
        out += [{d: lv} for lv in levels]
    if pairs:
        for (d1, l1), (d2, l2) in combinations(conditions.items(), 2):
            out += [{d1: a, d2: b} for a in l1 for b in l2]
    out.append(dict(USER_EXAMPLE))
    return out + (extra or [])


def check_page(pg, pairs: bool = True, extra: list[dict] | None = None) -> dict:
    """Runs every combination on an open report page (Playwright). Returns the summary and failures."""
    pg.evaluate("document.querySelector('.nav button[data-tab=\"aprende\"]').click()")
    # the full list of measures is folded under the lesson: unfolded to read it as the user would
    pg.evaluate("['a-more', 'a-phases-d'].forEach(id => { const d = document.getElementById(id); if (d) d.open = true; })")
    pg.wait_for_timeout(300)
    conds = pg.evaluate("Object.fromEntries(Object.entries(LEARN.conditions).map(([d, c]) => [d, Object.keys(c.levels)]))")
    from .learn import content
    c = content()
    expect = {"phases": [{"id": ph["id"], "focus": ph.get("focus"), "keys": [x["key"] for x in ph["checkpoints"]]} for ph in c["phases"]]}
    want = {d: list(v["levels"]) for d, v in c["conditions"].items()}
    missing = {d: [l for l in lv if l not in conds.get(d, [])] for d, lv in want.items()}
    todo = combos(want, extra, pairs)
    fails, rows, with_strokes, extra_out = [], 0, 0, {}
    for sel in todo:
        r = pg.evaluate(_JS_CHECK, [sel, expect])
        if not sel:
            extra_out.update(rows_all=r["rows"], valued_all=r["valued"], targeted_all=r["targeted"], glossed_all=r["gloss"], signature=r["sig"], style=r["style"])
        if sel == USER_EXAMPLE:
            extra_out["example"] = {"exact": r["exact"], "near": r["near"], "rows": r["rows"], "valued": r["valued"], "bad": r["bad"]}
        rows += r["rows"]
        with_strokes += bool(r["exact"])
        if r["bad"]:
            fails.append({"sel": sel, "bad": r["bad"][:5]})
    pg.evaluate("aSel = {}; renderLearn()")
    for d, lv in missing.items():
        if lv:
            fails.append({"sel": {d: lv}, "bad": ["condición que el código define y la página no ofrece"]})
    return {"combinations": len(todo), "with_exact_strokes": with_strokes, "checkpoints_checked": rows, "failures": fails, **extra_out}


_JS_LESSON = """async () => {
  const out = [], steps = [...document.querySelectorAll('#a-l-steps button')].map(b => b.dataset.ph);
  const words = el => (el && el.innerText || '').split(/\\s+/).filter(Boolean).length;
  for (const ph of steps) {
    document.querySelector(`#a-l-steps button[data-ph="${ph}"]`).click();
    await new Promise(r => setTimeout(r, 700));
    // the first video of the page takes longer to load: wait for it (up to 4 s) before judging
    for (let w = 0; w < 20 && typeof LS !== 'undefined' && lReps.length && LS.video.readyState < 2; w++) await new Promise(r => setTimeout(r, 200));
    const keys = [...document.querySelectorAll('#a-l-keys .lkey')];
    const panel = document.getElementById('a-lesson').getBoundingClientRect();
    const focus = (document.getElementById('a-l-focus').innerText || '').replace(/\\(regla general[\\s\\S]*$/, '');
    const prac = document.getElementById('a-l-practice').innerText || '';
    out.push({ phase: ph, keys: keys.length,
      valued: keys.filter(k => /Ella:\\s*\\S/.test(k.innerText) && !/—/.test(k.querySelector('.lh b')?.innerText || '—')).length,
      checked: keys.filter(k => k.textContent.includes('Cómo comprobarlo')).length,
      drilled: keys.filter(k => k.textContent.includes('Ejercicio')).length,
      // words to read in the keys (the bars of «cambia con la bola» are a picture, not text to read)
      words: words({ innerText: [...document.querySelectorAll('#a-l-keys .lkey')].map(k => { const c = k.cloneNode(true); c.querySelectorAll('.lbars, details').forEach(x => x.remove()); return c.innerText || c.textContent; }).join(' ') }),
      focus_words: words({ innerText: focus.replace(/^Foco:/, '') }), focus_body: /\\d\\s*(%|°|cm)/.test(focus),
      practice: /\\d+ de \\d+/.test(prac), strings: /Cuerdas/.test(document.getElementById('a-l-strings').innerText || ''),
      repeats: keys.filter(k => { const m = k.querySelector('.mine'); const v = k.querySelector('.lh b'); return m && v && m.innerText.includes(v.innerText.split(' (')[0]); }).length,
      reason: keys.length ? '' : (document.getElementById('a-l-keys').innerText || '').slice(0, 160),
      reps: typeof lReps !== 'undefined' ? lReps.length : 0,
      video: typeof LS !== 'undefined' && LS.video.readyState >= 2 && !document.getElementById('a-l-cv').hidden,
      height: Math.round(panel.height) });
  }
  // the phase strip shows her stroke in real photos (as the coaches' 3-4 photo sequences): give it 3 s
  for (let w = 0; w < 15 && document.querySelectorAll('#a-l-steps canvas[data-ok]').length < out.length - 1; w++) await new Promise(r => setTimeout(r, 200));
  out.thumbs = document.querySelectorAll('#a-l-steps canvas[data-ok]').length;
  return { rows: out, thumbs: out.thumbs };
}"""


def check_lesson(pg) -> dict:
    """«La lección» against the user's requirements: per phase at most 3 keys, each with her value, a
    drill and how to check it (or the reason none is given); her video of the phase; the lesson fits in
    about one screen and a half (1280 × 900)."""
    pg.evaluate("showTab('aprende')")
    pg.wait_for_timeout(300)
    res = pg.evaluate(_JS_LESSON)
    rows = res["rows"]
    bad = []
    for r in rows:
        why = []
        if r["keys"] > 3:
            why.append(f"{r['keys']} claves (máximo 3)")
        if not r["keys"] and not r["reason"]:
            why.append("sin claves y sin decir por qué")
        if r["valued"] < r["keys"] or r["checked"] < r["keys"] or r["drilled"] < r["keys"]:
            why.append("una clave sin su valor, su ejercicio o cómo comprobarlo")
        if r["height"] > 1400:
            why.append(f"la lección mide {r['height']} px (más de pantalla y media)")
        if r["words"] > 120:
            why.append(f"{r['words']} palabras en las claves (máximo 120)")
        if r["focus_words"] > 25 or r["focus_body"]:
            why.append("el foco es largo o lleva cifras del cuerpo")
        if r["keys"] and not r["practice"]:
            why.append("sin ejercicio con criterio «N de M»")
        if r["phase"] != "feet" and not r["strings"]:
            why.append("sin la línea de las cuerdas")
        if r["repeats"]:
            why.append("«Tu objetivo» repite su valor")
        if why:
            bad.append({"phase": r["phase"], "why": why})
    return {"phases": rows, "failures": bad, "with_video": sum(1 for r in rows if r["video"]),
            "with_keys": sum(1 for r in rows if r["keys"]), "thumbs": res["thumbs"]}


_JS_ENTRY = """() => {
  // as it opens: the extras folded and the situation picker closed (other checks may have opened them)
  ['a-more', 'a-phases-d', 'a-gloss-d', 'sec-modelo'].forEach(id => { const d = document.getElementById(id); if (d) d.open = false; });
  const cp = document.getElementById('a-cond-p'); if (cp) cp.hidden = true;
  scrollTo(0, 0); showTab('aprende');
  const sec = document.getElementById('tab-aprende'), v = document.querySelector('#a-lesson .lvid').getBoundingClientRect();
  const vis = el => el.checkVisibility();
  const words = [...sec.children].filter(vis).map(e => e.tagName === 'DETAILS' ? e.querySelector('summary').innerText : e.innerText).join(' ').split(/\\s+/).filter(Boolean).length;
  return { vid_top: Math.round(v.top + scrollY), vid_bottom: Math.round(v.bottom + scrollY), h2: [...sec.querySelectorAll('h2')].filter(vis).length,
           words, buttons: [...sec.querySelectorAll('button')].filter(vis).length, height: innerHeight };
}"""
_FILE_NAME = r"[a-z]+_[\w-]+-\d{7}"


def check_entry(pg) -> dict:
    """The entry screen and every screen against the definitive design (docs/diseno_definitivo.md §5):
    the lesson video in the first screen, few headings/words/buttons when it opens, no sideways scroll
    on any screen, no file name as the title of a stroke."""
    out = {"entry": pg.evaluate(_JS_ENTRY), "wide": {}, "file_names": {}}
    for t in ("aprende", "videoteca", "golpe", "comparar", "conclusiones", "explorador", "lateral", "fiabilidad", "datos"):
        pg.evaluate(f"showTab('{t}')")
        pg.wait_for_timeout(250)
        w, iw = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        if w > iw + 1:
            # which elements stick out (id or class, width), so the fix can go straight to them
            culprits = pg.evaluate(f"""(() => {{ const iw = innerWidth; return [...document.querySelectorAll('#tab-{t} *')]
                .filter(e => e.checkVisibility() && e.getBoundingClientRect().right > iw + 1 && !(e.parentElement && e.parentElement.getBoundingClientRect().right > iw + 1))
                .slice(0, 4).map(e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + String(e.className || '').split(' ')[0]) + ' ' + Math.round(e.getBoundingClientRect().width) + 'px'); }})()""")
            out["wide"][t] = f"{w} px: " + ", ".join(culprits)
        n = pg.evaluate(f"""(() => {{ const re = /{_FILE_NAME}/; return [...document.querySelectorAll('#tab-{t} b, #tab-{t} h2, #tab-{t} option')]
                           .filter(e => e.checkVisibility() && re.test(e.textContent)).length; }})()""")
        if n:
            out["file_names"][t] = n
    e = out["entry"]
    bad = []
    if e["vid_bottom"] > e["height"]:
        bad.append(f"el vídeo de la lección acaba en y={e['vid_bottom']} (más abajo que la primera pantalla, {e['height']})")
    if e["h2"] > 3 or e["buttons"] > 30:
        bad.append(f"al abrir: {e['h2']} títulos y {e['buttons']} botones (máximo 3 y 30)")
    if out["wide"]:
        bad.append("se sale por la derecha: " + "; ".join(f"{k} ({v})" for k, v in out["wide"].items()))
    if out["file_names"]:
        bad.append("nombres de fichero como título de un golpe en: " + ", ".join(out["file_names"]))
    out["failures"] = bad
    pg.evaluate("showTab('aprende')")
    return out
