"""The stages that show and measure the replays and other cameras linked to her strokes (#218, 09-11):

- ``view_clips``: a short clip of each linked view (replay of the main camera, side, front, close-up) around her
  stroke, in the match folder (view_clips/, beside windows/), and view_clips.json saying which clip shows which
  stroke and where her impact is in it. The report plays them on the stroke's page next to the live window.
- ``slowmo_fine`` (`views.fine_on_slowmo`): her pose (and the racket when its model is there) on the slow-motion
  replay around the impact, in slowmo_measures.json beside, never instead of, the live values of strokes.json.

Neither writes into strokes.json (the fine pass's output, where views_link already adds `views`): a third writer
would make views_link and these stages re-run each other in turn (pipeline.rewrites_lost). They live outside
stages.py so that adding them does not change the fine pass's code fingerprint (FINE_CODE hashes stages.py: an
edit there re-runs ~1 h of fine pass per match); pipeline.py imports this module so they are always registered."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .faults import fault
from .pipeline import Context, stage, write_atomic

CLIPS_FILE = "view_clips.json"
SLOWMO_FILE = "slowmo_measures.json"


def _write(path: Path, obj):
    write_atomic(path, json.dumps(obj, indent=1, ensure_ascii=False, default=float))


def _read(path: Path, default=None):
    """An output of a stage these depend on. #265: missing or damaged is C0 (entrada.ilegible), never `default`: the
    clips and slow-motion strokes of no strokes looked like a match without replays."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fault("entrada.ilegible", str(path), exc=e)


def _clips_settings(c: dict) -> dict:
    from .views import clip_settings
    return clip_settings(c)


def _source(ctx: Context) -> tuple[bool, dict]:
    """(interlaced, cut_window's arguments) of this match's video, as the fine pass cuts its windows."""
    from .stages import _cut_args

    pr = _read(ctx.path("probe.json"), {}) or {}
    return bool(pr.get("interlaced")), _cut_args(ctx)


@stage("view_clips", "1", deps=("views", "fine", "views_link"), settings=_clips_settings, outputs=(CLIPS_FILE,),
       code=("view_stages", "views"))
def st_view_clips(ctx: Context):
    """A clip of each replay / other camera linked to one of her strokes (tennisbio.views.clip_plan): around her
    impact when its instant in the replay is known (1 s before, 0.8 s after, × the slow-motion factor), else the
    shot from its start (≤ 10 s). One cut per distinct clip; clips that exist and are valid are not cut again;
    clips of views no longer linked are removed. Light encoding (≤ 1280 px, CRF 23): for watching, not measuring."""
    from .views import CLIP_DIR, clip_plan, clip_settings, cut_view_clip

    st = clip_settings(ctx.cfg)
    strokes = _read(ctx.path("strokes.json"), []) or []
    plan = clip_plan(strokes, st) if st["enabled"] else []
    folder = ctx.path(CLIP_DIR)
    interlaced, args = _source(ctx) if plan else (False, {})
    files: dict[str, dict] = {}
    for row in plan:
        files.setdefault(row["file"], row)
    cut = reused = 0
    failed: list[str] = []
    t_ = time.time()
    for n, (name, row) in enumerate(sorted(files.items()), 1):
        ctx.progress(n, len(files), "recortes de repeticiones y otras cámaras")
        dest = folder / name
        existed = dest.exists()
        try:
            cut_view_clip(ctx.video, row["clip_t0"], row["clip_dur"], dest, interlaced, args.get("audio_track", 0),
                          args.get("width", 0), st["width"], st["crf"])
            reused += existed
            cut += not existed
        except Exception as e:                    # noqa: BLE001 — that clip is missing; the others are cut
            failed.append(name)
            ctx.log(f"  AVISO: toma sin recorte ({name}): {str(e)[:160]}")
            fault("toma.sin_recorte", name, exc=e)
    for f in folder.glob("v*.mp4") if folder.exists() and st["enabled"] else []:
        if f.name not in files:                   # a view no longer linked to any stroke
            f.unlink(missing_ok=True)
    ok = set(files) - set(failed)
    rows = [{**r, "ok": r["file"] in ok} for r in plan]
    keys = {r["key"] for r in plan}
    summary = {"enabled": st["enabled"], "linked_strokes": len(keys), "views": len(plan), "clips": len(files),
               "cut": cut, "reused": reused, "failed": len(failed), "seconds": round(time.time() - t_, 1),
               "clip_seconds": round(sum(r["clip_dur"] for r in files.values()), 1),
               "strokes_with_clip": len({r["key"] for r in rows if r["ok"]})}
    _write(ctx.path(CLIPS_FILE), {"version": 1, "dir": CLIP_DIR, "clips": rows, "summary": summary})
    ctx.log(f"  tomas recortadas: {cut} nuevas, {reused} ya hechas, {len(failed)} fallidas, de {len(keys)} golpes")
    return summary


