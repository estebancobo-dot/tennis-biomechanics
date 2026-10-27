"""Replays and other cameras linked to the live stroke (#218, tennisbio.views and the stages views and
views_link), on synthetic scenes / court / players / score / audio data: one per case."""
import json

import numpy as np
import pytest

from tennisbio import pipeline, stages
from tennisbio import views as V
from tennisbio.catalog import Match, Player
from tennisbio.pipeline import Context
from tennisbio.replays import Run

FPS = 10.0
H = [[40.0, 0.0, 640.0], [0.0, -25.0, 700.0], [0.0, 0.0, 1.0]]      # court (m) → image (px), main camera


def lerp(t, t0, t1, a, b):
    """Position along a→b between t0 and t1, still before and after."""
    u = np.clip((t - t0) / (t1 - t0), 0, 1)
    return np.asarray(a, float) + u * (np.asarray(b, float) - np.asarray(a, float))


# point A: 4 m along the baseline in 2.4 s; B: 2 m forwards in 2 s; C: 4 m back along y = 2 in 2.4 s; D: still
A = lambda t: lerp(t, 2.0, 4.4, (0, 1), (4, 1))
B = lambda t: lerp(t, 12.5, 14.5, (-2, 1), (-2, 3))
C = lambda t: lerp(t, 30.0, 32.4, (4, 2.2), (0, 2.2))
D = lambda t: np.array([1.0, 0.5])
# (start s, end s, main camera, feet position at time t or None when she is not tracked, scoreboard read)
SHOTS = [
    (0, 8, True, A),                                                   # 0 live A
    (8, 12, True, lambda t: A(t - 8 + 2.0 - 1.0)),                     # 1 replay A, normal speed, silent
    (12, 20, True, B),                                                 # 2 live B
    (20, 25, True, lambda t: B(12.5 + (t - 20.5) / 2)),               # 3 replay B, 2× slower
    (25, 28, False, None),                                             # 4 side camera
    (28, 40, True, C),                                                 # 5 live C
    (40, 52, True, lambda t: C(30.0 + (t - 41.0) / 4)),               # 6 replay C, 4× slower
    (52, 55, False, None),                                             # 7 close-up
    (55, 70, True, D),                                                 # 8 live D (no replay)
    (70, 80, False, None),                                             # 9 crowd
]
STROKES = [3.0, 4.0, 13.5, 15.0, 31.0, 32.0, 60.0, 62.0]               # live strokes (candidates)
ONSETS = [3.0, 3.5, 4.0, 13.5, 14.2, 15.0, 26.0, 31.0, 31.6, 32.0, 60.0, 61.0, 62.0]
EVIDENCE = {4: {"sampled": 2, "lines_behind": 0, "long_lines": 4, "horiz_share": 0.8, "people_h": 0.3, "pitch_deg": None},
            7: {"sampled": 1, "lines_behind": 0, "long_lines": 0, "horiz_share": None, "people_h": 0.7, "pitch_deg": None},
            9: {"sampled": 3, "lines_behind": 0, "long_lines": 1, "horiz_share": 0.2, "people_h": 0.05, "pitch_deg": None}}


def person(u, v):
    """Box, 17 COCO keypoints and confidences of a standing person with her feet at image (u, v)."""
    y = {"nose": 160, "eye": 163, "ear": 160, "shoulder": 130, "elbow": 100, "wrist": 75, "hip": 80, "knee": 40, "ankle": 0}
    kp = []
    for name in ["nose", "eye", "eye", "ear", "ear", "shoulder", "shoulder", "elbow", "elbow", "wrist", "wrist",
                 "hip", "hip", "knee", "knee", "ankle", "ankle"]:
        kp.append((u, v - y[name]))
    kp = np.array(kp, float)
    kp[5::2, 0] -= 12                                    # left side to the left
    kp[6::2, 0] += 12
    return np.array([u - 25, v - 175, u + 25, v], float), kp, np.full(17, 0.9)


