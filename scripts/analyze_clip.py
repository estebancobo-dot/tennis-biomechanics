"""Analyse a short clip end to end: track the player, find strokes, 8 moments, metrics and racket.

For clips (practice videos, excerpts): pose runs on every frame, so it is not the two-pass
pipeline used for full matches. Needs the optional YOLO backend: `uv sync --extra yolo`.

    uv run python scripts/analyze_clip.py clip.mp4 --out C:\\tenis\\output\\clip1
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.clip_pipeline import run_clip  # noqa: E402
from tennisbio.kinematics import to_body_frame  # noqa: E402
from tennisbio.phases import PHASES  # noqa: E402
from tennisbio.racket import pick_racket, racket_from_polygon  # noqa: E402
from tennisbio.render import PHASE_TITLES, crop_around, draw_pose, draw_racket, label, strip  # noqa: E402

STROKE_ES = {"forehand": "derecha", "backhand": "revés"}


def phase_caption(name: str, r, fps) -> list[str]:
    p, m, rk = r.phases[name], r.metrics, r.racket.get(name, {})
    lines = [PHASE_TITLES[PHASES.index(name)]]
    t = p["t_rel"]
    lines.append("no detectado" if t is None else f"{t:+.2f} s  conf {p['confidence']:.2f}")
    extra = {
        "ready": "split step" if p["method"] == "split_step_landing" else "sin split step claro",
        "loaded": f"hombros {m.get('shoulder_turn_loaded_deg') or 0:.0f}°  X {m.get('x_factor_deg') or 0:.0f}°",
        "impact": f"codo {m.get('elbow_impact_deg') or 0:.0f}°  altura {m.get('contact_height_pct') or 0:.0f}%",
        "extension": f"lateral {m.get('contact_lateral_pct') or 0:.0f}% alt.",
        "finish": f"muñeca {m.get('finish_wrist_height_pct') or 0:+.0f}% sobre cadera",
    }.get(name)
    if extra:
        lines.append(extra)
    if rk.get("detected"):
        lines.append(f"raqueta {rk['elevation_deg']:+.0f}°  cabeza {rk['head_above_wrist_cm']:+.0f} cm")
    elif name in r.racket:
        lines.append("raqueta no vista")
    return lines


def render_strip(cap, r, kp_img, boxes_t, rackets, sk, height_px, k):
    tiles = []
    for name in PHASES:
        f = r.phases[name]["frame"]
        if f is None or boxes_t[f] is None:
            tiles.append(label(np.full((320, 260, 3), 20, np.uint8), phase_caption(name, r, 0)))
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frame = cap.read()
        frame = draw_pose(frame, kp_img[f], sk, thickness=3)
        poly = pick_racket(rackets[f], kp_img[f, sk["dom_wrist"]], 0.25 * height_px)
        obs = racket_from_polygon(poly, kp_img[f, sk["dom_wrist"]]) if poly is not None else None
        if obs is not None:
            draw_racket(frame, obs, 3)
        tile = crop_around(frame, boxes_t[f])
        cap_lines = phase_caption(name, r, 0)
        label(tile, cap_lines[:2], top=True)
        label(tile, cap_lines[2:] or [" "], top=False)
        tiles.append(tile)
    head = (f"#{k}  {STROKE_ES[r.stroke]}  impacto {r.impact_frame / cap.get(cv2.CAP_PROP_FPS):.2f} s ({r.impact_source})"
            f"  cadena: {' > '.join(r.chain['order'])}{'  OK' if r.chain['proximal_to_distal'] else '  (desordenada)'}"
            + (f"  REVISAR: {', '.join(r.review)}" if r.review else ""))
    return strip(tiles, head)


def render_curves(path, r, img, sk, fps, height_px):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    from tennisbio.kinematics import joint_angle, line_turn

    i = r.impact_frame
    a, b = max(0, i - int(fps)), min(len(img), i + int(0.8 * fps) + 1)
    w = img[a:b]
    body = to_body_frame(w, sk, height_px)
    t = (np.arange(a, b) - i) / fps
    fig, ax = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True)
    ax[0].plot(t, line_turn(w, sk, "shoulder"), label="giro hombros (°)")
    ax[0].plot(t, line_turn(w, sk, "hip"), label="giro cadera (°)")
    ax[0].plot(t, joint_angle(body[:, sk["dom_shoulder"]], body[:, sk["dom_elbow"]], body[:, sk["dom_wrist"]]), label="codo (°)")
    ax[1].plot(t, body[:, sk["dom_wrist"], 1] * 100, label="muñeca dominante sobre la cadera (% altura)")
    rt = np.array([[x if x is not None else np.nan for x in row] for row in r.racket_track], float)
    if len(rt):
        ax[1].plot(rt[:, 0], rt[:, 2] / 1.84, label="cabeza de raqueta sobre la muñeca (% altura)")
        ax[2].plot(rt[:, 0], rt[:, 1], label="elevación de la raqueta (°, +90 = vertical arriba)")
    for x in ax:
        for name in PHASES:
            tr = r.phases[name]["t_rel"]
            if tr is not None:
                x.axvline(tr, color="0.6", lw=0.8, ls="--")
        x.legend(loc="upper left", fontsize=8)
        x.grid(alpha=0.3)
    for name in PHASES:
        tr = r.phases[name]["t_rel"]
        if tr is not None:
            ax[0].text(tr, ax[0].get_ylim()[1], str(PHASES.index(name) + 1), ha="center", va="bottom", fontsize=9)
    ax[2].set_xlabel("tiempo respecto al impacto (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", help="npz de tennisbio.pose.yolo.extract (se crea si no existe)")
    ap.add_argument("--hand", default="right")
    ap.add_argument("--height-m", type=float, default=1.84)
    ap.add_argument("--imgsz", type=int, default=960, help="resolución de inferencia (1280 para planos generales de TV)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache or out / "extract.npz")
    run = run_clip(args.video, cache, args.hand, args.height_m, imgsz=args.imgsz)
    cap = cv2.VideoCapture(str(args.video))
    for k, (imp, r) in enumerate(zip(run.impacts, run.strokes)):
        cv2.imwrite(str(out / f"golpe_{k:02d}_fases.jpg"),
                    render_strip(cap, r, run.img, run.boxes, run.rackets, run.sk, run.height_px, k), [cv2.IMWRITE_JPEG_QUALITY, 88])
        render_curves(out / f"golpe_{k:02d}_curvas.png", r, run.img, run.sk, run.fps, run.height_px)
        ph = " ".join(f"{p[:4]}:{r.phases[p]['t_rel']:+.2f}" if r.phases[p]["t_rel"] is not None else f"{p[:4]}:--" for p in PHASES)
        print(f"#{k:02d} {imp.t:6.2f}s {STROKE_ES[r.stroke]:8} {ph}  cadena {'>'.join(r.chain['order'])}  revisar={r.review}")
    results = run.strokes
    (out / "golpes.json").write_text(json.dumps([r.to_dict() for r in results], indent=1, default=float), encoding="utf-8")
    print(f"\nResultados en {out}")


if __name__ == "__main__":
    main()
