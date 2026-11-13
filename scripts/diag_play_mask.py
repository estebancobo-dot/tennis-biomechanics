"""R22 (13-11): F3Set v17 came out equal to v16 stroke by stroke: the fix that stopped play_mask filling the start of a
shot changed nothing, and the Azarenka point is still given to the other player. Every court gap that stages.play_mask
fills (R16) with what surrounds it: its shot, how many court frames come before it in that shot and from which frame,
its length; and, around the given seconds, the strip frame by frame (cut, court found, play) with the identity runs
there. For the F3Set compilations of the tags given and the library matches given (the R16 serves of Osaka and Pegula:
which gaps a new rule must keep). Writes <output>/capturas_diag/diag_play_mask.json. Reads only.

    uv run python scripts/diag_play_mask.py --tags v15 v17 --match osaka pegula --window azaren:1090:1115
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.stages import play_mask  # noqa: E402


def _read(d: Path, name: str):
    f = mf.at(d, name)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def court_found(sc: dict, court: dict | None) -> np.ndarray:
    n = max([s["end"] for s in sc["shots"]] + [0])
    has = np.zeros(n, bool)
    for o in (court or {}).get("shots") or []:
        if o.get("H") is not None:
            has[o["start"]:o["end"]] = True
    return has


def play_mask_v6(sc: dict, court: dict | None) -> np.ndarray:
    """play_mask as it was in players v6 / score v13 (13-11 morning, F3Set v17): any gap after the court was found in
    the shot is filled, however briefly it was found. Kept here to show which gaps the 0.5 s rule stops filling."""
    from tennisbio.stages import COURT_GAP_FILL_S
    n = max([s["end"] for s in sc["shots"]] + [0])
    main = np.zeros(n, bool)
    for s in sc["shots"]:
        main[s["start"]:s["end"]] = s["main_camera"]
    if court is None or not court.get("shots"):
        return main
    has = court_found(sc, court)
    fill = int(round(COURT_GAP_FILL_S * float(sc.get("fps") or 10.0)))
    for s in sc["shots"]:
        a, b = int(s["start"]), int(s["end"])
        if not s["main_camera"] or not has[a:b].any():
            continue
        i = a
        while i < b and not has[i]:
            i += 1
        while i < b:
            if has[i]:
                i += 1
                continue
            j = i
            while j < b and not has[j]:
                j += 1
            if j - i <= fill:
                has[i:j] = True
            i = j
    return main & has


def filled_gaps(sc: dict, court: dict | None, mask=play_mask) -> list[dict]:
    """The stretches `mask` counts as play without the court found, with their shot, the court around them and whether
    today's play_mask still counts them."""
    fps = float(sc.get("fps") or 10.0)
    play = mask(sc, court)
    now = play_mask(sc, court)
    has = court_found(sc, court)[:len(play)]
    filled = play & ~has
    out = []
    edges = np.flatnonzero(np.diff(np.r_[0, filled.astype(int), 0]))
    for a, b in zip(edges[::2], edges[1::2]):
        shot = next((s for s in sc["shots"] if s["start"] <= a < s["end"]), None)
        s0, s1 = (int(shot["start"]), int(shot["end"])) if shot else (int(a), int(b))
        before, after = has[s0:a], has[b:s1]
        run = 0                                  # court frames without a break right before the gap
        while a - 1 - run >= s0 and has[a - 1 - run]:
            run += 1
        out.append({"t0": round(a / fps, 2), "t1": round(b / fps, 2), "len_s": round((b - a) / fps, 2),
                    "shot_s": [round(s0 / fps, 2), round(s1 / fps, 2)], "from_shot_start_s": round((a - s0) / fps, 2),
                    "court_frames_before": int(before.sum()), "court_run_before": run,
                    "first_court_frame_from_shot_start": int(np.flatnonzero(before)[0]) if before.any() else None,
                    "court_frames_after": int(after.sum()), "still_filled_now": bool(now[a:b].all())})
    return out