def write_match(out, shots=SHOTS, court=True, players=True, score=None, strokes=STROKES, onsets=ONSETS):
    out.mkdir(parents=True, exist_ok=True)
    sc = []
    for a, b, main, _ in shots:
        cf = 0.6 if main else (0.4 if (a, b) == (25, 28) else 0.05)
        sc.append({"start": int(a * FPS), "end": int(b * FPS), "main_camera": main, "court_fraction": cf,
                   "court_lines": 0.8 if main else 0.0, "main_view": 0.0})
    (out / "scenes.json").write_text(json.dumps({"fps": FPS, "shots": sc}))
    if court:
        segs = [{"start": int(a * FPS), "end": int(b * FPS), "score": 0.8, "H": H, "pitch_deg": 20.0}
                for a, b, main, _ in shots if main]
        (out / "court.json").write_text(json.dumps({"fps": FPS, "shots": segs}))
    if players:
        Hm = np.array(H)
        idx, boxes, kps, confs, feats = [], [], [], [], []
        for a, b, main, pos in shots:
            if not main or pos is None:
                continue
            for f in range(int(a * FPS) + 1, int(b * FPS)):      # the cut frame is missing: runs break at cuts
                x, y = pos(f / FPS)
                p = Hm @ [x, y, 1.0]
                bx, kp, cf = person(p[0] / p[2], p[1] / p[2])
                idx.append(f)
                boxes.append(bx[None].astype(np.float32))
                kps.append(kp[None].astype(np.float32))
                confs.append(cf[None].astype(np.float32))
                feats.append(np.full((1, 32), 1 / 32, np.float32))
        obj = lambda xs: np.array(xs + [None], dtype=object)[:-1]
        np.savez(out / "players.npz", fps=FPS, frames=np.array(idx), height=720, boxes=obj(boxes), kps=obj(kps),
                 confs=obj(confs), feats=obj(feats))
    (out / "score.json").write_text(json.dumps(score or {"readings": [], "shots": []}))
    (out / "audio_onsets.json").write_text(json.dumps({"t": list(onsets), "strength": [1.0] * len(onsets)}))
    cands = [{"t": t, "audio": True, "wrist_peak_t": t, "side": "near", "identity": True, "target": True} for t in strokes]
    (out / "candidates.json").write_text(json.dumps(cands))
    return cands


def ctx_for(out, cfg=None):
    c = Context(Match("m1", out / "v.mp4", Player("p", "P")), cfg or {"cheap_pass": {"fps": FPS}}, out, log=lambda *_: None)
    c._prog["stage"] = "views"
    return c


@pytest.fixture
def evidence(monkeypatch):
    asked = []

    def fake(ctx, scenes, shots, main_pitch):
        asked.append(list(shots))
        return {i: EVIDENCE[i] for i in shots if i in EVIDENCE}
    monkeypatch.setattr(stages, "_sample_views", fake)
    return asked


def views_by_shot(out):
    doc = json.loads((out / "views.json").read_text())
    return doc, {v["shot"]: v for v in doc["views"]}


def test_every_case_classified_and_linked(tmp_path, evidence):
    out = tmp_path / "m1"
    write_match(out)
    stages.st_views(ctx_for(out))
    doc, by = views_by_shot(out)
    assert evidence == [[4, 7, 9]]                     # only non-live shots are sampled (not the replays found)
    # normal-speed replay of A, by her path: factor 1, both strokes of A
    r1 = by[1]
    assert r1["kind"] == "repeticion_principal" and "recorrido" in r1["rule"]
    assert [ln["live_t"] for ln in r1["links"]] == [3.0, 4.0]
    assert all(ln["method"] == "recorrido" and ln["speed"] == "normal" for ln in r1["links"])
    assert r1["links"][0]["slowmo"] == pytest.approx(1.0, abs=0.15)
    # slow motion ×2 and ×4
    for shot, factor in ((3, 2.0), (6, 4.0)):
        v = by[shot]
        assert v["kind"] == "repeticion_principal" and v["links"], shot
        assert v["links"][0]["slowmo"] == pytest.approx(factor, rel=0.15), (shot, v["links"][0])
        assert v["links"][0]["speed"] == "lenta" and v["links"][0]["confidence"] >= 0.7
    assert [ln["live_t"] for ln in by[3]["links"]] == [13.5]          # B's moving stretch holds 13.5 only
    t_imp = by[3]["links"][0]["impact_t_in_replay"]                   # 13.5 live → 20.5 + 1.0 × 2 in the replay
    assert t_imp == pytest.approx(22.5, abs=0.3)
    # side camera: 1 impact heard → the last stroke of B, by order
    assert by[4]["kind"] == "lateral"
    assert [(ln["live_t"], ln["method"]) for ln in by[4]["links"]] == [(15.0, "orden")]
    # close-up: last stroke of C, low confidence; crowd: never linked
    assert by[7]["kind"] == "primer_plano" and [ln["live_t"] for ln in by[7]["links"]] == [32.0]
    assert by[7]["links"][0]["confidence"] <= 0.3
    assert by[9]["kind"] == "otra" and by[9]["links"] == []
    # D: no replay, no view linked to its strokes
    assert not any(ln["live_t"] in (60.0, 62.0) for ln in doc["links"])
    assert doc["summary"]["repeticion_principal"] == 3 and doc["summary"]["lateral"] == 1
    assert doc["main_pitch_deg"] == 20.0


