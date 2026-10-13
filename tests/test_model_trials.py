"""The automatic model trials recommend a variant only when it is as good on every count."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from model_trials import recommend  # noqa: E402


def test_recommend_only_when_better_in_everything():
    base = {"gt": 20, "f1": 0.80, "jerk_pct": 0.50, "ms_per_frame": 100.0, "feet_seen": None, "kp_diff_vs_fp32_px": None}
    res = {
        "yolo11m-pose@960": base,
        "faster": {"f1": 0.79, "jerk_pct": 0.50, "ms_per_frame": 60.0, "feet_seen": None, "kp_diff_vs_fp32_px": None},
        "feet": {"f1": 0.81, "jerk_pct": 0.40, "ms_per_frame": 150.0, "feet_seen": 0.9, "kp_diff_vs_fp32_px": None},
        "worse_f1": {"f1": 0.70, "jerk_pct": 0.40, "ms_per_frame": 30.0, "feet_seen": 0.9, "kp_diff_vs_fp32_px": None},
        "shaky": {"f1": 0.85, "jerk_pct": 0.80, "ms_per_frame": 30.0, "feet_seen": None, "kp_diff_vs_fp32_px": None},
        "fp16_moves": {"f1": 0.80, "jerk_pct": 0.50, "ms_per_frame": 50.0, "feet_seen": None, "kp_diff_vs_fp32_px": 3.0},
        "broken": {"error": "RuntimeError: x"},
    }
    rec = " ".join(recommend(res, "yolo11m-pose@960"))
    assert "faster:" in rec and "feet:" in rec
    for v in ("worse_f1", "shaky", "fp16_moves", "broken"):
        assert v + ":" not in rec


def test_variants_parse():
    from tennisbio.pose.variants import BASELINE, VARIANTS

    assert BASELINE in VARIANTS and all(v.startswith(("yolo11m-pose@", "rtmpose-", "hybrid-")) for v in VARIANTS)
