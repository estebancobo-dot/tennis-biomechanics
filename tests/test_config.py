from tennisbio.config import load_config


def test_local_overrides_default(tmp_path):
    (tmp_path / "default.yaml").write_text("device: dml\ncheap_pass: {width: 640, fps: 10}\n")
    (tmp_path / "local.yaml").write_text("cheap_pass: {fps: 5}\n")
    cfg = load_config(tmp_path)
    assert cfg["device"] == "dml"
    assert cfg["cheap_pass"] == {"width": 640, "fps": 5}


def test_ascii_ids_for_any_file_name():
    from tennisbio.catalog import ascii_id
    assert ascii_id("Теннис.Финал.Соболенко—Рыбакина.2026") == "tennis-final-sobolenko-rybakina-2026"
    assert ascii_id("Rybakina vs Świątek 'fín'") == "rybakina-vs-swiatek-fin"
    assert ascii_id("———") == "partido"