def test_views_link_adds_only_views_to_strokes(tmp_path, evidence):
    out = tmp_path / "m1"
    write_match(out)
    stages.st_views(ctx_for(out))
    strokes = [{"match_time_s": t + 0.04, "side": "near", "stroke": "forehand", "metrics": {"x": k}, "views": "old"}
               for k, t in enumerate(STROKES)]
    before = json.loads(json.dumps(strokes))
    (out / "strokes.json").write_text(json.dumps(strokes))
    cov = stages.st_views_link(ctx_for(out))
    after = json.loads((out / "strokes.json").read_text())
    for a, b in zip(before, after):                     # every field as it was; only views / slowmo_view
        assert {k: v for k, v in a.items() if k != "views"} == {k: v for k, v in b.items() if k not in ("views", "slowmo_view")}
    by_t = {round(s["match_time_s"] - 0.04, 2): s for s in after}
    assert [v["kind"] for v in by_t[3.0]["views"]] == ["repeticion_principal"] and "slowmo_view" not in by_t[3.0]
    assert by_t[13.5]["slowmo_view"] is True
    assert {v["kind"] for v in by_t[15.0]["views"]} == {"lateral"}
    assert by_t[32.0]["slowmo_view"] is True and {v["kind"] for v in by_t[32.0]["views"]} == {"repeticion_principal", "primer_plano"}
    assert "views" not in by_t[60.0] and "views" not in by_t[62.0]
    assert cov["strokes"] == 8 and cov["with_replay"] == 5 and cov["with_other_camera"] == 2
    assert (out / "views_link.json").exists()


def test_replay_without_scoreboard_is_linked_by_order(tmp_path, evidence):
    """A main-camera replay where she is not tracked: the scoreboard is missing → repeticion_principal,
    linked to the point before it by order."""
    shots = [(0, 8, True, A), (8, 12, True, None), (12, 20, True, B)]
    reads = [{"start": 0.0, "end": 8.0, "tried": 6, "read": 6}, {"start": 8.0, "end": 12.0, "tried": 2, "read": 0},
             {"start": 12.0, "end": 20.0, "tried": 6, "read": 6}]
    out = tmp_path / "m1"
    write_match(out, shots=shots, score={"readings": [], "shots": reads}, strokes=[3.0, 4.0, 15.0], onsets=[3.0, 4.0, 9.0, 15.0])
    stages.st_views(ctx_for(out))
    _, by = views_by_shot(out)
    v = by[1]
    assert v["kind"] == "repeticion_principal" and v["source"] == "marcador" and v["rule"] == "sin_marcador"
    assert [(ln["live_t"], ln["method"]) for ln in v["links"]] == [(4.0, "orden")]


def test_missing_court_and_no_players(tmp_path, evidence):
    """No court anywhere: nothing is live play, every shot is classified by its look, nothing breaks.
    No players: no replay by path, the other cameras are still classified and linked by order."""
    out = tmp_path / "nocourt"
    write_match(out, court=False)
    s = stages.st_views(ctx_for(out))
    doc, by = views_by_shot(out)
    assert s["views"] == len(SHOTS) and by[4]["kind"] == "lateral" and by[9]["kind"] == "otra"
    assert not any(ln["method"] == "recorrido" for ln in doc["links"])

    out = tmp_path / "noplayers"
    write_match(out, players=False)
    stages.st_views(ctx_for(out))
    doc, by = views_by_shot(out)
    assert 1 not in by and by[4]["kind"] == "lateral"           # the replays of the main camera are not found
    assert [ln["live_t"] for ln in by[4]["links"]] == [15.0]
    assert doc["summary"]["repeticion_principal"] == 0


