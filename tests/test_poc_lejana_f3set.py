"""22-11 (#312 point 3): F3Set today lost 5 strokes, all on the far side; the measure of the far player's detector on
F3Set's own broadcasts (RF-DETR against YOLO, with the fine pass's own search) and its rule written before measuring."""
import sys
from pathlib import Path

from tennisbio.infra import poc_lejana_f3set as P

ROOT = Path(__file__).resolve().parents[1]


def test_the_far_strokes_and_the_rule():
    rep = {"strokes": [{"side": "far", "t_clip": float(i), "match": "m"} for i in range(10)]
           + [{"side": "near", "t_clip": 1.0, "match": "m"}, {"side": "far", "t_clip": None, "match": "m"}]}
    rows = P.far_strokes(rep, 5)
    assert len(rows) == 5 and all(r["side"] == "far" for r in rows) and rows[1]["t_clip"] == 2.0
    assert P.decide({"yolo": {"share": 0.95}, "rfdetr": {"share": 0.94}})["pasa"] is True          # within 0.02
    d = P.decide({"yolo": {"share": 0.95}, "rfdetr": {"share": 0.90}})
    assert d["pasa"] is False and d["resultado"] == "vuelve YOLO"
    assert P.decide({"yolo": {"share": None}})["pasa"] is False


def test_it_runs_on_kaggle_with_f3sets_clips_and_both_detectors():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    assert correr.POCS["lejana_f3set"] == "tennisbio.infra.poc_lejana_f3set"
    args = correr.poc_args({"prueba": "lejana_f3set"}, Path("/d/models"), None)
    assert "--referencia" in args and args[args.index("--raiz") + 1] == str(Path("/d/datasets"))
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert 'job["prueba"] in ("lejana", "lejana_f3set")' in src and 'job["prueba"] in ("f3set", "lejana_f3set")' in src
