"""Request 199: our OWN ball-bounce model, trained and measured against the bounce rule (tennisbio.ball).

TennisProject's CatBoost model measured F1 0.899 against the rule's 0.581 (scripts/bench_candidates.py --only bounce,
with our ball detector), but it has no licence. This trains our own model on the same 12 features per frame
(tennisbio.candidates.bounce_ctb.features; tennisbio.candidates.bounce_own) with scikit-learn's
HistGradientBoostingClassifier, on the annotated bounces of the TrackNet dataset (the one bench_candidates already
downloaded to <datasets>/tracknet) and the ball path of OUR detector on its frames (as in a match).

No leakage: the clips are split BY GAME (each TrackNet game is one match: one video) into --folds groups. Each game's
bounces are predicted by a model that never saw that game; its threshold is chosen inside the training games only
(inner split by game). The rule runs on exactly the same tracks of the same clips.

Criterion, written before measuring: the own model is adopted only if its held-out F1 > the rule's F1 + 0.05 (with at
least 20 annotated bounces). Adopting it is then a configuration change (`bounce_model: {use: own}`); this script
never changes the configuration.

The final model (all games, threshold from the same split by game) is saved to models/bounce_own.pkl (not in git).
Our detector's tracks are cached in <datasets>/tracknet/tracks/ (recomputed if the ball model changes).

    uv run python scripts/train_bounce.py [--root C:\\tenis\\datasets] [--device dml] [--folds 5] [--with-annotated]
    (also: uv run python scripts/bench_candidates.py --only bounce_own)

Writes <output>/bench_bounce_own.json and .md (and the same in <datasets>/reports/).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

MARGIN = 0.05              # adopt only if held-out F1 > rule F1 + MARGIN (written before measuring)
MIN_BOUNCES = 20
MODEL_OUT = ROOT / "models" / "bounce_own.pkl"


# ---------------------------------------------------------------- data

def game_of(key: str) -> str:
    """TrackNet clip key 'game3_Clip7' → its game (one match, one video): the unit of the split."""
    return key.split("_")[0]


_DOWNLOAD = {"failed": None}     # the reason the whole zip could not be downloaded, once per run


def _frames(root: Path, key: str, folder: str, names: list[str]):
    """The clip's frames one by one (extracted from the zip once, as bench_candidates.tracknet_frames), so a long clip
    never has to fit in memory."""
    import cv2
    from bench_candidates import tracknet_download

    d = root / "tracknet" / "images" / key
    d.mkdir(parents=True, exist_ok=True)
    z = None
    for n in names:
        p = d / n
        if not p.exists():
            # all 95 clips' frames: the whole zip once (resumable) rather than thousands of reads by parts (07-11,
            # request 125: a read by parts died at 2.3 of 2.6 GB)
            if z is None:
                if _DOWNLOAD["failed"]:
                    raise OSError(_DOWNLOAD["failed"])
                try:
                    z = tracknet_download(root)
                except OSError as e:
                    # 07-11, request 128: Google Drive answers the PC with a page, not the zip; the clips already on
                    # disk (those of the bounce measure) are used and the rest skipped, said in the report
                    _DOWNLOAD["failed"] = str(e)[:200]
                    raise
            p.write_bytes(z.read(folder + n))
        yield cv2.imread(str(p))


def tracked(root: Path, key: str, folder: str, names: list[str], tracker, state: str) -> tuple[np.ndarray, int]:
    """(our detector's track (T, 3), frame height) of one clip, cached in <root>/tracknet/tracks/<key>.npz."""
    c = root / "tracknet" / "tracks" / f"{key}.npz"
    if c.exists():
        try:
            d = np.load(c)
            if str(d["state"]) == state and len(d["track"]) == len(names):
                return d["track"], int(d["frame_h"])
        except Exception:                          # damaged cache: computed again
            pass
    fh = {"h": 720}

    def frames():
        for i, f in enumerate(_frames(root, key, folder, names)):
            if i == 0 and f is not None:
                fh["h"] = int(f.shape[0])
            yield f
    tr = tracker.track(frames(), step=1)           # 30 fps: as bench_candidates (and the fine pass, ~25 fps)
    c.parent.mkdir(parents=True, exist_ok=True)
    tmp = c.with_name(c.stem + ".tmp.npz")
    np.savez(tmp, track=tr, frame_h=fh["h"], state=state)
    tmp.replace(c)
    return tr, fh["h"]


def load_clips(root: Path, cfg: dict, device: str, keys: list[str] | None = None) -> list[dict]:
    """Every TrackNet clip: {key, group, tracked, frame_h, annotated, hits (annotated), gt (annotated bounces)}."""
    from bench_candidates import read_tracknet, tracknet_index
    from tennisbio.ball import BallTracker
    from tennisbio.config import model_state, resolve_path

    folders = tracknet_index(root)
    lab = root / "tracknet" / "labels"
    bcfg = cfg.get("ball") or {}
    ours = resolve_path(bcfg.get("onnx") or "models/balltrack.onnx")
    if ours is None or not ours.exists():
        raise FileNotFoundError(f"falta nuestro modelo de bola ({ours}): ejecuta scripts/setup_models.py")
    tracker = BallTracker(str(ours), device, fp16=bool(bcfg.get("fp16", True)) and device != "cpu")
    state = f"{model_state(ours)}|{bcfg.get('threshold', 0.5)}"
    clips = []
    for key in (keys or sorted(folders)):
        names, ann, st = read_tracknet(lab / f"{key}.csv")
        t_ = time.time()
        try:
            tr, fh = tracked(root, key, folders[key], names, tracker, state)
        except OSError as e:
            print(f"  {key}: sin fotogramas en el disco y sin descarga ({str(e)[:100]}): se deja fuera", flush=True)
            continue
        print(f"  {key}: {len(names)} fotogramas, {int(np.sum(st == 2))} botes ({time.time() - t_:.0f} s)", flush=True)
        clips.append({"key": key, "group": game_of(key), "tracked": tr, "frame_h": fh, "annotated": ann,
                      "hits": [int(h) for h in np.flatnonzero(st == 1)], "gt": [int(b) for b in np.flatnonzero(st == 2)]})
    return clips


# ---------------------------------------------------------------- training and measuring

def _rows(clips: list[dict], train_on=("tracked",)):
    from tennisbio.candidates.bounce_own import labels, track_features

    X, y = [], []
    for c in clips:
        for src in train_on:
            tr = c.get(src)
            if tr is None:
                continue
            f, fr = track_features(tr, c.get("frame_h", 720) if src == "tracked" else 720)
            X.append(f)
            y.append(labels(fr, c["gt"]))
    if not X:
        return np.zeros((0, 12), np.float32), np.zeros(0, np.int8)
    return np.concatenate(X), np.concatenate(y)


def fit(clips: list[dict], train_on=("tracked",), seed: int = 0):
    from tennisbio.candidates.bounce_own import new_classifier

    X, y = _rows(clips, train_on)
    if len(np.unique(y)) < 2:
        raise ValueError("sin botes (o sin fotogramas sin bote) en los clips de entrenamiento")
    return new_classifier(seed).fit(X, y)


def clip_scores(model, clips: list[dict]) -> list[tuple[np.ndarray, np.ndarray]]:
    """(frames, scores) per clip on OUR detector's track (the task in a match)."""
    from tennisbio.candidates.bounce_own import OwnBounce

    ob = OwnBounce(model, 0.5)
    return [ob.scores(c["tracked"], c.get("frame_h", 720)) for c in clips]


def event_counts(preds: list[list[int]], gts: list[list[int]], tol: int) -> tuple[int, int, int]:
    from bench_candidates import match_events

    tp = fp = fn = 0
    for p, g in zip(preds, gts):
        a, b, c, _ = match_events(list(p), list(g), tol)
        tp, fp, fn = tp + a, fp + b, fn + c
    return tp, fp, fn


def _f1(tp, fp, fn) -> float:
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def pick_threshold(scored: list[tuple[np.ndarray, np.ndarray]], gts: list[list[int]], tol: int) -> float:
    """The threshold of the grid with the best event F1 on these (held-out) clips; ties: the higher one."""
    from tennisbio.candidates.bounce_own import GRID, detect

    best = (-1.0, 0.5)
    for t in GRID:
        f = _f1(*event_counts([detect(fr, s, t) for fr, s in scored], gts, tol))
        if f >= best[0]:
            best = (f, t)
    return best[1]


def choose_threshold(clips: list[dict], folds: int, train_on, tol: int) -> float:
    """Threshold from a split by game inside these clips only (each game scored by a model that did not see it)."""
    from tennisbio.candidates.bounce_own import group_folds

    groups = sorted({c["group"] for c in clips})
    if len(groups) < 2:
        return 0.5
    scored, gts = [], []
    for tr_g, held in group_folds(groups, folds):
        tr_c = [c for c in clips if c["group"] in tr_g]
        he_c = [c for c in clips if c["group"] in held]
        try:
            m = fit(tr_c, train_on)
        except ValueError:
            continue
        scored += clip_scores(m, he_c)
        gts += [c["gt"] for c in he_c]
    return pick_threshold(scored, gts, tol) if scored else 0.5


def evaluate(clips: list[dict], folds: int = 5, train_on=("tracked",), tol: int | None = None,
             rule=None, extra: dict | None = None) -> dict:
    """Held-out comparison, split by game. rule(clip) → the rule's bounces on our detector's track; extra: other
    reference detectors {name: fn(clip) → bounces} (information only). Returns per-model counts and F1, the
    thresholds chosen per fold and the per-clip predictions."""
    from bench_candidates import BOUNCE_TOL_F, prf
    from tennisbio.candidates.bounce_own import detect, group_folds

    tol = BOUNCE_TOL_F if tol is None else tol
    groups = sorted({c["group"] for c in clips})
    pred: dict[str, list[int]] = {}
    thr, secs = {}, {"own": 0.0, "rule": 0.0}
    for tr_g, held in group_folds(groups, folds):
        tr_c = [c for c in clips if c["group"] in tr_g]
        he_c = [c for c in clips if c["group"] in held]
        t = choose_threshold(tr_c, folds - 1, train_on, tol)
        m = fit(tr_c, train_on)
        for g in held:
            thr[g] = t
        t_ = time.time()
        for c, (fr, s) in zip(he_c, clip_scores(m, he_c)):
            pred[c["key"]] = detect(fr, s, t)
        secs["own"] += time.time() - t_
    order = [c["key"] for c in clips]
    gts = [c["gt"] for c in clips]
    out = {"own": prf(*event_counts([pred[k] for k in order], gts, tol))}
    rule_p = []
    for c in clips:
        t_ = time.time()
        rule_p.append(rule(c) if rule else [])
        secs["rule"] += time.time() - t_
    out["rule"] = prf(*event_counts(rule_p, gts, tol))
    for name, fn in (extra or {}).items():
        out[name] = prf(*event_counts([fn(c) for c in clips], gts, tol))
    for r in out.values():                    # no bounce predicted at all while some were annotated: F1 0, not unknown
        if r["f1"] is None and r["fn"]:
            r["f1"] = 0.0
    frames = sum(len(c["tracked"]) for c in clips)
    return {"per_model": out, "thresholds": thr, "bounces": sum(len(g) for g in gts), "clips": len(clips),
            "games": groups, "frames": frames, "seconds": secs,
            "predictions": {k: {"own": pred[k], "rule": r, "gt": c["gt"]} for k, r, c in zip(order, rule_p, clips)}}


def decide(own_f1, rule_f1, n_bounces: int) -> dict:
    if own_f1 is None or rule_f1 is None:
        return {"adopt": False, "insufficient": True, "reason": "sin medida completa"}
    if n_bounces < MIN_BOUNCES:
        return {"adopt": False, "insufficient": True,
                "reason": f"solo {n_bounces} botes anotados (hacen falta {MIN_BOUNCES})"}
    ok = own_f1 > rule_f1 + MARGIN
    return {"adopt": bool(ok), "reason": f"F1 botes (nuestra bola, partidos no vistos) {own_f1} frente a {rule_f1} de "
                                         f"la regla: {'supera' if ok else 'no supera'} la regla + {MARGIN}"}


def rule_on_tracked(c: dict) -> list[int]:
    from bench_candidates import TRACKNET_FPS, rule_bounces
    from tennisbio.ball import ball_hits

    tr = c["tracked"]
    hits = [h.frame for h in ball_hits(tr, int(c.get("frame_h", 720)), TRACKNET_FPS)]
    return rule_bounces(tr, hits, TRACKNET_FPS)


def to_markdown(rep: dict) -> str:
    pm = rep["per_model"]
    v = rep["verdict"]
    names = {"own": "propio (HistGradientBoosting, 12 rasgos)", "rule": "regla (giro más brusco, tennisbio.ball)",
             "catboost_ref": "CatBoost de TennisProject (solo referencia: sin licencia, entrenado con estos datos)"}
    lines = [f"# Bote: modelo propio frente a la regla ({rep['generated']})", "",
             f"Criterio escrito antes de medir: se adopta solo si su F1 en partidos no vistos supera el de la regla en "
             f"más de {MARGIN} (con al menos {MIN_BOUNCES} botes anotados).", "",
             f"**¿Se adopta?** {'**sí**' if v.get('adopt') else 'no'}: {v.get('reason', '')}", "",
             "| Modelo | F1 | Precisión | Recall | Acertados / falsos / perdidos |", "|---|---|---|---|---|"]
    for k in ("own", "rule", "catboost_ref"):
        r = pm.get(k)
        if r:
            lines.append(f"| {names[k]} | {r['f1']} | {r['precision']} | {r['recall']} | {r['tp']} / {r['fp']} / {r['fn']} |")
    lines += ["", f"- {rep['clips']} clips de {len(rep['games'])} partidos del conjunto TrackNet, {rep['bounces']} botes "
                  f"anotados; bola de nuestro detector (como en un partido).",
              f"- Separación por partido en {rep['folds']} grupos: cada partido lo predice un modelo que no lo vio; su "
              f"umbral se elige solo con los partidos de entrenamiento. Umbrales: {rep['thresholds']}.",
              f"- Bote acertado si está a ≤{rep['tol_frames']} fotogramas (0,1 s) de uno anotado.",
              f"- Entrenado con: {', '.join(rep['train_on'])}. Modelo final (todos los partidos, umbral "
              f"{rep['final_threshold']}): {rep['model']}.",
              f"- Velocidad: {rep['seconds_per_hour']['own']} s por hora de vídeo el propio, "
              f"{rep['seconds_per_hour']['rule']} s la regla (pasos sobre la bola ya calculada).",
              "- Activarlo (solo si se adopta): `bounce_model: {use: own}` en la configuración (por defecto, la regla)."]
    return "\n".join(lines) + "\n"


def run(root: Path, cfg: dict, device: str, folds: int = 5, train_on=("tracked",), out_dir: Path | None = None,
        model_out: Path = MODEL_OUT, keys: list[str] | None = None) -> dict:
    from bench_candidates import BOUNCE_TOL_F, TRACKNET_FPS
    from tennisbio.candidates.bounce_own import VERSION, OwnBounce

    clips = load_clips(root, cfg, device, keys)
    extra = {}
    ctb_path = ROOT / "models" / "bounce_ctb.onnx"
    if ctb_path.exists():                                # reference only: never part of the decision
        from tennisbio.candidates.bounce_ctb import CatBoostBounce
        ctb = CatBoostBounce(ctb_path, device)
        extra["catboost_ref"] = lambda c: ctb.bounces(c["tracked"])
    ev = evaluate(clips, folds, train_on, BOUNCE_TOL_F, rule_on_tracked, extra)
    own, rule = ev["per_model"]["own"], ev["per_model"]["rule"]
    v = decide(own["f1"], rule["f1"], ev["bounces"])
    thr = choose_threshold(clips, folds, train_on, BOUNCE_TOL_F)
    model = OwnBounce(fit(clips, train_on), thr, {"heldout_f1": own["f1"], "rule_f1": rule["f1"], "adopt": v["adopt"],
                                                  "train_on": list(train_on), "clips": len(clips),
                                                  "generated": time.strftime("%Y-%m-%d %H:%M")})
    model.save(model_out)
    hours = ev["frames"] / TRACKNET_FPS / 3600 if ev["frames"] else None
    sph = {k: (round(s / hours, 1) if hours else None) for k, s in ev["seconds"].items()}
    rep = {"version": VERSION, "generated": time.strftime("%Y-%m-%d %H:%M"), "device": device, "folds": folds,
           "train_on": list(train_on), "tol_frames": BOUNCE_TOL_F, "margin": MARGIN, "final_threshold": thr,
           "model": str(model_out), "seconds_per_hour": sph,
           **{k: ev[k] for k in ("per_model", "thresholds", "bounces", "clips", "games", "predictions")}, "verdict": v}
    md = to_markdown(rep)
    dirs = [root / "reports"] + ([out_dir] if out_dir is not None else [])
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        (d / "bench_bounce_own.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
        (d / "bench_bounce_own.md").write_text(md, encoding="utf-8")
    print(md, flush=True)
    return rep


def output_dir(cfg: dict) -> Path | None:
    out = (cfg.get("paths") or {}).get("output")
    return Path(out) if out and Path(out).is_dir() else None     # never the repository by default


def main(argv=None):
    from bench_candidates import default_root
    from tennisbio.config import load_config

    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="carpeta de datos anotados (por defecto <salidas>/../datasets)")
    ap.add_argument("--device", default=None, help="dml, cpu… (por defecto el de la configuración)")
    ap.add_argument("--folds", type=int, default=5, help="grupos de partidos para la separación (sin mezclar partidos)")
    ap.add_argument("--with-annotated", action="store_true",
                    help="entrenar también con la bola anotada de los partidos de entrenamiento (se mide siempre con la nuestra)")
    ap.add_argument("--model-out", default=str(MODEL_OUT))
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else default_root(cfg)
    device = a.device or cfg.get("device", "cpu")
    train_on = ("tracked", "annotated") if a.with_annotated else ("tracked",)
    run(root, cfg, device, a.folds, train_on, output_dir(cfg), Path(a.model_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
