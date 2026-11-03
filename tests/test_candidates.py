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


# ---------------------------------------------------------------- paso 2.5: learned bounce (CatBoost, TennisProject)

def _v_path(n=40, bounce=20):
    """A ball falling then rising in the image (y down): a bounce at `bounce`, x moving steadily."""
    t = np.arange(n)
    x = 100 + 5.0 * t
    y = np.where(t <= bounce, 200 + 8.0 * t, 200 + 8.0 * bounce - 6.0 * (t - bounce))
    return np.stack([x, y], 1)


def test_bounce_features_follow_the_model_columns():
    from tennisbio.candidates.bounce_ctb import features

    tr = _v_path()
    tr[5] = np.nan                                                   # not seen: frames 3-7 have no full window
    f, fr = features(tr[:, 0], tr[:, 1])
    assert f.shape == (len(fr), 12) and f.dtype == np.float32
    assert fr[0] == 2 and fr[-1] == 37 and not {3, 4, 5, 6, 7} & set(fr.tolist())
    row = f[list(fr).index(20)]                                      # at the bounce: y came down, goes back up
    assert row.tolist()[:4] == [5, 10, 5, 10]                        # |x| diffs: lag 1, 2, ahead 1, 2
    assert np.isclose(row[4], 1) and np.isclose(row[5], 1)           # their ratios
    assert row[6] == -8 and row[8] == -6 and np.isclose(row[10], 8 / 6)   # y before − y, y after − y, their ratio


def test_bounce_smooth_fills_short_gaps_only():
    from tennisbio.candidates.bounce_ctb import smooth

    tr = _v_path()
    x, y = tr[:, 0].copy(), tr[:, 1].copy()
    x[10] = y[10] = np.nan                                           # after 5 seen frames: extrapolated
    x[2] = y[2] = np.nan                                             # too early: stays missing
    sx, sy = smooth(x, y)
    assert np.isclose(sx[10], tr[10, 0], atol=0.5) and np.isclose(sy[10], tr[10, 1], atol=0.5)
    assert np.isnan(sx[2])
    x2, y2 = tr[:, 0].copy(), tr[:, 1].copy()
    x2[10] = y2[10] = np.nan
    y2[11] += 200                     # a jump right after the fill: dropped, then extrapolated in turn (as upstream)
    _, sy2 = smooth(x2, y2)
    assert np.isclose(sy2[11], tr[11, 1], atol=0.5)


def test_bounce_peaks_and_detector_with_fake_model():
    from tennisbio.candidates.bounce_ctb import CatBoostBounce, peaks

    s = np.array([0.1, 0.5, 0.9, 0.6, 0.1, 0.7, 0.1])
    assert peaks(np.array([1, 2, 3, 5]), s) == [2, 5]

    def fn(x):                                     # high score where y turns back up (y_diff_1 and y_diff_inv_1 < 0)
        return (((x[:, 6] < 0) & (x[:, 8] < 0)).astype(np.float32) * 0.9)[:, None]
    d = CatBoostBounce.__new__(CatBoostBounce)
    d.sess, d.threshold = FakeSession(fn), 0.45
    assert d.bounces(_v_path()) == [20]
    full = np.repeat(_v_path(), 2, axis=0)                           # a 60 fps track read at 30 fps
    assert d.bounces(full, step=2) == [40]
    assert d.bounces(np.full((10, 2), np.nan)) == []


def test_bounce_rule_and_event_matching():
    from bench_candidates import match_events, rule_bounces

    tr = _v_path(60, 30)
    tr[46:, 1] = tr[45, 1] + 8.0 * np.arange(1, 15)                 # hit at 45: the ball comes down again
    got = rule_bounces(tr, [10, 45], 30.0)
    assert 30 in got and all(f > 10 for f in got)
    assert rule_bounces(tr, [], 30.0) == []
    assert match_events([10, 31, 50], [30, 12], 3) == (2, 1, 0, [1, 2])
    assert match_events([], [5], 3) == (0, 0, 1, [])


