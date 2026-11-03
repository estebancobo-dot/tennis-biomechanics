"""The code's tests run on the PC (scripts/windows/pruebas_fondo.ps1) and read by the audit."""
from tennisbio.audit import code_tests_item


def test_reads_the_pc_test_log(tmp_path):
    f = tmp_path / "pruebas.log"
    f.write_text("\ufeffcommit: abc1234\ninicio: 2026-11-03T01:00:00\nfin: 2026-11-03T01:14:00\ncodigo: 0\n"
                 "....\n707 passed, 1 skipped in 600s\n", encoding="utf-8")
    it = code_tests_item(f)
    assert it["status"] == "ok" and it["passed"] == 707 and "abc1234" in it["detail"]
    f.write_text("commit: abc\ncodigo: 1\nFAILED tests/test_x.py::test_y - boom\n1 failed, 706 passed\n", encoding="utf-8")
    it = code_tests_item(f)
    assert it["status"] == "falta" and "tests/test_x.py::test_y" in it["detail"]
    f.write_text("commit: abc\ncodigo: cortado a los 40 min\n", encoding="utf-8")
    assert code_tests_item(f)["status"] == "falta"
    assert code_tests_item(None)["status"] == "aviso"
