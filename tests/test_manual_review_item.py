import sqlite3

from tennisbio.audit import MANUAL_REVIEW_ITEM, manual_review_item


def _db(base, jobs):
    (base / "datos").mkdir(parents=True)
    con = sqlite3.connect(base / "datos" / "tennisbio.db")
    con.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, kind TEXT, match TEXT, reason TEXT, state TEXT)")
    con.executemany("INSERT INTO jobs (kind, match, reason, state) VALUES (?, ?, ?, ?)", jobs)
    con.commit()
    con.close()


def test_a_job_waiting_for_the_user_fails_the_check(tmp_path):
    _db(tmp_path, [("partido", "m1", "nueva versión de la pasada fina", "por confirmar"), ("partido", "m2", "x", "hecho")])
    it = manual_review_item([tmp_path])
    assert it["name"] == MANUAL_REVIEW_ITEM and it["status"] == "aviso" and "1 trabajos esperan" in it["detail"]


def test_nothing_waiting_passes_and_no_index_is_not_a_pass(tmp_path):
    _db(tmp_path / "a", [("partido", "m1", "x", "hecho"), ("informe", None, "y", "pendiente")])
    assert manual_review_item([tmp_path / "a"])["status"] == "ok"
    assert manual_review_item([tmp_path / "nada"])["status"] == "aviso"
