"""The B7 checks the audit reads from the PC's own files (requests #50, #66, #81, #146, #160, #242), with the formats
the PC really writes (pc-logs, 04-11): each one passes on a good file and fails or warns, saying why, on a bad one."""
import json
import os
import time

from tennisbio.audit import (PETITIONS, app_items, infrastructure_items, log_dates, logs_item, old_test_folders_item,
                             progress_item, sizes_item)

TRANSCRIPT = """﻿**********************
Windows PowerShell transcript start
Start time: 20261013004141
**********************

==> [2026-10-13 00:41:42] Actualizando
    (paso terminado en 0 s)
Empezado 2026-10-13 00:41:41 - terminado 2026-10-13 00:44:11 - duracion total 2 min 30 s
**********************
Windows PowerShell transcript end
End time: 20261013004411
**********************
"""
REQUEST = "﻿Peticion 96: partido nuevo con la aplicacion (2026-11-04T12:27:32)\n  tramo: 35 min\nduracion total: 60.5 min; termina 2026-11-04T13:28:01\n"
TESTS = "﻿commit: 1b727f6\ninicio: 2026-11-04T16:30:09\nfin: 2026-11-04T16:40:53\ncodigo: 0\n....\n"
EVENTS = "2026-10-25 14:37:01 (+0.0 s) arranque (pid 10088)\n2026-10-25 14:40:06 (+185.1 s) ventana cerrada\n"


def test_each_log_format_of_the_pc_says_when_it_started_and_ended():
    for txt in (TRANSCRIPT, REQUEST, TESTS, EVENTS):
        assert log_dates(txt, 10 * 86400) == ""
    # the real case of 04-11: «prevision» wrote when it started, never when it ended
    no_end = "﻿Peticion 98: prevision (2026-11-04T13:47:38)\n# Previsión\n| a | b |\n"
    assert log_dates(no_end, 86400) == "sin «termina fecha» al final"
    assert log_dates(no_end, 600) == ""                                  # still running: not yet a fault
    assert log_dates(TRANSCRIPT.replace("Empezado", "Hecho").replace("duracion total", "en"), 0) == "terminó sin «Empezado … duracion total»"
    assert log_dates(TRANSCRIPT.replace("==> [2026-10-13 00:41:42]", "==>").replace("Empezado 2026", "Empezado"), 0) == "sin la fecha de sus pasos"
    assert log_dates("Peticion 5: algo\ntermina 2026-11-04T13:28:01\n", 0) == "sin la fecha de inicio"
    assert log_dates("hola\nadios\n", 0) == "sin fechas" and log_dates("", 0) == "vacío"