def test_tracknet_labels_are_read_with_blanks(tmp_path):
    from bench_candidates import read_tracknet

    p = tmp_path / "Label.csv"
    p.write_text("file name,visibility,x-coordinate,y-coordinate,status\n0000.jpg,1,599,423,0\n0001.jpg,0,,,\n"
                 "0002.jpg,1,601,388,2\n0003.jpg,2,600,380,1.0\n")
    names, tr, st = read_tracknet(p)
    assert names[2] == "0002.jpg" and np.isnan(tr[1]).all() and tr[2].tolist() == [601, 388]
    assert st.tolist() == [0, -1, 2, 1]


# ---------------------------------------------------------------- paso 2.5: scoreboard OCR (PP-OCRv5)

def test_ocr5_items_like_rapidocr_1():
    from tennisbio.candidates.ocr5 import MODELS, TORCH, to_items

    boxes = np.array([[[0, 0], [10, 0], [10, 5], [0, 5]]], np.float32)
    items = to_items(boxes, ("ABC 6",), (0.93,))
    assert items == [[[[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]], "ABC 6", pytest.approx(0.93)]]
    assert to_items(None, None, None) == []
    assert all(len(v[2]) == 64 and v[1].startswith("https://www.modelscope.cn/") for v in {**MODELS, **TORCH}.values())


def _reading(t, games, points, flags=()):
    return {"t": t, "games": games, "points": points, "flags": list(flags)}


def test_ocr5_consistency_follows_tennis_rules():
    from tennisbio.candidates.ocr5 import consistent

    rs = [_reading(0, [[2, 1]], ["15", "0"]), _reading(5, [[2, 1]], ["30", "0"]),
          _reading(10, [[2, 1]], ["15", "0"]),                       # points going back in the game: a misread
          _reading(15, [[2, 7]], ["0", "0"]),                       # games total jumps then falls: not in sequence
          _reading(20, [[3, 1]], ["0", "15"]), _reading(25, [[3, 1]], ["0", "15"], ["columns_mismatch"]),
          {}, _reading(30, [[3, 1]], ["X", "15"])]
    assert consistent(rs) == [True, True, False, False, True, False, False, False]
    assert consistent([]) == []


def test_ocr5_agreement_frame_by_frame():
    from tennisbio.candidates.ocr5 import agreement

    a = [_reading(0, [[1, 0]], ["15", "0"]), _reading(0, [[1, 0]], ["30", "0"]), None, _reading(0, [[1, 1]], ["0", "0"])]
    b = [_reading(0, [[1, 0]], ["15", "0"]), _reading(0, [[1, 0]], ["40", "0"]), _reading(0, [[1, 0]], ["0", "0"]), None]
    assert agreement(a, b) == {"both": 2, "same": 1, "same_share": 0.5, "only_first": 1, "only_second": 1}


def test_ocr_samples_read_and_missed():
    from bench_candidates import ocr_samples

    score = {"readings": [{"t": 10.5}, {"t": 15.5}, {"t": 20.5}, {"t": 25.5}],
             "shots": [{"start": 10.0, "end": 30.0, "tried": 5, "read": 4}, {"start": 40.0, "end": 50.0, "tried": 2, "read": 2}]}
    read, missed = ocr_samples(score, 2, 5.0)
    assert read == [10.5, 20.5] and missed == []                    # every try of the failing shot was read
    score["shots"][0]["end"] = 36.0                                  # two more tries there: 30.5 and 35.5
    _, missed = ocr_samples(score, 4, 5.0)
    assert missed == [30.5, 35.5]


# ---------------------------------------------------------------- paso 2.5: MotionAGFormer

def _coco_person(T=5):
    """A standing person (COCO-17, image px) seen from the front."""
    base = np.array([[100, 20], [95, 15], [105, 15], [90, 18], [110, 18], [80, 40], [120, 40], [75, 70], [125, 70],
                     [72, 95], [128, 95], [88, 100], [112, 100], [88, 140], [112, 140], [88, 180], [112, 180]], float)
    return np.repeat(base[None], T, 0), np.full((T, 17), 0.9)


