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


def test_surface_from_tournament_or_file_name():
    from pathlib import Path

    from tennisbio.catalog import Match, Player, surface_of
    assert surface_of("Теннис. ЮС Опен. Финал") == "dura"
    assert surface_of("smoke_tennis-yusipopen-final-sobolenko-rybakin") == "dura"
    assert surface_of("Wimbledon 2022 final") == "hierba" and surface_of("Roland Garros R16") == "tierra batida"
    assert surface_of("partido sin nombre") == ""
    assert Match("m", Path("x/Madrid QF.mp4"), Player("p", "P")).surface == "tierra batida"
    assert Match("m", Path("x.mp4"), Player("p", "P"), surface="dura cubierta").surface == "dura cubierta"   # never overwritten
