"""#305 (15-11): the mockup's validation (design/p0/validar_maqueta.py), on small made-up screens."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "design" / "p0"))

import validar_maqueta as vm  # noqa: E402


def test_matrix_rows_read_state_and_keys():
    md = ("## 1. Fases\n\n| Evento | Estado | Implementación |\n|---|---|---|\n| Impacto | ✔ | audio y bola |\n"
          "## 2. Cuerpo\n\n| Elemento | Fuente | Estado | Implementación |\n|---|---|---|---|\n"
          "| Giro de hombros | TA | ◐ | `loaded.shoulder_turn`, `hip_turn` (2D) |\n| Mirada | Lafont | ✘ | no medible |\n")
    rows = vm.matrix_rows(md)
    assert [(r["seccion"], r["estado"]) for r in rows] == [("1", "✔"), ("2", "◐"), ("2", "✘")]
    assert rows[1]["claves"] == ["loaded.shoulder_turn", "hip_turn"]


def test_a_measure_counts_only_when_its_name_is_on_screen():
    checks = {"loaded.shoulder_turn": "Giro de hombros", "ready.base_width": "Base en la espera"}
    assert vm.key_hits(["shoulder_turn"], checks) == ["loaded.shoulder_turn"]
    rows = [{"seccion": "2", "elemento": "Giro de hombros", "estado": "◐", "claves": ["shoulder_turn"]},
            {"seccion": "2", "elemento": "Anchura de la base en la espera", "estado": "✔", "claves": ["base_width"]},
            {"seccion": "6", "elemento": "Mirada al contacto", "estado": "✘", "claves": []}]
    states = {"leccion_fase_2": "Armado · Giro de hombros · 300 golpes", "leccion/Glosario": "Base en la espera: …"}
    res = vm.check_matrix(rows, states, checks, not_tv="Mirada y contacto visual: no se ve desde la tele")
    assert [r["resultado"] for r in res] == ["en_maqueta", "falta", "dicho"]   # the glossary is not a measure shown
    assert res[2]["fuente"] == "lista15"


def test_items_any_all_negated_and_planned():
    st = {"leccion_fase_0": "Bola rápida 12 · Bola lenta 9", "golpe": "Sus pies · Cerrar", "inicio": "nada"}
    items = [{"id": "a", "fuente": "ux", "texto": "", "busca": ["rápida", "lenta"], "todos": True, "en": ["leccion"]},
             {"id": "b", "fuente": "ux", "texto": "", "busca": ["rápida"], "en": ["golpe"]},
             {"id": "c", "fuente": "requisitos", "texto": "", "busca": ["puntuación"], "niega": True},
             {"id": "d", "fuente": "patrones", "texto": "", "busca": ["muñeco"], "tipo": "hueco", "paquete": "P4"}]
    assert [r["resultado"] for r in vm.check_items(items, st)] == ["en_maqueta", "falta", "en_maqueta", "hueco"]


def test_lesson_sections_are_screens_of_their_own():
    walk = {"estados": {"leccion_fase_0": "Fase 1 · Espera\nLo esencial\nA\nGlosario (2 términos)\nX: y",
                        "inicio": "Hola"},
            "a_la_vista": {"leccion_fase_0": "Fase 1 · Espera\nLo esencial\nGlosario (2 términos)", "inicio": "Hola"}}
    s = vm.screens(walk)
    assert s["leccion_fase_0"].startswith("Fase 1") and "X: y" not in s["leccion_fase_0"]
    assert s["leccion/Glosario"].startswith("Glosario") and "X: y" in s["leccion/Glosario"]


def test_the_real_checklist_and_catalogue_agree():
    import yaml
    cfg = yaml.safe_load((ROOT / "design" / "p0" / "cobertura_maqueta.yaml").read_text(encoding="utf-8"))
    refs = yaml.safe_load((ROOT / "config" / "referencias.yaml").read_text(encoding="utf-8"))
    ids = [i["id"] for i in cfg["items"]]
    assert len(ids) == len(set(ids)) and all(i["fuente"] in cfg["fuentes"] or i["fuente"] == "patrones" for i in cfg["items"])
    assert vm.check_patterns(refs, cfg["items"]) == []          # every adopted or planned pattern is looked for
    assert len(refs["referencias"]) >= 15 and all(p in refs["patrones"] for r in refs["referencias"] for p in r["patrones"])


def test_a_placeholder_is_not_the_media_it_announces():
    """15-11: «esqueleto» beside a marked placeholder counted as the video with its layers; an item that is media needs
    a real video or canvas on the screen where it is found."""
    st = {"golpe": "Vídeo real del golpe con capas · Capas: Cuerpo Raqueta Bola"}
    it = [{"id": "P.video_capas", "fuente": "patrones", "texto": "", "busca": ["capas"], "en": ["golpe"], "medio": True}]
    assert vm.check_items(it, st, {"golpe": 0})[0]["resultado"] == "falta"
    assert vm.check_items(it, st, {"golpe": 1})[0]["resultado"] == "en_maqueta"