def _slowmo_settings(c: dict) -> dict:
    from .config import model_state
    from .views import slowmo_settings

    st = slowmo_settings(c)
    if st["enabled"]:          # the models themselves: adding or replacing one re-runs it
        st["models"] = {"pose": c.get("yolo_pose", "yolo11m-pose.pt"),
                        "racket": model_state((c.get("racket_face") or {}).get("pose_onnx")) if st["racket"] else None}
    return st


def _racket_model(ctx: Context):
    """The 5-point racket model of the fine pass (racket_face.pose_onnx), or None when its file is not there."""
    from .config import resolve_path

    f = (ctx.cfg.get("racket_face") or {}).get("pose_onnx")
    p = resolve_path(f) if f else None
    if p is None or not Path(p).exists():
        return None
    try:
        from .racket_pose import RacketPose
        return RacketPose(p, ctx.cfg.get("device", "cpu"), bool((ctx.cfg.get("racket_face") or {}).get("fp16", False)))
    except Exception as e:                        # noqa: BLE001 — the arm is still measured
        ctx.log(f"  AVISO: cámara lenta sin raqueta (no se pudo cargar el modelo: {str(e)[:150]})")
        fault("modelo.raqueta_no_carga", "cámara lenta sin raqueta", exc=e)
        return None


@stage("slowmo_fine", "1", deps=("views", "fine", "views_link"), settings=_slowmo_settings, outputs=(SLOWMO_FILE,),
       code=("view_stages", "views"))
def st_slowmo_fine(ctx: Context):
    """`views.fine_on_slowmo`: each of her near-side strokes with a slow-motion replay of the main camera whose
    impact instant is known (views.slowmo_view) gets her arm at the impact (and the racket, with its model)
    measured on that replay (views.fine_on_slowmo), in slowmo_measures.json beside the live values. Switched off:
    the file says so and nothing is computed."""
    from .views import CLIP_DIR, fine_on_slowmo, slowmo_settings, slowmo_view, stroke_key

    st = slowmo_settings(ctx.cfg)
    strokes = _read(ctx.path("strokes.json"), []) or []
    todo = [(s, slowmo_view(s)) for s in strokes if s.get("side", "near") != "far"] if st["enabled"] else []
    todo = [(s, v) for s, v in todo if v is not None and stroke_key(s) is not None]
    rows, failed, t_ = [], 0, time.time()
    if todo:
        from .pose.backend import set_device, uses_fp16

        set_device(ctx.cfg.get("device", "cpu"), uses_fp16(ctx.cfg))
        interlaced, args = _source(ctx)
        racket = _racket_model(ctx) if st["racket"] else None
        p = ctx.match.player
        for n, (s, v) in enumerate(todo, 1):
            ctx.progress(n, len(todo), "golpes en la repetición a cámara lenta")
            try:
                got = fine_on_slowmo(ctx.video, s, v, ctx.cfg, ctx.path(CLIP_DIR) / "slowmo", interlaced, args,
                                     p.hand, p.height_m, racket, log=lambda *_: None)
            except Exception as e:                # noqa: BLE001 — that stroke is not measured; the others are
                failed += 1
                ctx.log(f"  AVISO: cámara lenta de {stroke_key(s)} sin medir: {str(e)[:160]}")
                fault("golpe.camara_lenta", stroke_key(s), exc=e)
                continue
            if got is not None:
                rows.append({"key": stroke_key(s), "stroke_id": s.get("stroke_id"), "stroke": s.get("stroke"),
                             "view_t0": v["t0"], **got})
    summary = {"enabled": st["enabled"], "slowmo_strokes": len(todo), "measured": len(rows), "failed": failed,
               "frames": sum(r["frames"] for r in rows), "seconds": round(time.time() - t_, 1)}
    _write(ctx.path(SLOWMO_FILE), {"version": 1, "enabled": st["enabled"], "strokes": rows, "summary": summary})
    if st["enabled"]:
        ctx.log(f"  cámara lenta: {len(rows)} de {len(todo)} golpes medidos ({summary['frames']} fotogramas, {summary['seconds']:.0f} s)")
    return summary
