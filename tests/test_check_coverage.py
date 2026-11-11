import json

from tennisbio.check_coverage import compare, coverage_item, norm, recorded


def _it(area, name, status="ok"):
    return {"area": area, "name": name, "status": status}


def test_kinds_without_a_failing_test_are_found_and_main_ones_named():
    items = [_it("Rendimiento", "Tiempo: partido_1"), _it("Rendimiento", "Tiempo: partido_2"),
             _it("Golpes", "Volumen: forehand"), _it("Vídeo", "Cada golpe tiene su vídeo")]
    rec = {("Rendimiento", "Tiempo"): {"ok"}, ("Golpes", "Volumen"): {"ok", "aviso"}}
    c = compare(items, rec, [r"^Tiempo: "])
    assert c["kinds"] == 3 and norm("Tiempo: partido_1") == "Tiempo"
    assert norm("Partido sin-fecha_49723c_rybakina: salida de cada etapa") == norm("Partido x: salida de cada etapa")
    assert c["no_test"] == [("Vídeo", "Cada golpe tiene su vídeo")]
    assert c["never_fail"] == [("Rendimiento", "Tiempo")]
    assert c["main"] == [("Rendimiento", "Tiempo")]


def test_the_audit_item_fails_while_a_main_check_cannot_fail_and_says_when_there_is_no_record(tmp_path):
    items = [_it("Rendimiento", "Tiempo desde cero"), _it("Golpes", "Volumen: forehand")]
    assert coverage_item(items, [tmp_path])["status"] == "aviso"                    # no record of the tests
    d = tmp_path / "comprobaciones_pruebas"
    d.mkdir()
    (d / "rec_gw0.json").write_text(json.dumps([["Rendimiento", "Tiempo desde cero", "ok"], ["Golpes", "Volumen", "aviso"]]),
                                    encoding="utf-8")
    assert recorded(d)[("Rendimiento", "Tiempo desde cero")] == {"ok"}
    it = coverage_item(items, [tmp_path])
    assert it["status"] == "aviso" and "Tiempo desde cero" in it["detail"]          # it is in B1's main test
    (d / "rec_gw1.json").write_text(json.dumps([["Rendimiento", "Tiempo desde cero", "aviso"]]), encoding="utf-8")
    assert coverage_item(items, [tmp_path])["status"] == "ok"