def test_views_link_without_views_or_strokes(tmp_path):
    out = tmp_path / "m1"
    out.mkdir()
    assert stages.st_views_link(ctx_for(out))["strokes"] == 0          # no strokes.json: nothing written
    assert not (out / "strokes.json").exists()
    (out / "strokes.json").write_text(json.dumps([{"match_time_s": 1.0, "side": "near"}]))
    stages.st_views_link(ctx_for(out))                                  # no views.json: strokes unchanged
    assert json.loads((out / "strokes.json").read_text()) == [{"match_time_s": 1.0, "side": "near"}]


def test_existing_outputs_and_stages_unchanged(tmp_path, evidence):
    """The new stages hang off the old ones: candidates and the fine passes keep their dependencies and
    versions (no re-run of anything already computed) and candidates.json is not touched."""
    from tennisbio.stage_code import check

    for n in ("candidates", "fine", "fine_opponent", "fine_doubtful"):
        assert "views" not in pipeline.STAGES[n].deps and "views_link" not in pipeline.STAGES[n].deps
    assert pipeline.STAGES["candidates"].version == "9" and pipeline.STAGES["fine"].version == "16"
    assert set(pipeline.STAGES["views"].deps) == {"scenes", "court", "players", "score", "audio", "candidates"}
    assert set(pipeline.STAGES["views_link"].deps) == {"views", "fine"}
    assert pipeline.STAGES["views"].resource is None
    assert not check()
    out = tmp_path / "m1"
    write_match(out)
    before = (out / "candidates.json").read_bytes()
    stages.st_views(ctx_for(out))
    assert (out / "candidates.json").read_bytes() == before


# --- the rules alone ---------------------------------------------------------------------------------
def test_classify_rules():
    assert V.classify({"replay": ["sin_marcador"]}, 20)[0] == "repeticion_principal"
    assert V.classify({"people_h": 0.6, "court_fraction": 0.5}, 20)[0] == "primer_plano"
    assert V.classify({"lines_behind": 2, "pitch_deg": 8.0, "court_fraction": 0.5}, 20)[0] == "frontal"
    k, conf, _ = V.classify({"lines_behind": 2, "pitch_deg": 19.0, "court_fraction": 0.5}, 20)
    assert k == "repeticion_principal" and conf == 0.5
    assert V.classify({"lines_behind": 1, "court_fraction": 0.5}, None)[1] == 0.4          # frontal, unsure
    assert V.classify({"court_fraction": 0.4, "horiz_share": 0.7, "long_lines": 3}, 20)[0] == "lateral"
    assert V.classify({"court_fraction": 0.05, "horiz_share": 0.9, "long_lines": 3}, 20)[0] == "otra"
    assert V.classify({"sampled": 0}, None)[0] == "otra"


def run_along(t0, xs, ys, speed=1.0, impacts=2):
    n = int(len(xs) / speed)
    s = np.linspace(0, len(xs) - 1, n)
    p = np.stack([np.interp(s, np.arange(len(xs)), xs), np.interp(s, np.arange(len(ys)), ys)], 1)
    return Run(t0, t0 + n / 25.0, p, 25.0, impacts)


@pytest.mark.parametrize("speed,factor", [(1.0, 1.0), (0.5, 2.0), (0.25, 4.0)])
def test_slowmo_factor(speed, factor):
    live = run_along(0, np.linspace(0, 4, 60), np.full(60, 1.0))
    f = V.slowmo_factor(run_along(10, np.linspace(0, 4, 60), np.full(60, 1.0), speed=speed, impacts=0), live)
    assert f["factor"] == pytest.approx(factor, rel=0.1) and f["agree"]
    assert V.speed_label(f["factor"]) == ("normal" if factor == 1.0 else "lenta")


def test_slowmo_factor_needs_points():
    live = run_along(0, np.linspace(0, 4, 60), np.full(60, 1.0))
    assert V.slowmo_factor(Run(5, 9, np.full((80, 2), np.nan), 25.0, 0), live) is None


