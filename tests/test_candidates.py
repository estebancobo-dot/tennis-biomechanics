"""Candidate models of paso 2 (tennisbio.candidates, scripts/export_*.py, scripts/bench_candidates.py): their
pre/post-processing on tiny synthetic inputs with fake ONNX sessions (no download, no model file), the adoption
rule, and that no stage uses a candidate."""
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class FakeSession:
    """Stands for an onnxruntime session: one input, outputs computed by `fn` from the input array."""

    def __init__(self, fn, names=("out",), shape=("n",)):
        self.fn, self.names, self.shape, self.calls = fn, names, shape, 0

    def get_inputs(self):
        return [type("I", (), {"name": "x", "shape": list(self.shape)})()]

    def get_outputs(self):
        return [type("O", (), {"name": n})() for n in self.names]

    def run(self, _, feeds):
        self.calls += 1
        out = self.fn(feeds["x"])
        return list(out) if isinstance(out, tuple) else [out]


def _disc(h, w, x, y, r=4, value=1.0):
    m = np.zeros((h, w), np.float32)
    cv2.circle(m, (int(round(x)), int(round(y))), r, value, -1)
    return m


# ---------------------------------------------------------------- WASB

def test_wasb_blob_and_triplets():
    from tennisbio.candidates.wasb import blob_centre, normalise, triplet_index

    assert triplet_index(0, 5) == (0, 0, 1) and triplet_index(4, 5) == (3, 4, 4) and triplet_index(2, 5) == (1, 2, 3)
    m = _disc(288, 512, 100, 50, 3, 0.7) + _disc(288, 512, 400, 200, 6, 0.9)       # the bigger blob wins
    x, y, peak = blob_centre(m)
    assert abs(x - 400) < 0.5 and abs(y - 200) < 0.5 and abs(peak - 0.9) < 1e-6
    assert blob_centre(np.zeros((288, 512), np.float32)) is None
    assert normalise(np.zeros((288, 512, 3), np.uint8)).shape == (3, 288, 512)


def test_wasb_track_maps_the_middle_heatmap_to_the_frame():
    from tennisbio.candidates.wasb import WasbTracker

    def fn(x):                      # ball at (256, 144) of 512x288 in the middle frame only
        n = len(x)
        assert x.shape[1:] == (9, 288, 512)
        hm = np.zeros((n, 3, 288, 512), np.float32)
        hm[:, 1] = _disc(288, 512, 256, 144, 3, 0.95)
        hm[:, 0] = _disc(288, 512, 10, 10, 3, 0.95)          # other frames must be ignored
        return hm
    t = WasbTracker.__new__(WasbTracker)
    t.sess, t.threshold, t.batch = FakeSession(fn), 0.5, 4
    frames = [np.zeros((1080, 1920, 3), np.uint8)] * 7
    tr = t.track(frames)
    assert tr.shape == (7, 3) and np.allclose(tr[:, 0], 960, atol=1) and np.allclose(tr[:, 1], 540, atol=1)
    assert t.sess.calls == 2                                       # batches of 4
    tr2 = t.track(frames, step=2)                                  # every 2nd frame, filled in between
    assert tr2.shape == (7, 3) and np.isfinite(tr2[:, 0]).all()


# ---------------------------------------------------------------- TennisCourtDetector

def _camera():
    """A plausible broadcast homography court (m) → 1280x720 image."""
    from tennisbio.candidates.court14 import REF

    img = np.array([[359, 229], [909, 229], [207, 559], [1061, 559]], np.float32)
    H, _ = cv2.findHomography(REF[:4].astype(np.float32), img)
    return H


