"""Guard (08-11): every validation script that reports stroke detection measures the SAME detector as the
analysis (its stages with the user's configuration: the learned spotter when `spotter.enabled`), unless it is
run with an explicit --legacy flag. PC request 154 measured the old clip path (run_clip) by default and its
numbers were read as the analysis's."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_guard", SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def detection_scripts():
    """scripts/validate_*.py that score strokes against annotations (impact_eval / recall_eval)."""
    return sorted(p.stem for p in SCRIPTS.glob("validate_*.py")
                  if re.search(r"validation(\.| import )(impact_eval|recall_eval|rv_eval)|import recall_eval as",
                               p.read_text(encoding="utf-8")))


def test_detection_scripts_are_known():
    assert {"validate_rv_strokes", "validate_recall", "validate_f3set"} <= set(detection_scripts())


@pytest.mark.parametrize("name", detection_scripts())
def test_each_detection_script_declares_its_detector(name):
    src = (SCRIPTS / f"{name}.py").read_text(encoding="utf-8")
    m = _load(name)
    assert getattr(m, "DETECTOR", None) in ("pipeline", "legacy"), f"{name}: falta DETECTOR"
    if "run_clip(" in src:               # the old clip path is only reachable behind an explicit flag
        assert '"--legacy"' in src, f"{name}: usa run_clip sin --legacy"
    if m.DETECTOR == "pipeline":
        assert "pipeline.run(" in src or "run_clip_pipeline(" in src


def _fake_rv(monkeypatch, V, tmp_path, calls):
    (tmp_path / "rv").mkdir()
    monkeypatch.setattr(V, "fetch", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                       dest.write_text(json.dumps([["m1", "000"]]) if dest.suffix == ".json"
                                                                       else "Frame,Visibility,X,Y\n"), dest)[2])
    monkeypatch.setattr(V, "racketvision_video", lambda root, m, c: tmp_path / f"{m}_{c}.mp4")
    monkeypatch.setattr(V, "read_ball_csv", lambda p: [])
    monkeypatch.setattr(V, "hits_from_ball", lambda b, h: {"near": [100], "far": [300]})
    monkeypatch.setattr(V, "run_clip", lambda *a, **k: calls.append("run_clip") or (_ for _ in ()).throw(AssertionError("legacy")))
    monkeypatch.setattr(V, "output_dir", lambda: None)


def test_rv_default_runs_the_analysis_stages_with_the_configured_spotter(monkeypatch, tmp_path):
    from tennisbio import pipeline
    from tennisbio.config import load_config
    from tennisbio.stages import spotter_on

    V = _load("validate_rv_strokes")
    assert V.DETECTOR == "pipeline"
    calls, seen = [], {}

    def fake_run(ctx, *a, **k):                       # the analysis's stage runner, not run_clip
        calls.append("pipeline")
        seen["spotter"] = spotter_on(ctx.cfg)
        d = ctx.dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "probe.json").write_text(json.dumps({"fps": 50.0}))
        (d / "manifest.json").write_text(json.dumps({"spotting": {"summary": {"enabled": True}},
                                                     "candidates": {"summary": {"source": "spotter"}}}))
        (d / "spotting.json").write_text(json.dumps([{"t": 2.0, "side": "near"}]))
        (d / "strokes.json").write_text(json.dumps([{"match_time_s": 2.02, "side": "near"}]))
        (d / "strokes_doubtful.json").write_text(json.dumps([{"match_time_s": 6.0, "side": "far"}]))
        return []
    monkeypatch.setattr(pipeline, "run", fake_run)
    _fake_rv(monkeypatch, V, tmp_path, calls)
    assert V.main(["--root", str(tmp_path), "--clips", "1"]) == 0
    assert calls == ["pipeline"]
    assert seen["spotter"] == spotter_on(load_config())        # the same detector as the analysis
    res = json.loads((tmp_path / "reports" / "rv_validation.json").read_text(encoding="utf-8"))
    assert res["path"] == "production" and (tmp_path / "reports" / "rv_validation.md").exists()
    assert res["summary"]["near"]["true_positives"] == 1 and res["summary"]["far"]["detected"] == 1
    assert res["summary"]["far"]["true_positives"] == 1            # doubtful strokes count (identity is not measured)
    assert any("sonido" in n for n in res["notes"])


def test_rv_legacy_only_with_the_flag_and_labelled(monkeypatch, tmp_path):
    from tennisbio import pipeline

    V = _load("validate_rv_strokes")
    calls = []
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: calls.append("pipeline"))
    _fake_rv(monkeypatch, V, tmp_path, calls)

    class R:
        strokes, fps, tracked_frac = [], 50.0, 1.0
    monkeypatch.setattr(V, "run_clip", lambda *a, **k: calls.append("run_clip") or R())
    monkeypatch.setattr(V, "is_doubles", lambda *a: False)
    assert V.main(["--legacy", "--root", str(tmp_path), "--clips", "1"]) == 0
    assert calls == ["run_clip"]
    out = json.loads((tmp_path / "reports" / "rv_strokes_validation_near.json").read_text())
    assert out["path"] == "legacy" and "LEGACY" in out["path_label"]


def test_rv_spotter_failure_is_said_not_replaced(monkeypatch, tmp_path):
    from tennisbio import pipeline

    V = _load("validate_rv_strokes")
    calls = []

    def boom(ctx, *a, **k):
        raise FileNotFoundError("falta el detector de golpes entrenado (models/spotting.onnx)")
    monkeypatch.setattr(pipeline, "run", boom)
    monkeypatch.setattr("tennisbio.stages.spotter_on", lambda c: True)
    _fake_rv(monkeypatch, V, tmp_path, calls)
    assert V.main(["--root", str(tmp_path), "--clips", "1"]) == 1
    res = json.loads((tmp_path / "reports" / "rv_validation.json").read_text(encoding="utf-8"))
    assert res["spotter_unavailable"] and res["clips_used"] == 0 and calls == []
    assert "no ha podido ejecutarse" in (tmp_path / "reports" / "rv_validation.md").read_text(encoding="utf-8")


def test_f3set_needs_the_legacy_flag(monkeypatch, capsys):
    V = _load("validate_f3set")
    assert V.DETECTOR == "legacy"
    monkeypatch.setattr(V, "run_clip", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran legacy")))
    assert V.main(["--root", "nada"]) == 2
    assert "validate_recall" in capsys.readouterr().out


def test_recall_default_uses_the_configured_detector(monkeypatch, tmp_path):
    from tennisbio import pipeline
    from tennisbio.config import load_config
    from tennisbio.stages import spotter_on

    V = _load("validate_recall")
    assert V.DETECTOR == "pipeline"
    seen = {}

    def fake_run(ctx, names=None, **k):
        seen["spotter"] = spotter_on(ctx.cfg)
        ctx.dir.mkdir(parents=True, exist_ok=True)
        return ["fine"]
    monkeypatch.setattr(pipeline, "run", fake_run)
    monkeypatch.setattr("tennisbio.catalog.load_player", lambda pid: type("P", (), {"name": "X", "hand": "right"})())
    V.run_pipeline(tmp_path / "v.mp4", "m", "rybakina", "Y", tmp_path, False)
    assert seen["spotter"] == spotter_on(load_config())
