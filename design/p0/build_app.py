"""P0.4 (15-11, #302): the navigable mockup of the whole desktop application, filled with real data.

The repository is public: it keeps this script and the template (`aplicacion.html`, no data); the built page is
written outside it and published privately.

    python design/p0/build_app.py <report index.html> <audit json> <queue estado.md> <matches json> <output .html>

Everything shown comes from those files and from config/players: the report's strokes, measures, lesson content,
conclusions and rhythm (the beta of 15-11); the audit and the quality model; the cloud queue as it is now; the match
catalogue. What a file name says (tournament, round, date) is shown as read from the file name. Nothing is invented:
what the mockup cannot know (videos, photos, disk use) is a marked placeholder.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_maqueta import MIN_N, quantile, report_data  # noqa: E402

M_TO_LEARN = None   # filled from the report (DATA.metric_rel)
ROUNDS = {"r1": "1.ª ronda", "r2": "2.ª ronda", "r3": "3.ª ronda", "r4": "4.ª ronda", "quarter-final": "cuartos de final",
          "semi-final": "semifinal", "polufinal": "semifinal", "final": "final"}
TOURNAMENTS = {"us-open": "US Open", "yusipopen": "US Open", "miami": "Miami", "indian-wells": "Indian Wells"}


def from_file_name(mid: str) -> dict:
    """Tournament, round and date as the file name says them (marked as such in the page)."""
    out = {}
    for k, v in TOURNAMENTS.items():
        if k in mid:
            out["torneo"] = v
            break
    for k, v in sorted(ROUNDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(^|-){re.escape(k)}(-|$)", mid):
            out["ronda"] = v
            break
    y = re.search(r"(20\d\d)", mid)
    d = re.search(r"(\d\d)-(\d\d)-(20\d\d)", mid)
    if d:
        out["fecha"] = f"{d.group(1)}-{d.group(2)}-{d.group(3)}"
    elif y:
        out["fecha"] = y.group(1)
    return out


def players() -> list[dict]:
    out = []
    for f in sorted((ROOT / "config" / "players").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        out.append({"id": f.stem, "name": d.get("name"), "hand": d.get("hand"), "backhand": d.get("backhand"),
                    "height_m": d.get("height_m"), "ficha": True})
    return out


def stats(xs: list[float]) -> dict | None:
    xs = [float(x) for x in xs if isinstance(x, (int, float))]
    if len(xs) < MIN_N:
        return {"n": len(xs)} if xs else None
    return {"n": len(xs), "med": quantile(xs, .5), "p25": quantile(xs, .25), "p75": quantile(xs, .75)}


SITUATIONS = [
    ("todas", "Todas", lambda s: True), ("rapida", "Bola rápida", lambda s: s.get("fast") is True),
    ("lenta", "Bola lenta", lambda s: s.get("fast") is False), ("alta", "Alta", lambda s: s.get("height") == "alta"),
    ("baja", "Baja", lambda s: s.get("height") == "baja"), ("abierta", "Abierta", lambda s: s.get("wide") is True),
    ("corta", "Corta", lambda s: s.get("short") is True), ("profunda", "Profunda", lambda s: s.get("short") is False),
    ("carrera", "En carrera", lambda s: s.get("movement") == "en carrera"),
    ("parada", "Parada", lambda s: s.get("movement") == "parada"), ("salto", "En salto", lambda s: s.get("movement") == "en el aire"),
    ("ataque", "Ataque", lambda s: (s.get("cl") or {}).get("intent") == "ataque"),
    ("defensa", "Defensa", lambda s: (s.get("cl") or {}).get("intent") == "defensa"),
]


def queue(estado_md: str) -> dict:
    head = next((l for l in estado_md.splitlines() if l.startswith("Última vuelta")), "")
    rows = []
    for l in estado_md.splitlines():
        if l.startswith("| ") and not l.startswith("| Trabajo") and not l.startswith("|---"):
            c = [x.strip() for x in l.strip().strip("|").split(" | ")]
            if len(c) >= 6:
                rows.append({"id": c[0], "accion": c[1], "partido": c[2], "estado": c[3], "donde": c[4], "nota": c[5][:220]})
    k = re.search(r"Kaggle dice ([\d.]+) h usadas de ([\d.]+)", head)
    m = re.search(r"quedan ([\d.]+) \$ de ([\d.]+) \$", head)
    return {"head": head, "jobs": rows,
            "kaggle": {"used": float(k.group(1)), "total": float(k.group(2))} if k else None,
            "modal": {"left": float(m.group(1)), "total": float(m.group(2))} if m else None}


def quality(audit: dict) -> dict:
    from tennisbio.quality_model import load_model, score
    model = load_model()
    items = audit.get("items", [])
    for it in items:                       # the 15-11 mapping (P0.2) on the beta audit, made before it
        if it.get("name") == "Equivalencia entre infraestructuras":
            it["area"] = "Portabilidad"
        if it.get("name") == "Prueba de concepto medida":
            it["area"] = "Rendimiento de modelos"
    r = score(items, model)
    D, C, L = model.get("dominios", {}), model.get("caracteristicas", {}), model.get("capas", {})
    how = model.get("como_se_mide") or {}
    cells = [{"d": D.get(k[0], k[0]), "c": C.get(k[1], k[1]), "l": L.get(k[2], k[2]), "score": v["score"], "n": v["n"],
              "ok": v["ok"], "unmeasured": bool(v.get("unmeasured")), "accepted": v["accepted"],
              "fail": v["fallan"][:4], "how": how.get("/".join(k))} for k, v in r["cells"].items()]
    counts = {}
    for it in items:
        counts[it.get("status")] = counts.get(it.get("status"), 0) + 1
    fails = [{"name": it["name"], "detail": str(it.get("detail", ""))[:200], "area": it.get("area")}
             for it in items if it.get("status") == "falta" and it.get("area") != "Peticiones"][:30]
    return {"total": r["total"], "threshold": r["threshold"], "cells": cells, "counts": counts, "fails": fails,
            "domains": {D.get(k, k): v for k, v in r["domains"].items()}}


def build(data: dict, audit: dict, estado_md: str, match_list: list) -> dict:
    rel = data.get("metric_rel") or {}
    learn_to_m = {v: k for k, v in rel.items()}
    # the same measures under the lesson's keys (same quantity; the report's own unit)
    learn_to_m.update({"footwork.split_landing_vs_opp_s": "split", "impact.base_court_m": "baseM",
                       "footwork.recovery_start_s": "recov"})
    near = [s for s in data["strokes"] if s.get("side") == "near"]
    metrics = {m["k"]: {k: m.get(k) for k in ("name", "sub", "unit", "dec", "noise", "rel", "est")} for m in data["metrics"]}
    sits = []
    for sid, label, keep in SITUATIONS:
        g = [s for s in near if keep(s)]
        sits.append({"id": sid, "label": label, "n": len(g),
                     "m": {k: stats([(s.get("m") or {}).get(k) for s in g]) for k in metrics}})
    L = data["learn"]
    phases = [{"id": p["id"], "title": p["title"], "focus": p.get("focus"), "when": p.get("when"),
               "checks": [{**{k: c.get(k) for k in ("key", "label", "unit", "dec", "read", "cue", "mistake", "drill")},
                           "m": learn_to_m.get(c.get("key"))} for c in (p.get("checkpoints") or [])]}
              for p in L["phases"]]
    mnames = {m["id"]: m for m in data["matches"]}
    matches = []
    analysed = {m["id"] for m in data["matches"]}
    for i, mm in enumerate(match_list):
        mid = mm["id"]
        src = mnames.get(mid, {})
        mine = [s for s in data["strokes"] if data["matches"][s["match"]]["id"] == mid] if mid in analysed else []
        matches.append({"id": mid, "rival": mm.get("rival") or src.get("rival"), "analysed": mm.get("analizado", mid in analysed),
                        "surf": src.get("surf"), **from_file_name(mid),
                        "near": sum(s["side"] == "near" for s in mine), "far": sum(s["side"] == "far" for s in mine)})
    def legible(s):
        m = data["matches"][s["match"]]
        bits = [x for x in (("rápida" if s.get("fast") else None), (f"bola {s['height']}" if s.get("height") else None),
                            ("abierta" if s.get("wide") else None), ("corta" if s.get("short") else None)) if x]
        return {"rival": m.get("rival"), "set": s.get("set"), "score": s.get("score"), "bits": bits}
    strokes = [{"id": s["id"], "match": s["match"], **legible(s), "outcome": s.get("outcome"), "detail": s.get("outcomeDetail"),
                "stance": s.get("stance"), "movement": s.get("movement"), "finish": s.get("finishType"), "quality": s.get("quality"),
                "repr": s.get("repr"), "tAvail": s.get("tAvail"), "fast": s.get("fast"), "wide": s.get("wide"), "short": s.get("short"),
                "height": s.get("height"), "intent": (s.get("cl") or {}).get("intent"), "pressure": s.get("pressure"),
                "game": s.get("game"), "x": s.get("x"), "y": s.get("y"), "shotX": s.get("shotX"), "shotY": s.get("shotY"),
                "shotIn": s.get("shotIn"), "shotDir": s.get("shotDir"), "phases": s.get("phases"), "body": s.get("body"),
                "feet": s.get("feet"), "ball": s.get("ballMoments"), "review": s.get("review") or [],
                "m": {k: (s.get("m") or {}).get(k) for k in metrics},
                "lv": s.get("lv") or {}} for s in near]          # change 1 (§10): the checkpoints, stroke by stroke
    return {"generated": data.get("generated"), "player": data["player"], "stroke": data.get("stroke"),
            "known": data.get("known_differences") or [], "conclusions": data.get("conclusions") or [],
            "findings": data.get("findings") or [], "metrics": metrics, "situations": sits, "phases": phases,
            "plan": L.get("plan") or [], "symptoms": L.get("symptoms") or [], "not_tv": L.get("not_tv") or [],
            "glossary": L.get("glossary") or [], "why": L.get("why") or {}, "checks": L.get("checks") or {},
            "reliability": data.get("reliability") or {}, "rhythm": data.get("rhythm"), "strokes": strokes,
            "n_near": len(near), "n_far": sum(s["side"] == "far" for s in data["strokes"]),
            "players": players(), "matches": matches, "queue": queue(estado_md), "quality": quality(audit),
            "run_info": data.get("run_info")}


def main(argv: list[str]) -> None:
    report, audit, estado, matches, out = map(Path, argv[1:6])
    page = Path(__file__).with_name("aplicacion.html").read_text(encoding="utf-8")
    payload = build(report_data(report), json.loads(audit.read_text(encoding="utf-8")), estado.read_text(encoding="utf-8"),
                    json.loads(matches.read_text(encoding="utf-8")))
    out.write_text(page.replace("/*DATA*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
                   encoding="utf-8")
    print(f"{out}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv)
