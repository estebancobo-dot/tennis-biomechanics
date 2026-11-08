"""Stroke detection on RacketVision broadcast clips through the PRODUCTION path (08-11).

Until 08-11, scripts/validate_rv_strokes.py measured the old clip path (tennisbio.clip_pipeline.run_clip: pose
+ the ball rule), which the analysis of a match no longer uses: PC request 154 (precision 0.64, recall 0.74,
19 strokes) measured that path, not the one the application runs. The application finds strokes with the
learned spotter (stage `spotting`, when `spotter.enabled`), turns them into candidates (stage `candidates`,
stages.spotter_candidates) and confirms them in the fine pass (`fine` / `fine_doubtful`). This module runs
exactly those stages (tennisbio.pipeline.run with the user's configuration, as recall_eval does for the F3Set
compilations) on each 10 s RacketVision clip, treated as a tiny match, and compares the confirmed strokes of
each end with the reference contacts from the annotated ball track (validation.ball_hits).

What differs from a full broadcast, and is said in the output (never hidden):
- the clips have NO SOUND: the spotter's sound features (impact transients, sound flux) are empty, while the
  model was trained with them;
- a clip is 10 s (100 frames at the spotter's 10 fps): the model sees little context, none before the first
  second or after the last;
- whose stroke it is (identity) cannot be decided in 10 s of unknown players (no scoreboard name, one shot):
  the strokes land in strokes_doubtful.json, which the application also counts as found strokes; here both
  files are read, by end (near / far), whoever the player is.
"""
from __future__ import annotations

import json
from pathlib import Path

DETECTOR = "pipeline"           # the validation's default path: the analysis's own stages (see tests/test_validation_detector.py)
LEGACY_LABEL = "LEGACY: camino antiguo (clip_pipeline.run_clip: pose + regla de la bola), no el del análisis"
STROKE_FILES = ("strokes.json", "strokes_doubtful.json")
SIDES = ("near", "far")
NOTES = (
    "Los clips de RacketVision no tienen sonido: los rasgos de sonido del detector entrenado van vacíos "
    "(se entrenó con ellos).",
    "Cada clip dura 10 s (100 fotogramas a los 10 fps del detector): poco contexto, ninguno antes del primer "
    "segundo ni después del último.",
    "La identidad no se puede decidir en 10 s de jugadores desconocidos: sus golpes van a strokes_doubtful.json "
    "(la aplicación también los cuenta como encontrados); aquí se leen strokes.json y strokes_doubtful.json por lado.",
    "Referencia: contactos deducidos de la bola anotada (validation.ball_hits, la misma que el camino antiguo); "
    "la bola está anotada cada ~12 fotogramas a 60 fps.",
)


def short_log(msg) -> None:
    """Only the lines that say what the detector and the fine pass did (the full stage log is long)."""
    s = str(msg)
    if any(k in s for k in ("detector entrenado", "candidatos", "AVISO", "fine terminada", "dobles")):
        print("    " + s.strip(), flush=True)


def run_clip_pipeline(video: Path, mid: str, out_dir: Path, cfg: dict | None = None, player_id: str | None = None,
                      log=print) -> list[str]:
    """All the analysis stages on one clip, with the user's configuration (the same detector as the analysis:
    the learned spotter when `spotter.enabled`). Outputs in out_dir/mid; incremental like any match."""
    from .. import pipeline, stages  # noqa: F401  (registers the stages)
    from ..catalog import Match, load_player
    from ..config import default_player, load_config

    cfg = load_config() if cfg is None else cfg
    match = Match(mid, Path(video), load_player(player_id or default_player(cfg)), opponent="RacketVision", surface="dura")
    ctx = pipeline.Context(match, cfg, Path(out_dir) / mid, log=log)
    return pipeline.run(ctx)