def test_court14_reference_points_are_the_court():
    from tennisbio.candidates.court14 import CONFS, REF
    from tennisbio.court import LENGTH, W_DOUBLES

    assert REF.shape == (14, 2) and len(CONFS) == 12 and all(len(c) == 4 and max(c) < 14 for c in CONFS)
    assert np.isclose(REF[1, 0] - REF[0, 0], W_DOUBLES) and np.isclose(REF[0, 1] - REF[2, 1], LENGTH)
    # the annotated frame of TennisCourtDetector's val split (EF-hx40Q4Mg_700) is a camera of this court: its 14
    # points are re-projected from 4 within a few px
    gt = np.array([[359, 229], [909, 229], [207, 559], [1061, 559], [428, 229], [315, 559], [841, 229], [954, 559],
                   [410, 282], [859, 283], [351, 454], [918, 454], [634, 283], [635, 454]], float)
    proj = cv2.perspectiveTransform(REF[:, None].astype(np.float32), _camera()).reshape(-1, 2)
    assert np.abs(proj - gt).max() < 6


def test_court14_homography_from_partial_points():
    from tennisbio.candidates.court14 import REF, best_homography

    H = _camera()
    pts = cv2.perspectiveTransform(REF[:, None].astype(np.float32), H).reshape(-1, 2).astype(float)
    pts[[0, 2, 12]] = np.nan                                       # some points not found
    m = best_homography(pts)
    back = cv2.perspectiveTransform(REF[:, None].astype(np.float32), m).reshape(-1, 2)
    truth = cv2.perspectiveTransform(REF[:, None].astype(np.float32), H).reshape(-1, 2)
    assert np.abs(back - truth).max() < 0.05
    assert best_homography(np.full((14, 2), np.nan)) is None


def test_court14_heatmap_point_and_refine():
    from tennisbio.candidates.court14 import heatmap_point, refine_point

    x, y = heatmap_point(_disc(360, 640, 100, 50, 15, 1.0))
    assert abs(x - 200) <= 2 and abs(y - 100) <= 2                 # heatmap px × 2 = 1280x720 px
    assert heatmap_point(np.zeros((360, 640), np.float32)) is None
    from tennisbio.candidates.court14 import _intersection
    cx, cy = _intersection((600, 300, 680, 420), (560, 380, 720, 340))
    for width, moved in ((1, True), (3, False)):     # as TennisCourtDetector: only when exactly 2 lines are left
        img = np.zeros((720, 1280, 3), np.uint8)
        cv2.line(img, (600, 300), (680, 420), (255, 255, 255), width)
        cv2.line(img, (560, 380), (720, 340), (255, 255, 255), width)
        rx, ry = refine_point(img, cx + 6, cy - 5)
        if moved:
            assert abs(rx - cx) <= 2 and abs(ry - cy) <= 2
        else:
            assert (rx, ry) == (int(cx + 6), int(cy - 5))


def test_court14_fit_end_to_end_with_fake_network():
    from tennisbio.candidates.court14 import REF, CourtTcd

    H = _camera()
    pts = cv2.perspectiveTransform(REF[:, None].astype(np.float32), H).reshape(-1, 2)

    def fn(x):
        assert x.shape == (1, 3, 360, 640)
        hm = np.zeros((1, 15, 360, 640), np.float32)
        for k, (px, py) in enumerate(pts):
            hm[0, k] = _disc(360, 640, px / 2, py / 2, 15, 1.0)
        return hm
    tcd = CourtTcd.__new__(CourtTcd)
    tcd.sess, tcd.refine = FakeSession(fn), False
    frame = np.zeros((1080, 1920, 3), np.uint8)                    # any size: points come back in its pixels
    fit = tcd.fit(frame)
    assert fit is not None and fit.score == 1.0
    assert np.abs(fit.to_image(REF) - pts * 1.5).max() < 4


# ---------------------------------------------------------------- RF-DETR

