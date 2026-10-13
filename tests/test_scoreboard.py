import numpy as np
import pytest

from tennisbio.scoreboard import parse


def box(x, y, w=40, h=20):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def test_parse_glued_digits_advantage_and_banner():
    items = [(box(50, 30), "BREAKPOINT#2", .99), (box(60, 70), "SABALENKA", .98), (box(400, 70), "472", 1.0),
             (box(60, 115), "RYBAKINA", .99), (box(230, 115), "KAZ", .99), (box(400, 115), "654", 1.0),
             (box(520, 115), "AD", .99)]
    s = parse(items, ("Rybakina", "Sabalenka"))
    assert s.games == [[6, 4], [5, 7], [4, 2]] and s.points == ["AD", "40"]
    assert s.set_number == 3 and s.sets_won == [1, 1] and s.pressure and s.banner == "BREAK POINT"


def test_parse_plain_points_no_pressure_and_ocr_typo():
    items = [(box(60, 70), "RYBAKlNA", .9), (box(400, 70), "2", 1.0), (box(450, 70), "15", 1.0),
             (box(60, 115), "SABALENKA", .98), (box(400, 115), "1", 1.0), (box(450, 115), "0", 1.0)]
    s = parse(items, ("Rybakina", "Sabalenka"))
    assert s.games == [[2, 1]] and s.points == ["15", "0"] and not s.pressure


def test_parse_missing_name_returns_none():
    assert parse([(box(60, 70), "SABALENKA", .9)], ("Rybakina", "Sabalenka")) is None


def test_opponent_from_items():
    from tennisbio.scoreboard import opponent_from_items
    items = [(box(50, 30, 200), "BREAKPOINT#2", .99), (box(60, 70, 150), "SABALENKA", .98), (box(400, 70), "472", 1.0),
             (box(60, 115, 140), "RYBAKINA", .99), (box(230, 115), "KAZ", .99), (box(400, 115), "654", 1.0)]
    assert opponent_from_items(items, "Rybakina") == "Sabalenka"
    assert opponent_from_items(items[3:], "Rybakina") is None


