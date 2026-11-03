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


def test_module_items_from_the_pc_junit(tmp_path):
    """Requests checked by their own tests run on the PC: one item per module, from pytest's JUnit XML."""
    from tennisbio.audit import PETITIONS, module_tests_items

    x = tmp_path / "pruebas.xml"
    x.write_text('<?xml version="1.0"?><testsuites><testsuite>'
                 '<testcase classname="tests.test_library" name="test_a"/>'
                 '<testcase classname="tests.test_library" name="test_b"><failure message="x"/></testcase>'
                 '<testcase classname="tests.test_layout" name="test_c"/>'
                 '<testcase classname="tests.test_layout" name="test_d"><skipped/></testcase>'
                 '</testsuite></testsuites>', encoding="utf-8")
    items = {i["name"].split(": ")[1]: i for i in module_tests_items(x)}
    assert items["test_library"]["status"] == "falta" and "test_b" in items["test_library"]["detail"]
    assert items["test_layout"]["status"] == "ok" and items["test_app_core"]["status"] == "aviso"
    assert module_tests_items(None)[0]["status"] == "aviso"
    assert "test_library" in PETITIONS[220] and "test_auto_catalog_rename" in PETITIONS[229]
