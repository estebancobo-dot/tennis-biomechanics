"""Prueba rápida de todo el pipeline con unos minutos de un partido real (antes de los 20 GB).

Corta un trozo del vídeo sin recodificar, ejecuta todas las etapas, genera el informe y estima
cuánto tardaría el partido entero.

    uv run python scripts/smoke_test.py "C:\\tenis\\videos\\partido1.mp4" --player rybakina --opponent "Aryna Sabalenka" --start 1800 --minutes 4
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import Match, load_player  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.io.video import probe  # noqa: E402
from tennisbio.report import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--player", default="rybakina")
    ap.add_argument("--opponent", default="", help="nombre del rival tal como sale en el marcador (para el OCR)")
    ap.add_argument("--start", type=float, default=None,
                    help="segundo de inicio del trozo (por defecto: un tramo de juego buscado automáticamente)")
    ap.add_argument("--minutes", type=float, default=4)
    args = ap.parse_args()

    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output")) / "_smoke"
    out_root.mkdir(parents=True, exist_ok=True)
    src = Path(args.video)
    full = probe(src).duration
    if args.start is None:            # searched once per video; remembered in _smoke/tramo.json
        memo = out_root / "tramo.json"
        key = f"{src.name}|{src.stat().st_size}"
        try:
            known = json.loads(memo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            known = {}
        if key in known:
            args.start = float(known[key])
            print(f"Tramo de juego (ya buscado): minuto {args.start / 60:.0f}")
        else:
            args.start = find_play(src, full, args.minutes * 60)
            known[key] = args.start
            memo.write_text(json.dumps(known, ensure_ascii=False), encoding="utf-8")
    if args.start + args.minutes * 60 > full:          # short video: take the piece from its first third
        args.start = max(0.0, min(full * 0.3, full - args.minutes * 60))
    from tennisbio.catalog import ascii_id
    clip = out_root / f"{ascii_id(src.stem, 40)}_{int(args.start)}_{int(args.minutes)}m{src.suffix}"
    if not clip.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(args.start), "-i", str(src), "-t", str(args.minutes * 60),
                        "-c", "copy", str(clip)], check=True)
    match = Match(f"smoke_{ascii_id(src.stem, 40)}", clip, load_player(args.player), opponent=args.opponent)
    ctx = pipeline.Context(match, cfg, out_root / match.id)
    t0 = time.time()
    print(f"Análisis del tramo: empieza {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    done = pipeline.run(ctx)
    total = time.time() - t0
    print(f"Análisis del tramo: termina {time.strftime('%Y-%m-%d %H:%M:%S')} ({total / 60:.1f} min)", flush=True)
    manifest = json.loads((ctx.dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"\nEtapas ejecutadas: {', '.join(done) or 'ninguna (ya estaba al día)'}")
    for name, m in manifest.items():
        print(f"  {name:11} {m['seconds']:7.1f} s  {m['summary']}")
    diagnostics(ctx, out_root / "diag")
    report = build([match], out_root, out_root / "informe")
    from tennisbio.export import export
    exp = export([match], out_root, out_root / "exportar", strokes_all=True)
    if "players" in done and "fine" in done:        # a partial re-run (caches) says nothing about the time
        print(f"\nTotal {total / 60:.1f} min para {args.minutes:g} min de vídeo → partido de {full / 60:.0f} min "
              f"≈ {total * full / (args.minutes * 60) / 3600:.1f} h (estimación lineal)")
    elif done:
        print("\n(Solo se rehicieron algunas etapas: el tiempo no sirve para estimar un partido)")
    print(f"Informe: {report}")
    print(f"Vídeos, montajes y resumen PDF: {exp}")
    # the audit of these outputs against the requirements, with screenshots of the report as the
    # user sees it (uploaded to Claude with the logs)
    from tennisbio.cli import run_audit
    try:
        run_audit(out_root, report.parent, out_root / "auditoria")
    except Exception as e:                  # the test itself went well: never fail it for the audit
        print(f"AVISO: la auditoría no se pudo hacer ({e})")


def find_play(video: Path, full: float, need_s: float, step_s=60.0) -> float:
    """Start of a stretch of match play: a broadcast begins with a long pre-match (anthem, recaps,
    interviews). Frames every step_s/2 from 15 % to 85 % of the video; the first window of need_s
    in which most samples show the court lines (between points there are close-ups and replays)
    starts the piece."""
    from tennisbio.court import fit_court
    from tennisbio.stages import grab_frame

    dt = step_s / 2
    n = max(2, int(need_s / dt))
    hits = []
    t = full * 0.15
    print(f"Buscando un tramo de juego (un fotograma cada {dt:.0f} s desde el minuto {t / 60:.0f})…", flush=True)
    t_start = time.time()
    while t < full * 0.85:
        fr = grab_frame(video, t)
        hits.append((t, fr is not None and fit_court(fr) is not None))
        if len(hits) % 10 == 0:
            print(f"  minuto {t / 60:.0f}: pista vista en {sum(h for _, h in hits[-10:])} de los últimos 10 fotogramas "
                  f"({time.time() - t_start:.0f} s)", flush=True)
        if len(hits) >= n and sum(h for _, h in hits[-n:]) >= 0.6 * n:
            start = hits[-n][0]
            print(f"Tramo de juego encontrado en el minuto {start / 60:.0f}")
            return float(start)
        t += dt
    print("No se encontró un tramo largo de juego; se usa el 30 % del vídeo")
    return full * 0.3


def diagnostics(ctx, dest: Path, n_frames=8):
    """Small images and texts for Claude (uploaded with the logs; the video never is): the middle
    frame of a few main-camera shots with the fitted court drawn, and what the OCR reads there."""
    import cv2
    import numpy as np
    from tennisbio.court import LINES
    from tennisbio.stages import court_at, grab_frame

    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("*"):
        f.unlink()
    sc = json.loads(ctx.path("scenes.json").read_text(encoding="utf-8"))
    court = json.loads(ctx.path("court.json").read_text(encoding="utf-8")) if ctx.path("court.json").exists() else {}
    fps = sc["fps"]
    shots = [x for x in sc["shots"] if x["main_camera"]] or sc["shots"]
    shots = shots[:: max(1, len(shots) // n_frames)][:n_frames]
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except ImportError:
        ocr = None
    lines = []
    for k, x in enumerate(shots):
        t = (x["start"] + x["end"]) / 2 / fps
        fr = grab_frame(ctx.video, t)
        if fr is None:
            continue
        H, _ = court_at(court, t)
        img = fr.copy()
        if H is not None:
            for a, b in LINES.values():
                p = np.array([[*a, 1.0], [*b, 1.0]]) @ np.asarray(H).T
                p = p[:, :2] / p[:, 2:]
                cv2.line(img, tuple(int(v) for v in p[0]), tuple(int(v) for v in p[1]), (0, 255, 255), 2)
        cv2.putText(img, f"t={t:.1f}s main={x['main_camera']} court={'si' if H is not None else 'no'}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        small = cv2.resize(img, (960, int(960 * img.shape[0] / img.shape[1])))
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            (dest / f"plano_{k:02d}.jpg").write_bytes(buf.tobytes())
        if ocr is not None:
            res, _ = ocr(fr)
            lines.append(f"t={t:.1f}s: " + " | ".join(
                f"{txt} @({int(np.asarray(b)[:, 0].min())},{int(np.asarray(b)[:, 1].min())})" for b, txt, _ in (res or [])))
    # a few frames of every shot type (main camera or not) to see why shots are rejected
    for k, x in enumerate([x for x in sc["shots"] if not x["main_camera"]][:4]):
        fr = grab_frame(ctx.video, (x["start"] + x["end"]) / 2 / fps)
        if fr is not None:
            small = cv2.resize(fr, (640, int(640 * fr.shape[0] / fr.shape[1])))
            ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                (dest / f"otro_plano_{k:02d}.jpg").write_bytes(buf.tobytes())
    (dest / "ocr.txt").write_text("\n".join(lines), encoding="utf-8")
    stroke_sheets(ctx, dest)


def stroke_sheets(ctx, dest: Path, per_sheet=6):
    """Contact sheets of the analysed strokes: for each one the frame at the end of the backswing
    and at contact, cropped around her, with what the program says about it (stroke, stance, how
    she arrives, speed, steps, finish, ball height), so Claude can check by eye that the classes
    match the images."""
    import cv2
    import numpy as np
    from tennisbio.stages import grab_frame

    p = ctx.path("strokes.json")
    if not p.exists():
        return
    strokes = json.loads(p.read_text(encoding="utf-8"))
    tiles = []
    for k, s in enumerate(strokes):
        win = ctx.path("windows") / s.get("window", "")
        ser = ctx.dir / s["series"] if s.get("series") else None
        if not win.exists() or ser is None or not ser.exists():
            continue
        sj = json.loads(ser.read_text(encoding="utf-8"))
        fps = float(sj["fps"])
        c = (s.get("technique") or {}).get("classes", {})
        f = (s.get("technique") or {}).get("footwork", {})
        crops = []
        for name in ("loaded", "impact"):
            fr_i = (s.get("phases") or {}).get(name, {}).get("frame") if name != "impact" else s.get("impact_frame")
            img = grab_frame(win, fr_i / fps) if fr_i is not None else None
            box = None
            if fr_i is not None and 0 <= fr_i - sj["first"] < len(sj["box"]):
                box = sj["box"][fr_i - sj["first"]]
            if img is None or not box:
                crops.append(np.zeros((360, 300, 3), np.uint8))
                continue
            x0, y0, x1, y1 = [int(v) for v in box]
            h = y1 - y0
            cx = (x0 + x1) // 2
            a0, a1 = max(0, y0 - h // 3), min(img.shape[0], y1 + h // 5)
            b0, b1 = max(0, cx - h), min(img.shape[1], cx + h)
            crops.append(cv2.resize(img[a0:a1, b0:b1], (300, 360)))
        tile = np.hstack(crops)
        txt = [f"#{k} {s['stroke']} t={s['match_time_s']:.0f}s",
               f"apoyo {c.get('stance_impact')} | {c.get('movement')} {f.get('speed_at_impact_mps')} m/s",
               f"pasos {f.get('steps_to_impact')} | fin {c.get('finish')} | bola {c.get('ball_height')}"]
        for i, t in enumerate(txt):
            cv2.putText(tile, t, (6, 22 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(tile)
    for n in range(0, len(tiles), per_sheet):
        g = tiles[n:n + per_sheet]
        while len(g) < per_sheet:
            g.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(g[i:i + 2]) for i in range(0, per_sheet, 2)])
        ok, buf = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            (dest / f"golpes_{n // per_sheet:02d}.jpg").write_bytes(buf.tobytes())


if __name__ == "__main__":
    main()
