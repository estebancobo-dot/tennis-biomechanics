"""Package B4 (08-11): #23, #155, #205, #218 and #219 checked on the outputs by their own audit items, not by a note
or by a check of something else."""
import json

from tennisbio import audit as A
from tennisbio import real_status

# the identity stage's summary of 584c5b on the PC (pc-logs, partidos/bib_sin-fecha_584c5b_rybakina_manifest.json, 08-11)
SUMM = {"runs": 276, "agree": 240, "ends_only": 10, "clothes_only": 9, "ends_won": 1, "clothes_won": 14, "doubtful": 2,
        "none": 0, "decided": 274, "clothes": {"same_game_same": 1.0}}


def test_identity_across_ends_ok_with_both_cues_and_strokes_at_both_ends():
    it = A.identity_item("m", SUMM, (180, 106))
    assert it["status"] == "ok", it["detail"]
    assert "240 de 257" in it["detail"] and "180 cerca y 106 lejos" in it["detail"]


def test_identity_warns_when_undecided_cues_disagree_or_she_is_only_at_one_end():
    assert A.identity_item("m", {**SUMM, "decided": 250}, (180, 106))["status"] == "aviso"          # 91 % decided
    assert A.identity_item("m", {**SUMM, "agree": 150}, (180, 106))["status"] == "aviso"            # cues disagree
    assert A.identity_item("m", {**SUMM, "clothes": {"same_game_same": 0.8}}, (180, 106))["status"] == "aviso"
    it = A.identity_item("m", SUMM, (280, 6))                     # lost when she goes to the far end
    assert it["status"] == "aviso" and "golpes en un lado" in it["detail"]
    assert A.identity_item("m", None, (180, 106))["status"] == "aviso"
    assert A.identity_item("m", SUMM, None)["status"] == "aviso"


def test_sides_from_the_item_fields_or_its_text():
    assert A._sides_of({"near": 3, "far": 2}) == (3, 2)
    assert A._sides_of({"detail": "... de su saque) (90 cerca, 79 lejos); además 4 de identidad dudosa"}) == (90, 79)
    assert A._sides_of(None) is None


def test_far_end_counted_confirmed_and_measured():
    fine = {"candidates": 289, "confirmed": 286}
    far = [{"side": "far", "court_pos_m": [1.0, 2.0]}] * 9 + [{"side": "far"}]
    assert A.far_end_item("m", (180, 106), fine, far)["status"] == "ok"
    assert A.far_end_item("m", (280, 6), fine, far)["status"] == "aviso"                  # far strokes lost
    assert A.far_end_item("m", (180, 106), {"candidates": 289, "confirmed": 200}, far)["status"] == "aviso"
    assert A.far_end_item("m", (180, 106), fine, far, far_candidates=200)["status"] == "aviso"   # far ones discarded
    assert A.far_end_item("m", (180, 106), fine, [{"side": "far"}] * 5)["status"] == "aviso"     # nothing measured
    assert A.far_end_item("m", (180, 106), fine, None)["status"] == "aviso"                      # not checked: said


def test_volume_against_400():
    assert A.volume_item("forehand", 265, 180, 4)["status"] == "ok"
    assert A.volume_item("forehand", 150, 100, 4)["status"] == "aviso"


def test_b4_items_read_the_match_folder(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"identity": {"summary": SUMM}, "fine": {"summary": {"candidates": 10, "confirmed": 10}}}))
    (d / "strokes.json").write_text(json.dumps([{"side": "near"}] * 6 + [{"side": "far", "court_pos_m": [0, 1]}] * 4))
    (d / "candidates.json").write_text(json.dumps({"candidates": [{"side": "far", "target": True}] * 4 + [{"side": "far", "target": False}] * 5}))
    found = {"req": 1, "area": "Golpes", "name": "Golpes encontrados frente al marcador: m", "status": "ok", "detail": "",
             "near": 6, "far": 4}
    out = A.b4_items([d, tmp_path / "sin_marcador"], [found], "forehand", 6, 4)
    by = {i["name"]: i for i in out}
    assert by["Identidad en los cambios de lado: m"]["status"] == "ok"
    assert by["Golpes del fondo: m"]["status"] == "ok" and "4 de 4 candidatos suyos del fondo" in by["Golpes del fondo: m"]["detail"]
    assert by["Volumen: forehand analizados en los partidos"]["status"] == "aviso"
    assert not any("sin_marcador" in n for n in by)          # a folder without its scoreboard is not a complete match


def _recall(tmp_path, ident, near, far):
    (tmp_path / "recall_validation_detector.json").write_text(json.dumps({"summary_valid": {
        "identity": {"strokes": ident}, "by_side": {"near": near, "far": far}}}))
    return {i["name"]: i for i in A.f3set_sides_items(tmp_path)}


def test_identity_and_far_end_against_f3set(tmp_path):
    """The PC's F3Set count of 08-11 (summary_valid): identity right in 487 of 492, far end 253/288 against 213/229."""
    near, far = {"gt": 229, "found": 213, "recall": 0.93}, {"gt": 288, "found": 253, "recall": 0.878}
    by = _recall(tmp_path, {"right": 487, "wrong": 5, "undecided": 5, "no_run": 20, "lost_by_identity": 5}, near, far)
    assert by["Identidad frente a F3Set (anotado)"]["status"] == "ok"
    assert by["Golpes del fondo frente a F3Set (anotado)"]["status"] == "ok"
    by = _recall(tmp_path, {"right": 400, "wrong": 92}, near, {**far, "recall": 0.70})
    assert by["Identidad frente a F3Set (anotado)"]["status"] == "aviso"           # 81 % right
    assert by["Golpes del fondo frente a F3Set (anotado)"]["status"] == "aviso"     # 23 points below the near end


