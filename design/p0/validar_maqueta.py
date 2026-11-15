"""#305 (15-11): the P0 mockup against everything the project asks of it, computed and not by eye.

Sources:
- docs/matriz_cobertura.md: the forehand's taxonomy (§1-§5b) and the user's 15-point matrix (§6), row by row. A
  measured row (✔/◐) is in the mockup when one of its measure keys is a check of the lesson whose name is on screen
  (else, «por texto» when most of its words are on one screen: to look at); a row not measurable from TV (✘) must be
  said («Lo que la tele no mide» or «no medible»).
- design/p0/cobertura_maqueta.yaml: the requirements of CLAUDE.md, the Ivanovic guide's 20 gaps, what the coaches
  teach (§3, §5, §6), the state of the art's patterns and the usability items, each with where it must be visible.
- config/referencias.yaml: every pattern adopted (or planned) must have its item.
- The walk (recorrer_maqueta.py): JavaScript errors and sideways overflow at each width; how many measures the lesson
  shows at first sight (few, well chosen: requirement 2).

    uv run python design/p0/validar_maqueta.py <built mockup .html> <walk .json> <out .md>

The report holds no data of the player (only names of measures and screens), so it can go to the repository.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
KEY = re.compile(r"`([a-z][a-z0-9_.]*)`")
STOP = {"desde", "sobre", "entre", "hasta", "donde", "cuando", "tras", "antes", "después", "durante", "contra", "según",
        "porque", "mismo", "misma", "cada", "otros", "otras", "todos", "todas", "también", "solo", "medida", "medidas"}
SECTION = re.compile(r"^## (\d+b?)\.")
MAX_MEASURES_AT_SIGHT = 4          # requirement 2: few numbers, well chosen (the lesson's key measures at first sight)
# the lesson's sections under its phases (collapsed; the same on every phase): each is a screen of its own here, so a
# word of the glossary is never taken for a measure shown in a phase
LESSON_SECTIONS = ("Lo esencial", "Su ritmo y su cadena cinética", "Qué cambia según la bola", "Tu plan completo",
                   "Si te pasa…", "Lo que la tele no mide", "Todas las medidas", "Glosario")
VIEWER = ("leccion", "golpe", "mas_", "situacion")   # the screens about her forehand (not the system's)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def words(s: str) -> list[str]:
    s = re.sub(r"\([^)]*\)", " ", s)
    return [w for w in re.findall(r"[a-z]{5,}", norm(s)) if w not in {norm(x) for x in STOP}]


def matrix_rows(md: str) -> list[dict]:
    """Every table row of the coverage matrix: its section, element, state (✔, ◐ or ✘) and measure keys."""
    out, sec = [], None
    for line in md.splitlines():
        m = SECTION.match(line)
        if m:
            sec = m.group(1)
            continue
        if not (sec and line.startswith("| ")) or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        state = next((c for c in cells if c[:1] in "✔◐✘"), None)
        if state is None:
            continue
        out.append({"seccion": sec, "elemento": cells[0], "estado": state[:1],
                    "claves": [k for k in KEY.findall(line) if "_" in k or "." in k], "texto": line})
    return out


def mockup_data(html: str) -> dict:
    i = html.find('{"generated"')
    return json.JSONDecoder().raw_decode(html[i:])[0] if i >= 0 else {}


def checks_of(data: dict) -> dict[str, str]:
    return {c["key"]: c.get("label") or "" for p in data.get("phases", []) for c in p.get("checks", []) if c.get("key")}


def key_hits(keys: list[str], checks: dict[str, str]) -> list[str]:
    out = []
    for k in keys:
        last = k.split(".")[-1]
        out += [c for c in checks if c == k or c.endswith("." + k) or c.split(".")[-1] == last]
    return sorted(set(out))


def by_words(text: str, states: dict[str, str], share: float = 0.6) -> str | None:
    """The first screen holding most of the text's significant words (None when there are fewer than 2)."""
    ws = set(words(text))
    if len(ws) < 2:
        return None
    for name, t in states.items():
        nt = norm(t)
        if sum(w in nt for w in ws) / len(ws) >= share:
            return name
    return None


