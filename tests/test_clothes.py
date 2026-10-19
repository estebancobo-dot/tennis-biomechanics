"""Clothes as an identity cue (tennisbio.clothes): two outfits told apart under lighting changes on a
court-coloured background, outlier runs, the near/far cannot-link pairs, and the fusion with the
end-change chain (a misread game on the scoreboard corrected by the clothes)."""
from types import SimpleNamespace

import cv2
import numpy as np

from tennisbio.clothes import (aggregate, clothes_distances, clothing_feature, court_colours, fuse, hist_distances,
                               identity_from_cues, split_two)
from tennisbio.identity import decide_by_ends, end_changes
from tennisbio.pose.yolo import appearance

BLUE, GREEN, WHITE = (150, 95, 60), (70, 120, 60), (235, 235, 235)        # BGR: hard court, outer court, lines
SKIN = (120, 150, 200)
# outfits: (shirt, shorts/skirt) BGR; B wears navy shorts, close to the blue court
OUTFITS = {"A": ((40, 200, 230), (30, 30, 30)), "B": ((240, 240, 240), (110, 50, 20))}


def person(outfit, light=1.0, x=300, y=80, h=240, rng=None, frame=None, court=BLUE):
    """A frame with a court-coloured background and one player: shirt (shoulders–hips), shorts (hips–
    mid-thigh), skin arms and legs, a dark head. Returns (frame, box, keypoints (17, 2), conf (17,))."""
    rng = rng or np.random.default_rng(0)
    img = np.zeros((480, 720, 3), np.uint8) if frame is None else frame
    if frame is None:
        img[:] = GREEN
        img[60:, 80:640] = court
        img[330:336, :] = WHITE                                      # a baseline under her feet
    w = 0.38 * h
    kp = np.zeros((17, 2))
    cx = x + w / 2
    kp[0] = [cx, y + 0.08 * h]
    kp[5], kp[6] = [cx - 0.22 * w * 1.6, y + 0.2 * h], [cx + 0.22 * w * 1.6, y + 0.2 * h]
    kp[11], kp[12] = [cx - 0.2 * w, y + 0.52 * h], [cx + 0.2 * w, y + 0.52 * h]
    kp[13], kp[14] = [cx - 0.22 * w, y + 0.74 * h], [cx + 0.22 * w, y + 0.74 * h]
    kp[15], kp[16] = [cx - 0.24 * w, y + 0.97 * h], [cx + 0.24 * w, y + 0.97 * h]
    kp[7], kp[8] = kp[5] + [-0.12 * w, 0.15 * h], kp[6] + [0.12 * w, 0.15 * h]
    kp[9], kp[10] = kp[7] + [0.0, 0.14 * h], kp[8] + [0.0, 0.14 * h]
    shirt, shorts = OUTFITS[outfit]
    for a, b in ((11, 13), (12, 14), (13, 15), (14, 16), (5, 7), (7, 9), (6, 8), (8, 10)):
        cv2.line(img, tuple(map(int, kp[a])), tuple(map(int, kp[b])), SKIN, max(3, int(0.06 * h)))
    cv2.fillPoly(img, [np.round(kp[[5, 6, 12, 11]]).astype(np.int32)], shirt)
    mid = kp[[11, 12]] + 0.5 * (kp[[13, 14]] - kp[[11, 12]])
    cv2.fillPoly(img, [np.round(np.array([kp[11], kp[12], mid[1], mid[0]])).astype(np.int32)], shorts)
    cv2.circle(img, tuple(map(int, kp[0])), int(0.07 * h), (40, 50, 70), -1)
    out = np.clip(img.astype(np.float32) * light + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    box = np.array([x - 0.2 * w, y, x + 1.2 * w, y + h], np.float32)
    return out, box, kp.astype(np.float32), np.ones(17, np.float32)


def run_code(outfit, light, rng, frames=4, court=BLUE):
    codes = []
    for k in range(frames):
        f, b, kp, cf = person(outfit, light * rng.uniform(0.92, 1.08), x=int(rng.uniform(150, 450)),
                              h=int(rng.uniform(200, 260)), rng=rng, court=court)
        codes.append(clothing_feature(f, kp, cf, b))
    return aggregate(codes)


def test_court_colours_are_the_ground_around_her_not_the_lines():
    f, b, _, _ = person("A")
    cc = court_colours(f, b)
    blue = cv2.cvtColor(np.uint8([[BLUE]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    assert len(cc) >= 1 and np.linalg.norm(cc[0] - blue) < 8
    white = cv2.cvtColor(np.uint8([[WHITE]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    assert all(np.linalg.norm(c - white) > 30 for c in cc)


def test_same_outfit_under_other_light_is_closer_than_the_other_outfit():
    rng = np.random.default_rng(1)
    a_sun, a_shade = run_code("A", 1.25, rng), run_code("A", 0.6, rng)
    b_sun, b_shade = run_code("B", 1.25, rng), run_code("B", 0.6, rng)
    D = clothes_distances(np.array([a_sun, a_shade, b_sun, b_shade]))
    within = max(D[0, 1], D[2, 3])
    between = min(D[0, 2], D[0, 3], D[1, 2], D[1, 3])
    assert between > 3 * within, (within, between)


def test_clothes_code_beats_the_whole_box_histogram():
    """The whole box is mostly court: its histograms of the two players are close (the 19-10 problem);
    the clothing code tells them apart several times better."""
    rng = np.random.default_rng(2)
    boxes, codes = [], []
    for o in "AABB":
        f, b, kp, cf = person(o, rng.uniform(0.7, 1.2), rng=rng)
        boxes.append(appearance(f, b))
        codes.append(clothing_feature(f, kp, cf, b))
    Dh, Dc = hist_distances(np.array(boxes)), clothes_distances(np.array(codes))
    ratio = lambda D: min(D[0, 2], D[0, 3], D[1, 2], D[1, 3]) / max(D[0, 1], D[2, 3])
    assert ratio(Dc) > 2 * ratio(Dh)


def test_navy_shorts_on_a_blue_court_still_count():
    """Shorts close to the court colour: the code survives (it is not all thrown away as court)."""
    f, b, kp, cf = person("B")
    code = clothing_feature(f, kp, cf, b)
    assert np.isfinite(code).all()


def test_box_fallback_without_keypoints():
    f, b, kp, cf = person("A")
    code = clothing_feature(f, None, None, b)
    full = clothing_feature(f, kp, cf, b)
    assert np.isfinite(code[:15]).all()
    assert clothes_distances(code[None], full[None])[0, 0] < 0.35


def _match(rng, n_per=24, outliers=2):
    codes, truth = [], []
    for i in range(2 * n_per):
        o = "AB"[i % 2]
        codes.append(run_code(o, rng.uniform(0.6, 1.3), rng, frames=3))
        truth.append(o)
    for _ in range(outliers):                      # a ball kid / a replay frame: a run unlike both
        c = np.full(30, 1e-3, np.float32)
        c[rng.integers(0, 12)] = 1.0
        c[15 + rng.integers(0, 12)] = 1.0
        codes.append(aggregate([c]))
        truth.append("X")
    return np.array(codes), np.array(truth)


def test_split_two_is_robust_to_outlier_runs():
    rng = np.random.default_rng(3)
    codes, truth = _match(rng)
    sp = split_two(clothes_distances(codes))
    lab, m = sp["labels"], sp["margins"]
    a, b = lab[truth == "A"], lab[truth == "B"]
    assert len(set(a)) == 1 and len(set(b)) == 1 and a[0] != b[0]
    assert np.median(m[truth != "X"]) > 0.3 and sp["separation"] > 2
    assert (m[truth == "X"] < np.median(m[truth != "X"])).all()       # outliers get small margins


def test_cannot_link_pairs_are_checked():
    rng = np.random.default_rng(4)
    codes, truth = _match(rng, n_per=10, outliers=0)
    n = len(codes)
    # the far player seen in four runs: the other outfit
    far = [(i, run_code("B" if truth[i] == "A" else "A", 1.0, rng, frames=2)) for i in (0, 1, 2, 3)]
    X = np.vstack([codes, [c for _, c in far]])
    sp = split_two(clothes_distances(X), [(i, n + k) for k, (i, _) in enumerate(far)], n_core=n)
    assert sp["links_ok"] == 1.0 and sp["links"] == 4


def _games_sequence(runs_per_game=3, games=12):
    """Scoreboard games of a set read in each run (a pair per set), and who is near: the target is
    near at an even number of end changes."""
    out = []
    a = b = 0
    for g in range(games):
        for _ in range(runs_per_game):
            out.append([[a, b]])
        if g % 2 == 0:
            a += 1
        else:
            b += 1
    return out


def test_fusion_corrects_a_misread_game_and_fills_runs_without_scoreboard():
    rng = np.random.default_rng(5)
    games = _games_sequence()
    n = len(games)
    truth = [end_changes(g) % 2 == 0 for g in games]                        # target near at even counts
    codes = np.array([run_code("A" if t else "B", rng.uniform(0.6, 1.3), rng, frames=3) for t in truth])
    read = [None if g is None else [list(s) for s in g] for g in games]
    bad = 10                                                  # 2-1 misread as 1-1 (one change less)
    read[bad] = [list(s) for s in games[bad - 3]]
    read[20] = read[21] = None                                               # scoreboard not read here
    par = [None if g is None else end_changes(g) for g in read]
    votes = [(0, truth[0]), (14, truth[14])]                                 # two serves seen with the marker
    direct = [None] * n
    for i, v in votes:
        direct[i] = v
    base = decide_by_ends(par, votes)
    ends = [None if base is None or p is None else bool(base ^ bool(p % 2)) for p in par]
    assert ends[bad] is not None and ends[bad] != truth[bad]                 # the chain is wrong there
    per, s = identity_from_cues(codes, [], None, ends, direct, votes, [None if g is None else str(g) for g in read])
    got = [p["near_is_target"] for p in per]
    assert got == truth
    assert per[bad]["method"] == "ropa (corrige el marcador)"
    assert per[20]["method"] == "ropa" and per[21]["method"] == "ropa"
    assert s["clothes_won"] == 1 and s["clothes_only"] == 2 and s["agree"] == n - 3
    assert s["by_clothes"] == n and s["conflicts"] == 0 and s["decided"] == n
    assert s["clothes"]["same_game_same"] == 1.0 and s["confidence"] >= 0.95


def test_fusion_keeps_doubt_when_the_clothes_are_not_clear():
    labels = np.array([0, 1, 0, 1, 0, 1])
    ends = [True, False, True, False, True, True]          # the last run: the chain says target
    direct = [None] * 6
    # the last run's clothes say opponent, but with a small margin: neither wins
    per, s = fuse(labels, np.array([.5, .5, .5, .5, .5, .12]), ends, direct)
    assert per[5]["near_is_target"] is None and per[5]["method"] == "dudoso" and s["doubtful"] == 1
    # with her own serve seen in that run, the chain wins
    direct[5] = True
    per, s = fuse(labels, np.array([.5, .5, .5, .5, .5, .12]), ends, direct)
    assert per[5]["near_is_target"] is True and s["ends_won"] == 1
    # a clear margin on clothes wins over the chain
    per, s = fuse(labels, np.array([.5, .5, .5, .5, .5, .5]), ends, [None] * 6)
    assert per[5]["near_is_target"] is False and s["clothes_won"] == 1


def test_fusion_does_not_trust_a_split_that_is_not_the_two_people():
    """Clothes groups that do not follow the end changes (a split by light, say) name nobody."""
    labels = np.array([0, 0, 1, 1, 0, 0, 1, 1])
    ends = [True, False, True, False, True, False, True, False]
    per, s = fuse(labels, np.full(8, 0.5), ends, [None] * 8)
    assert s["target_cluster"] is None and s["clothes_only"] == 0
    assert [p["near_is_target"] for p in per] == ends and s["ends_only"] == 8


def test_fallback_to_whole_box_histograms_without_video():
    feats = np.array([np.eye(32)[3] * .7 + .01, np.eye(32)[1] * .7 + .01] * 4)
    ends = [True, False] * 4
    per, s = identity_from_cues(None, [], feats, ends, [None] * 8, [])
    assert s["clothes"]["source"].startswith("caja entera") and s["agree"] == 8


def test_no_runs():
    per, s = identity_from_cues(None, [], None, [], [], [])
    assert per == [] and s["decided"] == 0


def test_run_clothes_reads_the_frames_of_each_run(tmp_path):
    """The stage's reader: a short video of two runs (outfit A, then B), the players stage's data for
    it, and the codes come out in two clearly different groups."""
    from tennisbio.stages import run_clothes

    fps, T, gap = 10, 20, 5
    path = tmp_path / "v.mp4"
    rng = np.random.default_rng(6)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (720, 480))
    boxes, kps, confs = [], [], []
    for t in range(2 * T + gap):                    # run A, a cut (a close-up), run B
        if T <= t < T + gap:
            vw.write(np.full((480, 720, 3), 90, np.uint8))
            continue
        f, b, kp, cf = person("A" if t < T else "B", rng=rng, x=200 + 3 * (t % (T + gap)))
        vw.write(f)
        boxes.append(b[None]); kps.append(kp[None]); confs.append(cf[None])
    vw.release()

    def obj(xs):
        a = np.empty(len(xs), dtype=object)
        a[:] = xs
        return a

    d = {"fps": np.float64(fps), "frames": np.r_[np.arange(T), np.arange(T + gap, 2 * T + gap)],
         "boxes": obj(boxes), "kps": obj(kps), "confs": obj(confs)}
    runs = [np.arange(T), np.arange(T, 2 * T)]
    tracks = [(r, np.zeros(len(r), int), np.stack([kps[k][0] for k in r])) for r in runs]
    ctx = SimpleNamespace(video=path, cfg={}, log=lambda *a: None, progress=lambda *a, **k: None)
    codes, far = run_clothes(ctx, d, tracks, None)
    assert np.isfinite(codes).all() and far == []
    assert clothes_distances(codes)[0, 1] > 0.4
    ctx.video = tmp_path / "missing.mp4"
    assert run_clothes(ctx, d, tracks, None) == (None, [])


def test_identity_click_names_her_clothes():
    """19-10: one click per match. The run at the click is hers (near) or not; every run with clear clothes
    follows its group, whatever the end-change chain said; runs without clear clothes keep their answer."""
    from tennisbio.identity import apply_pick

    ident = {"fps": 10.0, "runs": [
        {"start": 0, "end": 100, "cluster": 0, "clothes_margin": 0.5, "near_is_target": None},
        {"start": 100, "end": 200, "cluster": 1, "clothes_margin": 0.4, "near_is_target": True},     # chain wrong
        {"start": 200, "end": 300, "cluster": 0, "clothes_margin": 0.02, "near_is_target": False},   # unclear: kept
        {"start": 300, "end": 400, "cluster": -1, "near_is_target": None}]}
    out, why = apply_pick(ident, {"t": 5.0, "near_is_her": True})
    assert [r["near_is_target"] for r in out["runs"]] == [True, False, False, None]
    assert why["pick"] == "aplicado" and why["by_click"] == 2 and ident["runs"][1]["near_is_target"] is True
    out, _ = apply_pick(ident, {"t": 15.0, "near_is_her": False})      # the opponent near at the click
    assert [r["near_is_target"] for r in out["runs"]][:2] == [True, False]
    out, why = apply_pick(ident, {"t": 35.0, "near_is_her": True})     # no clothes there: nothing changes
    assert why["pick"] == "sin grupo de ropa en ese momento" and out["runs"][1]["near_is_target"] is True