def test_point_link_skips_another_point_and_old_points():
    strokes = [{"t": 3.0, "side": "near"}, {"t": 4.0, "side": "near"}]
    v = V.View(60.0, 63.0, "plano", kind="lateral")
    assert V.link_by_order(v, strokes, [(0, 8), (20, 45)], hits=1) == []        # 25 s of another point in between
    assert V.link_by_order(V.View(200.0, 203.0, "plano", kind="lateral"), strokes, [], 1) == []    # > 90 s later
    got = V.link_by_order(V.View(10.0, 13.0, "plano", kind="frontal"), strokes, [(0, 8)], hits=2)
    assert [x["live_t"] for x in got] == [3.0, 4.0] and got[0]["confidence"] == 0.6


def test_frame_evidence_on_real_pixels():
    """A drawn side view (long horizontal lines on a blue court) and an empty frame."""
    import cv2

    img = np.full((360, 640, 3), (140, 90, 40), np.uint8)
    for y in (120, 200, 300):
        cv2.line(img, (20, y), (620, y + 6), (255, 255, 255), 3)
    ev = V.frame_evidence(img, people_h=0.3)
    assert ev["lines_behind"] == 0 and ev["long_lines"] >= 2 and ev["horiz_share"] >= 0.9 and ev["people_h"] == 0.3
    blank = V.frame_evidence(np.zeros((360, 640, 3), np.uint8))
    assert blank["long_lines"] == 0 and blank["horiz_share"] is None and blank["people_h"] is None
    m = V.merge_evidence([ev, blank, {**ev, "pitch_deg": 12.0}])
    assert m["sampled"] == 3 and m["people_h"] == 0.3 and m["pitch_deg"] == 12.0
    assert V.merge_evidence([]) == {"sampled": 0}


def test_coverage_and_audit_item(tmp_path):
    from tennisbio.audit import views_items

    strokes = [{"views": [{"kind": "repeticion_principal", "slowmo": 2.0}], "slowmo_view": True},
               {"views": [{"kind": "lateral"}]}, {}, {}]
    c = V.coverage(strokes)
    assert c == {"strokes": 4, "with_replay": 1, "with_other_camera": 1, "with_slowmo": 1, "replay_share": 0.25, "other_share": 0.25}
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(strokes))
    it = views_items([d])
    assert it[0]["status"] == "aviso" and "views" in it[0]["detail"]            # stage not run
    (d / "views.json").write_text(json.dumps({"summary": {"repeticion_principal": 3, "lateral": 1}}))
    it = views_items([d], min_strokes=2)
    assert it[0]["status"] == "ok" and "25%" in it[0]["detail"] and it[0]["area"] == "Repeticiones y otras cámaras"
    assert views_items([d])[0]["status"] == "pocos datos"


def test_fine_on_slowmo_is_a_declared_todo():
    with pytest.raises(NotImplementedError):
        V.fine_on_slowmo(None, {}, {}, {})


def test_shot_frames_come_from_a_keyframe_inside_each_shot(tmp_path):
    """27-10 (B-3): every sampled shot is read at a keyframe inside it (decoded alone); a shot with no keyframe
    inside it at all is read at its exact frame. Nothing is taken from another shot."""
    import subprocess
    from tennisbio import pipeline, stages
    from tennisbio.catalog import Match, Player
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=6:size=160x90:rate=25",
                    "-c:v", "libx264", "-g", "25", "-keyint_min", "25", "-sc_threshold", "0", "-pix_fmt", "yuv420p", str(v)],
                   check=True, timeout=60)
    scenes = {"fps": 25.0, "shots": [{"start": 0, "end": 60, "main_camera": False},          # 0-2.4 s: keyframes 0, 1, 2
                                     {"start": 60, "end": 70, "main_camera": False},         # 2.4-2.8 s: none inside
                                     {"start": 70, "end": 150, "main_camera": False}]}       # 2.8-6 s: 3, 4, 5
    logs = []
    ctx = pipeline.Context(Match("m", v, Player("p", "P")), {"views": {"people": False}}, tmp_path / "o", log=logs.append)
    ctx.dir.mkdir(parents=True)
    ctx.progress = lambda *a, **k: None
    ev = stages._sample_views(ctx, scenes, [0, 1, 2], None)
    assert set(ev) == {0, 1, 2} and all(e["sampled"] >= 1 for e in ev.values())
    line = next(l for l in logs if "tomas:" in l)
    assert "1 exactos" in line and "6 claves en el vídeo" in line
