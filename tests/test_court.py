import json
from itertools import combinations

import cv2
import numpy as np

from tennisbio import court as C
from tennisbio.court import LINES, camera_pitch_deg, fit_court


def broadcast_H(pitch=20.0, f=1400.0, w=1920, h=1080, cam=(0.0, -12.0, 7.5)):
    """Ground (x, y) → image homography of a pinhole camera behind the near baseline."""
    t = np.radians(pitch)
    right, fwd = np.array([1.0, 0, 0]), np.array([0, np.cos(t), -np.sin(t)])
    up = np.cross(right, fwd)
    R = np.stack([right, -up, fwd])
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]])
    C = np.array(cam)
    return K @ np.c_[R[:, 0], R[:, 1], -R @ C]


def render(H, w=1920, h=1080, seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), (60, 110, 50), np.uint8)
    court = np.array([[-6.5, -3], [6.5, -3], [6.5, 27], [-6.5, 27]], float)
    pc = (np.c_[court, np.ones(4)] @ H.T)
    cv2.fillPoly(img, [(pc[:, :2] / pc[:, 2:]).astype(np.int32)], (150, 95, 45))
    for p, q in LINES.values():
        a, b = (H @ [*p, 1]), (H @ [*q, 1])
        cv2.line(img, tuple((a[:2] / a[2]).astype(int)), tuple((b[:2] / b[2]).astype(int)), (245, 245, 245), 4)
    cv2.rectangle(img, (900, 700), (1000, 1000), (40, 40, 200), -1)          # a player occluding lines
    noise = rng.normal(0, 6, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def test_fit_recovers_court_and_pitch():
    H = broadcast_H(20.0)
    fit = fit_court(render(H))
    assert fit is not None and fit.score > 0.6
    corners = np.array([[-5.485, 0], [5.485, 0], [-5.485, 23.77], [5.485, 23.77]])
    true = np.c_[corners, np.ones(4)] @ H.T
    true = true[:, :2] / true[:, 2:]
    assert np.abs(fit.to_image(corners) - true).max() < 6        # pixels
    assert abs(camera_pitch_deg(fit, (1080, 1920)) - 20.0) < 2.5


# --- fast paths (batched search, known courts) give the same result as the former search ------

def _reference_score(H, dil):
    """The former score_homography: the density averaged over the box pixels."""
    h, w = dil.shape
    img = C.MODEL_PTS @ H.T
    if np.any(img[:, 2] <= 0):
        return 0.0
    img = img[:, :2] / img[:, 2:]
    inside = (img[:, 0] >= 0) & (img[:, 0] < w) & (img[:, 1] >= 0) & (img[:, 1] < h)
    xy = img[inside].astype(int)
    hits = int(dil[xy[:, 1], xy[:, 0]].sum()) / len(C.MODEL_PTS)
    if len(xy) < 3:
        return hits
    x0, y0 = xy.min(0)
    x1, y1 = xy.max(0) + 1
    return hits - float(dil[y0:y1, x0:x1].mean())


def _reference_merge(segs):
    groups = []
    for s in segs:
        x0, y0, x1, y1 = s
        a, b = y1 - y0, x0 - x1
        n = np.hypot(a, b)
        L = np.array([a / n, b / n, -(a * x0 + b * y0) / n])
        if L[1] < 0 or (abs(L[1]) < 1e-9 and L[0] < 0):
            L = -L
        length = np.hypot(s[2] - s[0], s[3] - s[1])
        for g in groups:
            if abs(np.arctan2(L[1], L[0]) - np.arctan2(g["L"][1], g["L"][0])) < np.radians(2) and abs(L[2] - g["L"][2]) < 8:
                g["len"] += length
                break
        else:
            groups.append({"L": L, "len": length})
    groups.sort(key=lambda g: -g["len"])
    return [g["L"] for g in groups]


def _reference_fit_with(mask, max_lines=6):
    """The former nested-loop search (one getPerspectiveTransform, plausible and score per try)."""
    dil = C.dilate_lines(mask)
    h, w = mask.shape
    segs = cv2.HoughLinesP(mask * 255, 1, np.pi / 360, threshold=60, minLineLength=w // 12, maxLineGap=10)
    if segs is None:
        return None
    segs = segs.reshape(-1, 4).astype(float)
    ang = np.degrees(np.arctan2(segs[:, 3] - segs[:, 1], segs[:, 2] - segs[:, 0])) % 180
    horiz = _reference_merge(segs[(ang < 4) | (ang > 176)])[:max_lines]
    sides = _reference_merge(segs[(ang > 6) & (ang < 174)])[:max_lines]
    best = None
    for h2 in combinations(horiz, 2):
        h2 = sorted(h2, key=lambda L: -(-L[2] / L[1]))
        for s2 in combinations(sides, 2):
            pts = [C._intersect(hl, sl) for hl in h2 for sl in s2]
            if any(p is None for p in pts):
                continue
            pts = np.array(pts)
            if pts[0, 0] > pts[1, 0]:
                pts = pts[[1, 0, 3, 2]]
            for (_, yn), (_, yf) in combinations(sorted(C.HORIZONTAL.items(), key=lambda kv: kv[1]), 2):
                for (_, xl), (_, xr) in combinations(sorted(C.SIDELINES.items(), key=lambda kv: kv[1]), 2):
                    court = np.array([[xl, yn], [xr, yn], [xl, yf], [xr, yf]], np.float32)
                    H = cv2.getPerspectiveTransform(court, pts.astype(np.float32))
                    if not C.plausible(H, (h, w)):
                        continue
                    sc = _reference_score(H, dil)
                    if best is None or sc > best.score:
                        best = C.CourtFit(H, sc)
    return best


def _reference_fit_court(frame, good=0.8, min_score=0.5):
    best = None
    for params in C.LINE_PARAMS:
        fit = _reference_fit_with(C.white_lines(frame, *params))
        if fit is not None and (best is None or fit.score > best.score):
            best = fit
        if best is not None and best.score >= good:
            break
    return best if best is not None and best.score >= min_score else None


def _corner_err(H1, H2):
    pts = np.array([[-5.485, 0], [5.485, 0], [-5.485, 23.77], [5.485, 23.77], [0, 11.885]])
    return np.abs(C.CourtFit(H1, 0).to_image(pts) - C.CourtFit(H2, 0).to_image(pts)).max()


PRESETS = {"p20": dict(pitch=20.0), "p15": dict(pitch=15.0, f=1600.0), "p25": dict(pitch=25.0, cam=(1.0, -13.0, 9.0))}


def _clutter(seed=5):
    """No court: noisy texture crossed by white strokes (crowd, logos)."""
    rng = np.random.default_rng(seed)
    img = cv2.GaussianBlur(rng.integers(0, 255, (1080, 1920, 3), np.uint8), (5, 5), 0)
    for _ in range(25):
        x, y = int(rng.integers(0, 1800)), int(rng.integers(0, 1000))
        cv2.line(img, (x, y), (x + int(rng.integers(100, 600)), y + int(rng.integers(-40, 40))), (250, 250, 250), 3)
        cv2.line(img, (x, y), (x + int(rng.integers(-100, 100)), y + int(rng.integers(100, 500))), (250, 250, 250), 3)
    return img


def test_batched_search_equals_former_search():
    for i, kw in enumerate(PRESETS.values()):
        frame = render(broadcast_H(**kw), seed=i)
        ref, fast = _reference_fit_court(frame), fit_court(frame)
        assert ref is not None and fast is not None
        assert abs(ref.score - fast.score) < 1e-9
        assert _corner_err(ref.H, fast.H) < 0.01                   # pixels
    assert _reference_fit_court(_clutter()) is None and fit_court(_clutter()) is None


def test_merge_equals_former_grouping():
    rng = np.random.default_rng(1)
    base = rng.uniform(0, 1900, (300, 4))
    segs = np.r_[base, base + rng.normal(0, 1.5, base.shape)]       # near-duplicates to be merged
    ref, fast = _reference_merge(segs), C._merge(segs, "s")
    assert len(ref) == len(fast) and all(np.allclose(a, b) for a, b in zip(ref, fast))


def test_score_many_equals_pixel_average():
    _, dil, integ = C.LineMasks(render(broadcast_H(20.0)))[0]
    Hs = [broadcast_H(p, f=f, cam=(x, -12.0, 7.5)) for p in (12, 20, 30) for f in (1200, 1400, 2000) for x in (-2, 0, 3)]
    Hs.append(np.diag([1.0, -1.0, 1.0]) @ broadcast_H(20.0))         # mostly outside the image
    Hs.append(np.diag([1.0, 1.0, -1.0]) @ broadcast_H(20.0))         # behind the camera
    fast = C.score_many(np.array(Hs), dil, integ)
    assert np.allclose(fast, [_reference_score(H, dil) for H in Hs], atol=1e-12)


def test_known_court_reused_when_the_camera_preset_repeats():
    fits = {k: fit_court(render(broadcast_H(**kw), seed=i)) for i, (k, kw) in enumerate(PRESETS.items())}
    known = [fits["p15"], fits["p20"]]
    for seed in (11, 12):                                         # the same preset later in the match
        frame = render(broadcast_H(20.0), seed=seed)
        hit, full = C.match_known(frame, known), fit_court(frame)
        assert hit is not None and full is not None
        assert np.array_equal(hit.H, fits["p20"].H)                 # the right preset is picked
        assert _corner_err(hit.H, full.H) < 2.0                     # same court as a fresh search (px)
    # another preset or no court: nothing known fits → the full search runs
    assert C.match_known(render(broadcast_H(**PRESETS["p25"]), seed=3), known) is None
    assert C.match_known(_clutter(), known) is None
    assert C.match_known(render(broadcast_H(20.0)), []) is None


def test_court_stage_reuses_presets(tmp_path, monkeypatch):
    """The court stage on a synthetic broadcast (two camera presets, a shot without court): every
    stretch gets the court a full search finds there, and the search runs only when needed."""
    from tennisbio import stages
    from tennisbio.catalog import Match, Player
    from tennisbio.pipeline import Context

    fps = 25
    plan = ["p20", "p20", "p15", None, "p20", "p15", "p15", "p20"]   # one 8-s shot each
    shots = [{"start": i * 8 * fps, "end": (i + 1) * 8 * fps, "main_camera": True} for i in range(len(plan))]
    frames = {}

    def grab(video, t):
        i = int(t // 8)
        if i not in frames:
            frames[i] = _clutter(i) if plan[i] is None else render(broadcast_H(**PRESETS[plan[i]]), seed=100 + i)
        return frames[i]

    calls = {"search": 0}
    real_fit = C.fit_court

    def counting_fit(*a, **k):
        calls["search"] += 1
        return real_fit(*a, **k)

    monkeypatch.setattr(stages, "grab_frame", grab)
    monkeypatch.setattr(C, "fit_court", counting_fit)
    out = tmp_path / "out"
    out.mkdir()
    (out / "scenes.json").write_text(json.dumps({"fps": fps, "shots": shots}))
    ctx = Context(Match("m1", tmp_path / "v.mp4", Player("p", "P")), {}, out, log=lambda *_: None)
    ctx._prog["stage"] = "court"                    # as pipeline.run sets it
    res = stages.st_court(ctx)
    segs = json.loads((out / "court.json").read_text())["shots"]
    assert segs[0]["start"] == 0 and segs[-1]["end"] == len(plan) * 8 * fps
    for s in segs:
        for i in range(s["start"] // (8 * fps), s["end"] // (8 * fps)):
            if plan[i] is None:
                assert s["H"] is None
            else:
                assert s["H"] is not None and _corner_err(np.array(s["H"]), real_fit(grab(None, i * 8 + 4)).H) < 2.0
    # the 6 longest shots are fitted first; afterwards only the shot without court is searched
    assert calls["search"] == 6 + 1
    assert res["known_court_reused"] == 7 and res["with_court"] >= 4
