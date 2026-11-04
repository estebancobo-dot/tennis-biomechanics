"""Time budgets of the stages, alarms while they run, and the forecast before a long run (B1, 03-11).

Why: request 84 (the reference of the 4 matches) spent ~80 min per whole match in the identity stage, ~3 s per
clothes frame, and nobody knew for hours: the stage had only ever been timed from its caches (seconds) or on a
35-min clip. Three pieces, all automatic:

- **Rates.** Every stage that really computes (≥ 60 s) records on this machine its seconds per minute of video and,
  when it reports progress, its seconds per unit (frame, stroke…) in <output>/ritmos.json.
- **Alarm.** While a stage runs, its seconds per unit are compared with its budget: `budgets.<stage>` of the
  configuration (s per unit) or, without one, the median of its own past rates here. Above `budgets.factor` (2×)
  once warmed up (5 % done and 2 min), one line «ALARMA» goes to the log and to <output>/alarmas.json, which the PC
  uploads with every heartbeat (every 10 min, even while a long job runs).
- **Forecast.** Before a long run: per match, the stages that would re-run (their fingerprints changed) and how long
  each would take from its measured rate per minute of video; a stage never measured on a whole match (≥ 60 min of
  video) is said, so it is measured alone first (docs/plan_corto_plazo.md, rules).
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

RATES = "ritmos.json"
ALARMS = "alarmas.json"
KEEP = 30                     # entries kept per stage
WHOLE_MATCH_MIN = 60.0        # minutes of video that make a rate one of a whole match
REAL_RUN_S = 60.0             # a stage that took less only read its caches: not a rate
WARM_FRAC, WARM_S = 0.05, 120.0


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(path: Path, data: dict):
    from .pipeline import write_atomic
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, json.dumps(data, ensure_ascii=False, indent=1))
    except OSError:
        pass


def _add(path: Path, stage: str, entry: dict):
    d = _load(path)
    d.setdefault(stage, []).append(entry)
    d[stage] = d[stage][-KEEP:]
    _save(path, d)


def record_unit(out: Path, stage: str, s_per_unit: float, units: int, match: str):
    """The finished stage's seconds per unit of its progress (a whole-stage figure)."""
    if units > 0 and s_per_unit > 0:
        _add(Path(out) / RATES, f"{stage}:unidad", {"s": round(s_per_unit, 4), "units": int(units), "match": match,
                                                   "date": time.strftime("%Y-%m-%d %H:%M")})


def record_stage(out: Path, stage: str, seconds: float, video_min: float | None, match: str):
    """The finished stage's seconds per minute of video, when it really computed (≥ REAL_RUN_S)."""
    if seconds >= REAL_RUN_S and video_min and video_min > 0:
        _add(Path(out) / RATES, f"{stage}:minuto", {"s": round(seconds / video_min, 3), "video_min": round(video_min, 1),
                                                   "match": match, "date": time.strftime("%Y-%m-%d %H:%M")})


def budget_per_unit(cfg: dict, out: Path, stage: str) -> tuple[float | None, str]:
    """(seconds per unit allowed before the alarm factor, where it comes from)."""
    b = (cfg.get("budgets") or {}).get(stage)
    if b:
        return float(b), "configuración"
    past = [e["s"] for e in _load(Path(out) / RATES).get(f"{stage}:unidad", [])]
    if len(past) >= 2:
        return float(statistics.median(past)), f"mediana de {len(past)} ejecuciones aquí"
    return None, ""


def check(cfg: dict, out: Path, stage: str, elapsed: float, done: int, total: int) -> str | None:
    """The alarm text when the running stage goes over its budget × factor, else None."""
    if not total or done <= 0 or done / total < WARM_FRAC or elapsed < WARM_S:
        return None
    b, why = budget_per_unit(cfg, out, stage)
    if not b:
        return None
    factor = float((cfg.get("budgets") or {}).get("factor", 2.0))
    rate = elapsed / done
    if rate <= factor * b:
        return None
    left = rate * (total - done)
    return (f"{stage}: {rate:.2f} s por unidad frente a {b:.2f} de presupuesto ({why}), {rate / b:.1f} veces; "
            f"a este ritmo quedan {left / 60:.0f} min")


def raise_alarm(out: Path, match: str, stage: str, text: str):
    p = Path(out) / ALARMS
    d = _load(p)
    d.setdefault("alarmas", []).append({"hora": time.strftime("%Y-%m-%d %H:%M:%S"), "partido": match, "etapa": stage,
                                        "texto": text})
    d["alarmas"] = d["alarmas"][-50:]
    _save(p, d)


def per_minute(out: Path, stage: str) -> tuple[float | None, bool]:
    """(median seconds per minute of video of a stage here, whether one of them was a whole match)."""
    es = _load(Path(out) / RATES).get(f"{stage}:minuto", [])
    if not es:
        return None, False
    return float(statistics.median(e["s"] for e in es)), any(e.get("video_min", 0) >= WHOLE_MATCH_MIN for e in es)


def forecast(rows: list[dict], out: Path) -> tuple[str, float]:
    """rows: [{"match", "video_min", "stages": {name: "ok"|"stale"|"upstream"|"missing"}, "seconds": {name: last s}}] →
    (markdown, total seconds). A stage without a whole-match rate is flagged, and its estimate is the larger of its
    rate × minutes and its last time."""
    L = ["# Previsión antes de ejecutar", "",
         "| Partido | Etapa | Estado | Estimación | Base de la estimación |", "|---|---|---|---|---|"]
    total, maybe, unmeasured = 0.0, 0.0, set()
    for r in rows:
        for n, st in r["stages"].items():
            if st == "ok":
                continue
            rate, whole = per_minute(out, n)
            last = (r.get("seconds") or {}).get(n) or 0.0
            est = max(rate * r["video_min"], last) if rate and r.get("video_min") else last
            basis = ("medido en partido entero" if whole else
                     "**sin medir en partido entero**" if rate else "**sin medir aquí**")
            if st == "upstream":          # re-runs only if a stage above comes out different (pipeline 1.7)
                maybe += est
                L.append(f"| {r['match']} | {n} | solo si cambia lo de arriba | hasta {est / 60:.0f} min | {basis} |")
                continue
            if not whole:
                unmeasured.add(n)
            total += est
            L.append(f"| {r['match']} | {n} | {'por rehacer' if st == 'stale' else 'falta'} | "
                     f"{est / 60:.0f} min | {basis} |")
    L += ["", f"**Total estimado: {total / 3600:.1f} h**"
          + (f" (y hasta {maybe / 3600:.1f} h más si cambian los resultados de las etapas de arriba)." if maybe else ".")]
    if unmeasured:
        L.append(f"Etapas sin medir en un partido entero: {', '.join(sorted(unmeasured))} → se miden antes, solas.")
    return "\n".join(L) + "\n", total
