"""09-11 (request 167): in Rybakina–Pegula the two photos of the identity click were the same woman. Both
players in white: the clothes split followed the light, not the people, and nothing checked it. Now
- the identity stage checks its clothes groups against the end changes read on the scoreboard (no serve needed)
  and the distance between the groups' typical clothes (clothes.groups_check); groups that are not two people
  decide nothing and the click goes by the end changes (click_by «ends»);
- each photo is the run most typical of its group, checked on the photo itself (a frame of the other player is
  not chosen), and the two photos must differ in clothes, else the photos are of the two ends of the court;
- the cache of the photos follows identity.json, and estado.json says «fotos no distinguibles»."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_clothes import person  # noqa: E402

from tennisbio.app import identity_click as ic  # noqa: E402
from tennisbio.clothes import (aggregate, clothes_distances, clothing_feature, groups_check,  # noqa: E402
                               identity_from_cues)
from tennisbio.identity import apply_pick  # noqa: E402

FPS = 10.0
RUN_LEN = 10


def _code(outfit, light, rng, n=3):
    return aggregate([clothing_feature(*_frame(outfit, light * rng.uniform(0.95, 1.05), rng)) for _ in range(n)])


def _frame(outfit, light, rng):
    f, b, kp, cf = person(outfit, light, x=300, y=80, h=240, rng=rng)
    return f, kp, cf, b


# ---------------------------------------------------------------- the stage's check of its clothes groups

def test_one_white_dress_split_by_the_light_is_not_two_people():
    rng = np.random.default_rng(3)
    n = 24
    light = [0.6 if i % 3 else 1.3 for i in range(n)]                     # the light, not the person
    parity = [(i // 2) % 2 for i in range(n)]                             # who is near: the end changes
    codes = np.array([_code("B", li, rng) for li in light])
    per, s = identity_from_cues(codes, [], None, [None] * n, [None] * n, (), None, parities=parity)
    ck = s["clothes"]["check"]
    assert s["clothes"]["separation"] is not None and s["clothes"]["separation"] > 1.5   # the separation looks fine
    assert ck["distinguishable"] is False and ck["parity_runs"] >= 8 and ck["parity_agree"] < 0.7
    assert ck["centroid_dist"] < 0.10 and "casi igual" in ck["why"]
    assert s["click_by"] == "ends"
    assert all(p["method"] != "ropa" for p in per)                         # the clothes decide nothing


def test_two_outfits_that_follow_the_end_changes_are_two_people():
    rng = np.random.default_rng(4)
    n = 16
    parity = [(i // 2) % 2 for i in range(n)]
    codes = np.array([_code("A" if p == 0 else "B", rng.uniform(0.6, 1.3), rng) for p in parity])
    _, s = identity_from_cues(codes, [], None, [None] * n, [None] * n, (), None, parities=parity)
    ck = s["clothes"]["check"]
    assert ck["distinguishable"] is True and ck["parity_agree"] == 1.0 and ck["centroid_dist"] > 0.3
    assert s["click_by"] == "clothes"


def test_check_edge_cases():
    # nothing to check with: unknown, the click by clothes as before
    assert groups_check(None, np.array([0, 1]), np.array([.5, .5]))["distinguishable"] is None
    # few runs with the scoreboard: the parity is not used
    ck = groups_check(None, np.array([0, 1, 0, 1]), np.full(4, .5), [0, 0, 1, 1])
    assert ck["parity_runs"] == 4 and ck["distinguishable"] is None
    # groups that follow the parity inverted are still two people (group 0 at odd counts)
    lab = np.array([1, 1, 0, 0] * 3)
    ck = groups_check(None, lab, np.full(12, .5), [0, 0, 1, 1] * 3)
    assert ck["distinguishable"] is True and ck["parity_agree"] == 1.0
    # the far player in the same group as the near one: not two people
    ck = groups_check(None, lab, np.full(12, .5), None, far_pairs=10, far_opposite=0.4)
    assert ck["distinguishable"] is False and "fondo" in ck["why"]
    # alike and no scoreboard: no click at all
    rng = np.random.default_rng(5)
    codes = np.array([_code("B", 0.6 if i % 2 else 1.3, rng) for i in range(10)])
    _, s = identity_from_cues(codes, [], None, [None] * 10, [None] * 10, (), None, parities=[None] * 10)
    assert s["clothes"]["check"]["distinguishable"] is False and s["click_by"] is None


def test_the_click_goes_by_the_end_changes_when_the_clothes_are_alike():
    ident = {"fps": 10.0, "click_by": "ends", "runs": [
        {"start": 0, "end": 100, "cluster": 0, "clothes_margin": 0.5, "end_changes": 0, "near_is_target": None},
        {"start": 100, "end": 200, "cluster": 0, "clothes_margin": 0.5, "end_changes": 1, "near_is_target": None},
        {"start": 200, "end": 300, "cluster": 1, "clothes_margin": 0.5, "end_changes": 2, "near_is_target": None},
        {"start": 300, "end": 400, "cluster": 1, "clothes_margin": 0.5, "end_changes": None, "near_is_target": None}]}
    out, why = apply_pick(ident, {"t": 15.0, "near_is_her": True})         # she is near at 1 change
    assert why["pick"] == "aplicado" and why["by"] == "ends" and why["her_parity"] == 1
    assert [r["near_is_target"] for r in out["runs"]] == [False, True, False, None]
    assert all(r["method"] == "cambios de lado + clic" for r in out["runs"][:3])
    out, why = apply_pick(ident, {"t": 35.0, "near_is_her": True})         # no end changes read there
    assert why["pick"] == "sin cambios de lado leídos en ese momento"
    # a click made on clothes photos follows the end changes too once the stage found the clothes alike
    out, _ = apply_pick(ident, {"t": 5.0, "near_is_her": True, "by": "clothes"})
    assert [r["near_is_target"] for r in out["runs"]][:3] == [True, False, True]
    # neither: the click is not applied
    out, why = apply_pick({**ident, "click_by": None}, {"t": 5.0, "near_is_her": True})
    assert why["pick"].startswith("no aplicable") and out["runs"][0]["near_is_target"] is None
    # old identity.json (v8, no click_by): by clothes as before
    old = {k: v for k, v in ident.items() if k != "click_by"}
    out, why = apply_pick(old, {"t": 5.0, "near_is_her": True})
    assert why["pick"] == "aplicado" and [r["near_is_target"] for r in out["runs"]] == [True, True, False, False]


# ---------------------------------------------------------------- the photos

def _match(tmp_path, outfits, lights, clusters, parities, video_outfit=None, click_by="clothes", stage_check=None):
    """A match folder: players.npz (one player, the same pose in every frame), identity.json (runs with their
    clothes codes), and the frames the 'video' gives: outfit/light of the run at that time (video_outfit
    overrides the outfit per run: a frame of the other player)."""
    rng = np.random.default_rng(0)
    n = len(outfits)
    f, box, kp, cf = person("A", 1.0, x=300, y=80, h=240, rng=rng)
    frames = np.concatenate([np.arange(i * 100, i * 100 + RUN_LEN) for i in range(n)])
    m = len(frames)
    obj = lambda a: np.array([a] * m + [None], dtype=object)[:-1]          # noqa: E731
    np.savez(tmp_path / "players.npz", fps=FPS, frames=frames, boxes=obj(np.array([box])),
             kps=obj(np.array([kp])), confs=obj(np.array([cf])), feats=obj(np.zeros((1, 4))))
    runs = []
    for i in range(n):
        code = _code(outfits[i], lights[i], rng)
        runs.append({"start": i * 100, "end": i * 100 + RUN_LEN, "cluster": clusters[i], "clothes_margin": 0.4,
                     "end_changes": parities[i], "clothes_code": [round(float(v), 4) for v in code]})
    ident = {"fps": FPS, "click_by": click_by, "runs": runs}
    if stage_check is not None:
        ident["clothes"] = {"check": stage_check}
    (tmp_path / "identity.json").write_text(json.dumps(ident), encoding="utf-8")
    vo = video_outfit or {}

    def grab(video, t):
        i = int(round(t * FPS)) // 100
        return person(vo.get(i, outfits[i]), lights[i], x=300, y=80, h=240, rng=np.random.default_rng(i))[0]

    def runs_gen(pl, sk, court=None, with_sel=False):
        for i in range(n):
            run = np.arange(i * RUN_LEN, (i + 1) * RUN_LEN)
            yield run, np.zeros((RUN_LEN, 17, 2)), np.ones((RUN_LEN, 17)), 240.0, np.zeros(4), np.zeros(RUN_LEN, int)
    return grab, runs_gen


def _patch(monkeypatch, grab, runs_gen):
    import tennisbio.stages as stages
    monkeypatch.setattr(stages, "grab_frame", grab)
    monkeypatch.setattr(stages, "near_runs", runs_gen)


def _run_of(p):
    return int(round(p["t"] * FPS)) // 100


def test_each_photo_is_checked_against_its_group(tmp_path, monkeypatch):
    """Two outfits; in run 0 (group 0) the video frame shows the other player (the track switched): its photo
    is not chosen, the photo of group 0 is a run whose frame looks like group 0."""
    outfits = ["A"] * 4 + ["B"] * 4
    grab, gen = _match(tmp_path, outfits, [1.0, 0.9, 1.1, 1.0, 1.0, 0.9, 1.1, 1.0], [0] * 4 + [1] * 4,
                       [0] * 4 + [1] * 4, video_outfit={0: "B"})
    _patch(monkeypatch, grab, gen)
    res = ic.photo_set(tmp_path, tmp_path / "v.mp4", n_try=4)
    assert res["by"] == "clothes" and res["check"]["distinguishable"] is True and res["check"]["verified"]
    assert res["check"]["photo_dist"] > 0.3
    p0, p1 = res["photos"]
    assert p0["cluster"] == 0 and _run_of(p0) in (1, 2, 3) and p1["cluster"] == 1 and _run_of(p1) >= 4
    assert all(Path(p["path"]).exists() for p in res["photos"])
    assert ic.photos(tmp_path, tmp_path / "v.mp4") == res["photos"]          # cached
    # with only run 0 to choose from, group 0's photo looks like the other group: not distinguishable, and the
    # photos go by the end changes
    (tmp_path / "identidad_fotos" / "fotos.json").unlink()
    ident = json.loads((tmp_path / "identity.json").read_text())
    for r in ident["runs"][1:4]:
        r["cluster"] = -1
    (tmp_path / "identity.json").write_text(json.dumps(ident))
    res = ic.photo_set(tmp_path, tmp_path / "v.mp4", n_try=4)
    assert res["check"]["distinguishable"] is False and "otro grupo" in res["check"]["why"]
    assert res["by"] == "ends" and [p["group_by"] for p in res["photos"]] == ["ends", "ends"]


def test_two_photos_of_the_same_white_dress_are_not_asked(tmp_path, monkeypatch):
    """The v8 identity.json of Rybakina–Pegula: clothes groups by the light, no check in the stage. The photos'
    own clothes are alike: the photos are taken by the end changes, marked «no distinguibles»."""
    lights = [0.6, 0.6, 1.3, 1.3, 0.6, 1.3, 0.6, 1.3]
    clusters = [0 if li < 1 else 1 for li in lights]
    parities = [0, 1, 0, 1, 1, 0, 0, 1]
    grab, gen = _match(tmp_path, ["B"] * 8, lights, clusters, parities)
    ident = json.loads((tmp_path / "identity.json").read_text())
    del ident["click_by"]
    (tmp_path / "identity.json").write_text(json.dumps(ident))
    _patch(monkeypatch, grab, gen)
    res = ic.photo_set(tmp_path, tmp_path / "v.mp4")
    assert res["check"]["distinguishable"] is False and res["check"]["photo_dist"] < ic.PHOTO_MIN_DIST
    assert "casi igual" in res["check"]["why"] and res["by"] == "ends"
    assert {p["cluster"] for p in res["photos"]} == {0, 1}
    assert {parities[_run_of(p)] for p in res["photos"]} == {0, 1}
    # the click on one of them is saved with how the photos were grouped, and applied by the end changes
    pick = ic.save_pick(tmp_path, res["photos"][1]["t"])
    assert pick["by"] == "ends"
    out, why = apply_pick(ident, pick)
    assert why["by"] == "ends" and why["her_parity"] == 1
    assert [r["near_is_target"] for r in out["runs"]] == [p == 1 for p in parities]


def test_no_click_when_the_clothes_are_alike_and_there_are_no_end_changes(tmp_path, monkeypatch):
    grab, gen = _match(tmp_path, ["B"] * 6, [0.6, 1.3] * 3, [0, 1] * 3, [None] * 6, click_by=None,
                       stage_check={"distinguishable": False, "why": "la ropa típica de los dos grupos es casi igual"})
    _patch(monkeypatch, grab, gen)
    assert ic.state(tmp_path)["possible"] is False
    assert ic.stage_check(tmp_path)["distinguishable"] is False
    res = ic.photo_set(tmp_path, tmp_path / "v.mp4")
    assert res["photos"] == [] and res["by"] is None and res["check"]["distinguishable"] is False


def test_the_photo_cache_follows_identity_json(tmp_path, monkeypatch):
    """Until 09-11 a photo once written was never redone, even after the identity changed."""
    grab, gen = _match(tmp_path, ["A", "A", "B", "B"], [1.0] * 4, [0, 0, 1, 1], [0, 0, 1, 1])
    _patch(monkeypatch, grab, gen)
    (tmp_path / "identidad_fotos").mkdir()
    (tmp_path / "identidad_fotos" / "0.jpg").write_bytes(b"old")            # a photo of an older identity
    res = ic.photo_set(tmp_path, tmp_path / "v.mp4")
    assert (tmp_path / "identidad_fotos" / "0.jpg").read_bytes() != b"old"
    assert ic.cached(tmp_path) == res
    ident = json.loads((tmp_path / "identity.json").read_text())
    ident["runs"][0]["clothes_margin"] = 0.3
    (tmp_path / "identity.json").write_text(json.dumps(ident))
    assert ic.cached(tmp_path) is None


def test_distance_between_two_white_photos_is_below_the_threshold():
    rng = np.random.default_rng(9)
    w1, w2 = _code("B", 0.6, rng, 1), _code("B", 1.3, rng, 1)
    a = _code("A", 1.0, rng, 1)
    assert clothes_distances(w1[None], w2[None])[0, 0] < ic.PHOTO_MIN_DIST < clothes_distances(w1[None], a[None])[0, 0]


def test_prepare_marks_photos_not_distinguishable(tmp_path, monkeypatch):
    from types import SimpleNamespace
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import identity_prepare as IP

    d = tmp_path / "out" / "m"
    d.mkdir(parents=True)
    img = tmp_path / "x.jpg"
    img.write_bytes(b"jpg")
    monkeypatch.setattr(IP, "load_config", lambda: {"paths": {"output": str(tmp_path / "out")}})
    monkeypatch.setattr(IP, "load_matches", lambda cfg: [SimpleNamespace(id="m", video=str(tmp_path / "v.mp4"))])
    import tennisbio.layout as layout
    monkeypatch.setattr(layout, "dir_of", lambda root, m, cfg=None: d)
    monkeypatch.setattr(IP.ic, "state", lambda d: {"possible": True, "done": False, "pick": None})
    monkeypatch.setattr(IP.ic, "photo_set", lambda d, v: {
        "photos": [{"cluster": 0, "t": 1.0, "path": str(img)}, {"cluster": 1, "t": 2.0, "path": str(img)}],
        "by": "ends", "check": {"distinguishable": False, "why": "la ropa de las dos fotos es casi igual", "photo_dist": 0.03}})
    monkeypatch.setattr(IP.pipeline, "run", lambda ctx, stages: None)
    monkeypatch.setattr(IP.pipeline, "Context", lambda m, cfg, d, log=None: SimpleNamespace(dir=d))
    monkeypatch.setattr(sys, "argv", ["identity_prepare", str(tmp_path / "fotos")])
    IP.main()
    st = json.loads((tmp_path / "fotos" / "estado.json").read_text(encoding="utf-8"))["m"]
    assert st["fotos"] == "fotos no distinguibles" and st["fotos_por"] == "cambios de lado del marcador"
    assert st["listo"] and st["distancia_fotos"] == 0.03 and "casi igual" in st["motivo"]
