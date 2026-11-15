"""P0.5d (docs/p0_plan.md §3 ter): the application's requests become the queue's own jobs, and the queue's rules hold
for them: the whole match only with her approval (#262) and after the click, a video goes only when its match is
analysed and its results are on the PC, a wrong request never stops the queue."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))

import cola  # noqa: E402
from tennisbio.infra import peticiones as pt  # noqa: E402

NOW = 1_794_800_000.0
M = "rybakina-ejemplo-r1-2026"


def req(kind, k=0, m=M, **d):
    r = pt.request(kind, NOW + k, m, **d)
    return pt.file_name(kind, m, NOW + k), r


def alta(k=0, **d):
    return req("alta", k, **{"video": "partido.ts", "jugadora": "Jugadora", "rival": "Rival", "preparar": True, **d})


def ids(out):
    return [j["id"] for j in out["trabajos"]]


def test_an_added_match_is_prepared_and_waits_for_the_click_then_for_her_approval():
    out = pt.interpret([alta()])
    assert ids(out) == [f"app_prueba_{M}", f"app_cortes_{M}", f"app_clic_{M}"]
    cortes, clic = out["trabajos"][1], out["trabajos"][2]
    assert cortes["cpu"] is True and cortes["etapas"] == pt.CPU_STAGES and clic["etapas"] == pt.CLICK_STAGES
    assert "cpu" not in clic and clic["tras"] == cortes["id"] and cortes["tras"] == f"app_prueba_{M}"
    assert out["partidos"] == [{"id": M, "video": f"{M}.ts", "jugador": "jugadora", "jugadora": "Jugadora", "rival": "Rival",
                                "desde": "aplicacion"}]
    assert "clic" in out["esperas"][M]
    out = pt.interpret([alta(), req("clic", 5, t=12.5, near_is_her=True)])
    assert f"app_{M}" not in ids(out) and "aprobación" in out["esperas"][M]
    out = pt.interpret([alta(), req("aprobar", 9), req("clic", 5, t=12.5)])     # in time order: click, then approval
    fina, whole = out["trabajos"][-2:]                  # by parts (T24): the fine pass on a GPU, the end on a CPU
    assert fina["id"] == f"app_fina_{M}" and fina["tras"] == f"app_clic_{M}" and fina["etapas"] == pt.FINE_STAGES
    assert whole["id"] == f"app_{M}" and whole["aprobado"] is True and whole["tras"] == fina["id"] and whole["cpu"]
    # every stage of the analysis is in one of the parts, once
    from tennisbio import pipeline, stages  # noqa: F401
    allp = pt.CPU_STAGES + pt.CLICK_STAGES + pt.FINE_STAGES + pt.END_STAGES
    assert sorted(allp) == sorted(pipeline.STAGES) and len(set(allp)) == len(allp)
    assert M not in out["esperas"]
    assert cola.check_queue(out["trabajos"]) == []          # the queue's own checks pass on them


def test_her_approval_without_the_click_does_not_launch_the_whole_match():
    out = pt.interpret([alta(), req("aprobar", 9)])
    assert f"app_{M}" not in ids(out)


def test_the_preparation_needs_her_yes_on_the_alta_screen():
    name, r = alta()
    r.pop("preparar")
    out = pt.interpret([(name, r)])
    assert out["trabajos"] == [] and "preparación" in out["errores"][0][1]


def test_the_queue_never_launches_an_unapproved_whole_match_of_the_application():
    jobs = pt.interpret([alta()])["trabajos"] + [{"id": "app_x", "accion": "partido", "partido": M}]
    sources = {"kaggle": {"ok": True}, "modal": {"ok": True}, "kaggle_cpu": {"ok": True}}
    for jid, src, why in cola.plan(jobs, {}, {}, sources, NOW):
        if jid == "app_x":
            assert not src and "#262" in why


def test_wrong_requests_are_reported_and_the_rest_goes_on():
    bad = [("1", {"tipo": "otra"}), req("alta", 1, m="Con Mayúsculas", video="a.ts", jugadora="J", rival="R", preparar=True),
           req("alta", 2, m="otro-partido", video="a.txt", jugadora="J", rival="R", preparar=True),
           req("alta", 3, m="otro-mas", video="a.mp4", jugadora="", rival="R", preparar=True),
           req("clic", 4), req("cancelar", 5, m=None), req("persona", 6, m=None, name="X", hand="right")]
    out = pt.interpret(bad + [alta(7)])
    assert len(out["errores"]) == len(bad) and ids(out)[0] == f"app_prueba_{M}"


def test_the_same_match_added_twice_counts_once():
    out = pt.interpret([alta(), alta(3, rival="Otra")])
    assert ids(out).count(f"app_prueba_{M}") == 1 and out["partidos"][0]["rival"] == "Rival"


def test_the_last_pause_or_resume_wins_and_a_pause_launches_nothing_new():
    out = pt.interpret([req("pausar", 1, m=None), req("reanudar", 2, m=None), req("pausar", 3, m=None)])
    assert out["pausa"]["en_pausa"] is True
    decisions = [("a", "kaggle", "sitio"), ("b", "", "espera a a"), ("c", "github", "se compara")]
    held = pt.paused_decisions(decisions, out["pausa"])
    assert [d[1] for d in held] == [None, None, None] and "en pausa" in held[0][2] and held[1][2] == "espera a a"
    assert pt.paused_decisions(decisions, pt.interpret([req("reanudar", 1, m=None)])["pausa"]) == decisions
    assert pt.paused_decisions(decisions, None) == decisions


def test_a_video_goes_only_when_its_match_is_analysed_and_on_the_pc():
    asks = [req("borrar_video", 1)]
    assert pt.interpret(asks)["borrar"] == [] and "analizado" in pt.interpret(asks)["errores"][0][1]
    assert pt.interpret(asks, analysed={M})["borrar"] == []                       # not downloaded yet
    assert pt.interpret([req("descargado", 0)] + asks, analysed={M})["borrar"] == [M]


def test_a_cancellation_says_it_came_from_the_application():
    out = pt.interpret([req("cancelar", 1, m=None, trabajo="app_prueba_x")])
    assert "desde la aplicación" in out["cancelar"]["app_prueba_x"]


def test_a_person_needs_name_hand_and_backhand():
    out = pt.interpret([req("persona", 1, m=None, name="Nueva", hand="left", backhand="one_handed", height_m=1.7)])
    assert out["personas"] == [{"id": "nueva", "name": "Nueva", "hand": "left", "backhand": "one_handed", "height_m": 1.7}]


def test_request_names_sort_by_time():
    a, b = pt.file_name("pausar", None, NOW), pt.file_name("reanudar", None, NOW + 1)
    assert a < b and a.endswith("_pausar_cola.json")


def test_a_dry_pass_of_the_queue_takes_the_applications_requests(tmp_path):
    """The whole pass (cloud/cola.py main, dry): the requests on the storage become rows of the queue's state, the pause
    holds every launch, the answer for the application is cola/app.json, and a refused request does not stop it."""
    import json

    import yaml
    root = tmp_path / "volumen"
    folder = root / pt.FOLDER.strip("/")
    folder.mkdir(parents=True)
    for name, r in [alta(jugadora="Elena Rybakina"), req("pausar", 2, m=None), ("3_roto.json", {"tipo": "alta"})]:
        (folder / name).write_text(json.dumps(r), encoding="utf-8")
    (folder / "4_no_json.json").write_text("{", encoding="utf-8")
    q = tmp_path / "cola.yaml"
    q.write_text(yaml.safe_dump({"trabajos": [{"id": "medir_x", "accion": "medir", "prueba": "bola", "donde": "kaggle",
                                               "cpu": True}]}), encoding="utf-8")
    logs = tmp_path / "logs"
    assert cola.main(["--cola", str(q), "--logs", str(logs), "--en-seco", "--peticiones", str(root)]) == 0
    md = (logs / "cola" / "estado.md").read_text(encoding="utf-8")
    assert f"| app_prueba_{M} |" in md and f"| app_clic_{M} |" in md and "En pausa desde la aplicación" in md
    assert "| medir_x |" in md
    ans = json.loads((logs / "cola" / "app.json").read_text(encoding="utf-8"))
    assert ans["pausa"]["en_pausa"] and "clic" in ans["esperas"][M] and len(ans["errores"]) == 2
    assert ans["partidos"][0]["id"] == M and "app.json" in cola.QUEUE_FILES


def test_a_match_names_its_players_record_and_is_refused_without_one():
    """The cloud's catalogue loads config/players/<id>.yaml for the match's player: the request carries that id (or it
    comes from her surname), and with the records known a match of a player without one is refused, with its reason;
    a person added in the application counts."""
    assert pt.player_id("Elena Rybakina") == "rybakina" and pt.player_id("Ñoño Pérez") == "perez"
    out = pt.interpret([alta(jugadora="Elena Rybakina")], players={"rybakina"})
    assert out["partidos"][0]["jugador"] == "rybakina" and ids(out)
    out = pt.interpret([alta(jugadora="Otra Jugadora")], players={"rybakina"})
    assert out["trabajos"] == [] and "no hay ficha" in out["errores"][0][1]
    nueva = req("persona", -5, m=None, name="Otra Jugadora", hand="left", backhand="one_handed", height_m=1.75)
    out = pt.interpret([nueva, alta(jugadora="Otra Jugadora")], players={"rybakina"})
    assert out["personas"][0]["id"] == "jugadora" and out["partidos"][0]["jugador"] == "jugadora"
    assert pt.interpret([alta(jugadora="X Y", jugadora_id="rybakina")], players={"rybakina"})["partidos"][0]["jugador"] == "rybakina"
