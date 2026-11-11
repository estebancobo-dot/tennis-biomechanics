import sqlite3

from tennisbio.audit import MATCH_LIST_ITEM, match_list_item


def _db(base, rows):
    (base / "datos").mkdir(parents=True)
    con = sqlite3.connect(base / "datos" / "tennisbio.db")
    con.execute("CREATE TABLE matches (id TEXT PRIMARY KEY, tournament TEXT, date TEXT, round TEXT, opponent TEXT, state TEXT)")
    con.executemany("INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()


def test_the_real_registry_of_11_11_fails(tmp_path):
    _db(tmp_path, [("us-open-2026-r4-naomi-osaka-elena-rybakina", "", "", "", "", "nuevo"),
                   ("zheng-qinwen-elena-rybakina", "", "", "", "", "nuevo"),
                   ("_smoke:x", "", "", "", "", "nuevo")])                     # a test run does not count
    it = match_list_item([tmp_path])
    assert it["name"] == MATCH_LIST_ITEM and it["status"] == "falta" and "sin rival: 2" in it["detail"]


def test_complete_rows_pass_and_archived_ones_do_not_count(tmp_path):
    _db(tmp_path, [("a", "US Open", "2026-09-01", "R4", "Naomi Osaka", "analizado"), ("b", "", "", "", "", "archivado")])
    assert match_list_item([tmp_path])["status"] == "ok"
    assert match_list_item([tmp_path / "nada"])["status"] == "aviso"
