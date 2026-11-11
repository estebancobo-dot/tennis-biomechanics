"""The application's quality model, the «cube» (11-11, request #256; config/calidad.yaml).

Every audit check (its area in audit.py) falls in a cell: domain × characteristic (ISO/IEC 25010 plus «exactitud»
against annotated data) × layer (where it is checked). A cell's score is the share of its checks that pass
(ok / ok+aviso+falta); «pocos datos» is counted apart. Expected cells with no check are NOT MEASURED: the model's gaps,
never passes. The result says, with numbers, what accepting the application still needs."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

MODEL_FILE = Path(__file__).resolve().parents[2] / "config" / "calidad.yaml"
DECIDED = ("ok", "aviso", "falta")


def load_model(path: Path | None = None) -> dict:
    return yaml.safe_load(Path(path or MODEL_FILE).read_text(encoding="utf-8")) or {}


def score(items: list[dict], model: dict | None = None) -> dict:
    """{"cells": {(dom, car, capa): {...}}, "domains": {...}, "characteristics": {...}, "unmapped": [...], ...}."""
    m = model or load_model()
    areas = m.get("areas") or {}
    cells: dict = defaultdict(lambda: {"ok": 0, "aviso": 0, "falta": 0, "pocos datos": 0, "fallan": []})
    unmapped = defaultdict(int)
    for it in items:
        where = areas.get(it.get("area"))
        if where == "agregado":
            continue
        if not where:
            unmapped[it.get("area") or "?"] += 1
            continue
        c = cells[tuple(where)]
        st = it.get("status")
        if st in c:
            c[st] += 1
        if st in ("aviso", "falta"):
            c["fallan"].append(it.get("name", ""))
    thr = float(m.get("umbral_aceptacion", 0.95))
    out_cells = {}
    for key, c in cells.items():
        n = sum(c[s] for s in DECIDED)
        sc = c["ok"] / n if n else None
        out_cells[key] = {**c, "n": n, "score": sc, "accepted": sc is not None and sc >= thr - 1e-9}
    for key in (tuple(x) for x in m.get("esperadas") or []):
        if key not in out_cells:
            out_cells[key] = {"ok": 0, "aviso": 0, "falta": 0, "pocos datos": 0, "fallan": [], "n": 0, "score": None,
                              "accepted": False, "unmeasured": True}

    def roll(idx: int) -> dict:
        agg: dict = defaultdict(lambda: {"ok": 0, "n": 0, "cells": 0, "unmeasured": 0, "accepted": 0})
        for key, c in out_cells.items():
            a = agg[key[idx]]
            a["ok"] += c["ok"]
            a["n"] += c["n"]
            a["cells"] += 1
            a["unmeasured"] += bool(c.get("unmeasured"))
            a["accepted"] += bool(c["accepted"])
        return {k: {**v, "score": (v["ok"] / v["n"]) if v["n"] else None} for k, v in agg.items()}

    total_n = sum(c["n"] for c in out_cells.values())
    return {"cells": out_cells, "domains": roll(0), "characteristics": roll(1), "layers": roll(2),
            "unmapped": dict(unmapped), "threshold": thr,
            "total": {"ok": sum(c["ok"] for c in out_cells.values()), "n": total_n,
                      "score": (sum(c["ok"] for c in out_cells.values()) / total_n) if total_n else None,
                      "cells": len(out_cells), "accepted": sum(c["accepted"] for c in out_cells.values()),
                      "unmeasured": sum(bool(c.get("unmeasured")) for c in out_cells.values())}}


def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.0f} %"


def markdown(res: dict, model: dict | None = None) -> str:
    m = model or load_model()
    D, C, L = m.get("dominios") or {}, m.get("caracteristicas") or {}, m.get("capas") or {}
    t = res["total"]
    lines = ["# Modelo de calidad: puntuación (petición #256; generado por `tennisbio calidad`, no editar)", "",
             f"**Total:** {_pct(t['score'])} de {t['n']} comprobaciones cumplidas · casillas aceptadas {t['accepted']} de "
             f"{t['cells']} (umbral {_pct(res['threshold'])}) · **sin medir: {t['unmeasured']}**", "",
             "## Por dominio", "", "| Dominio | Puntuación | Comprobaciones | Casillas aceptadas | Sin medir |", "|---|---|---|---|---|"]
    for k, v in sorted(res["domains"].items(), key=lambda kv: (kv[1]["score"] is None, kv[1]["score"] or 0)):
        lines.append(f"| {D.get(k, k)} | {_pct(v['score'])} | {v['ok']}/{v['n']} | {v['accepted']}/{v['cells']} | {v['unmeasured']} |")
    lines += ["", "## Por característica (ISO/IEC 25010)", "", "| Característica | Puntuación | Comprobaciones | Sin medir |", "|---|---|---|---|"]
    for k, v in sorted(res["characteristics"].items(), key=lambda kv: (kv[1]["score"] is None, kv[1]["score"] or 0)):
        lines.append(f"| {C.get(k, k)} | {_pct(v['score'])} | {v['ok']}/{v['n']} | {v['unmeasured']} |")
    lines += ["", "## Casillas (dominio × característica × capa)", "",
              "| Dominio | Característica | Capa | Puntuación | ok / decididas | pocos datos | Estado | Lo que falla |", "|---|---|---|---|---|---|---|---|"]
    order = sorted(res["cells"].items(), key=lambda kv: (not kv[1].get("unmeasured"), kv[1]["accepted"], kv[1]["score"] or 0))
    for (d, c, l), v in order:
        st = "SIN MEDIR" if v.get("unmeasured") else ("aceptada" if v["accepted"] else "no aceptada")
        bad = "; ".join(v["fallan"][:3]) + (f" (+{len(v['fallan']) - 3})" if len(v["fallan"]) > 3 else "")
        lines.append(f"| {D.get(d, d)} | {C.get(c, c)} | {L.get(l, l)} | {_pct(v['score'])} | {v['ok']}/{v['n']} | "
                     f"{v['pocos datos']} | {st} | {bad} |")
    if res["unmapped"]:
        lines += ["", "**Áreas de la auditoría sin casilla (añadirlas a `config/calidad.yaml`):** "
                  + ", ".join(f"{k} ({n})" for k, n in res["unmapped"].items())]
    return "\n".join(lines) + "\n"


def run(audit_json: Path, out_dir: Path) -> dict:
    items = json.loads(Path(audit_json).read_text(encoding="utf-8")).get("items", [])
    res = score(items)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "calidad.md").write_text(markdown(res), encoding="utf-8")
    js = {**res, "cells": [{"dominio": k[0], "caracteristica": k[1], "capa": k[2], **v} for k, v in res["cells"].items()]}
    (out_dir / "calidad.json").write_text(json.dumps(js, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