def test_logs_item_names_the_logs_without_dates(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    for name, txt in [("prueba_rapida.log", TRANSCRIPT), ("prueba_app_nuevo.log", REQUEST), ("pruebas.log", TESTS)]:
        (out / name).write_text(txt, encoding="utf-8")
    assert logs_item([out])["status"] == "ok"
    f = out / "prevision.log"
    f.write_text("Peticion 98: prevision (2026-11-04T13:47:38)\n# Previsión\n", encoding="utf-8")
    os.utime(f, (time.time() - 86400, time.time() - 86400))
    it = logs_item([out])
    assert it["status"] == "falta" and "prevision.log: sin «termina fecha»" in it["detail"] and "3 de 4" in it["detail"]
    assert logs_item([tmp_path / "nada"])["status"] == "aviso"


def test_progress_item(tmp_path):
    assert progress_item([tmp_path])["status"] == "aviso"
    p = {"partido": "m1", "etapa": "fine", "hecho": 3, "total": 10, "porcentaje": 30.0, "segundos": 60, "quedan_s": 140,
         "hora": "2026-11-04 17:19:44"}
    (tmp_path / "progreso.json").write_text(json.dumps(p), encoding="utf-8")
    it = progress_item([tmp_path])
    assert it["status"] == "ok" and "fine de m1 al 30.0 %" in it["detail"]
    (tmp_path / "progreso.json").write_text(json.dumps({**p, "hora": None}), encoding="utf-8")
    assert progress_item([tmp_path])["status"] == "falta"
    (tmp_path / "progreso.json").write_text("{", encoding="utf-8")
    assert progress_item([tmp_path])["status"] == "falta"


SIZES = "fecha: 2026-11-04T18:10:19\n         4 MB  \\output\\auditoria\n    7818.9 MB  \\output\\_poc9_largo\n    1300.4 MB  \\output\\_poc70_35\n    2319.5 MB  \\output\\_smoke\n       1.2 MB  \\output\\_smoke\\auditoria\n"


def test_sizes_item_reads_tamanos(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    assert sizes_item([out, tmp_path])["status"] == "aviso"
    (tmp_path / "registros").mkdir()
    (tmp_path / "registros" / "tamanos.txt").write_text(SIZES, encoding="utf-8")
    it = sizes_item([out, tmp_path])
    assert it["status"] == "ok" and "5 carpetas" in it["detail"] and "_poc9_largo 7.6 GB" in it["detail"]
    (tmp_path / "registros" / "tamanos.txt").write_text("nada\n", encoding="utf-8")
    assert sizes_item([out, tmp_path])["status"] == "falta"


def test_old_test_folders_are_named_with_their_size(tmp_path):
    out = tmp_path / "output"
    (tmp_path / "registros").mkdir(parents=True)
    (tmp_path / "registros" / "tamanos.txt").write_text(SIZES, encoding="utf-8")
    out.mkdir()
    assert old_test_folders_item([out, tmp_path])["status"] == "ok"           # none at all
    now = time.time()
    for name, age_days in [("_poc9_largo", 30), ("_poc70_35", 3), ("_smoke", 60)]:
        d = out / name
        d.mkdir()
        (d / "registro.log").write_text("x", encoding="utf-8")
        for p in (d, d / "registro.log"):
            os.utime(p, (now - age_days * 86400, now - age_days * 86400))
    it = old_test_folders_item([out, tmp_path], now=now)
    assert it["status"] == "aviso" and "1 carpeta(s)" in it["detail"] and "_poc9_largo" in it["detail"]
    assert "_poc70_35" not in it["detail"] and "_smoke" not in it["detail"] and "7.6 GB" in it["detail"]
    assert (out / "_poc9_largo").exists()                                   # only said, never deleted
    assert old_test_folders_item([out, tmp_path], now=now, days=60)["status"] == "ok"


def test_app_items_from_the_pcs_own_check(tmp_path):
    assert {i["status"] for i in app_items([tmp_path])} == {"aviso"}
    (tmp_path / "capturas_app").mkdir()
    f = tmp_path / "capturas_app" / "ventana.json"
    v = {"problems": [], "screens": 56, "live": {"opened": True, "ready": True},
         "index": {"matches": 18, "players": 2, "analyses": 0}}                # the PC on 04-11
    f.write_text(json.dumps(v), encoding="utf-8")
    win, an = app_items([tmp_path])
    assert win["status"] == "ok" and "56 pantallas" in win["detail"]
    assert an["status"] == "aviso" and "0 análisis y 18 partidos" in an["detail"]
    f.write_text(json.dumps({**v, "problems": ["390: cola se sale por el lado"], "index": {**v["index"], "analyses": 2}}),
                 encoding="utf-8")
    win, an = app_items([tmp_path])
    assert win["status"] == "falta" and "se sale" in win["detail"] and an["status"] == "ok"
    f.write_text(json.dumps({**v, "live": {"ready": False, "error": "sin respuesta en 120 s"}}), encoding="utf-8")
    assert app_items([tmp_path])[0]["status"] == "falta"


def test_app_index_item_reads_the_index_itself_not_an_old_window_check(tmp_path):
    """#160, #242 (07-11): the audit said «0 análisis» from capturas_app/ventana.json of 04-11 while the index had
    the forehand of the 4 matches since request 114 (07-11 00:40): the item reads the index as it is now."""
    from tennisbio.app.db import DB
    out = tmp_path / "output"
    (out / "capturas_app").mkdir(parents=True)
    (out / "capturas_app" / "ventana.json").write_text(json.dumps(
        {"problems": [], "screens": 56, "live": {"opened": True, "ready": True},
         "index": {"matches": 18, "players": 2, "analyses": 0}}), encoding="utf-8")      # the PC on 04-11
    bases = [out, tmp_path, tmp_path.parent]
    assert app_items(bases)[1]["status"] == "aviso"                                     # no index: the snapshot
    db = DB(tmp_path / "datos" / "tennisbio.db")
    db.upsert("matches", {"id": "zheng-qinwen-elena-rybakina", "state": "analizado"})
    db.upsert("analyses", {"id": "rybakina_forehand", "player": "rybakina", "stroke": "forehand", "n_strokes": 441})
    db.close()
    win, an = app_items(bases)
    assert win["status"] == "ok" and an["status"] == "ok"
    assert "1 análisis y 1 partidos" in an["detail"] and "tennisbio.db" in an["detail"]
    (out / "capturas_app" / "ventana.json").unlink()                                    # no window check yet
    win, an = app_items(bases)
    assert win["status"] == "aviso" and an["status"] == "ok"


def test_every_infrastructure_item_is_tied_to_its_request(tmp_path):
    import re
    names = [i["name"] for i in infrastructure_items(tmp_path / "output")]
    # 07-11: + the application's new match from start to end (B7's main test); 11-11 (R7): + the queue's 3 (B8's)
    assert len(names) == 10
    by = {n: [r for r, rule in PETITIONS.items() if isinstance(rule, str) and type(rule) is str and re.search(rule, n)]
          for n in names}
    assert 50 in by["Progreso visible (progreso.json)"] and 66 in by["Registros con fecha y duración"]
    assert 81 in by["Tamaño de la salida (tamanos.txt)"] and 146 in by["Carpetas de pruebas antiguas"]
    assert {160, 242} <= set(by["Aplicación: ventana real y pantallas"]) & set(by["Aplicación: análisis en su índice"])
    assert 242 in by["Aplicación: un partido nuevo de principio a fin"]
    assert 249 in by["Orquestador: prueba de extremo a extremo"] and 237 in by["Orquestador: espera hasta empezar cada trabajo"]
    assert 246 in by["Orquestador: ejecutor vivo cuando hay trabajo"]


def test_app_queue_log_and_a_request_log_open_while_its_analysis_runs(tmp_path):
    # 10-11 (#66): app_cola.log «sin fechas», prueba_completo.log audited from inside the analysis it launched
    import os
    import time as _t
    from tennisbio.audit import log_dates, logs_item
    q = "\n== 2026-11-09 21:00:00 cola\nanalizando...\n== 2026-11-09 22:00:00 fin (código 0)\n"
    assert log_dates(q, 86400) == ""
    assert log_dates("\n== 2026-11-09 21:00:00 cola\nanalizando...\n", 86400) == "sin «== fecha fin» al final"
    (tmp_path / "prueba_completo.log").write_text("Peticion 181: analisis completo (2026-11-09T23:29:01)\n  video: x\n",
                                                  encoding="utf-8")
    old = _t.time() - 5 * 3600
    os.utime(tmp_path / "prueba_completo.log", (old, old))
    assert logs_item([tmp_path])["status"] == "falta"
    (tmp_path / "progreso.json").write_text("{}", encoding="utf-8")         # the analysis is still writing its progress
    assert logs_item([tmp_path])["status"] == "ok"


def test_new_match_through_the_single_worker(tmp_path):
    # 11-11: B7's run now goes through `tennisbio worker --once`; its queue says the match job «hecho»
    from tennisbio.audit import new_match_item
    (tmp_path / "prueba_app_nuevo.log").write_text(
        "Peticion 206: partido nuevo\nejecutor: parado · cola activa\n  hecho     #3 partido partido nuevo \n"
        "duracion total: 52.1 min; termina 2026-11-11T22:10:00\n", encoding="utf-8")
    it = new_match_item([tmp_path])
    assert it["status"] == "ok", it["detail"]
    (tmp_path / "prueba_app_nuevo.log").write_text("Peticion 1\n  error     #3 partido x\ntermina 2026-11-11T22:10:00\n", encoding="utf-8")
    assert new_match_item([tmp_path])["status"] == "falta"
