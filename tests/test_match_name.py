from tennisbio.match_name import parse

R = ("Elena Rybakina", "rybakina")


def test_the_six_videos_of_the_pc():
    # 11-11 (R6, #226): the names of the PC's videos (prueba_completo.log); the registry had none of this
    p = parse("US Open 2026.R4.Naomi Osaka - Elena Rybakina", *R)
    assert (p["tournament"], p["date"], p["round"], p["opponent"]) == ("US Open", "2026", "R4", "Naomi Osaka")
    p = parse("Elena Rybakina - Jessica Pegula - Miami - 2026 - Quarter final", *R)
    assert (p["tournament"], p["date"], p["round"], p["opponent"]) == ("Miami", "2026", "QF", "Jessica Pegula")
    p = parse("Zheng Qinwen - Elena Rybakina", *R)
    assert (p["tournament"], p["date"], p["round"], p["opponent"]) == ("", "", "", "Zheng Qinwen")
    p = parse("Zverev Alexander - Sinner Jannik - Indian Wells - 2026 - Semi final", "Jannik Sinner", "sinner")
    assert (p["tournament"], p["date"], p["round"], p["opponent"]) == ("Indian Wells", "2026", "SF", "Zverev Alexander")
    p = parse("Теннис.ЮСИПОПЕН.Полуфинал.Гауфф—Рыбакина.10.09.2026.1080р.50fps.Мосгортранс", *R)
    assert (p["tournament"], p["date"], p["round"], p["opponent"]) == ("US Open", "2026-09-10", "SF", "Gauff")
    p = parse("Теннис.ЮСИПОПЕН.Финал.Соболенко—Рыбакина.12.09.2026.1080р.50fps.Мосгортранс", *R)
    assert (p["tournament"], p["date"], p["round"], p["opponent"]) == ("US Open", "2026-09-12", "F", "Sobolenko")


def test_nothing_is_invented():
    p = parse("prueba_app_35m", *R)
    assert p == {"tournament": "", "date": "", "round": "", "players": [], "opponent": ""}
    assert parse("Rybakina entrenamiento 1080p", *R)["opponent"] == ""        # one name only: no rival


def test_the_catalogue_fills_only_what_is_empty(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("auto_catalog", Path(__file__).resolve().parents[1] / "scripts" / "auto_catalog.py")
    ac = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ac)
    (tmp_path / "players").mkdir()
    (tmp_path / "players" / "rybakina.yaml").write_text("name: Elena Rybakina\n", encoding="utf-8")
    es = [{"id": "a", "video": "US Open 2026.R4.Naomi Osaka - Elena Rybakina.ts", "player": "rybakina"},
          {"id": "b", "video": "Zheng Qinwen - Elena Rybakina.mkv", "player": "rybakina", "opponent": "Qinwen Zheng"}]
    filled = ac.fill_from_names(es, tmp_path)
    assert es[0]["opponent"] == "Naomi Osaka" and es[0]["round"] == "R4" and es[0]["date"] == "2026"
    assert es[1]["opponent"] == "Qinwen Zheng" and "tournament" not in es[1]        # written by hand: kept; nothing else said
    assert filled == ["a: opponent, tournament, date, round"]
