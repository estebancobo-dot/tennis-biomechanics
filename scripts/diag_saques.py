"""Why points of HER serve have no serve of hers found (12-11: Osaka – Rybakina, 27 of 36, 75 %, «Saques por punto de
su saque», a known fault of B4 that stops the full analysis). The same points the audit counts (point_count.serve_gaps
over score.json, strokes.json, the main-camera shots, spotting, candidates, doubtful and dropped strokes); for each one
without her serve: its stretch, the main-camera shots in it, the scoreboard readings (who serves, score), what the
learned spotter saw (both players), the candidates and whose they were, her strokes found, the doubtful and dropped
ones, and the identity run (which player the near one is); plus a sheet of frames from the main camera's return to her
first stroke found, each labelled with what was detected next to it. Also where her serves outside her points fall.
Writes <output>/capturas_diag/diag_saques.json and saques_<min>.jpg (flat). Reads only.

    uv run python scripts/diag_saques.py --match f43dd2 [--max 12]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as _mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.point_count import clean_states, serve_gaps  # noqa: E402
from tennisbio.stage_times import manifests, roots_of  # noqa: E402

W, H, COLS = 480, 270, 4
NEAR_S = 0.45                 # a detection labels a frame when it is this close to it


def _load(d: Path, name: str, default=None):
    f = _mf.at(d, name)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default
    except (OSError, ValueError):
        return default


def _small(e: dict) -> dict:
    return {k: v for k, v in e.items() if isinstance(v, (int, float, str, bool)) or v is None}


def _in(xs, a, b, key="t"):
    return [x for x in xs if x.get(key) is not None and a <= float(x[key]) <= b]


def match_dir(cfg: dict, needle: str) -> Path | None:
    for r in roots_of(cfg):
        for man in manifests(r):
            d = man.parent.parent if man.parent.name == "etapas" else man.parent
            if needle.lower() in str(d).lower() and _mf.at(d, "score.json").exists():
                return d
    return None


def gather(d: Path) -> dict:
    """Everything serve_gaps reads, loaded as the audit does (audit.serve_coverage)."""
    scn = _load(d, "scenes.json") or {}
    fps = float(scn.get("fps") or 1.0)
    shots = [(sh["start"] / fps, sh["end"] / fps) for sh in scn.get("shots", []) if sh.get("main_camera")]
    cj = _load(d, "candidates.json")
    cands = (cj.get("candidates", cj) if isinstance(cj, dict) else cj) if cj is not None else None
    return {"readings": (_load(d, "score.json") or {}).get("readings") or [], "strokes": _load(d, "strokes.json", []),
            "shots": shots, "spotted": _load(d, "spotting.json"), "candidates": cands,
            "doubtful": _load(d, "strokes_doubtful.json", []) or [], "dropped": _load(d, "strokes_descartados.json"),
            "identity": _load(d, "identity.json") or {}}


def describe(g: dict, data: dict, states: list[dict]) -> dict:
    a, b = g["t0"], g["t1"]
    runs = data["identity"].get("runs") or []
    fps = float(data["identity"].get("fps") or 1.0)            # the runs' start and end are frames
    run = next((r for r in runs if r.get("start") is not None and r.get("end") is not None
                and float(r["start"]) / fps <= b and float(r["end"]) / fps >= a), None)
    return {**g, "min": round(a / 60, 2),
            "planos_camara_principal": [[round(s, 1), round(e, 1)] for s, e in data["shots"] if e > a and s < b],
            "marcador": [{"t": s["t"], "g": s["g"], "pts": s["pts"], "saca": s["server"]} for s in states
                         if a - 10 <= s["t"] <= b + 10],
            "detector": [_small(e) for e in _in(data["spotted"] or [], a, b)],
            "candidatos": [_small(c) for c in _in(data["candidates"] or [], a, b)],
            "golpes_suyos": [{"t": s.get("match_time_s"), "golpe": s.get("stroke"), "lado": s.get("side"),
                              "fuente": s.get("stroke_source"), "id": s.get("stroke_id")}
                             for s in _in(data["strokes"], a, b, "match_time_s")],
            "dudosos": [_small(s) for s in _in(data["doubtful"], a, b, "match_time_s")],
            "descartados": [_small(s) for s in _in(data["dropped"] or [], a, b)],
            "identidad": None if run is None else _small(run)}


def sheet(video: Path, g: dict, out: Path) -> str | None:
    """Frames every 0.6 s from the main camera's return (or the stretch's start) to 1 s after her first stroke found
    (or 7 s), at most 12, each labelled with the detections next to it."""
    import cv2
    import numpy as np

    from tennisbio.io.video import frames_at, probe

    s0 = float(g.get("shot_start", g["t0"]))
    first = [x["t"] for x in g["golpes_suyos"] if x["t"] is not None and x["t"] >= s0]
    end = min(float(g["t1"]), (min(first) + 1.0) if first else s0 + 7.0)
    times = [round(s0 + 0.6 * i, 2) for i in range(12) if s0 + 0.6 * i <= end]
    if not times:
        return None
    labels = []
    for t in times:
        lab = [f"{int(t // 60)}:{t % 60:04.1f}"]
        lab += [f"det {e.get('side')}/{e.get('kind')}" for e in g["detector"] if abs(float(e["t"]) - t) <= NEAR_S]
        lab += [f"suyo {x['lado']}/{x['golpe']}" for x in g["golpes_suyos"] if abs(float(x["t"]) - t) <= NEAR_S]
        labels.append(" · ".join(lab))
    items = list(zip((fr for _, fr in frames_at(probe(video), times)), labels))
    rows = max(1, (len(items) + COLS - 1) // COLS)
    img = np.full((rows * (H + 24) + 30, COLS * W, 3), 24, np.uint8)
    title = f"{g['min']} min · {g['cause']} · {len(g['detector'])} del detector · {len(g['golpes_suyos'])} suyos"
    cv2.putText(img, title, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
    for i, (fr, label) in enumerate(items):
        r, c = divmod(i, COLS)
        y, x = 30 + r * (H + 24), c * W
        if fr is not None:
            img[y:y + H, x:x + W] = cv2.resize(fr, (W, H))
        cv2.putText(img, label[:70], (x + 4, y + H + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 230, 120), 1,
                    cv2.LINE_AA)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return out.name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--max", type=int, default=12, help="hojas de fotogramas como mucho")
    a = ap.parse_args()
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    d = match_dir(cfg, a.match)
    if d is None:
        rep = {"error": f"ningún partido con marcador cuyo nombre contenga «{a.match}»"}
    else:
        data = gather(d)
        g = serve_gaps(data["readings"], data["strokes"], data["shots"], spotted=data["spotted"],
                       candidates=data["candidates"], doubtful=data["doubtful"], dropped=data["dropped"])
        states = clean_states(data["readings"])
        gaps = [describe(x, data, states) for x in g["gaps"] if not x.get("unseen")]
        probe_ = _load(d, "probe.json") or {}
        video = Path(probe_["path"]) if probe_.get("path") else None
        for x in gaps[:a.max]:
            try:
                x["hoja"] = sheet(video, x, dst / f"saques_{x['min']:05.2f}.jpg") if video and video.exists() else None
            except Exception as e:  # noqa: BLE001 — one sheet that fails leaves the rest
                x["hoja"] = f"error: {type(e).__name__}: {e}"[:200]
        serve_t = sorted(float(s["match_time_s"]) for s in data["strokes"]
                         if s.get("stroke") == "overhead" and s.get("match_time_s") is not None)
        # each serve of hers with the scoreboard states before and after it (are the 11 outside every point read the
        # first points of the games? a change of ends? the score not shown?)
        outside = []
        for t in serve_t:
            prev = max((s for s in states if s["t"] <= t), key=lambda s: s["t"], default=None)
            nxt = min((s for s in states if s["t"] > t), key=lambda s: s["t"], default=None)
            outside.append({"t": round(t, 1), "min": round(t / 60, 2),
                            "antes": None if prev is None else {"t": prev["t"], "g": prev["g"], "pts": prev["pts"],
                                                                "saca": prev["server"]},
                            "despues": None if nxt is None else {"t": nxt["t"], "g": nxt["g"], "pts": nxt["pts"],
                                                                 "saca": nxt["server"]}})
        rep = {"partido": str(d), "puntos_de_su_saque": g["points"], "con_saque": g["found"], "no_vistos": g["unseen"],
               "por_causa": g["by_cause"], "saques_caen_en": g.get("serves_at"),
               "primer_golpe_sin_saque": g.get("first_strokes_without_serve"),
               "detector_antes_del_primer_golpe": g.get("spotter_before_first"),
               "puntos_sin_golpes": g.get("no_strokes_points"), "huecos": gaps, "sus_saques": outside,
               "lecturas_marcador": len(data["readings"]), "estados": len(states)}
    (dst / "diag_saques.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("huecos", "sus_saques")}, ensure_ascii=False, indent=1,
                     default=str)[:4000])


if __name__ == "__main__":
    main()
