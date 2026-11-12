"""Checks of the Base packages B1 (speed and use of the PC) and B3 (best models) in the audit, 04-11: every request
of both packages has an automatic check (or says why not), computed from what the PC leaves (bench_candidates.json,
ritmos.json, recursos/*.csv, ciclo_actions.log), the manifests, the configuration and its own tests on the PC."""
import json
from datetime import datetime

import tennisbio.audit as A
from tennisbio import real_status

HEAD = "hora,partido,etapa,cpu_total,cpu_python,cpu_ffmpeg,ram_usada_gb,ram_total_gb,ram_python_gb,gpu_3d,gpu_compute,gpu_decode,disco\n"


def _manifest(d, **stages):
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(stages), encoding="utf-8")
    return d


def test_each_candidate_measured_or_said_why_not(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    items = A.candidate_items(out)
    assert len(items) == len(A.CANDIDATE_MODELS) and {i["status"] for i in items} == {"aviso"}
    rep = {"version": 1, "device": "dml", "generated": "2026-11-03 10:00", "results": {
        "wasb": {"baseline": "ours (TrackNetV3, fp16)", "accuracy": "F1 0.863 / 0.906", "speed": "44.4 / 34.5 fps",
                 "verdict": {"adopt": False, "reason": "F1 peor"}},
        "mag3d": {"accuracy": "58 % / 13 %", "speed": "196 / 34", "verdict": {"adopt": True, "reason": "mejor"}},
        "ocr5": {"error": "RuntimeError: boom"},
        "rfdetr": {"verdict": {"adopt": False, "insufficient": True, "reason": "sin medida completa"}}}}
    rd = tmp_path / "datasets" / "reports"            # where bench_candidates.py writes it, next to the output
    rd.mkdir(parents=True)
    (rd / "bench_candidates.json").write_text(json.dumps(rep), encoding="utf-8")
    it = {i["name"].split(": ")[1].split(" ")[0]: i for i in A.candidate_items(out)}
    assert it["wasb"]["status"] == "ok" and "no se adopta" in it["wasb"]["detail"] and "0.863" in it["wasb"]["detail"]
    assert it["mag3d"]["status"] == "ok" and "se adopta" in it["mag3d"]["detail"]
    assert it["ocr5"]["status"] == "falta" and "boom" in it["ocr5"]["detail"]
    assert it["rfdetr"]["status"] == "aviso" and it["bounce"]["status"] == "aviso"
    # the copy in the output folder wins over the one in datasets
    (out / "bench_candidates.json").write_text(json.dumps({"results": {}}), encoding="utf-8")
    assert {i["status"] for i in A.candidate_items(out)} == {"aviso"}


def test_models_in_use_from_the_configuration_and_their_files(tmp_path, monkeypatch):
    from tennisbio import court

    f = {k: tmp_path / f"{k}.onnx" for k in ("spot", "ball", "racket", "scenes", "mag", "tcd")}
    for p in f.values():
        p.write_bytes(b"x")
    monkeypatch.setattr(court, "TCD_ONNX", f["tcd"])
    cfg = {"spotter": {"enabled": True, "onnx": str(f["spot"])}, "fine_pass": {"pose_model": "hybrid", "refine": "rtmpose-x"},
           "court": {"detector": "tcd14"}, "trunk3d": {"model": "motionagformer", "onnx": str(f["mag"])},
           "ball": {"onnx": str(f["ball"])}, "racket_face": {"pose_onnx": str(f["racket"])}, "scenes": {"onnx": str(f["scenes"])}}
    items = A.models_in_use_items(cfg)
    assert len(items) == 7 and all(i["status"] == "ok" for i in items), items
    f["mag"].unlink()                                          # adopted but missing: the former reading is used
    cfg["court"]["detector"] = "lines"
    it = {i["name"]: i for i in A.models_in_use_items(cfg)}
    assert it["Modelo en uso: giro 3D del tronco (MotionAGFormer)"]["status"] == "aviso"
    assert "sin su fichero" in it["Modelo en uso: giro 3D del tronco (MotionAGFormer)"]["detail"]
    assert "no elegido" in it["Modelo en uso: pista de 14 puntos (TennisCourtDetector)"]["detail"]


def test_strokes_from_the_learned_detector_per_match(tmp_path):
    a = _manifest(tmp_path / "a", candidates={"summary": {"candidates": 625, "source": "spotter"}},
                  spotting={"summary": {"enabled": True, "near": 344, "far": 299, "threshold": 0.1}})
    b = _manifest(tmp_path / "b", candidates={"summary": {"candidates": 40}})
    c = _manifest(tmp_path / "c", probe={"summary": {"duration_min": 10}})       # no candidates yet: nothing said
    it = {i["name"]: i for i in A.spotter_items([a, b, c])}
    assert it["Golpes del detector aprendido: a"]["status"] == "ok" and "625" in it["Golpes del detector aprendido: a"]["detail"]
    assert it["Golpes del detector aprendido: b"]["status"] == "aviso" and len(it) == 2


def test_the_detector_had_the_ball_of_the_match(tmp_path):
    """12-11: a detector trained with the ball ran without it in every library match; the audit says it per match."""
    from tennisbio.spotting import FEATURE_DIM
    cand = {"summary": {"candidates": 600, "source": "spotter"}}
    sp = lambda **k: {"summary": {"enabled": True, "near": 300, "far": 300, "threshold": 0.1,
                                  "feature_dim": FEATURE_DIM + 8, **k}}
    a = _manifest(tmp_path / "a", candidates=cand, spotting=sp(ball={"min": 16.8, "seen": 0.71, "play_min": 17.0}))
    b = _manifest(tmp_path / "b", candidates=cand, spotting=sp())                                # before the fix
    c = _manifest(tmp_path / "c", candidates=cand, spotting=sp(ball={"min": 0.0, "seen": 0.0, "play_min": 17.0}))
    d = _manifest(tmp_path / "d", candidates=cand, spotting={"summary": {"enabled": True, "feature_dim": FEATURE_DIM}})
    it = {i["name"]: i for i in A.spotter_items([a, b, c, d])}
    ball = lambda m: it[f"{A.BALL_SPOTTER_ITEM}: {m}"]
    assert ball("a")["status"] == "ok" and "16.8 de 17.0" in ball("a")["detail"]
    assert ball("b")["status"] == "aviso" and "sin la bola" in ball("b")["detail"]
    assert ball("c")["status"] == "aviso"
    assert f"{A.BALL_SPOTTER_ITEM}: d" not in it                      # a model without the ball: nothing to say


def test_a_stage_twice_as_slow_as_usual_is_named(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    m = _manifest(out / "m", probe={"seconds": 10, "summary": {"duration_min": 100.0}},
                  identity={"seconds": 600.0}, fine={"seconds": 150.0}, scenes={"seconds": 30.0})
    assert A.stage_time_items([m], out)[0]["status"] == "pocos datos"             # nothing to compare with yet
    rates = {"identity:minuto": [{"s": 1.0}, {"s": 1.1}, {"s": 0.9}], "fine:minuto": [{"s": 1.4}, {"s": 1.6}, {"s": 1.5}],
             "scenes:minuto": [{"s": 0.01}] * 3}
    (out / "ritmos.json").write_text(json.dumps(rates), encoding="utf-8")
    (out / "alarmas.json").write_text(json.dumps({"alarmas": [{"etapa": "identity", "texto": "identity: 2.41 s por unidad"}]}),
                                      encoding="utf-8")
    it = A.stage_time_items([m], out)[0]
    assert it["status"] == "aviso" and "identity 6.0 s por min" in it["detail"] and "alarma en vivo" in it["detail"]
    assert "fine" not in it["detail"].split("MÁS LENTAS")[1]                       # 1.5 s/min, its usual rate
    assert "scenes" not in it["detail"]                                            # read from its caches: not judged
    m2 = _manifest(out / "m2", probe={"summary": {"duration_min": 100.0}}, identity={"seconds": 120.0})
    assert A.stage_time_items([m2], out)[0]["status"] == "ok"


def test_stages_at_the_same_time(tmp_path):
    a = _manifest(tmp_path / "a", score={"seconds": 600}, players={"seconds": 1466, "overlap_s": 569.7})
    b = _manifest(tmp_path / "b", score={"seconds": 600}, players={"seconds": 1466})
    it = {i["name"]: i for i in A.parallel_items([a, b])}
    assert it["Etapas a la vez: a"]["status"] == "ok" and "9.5 min" in it["Etapas a la vez: a"]["detail"]
    assert it["Etapas a la vez: b"]["status"] == "aviso"


def test_use_of_the_pc_per_stage(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    assert A.resources_items(out)[0]["status"] == "aviso"
    (out / "recursos").mkdir()
    (out / "recursos" / "recursos_2026-11-04_1648.csv").write_text(
        HEAD + "t,osaka,identity,65.0,0.0,46.3,5.3,19.8,0.1,0.0,0.0,0.0,0.0\n"
        + "t,osaka,fine,40.0,30.0,5.0,12.0,19.8,4.0,95.0,0.0,0.0,2.0\n", encoding="ascii")
    it = A.resources_items(out)[0]
    assert it["status"] == "ok" and "identity" in it["detail"] and "iGPU al límite" in it["detail"]


def test_requests_start_at_once_by_github_actions(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    assert A.actions_item(out, datetime(2026, 11, 4, 13, 30))["status"] == "aviso"
    (out / "ciclo_actions.log").write_text("**********************\nWindows PowerShell transcript start\n"
                                           "Start time: 20261104133433\n", encoding="utf-8")
    assert A.actions_item(out, datetime(2026, 11, 4, 13, 30))["status"] == "ok"
    late = A.actions_item(out, datetime(2026, 11, 4, 13, 0))
    assert late["status"] == "aviso" and "empezó a los 34." in late["detail"]
    newer = A.actions_item(out, datetime(2026, 11, 4, 15, 0))                 # the last request did not come by Actions
    assert newer["status"] == "aviso" and "no empezó por GitHub Actions" in newer["detail"]


def test_actions_wait_does_not_count_the_time_the_pc_was_busy(tmp_path):
    """#237 (07-11): request at 06:20 while the full analysis ran until 07:06; the job started at 07:11."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "ciclo_actions.log").write_text("Windows PowerShell transcript start\nStart time: 20261107071120\n", encoding="utf-8")
    req = datetime(2026, 11, 7, 6, 20, 30)
    idle = A.actions_item(out, req)                                    # nothing else ran: 50.8 min of real wait
    assert idle["status"] == "aviso" and "empezó a los 50.8 min" in idle["detail"] and "estaba libre" in idle["detail"]
    (out / "ciclo_automatico.log").write_text(
        "Start time: 20261107044424\n==> [2026-11-07 05:13:32] Peticion 119: analisis completo\n"
        "Empezado 2026-11-07 04:44:19 - terminado 2026-11-07 07:05:57 - duracion total 2 h 21 min\n"
        "End time: 20261107070603\n", encoding="utf-8")
    (out / "solo_informe.log").write_text("End time: 20261107100000\n", encoding="utf-8")   # after: not the previous job
    busy = A.actions_item(out, req)
    assert busy["status"] == "ok", busy["detail"]
    assert "otro trabajo hasta las 07:06" in busy["detail"] and "45.5 min" in busy["detail"]
    assert "5.3 min después de quedar libre" in busy["detail"]
    (out / "ciclo_automatico.log").write_text("End time: 20261107061000\n", encoding="utf-8")  # ended before the request
    assert A.actions_item(out, req)["status"] == "aviso"


def test_base_items_never_break_the_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "candidate_items", lambda out: 1 / 0)
    items = A.base_items([], tmp_path, cfg={})
    assert any(i["name"] == "Comprobaciones de la base (B1, B3)" and i["status"] == "aviso" for i in items)
    assert any(i["name"].startswith("Peticiones por GitHub Actions") for i in items)


def test_every_request_of_b1_and_b3_has_a_check_and_reaches_level_3_when_it_holds(monkeypatch):
    """With every check passing, each HECHO request of B1 and B3 is «comprobado en salidas»; a PARCIAL one stays at
    level 2 (built only in part, whatever its checks say). #30, a document, is checked since 07-11 against the measured
    state (comparison_doc_item), so it reaches level 3 too."""
    pk = real_status.packages()
    ids = pk["B1"]["peticiones"] + pk["B3"]["peticiones"]
    for rid in ids:
        assert A.PETITIONS.get(rid) is not None, rid
    assert [r for r in ids if isinstance(A.PETITIONS[r], A.Note)] == []
    ok = lambda area, name: {"req": 9, "area": area, "name": name, "status": "ok", "detail": ""}
    items = [ok("Rendimiento", "Tiempo: m"), ok("Pantallas", "Novedades de la versión"), ok("Uso del PC", "Uso del PC por etapa"),
             ok("Tiempo por etapa", "Tiempo de cada etapa frente a su ritmo en este PC: m"),
             ok("Trabajo en paralelo", "Etapas a la vez: m"), ok("Peticiones del PC", "Peticiones por GitHub Actions: espera"),
             ok("Modelos", "Golpes del detector aprendido: m"), ok("Modelos", A.COMPARISON_ITEM)]
    items += [ok("Modelos", f"Modelo candidato medido: {n} ({w})") for n, (w, _) in A.CANDIDATE_MODELS.items()]
    items += [ok("Modelos", f"Modelo en uso: {x}") for x in ("detector de golpes aprendido (F3Set)", "esqueleto híbrido (YOLO11 + RTMPose)",
                                                           "pista de 14 puntos (TennisCourtDetector)", "giro 3D del tronco (MotionAGFormer)",
                                                           "bola (TrackNetV3 de RacketVision)")]
    items += [ok("Pruebas en este PC", f"Pruebas en este PC: {m}") for m in A.MODULE_TESTS]
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(items)}
    states = {rid: st for rid, _, st in real_status.registry()}
    for rid in ids:
        lv = real_status.level(states[rid], pet.get(rid), rid)
        want = 3 if states[rid] == "HECHO" else 2
        assert lv == want, (rid, states[rid], pet.get(rid))
    # and a failing check is said: the candidate of #202 not measured → #202 drops to level 2
    items = [i if not i["name"].startswith("Modelo candidato medido: wasb") else {**i, "status": "aviso"} for i in items]
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(items)}
    assert real_status.level(states[202], pet[202], 202) == 2



def test_a_request_the_scheduled_cycle_started_once_the_pc_was_free_is_ok(tmp_path):
    """08-11: request 143 (05:48) was started by the scheduled cycle at 06:02:50, when request 142 ended (06:02:37)."""
    from datetime import datetime
    from tennisbio.audit import actions_item
    (tmp_path / "ciclo_actions.log").write_text("Start time: 20261108030400\n", encoding="utf-8")
    (tmp_path / "prueba_recall.log").write_text("termina 2026-11-08T06:02:37\n", encoding="utf-8")
    (tmp_path / "ciclo_automatico.log").write_text(
        "Start time: 20261108055321\n==> [2026-11-08 06:02:50] Peticion 143: analisis completo\n", encoding="utf-8")
    it = actions_item(tmp_path, request_time=datetime(2026, 11, 8, 5, 48))
    assert it["status"] == "ok" and "ciclo programado" in it["detail"], it["detail"]
    (tmp_path / "prueba_recall.log").write_text("termina 2026-11-08T05:40:00\n", encoding="utf-8")
    assert actions_item(tmp_path, request_time=datetime(2026, 11, 8, 5, 48))["status"] == "aviso"   # idle 14.8 min


def test_b6_and_b7_requests_are_checked_on_the_outputs_and_their_level_follows_the_checks():
    """08-11: #1 and #234 (B6) were notes (level 0-1 whatever the outputs said); now each request of B6 and of the B7
    ones that were open (#45, #66, #146, #160, #242) has a rule on the real outputs. With every check passing a HECHO
    request reaches level 3 and a PARCIAL one stays at 2; a warning on the strokes found against the scoreboard of
    one match drops #1, #45, #134 and #233 to level 2; the old test folder still on disk drops #146."""
    pk = real_status.packages()
    ids = pk["B6"]["peticiones"] + [45, 66, 146, 160, 242]
    for rid in ids:
        assert A.PETITIONS.get(rid) is not None and not isinstance(A.PETITIONS[rid], A.Note), rid
    ok = lambda area, name: {"req": 5, "area": area, "name": name, "status": "ok", "detail": ""}
    items = [ok("Golpes", "forehand: golpes analizados"), ok("Golpes", "Golpes encontrados frente al marcador: m"),
             ok("Golpes", "Saques por punto de su saque: m"), ok("Ficheros", "Partido m: salida de cada etapa, ventanas y series"),
             ok("Automático", "Golpes que fallaron al procesarse"), ok("Automático", "Nada pide revisión manual"),
             ok("Pantallas", "Pantalla «Cópiala (Aprende su derecha, con su patrón típico)»"),
             ok("Pantallas", "Pantalla «Conclusiones (Panel y Comparativas)»"),
             ok("Infraestructura", "Registros con fecha y duración"), ok("Infraestructura", "Carpetas de pruebas antiguas"),
             ok("Aplicación", "Aplicación: ventana real y pantallas"), ok("Aplicación", "Aplicación: análisis en su índice"),
             ok("Aplicación", A.NEW_MATCH_ITEM)]
    items += [ok("Pruebas en este PC", f"Pruebas en este PC: {m}") for m in A.MODULE_TESTS]
    states = {rid: st for rid, _, st in real_status.registry()}
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(items)}
    for rid in ids:
        assert real_status.level(states[rid], pet.get(rid), rid) == (3 if states[rid] == "HECHO" else 2), (rid, pet.get(rid))
    assert "3 comprobaciones" in pet[234]["detail"], pet[234]        # the application with the real data, not a note
    # the strokes of one match below the scoreboard's typical range: every request that needs the reference complete
    bad = [{**i, "status": "aviso"} if i["name"].startswith("Golpes encontrados frente al marcador") else i for i in items]
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(bad)}
    for rid in (1, 45, 134, 233):
        assert pet[rid]["status"] == "aviso" and real_status.level(states[rid], pet[rid], rid) == 2, rid
    assert real_status.level(states[234], pet[234], 234) == (3 if states[234] == "HECHO" else 2)
    old = [{**i, "status": "aviso"} if i["name"] == "Carpetas de pruebas antiguas" else i for i in items]
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items(old)}
    assert real_status.level(states[146], pet[146], 146) == 2


def test_a_stage_that_really_computed_is_judged_against_the_slowest_run_not_the_median(tmp_path):
    """08-11: 584c5b's fine (7.5 min after a code change) was called slow against a median of cache re-reads."""
    import json
    from tennisbio.audit import stage_time_items
    out = tmp_path / "output"
    d = out / "m"
    d.mkdir(parents=True)
    (out / "ritmos.json").write_text(json.dumps({"fine:minuto": [{"s": 1.5}, {"s": 1.6}, {"s": 1.8}, {"s": 3.5}]}),
                                     encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"probe": {"summary": {"duration_min": 120}},
                                                 "fine": {"seconds": 450}}), encoding="utf-8")
    it = stage_time_items([d], out)[0]
    assert it["status"] == "ok", it["detail"]                       # 3.75 s/min < 2 × 3.5
    (d / "manifest.json").write_text(json.dumps({"probe": {"summary": {"duration_min": 120}},
                                                 "fine": {"seconds": 900}}), encoding="utf-8")
    assert stage_time_items([d], out)[0]["status"] == "aviso"       # 7.5 s/min > 2 × 3.5
