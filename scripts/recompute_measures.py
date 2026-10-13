"""Recompute the measurements of the strokes already analysed in the test folder (<output>/_smoke)
with the current code, then rebuild the report, the export and the audit (minutes, not hours).

Nothing expensive is repeated: no new clip is cut, the cheap pass (probe, scenes, audio, court,
players, score) is read from its outputs even if its code changed since, and the fine pass reuses
the pose, ball and racket caches of every window (<match>/windows/*.npz, *.npy). Only the fine
passes are forced; identity and candidates are re-run only when stale (seconds).

    uv run python scripts/recompute_measures.py [--player rybakina]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import Match, load_player  # noqa: E402
from tennisbio.config import load_config  # noqa: E402

EXPENSIVE = ("probe", "scenes", "audio", "court", "players", "score")    # never re-run here
CHEAP = ("identity", "candidates")                                       # re-run only when stale
FINE = ("fine", "fine_opponent")                                         # always re-run
VIDEO_EXT = {".mp4", ".mkv", ".ts", ".mov", ".avi", ".m4v", ".webm"}
CLIP_NAME = re.compile(r"_\d+_\d+m$")          # smoke_test.py: <ascii>_<start>_<minutes>m.<ext>


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def took(t0: float) -> str:
    s = time.time() - t0
    return f"{s / 60:.1f} min" if s >= 90 else f"{s:.0f} s"


class Problem(RuntimeError):
    """A message for the user (Spanish)."""


def match_dirs(out_root: Path) -> list[Path]:
    """Match folders of the test runs: those with a manifest and strokes."""
    if not out_root.exists():
        return []
    return [d for d in sorted(out_root.iterdir())
            if d.is_dir() and (d / "strokes.json").exists() and (d / "manifest.json").exists()]


def find_clip(d: Path, out_root: Path, tol_s: float = 0.5) -> Path:
    """The clip of <out_root> that produced match folder d: the cut pieces smoke_test.py leaves in
    <out_root> (the 4-minute and the 35-minute ones may both be there), the one with the duration
    recorded by the probe stage; the file named in probe.json first."""
    from tennisbio.io.video import probe

    pj = d / "probe.json"
    if not pj.exists():
        raise Problem(f"Falta {pj}: esa prueba no llegó a empezar. Lanza 2_prueba_rapida.bat o 2b_prueba_media.bat.")
    info = json.loads(pj.read_text(encoding="utf-8"))
    dur, name = float(info.get("duration") or 0), PureWindowsPath(str(info.get("path") or "")).name
    clips = [f for f in out_root.iterdir()
             if f.is_file() and f.suffix.lower() in VIDEO_EXT and CLIP_NAME.search(f.stem)]
    clips.sort(key=lambda f: (f.name != name, f.name))
    seen = []
    for f in clips:
        try:
            got = probe(f).duration
        except Exception as e:                # a broken file: say so and try the others
            seen.append(f"{f.name} (no se puede leer: {e})")
            continue
        if abs(got - dur) <= tol_s:
            return f
        seen.append(f"{f.name} ({got:.1f} s)")
    raise Problem(f"No se encuentra en {out_root} el trozo de vídeo de {d.name} (dura {dur:.1f} s). "
                  + (f"Hay: {', '.join(seen)}. " if seen else "No hay ningún trozo de vídeo. ")
                  + "Lanza otra vez 2_prueba_rapida.bat o 2b_prueba_media.bat (el trozo se corta de nuevo).")


def window_files(d: Path) -> set[str]:
    w = d / "windows"
    return {f.name for f in w.iterdir() if f.is_file()} if w.exists() else set()


def recompute(d: Path, out_root: Path, cfg: dict, player) -> dict:
    """Fine passes (forced) and the stale cheap stages of one match folder, on the outputs there."""
    t_all = time.time()
    clip = find_clip(d, out_root)
    sc = d / "score.json"
    opp = (json.loads(sc.read_text(encoding="utf-8")).get("opponent") or "") if sc.exists() else ""
    match = Match(d.name, clip, player, opponent=opp)       # as smoke_test.py builds it
    ctx = pipeline.Context(match, cfg, d)
    print(f"\n[{now()}] {d.name}: trozo de vídeo {clip.name}" + (f", rival {opp}" if opp else ""), flush=True)
    m = pipeline.load_manifest(d)
    missing = [n for n in EXPENSIVE if n not in m or not pipeline.outputs_ok(n, ctx)]
    if missing:
        raise Problem(f"En {d.name} faltan resultados de la pasada barata ({', '.join(missing)}): "
                      "esa prueba no terminó. Lanza 2_prueba_rapida.bat o 2b_prueba_media.bat.")
    old = [n for n in EXPENSIVE if m[n]["fingerprint"] != pipeline.fingerprint(n, ctx, m)]
    if old:
        print(f"  Se usan los resultados que hay de {', '.join(old)} aunque su código o su vídeo cambiaron "
              "(no se rehacen aquí; la próxima prueba completa sí lo hará)")
    before = window_files(d)
    times = {}
    t0 = time.time()
    done = pipeline.run(ctx, list(CHEAP), upstream=False)
    times["identidad y candidatos"] = time.time() - t0
    print(f"[{now()}] Etapas baratas rehechas: {', '.join(done) or 'ninguna (al día)'} ({took(t0)})", flush=True)
    t0 = time.time()
    done += pipeline.run(ctx, list(FINE), force=True, upstream=False)
    times["medidas de los golpes"] = time.time() - t0
    m = pipeline.load_manifest(d)
    fs = m.get("fine", {}).get("summary", {})
    print(f"[{now()}] Medidas recalculadas en {took(t0)}: {fs.get('confirmed')} golpes de {fs.get('candidates')} "
          f"candidatos en {fs.get('windows')} ventanas" + (f", {fs.get('errors')} con error" if fs.get("errors") else ""),
          flush=True)
    if fs.get("seconds"):
        print("  Tiempo por parte (s): " + ", ".join(f"{k} {v}" for k, v in fs["seconds"].items()))
    # the caches: any new pose/ball/racket file means a window was analysed again from the video
    new = sorted(window_files(d) - before)
    heavy = [f for f in new if f.endswith((".npz", ".npy", ".mp4"))]
    if heavy:
        print(f"  AVISO: {len(heavy)} ficheros de ventana nuevos (no estaban en caché): {', '.join(heavy[:8])}"
              + (" …" if len(heavy) > 8 else ""))
    else:
        print("  Cachés de pose, bola y raqueta reutilizadas en todas las ventanas")
    # contact sheets of the strokes with their classes, for Claude (uploaded with the logs)
    try:
        from smoke_test import stroke_sheets
        diag = out_root / "diag"
        diag.mkdir(parents=True, exist_ok=True)
        for f in diag.glob("golpes_*.jpg"):
            f.unlink()
        stroke_sheets(ctx, diag)
    except Exception as e:
        print(f"  AVISO: no se pudieron hacer las hojas de golpes ({e})")
    print(f"[{now()}] {d.name} terminado en {took(t_all)}", flush=True)
    return {"done": done, "times": times}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default="rybakina")
    args = ap.parse_args()
    t_start = time.time()
    print(f"Recalcular medidas: empieza {now()}", flush=True)
    cfg = load_config()
    out_root = Path(cfg.get("paths", {}).get("output", "output")) / "_smoke"
    dirs = match_dirs(out_root)
    if not dirs:
        print(f"No hay nada analizado en {out_root}: lanza antes 2_prueba_rapida.bat o 2b_prueba_media.bat")
        return 1
    player = load_player(args.player)
    try:
        for d in dirs:
            recompute(d, out_root, cfg, player)
    except Problem as e:
        print(f"ERROR: {e}")
        return 1
    except pipeline.MissingVideo as e:
        print(f"ERROR: falta el trozo de vídeo {e}. Lanza otra vez 2_prueba_rapida.bat o 2b_prueba_media.bat.")
        return 1
    except pipeline.DiskFull as e:
        print(f"ERROR: {e}")
        return 1
    t0 = time.time()
    print(f"\n[{now()}] Informe, PDF y auditoría…", flush=True)
    from rebuild_report import rebuild
    code = rebuild(out_root, args.player, t0, done="con las medidas nuevas")
    print(f"[{now()}] Informe, PDF y auditoría en {took(t0)}")
    print(f"Recalcular medidas: termina {now()} (total {took(t_start)})")
    return code


if __name__ == "__main__":
    sys.exit(main())