def screens(walk: dict) -> dict[str, str]:
    """The walked screens as checked: each lesson phase with what it shows; the lesson's sections, once each and
    opened («leccion/<section>»); every other screen with its collapsed parts opened (one click away)."""
    out, full, sight = {}, walk["estados"], walk["a_la_vista"]
    for k, v in full.items():
        if k.startswith("leccion_fase"):
            # the phase with its own collapsed parts opened, up to the lesson's common sections (never the glossary)
            cut = min([i for i in (v.find(h) for h in LESSON_SECTIONS) if i >= 0] or [len(v)])
            out[k] = sight.get(k, "") + "\n" + v[:cut]      # on screen (the sections' titles too), plus the phase opened
        else:
            out[k] = v
    first = next((k for k in sorted(full) if k.startswith("leccion_fase")), None)
    if first:
        t = full[first]
        at = sorted((t.find(h), h) for h in LESSON_SECTIONS if t.find(h) >= 0)
        for (i, h), (j, _) in zip(at, at[1:] + [(len(t), "")]):
            out[f"leccion/{h}"] = t[i:j]
    return out


def check_matrix(rows: list[dict], states: dict[str, str], checks: dict[str, str], not_tv: str,
                 stroke_keys: dict[str, str] | None = None) -> list[dict]:
    """stroke_keys: measure keys each stroke's analysis shows (its feet), with the screen that shows them."""
    allt = "\n".join(v for k, v in states.items() if k != "leccion/Glosario")
    viewer = {k: v for k, v in states.items() if k.startswith(VIEWER) and k != "leccion/Glosario"}
    out = []
    for r in rows:
        src = "lista15" if r["seccion"] == "6" else "taxonomia"
        res = {"id": f"M{r['seccion']}.{len(out) + 1}", "fuente": src, "texto": r["elemento"], "estado_medida": r["estado"]}
        if r["estado"] == "✘":
            said = by_words(r["elemento"], {"no medible": not_tv}, 0.34) or by_words(
                r["elemento"], {k: v for k, v in states.items() if re.search("no medible|la tele no", v, re.I)}, 0.75)
            res.update(resultado="dicho" if said else "falta", donde=said or "",
                       nota="no medible desde la tele: la aplicación lo dice" if said else "no medible y no lo dice")
        else:
            hits = key_hits(r["claves"], checks)
            shown = [h for h in hits if checks[h] and checks[h] in allt]
            panel = [h for h in key_hits(r["claves"], stroke_keys or {}) if (stroke_keys or {})[h] in states]
            if shown or panel:
                res.update(resultado="en_maqueta", donde=", ".join(shown[:3] or [f"golpe: {h}" for h in panel[:3]]))
            else:
                w = by_words(r["elemento"], viewer)
                res.update(resultado="por_texto" if w else "falta", donde=w or "",
                           nota=("su medida no está en la lección" if r["claves"] else "sin medida con clave"))
        out.append(res)
    return out


def check_items(items: list[dict], states: dict[str, str], media: dict[str, int] | None = None) -> list[dict]:
    """media: real video or canvas elements per screen; an item with `medio: true` needs them where it is found (its
    words beside a marked placeholder are not the thing)."""
    out = []
    for it in items:
        pats = [re.compile(p, re.I) for p in it["busca"]]
        where = [k for k in states if not it.get("en") or any(k.startswith(e) for e in it["en"])]
        if it.get("medio"):
            where = [k for k in where if (media or {}).get(k.split("/")[0], 0) > 0]
        found = [k for k in where if (all if it.get("todos") else any)(p.search(states[k]) for p in pats)]
        if it.get("niega"):
            ok = not found
        else:
            ok = bool(found)
        res = {"id": it["id"], "fuente": it["fuente"], "texto": it["texto"], "donde": ", ".join(found[:3])}
        if it.get("tipo") == "hueco":
            res.update(resultado="en_maqueta" if ok else "hueco", nota=it.get("paquete", ""))
        else:
            res.update(resultado="en_maqueta" if ok else "falta")
        out.append(res)
    return out