def _read(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def clip_outputs(mdir: Path) -> dict:
    """What the stages left for one clip: the confirmed strokes of each end (time in s, file, stroke, source),
    the spotter's strokes, the candidates, whether it is doubles, and the video's fps."""
    from .. import match_files as mf

    mdir = Path(mdir)
    rd = lambda n: _read(mf.at(mdir, n))                     # noqa: E731
    man = rd("manifest.json") or {}
    summ = lambda st: (man.get(st) or {}).get("summary") or {}     # noqa: E731
    strokes = []
    for f in STROKE_FILES:
        for s in rd(f) or []:
            if s.get("match_time_s") is None:
                continue
            strokes.append({"t": float(s["match_time_s"]), "side": s.get("side", "near"), "file": f,
                            "stroke": s.get("stroke"), "source": s.get("impact_source")})
    probe = rd("probe.json") or {}
    return {"strokes": sorted(strokes, key=lambda s: s["t"]), "spotted": rd("spotting.json") or [],
            "candidates": rd("candidates.json") or [], "doubles": bool(summ("candidates").get("doubles")),
            "candidate_source": summ("candidates").get("source") or "reglas",
            "spotter_enabled": bool(summ("spotting").get("enabled")), "fps": float(probe.get("fps") or 0) or None}


def predicted_frames(out: dict, side: str, fps: float) -> list[int]:
    """Frames of the video (its own fps) of the confirmed strokes of one end."""
    return [int(round(s["t"] * fps)) for s in out["strokes"] if s["side"] == side]


def evaluate(clips: list[dict], tol: int) -> dict:
    """Per end: precision, recall, F1 and timing error (frames of the video) over all clips. clips: [{gt: {side:
    [frames]}, pred: {side: [frames]}}]."""
    from .impact_eval import GTEvent, Pred, match, summarize

    out = {}
    for side in SIDES:
        pairs_all, fp_all, fn_all = [], [], []
        for c in clips:
            preds = [Pred(f, "-") for f in c["pred"].get(side, [])]
            gts = [GTEvent(g, side, "stroke", "-", "-") for g in c["gt"].get(side, [])]
            pairs, fp, fn = match(preds, gts, tol)
            pairs_all += pairs
            fp_all += fp
            fn_all += fn
        s = summarize(pairs_all, fp_all, fn_all)
        out[side] = {k: s[k] for k in ("gt", "detected", "true_positives", "precision", "recall", "f1",
                                       "timing_err_frames_median", "timing_bias_frames")}
    return out


def _pct(x):
    return "—" if x is None else f"{x:.2f}"


def to_markdown(res: dict) -> str:
    """The report for the user (Spanish), next to the JSON."""
    ln = ["# Validación de golpes con RacketVision", "",
          f"**Camino medido:** {res['path_label']}.", "",
          f"Clips: {res['clips_used']} usados de {res['clips_selected']} elegidos del conjunto de prueba "
          f"({res['clips_doubles']} de dobles y {res['clips_failed']} con error, fuera). Tolerancia ±{res['tol_frames']} "
          f"fotogramas del vídeo (≈ {res['tol_s']} s). Detector: {res['detector']}.", ""]
    if res.get("spotter_unavailable"):
        ln += [f"**El detector entrenado no ha podido ejecutarse:** {res['spotter_unavailable']}", ""]
    ln += ["| Lado | Anotados | Detectados | Aciertos | Precisión | Recall | F1 | Error de instante (mediana, fotogramas) | Sesgo |",
           "|---|---|---|---|---|---|---|---|---|"]
    for side, name in (("near", "cercano"), ("far", "lejano")):
        s = res["summary"].get(side) or {}
        ln.append(f"| {name} | {s.get('gt', 0)} | {s.get('detected', 0)} | {s.get('true_positives', 0)} | {_pct(s.get('precision'))} | "
                  f"{_pct(s.get('recall'))} | {_pct(s.get('f1'))} | {s.get('timing_err_frames_median') if s.get('timing_err_frames_median') is not None else '—'} | "
                  f"{s.get('timing_bias_frames') if s.get('timing_bias_frames') is not None else '—'} |")
    ln += ["", "## Diferencias con un partido completo", ""] + [f"- {n}" for n in res["notes"]]
    if res.get("legacy_reference"):
        ln += ["", f"Referencia anterior (camino antiguo, petición 154 del PC): {res['legacy_reference']}."]
    ln += ["", "## Clips", "", "| Clip | Anotados cerca / lejos | Detectados cerca / lejos | Golpes del detector | Candidatos | Nota |",
           "|---|---|---|---|---|---|"]
    for c in res["clips"]:
        ln.append(f"| {c['clip']} | {c['gt'].get('near', [])} / {c['gt'].get('far', [])} | {c['pred'].get('near', [])} / "
                  f"{c['pred'].get('far', [])} | {c.get('spotted', '—')} | {c.get('candidates', '—')} | {c.get('note', '')} |")
    return "\n".join(ln) + "\n"
