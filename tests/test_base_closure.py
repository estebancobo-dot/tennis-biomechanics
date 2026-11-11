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
        "  [ok] Derecha de Elena Rybakina actualizada: 318 ✔, 28 ✘.\nduracion total: 60.5 min; termina 2026-11-11T13:28:01\n",
        encoding="utf-8")
    it = new_match_item([tmp_path])
    assert it["name"] == NEW_MATCH_ITEM and it["status"] == "ok" and "60.5 min" in it["detail"]
    (tmp_path / "prueba_app_nuevo.log").write_text("  [ok] x\ntermina 2026-11-08T13:28:01\n", encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "aviso"          # made with older code
    (tmp_path / "prueba_app_nuevo.log").write_text(
        "  hecho     #2 informe partido x analizado FALLOS\n  hecho     #1 partido partido nuevo\n"
        "  x: identidad dudosa — Identidad dudosa: decidida en el 0 % de los planos\n"
        "duracion total: 115.6 min; termina 2026-11-11T19:27:39\n", encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "falta"          # another player's match: not a pass
    (tmp_path / "prueba_app_nuevo.log").write_text("Traceback (most recent call last):\n", encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "falta"


def test_the_new_match_is_judged_by_its_own_checks(tmp_path):
    # 11-11 (R6): request 207 said «FALLOS» for 32 checks: 20 requests outside the Base, the PC's logs, the test itself
    import json
    from tennisbio.audit import new_match_item
    log = ("  hecho     #2 informe partido prueba-app-35m analizado FALLOS · versión 1 · al día\n"
           "  hecho     #1 partido partido nuevo \n  [ok] Derecha de Elena Rybakina actualizada: 356 ✔, 32 ✘.\n"
           "duracion total: 79.1 min; termina 2026-11-11T20:54:10\n")
    (tmp_path / "prueba_app_nuevo.log").write_text(log, encoding="utf-8")
    aud = tmp_path / "_app_nuevo" / "output" / "analisis" / "rybakina_forehand" / "actual" / "auditoria"
    aud.mkdir(parents=True)
    items = [{"area": "Peticiones", "name": "#176 Nuevo split step", "status": "falta"},
             {"area": "Infraestructura", "name": "Registros con fecha y duración", "status": "falta"},
             {"area": "Fases", "name": "Fotograma clave: inicio de preparación", "status": "falta"},
             {"area": "Ficheros", "name": "Partido prueba-app-35m: salida de cada etapa, ventanas y series", "status": "ok"}]
    (aud / "auditoria.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "ok"
    items[3]["status"] = "falta"
    items[3]["detail"] = "faltan o están vacíos: fine/strokes.json"
    (aud / "auditoria.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    it = new_match_item([tmp_path])
    assert it["status"] == "falta" and "fine/strokes.json" in it["detail"]
