"""Why a broadcast's scoreboard gives no server (09-11: Indian Wells and Miami 2026, 0 serve votes for the identity):
for each match, a few crops of its scoreboard at the times score.json read it, each enlarged with what the reader saw
(OCR words, the colour mask of the serve marker, the per-frame marker and the server finally kept), plus one whole
frame to see where the scoreboard is, and diag_marcador.json with the counts per match (readings, games, points,
server 0/1/None, the learned marker of score v7). For Claude to look at; nothing is recomputed.

    uv run python scripts/diag_scoreboard.py [OUT_DIR] [--match ID ...] [--n 6]
Default OUT_DIR: <output>/capturas_diag (uploaded to pc-logs/capturas_diag); files marcador_<match>_<k>.jpg."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def counts(score: dict) -> dict:
    rd = score.get("readings", [])
    return {"readings": len(rd), "names": score.get("names"), "opponent": score.get("opponent"),
            "roi": score.get("roi"), "server": dict(Counter(str(r.get("server")) for r in rd)),
            "server_marker": dict(Counter(str(r.get("server_marker", r.get("server"))) for r in rd)),
            "server_check": score.get("server_check"),
            "games_distinct": len({json.dumps(r.get("games")) for r in rd}),
            "points": dict(Counter(json.dumps(r.get("points")) for r in rd).most_common(8)),
            "shots_tried": sum(x.get("tried", 0) for x in score.get("shots", [])),
            "shots_read": sum(x.get("read", 0) for x in score.get("shots", []))}


def pick(readings: list, n: int) -> list:
    """n readings spread over the match, half with each server value seen (so both rows' marker show)."""
    if not readings:
        return []
    by = {}
    for r in readings:
        by.setdefault(str(r.get("server_marker", r.get("server"))), []).append(r)
    out = []
    for group in by.values():
        k = max(1, n // len(by))
        out += [group[int(i)] for i in np.linspace(0, len(group) - 1, min(k, len(group)))]
    return sorted(out, key=lambda r: r["t"])[:n]


def sheet(frame, roi, items, names, reading) -> np.ndarray:
    from tennisbio.scoreboard import parse

    x0, y0, x1, y1 = roi
    crop = frame[y0:y1, x0:x1]
    st = parse(items, tuple(names), crop)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] > 110) & (hsv[..., 2] > 120)).astype(np.uint8) * 255
    s = max(1, int(round(900 / max(crop.shape[1], 1))))
    big = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
    mk = cv2.cvtColor(cv2.resize(m, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
    for box, text, _ in items:
        b = (np.asarray(box, float) * s).astype(np.int32)
        cv2.polylines(big, [b], True, (0, 200, 255), 1)
    lines = [f"t={reading['t']:.1f}s games={reading.get('games')} points={reading.get('points')} "
             f"server kept={reading.get('server')} marker={reading.get('server_marker', reading.get('server'))}",
             f"now: parse={'none' if st is None else st.games} marker={None if st is None else st.server}",
             "ocr: " + " | ".join(str(t) for _, t, _ in items)[:150]]
    pad = np.full((22 * len(lines) + 8, big.shape[1], 3), 20, np.uint8)
    for i, ln in enumerate(lines):
        cv2.putText(pad, ln, (6, 20 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 230, 140), 1, cv2.LINE_AA)
    return np.vstack([big, mk, pad])


def diag(m, cfg, root: Path, out: Path, n: int, times: list[float] | None = None) -> dict:
    from tennisbio import layout
    from tennisbio import match_files as mf
    from tennisbio.scoreboard import ScoreReader

    d = layout.dir_of(root, m, cfg)
    f = mf.at(d, "score.json")
    if not f.exists():
        return {"match": m.id, "error": f"sin score.json en {d}"}
    score = json.loads(f.read_text(encoding="utf-8"))
    res = {"match": m.id, **counts(score)}
    video = pipeline.Context(m, cfg, d).video
    if not Path(video).exists():
        return {**res, "error": "sin vídeo"}
    names = score.get("names") or []
    rd = score.get("readings", [])
    reader = ScoreReader(*names) if len(names) == 2 and all(names) else None
    if reader is None:
        return {**res, "error": "sin nombres"}
    saved = []
    if times:                       # 11-11: moments with NO reading (why the reader missed them): what it sees there
        roi0 = score.get("roi")
        # was the moment sampled as play (main camera with the court found)? and what does a full read() say?
        try:
            sc = json.loads(mf.at(d, "scenes.json").read_text(encoding="utf-8"))
            court = json.loads(mf.at(d, "court.json").read_text(encoding="utf-8")) if mf.at(d, "court.json").exists() else None
            play_m = stages.play_mask(sc, court or None)
            fps_s = float(sc["fps"])
        except Exception as e:  # noqa: BLE001 — the crops still help
            play_m, fps_s = None, 1.0
            res["play_mask_error"] = str(e)[:200]
        res["momentos"] = []
        for k, t in enumerate(times):
            fr = stages.grab_frame(Path(video), float(t))
            if fr is None:
                continue
            fresh = ScoreReader(*names)
            st = fresh.read(fr)
            near = [x for x in rd if abs(x["t"] - t) < 60]
            res["momentos"].append({"t": t, "juego": None if play_m is None else bool(int(t * fps_s) < len(play_m) and play_m[int(t * fps_s)]),
                                    "read": None if st is None else st.to_dict().get("games"),
                                    "lecturas_a_menos_de_60s": len(near)})
            small = cv2.resize(fr, (960, int(fr.shape[0] * 960 / fr.shape[1])))
            cv2.imwrite(str(out / f"marcador_{m.id[:40]}_t{int(t)}_entero.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 80])
            saved.append(f"marcador_{m.id[:40]}_t{int(t)}_entero.jpg")
            if roi0:
                roi = [int(v) for v in roi0]
                items = reader._items(fr[roi[1]:roi[3], roi[0]:roi[2]], cls=False)
                img = sheet(fr, roi, items, names, {"t": float(t), "games": None, "points": None, "server": None})
                p = out / f"marcador_{m.id[:40]}_t{int(t)}.jpg"
                cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                saved.append(p.name)
        return {**res, "images": saved}
    for k, r in enumerate(pick(rd, n)):
        fr = stages.grab_frame(Path(video), float(r["t"]))
        if fr is None:
            continue
        if k == 0:
            small = cv2.resize(fr, (960, int(fr.shape[0] * 960 / fr.shape[1])))
            cv2.imwrite(str(out / f"marcador_{m.id}_entero.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        roi = score.get("roi")
        if not roi:
            reader.roi = None
            if not reader.locate(fr):
                continue
            roi = reader.roi
        roi = [int(v) for v in roi]
        items = reader._items(fr[roi[1]:roi[3], roi[0]:roi[2]], cls=False)
        img = sheet(fr, roi, items, names, r)
        p = out / f"marcador_{m.id}_{k}.jpg"
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        saved.append(p.name)
    if not rd:                      # nothing read: whole frames of play, to see whether there is a scoreboard at all
        sc = mf.at(d, "scenes.json")
        if sc.exists():
            s = json.loads(sc.read_text(encoding="utf-8"))
            mains = [x for x in s["shots"] if x["main_camera"]]
            for k, x in enumerate(mains[:: max(1, len(mains) // 4)][:4]):
                fr = stages.grab_frame(Path(video), (x["start"] + x["end"]) / 2 / s["fps"])
                if fr is not None:
                    cv2.imwrite(str(out / f"marcador_{m.id}_sin_lectura_{k}.jpg"),
                                cv2.resize(fr, (960, int(fr.shape[0] * 960 / fr.shape[1]))), [cv2.IMWRITE_JPEG_QUALITY, 80])
                    saved.append(f"marcador_{m.id}_sin_lectura_{k}.jpg")
    return {**res, "images": saved}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--match", nargs="+")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--times", default="", help="seconds without a reading to look at, comma separated (e.g. 200,700,1100)")
    args = ap.parse_args()
    cfg = load_config()
    root = Path(cfg.get("paths", {}).get("output", "output"))
    out = Path(args.out) if args.out else root / "capturas_diag"
    out.mkdir(parents=True, exist_ok=True)
    rep = []
    for m in load_matches(cfg):
        if args.match and not any(x in m.id for x in args.match):
            continue
        try:
            r = diag(m, cfg, root, out, args.n, [float(x) for x in args.times.split(",") if x.strip()] or None)
        except Exception as e:  # noqa: BLE001 — one broken match never stops the others
            r = {"match": m.id, "error": f"{type(e).__name__}: {e}"[:300]}
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rep.append(r)
    (out / "diag_marcador.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
