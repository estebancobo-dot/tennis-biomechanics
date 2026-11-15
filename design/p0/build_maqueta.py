"""P0.4 (15-11): the interactive mockup of the new web app, filled with the real numbers of a report.

The repository is public, so it keeps only this script and the page template (`maqueta.html`, no data); the built page,
with the numbers of the analysed matches, is written outside the repository and published as a private page.

    python design/p0/build_maqueta.py <report index.html> <output .html>

Every number comes from the report's DATA (the same strokes, measures, conclusions and rhythm the report shows): medians
per situation are plain medians of the near-side strokes (the app will use the report's adjustment by ball and match;
its conclusions and findings, copied here, already use it). A measure is shown in a situation only with at least
MIN_N strokes, and a difference from all strokes only when it is larger than the measure's noise (requirement 3).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MIN_N = 10
# phase → the report's per-stroke measures shown on its card (keys of DATA.metrics)
PHASE_KEYS = {
    "ready": ["split"],
    "takeback": [],
    "loaded": ["sh", "xf", "offArm", "rHead", "rFaceArm"],
    "acceleration": ["rDrop", "knee"],
    "impact": ["contactH", "lat", "elbow", "baseM", "head", "rFaceImp"],
    "extension": [],
    "finish": ["finishH", "rFaceFin"],
    "recovery": ["recov"],
    "feet": ["disp", "baseM"],
}
SITUATIONS = [
    ("todas", "Todas", lambda s: True),
    ("rapida", "Bola rápida", lambda s: s.get("fast") is True),
    ("lenta", "Bola lenta", lambda s: s.get("fast") is False),
    ("abierta", "Abierta", lambda s: s.get("wide") is True),
    ("corta", "Corta", lambda s: s.get("short") is True),
    ("baja", "Baja", lambda s: s.get("height") == "baja"),
    ("alta", "Alta", lambda s: s.get("height") == "alta"),
    ("carrera", "En carrera", lambda s: s.get("movement") == "en carrera"),
    ("parada", "Parada", lambda s: s.get("movement") == "parada"),
]
STROKE_KEYS = ("sh", "xf", "elbow", "contactH", "lat", "baseM", "head", "finishH", "split", "disp", "recov")


def report_data(path: Path) -> dict:
    html = path.read_text(encoding="utf-8")
    m = re.search(r"const DATA\s*=\s*", html)
    if not m:
        raise SystemExit(f"{path}: no DATA in the page")
    data, _ = json.JSONDecoder().raw_decode(html[m.end():])
    return data


def quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def stats(strokes: list[dict], key: str) -> dict | None:
    xs = [float(s["m"][key]) for s in strokes if isinstance((s.get("m") or {}).get(key), (int, float))]
    if len(xs) < MIN_N:
        return {"n": len(xs)} if xs else None
    return {"n": len(xs), "med": quantile(xs, 0.5), "p25": quantile(xs, 0.25), "p75": quantile(xs, 0.75)}


def shares(strokes: list[dict], field: str) -> list[tuple[str, int]]:
    out: dict[str, int] = {}
    for s in strokes:
        v = s.get(field)
        if v:
            out[v] = out.get(v, 0) + 1
    return sorted(out.items(), key=lambda kv: -kv[1])


def build(data: dict) -> dict:
    near = [s for s in data["strokes"] if s.get("side") == "near"]
    metrics = {m["k"]: {k: m.get(k) for k in ("name", "sub", "unit", "dec", "noise", "rel", "est")}
               for m in data["metrics"]}
    keys = sorted({k for ks in PHASE_KEYS.values() for k in ks} | set(STROKE_KEYS))
    sits = []
    for sid, label, keep in SITUATIONS:
        group = [s for s in near if keep(s)]
        sits.append({"id": sid, "label": label, "n": len(group),
                     "stats": {k: stats(group, k) for k in keys},
                     "stance": shares(group, "stance"), "finish": shares(group, "finishType"),
                     "movement": shares(group, "movement")})
    phases = []
    for p in data["learn"]["phases"]:
        phases.append({"id": p["id"], "title": p["title"], "focus": p.get("focus"), "when": p.get("when"),
                       "keys": PHASE_KEYS.get(p["id"], []),
                       "checks": [{k: c.get(k) for k in ("label", "cue", "mistake", "drill")}
                                  for c in (p.get("checkpoints") or [])[:3]]})
    matches = []
    for i, m in enumerate(data["matches"]):
        mine = [s for s in data["strokes"] if s.get("match") == i]
        matches.append({"rival": m.get("rival"), "surf": m.get("surf"),
                        "near": sum(s.get("side") == "near" for s in mine),
                        "far": sum(s.get("side") == "far" for s in mine)})
    strokes = [{"id": s["id"], "match": s.get("match"), "set": s.get("set"), "score": s.get("score"),
                "outcome": s.get("outcome"), "stance": s.get("stance"), "movement": s.get("movement"),
                "finish": s.get("finishType"), "tAvail": s.get("tAvail"), "quality": s.get("quality"),
                "fast": s.get("fast"), "wide": s.get("wide"), "short": s.get("short"), "height": s.get("height"),
                "x": s.get("x"), "y": s.get("y"), "shotX": s.get("shotX"), "shotY": s.get("shotY"),
                "shotIn": s.get("shotIn"), "shotDir": s.get("shotDir"), "phases": s.get("phases"),
                "review": s.get("review") or [], "m": {k: (s.get("m") or {}).get(k) for k in STROKE_KEYS}}
               for s in near]
    findings = [{"k": f["k"], "t": f["t"], "c": f["c"], "verdict": (f.get("v") or [None, None])[1],
                 "level": (f.get("v") or [None])[0], **{k: f["e"].get(k) for k in ("d", "lo", "hi", "na", "nb", "ma", "mb")}}
                for f in data.get("findings") or []]
    return {"player": data["player"]["name"], "stroke": "Derecha", "generated": data.get("generated"),
            "known": data.get("known_differences") or [], "conclusions": data.get("conclusions") or [],
            "findings": findings, "metrics": {k: metrics[k] for k in keys if k in metrics},
            "situations": sits, "phases": phases, "plan": data["learn"].get("plan") or [],
            "rhythm": data["rhythm"], "matches": matches, "strokes": strokes,
            "n_near": len(near), "n_far": sum(s.get("side") == "far" for s in data["strokes"])}


def main(argv: list[str]) -> None:
    src, out = Path(argv[1]), Path(argv[2])
    page = (Path(__file__).with_name("maqueta.html")).read_text(encoding="utf-8")
    payload = json.dumps(build(report_data(src)), ensure_ascii=False, separators=(",", ":"))
    out.write_text(page.replace("/*DATA*/null", payload), encoding="utf-8")
    print(f"{out}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv)