def test_rfdetr_decodes_people_only():
    from tennisbio.candidates.rfdetr import PERSON, RfDetrPeople, decode_people

    dets = np.array([[0.5, 0.5, 0.2, 0.4], [0.1, 0.1, 0.1, 0.1], [0.8, 0.2, 0.05, 0.1]], np.float32)
    logits = np.full((3, 91), -10, np.float32)
    logits[0, PERSON], logits[1, 3], logits[2, PERSON] = 4.0, 5.0, 1.0      # 1: a car; 2: a weaker person
    out = decode_people(dets, logits, 1000, 500, 0.5)
    assert out.shape == (2, 5) and out[0, 4] > out[1, 4]
    assert np.allclose(out[0, :4], [400, 150, 600, 350])
    assert decode_people(dets, logits, 1000, 500, 0.99).shape == (0, 5)
    r = RfDetrPeople.__new__(RfDetrPeople)
    r.size, r.threshold, r.names = 64, 0.5, ["dets", "labels"]
    r.sess = FakeSession(lambda x: (np.repeat(dets[None], len(x), 0), np.repeat(logits[None], len(x), 0)),
                         names=("dets", "labels"))
    assert r.prepare(np.zeros((90, 160, 3), np.uint8)).shape == (3, 64, 64)
    got = r.people([np.zeros((500, 1000, 3), np.uint8)] * 2)
    assert len(got) == 2 and got[1].shape == (2, 5)


# ---------------------------------------------------------------- RTMW-x

def test_rtmw_to_halpe26_layout():
    from tennisbio.candidates.rtmw import to_halpe26
    from tennisbio.skeleton import HALPE26

    k = np.arange(133 * 2, dtype=np.float32).reshape(1, 133, 2)
    s = np.linspace(0.1, 0.9, 133, dtype=np.float32)[None]
    hk, hs = to_halpe26(k, s)
    assert hk.shape == (1, 26, 2) and hs.shape == (1, 26)
    assert np.array_equal(hk[0, :17], k[0, :17])
    wb = {"left_big_toe": 17, "left_small_toe": 18, "left_heel": 19, "right_big_toe": 20, "right_small_toe": 21,
          "right_heel": 22}
    for name, j in wb.items():
        assert np.array_equal(hk[0, HALPE26.index(name)], k[0, j]), name
    assert np.allclose(hk[0, HALPE26.index("hip")], k[0, [11, 12]].mean(0))
    assert to_halpe26(np.zeros((0, 133, 2)), np.zeros((0, 133)))[0].shape == (0, 26, 2)


# ---------------------------------------------------------------- F3ED

def test_f3ed_crop_step_and_kinds():
    from tennisbio.candidates.f3ed import ELEMENTS, GROUPS, crop, kind_of, sample_step

    assert len(ELEMENTS) == 29 and GROUPS["outcome"][1] == 29
    assert crop(np.zeros((720, 1280, 3), np.uint8)).shape == (224, 224, 3)
    assert sample_step(25) == 2 and sample_step(29.97) == 2 and sample_step(50) == 4 and sample_step(59.94) == 4
    el = np.zeros(29)
    el[ELEMENTS.index("stroke")] = el[ELEMENTS.index("bh")] = el[ELEMENTS.index("slice")] = 1
    assert kind_of(el) == "backhand"
    el[ELEMENTS.index("volley")] = 2
    assert kind_of(el) == "other"
    el[ELEMENTS.index("serve")] = 2
    assert kind_of(el) == "serve"


def test_f3ed_decode_keeps_one_hit_per_peak():
    from tennisbio.candidates.f3ed import ELEMENTS, decode

    p = np.full(40, 0.05)
    p[[9, 10, 11]] = [0.6, 0.9, 0.7]            # one hit spread over 3 samples
    p[30] = 0.8
    hit = np.stack([1 - p, p], 1)
    el = np.zeros((40, 29))
    el[:, ELEMENTS.index("far")] = 1
    el[:, ELEMENTS.index("stroke")] = el[:, ELEMENTS.index("fh")] = 1
    out = decode(hit, el, step=2, fps=25.0)
    assert [e["t"] for e in out] == [round(10 * 2 / 25, 3), round(30 * 2 / 25, 3)]
    assert all(e["side"] == "far" and e["kind"] == "forehand" for e in out)