def check_patterns(refs: dict, items: list[dict]) -> list[str]:
    """Patterns adopted or planned in the catalogue without an item that looks for them in the mockup."""
    have = {it["id"].split(".", 1)[1] for it in items if it["id"].startswith("P.")}
    return sorted(k for k, v in (refs.get("patrones") or {}).items() if str(v.get("adopta")) in ("si", "hueco") and k not in have)


def by_reference(refs: dict, results: list[dict]) -> list[dict]:
    """Each reference of the catalogue against the mockup: its patterns the mockup shows, its adopted patterns it does
    not show, and the ones turned down on purpose (with the catalogue's reason) or planned later."""
    pats = refs.get("patrones") or {}
    got = {r["id"].split(".", 1)[1]: r["resultado"] for r in results if r["id"].startswith("P.")}
    out = []
    for ref in refs.get("referencias") or []:
        ps = ref.get("patrones") or []
        out.append({"nombre": ref.get("nombre"), "tipo": ref.get("tipo"),
                    "tiene": [p for p in ps if got.get(p) == "en_maqueta"],
                    "falta": [p for p in ps if str(pats.get(p, {}).get("adopta")) == "si" and got.get(p) != "en_maqueta"],
                    "despues": [p for p in ps if str(pats.get(p, {}).get("adopta")) == "hueco"],
                    "no": [p for p in ps if str(pats.get(p, {}).get("adopta")) == "no"]})
    return out


def check_walk(walk: dict) -> list[dict]:
    out = []
    for w, r in walk.items():
        desk = int(w) >= 1024
        out.append({"id": f"U.errores_{w}", "fuente": "ux", "texto": f"Sin errores de JavaScript a {w} px",
                    "resultado": "en_maqueta" if not r["errores"] else "falta", "donde": "; ".join(r["errores"][:3])})
        out.append({"id": f"U.desborde_{w}", "fuente": "ux",
                    "texto": f"Nada se sale de la pantalla a {w} px" + ("" if desk else " (móvil: solo para revisar, #301)"),
                    "resultado": "en_maqueta" if not r["desborde"] else ("falta" if desk else "aviso"),
                    "donde": f"{len(r['desborde'])} de {len(r['estados'])} pantallas" if r["desborde"] else ""})
    sight = walk.get("1920", {}).get("a_la_vista", {})
    counts = {k: len(re.findall(r"· \d+ golpes", v)) for k, v in sight.items() if k.startswith("leccion")}
    worst = max(counts.values()) if counts else 0
    out.append({"id": "U.pocos_numeros", "fuente": "ux",
                "texto": f"Pocas medidas a la vista en cada fase de la lección (≤ {MAX_MEASURES_AT_SIGHT}; requisito 2)",
                "resultado": "en_maqueta" if counts and worst <= MAX_MEASURES_AT_SIGHT else "falta",
                "donde": f"como mucho {worst} por fase"})
    return out


NAMES = {"requisitos": "Requisitos de CLAUDE.md (1-10, vistas pedidas, informe, gestión)",
         "taxonomia": "Taxonomía de la derecha (`matriz_cobertura.md` §1-§5b)",
         "lista15": "Tu lista de 15 puntos (`matriz_cobertura.md` §6)", "ivanovic": "Guía de Ivanovic (20 huecos)",
         "entrenadores": "Entrenadores de YouTube (§3, Joel Myers, The Tennis Mentor)",
         "patrones": "Estado del arte: patrones adoptados (`referencias.yaml`)", "ux": "Usabilidad y aprendizaje"}
MARK = {"en_maqueta": "✔", "dicho": "✔ (dice que no se mide)", "por_texto": "≈", "falta": "✘", "hueco": "◇", "aviso": "⚠"}


