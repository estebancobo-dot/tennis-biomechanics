"""The court surface of each stroke: from the catalogue entry of the video (also for test runs), the
command line or the names, written on every stroke and shown on the stroke screen."""
import json
from pathlib import Path

import pytest

from tennisbio.catalog import Match, Player, catalog_entry, save_test_info, trial_match

VIDEO = "Теннис.ЮСИПОПЕН.Финал.Соболенко—Рыбакина.12.09.2026.1080р.50fps.Мосгортранс.mkv"


@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "config"
    (d / "players").mkdir(parents=True)
    (d / "players" / "rybakina.yaml").write_text("name: Elena Rybakina\nhand: right\nheight_m: 1.84\n", encoding="utf-8")
    (d / "matches.yaml").write_text(
        "matches:\n"
        "  - id: 2026-uso-f\n"
        f"    video: {VIDEO}\n"
        "    player: rybakina\n"
        "    opponent: Aryna Sabalenka\n"
        "    tournament: US Open\n"
        "    date: 2026-09-12\n"
        "    surface: dura (Laykold)\n"
        "    round: F\n"
        "    opponent_id: sabalenka\n", encoding="utf-8")
    return d


def _player():
    return Player("rybakina", "Elena Rybakina")


def test_test_run_takes_the_catalogue_entry_of_its_video(config_dir, tmp_path):
    cfg = {"paths": {"videos": str(tmp_path)}}
    m = trial_match("smoke_x", tmp_path / "clip.mkv", _player(), cfg, source=Path("C:/tenis/videos") / VIDEO,
                   config_dir=config_dir)
    assert m.surface == "dura (Laykold)" and m.opponent == "Aryna Sabalenka" and m.round == "F"
    assert m.extra.get("opponent_id") == "sabalenka"
    # recomputing later knows only the folder name (smoke_<ascii of the video name, 40>)
    e = catalog_entry(cfg, match_id="smoke_tennis-yusipopen-final-sobolenko-rybakin", config_dir=config_dir)
    assert e is not None and e.id == "2026-uso-f"
    # the command line wins (the rival as the scoreboard writes it)
    m = trial_match("smoke_x", tmp_path / "clip.mkv", _player(), cfg, source=Path(VIDEO), config_dir=config_dir,
                   opponent="SABALENKA", surface="")
    assert m.opponent == "SABALENKA" and m.surface == "dura (Laykold)"


def test_without_catalogue_the_command_line_or_the_name(tmp_path):
    empty = tmp_path / "nocfg"
    empty.mkdir()
    cfg = {"paths": {"videos": str(tmp_path)}}
    assert catalog_entry(cfg, source_name=VIDEO, config_dir=empty) is None
    # the name of the video says US Open (transliterated): hard court
    m = trial_match("smoke_tennis-yusipopen-final-sobolenko-rybakin", tmp_path / "c.mkv", _player(), cfg,
                   source=Path(VIDEO), config_dir=empty)
    assert m.surface == "dura"
    # a name that says nothing: only the command line gives it; it is remembered for recomputing
    d = tmp_path / "out" / "smoke_partido"
    m = trial_match("smoke_partido", tmp_path / "partido_0_4m.mp4", _player(), cfg, source=Path("partido.mp4"),
                   config_dir=empty, surface="tierra batida")
    assert m.surface == "tierra batida"
    save_test_info(m, d)
    again = trial_match("smoke_partido", tmp_path / "partido_0_4m.mp4", _player(), cfg, match_dir=d, config_dir=empty)
    assert again.surface == "tierra batida"
    assert trial_match("smoke_partido", tmp_path / "p.mp4", _player(), cfg, config_dir=empty).surface == ""


def test_broken_catalogue_or_saved_file_never_stops_a_test_run(tmp_path):
    bad = tmp_path / "bad"
    (bad / "players").mkdir(parents=True)
    (bad / "matches.yaml").write_text("matches:\n  - id: x\n    video: v.mp4\n    player: nobody\n", encoding="utf-8")
    cfg = {"paths": {"videos": str(tmp_path)}}
    assert catalog_entry(cfg, source_name="v.mp4", config_dir=bad) is None          # missing player profile
    d = tmp_path / "m"
    d.mkdir()
    (d / "partido.json").write_text("{roto", encoding="utf-8")
    m = trial_match("m", tmp_path / "v.mp4", _player(), cfg, match_dir=d, config_dir=bad)
    assert m.surface == "" and m.opponent == ""
    (d / "partido.json").write_text(json.dumps(["no es un objeto"]), encoding="utf-8")
    assert trial_match("m", tmp_path / "v.mp4", _player(), cfg, match_dir=d, config_dir=bad).surface == ""


def test_surface_reaches_the_stroke_screen_and_the_audit():
    from tennisbio.audit import planned_keys, shown_keys, stroke_values
    from tennisbio.report import stroke_record

    s = {"stroke": "forehand", "match_time_s": 5.0, "review": [], "metrics": {}, "phases": {}, "surface": "dura"}
    r = stroke_record(s, 0, Match("m1", None, Player("p", "P")), 60.0, 0)
    assert r["surface"] == "dura"
    assert stroke_values(s)["surface"] == "dura"
    assert "surface" in planned_keys()
    assert "surface" in shown_keys({"strokes": [r]})
    assert "surface" not in shown_keys({"strokes": [{**r, "surface": None}]})
