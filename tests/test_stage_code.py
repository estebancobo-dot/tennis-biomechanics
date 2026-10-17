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
