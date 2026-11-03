"""Scoreboard OCR with PP-OCRv5 (candidate, request #201): rapidocr 3.x with the PP-OCRv5 mobile text detector and
recogniser (ONNX, published by RapidAI; scripts/export_ppocrv5.py), against what the `score` stage uses today
(rapidocr-onnxruntime 1.4, its PP-OCRv4 models).

rapidocr 3.x is not a dependency of the project (it brings opencv-python-headless next to our opencv-python): the
measure runs it in a separate environment, `uv run --with rapidocr==3.10.0` (scripts/bench_ocr.py). Its onnxruntime
is the installed one (DirectML on the PC); it downloads nothing here, every model path is given.

RapidOcr3 has the call of rapidocr-onnxruntime's RapidOCR (img, use_cls=…) → ([box, text, score] list, elapse), so
tennisbio.scoreboard.ScoreReader reads the scoreboard with either engine unchanged: only the OCR differs.

There is no annotated scoreboard set: the comparison is agreement and consistency, not accuracy against truth.
consistent() says which readings of one engine can follow each other as tennis scores do (tennisbio.point_count's
rules, per reading); agreement() compares the two engines' states frame by frame."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

RAPIDOCR3 = "rapidocr==3.10.0"
BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0"
# rapidocr 3.10.0 default_models.yaml (onnxruntime / PP-OCRv5 / mobile), with its SHA256
MODELS = {
    "det": ("ch_PP-OCRv5_det_mobile.onnx", f"{BASE}/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx",
            "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae"),
    "rec": ("ch_PP-OCRv5_rec_mobile.onnx", f"{BASE}/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx",
            "5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5"),
}
# the same models as PyTorch weights (rapidocr's torch engine), only for the export check
TORCH = {
    "det": ("ch_PP-OCRv5_det_mobile.pth", f"{BASE}/torch/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.pth",
            "df848ed5060bac4d0f6e58572aea97d92e909a8a87cf292849237b0e84f6ffdb"),
    "rec": ("ch_PP-OCRv5_rec_mobile.pth", f"{BASE}/torch/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.pth",
            "d20ee8dac2ca63e2d1989b02ecc42595c71d61bf8dd8c8ddc5ad2ee68e7b5be2"),
}
MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "ppocrv5"


def to_items(boxes, txts, scores) -> list:
    """rapidocr 3.x output (boxes (n, 4, 2), texts, scores) → rapidocr 1.x items [[box, text, score], …]."""
    if boxes is None or txts is None:
        return []
    return [[[[float(x), float(y)] for x, y in b], str(t), float(s)] for b, t, s in zip(boxes, txts, scores)]


class RapidOcr3:
    """rapidocr 3.x with PP-OCRv5, called like rapidocr-onnxruntime's RapidOCR."""

    def __init__(self, model_dir: str | Path = MODEL_DIR, device: str = "cpu"):
        from rapidocr import RapidOCR

        d = Path(model_dir)
        params = {"Global.log_level": "warning",
                  "Det.model_path": str(d / MODELS["det"][0]), "Rec.model_path": str(d / MODELS["rec"][0]),
                  "EngineConfig.onnxruntime.use_dml": device == "dml"}
        self.engine = RapidOCR(params=params)

    def __call__(self, img, use_cls: bool = True):
        out = self.engine(img, use_cls=use_cls)
        return to_items(getattr(out, "boxes", None), getattr(out, "txts", None), getattr(out, "scores", None)), \
            getattr(out, "elapse", None)


# ---------------------------------------------------------------- comparison without ground truth

def state_key(reading: dict | None):
    """(games per set, point ranks) of a reading as tennisbio.point_count reads it, or None when it cannot be read
    as a score (flagged by the reader, impossible games or points)."""
    from ..point_count import _state

    if not reading:
        return None
    s = _state({"t": 0.0, **reading})
    return None if s is None else (s["games"], s["pts"])


def consistent(readings: list[dict]) -> list[bool]:
    """For each reading (input order): does it fit the match's score sequence by tennis rules? The rules of
    tennisbio.point_count.clean_states, per reading instead of merged: a valid state; the games played only grow
    (longest non-decreasing sequence in time); for each total of games the most read set of games; inside a game the
    points only grow (outside deuce)."""
    from ..point_count import _in_game, _lnds, _state

    st = [(i, s) for i, s in ((i, _state(r)) for i, r in enumerate(readings or [])) if s is not None]
    ok = [False] * len(readings or [])
    if not st:
        return ok
    st.sort(key=lambda p: p[1]["t"])
    st = [st[k] for k in _lnds([s["g"] for _, s in st])]
    modal = {g: Counter(s["games"] for _, s in st if s["g"] == g).most_common(1)[0][0] for g in {s["g"] for _, s in st}}
    last = None
    for i, s in st:
        if s["games"] != modal[s["g"]]:
            continue
        if last is not None and last["g"] == s["g"] and _in_game(last, s) is None:
            continue
        ok[i], last = True, s
    return ok


def agreement(a: list, b: list) -> dict:
    """Frame-by-frame comparison of two engines' readings of the same samples (None = no reading): how many both
    read, and of those how many give the same games and points."""
    both = same = only_a = only_b = 0
    for ra, rb in zip(a, b):
        ka, kb = state_key(ra), state_key(rb)
        if ka is not None and kb is not None:
            both += 1
            same += ka == kb
        elif ka is not None:
            only_a += 1
        elif kb is not None:
            only_b += 1
    return {"both": both, "same": same, "same_share": round(same / both, 3) if both else None,
            "only_first": only_a, "only_second": only_b}
