"""Export the learned ball-bounce model (CatBoost regressor of yastrebksv/TennisProject) to ONNX.

Candidate of paso 2.5 (B3, request #199): measured on the PC against our rule (the sharpest turn of the ball path
between two hits, tennisbio.ball.bounce_before / bounce_after) with scripts/bench_candidates.py; not used by any
stage. github.com/JustinSongXh/tennisvision (`tennisvision/bounce/catboost.py`) uses this same model, ported
unchanged; it publishes no weights and no annotated bounces of its own.

The model reads 12 features of the ball path per frame (x/y differences to the frames 1 and 2 before and after
and their ratios; tennisbio.candidates.bounce_ctb) and gives a bounce score per frame. It was trained by
yastrebksv/TrackNet `bounce_train.py` on the TrackNet tennis dataset (10 broadcast games, frame status 2 =
bounce) with a random 75/25 split of its frames: every game of that dataset was seen in training.

Weights: Google Drive file 1Eo5HDnAQE8y_FbOftKZ8pjiojwuy2BmJ (ctb_regr_bounce.cbm, 332 976 bytes), linked from
https://github.com/yastrebksv/TennisProject (README, "Bounce detection"); the repository has no licence file.

    uv run --with catboost==1.2.10 python scripts/export_bounce_ctb.py [--out models/bounce_ctb.onnx]

Needs catboost only here (CatBoost writes the ONNX file itself: an ai.onnx.ml TreeEnsembleRegressor that
onnxruntime runs on the CPU, also in the DirectML package). Prints the largest difference between the ONNX
model (onnxruntime CPU) and CatBoost on random features.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import download  # noqa: E402

URL = "https://drive.usercontent.google.com/download?id=1Eo5HDnAQE8y_FbOftKZ8pjiojwuy2BmJ&export=download&confirm=t"
N_FEATURES = 12


def check(cbm: Path, onnx_path: Path, n: int = 4096, seed: int = 0) -> float:
    """Largest absolute difference between CatBoost and its ONNX export on random features (the scale of real
    ones: differences of tens of px, ratios around 1, a few huge ratios when the ball stops)."""
    import catboost as ctb
    import numpy as np
    import onnxruntime as ort

    rng = np.random.default_rng(seed)
    x = rng.normal(0, 20, (n, N_FEATURES)).astype(np.float32)
    x[:, [4, 5, 10, 11]] = rng.lognormal(0, 1.5, (n, 4)) * rng.choice([-1, 1], (n, 4))
    x[:, [0, 1, 2, 3]] = np.abs(x[:, [0, 1, 2, 3]])                 # |x| differences
    m = ctb.CatBoostRegressor()
    m.load_model(str(cbm))
    ref = m.predict(x.astype(np.float64))
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    got = sess.run(None, {sess.get_inputs()[0].name: x})[0].reshape(-1)
    return float(np.abs(ref - got).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cbm", default="models/bounce_ctb.cbm")
    ap.add_argument("--out", default="models/bounce_ctb.onnx")
    args = ap.parse_args()
    import catboost as ctb

    cbm = download(URL, Path(args.cbm))
    m = ctb.CatBoostRegressor()
    m.load_model(str(cbm))
    names = list(m.feature_names_ or [])
    if len(names) != N_FEATURES:
        raise SystemExit(f"el modelo espera {len(names)} rasgos, no {N_FEATURES}")
    print("rasgos:", names)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save_model(str(out), format="onnx", export_parameters={"onnx_domain": "ai.catboost", "onnx_model_version": 1,
                                                             "onnx_graph_name": "bounce_ctb"})
    diff = check(cbm, out)
    print(f"guardado {out}; diferencia máxima ONNX frente a CatBoost: {diff:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
