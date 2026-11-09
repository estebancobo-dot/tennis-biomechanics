"""#218 (09-11): the replays and other cameras linked to her strokes, shown on the stroke's page of the report (clips
of those shots, stage view_clips) and measured on the slow-motion replay (stage slowmo_fine, `views.fine_on_slowmo`),
with their audit checks. Synthetic videos and data, one case per test."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tennisbio import audit as A
from tennisbio import pipeline, real_status, stages  # noqa: F401  (registers the stages)
from tennisbio import view_stages as VS
from tennisbio import views as V
from tennisbio.catalog import Match, Player
from tennisbio.clip_pipeline import ClipRun
from tennisbio.pipeline import Context
from tennisbio.skeleton import Skeleton

CHROMIUM = Path("/opt/pw-browsers/chromium")
REPLAY = {"kind": "repeticion_principal", "label": "Repetición (cámara principal)", "t0": 6.0, "t1": 11.0, "slowmo": 2.0,
          "speed": "lenta", "impact_t": 8.0, "method": "recorrido", "confidence": 0.9}
SIDE = {"kind": "lateral", "label": "Cámara lateral", "t0": 2.0, "t1": 4.0, "slowmo": None, "speed": None, "impact_t": None,
        "method": "orden", "confidence": 0.6}


def video(path: Path, seconds=12, size="320x180", rate=25) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate={rate}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True, timeout=60)
    return path


def ctx_for(tmp_path, cfg=None, vid=None) -> Context:
    out = tmp_path / "m1"
    out.mkdir(exist_ok=True)
    c = Context(Match("m1", vid or tmp_path / "v.mp4", Player("p", "P", height_m=1.84)), cfg or {}, out, log=lambda *_: None)
    c.progress = lambda *a, **k: None
    return c


def stroke(t, views=None, **kw):
    s = {"stroke": "forehand", "side": "near", "match_time_s": t, "stroke_id": f"g{int(t)}",
         "metrics": {"elbow_impact_deg": 140.0, "contact_height_pct": 50.0, "contact_lateral_pct": 30.0}, **kw}
    if views is not None:
        s["views"] = views
        if any(v["kind"] == "repeticion_principal" and (v.get("slowmo") or 0) > 1.25 for v in views):
            s["slowmo_view"] = True
    return s


# --- where each clip is cut ---------------------------------------------------------------------------------
def test_clip_spec_around_the_impact_times_the_slowmo_factor():
    c = V.clip_spec(REPLAY)
    assert c["t0"] == 6.0 and c["dur"] == pytest.approx(3.6)       # 8 − 1 × 2 → clipped to the shot start; 8 + 0.8 × 2
    assert c["impact_in_clip"] == 2.0 and not c["whole_shot"] and c["file"] == "v000006000_03600.mp4"
    c = V.clip_spec({**REPLAY, "t0": 0.0, "t1": 30.0, "slowmo": 1.0, "speed": "normal"})
    assert (c["t0"], c["dur"], c["impact_in_clip"]) == (7.0, 1.8, 1.0)


def test_clip_spec_without_an_instant_takes_the_shot_from_its_start():
    c = V.clip_spec(SIDE)
    assert (c["t0"], c["dur"], c["impact_in_clip"], c["whole_shot"]) == (2.0, 2.0, None, True)
    c = V.clip_spec({**SIDE, "t1": 40.0})                                   # a long close-up: the first 10 s
    assert c["dur"] == 10.0 and not c["whole_shot"]
    assert V.clip_spec({**SIDE, "t1": 2.2}) is None                         # shorter than a view
    # an instant outside the shot (a bad factor): treated as unknown, never a clip pointing outside it
    assert V.clip_spec({**REPLAY, "impact_t": 30.0})["impact_in_clip"] is None


def test_clip_plan_one_row_per_linked_view_and_shared_files():
    strokes = [stroke(3.0, [SIDE]), stroke(4.0, [SIDE, REPLAY]), stroke(5.0), {"stroke": "forehand", "views": [SIDE]}]
    plan = V.clip_plan(strokes)
    assert [(r["key"], r["kind"]) for r in plan] == [("near@3.000", "lateral"), ("near@4.000", "lateral"),
                                                     ("near@4.000", "repeticion_principal")]
    assert plan[0]["file"] == plan[1]["file"]                               # the same shot, the same cut: one file
    assert V.clip_plan(strokes, {**V.clip_settings({}), "max_s": 1.0})[0]["clip_dur"] == 1.0


def test_clip_settings_defaults_and_switch():
    assert V.clip_settings({}) == {"enabled": True, "pre_s": 1.0, "post_s": 0.8, "max_s": 10.0, "width": 1280, "crf": 23}
    assert V.clip_settings({"views": {"clips": {"enabled": False}}})["enabled"] is False


# --- the stage view_clips -------------------------------------------------------------------------------------
def test_view_clips_cuts_each_clip_once_and_never_touches_strokes(tmp_path):
    vid = video(tmp_path / "v.mp4")
    ctx = ctx_for(tmp_path, vid=vid)
    late = {**SIDE, "t0": 50.0, "t1": 53.0}                                 # after the end of the video: fails, alone
    strokes = [stroke(3.0, [SIDE]), stroke(4.0, [SIDE, REPLAY]), stroke(8.5, [late]), stroke(9.0)]
    ctx.path("strokes.json").write_text(json.dumps(strokes), encoding="utf-8")
    before = ctx.path("strokes.json").read_bytes()
    s = VS.st_view_clips(ctx)
    assert s["linked_strokes"] == 3 and s["clips"] == 3 and s["cut"] == 2 and s["failed"] == 1
    assert s["strokes_with_clip"] == 2
    assert ctx.path("strokes.json").read_bytes() == before                 # the fine pass's output is not rewritten
    doc = json.loads(ctx.path(VS.CLIPS_FILE).read_text(encoding="utf-8"))
    files = sorted(p.name for p in (ctx.dir / "view_clips").glob("*.mp4"))
    assert files == ["v000002000_02000.mp4", "v000006000_03600.mp4"]
    rep = next(c for c in doc["clips"] if c["kind"] == "repeticion_principal")
    assert rep["impact_in_clip"] == 2.0 and rep["ok"] and rep["speed"] == "lenta"
    from tennisbio.io.video import probe
    assert probe(ctx.dir / "view_clips" / "v000006000_03600.mp4").duration == pytest.approx(3.6, abs=0.15)
    # again: nothing cut again; a view no longer linked loses its clip
    ctx.path("strokes.json").write_text(json.dumps([stroke(4.0, [REPLAY])]), encoding="utf-8")
    s = VS.st_view_clips(ctx)
    assert s["cut"] == 0 and s["reused"] == 1
    assert sorted(p.name for p in (ctx.dir / "view_clips").glob("*.mp4")) == ["v000006000_03600.mp4"]


def test_view_clips_without_strokes_or_switched_off(tmp_path):
    ctx = ctx_for(tmp_path)
    assert VS.st_view_clips(ctx)["clips"] == 0                             # no strokes.json: an empty plan, no error
    ctx.path("strokes.json").write_text(json.dumps([stroke(4.0, [REPLAY])]), encoding="utf-8")
    ctx.cfg = {"views": {"clips": {"enabled": False}}}
    s = VS.st_view_clips(ctx)
    assert s == {**s, "enabled": False, "clips": 0} and not (ctx.dir / "view_clips").exists()
    assert ctx.path(VS.CLIPS_FILE).exists()                                # the output is always written


def test_new_stages_hang_off_the_old_ones_without_changing_them():
    S = pipeline.STAGES
    for n in ("view_clips", "slowmo_fine"):
        assert set(S[n].deps) == {"views", "fine", "views_link"} and S[n].resource is None
        assert S[n].code == ("view_stages", "views")
    for n in ("candidates", "fine", "fine_opponent", "fine_doubtful", "views", "views_link"):
        assert not {"view_clips", "slowmo_fine"} & set(S[n].deps)
    assert S["fine"].version == "16" and S["views"].version == "6" and S["views_link"].version == "1"
    assert "view_stages" not in S["fine"].code and "views" not in S["fine"].code
    order = pipeline.order(list(S))
    assert order.index("views_link") < order.index("view_clips") and order.index("views_link") < order.index("slowmo_fine")


# --- the measures on the slow-motion replay -------------------------------------------------------------------
def standing(T=60, fps=50.0, hit=30):
    """A standing near player (COCO 17, image px, y down, 400 px tall) whose dominant (right) wrist sweeps fast
    through frame `hit`, with the arm straight there."""
    sk = Skeleton("coco17", "right")
    kp = np.zeros((T, 17, 2))
    y = {"nose": 100, "eye": 95, "ear": 98, "shoulder": 160, "elbow": 230, "wrist": 300, "hip": 300, "knee": 400, "ankle": 500}
    for j, name in enumerate(["nose", "eye", "eye", "ear", "ear", "shoulder", "shoulder", "elbow", "elbow", "wrist", "wrist",
                              "hip", "hip", "knee", "knee", "ankle", "ankle"]):
        kp[:, j] = (500 + (-20 if j % 2 else 20) * (j >= 5), y[name])
    f = np.arange(T)
    rs, re, rw = sk["dom_shoulder"], sk["dom_elbow"], sk["dom_wrist"]
    # the arm swings around the shoulder; straight (elbow on the shoulder→wrist line) at the hit
    ang = np.radians(-60 + 120 / (1 + np.exp(-(f - hit) / 2.0)))
    kp[:, rw] = kp[:, rs] + 140 * np.c_[np.cos(ang), np.sin(ang)]
    kp[:, re] = kp[:, rs] + 70 * np.c_[np.cos(ang), np.sin(ang)]
    run = ClipRun(fps, sk, kp, np.ones((T, 17)), [[0, 0, 1, 1]] * T, 1.0, 400.0, np.zeros(0), [])
    run.height_t = np.full(T, 400.0)
    return run


def test_slowmo_measures_find_the_impact_by_the_wrist_and_measure_as_live():
    run = standing()
    got = V.slowmo_measures(run, guess=27, factor=2.0)
    assert got["impact_by"] == "muñeca" and abs(got["impact_frame"] - 30) <= 1
    m = got["measures"]
    assert m["elbow_impact_deg"] == pytest.approx(180, abs=2)               # straight arm
    assert m["contact_height_pct"] == pytest.approx((500 - 160) / 400 * 100, abs=4)     # the hand at shoulder height
    assert m["contact_lateral_pct"] == pytest.approx(140 / 400 * 100, abs=4)
    blank = standing()
    blank.img[:] = np.nan
    assert V.slowmo_measures(blank, 30, 2.0) is None                        # she is not seen: nothing measured
    assert V.slowmo_measures(run, 500, 2.0) is None


def test_slowmo_view_and_settings():
    assert V.slowmo_view(stroke(4.0, [SIDE, REPLAY]))["t0"] == 6.0
    assert V.slowmo_view(stroke(4.0, [{**REPLAY, "slowmo": 1.0}])) is None   # normal speed
    assert V.slowmo_view(stroke(4.0, [{**REPLAY, "impact_t": None}])) is None   # instant unknown
    assert V.slowmo_settings({})["enabled"] is True
    assert V.slowmo_settings({"views": {"fine_on_slowmo": False}})["enabled"] is False
    assert V.slowmo_settings({"views": {"fine_on_slowmo": {"enabled": False}}})["enabled"] is False


def test_fine_on_slowmo_cuts_the_replay_and_keeps_the_live_values(tmp_path):
    vid = video(tmp_path / "v.mp4")
    asked = []

    def runner(clip, cache, hand, height_m, **kw):
        asked.append((Path(clip).name, kw["pose_only"], kw["rackets"]))
        return standing(T=50, fps=25.0, hit=20)

    s = stroke(4.0, [REPLAY], racket={"impact": {"elevation_deg": 10.0}})
    keep = json.dumps(s)
    got = V.fine_on_slowmo(vid, s, REPLAY, {}, tmp_path / "slow", runner=runner)
    assert asked == [("s000007200_01600.mp4", True, False)]                 # 8 ± 0.4 × 2 s of the replay, pose only
    assert (tmp_path / "slow" / "s000007200_01600.mp4").exists()
    assert got["impact_by"] == "muñeca" and got["slowmo"] == 2.0 and got["clip_t0"] == 7.2
    assert got["measures"]["elbow_impact_deg"] == pytest.approx(180, abs=2)
    assert got["live"]["elbow_impact_deg"] == 140.0 and got["live"]["racket_elevation_deg"] == 10.0
    assert json.dumps(s) == keep                                             # the live stroke is never changed
    assert V.fine_on_slowmo(vid, s, SIDE, {}, tmp_path / "slow", runner=runner) is None
    assert V.fine_on_slowmo(vid, s, None, {}, tmp_path / "slow", runner=runner) is None


def test_racket_on_the_slowmo_frames_with_a_racket_model(tmp_path):
    vid = video(tmp_path / "v.mp4", size="640x360")
    wrist = np.tile([[300.0, 200.0]], (60, 1))

    def racket(frame, boxes):                  # handle at the wrist, head 50 px to the right and 50 px up
        kp = np.array([[[370, 130], [330, 170], [300, 200], [340, 140], [360, 160]]], float)
        return kp, np.full((1, 5), 0.9)

    r = V._racket_at(vid, [10, 11, 12], wrist, 400.0, 1.84, racket)
    assert r["racket_frames"] == 3 and r["racket_elevation_deg"] == pytest.approx(45, abs=1)
    assert r["racket_head_above_wrist_cm"] == pytest.approx(50 / 400 * 184, abs=1)
    assert V._racket_at(vid, [10], wrist, 400.0, 1.84, lambda f, b: (np.zeros((1, 5, 2)), np.zeros((1, 5)))) == {}


def test_slowmo_stage_on_and_off(tmp_path, monkeypatch):
    seen = []

    def fake(video, s, view, cfg, dest_dir, *a, **k):
        seen.append((s["match_time_s"], view["slowmo"]))
        return {"clip": "s1.mp4", "clip_t0": 7.2, "slowmo": view["slowmo"], "impact_in_clip": 0.8, "impact_by": "muñeca",
                "fps": 50.0, "frames": 80, "tracked": 1.0, "measures": {"elbow_impact_deg": 150.0}, "live": {"elbow_impact_deg": 140.0}}

    monkeypatch.setattr(V, "fine_on_slowmo", fake)
    ctx = ctx_for(tmp_path)
    far = stroke(9.0, [REPLAY], side="far")
    ctx.path("strokes.json").write_text(json.dumps([stroke(4.0, [SIDE, REPLAY]), stroke(5.0, [SIDE]), far]), encoding="utf-8")
    before = ctx.path("strokes.json").read_bytes()
    s = VS.st_slowmo_fine(ctx)
    assert seen == [(4.0, 2.0)] and s["measured"] == 1 and s["slowmo_strokes"] == 1 and s["frames"] == 80
    doc = json.loads(ctx.path(VS.SLOWMO_FILE).read_text(encoding="utf-8"))
    assert doc["enabled"] and doc["strokes"][0]["key"] == "near@4.000" and doc["strokes"][0]["view_t0"] == 6.0
    assert ctx.path("strokes.json").read_bytes() == before                 # beside, never instead of, the live values
    ctx.cfg = {"views": {"fine_on_slowmo": False}}
    seen.clear()
    s = VS.st_slowmo_fine(ctx)
    assert seen == [] and s["enabled"] is False and json.loads(ctx.path(VS.SLOWMO_FILE).read_text())["strokes"] == []
    # the switch and the models are part of its fingerprint
    assert VS._slowmo_settings({})["enabled"] and "models" in VS._slowmo_settings({})
    assert VS._slowmo_settings({"views": {"fine_on_slowmo": False}}) != VS._slowmo_settings({})


def test_slowmo_stage_survives_a_failing_stroke(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("sin vídeo")

    monkeypatch.setattr(V, "fine_on_slowmo", boom)
    ctx = ctx_for(tmp_path)
    ctx.path("strokes.json").write_text(json.dumps([stroke(4.0, [REPLAY])]), encoding="utf-8")
    s = VS.st_slowmo_fine(ctx)
    assert s["failed"] == 1 and s["measured"] == 0


# --- the report and the audit ---------------------------------------------------------------------------------
def match_with_views(tmp_path, cut=True, slow=True):
    """A match folder with 2 strokes shown by replays / a side camera, their clips and one slow-motion measure."""
    d = tmp_path / "m1"
    (d / "view_clips" / "slowmo").mkdir(parents=True)
    strokes = [stroke(3.0, [SIDE]), stroke(4.0, [SIDE, REPLAY]), stroke(9.0)]
    (d / "strokes.json").write_text(json.dumps(strokes), encoding="utf-8")
    plan = V.clip_plan(strokes)
    for r in plan:
        if cut:
            (d / "view_clips" / r["file"]).write_bytes(b"x" * 100)
    (d / VS.CLIPS_FILE).write_text(json.dumps({"version": 1, "dir": "view_clips", "clips": [{**r, "ok": cut} for r in plan],
                                               "summary": {"clips": 2}}), encoding="utf-8")
    if slow:
        (d / "view_clips" / "slowmo" / "s1.mp4").write_bytes(b"x" * 100)
        (d / VS.SLOWMO_FILE).write_text(json.dumps({"version": 1, "enabled": True, "summary": {"frames": 80, "seconds": 9},
                                                    "strokes": [{"key": "near@4.000", "clip": "s1.mp4", "slowmo": 2.0,
                                                                 "impact_in_clip": 0.8, "impact_by": "muñeca",
                                                                 "measures": {"elbow_impact_deg": 152.0, "contact_height_pct": 51.0},
                                                                 "live": {"elbow_impact_deg": 140.0, "contact_height_pct": 50.0}}]}),
                                         encoding="utf-8")
    return d


def report_of(tmp_path):
    from tennisbio.audit import report_data
    from tennisbio.report import build

    html = build([Match("m1", None, Player("p", "P", height_m=1.84))], tmp_path)
    return html, report_data(html)


def test_report_puts_the_clips_and_the_slowmo_measures_on_the_stroke(tmp_path):
    d = match_with_views(tmp_path)
    html, data = report_of(tmp_path)
    by_t = {r["t"] if "t" in r else i: r for i, r in enumerate(data["strokes"])}
    rows = data["strokes"]
    with_views = [r for r in rows if r.get("views")]
    assert len(with_views) == 2 and not any("_key" in r for r in rows)
    two = max(with_views, key=lambda r: len(r["views"]))
    rep = next(v for v in two["views"] if v["kind"] == "repeticion_principal")
    assert rep["clip"].endswith("m1/view_clips/v000006000_03600.mp4") and rep["impact"] == 2.0 and rep["speed"] == "lenta"
    assert (html.parent / rep["clip"]).resolve() == (d / "view_clips" / "v000006000_03600.mp4").resolve()
    side = next(v for v in two["views"] if v["kind"] == "lateral")
    assert side["impact"] is None and side["whole"]
    sm = two["slowmo"]
    assert sm["factor"] == 2.0 and sm["clip"].endswith("view_clips/slowmo/s1.mp4")
    assert [(x["k"], x["v"], x["live"]) for x in sm["rows"]] == [("elbow_impact_deg", 152.0, 140.0), ("contact_height_pct", 51.0, 50.0)]
    assert by_t and "en la repetición a cámara lenta" in html.read_text(encoding="utf-8")
    # the audit: every linked stroke has its clips in the report; the slow-motion one is measured and shown
    it = A.view_clips_items([d], html.parent)[0]
    assert it["name"] == "Repeticiones en el informe: m1" and it["status"] == "ok", it["detail"]
    assert "100% de sus golpes" in it["detail"] and it["linked"] == 2
    it = A.slowmo_items([d], html.parent)[0]
    assert it["name"] == "Medidas en la cámara lenta: m1" and it["status"] == "ok", it["detail"]
    assert "1 de 1" in it["detail"]


def test_report_without_the_new_stages_is_as_before(tmp_path):
    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps([stroke(3.0, [SIDE]), stroke(9.0)]), encoding="utf-8")
    html, data = report_of(tmp_path)
    assert not any(r.get("views") or r.get("slowmo") for r in data["strokes"])
    it = A.view_clips_items([d], html.parent)[0]
    assert it["status"] == "aviso" and "view_clips" in it["detail"]
    it = A.slowmo_items([d], html.parent)[0]                                # no slow-motion replay with its instant
    # 09-11: nothing to measure holds (every stroke with such a replay is measured: there are none), and says so
    assert it["status"] == "ok" and "nada que medir" in it["detail"]


def test_audit_warns_when_clips_are_missing_or_not_in_the_report(tmp_path):
    d = match_with_views(tmp_path, cut=False, slow=False)
    html, _ = report_of(tmp_path)
    it = A.view_clips_items([d], html.parent)[0]
    assert it["status"] == "aviso" and "2 sin recorte" in it["detail"]
    it = A.slowmo_items([d], html.parent)[0]
    assert it["status"] == "aviso" and "slowmo_fine" in it["detail"]
    # the clips exist but the report was built before them: not referenced
    d2 = match_with_views(tmp_path / "b")
    it = A.view_clips_items([d2], html.parent)[0]
    assert it["status"] == "aviso" and "no en el informe" in it["detail"]
    assert A.view_clips_items([d2], None)[0]["status"] == "aviso"
    # nothing linked: few data, not a failure
    d3 = tmp_path / "c" / "m1"
    d3.mkdir(parents=True)
    (d3 / "strokes.json").write_text(json.dumps([stroke(1.0)]), encoding="utf-8")
    assert A.view_clips_items([d3], None)[0]["status"] == "pocos datos"
    # the switch off: no slow-motion check at all
    (d / VS.SLOWMO_FILE).write_text(json.dumps({"version": 1, "enabled": False, "strokes": []}), encoding="utf-8")
    assert A.slowmo_items([d], html.parent) == []


def test_audit_slowmo_below_the_share_warns(tmp_path):
    d = match_with_views(tmp_path)
    st = json.loads((d / "strokes.json").read_text(encoding="utf-8"))
    st += [stroke(20.0 + k, [{**REPLAY, "t0": 20.0 + k, "t1": 21.0 + k, "impact_t": 20.5 + k}]) for k in range(3)]
    (d / "strokes.json").write_text(json.dumps(st), encoding="utf-8")
    it = A.slowmo_items([d], None)[0]
    assert it["status"] == "aviso" and "1 de 4" in it["detail"]


def test_requests_218_follow_the_new_checks():
    rule = A.PETITIONS[218]
    import re
    for name in ("Repeticiones en el informe: m1", "Medidas en la cámara lenta: m1", "Golpes del fondo: m1"):
        assert re.search(rule, name)
    states = {rid: st for rid, _, st in real_status.registry()}
    ok = lambda name: {"req": 2, "area": "Repeticiones y otras cámaras", "name": name, "status": "ok", "detail": ""}
    items = [ok("Repeticiones y otras cámaras enlazadas: m"), ok("Repeticiones en el informe: m"),
             ok("Medidas en la cámara lenta: m"), {**ok("Golpes del fondo: m"), "area": "Golpes"}]
    want = 3 if states[218] == "HECHO" else 2
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(items)}
    assert real_status.level(states[218], pet[218], 218) == want
    for bad_name in ("Repeticiones en el informe: m", "Medidas en la cámara lenta: m"):
        bad = [{**i, "status": "aviso"} if i["name"] == bad_name else i for i in items]
        pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(bad)}
        assert pet[218]["status"] == "aviso" and real_status.level(states[218], pet[218], 218) == 2


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_stroke_page_plays_the_replays_next_to_the_live_window(tmp_path):
    """«Análisis de golpe» in a real browser: the stroke's replay and side camera as playable clips, the slow-motion
    replay at her impact, and what it measured «en la repetición a cámara lenta» beside the live value."""
    from playwright.sync_api import sync_playwright

    d = match_with_views(tmp_path)
    for r in V.clip_plan(json.loads((d / "strokes.json").read_text(encoding="utf-8"))):
        video(d / "view_clips" / r["file"], seconds=4)
    html, data = report_of(tmp_path)
    idx = next(i for i, r in enumerate(data["strokes"]) if r.get("slowmo"))
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROMIUM), args=["--allow-file-access-from-files"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate(f"(async () => {{ showTab('golpe'); await loadStroke(STROKES[{idx}]); }})()")
        pg.wait_for_timeout(1500)
        hidden = pg.evaluate("document.getElementById('g-views').hidden")
        text = pg.evaluate("document.getElementById('g-views').innerText")
        n_vid = pg.evaluate("document.querySelectorAll('#g-views-list video').length")
        srcs = pg.evaluate("[...document.querySelectorAll('#g-views-list video')].map(v => v.getAttribute('src'))")
        pg.click("#g-views-list [data-vimp]")                                # «▶ Impacto» (this Chromium plays no H.264)
        pg.click("#g-views-list [data-vrate][data-v='0.25']")
        pg.wait_for_timeout(200)
        other = next(i for i, r in enumerate(data["strokes"]) if not r.get("views"))
        pg.evaluate(f"(async () => {{ await loadStroke(STROKES[{other}]); }})()")
        pg.wait_for_timeout(500)
        hidden_other = pg.evaluate("document.getElementById('g-views').hidden")
        b.close()
    assert not errors, errors[:3]
    assert not hidden and n_vid == 2
    assert sorted(srcs) == sorted(r["clip"] for r in data["strokes"][idx]["views"])
    assert all((html.parent / x).exists() for x in srcs)                    # each clip plays from the report's folder
    assert "Repetición (cámara principal)" in text and "a cámara lenta (2,0× más despacio)" in text and "Cámara lateral" in text
    assert "Impacto (2,0 s)" in text and "el instante de su impacto no se conoce" in text
    assert "En la repetición a cámara lenta" in text and "Codo en el impacto: 152 °" in text and "140 ° en directo" in text
    assert hidden_other