def test_without_the_f3set_count_it_is_said(tmp_path):
    out = A.f3set_sides_items(tmp_path)
    assert len(out) == 2 and all(i["status"] == "aviso" and "sin recuento" in i["detail"] for i in out)


def test_b4_requests_have_a_rule_and_their_level_follows_their_checks():
    """Each request of B4 has a rule on the outputs (no note); with its checks passing a HECHO one reaches level 3, a
    PARCIAL one stays at 2; a warning on its own check drops it."""
    ids = real_status.packages()["B4"]["peticiones"]
    for rid in ids:
        assert A.PETITIONS.get(rid) is not None and not isinstance(A.PETITIONS[rid], A.Note), rid
    assert A.PETITIONS[23] != r"golpes analizados"               # «any stroke analysed» said nothing about the ends
    ok = lambda name: {"req": 1, "area": "Golpes", "name": name, "status": "ok", "detail": ""}
    items = [ok(n) for n in ("forehand: golpes analizados", "Golpes encontrados frente al marcador: m",
                             "Saques por punto de su saque: m", "Golpes inventados: precisión en F3Set ≥ 0.94",
                             "Identidad en los cambios de lado: m", "Golpes del fondo: m",
                             "Volumen: forehand analizados en los partidos", "Identidad frente a F3Set (anotado)",
                             "Golpes del fondo frente a F3Set (anotado)")]
    items.append({"req": 2, "area": "Repeticiones y otras cámaras", "name": "Repeticiones y otras cámaras enlazadas: m",
                  "status": "ok", "detail": ""})
    states = {rid: st for rid, _, st in real_status.registry()}
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(items)}
    for rid in ids:
        want = 0 if states[rid] == "FALTA" else 3 if states[rid] == "HECHO" else 2
        assert real_status.level(states[rid], pet.get(rid), rid) == want, (rid, states[rid], pet.get(rid))
    for name, rids in (("Identidad en los cambios de lado: m", (23,)), ("Identidad frente a F3Set", (23,)),
                       ("Volumen: ", (205,)), ("Golpes del fondo: m", (218, 219)),
                       ("Golpes del fondo frente a F3Set", (218, 219)), ("Saques por punto de su saque: m", (155,))):
        bad = [{**i, "status": "aviso"} if i["name"].startswith(name) else i for i in items]
        pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(bad)}
        for rid in rids:
            assert states[rid] == "FALTA" or real_status.level(states[rid], pet[rid], rid) == 2, (rid, name)


def test_far_end_detail_lists_what_is_measured_there():
    """#219 (08-11): the PC audit shows, for her far strokes, position, displacement, contact height and destination,
    the positions taken next to contact and the strokes without pose."""
    fine = {"candidates": 10, "confirmed": 10}
    ok = {"side": "far", "court_pos_m": [0.5, 2.0], "displacement_m": 1.2, "metrics": {"contact_height_pct": 40},
          "shot_bounce_m": [1, 20], "phases": {"loaded": {"frame": 90}}}
    far = [ok] * 7 + [{**ok, "court_pos_offset_s": -0.08, "shot_bounce_m": None}] + \
          [{"side": "far", "phases": {"ready": {"frame": 68}, "impact": {"frame": 110}}}] * 2
    it = A.far_end_item("m", (10, 10), fine, far)
    assert it["status"] == "ok", it["detail"]
    d = it["detail"]
    assert "posición en la pista 80%" in d and "desplazamiento 80%" in d and "altura del impacto 80%" in d
    assert "destino 70%" in d and "≤ 0,2 s del impacto en 1" in d and "2 sin pose" in d
    assert A.far_end_item("m", (10, 10), fine, far[:7] + far[8:] + far[8:9])["status"] == "aviso"     # 70 % with position


def test_identity_counts_the_users_click(tmp_path):
    # 09-11 (Osaka): the click decides every run in the analysis, but identity.json (before the click) said 0 decided
    runs = [{"start": i * 100, "end": i * 100 + 90, "cluster": i % 2, "clothes_margin": 0.6, "near_is_target": None,
             "method": None} for i in range(148)]
    (tmp_path / "identity.json").write_text(json.dumps({"fps": 25.0, "click_by": "clothes", "runs": runs}), encoding="utf-8")
    summ = {"runs": 148, "decided": 0, "agree": 0, "none": 148,
            "clothes": {"same_game_same": 0.95, "check": {"parity_agree": 0.95, "parity_runs": 136}}}
    assert A.identity_item("m", A.with_click(tmp_path, summ), (93, 79))["status"] == "aviso"    # no click: undecided
    (tmp_path / "identidad_clic.json").write_text(json.dumps({"t": 2.0, "near_is_her": True}), encoding="utf-8")
    s = A.with_click(tmp_path, summ)
    assert s["decided"] == 148 and s["click"] == 148
    it = A.identity_item("m", s, (93, 79))
    assert it["status"] == "ok", it["detail"]
    assert "con su clic 148" in it["detail"]