def report(results: list[dict], missing_patterns: list[str], refs: list[dict] | None = None) -> str:
    lines = ["# Validación de la maqueta P0 (#305)", "",
             "Calculada por `design/p0/validar_maqueta.py` sobre la maqueta recorrida en un navegador "
             "(`recorrer_maqueta.py`: 35 pantallas y paneles, a 1920, 1280, 1024 y 390 px). ✔ está y se ve (o se abre "
             "con un clic); ≈ sus palabras están en una pantalla, pero no su medida (a revisar); ✘ falta; ◇ hueco "
             "previsto en un paquete posterior; ⚠ aviso.", "", "## Resumen", "",
             "| Fuente | Elementos | ✔ | ≈ | ✘ | ◇ / ⚠ | Cobertura |", "|---|---|---|---|---|---|---|"]
    for src, name in NAMES.items():
        rs = [r for r in results if r["fuente"] == src]
        if not rs:
            continue
        ok = sum(r["resultado"] in ("en_maqueta", "dicho") for r in rs)
        tx = sum(r["resultado"] == "por_texto" for r in rs)
        no = sum(r["resultado"] == "falta" for r in rs)
        other = len(rs) - ok - tx - no
        due = len(rs) - sum(r["resultado"] in ("hueco", "aviso") for r in rs)
        lines.append(f"| {name} | {len(rs)} | {ok} | {tx} | {no} | {other} | {round(100 * ok / due) if due else 100} % |")
    if missing_patterns:
        lines += ["", f"Patrones del catálogo sin comprobación: {', '.join(missing_patterns)}"]
    if refs:
        lines += ["", "## Frente a cada referencia del estado del arte (`config/referencias.yaml`)", "",
                  "Sus patrones de presentación: los que la maqueta tiene, los adoptados que le faltan, los previstos "
                  "para después y los descartados a propósito (con su motivo en el catálogo).", "",
                  "| Referencia | Tipo | Tiene | Le falta | Después | Descartado |", "|---|---|---|---|---|---|"]
        for r in refs:
            lines.append(f"| {r['nombre'][:60]} | {r['tipo']} | {', '.join(r['tiene']) or '—'} | {', '.join(r['falta']) or '—'} "
                         f"| {', '.join(r['despues']) or '—'} | {', '.join(r['no']) or '—'} |")
    for src, name in NAMES.items():
        rs = [r for r in results if r["fuente"] == src and r["resultado"] not in ("en_maqueta", "dicho")]
        if not rs:
            continue
        lines += ["", f"## {name}: lo que falta o hay que mirar", "", "| | Elemento | Dónde | Nota |", "|---|---|---|---|"]
        for r in rs:
            lines.append(f"| {MARK[r['resultado']]} | {r['texto'][:110]} | {r.get('donde', '')[:60]} | {r.get('nota', '')[:80]} |")
    return "\n".join(lines) + "\n"


VALIDATE_REFS: list[dict] = []


def validate(html: str, walk: dict) -> tuple[list[dict], list[str]]:
    data = mockup_data(html)
    states = screens(walk["1920"])
    not_tv = "\n".join(" ".join(x) if isinstance(x, list) else str(x) for x in data.get("not_tv", []))
    rows = matrix_rows((ROOT / "docs" / "matriz_cobertura.md").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((Path(__file__).with_name("cobertura_maqueta.yaml")).read_text(encoding="utf-8"))
    refs = yaml.safe_load((ROOT / "config" / "referencias.yaml").read_text(encoding="utf-8"))
    feet = ((data.get("strokes") or [{}])[0].get("feet") or {})
    stroke_keys = {k: "golpe" for k in feet} if "Sus pies" in states.get("golpe", "") else {}
    results = (check_matrix(rows, states, checks_of(data), not_tv, stroke_keys) + check_items(cfg["items"], states, walk["1920"].get("medios"))
               + check_walk(walk))
    VALIDATE_REFS[:] = by_reference(refs, results)
    return results, check_patterns(refs, cfg["items"])


def main(argv: list[str]) -> int:
    html = Path(argv[1]).read_text(encoding="utf-8")
    walk = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    results, missing = validate(html, walk)
    md = report(results, missing, VALIDATE_REFS)
    Path(argv[3]).write_text(md, encoding="utf-8")
    Path(argv[3]).with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(md.split("## ", 2)[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
