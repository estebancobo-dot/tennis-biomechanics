"""Request #139 «si se pierde calidad no tocamos nada» (14-10): the speed-ups that lose quality (a lighter pose,
fewer pixels, no far-side strokes) stay off; a speed-up is adopted only when measured with the same result, and the
configuration says that measure next to it. Run on the PC with the other tests (pruebas.xml), so the audit ties
#139 to this module."""
import re
from pathlib import Path

import yaml

from tennisbio import stages

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "config" / "default.yaml"


def _cfg() -> dict:
    return yaml.safe_load(DEFAULT.read_text(encoding="utf-8"))


def test_the_fine_pass_keeps_its_full_quality_models():
    fp = _cfg()["fine_pass"]
    # YOLO11m-pose finds her, RTMPose-x (or RTMW-x, measured with the same strokes, tremor and feet) redoes her:
    # never the YOLO pose alone (no feet) nor a lighter model
    assert fp["pose_model"] == "hybrid"
    assert fp["refine"] in ("rtmpose-x", "rtmw-x")
    assert fp["pose"] == "performance" and fp["detector"] != "lightweight"
    assert _cfg().get("fine_imgsz", 960) >= 960                     # the fine pass is not read at fewer pixels


def test_far_side_strokes_are_still_analysed():
    src = (ROOT / "src" / "tennisbio" / "stages.py").read_text(encoding="utf-8")
    body = src[src.index("def st_fine("):src.index("def opponent_profile(")]
    assert 'if c.get("side", "near") == "far":' in body and "return who is True" in body


def test_every_half_precision_switch_states_its_measured_difference():
    """fp16 changes the numbers a little: each one switched on says next to it what was measured (px of difference,
    the same strokes), as the adoption rule asks."""
    lines = DEFAULT.read_text(encoding="utf-8").splitlines()
    bad, seen = [], 0
    for i, ln in enumerate(lines):
        if re.match(r"\s*fp16:\s*true\b", ln):
            seen += 1
            j, notes = i - 1, []
            while j >= 0 and lines[j].strip().startswith("#"):
                notes.append(lines[j])
                j -= 1
            if not re.search(r"\d\s*px", " ".join(notes)):
                bad.append(f"línea {i + 1}: {ln.strip()} sin su medida")
    assert seen and not bad, bad


def test_speed_only_settings_do_not_change_what_the_fine_pass_computes():
    """fine_speed (threads, ball ahead) and the ball's fp16 are speed only: outside the fine pass's fingerprint, so
    they can never be traded for quality without it showing as a new result."""
    c = _cfg()
    base = stages._fine_settings(c)
    faster = {**c, "fine_speed": {**(c.get("fine_speed") or {}), "ball_ahead_threads": 8, "workers": 3},
              "ball": {**(c.get("ball") or {}), "fp16": not (c.get("ball") or {}).get("fp16")}}
    assert stages._fine_settings(faster) == base
    lighter = {**c, "fine_pass": {**c["fine_pass"], "refine": "rtmpose-m"}}
    assert stages._fine_settings(lighter) != base                   # a lighter model would be a new result