def board_frame(rows, server=0, seed=0, size=(720, 1280), banner=""):
    """A broadcast-like frame: noisy court background, scoreboard box at the top left with both
    names, set games and points, a yellow serve ball next to the server's row."""
    import cv2
    rng = np.random.default_rng(seed)
    img = np.full((*size, 3), (60, 100, 70), np.uint8)
    cv2.rectangle(img, (0, 400), (size[1], size[0]), (90, 90, 160), -1)
    x0, y0 = 40, 40
    cv2.rectangle(img, (x0, y0), (x0 + 420, y0 + 100), (40, 20, 20), -1)
    for k, (name, games, pts) in enumerate(rows):
        y = y0 + 38 + 44 * k
        cv2.putText(img, name, (x0 + 28, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        for j, g in enumerate(games):
            cv2.putText(img, str(g), (x0 + 250 + 32 * j, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, pts, (x0 + 350, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.circle(img, (x0 + 14, y0 + 28 + 44 * server), 7, (0, 230, 255), -1)
    if banner:
        cv2.putText(img, banner, (x0 + 40, y0 + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    noise = rng.normal(0, 2.0, img.shape)                 # compression-like noise on every frame
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def test_crop_changed_ignores_noise_but_sees_a_new_digit_or_serve_marker():
    from tennisbio.scoreboard import crop_changed
    rows = [("RYBAKINA", [6, 3], "15"), ("SABALENKA", [4, 2], "30")]
    a = board_frame(rows, seed=1)[40:140, 40:460]
    assert not crop_changed(a, board_frame(rows, seed=2)[40:140, 40:460])
    assert crop_changed(a, board_frame([rows[0], ("SABALENKA", [4, 2], "40")], seed=2)[40:140, 40:460])
    assert crop_changed(a, board_frame([("RYBAKINA", [6, 4], "15"), rows[1]], seed=2)[40:140, 40:460])
    assert crop_changed(a, board_frame(rows, server=1, seed=2)[40:140, 40:460])
    assert crop_changed(a, a[:-2]) and crop_changed(None, a)


class FakeOCR:
    """Stands in for RapidOCR: returns the items of whatever scoreboard is drawn (known by the test)."""

    def __init__(self):
        self.calls, self.items = [], None

    def __call__(self, img, use_cls=None):
        self.calls.append((img.shape, use_cls))
        return self.items, None


def test_reader_reuses_the_region_ocr_while_the_scoreboard_does_not_change():
    from tennisbio.scoreboard import ScoreReader
    ocr = FakeOCR()
    r = ScoreReader("Rybakina", "Sabalenka", max_reuse=2, ocr=ocr)
    full = [(box(60, 70, 140), "RYBAKINA", .99), (box(300, 70), "6", 1.), (box(400, 70), "15", 1.),
            (box(60, 115, 140), "SABALENKA", .99), (box(300, 115), "4", 1.), (box(400, 115), "30", 1.)]
    ocr.items = full
    rows = [("RYBAKINA", [6], "15"), ("SABALENKA", [4], "30")]
    frames = [board_frame(rows, seed=s) for s in range(5)]
    sts = [r.read(f) for f in frames]
    # first read: full-frame search + region; then 2 reuses; then the safety re-read; then a reuse
    assert len(ocr.calls) == 3 and r.ocr_calls == 3
    assert ocr.calls[0][1] is None and ocr.calls[1][1] is False      # no angle classifier in the region
    assert all(s is not None and s.games == [[6, 4]] and s.points == ["15", "30"] for s in sts)
    # the scoreboard changes: OCR again at once
    ocr.items = full[:5] + [(box(400, 115), "40", 1.)]
    st = r.read(board_frame([rows[0], ("SABALENKA", [4], "40")], seed=9))
    assert len(ocr.calls) == 4 and st.points == ["15", "40"]


def test_reader_lost_region_is_searched_again_and_cache_dropped():
    from tennisbio.scoreboard import ScoreReader
    ocr = FakeOCR()
    r = ScoreReader("Rybakina", "Sabalenka", relocate_after=2, max_reuse=10, ocr=ocr)
    ocr.items = [(box(60, 70, 140), "RYBAKINA", .99), (box(300, 70), "6", 1.),
                 (box(60, 115, 140), "SABALENKA", .99), (box(300, 115), "4", 1.)]
    blank = board_frame([("RYBAKINA", [6], ""), ("SABALENKA", [4], "")], seed=0)
    assert r.read(blank) is not None            # names found: region located
    ocr.items = []                              # e.g. a replay without the scoreboard
    empty = np.full_like(blank, 30)
    assert r.read(empty) is None and r.roi is not None
    assert r.read(empty) is None and r.roi is None and r.last is None


def test_same_readings_with_real_ocr_as_reading_every_frame():
    """On synthetic broadcast frames the readings with the region cache and without the angle
    classifier are the ones of an OCR of every frame (the previous behaviour)."""
    pytest.importorskip("rapidocr_onnxruntime")
    from tennisbio.scoreboard import ScoreReader
    seq = [("15", "15", 0), ("15", "15", 0), ("15", "15", 0), ("30", "40", 0), ("30", "40", 0), ("15", "30", 1)]
    frames = []
    for k, (p, o, srv) in enumerate(seq):
        g = [6, 3] if srv == 0 else [6, 4]
        frames.append(board_frame([("RYBAKINA", g, p), ("SABALENKA", [4, 2], o)], server=srv, seed=k))
    old = ScoreReader("Rybakina", "Sabalenka", max_reuse=0)
    old._cls_kw = False                         # the old call: angle classifier on, OCR every frame
    new = ScoreReader("Rybakina", "Sabalenka", max_reuse=5)
    a = [s.to_dict() if s else None for s in map(old.read, frames)]
    b = [s.to_dict() if s else None for s in map(new.read, frames)]
    assert a == b
    assert a[0]["points"] == ["15", "15"] and a[3]["points"] == ["30", "40"] and a[-1]["games"][-1] == [4, 2]
    assert a[0]["server"] == 0 and a[-1]["server"] == 1
    assert (old.ocr_calls, new.ocr_calls) == (7, 4)          # 1 full-frame search + 6 or 3 region reads


def test_score_stage_samples_the_same_times_with_one_sequential_read(tmp_path, monkeypatch):
    """The stage reads the main-camera shots every few seconds from one sequential decode: same
    sample times, frames and score.json format as the previous grab-per-sample loop."""
    import json
    import subprocess
    import sys
    import types

    import cv2

    from tennisbio import pipeline, stages
    from tennisbio.catalog import Match, Player

    fps, n = 25, 25 * 24
    video = tmp_path / "m.mp4"
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "640x360",
                             "-r", str(fps), "-i", "pipe:0", "-pix_fmt", "yuv420p", "-c:v", "libx264", str(video)],
                            stdin=subprocess.PIPE)
    for i in range(n):
        img = np.full((360, 640, 3), 80, np.uint8)
        cv2.putText(img, str(i), (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 5)   # frame number
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    proc.wait()

    seen = []

    class OCR:                                   # records which frame each OCR call saw
        def __call__(self, img, use_cls=None):
            seen.append(img.copy())
            return [(box(10, 10, 80), "PLAYER", .9), (box(200, 10), "3", 1.), (box(10, 40, 80), "RIVAL", .9),
                    (box(200, 40), "2", 1.)], None
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", types.SimpleNamespace(RapidOCR=OCR))
    ctx = pipeline.Context(Match("m", video, Player("p", "Ana Player"), opponent="Rival"),
                           {"score": {"every_s": 5.0}}, tmp_path / "out", log=lambda *_: None)
    ctx.dir.mkdir()
    ctx._prog["stage"] = "score"                 # as pipeline.run sets it
    shots = [{"start": 0, "end": 230, "main_camera": True}, {"start": 230, "end": 300, "main_camera": False},
             {"start": 300, "end": 310, "main_camera": True}, {"start": 310, "end": 600, "main_camera": True}]
    (ctx.dir / "scenes.json").write_text(json.dumps({"fps": fps, "shots": shots}))
    stages.st_score(ctx)
    res = json.loads((ctx.dir / "score.json").read_text())
    # the previous loop's times: from 0.5 s after each main shot's start, every 5 s, before its end
    exp = []
    for s in shots:
        t = s["start"] / fps + 0.5
        while s["main_camera"] and t < s["end"] / fps:
            exp.append(round(t, 2))
            t += 5.0
    assert [r["t"] for r in res["readings"]] == exp
    assert [(x["tried"], x["read"]) for x in res["shots"]] == [(2, 2), (0, 0), (3, 3)]
    assert set(res["readings"][0]) == {"t", "games", "points", "banner", "server", "set", "sets_won", "tiebreak",
                                       "pressure", "flags"}
    assert res["readings"][0]["games"] == [[3, 2]] and res["names"] == ["Player", "Rival"]
    # the first OCR (full-frame search) saw exactly the frame a seek to 0.5 s gives
    assert np.array_equal(seen[0], stages.grab_frame(video, 0.5))