def strip(sc: dict, court: dict | None, ident: dict | None, t0: float, t1: float) -> dict:
    """Frame by frame between t0 and t1 s: | at a cut, court found (1/0), play (1/0); and the identity runs there."""
    fps = float(sc.get("fps") or 10.0)
    play = play_mask(sc, court)
    old = play_mask_v6(sc, court)
    has = court_found(sc, court)
    a, b = max(0, int(t0 * fps)), min(len(play), int(t1 * fps))
    cuts = {int(s["start"]) for s in sc["shots"]}
    main = np.zeros(len(play), bool)
    for s in sc["shots"]:
        main[s["start"]:s["end"]] = s["main_camera"]
    line = lambda arr: "".join(("|" if i in cuts else "") + ("1" if arr[i] else "0") for i in range(a, b))  # noqa: E731
    runs = []
    if ident:
        ifps = float(ident.get("fps") or fps)
        for r in ident.get("runs") or []:
            rs, re_ = float(r.get("start", 0)) / ifps, float(r.get("end", 0)) / ifps
            if rs < t1 and re_ > t0:
                runs.append({k: r.get(k) for k in ("start", "end", "near_is_target", "method", "clothes_margin",
                                                    "clothes_says", "cluster")} | {"t0": round(rs, 2), "t1": round(re_, 2)})
    return {"t0": t0, "t1": t1, "fps": fps, "first_frame": a, "main_camera": line(main), "court": line(has),
            "play_v6": line(old), "play": line(play), "identity_runs": runs}


def report(d: Path, windows: list[tuple[str, float, float]]) -> dict:
    sc, court, ident = _read(d, "scenes.json"), _read(d, "court.json"), _read(d, "identity.json")
    if not sc:
        return {"error": f"sin scenes.json en {d}"}
    g = filled_gaps(sc, court, play_mask_v6)       # what v6 filled (F3Set v17), each with whether it is filled now
    res = {"fps": float(sc.get("fps") or 10.0), "filled_gaps": g,
           "summary": {"gaps_v6": len(g), "seconds_v6": round(sum(x["len_s"] for x in g), 1),
                       "still_filled_now": sum(x["still_filled_now"] for x in g),
                       "dropped_now": [x["t0"] for x in g if not x["still_filled_now"]],
                       "with_at_most_3_court_frames_before": sum(x["court_run_before"] <= 3 for x in g),
                       "starting_within_2s_of_the_shot": sum(x["from_shot_start_s"] <= 2.0 for x in g)}}
    res["windows"] = [strip(sc, court, ident, t0, t1) for sub, t0, t1 in windows if sub.lower() in d.name.lower()]
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*", default=["v17"], help="carpetas salidas_<tag> de F3Set")
    ap.add_argument("--match", nargs="*", default=[], help="partidos de la biblioteca (parte del nombre)")
    ap.add_argument("--window", nargs="*", default=[], help="parte_del_nombre:t0:t1 (segundos)")
    a = ap.parse_args()
    windows = []
    for w in a.window:
        sub, t0, t1 = w.split(":")
        windows.append((sub, float(t0), float(t1)))
    cfg = load_config()
    out = Path((cfg.get("paths") or {}).get("output") or "output")
    rec = out.parent / "datasets" / "f3set" / "recall"
    rep: dict = {}
    for tag in a.tags:
        for d in sorted((rec / f"salidas_{tag}").glob("recall_*")):
            rep[f"{tag}/{d.name}"] = report(d, windows)
    if a.match:
        from tennisbio import layout
        from tennisbio.catalog import load_matches
        for m in load_matches(cfg):
            if any(s.lower() in m.id.lower() for s in a.match):
                rep[m.id] = report(layout.dir_of(out, m, cfg), windows)
    for k, v in rep.items():
        print(k, json.dumps(v.get("summary") or v.get("error"), ensure_ascii=False), flush=True)
    cd = out / "capturas_diag"
    cd.mkdir(parents=True, exist_ok=True)
    (cd / "diag_play_mask.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
