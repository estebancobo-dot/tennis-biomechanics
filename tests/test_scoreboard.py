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