def test_mag_coco_to_h36m_and_flip():
    from tennisbio.candidates.motionagformer import (H36M_L_HIP, H36M_L_SH, H36M_R_HIP, H36M_R_SH, clips,
                                                     coco_to_h36m, flip, normalise)

    k, s = _coco_person()
    h, hs = coco_to_h36m(k, s)
    assert h.shape == (5, 17, 2) and hs.shape == (5, 17)
    assert np.allclose(h[0, 0], [100, 100])                          # pelvis: between the hips
    assert np.allclose(h[0, H36M_L_SH], k[0, 5]) and np.allclose(h[0, H36M_R_SH], k[0, 6])
    assert np.allclose(h[0, H36M_L_HIP], k[0, 11]) and np.allclose(h[0, H36M_R_HIP], k[0, 12])
    assert np.isclose(hs[0, 0], 0.9)
    x = np.random.default_rng(0).normal(size=(3, 17, 3))
    assert np.allclose(flip(flip(x)), x)
    assert np.allclose(normalise(np.array([[0, 0], [1920, 1080]]), 1920, 1080), [[-1, -0.5625], [1, 0.5625]])
    c = clips(60, 27)
    assert [len(i) for i in c] == [27, 27, 27] and set(np.concatenate(c).tolist()) == set(range(60))
    short = clips(10, 27)[0]
    assert len(short) == 27 and short[0] == 0 and short[-1] == 9 and (np.diff(short) >= 0).all()


def test_mag_lifter_with_fake_model():
    from tennisbio.candidates.motionagformer import H36M_L_SH, H36M_R_SH, MotionAGFormerLifter, line_yaw_world

    def fn(x):                          # "lift": x, y as given, depth 0 (a flat person facing the camera)
        assert x.shape == (2, 27, 17, 3)
        y = x.copy()
        y[..., 2] = 0
        return y
    lf = MotionAGFormerLifter.__new__(MotionAGFormerLifter)
    lf.sess, lf.length, lf.name = FakeSession(fn, shape=(2, 27, 17, 3)), 27, "x"
    k, s = _coco_person(40)
    k[7] = np.nan                                                    # one frame without 2D: filled, not a crash
    X = lf.lift(k, s, 200, 200)
    assert X.shape == (40, 17, 3) and np.allclose(X[:, 0], 0) and np.isfinite(X).all()
    # a camera looking along world +y (z up): image right is world +x, so the shoulders read along world +x
    r_c2w = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
    assert np.allclose(line_yaw_world(X, H36M_L_SH, H36M_R_SH, r_c2w), 0, atol=1e-4)
    assert lf.lift(np.full((5, 17, 2), np.nan), np.zeros((5, 17)), 200, 200).shape == (5, 17, 3)


def test_mag_network_matches_the_checkpoint_names():
    torch = pytest.importorskip("torch")
    import export_motionagformer as E

    m = E.build("xs").eval()
    keys = set(m.state_dict())
    assert {"pos_embed", "joints_embed.weight", "layers.0.att_spatial.mixer.qkv.weight",
            "layers.0.att_temporal.layer_scale_1", "layers.11.graph_temporal.mixer.batch_norm.running_var",
            "layers.0.graph_spatial.mixer.U.weight", "layers.0.fusion.weight", "rep_logit.fc.weight", "head.weight"} <= keys
    assert not any(k.endswith(".adj") for k in keys)                  # the graph is not in the published files
    assert sum(1 for k in keys if k.endswith("att_spatial.mixer.qkv.weight")) == 12
    with torch.no_grad():
        y = m(torch.randn(2, 27, 17, 3))
    assert y.shape == (2, 27, 17, 3) and torch.isfinite(y).all()


# ---------------------------------------------------------------- paso 2.5: CalTennis geometry