def test_f3ed_scores_average_overlapping_clips():
    from tennisbio.candidates.f3ed import CLIP, F3edSpotter

    def fn(x):
        assert x.shape == (1, CLIP, 3, 224, 224)
        n = x.shape[1]
        return np.tile([0.7, 0.3], (1, n, 1)).astype(np.float32), np.full((1, n, 29), 0.5, np.float32)
    s = F3edSpotter.__new__(F3edSpotter)
    s.sess, s.name = FakeSession(fn), "x"
    frames = (np.zeros((72, 128, 3), np.uint8) for _ in range(500))     # a generator: read once
    hit, el, step = s.scores(frames, 25.0)
    assert step == 2 and hit.shape == (250, 2) and el.shape == (250, 29)
    assert np.allclose(hit, [0.7, 0.3]) and np.allclose(el, 0.5)
    assert s.sess.calls == 5                                         # starts 0, 48, 96, 144 and the tail at 192


def test_f3ed_temporal_shift_matches_f3set():
    torch = pytest.importorskip("torch")
    from export_f3ed import build

    def reference(x, n_segment, fold_div=8, step=2):               # F3Set model/impl/tsm.py, inplace=False
        nt, c, h, w = x.size()
        x = x.view(nt // n_segment, n_segment, c, h, w)
        fold = c // fold_div
        out = torch.zeros_like(x)
        out[:, :-step, :fold] = x[:, step:, :fold]
        out[:, step:, fold:2 * fold] = x[:, :-step, fold:2 * fold]
        out[:, :, 2 * fold:] = x[:, :, 2 * fold:]
        return out.view(nt, c, h, w)
    m = build(clip=6).eval()
    conv1 = m._glb_feat.s1.b1.conv1
    seen = {}
    hook = conv1.net.register_forward_pre_hook(lambda mod, inp: seen.update(x=inp[0]))
    x = torch.randn(2 * 6, 32, 5, 5)
    conv1(x)
    hook.remove()
    assert torch.equal(seen["x"], reference(x, 6))
    hit, el = m(torch.randn(1, 6, 3, 64, 64))
    assert hit.shape == (1, 6, 2) and el.shape == (1, 6, 29)
    assert torch.allclose(hit.sum(-1), torch.ones(1, 6))


def test_export_networks_build():
    torch = pytest.importorskip("torch")
    import export_court_tcd
    import export_wasb

    with torch.no_grad():
        assert export_wasb.build().eval()(torch.zeros(1, 9, 64, 128)).shape == (1, 3, 64, 128)
        assert export_court_tcd.build().eval()(torch.zeros(1, 3, 32, 64)).shape == (1, 15, 32, 64)
    # module names as in the published checkpoints (strict loading on the PC depends on them)
    keys = set(export_wasb.build().state_dict())
    assert {"conv1.weight", "layer1.0.downsample.0.weight", "transition1.1.0.0.weight",
            "stage4.0.fuse_layers.3.0.0.0.weight", "final_layers.0.weight"} <= keys
    assert "conv18.block.2.running_var" in export_court_tcd.build().state_dict()


# ---------------------------------------------------------------- the measure and its rule

def test_verdict_needs_both_accuracy_and_speed():
    from bench_candidates import verdict

    assert verdict(0.9, 0.8, 30, 25, "F1", "fps")["adopt"]
    assert verdict(0.8, 0.8, 25, 25, "F1", "fps")["adopt"]                     # equal is enough
    assert not verdict(0.95, 0.8, 20, 25, "F1", "fps")["adopt"]                # more accurate but slower
    assert not verdict(0.7, 0.8, 50, 25, "F1", "fps")["adopt"]                 # faster but worse
    assert verdict(0.9, 0.8, 0.2, 0.3, "F1", "min", higher_is_faster=False)["adopt"]
    missing = verdict(None, 0.8, 30, 25, "F1", "fps")
    assert not missing["adopt"] and missing["insufficient"]          # measured again on the next run


def test_ball_and_court_scores():
    from bench_candidates import covers, prf, score_ball, score_court

    track = np.full((10, 3), np.nan)
    track[2] = (100, 100, 1)
    track[4] = (300, 300, 1)                    # 50 px off: a false one and a miss
    track[6] = (10, 10, 1)                      # ball not visible there: a false one
    rows = [(2, 1, 103, 104), (4, 1, 350, 300), (6, 0, 0, 0), (8, 1, 5, 5)]
    s = score_ball(track, rows)
    assert (s["tp"], s["fp"], s["fn"]) == (1, 2, 2) and s["median_err_px"] == 5.0
    assert prf(0, 0, 0)["f1"] is None and prf(3, 1, 0)["precision"] == 0.75
    gt = np.array([[10, 10], [100, 10], [5000, 10]], float)                      # the last is out of the frame
    assert score_court(gt + [3, 4], gt, (720, 1280)) == (2, 2, [5.0, 5.0])
    assert score_court(None, gt, (720, 1280))[:2] == (0, 2)
    assert covers([100, 100, 120, 160], [125, 90, 4, 4]) and not covers([100, 100, 120, 160], [200, 90, 4, 4])


def test_tcd_dataset_is_read_by_ranges(tmp_path, monkeypatch):
    import bench_candidates as B

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("data/data_val.json", json.dumps([{"id": f"im{i}", "kps": [[i, i]] * 14} for i in range(6)]))
        for i in range(6):
            z.writestr(f"data/images/im{i}.png", cv2.imencode(".png", np.full((4, 4, 3), i, np.uint8))[1].tobytes())
        z.writestr("data/data_train.json", "x" * 200000)
    blob = buf.getvalue()
    asked = []

    class Resp(io.BytesIO):
        def __init__(self, data, rng):
            super().__init__(data)
            self.headers = {"Content-Range": f"bytes {rng}/{len(blob)}"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        assert timeout is not None
        a, b = map(int, re.match(r"bytes=(\d+)-(\d+)", req.headers["Range"]).groups())
        asked.append((a, b))
        return Resp(blob[a:b + 1], f"{a}-{b}")
    monkeypatch.setattr(B.urllib.request, "urlopen", urlopen)
    f = B.HttpFile("https://example.invalid/x.zip", block=4096)
    items = B.tcd_val(tmp_path, 3)
    assert [p.name for p, _ in items] == ["im0.png", "im2.png", "im4.png"] and items[1][1].shape == (14, 2)
    assert all(p.exists() for p, _ in items) and f.size == len(blob)
    assert sum(b - a + 1 for a, b in asked) < len(blob) * 4            # never the whole file per member
    assert B.tcd_val(tmp_path, 3)[0][0].exists()                        # cached: no more requests
    n = len(asked)
    B.tcd_val(tmp_path, 3)
    assert len(asked) == n


def test_markdown_report_lists_every_candidate():
    from bench_candidates import CANDIDATES, to_markdown

    rep = {"generated": "x", "device": "dml", "results": {
        "wasb": {"baseline": "ours", "accuracy": "F1 0.9 / 0.8", "speed": "30 / 25 fps",
                 "verdict": {"adopt": True, "reason": "ok"}, "notes": ["n"]},
        "court14": {"error": "RuntimeError: boom"}}}
    md = to_markdown(rep)
    assert all(f"| {c} |" in md for c in CANDIDATES) and "**sí**" in md and "boom" in md


def test_no_stage_uses_a_candidate():
    """Candidates are measured, not used: nothing outside tennisbio/candidates imports them."""
    src = ROOT / "src" / "tennisbio"
    bad = [f.relative_to(src).as_posix() for f in src.rglob("*.py")
           if "candidates" not in f.relative_to(src).parts and "candidates" in f.read_text(encoding="utf-8")
           and re.search(r"(from|import)\s+[.\w]*candidates", f.read_text(encoding="utf-8"))]
    assert not bad, bad
