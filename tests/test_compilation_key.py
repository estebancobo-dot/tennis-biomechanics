"""13-11: a saved F3Set compilation is reused as it is. Its plan's key came back from JSON as lists and never equalled
the tuples it was compared with: the PC joined it again on every run, and the cloud (which has the compilations but
not their pieces) asked YouTube for every piece and measured nothing."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_key", ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SEGS = [{"src_t0": 12.5, "src_t1": 21.25}, {"src_t0": 100.0, "src_t1": 109.04}]


def _saved(base: Path, name: str) -> list[dict]:
    done = [dict(s, offset=o) for s, o in zip(SEGS, (0.0, 8.75))]
    (base / "videos").mkdir(parents=True)
    (base / "videos" / f"{name}.mp4").write_bytes(b"x")
    key = [[s["src_t0"], s["src_t1"]] for s in SEGS]
    (base / "videos" / f"{name}.json").write_text(json.dumps({"key": key, "segments": done}), encoding="utf-8")
    return done


def test_validate_recall_reuses_saved_compilation(tmp_path, monkeypatch):
    V = _load("validate_recall")
    done = _saved(tmp_path / "f3set" / "recall", "m1")

    def no_download(*a, **k):
        raise AssertionError("the saved compilation must be reused, not downloaded again")

    monkeypatch.setattr(V, "download", no_download)
    out, segs = V.build_compilation(tmp_path, "m1", "yt", 25.0, [dict(s) for s in SEGS])
    assert out == tmp_path / "f3set" / "recall" / "videos" / "m1.mp4"
    assert segs == done


def test_validate_recall_rebuilds_when_points_change(tmp_path, monkeypatch):
    V = _load("validate_recall")
    _saved(tmp_path / "f3set" / "recall", "m1")
    asked = []
    monkeypatch.setattr(V, "download", lambda yt, dest, t0, t1: asked.append((t0, t1)))
    out, segs = V.build_compilation(tmp_path, "m1", "yt", 25.0, [dict(s) for s in SEGS[:1]])
    assert asked == [(12.5, 21.25)] and out is None and segs == []


def test_spotting_data_reuses_saved_compilation(tmp_path):
    S = _load("spotting_data")
    done = _saved(tmp_path / "f3set" / "spotting", "m2")
    out, segs = S.local_compilation(tmp_path, "m2", None, 25.0, [dict(s) for s in SEGS])
    assert out == tmp_path / "f3set" / "spotting" / "videos" / "m2.mp4"
    assert segs == done
