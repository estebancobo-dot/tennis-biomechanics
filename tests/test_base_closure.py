from tennisbio.real_status import closed, main_test


def _it(name, status="ok"):
    return {"name": name, "status": status}


def test_main_test_needs_every_matching_item_ok_and_every_pattern_measured():
    items = [_it("Tiempo: a"), _it("Tiempo: b", "aviso"), _it("Exportación terminada: x")]
    assert main_test(["^Exportación"], items) == ("ok", [])
    st, bad = main_test(["^Tiempo: "], items)
    assert st == "falla" and bad == ["Tiempo: b: aviso"]
    st, bad = main_test(["^Exportación", "^Aplicación: un partido nuevo"], items)
    assert st == "falla" and bad == ["Aplicación: un partido nuevo: sin medir"]
    assert main_test(["^Nada"], items)[0] == "sin medir"
    assert main_test(["^Exportación", "?^Etapas con errores"], items) == ("ok", [])     # written only when failing
    assert main_test(["?^Etapas con errores"], items + [_it("Etapas con errores", "falta")])[0] == "falla"


def test_a_package_is_closed_only_with_its_test_and_all_its_requests_checked():
    assert closed([3, 4, 3], "ok")
    assert not closed([3, 2], "ok")            # one request fails its check
    assert not closed([3, 3], "falla")         # the main test fails
    assert not closed([3, 3], "sin medir")
    assert not closed([], "ok")


def test_the_real_plan_gives_every_base_package_a_main_test():
    from tennisbio.real_status import packages
    pk = packages()
    assert all(pk[k].get("prueba") for k in ("B1", "B2", "B3", "B4", "B5", "B6", "B7"))


def test_new_match_item_reads_the_app_new_log(tmp_path):
    from tennisbio.audit import NEW_MATCH_ITEM, new_match_item
    assert new_match_item([tmp_path])["status"] == "aviso"
    (tmp_path / "prueba_app_nuevo.log").write_text(
        "  [ok] Derecha de Elena Rybakina actualizada: 318 ✔, 28 ✘.\nduracion total: 60.5 min; termina 2026-11-08T13:28:01\n",
        encoding="utf-8")
    it = new_match_item([tmp_path])
    assert it["name"] == NEW_MATCH_ITEM and it["status"] == "ok" and "60.5 min" in it["detail"]
    (tmp_path / "prueba_app_nuevo.log").write_text("  [ok] x\ntermina 2026-11-04T13:28:01\n", encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "aviso"          # made with older code
    (tmp_path / "prueba_app_nuevo.log").write_text("Traceback (most recent call last):\n", encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "falta"
