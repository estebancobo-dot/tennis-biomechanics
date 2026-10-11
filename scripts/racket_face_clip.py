"""Where the strings face in each stroke of a clip (8 key moments + per-frame JSON).

Runs after analyze_clip.py (reuses its caches) and adds the 3D hand model in the stroke windows.

    uv run python scripts/racket_face_clip.py clip.mp4 --out C:\\tenis\\output\\clip1 --strokes 0 3 5
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.clip_pipeline import run_clip  # noqa: E402
from tennisbio.phases import PHASES  # noqa: E402
from tennisbio.pose.wholebody3d import RTMW3D_URL, WholeBody3D  # noqa: E402
from tennisbio.racket import pick_racket, racket_from_polygon  # noqa: E402
from tennisbio.racket3d import Camera  # noqa: E402
from tennisbio.racket_face import face_track  # noqa: E402
from tennisbio.render import PHASE_TITLES, crop_around, draw_pose, draw_racket, label, strip  # noqa: E402


def draw_face(img, head, n, cam, scale):
    """Arrow from the head along the projected face normal; filled tip = towards the net (away)."""
    d = cam.project_dir(np.asarray(n))
    end = head + d * scale
    cv2.arrowedLine(img, tuple(map(int, head)), tuple(map(int, end)), (0, 230, 255), 3, cv2.LINE_AA, tipLength=0.3)
    toward_cam = float(np.asarray(n) @ cam.basis[2]) < 0
    cv2.circle(img, tuple(map(int, end)), 6, (0, 230, 255), 2 if toward_cam else -1, cv2.LINE_AA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--strokes", type=int, nargs="*", help="índices de golpe (por defecto todos)")
    ap.add_argument("--hand", default="right")
    ap.add_argument("--height-m", type=float, default=1.84)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--grip-close", type=float, default=15.0, help="grados que la empuñadura cierra la cara respecto a la palma")
    ap.add_argument("--camera-pitch", type=float, default=20.0)
    ap.add_argument("--wb3d", default=RTMW3D_URL, help="modelo RTMW3D (ruta local o URL)")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    out = Path(args.out)
    run = run_clip(args.video, out / "extract.npz", args.hand, args.height_m, imgsz=args.imgsz)
    cam = Camera(args.camera_pitch)
    wb = WholeBody3D(args.wb3d, args.device)
    cap = cv2.VideoCapture(str(args.video))
    sel = args.strokes if args.strokes else range(len(run.strokes))
    allres = {}
    for k in sel:
        r = run.strokes[k]
        i = r.impact_frame
        a, b = max(0, i - int(run.fps)), min(len(run.img), i + int(0.8 * run.fps) + 1)
        frames = {}
        cap.set(cv2.CAP_PROP_POS_FRAMES, a)
        for f in range(a, b):
            ok, fr = cap.read()
            if ok:
                frames[f] = fr
        track = face_track(frames, run.boxes, run.img, run.rackets, run.sk, run.height_px, args.height_m,
                           i, a, b, wb, cam, args.grip_close, fps=run.fps)
        by_frame = {t["frame"]: t for t in track}
        allres[k] = track
        tiles = []
        for name in PHASES:
            f = r.phases[name]["frame"]
            if f is None or f not in frames or run.boxes[f] is None:
                tiles.append(label(np.full((320, 260, 3), 20, np.uint8), [PHASE_TITLES[PHASES.index(name)], "no detectado"]))
                continue
            img = draw_pose(frames[f].copy(), run.img[f], run.sk, 3)
            wrist = run.img[f, run.sk["dom_wrist"]]
            poly = pick_racket(run.rackets[f], wrist, 0.3 * run.height_px)
            obs = racket_from_polygon(poly, wrist) if poly is not None else None
            t = by_frame.get(f, {})
            if obs is not None:
                draw_racket(img, obs, 3)
            if t.get("face") is not None:
                head = obs.head if obs is not None else wrist
                draw_face(img, head, t["face"], cam, 0.12 * run.height_px)
            tile = crop_around(img, run.boxes[f])
            label(tile, [PHASE_TITLES[PHASES.index(name)], f"{r.phases[name]['t_rel']:+.2f} s"], top=True)
            if t.get("face") is not None:
                src = ("silueta+mano" if t["hand_evidence"] else "silueta") if t["observed"] else "interpolado"
                label(tile, [f"cuerdas -> {t['points_to']}", f"cierre {t['tilt_deg']:+.0f}  giro {t['yaw_deg']:+.0f}  ({src})"], top=False)
            tiles.append(tile)
        img = strip(tiles, f"#{k}  orientación de las cuerdas  (flecha amarilla: hacia dónde miran; punto relleno = hacia la red, hueco = hacia la cámara)")
        cv2.imwrite(str(out / f"golpe_{k:02d}_cuerdas.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        ph = "  ".join(f"{p[:4]}:{by_frame[r.phases[p]['frame']]['points_to']}({by_frame[r.phases[p]['frame']]['tilt_deg']:+.0f})"
                       for p in PHASES if r.phases[p]["frame"] in by_frame and by_frame[r.phases[p]["frame"]].get("face"))
        hand_frac = np.mean([t.get("hand_evidence", False) for t in track])
        print(f"#{k:02d} mano 3D en {hand_frac * 100:.0f} % de fotogramas · {ph}", flush=True)
    (out / "cuerdas.json").write_text(json.dumps({str(k): v for k, v in allres.items()}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
