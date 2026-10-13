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
  let rows = 0, valued = 0;
  expect.phases.forEach(ph => {
    const cd = cards.find(c => c.dataset.phase === ph.id); if (!cd) return;
    const keys = [...cd.querySelectorAll('.cpk')].map(r => r.dataset.key);
    ph.keys.forEach(k => { if (!keys.includes(k)) bad.push(`${ph.id}: falta ${k}`); });
    cd.querySelectorAll('.cpk').forEach(r => {
      rows++; if (r.querySelector('.v')) valued++;
      const v = r.children[1].innerText.trim(), how = r.querySelector('.how').innerText;
      if (!v || v === '—' || /^—\s*$/.test(v)) bad.push(`${r.dataset.key}: sin valor ni motivo`);
      for (const lab of ['Cómo hacerlo tú:', 'Error típico:', 'Ejercicio:']) {
        const m = how.split(lab)[1];
        if (!m || m.split('\n')[0].trim().length < 3) bad.push(`${r.dataset.key}: «${lab}» vacío`);
      }
      if (r.querySelector('.v') && !/Ella:/.test(how)) bad.push(`${r.dataset.key}: con valor pero sin su patrón`);
    });
    if (!cd.querySelector('button[data-open]') && document.querySelectorAll('#a-res .athumbs button').length) bad.push(`${ph.id}: sin «Ver en vídeo»`);
  });
  const sit = [...document.querySelectorAll('#a-sit li')].map(li => li.innerText);
  Object.values(sel).forEach(l => { const li = sit.find(t => t.startsWith(l + ':')); if (!li || li.length < l.length + 15) bad.push(`qué cambia: falta «${l}»`); });
  if (!/Estilo de su derecha:/.test(document.getElementById('a-sig').innerText)) bad.push('sin estilo ni firma');
  const sig = document.querySelectorAll('#a-sig li').length;
  if (!document.querySelectorAll('#a-plan li').length) bad.push('sin plan');
  if (!document.querySelectorAll('#a-nottv li').length) bad.push('sin lo no medible');
  return {bad, rows, valued, sig, style: document.getElementById('a-sig').querySelector('p').innerText, exact: R.exact.length, wider: R.wider.length, near: document.querySelectorAll('#a-res .athumbs button').length};
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
    pg.wait_for_timeout(300)
    conds = pg.evaluate("Object.fromEntries(Object.entries(LEARN.conditions).map(([d, c]) => [d, Object.keys(c.levels)]))")
    from .learn import content
    c = content()
    expect = {"phases": [{"id": ph["id"], "keys": [x["key"] for x in ph["checkpoints"]]} for ph in c["phases"]]}
    want = {d: list(v["levels"]) for d, v in c["conditions"].items()}
    missing = {d: [l for l in lv if l not in conds.get(d, [])] for d, lv in want.items()}
    todo = combos(want, extra, pairs)
    fails, rows, with_strokes, extra_out = [], 0, 0, {}
    for sel in todo:
        r = pg.evaluate(_JS_CHECK, [sel, expect])
        if not sel:
            extra_out.update(rows_all=r["rows"], valued_all=r["valued"], signature=r["sig"], style=r["style"])
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