def _look_at(C, target):
    from tennisbio.candidates.caltennis import Camera

    C, target = np.asarray(C, float), np.asarray(target, float)
    f = (target - C) / np.linalg.norm(target - C)
    right = np.cross(f, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    down = np.cross(f, right)
    K = np.array([[1600, 0, 960], [0, 1600, 540], [0, 0, 1.0]])
    return Camera(K, np.stack([right, down, f], 1), C, (1920, 1080))


def _two_views():
    return _look_at([11, -3.4, 1.7], [0.6, 5.7, 1.0]), _look_at([10.9, 14.0, 1.7], [0.6, 5.7, 1.0])


def test_caltennis_camera_files_and_names():
    from tennisbio.candidates.caltennis import Camera, start_time

    rt = [[0.66, 0.0065, -0.75, 11.07], [0.75, -0.0014, 0.66, -3.44], [0.0033, -1.0, -0.0059, 1.68]]
    good = {"K": np.eye(3).tolist(), "Rt_c2w": rt, "camera_model": "pinhole", "dist_coeffs": None,
            "reprojection_error": 2.3, "image_shape": {"height": 1080, "width": 1920}}
    cam = Camera.from_json(good)
    assert np.allclose(cam.C, [11.07, -3.44, 1.68]) and cam.size == (1920, 1080)
    assert Camera.from_json({**good, "camera_model": "fisheye", "dist_coeffs": [0.1, 0, 0, 0]}) is None
    assert Camera.from_json({**good, "reprojection_error": 110.0}) is None
    a = start_time("01_23_2026_16_59_47_000_2_E_01_18_20_30_998")
    b = start_time("01_23_2026_17_00_17_000_2_W_02_18_10_24_610")
    assert b - a == pytest.approx(30.0)
    assert start_time("09_18_2025_16_15_court5_overhead") is None


def test_caltennis_triangulation_and_view_pair():
    from tennisbio.candidates.caltennis import reproj_error, triangulate, trunk_yaw_from_world, view_pair

    a, b = _two_views()
    ang, tgt = view_pair(a, b)
    assert 70 < ang < 90 and np.allclose(tgt, [0.6, 5.7], atol=0.3)
    assert view_pair(a, a) is None                                    # same direction: nothing to triangulate
    X = np.array([[0.4, 5.6, 1.4], [0.8, 5.8, 1.45], [0.5, 5.6, 0.95], [0.75, 5.8, 0.95]])   # ls, rs, lh, rh
    Y = triangulate(a.P, b.P, a.project(X), b.project(X))
    assert np.allclose(Y, X, atol=1e-6) and reproj_error(a, b, a.project(X), b.project(X), Y).max() < 1e-6
    assert np.allclose(trunk_yaw_from_world(X), np.degrees(np.arctan2([0.2, 0.2], [0.4, 0.25])))
    assert np.isnan(triangulate(a.P, b.P, np.full((1, 2), np.nan), np.zeros((1, 2)))).all()


def test_caltennis_sync_offset_is_found():
    from tennisbio.candidates.caltennis import best_offset

    a, b = _two_views()
    pts = np.random.default_rng(1).normal([0.6, 5.7, 1.0], 0.3, (17, 3))

    def body(t):                                                     # a person moving sideways and turning
        c, s = np.cos(2.0 * t), np.sin(2.0 * t)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        return (pts - pts.mean(0)) @ R.T + pts.mean(0) + [1.5 * t, 0, 0]
    ta = np.arange(120) / 60.0
    true = 0.35                                                      # b's clock + 0.35 s = a's clock
    tb = np.arange(160) / 60.0 - 0.2
    ka = np.stack([a.project(body(t)) for t in ta])
    kb = np.stack([b.project(body(t + true)) for t in tb])
    off, err = best_offset(a, b, ta, ka, np.ones((len(ta), 17)), tb, kb, np.ones((len(tb), 17)),
                           np.arange(-1.0, 1.0, 1 / 120))
    assert abs(off - true) <= 1 / 120 and err < 1.0


def test_caltennis_tracking_pairing_and_errors():
    from tennisbio.candidates.caltennis import angle_errors, interp, match_people, track, wrap

    boxes = [np.array([[0, 0, 10, 20], [100, 0, 110, 20]]), np.array([[101, 1, 111, 21], [1, 0, 11, 20]]),
             np.array([[2, 1, 12, 21]]), np.zeros((0, 4)), np.array([[3, 1, 13, 21]])]
    assert track(boxes, 0, 0) == [0, 1, 0, None, None]               # lost at the empty frame: stops there
    assert track(boxes, 1, 0) == [1, 0, None, None, None]
    a, b = _two_views()
    p1 = np.random.default_rng(2).normal([0.6, 5.7, 1.0], 0.3, (17, 3))
    p2 = p1 + [3.0, -2.0, 0]
    ka, kb = np.stack([a.project(p1), a.project(p2)]), np.stack([b.project(p2), b.project(p1)])
    i, j, e = match_people(a, b, ka, np.ones((2, 17)), kb, np.ones((2, 17)))
    assert (i, j) == (0, 1) and e < 1e-3
    assert np.allclose(wrap([190, -190, 360]), [-170, 170, 0])
    e = angle_errors(np.array([[10, 0], [179, 5], [np.nan, 0]]), np.array([[0, 0], [-179, 0], [0, 0]]))
    assert e["frames"] == 2 and e["median_err_deg"] == pytest.approx(3.5) and e["within_15deg"] == 1.0
    v = interp(np.array([0.0, 1.0]), np.array([[0.0], [10.0]]), np.array([0.25, 2.0]))
    assert v[0, 0] == pytest.approx(2.5) and np.isnan(v[1, 0])


def test_new_exports_run_with_their_packages(monkeypatch, tmp_path):
    import bench_candidates as B

    seen = []

    def run(cmd, **kw):
        assert kw.get("timeout")
        seen.append(cmd)
        Path(cmd[cmd.index("--out") + 1]).write_bytes(b"x")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(B.subprocess, "run", run)
    monkeypatch.setitem(B.EXPORTS, "bounce", (tmp_path / "b.onnx", ["export_bounce_ctb.py"], ("catboost==1.2.10",)))
    monkeypatch.setitem(B.EXPORTS, "mag3d-s", (tmp_path / "s.onnx", ["export_motionagformer.py", "--size", "s"], ()))
    B.ensure_model("bounce")
    B.ensure_model("mag3d-s")
    assert seen[0][1:4] == ["run", "--with", "catboost==1.2.10"] and seen[0][-2:] == ["--out", str(tmp_path / "b.onnx")]
    assert seen[1][0] == sys.executable and seen[1][2:4] == ["--size", "s"]
    assert {"ocr5", "mag3d", "bounce"} <= set(B.CANDIDATES) and all(c in B.EXPORTS for c in B.CANDIDATES)


def test_pose_track_keeps_frames_with_nobody(tmp_path, monkeypatch):
    """Request 82: a CalTennis frame with no person raised reshape(0, -1); it is now an empty frame."""
    import cv2
    import bench_candidates as B

    vid = tmp_path / "v.avi"
    w = cv2.VideoWriter(str(vid), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for _ in range(3):
        w.write(np.zeros((48, 64, 3), np.uint8))
    w.release()
    calls = iter([([], [], [], None, None), ([[1, 2, 30, 40, 0.9]], np.zeros((1, 17, 2)), np.ones((1, 17)), None, None),
                  ([], [], [], None, None)])
    p = B.pose_track(vid, lambda fr: next(calls))
    assert [len(b) for b in p["boxes"]] == [0, 1, 0] and p["kps"][0].shape == (0, 17, 2)


def test_http_file_asks_again_for_a_short_block(monkeypatch):
    """Request 82: a block that came back short gave a truncated zip; it is asked for again."""
    import io as _io
    import bench_candidates as B

    data = bytes(range(256)) * 16
    served = {"n": 0}

    class R(_io.BytesIO):
        headers = {"Content-Range": f"bytes 0-0/{len(data)}"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        a, b = map(int, req.headers["Range"].split("=")[1].split("-"))
        served["n"] += 1
        chunk = data[a:b + 1]
        return R(chunk[: len(chunk) // 2] if served["n"] == 2 else chunk)   # the first real block comes short once

    monkeypatch.setattr(B.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    f = B.HttpFile("http://x", block=1024)
    assert f.read() == data
