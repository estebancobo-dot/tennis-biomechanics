"""fine_pass.max_fps (10-11): windows of a 50-60 fps match at half their frame rate, off by default."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from tennisbio import stages


def _ctx(tmp_path, cfg, probe):
    (tmp_path / "probe.json").write_text(json.dumps(probe), encoding="utf-8")
    return SimpleNamespace(cfg=cfg, path=lambda f: tmp_path / f)


def test_off_by_default_and_for_25_30_fps(tmp_path):
    ctx = _ctx(tmp_path, {"fine_pass": {}}, {"fps": 59.998, "width": 1920})
    args, sfx = stages._fine_cut(ctx)
    assert sfx == "" and args["cfr_fps"] is None
    ctx = _ctx(tmp_path, {"fine_pass": {"max_fps": 30}}, {"fps": 25.0, "width": 1920})
    assert stages._fine_cut(ctx)[1] == ""


def test_halves_60_progressive_and_50_fields(tmp_path):
    args, sfx = stages._fine_cut(_ctx(tmp_path, {"fine_pass": {"max_fps": 30}}, {"fps": 59.998, "width": 1920}))
    assert sfx == "_f30" and abs(args["cfr_fps"] - 29.999) < 0.01
    args, sfx = stages._fine_cut(_ctx(tmp_path, {"fine_pass": {"max_fps": 30}}, {"fps": 25.0, "interlaced": True}))
    assert sfx == "_f25" and abs(args["cfr_fps"] - 12.5) < 1e-6          # ×2 fields in cut_window: 25 frames/s


def test_bench_compare_matches_strokes_by_time():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import bench_fine_fps as B
    a = [{"match_time_s": t, "stroke": "forehand", "side": "near", "metrics": {"x": t % 7}} for t in (10, 20, 30, 40, 50, 60)]
    b = [{"match_time_s": t + 0.04, "stroke": "forehand", "side": "near", "metrics": {"x": t % 7 + 0.1}} for t in (10, 20, 30, 40, 50)]
    c = B.compare(a, b)
    assert c["matched"] == 5 and c["only_A"] == 1 and c["only_B"] == 0 and c["same_kind"] == 5
    assert c["metrics"] == 1 and c["metrics_close"] == 1
