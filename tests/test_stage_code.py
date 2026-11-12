"""A stage without a code fingerprint cannot change its code without a new version (or a declared
change that does not alter its results): otherwise old results would pass for new ones."""
from tennisbio.stage_code import check, stage_code, REGISTRY


def test_stage_code_changes_come_with_a_version():
    assert REGISTRY.exists()
    assert not check(), check()


def test_registry_covers_every_stage_without_code_fingerprint():
    import json

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert set(stage_code()) <= set(reg)


def test_a_change_in_a_helper_the_stage_calls_counts_as_its_code():
    """12-11: the candidates stage calls add_serve_candidates, which uses point_count.her_serve_points; before, only the
    stage's own function and its own imports counted, so editing the helper left old candidates passing for new ones."""
    from tennisbio.stage_code import ROOT
    src = (ROOT / "stages.py").read_text(encoding="utf-8")
    base = stage_code(src)
    assert "point_count" in base["candidates"]["modules"]
    edited = src.replace("def add_serve_candidates(cands: list[dict], score: dict, identity: dict, fps: float) -> int:\n",
                         "def add_serve_candidates(cands: list[dict], score: dict, identity: dict, fps: float) -> int:\n"
                         "    fps = fps * 1.0\n", 1)
    assert edited != src
    new = stage_code(edited)
    assert new["candidates"]["hash"] != base["candidates"]["hash"]
    assert new["court"]["hash"] == base["court"]["hash"]          # a stage that does not reach it stays as it was
