"""The automatic cycle of the PC: what to run for each change, and the review against the last run."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from auto_cycle import decide, review  # noqa: E402


def test_decide():
    assert decide(["src/tennisbio/technique.py", "docs/x.md"]) == "medidas"
    assert decide(["src\\tennisbio\\stages.py"]) == "medidas"
    assert decide(["src/tennisbio/report_template.html"]) == "informe"
    assert decide(["src/tennisbio/audit.py", "config/practice_videos.yaml"]) == "informe"
    assert decide(["uv.lock"]) == "informe"
    assert decide(["docs/matriz_cobertura.md", "tests/test_audit.py"]) == "informe"      # the audit reads it
    assert decide(["docs/estado_proyecto.md", "tests/test_x.py", "CLAUDE.md"]) == "nada"
    assert decide([]) == "nada"


def test_decide_covers_every_fine_pass_module():
    """Any module whose code is in the fine-pass fingerprint must make the PC recompute the measures."""
    from tennisbio.stages import FINE_CODE

    for mod in FINE_CODE:
        assert decide([f"src/tennisbio/{mod.replace('.', '/')}.py"]) == "medidas", mod


def audit(tmp, name, items):
    p = tmp / name
    p.write_text(json.dumps({"items": [{"name": n, "status": s, "detail": d} for n, s, d in items]}), encoding="utf-8")
    return p


def test_review(tmp_path):
    old = audit(tmp_path, "old.json", [("A", "ok", ""), ("B", "aviso", ""), ("C", "ok", ""), ("Cada medida comprobada: x", "ok", "1 fiable")])
    new = audit(tmp_path, "new.json", [("A", "ok", ""), ("B", "ok", ""), ("C", "falta", "se rompió"), ("D", "ok", "nueva"),
                                       ("Cada medida comprobada: x", "ok", "2 fiable")])
    v, md = review(new, old, [])
    assert v == "REGRESIÓN" and "C**: ok → falta" in md and "B: aviso → ok" in md and "D: ok" in md and "2 fiable" in md
    v, _ = review(old, old, [])
    assert v == "OK"
    log = tmp_path / "x.log"
    log.write_text("bla\nTraceback (most recent call last):\n  File x\nValueError: boom\n", encoding="utf-8")
    v, md = review(old, old, [log])
    assert v == "ERROR" and "x.log" in md
    v, md = review(tmp_path / "none.json", old, [])
    assert v == "ERROR"


def test_decide_for_the_long_run_fixes():
    """Surface on each stroke, ball speed limits, catalogue of test runs: measures again; the single-level
    situations of «Su derecha»: only the report."""
    for f in ("src/tennisbio/ball3d.py", "src/tennisbio/limits.py", "src/tennisbio/catalog.py", "scripts/recompute_measures.py"):
        assert decide([f]) == "medidas", f
    for f in ("src/tennisbio/model.py", "src/tennisbio/explain.py", "scripts/rebuild_report.py"):
        assert decide([f]) == "informe", f


def test_request_informe_recomputes_a_given_folder():
    """config/peticion_pc.txt «accion: informe» + «carpeta: _pocN_largo»: measures from the caches,
    report and audit of that folder, logged where comun.ps1 uploads it."""
    ps1 = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()                                   # Windows PowerShell 5.1 reads it as ANSI
    block = ps1[ps1.index('$p["accion"] -eq "informe"'):]
    block = block[:block.index("} else {")]
    assert 'recompute_measures.py --out-name $c' in block
    assert '$lg = "$Base\\output\\prueba$($c)_informe.log"' in block
    assert "$p['carpeta']" in block and "^_[A-Za-z0-9_-]+$" in block          # only a folder inside output


def test_recompute_and_rebuild_take_the_output_folder(tmp_path, monkeypatch, capsys):
    import importlib.util

    for name in ("recompute_measures", "rebuild_report"):
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod, "load_config", lambda: {"paths": {"output": str(tmp_path)}})
        monkeypatch.setattr(sys, "argv", [name, "--out-name", "_poc9_largo"])
        assert mod.main() == 1                              # nothing analysed there: says so, no crash
        assert str(tmp_path / "_poc9_largo") in capsys.readouterr().out


def test_cycle_starts_without_any_window():
    """The task, the loop and the start-up entry go through oculto.vbs (wscript, window 0): with
    powershell -WindowStyle Hidden Windows showed a terminal for a moment every 10 minutes."""
    win = Path(__file__).resolve().parents[1] / "scripts" / "windows"
    vbs = (win / "oculto.vbs").read_text(encoding="utf-8")
    assert vbs.isascii() and ", 0, True" in vbs
    comun = (win / "comun.ps1").read_text(encoding="utf-8")
    assert '-Execute "wscript.exe"' in comun and '"ciclo v5"' in comun and "tenis-ciclo.vbs" in comun
    # 02-11: the task at normal priority (without it Windows ran it below normal, ~3 times slower)
    assert "-Priority 4" in comun
    assert "PriorityClass" in (win / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert "oculto.vbs" in (win / "ciclo_bucle.ps1").read_text(encoding="utf-8")


def test_request_borrar_only_old_speed_test_folders():
    """«accion: borrar» removes only folders named _poc, _pocN or _pocN_M and, named by hand, the long run _poc9_largo
    (08-11, #146: the application no longer uses it; the user approved deleting the old test folders on 07-11):
    never _smoke nor anything else."""
    import re

    ps1 = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()
    block = ps1[ps1.index('$p["accion"] -eq "borrar"'):]
    block = block[:block.index("} else {")]
    rx = re.search(r"-notmatch '([^']+)'", block).group(1)
    for ok in ("_poc", "_poc3", "_poc3_4", "_poc5_35", "_poc7_4", "_poc9_largo"):
        assert re.match(rx, ok), ok
    for no in ("_smoke", "_poc_x", "..", "_poc3\\..", "videos", "", "_poc8_largo", "_poc9_largo\\..", "_poc9_largox"):
        assert not re.match(rx, no), no
    assert 'prueba_borrado.log' in block


def test_request_youtube_runs_the_chosen_videos():
    """«accion: youtube» + «urls: …»: only the videos the user chose, into output\\investigacion_<id>,
    logged where comun.ps1 uploads it; each investigacion_* folder is uploaded to pc-logs."""
    win = Path(__file__).resolve().parents[1] / "scripts" / "windows"
    ps1 = (win / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    block = ps1[ps1.index('$p["accion"] -eq "youtube"'):]
    block = block[:block.index("} elseif")]
    assert '--urls "$($p[\'urls\'])"' in block and "investigacion_$($p['id'])" in block and "prueba_youtube.log" in block
    comun = (win / "comun.ps1").read_text(encoding="utf-8")
    assert comun.isascii() and '-Filter "investigacion_*"' in comun
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from youtube_research import video_id
    assert [video_id(u) for u in ("https://youtu.be/A5jgd_CPohM", "https://www.youtube.com/watch?v=rcZUuIpp-y0&t=3", "cFFPGpGmkKE")] == \
        ["A5jgd_CPohM", "rcZUuIpp-y0", "cFFPGpGmkKE"]


def test_youtube_falls_back_when_the_installed_ytdlp_gets_no_formats(tmp_path, monkeypatch):
    """YouTube changes: the installed yt-dlp says «Requested format is not available». The script tries other
    clients, then the newest yt-dlp; the video that one downloads is used and the errors are kept."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import subprocess
    import youtube_research as yr
    calls = []

    def fake(*args, timeout=600, cmd=None):
        calls.append(cmd)
        if "-f" in args and cmd is yr.FALLBACKS[-1]:
            (tmp_path / "t" / "abcdefghijk.video.mp4").write_bytes(b"x")
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "ERROR: Requested format is not available")

    def fake_ffmpeg(cmd, timeout=None):
        (tmp_path / "out" / "abcdefghijk" / "f_001.jpg").write_bytes(b"j")
    monkeypatch.setattr(yr, "ytdlp", fake)
    monkeypatch.setattr(yr.subprocess, "run", fake_ffmpeg)
    (tmp_path / "t").mkdir()
    v = yr.one({"id": "abcdefghijk", "title": "x", "duration_s": 300.0, "chosen_by_user": True}, tmp_path / "out", tmp_path / "t")
    assert v["frames"] == 1 and "video_error" not in v
    assert calls.count(None) == 2 and yr.FALLBACKS[-1] in calls      # subtitles + video with the installed one first
    assert not list((tmp_path / "t").iterdir())                        # the video is deleted


def test_request_app_builds_the_local_index_without_running_jobs():
    """«accion: app»: the application's index on the PC with its real data (status, plan, status), logged
    in output\\prueba_app.log (uploaded with the other logs); it never runs the queue («work»)."""
    win = Path(__file__).resolve().parents[1] / "scripts" / "windows"
    ps1 = (win / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()
    block = ps1[ps1.index('$p["accion"] -eq "app"'):]
    block = block[:block.index("} elseif")]
    assert '@("status", "plan", "status")' in block and "uv run tennisbio app $orden" in block and "prueba_app.log" in block
    # the queue runs only when asked («trabajar: si», 04-11) AND the plan has nothing to recompute (reports only)
    before_guard = block[:block.index("trabajar")]
    assert "work" not in before_guard
    guarded = block[block.index("trabajar"):]
    assert "0 partido\\(s\\) a recalcular" in guarded and guarded.index("a recalcular") < guarded.index("app work")


def test_request_ventana_paints_the_app_screens_with_the_real_index():
    """«accion: ventana»: every screen of the application painted with the real index (read-only, no window
    opened to the user), its check and screenshots uploaded to pc-logs; the app's extra is installed by the
    cycle and the installer (otherwise each cycle's sync would remove pywebview)."""
    win = Path(__file__).resolve().parents[1] / "scripts" / "windows"
    ps1 = (win / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    block = ps1[ps1.index('$p["accion"] -eq "ventana"'):]
    block = block[:block.index("} elseif")]
    assert '"comprobar", $s, "--real"' in block and "prueba_ventana.log" in block
    assert "WaitForExit(900000)" in block and "taskkill.exe /T /F" in block          # never hangs the cycle again
    comun = (win / "comun.ps1").read_text(encoding="utf-8")
    assert comun.isascii() and "--extra app" in comun and "capturas_app" in comun
    assert '"--extra", "app"' in (win / "instalar.ps1").read_text(encoding="utf-8")
    vbs = (Path(__file__).resolve().parents[1] / "Tennisbio.vbs").read_text(encoding="utf-8")
    assert vbs.isascii() and "tennisbio app ventana" in vbs and ", 0, False" in vbs


def test_recompute_runs_the_stages_the_config_adds():
    """29-10: a trial folder made before the spotter had no spotting.json and the cycle stopped."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import recompute_measures as r

    on = r.cheap_stages({"spotter": {"enabled": True}})
    assert on.index("spotting") < on.index("candidates") and not set(on) & set(r.EXPENSIVE + r.FINE)
    assert "spotting" not in r.cheap_stages({"spotter": {"enabled": False}})


def test_every_module_the_fine_pass_imports_is_in_its_code_fingerprint():
    """04-11 (request 106): the serve rule lived in point_count, not in FINE_CODE, so the PC never re-ran the fine pass
    after a change to it and kept the former results."""
    import re
    from pathlib import Path
    from tennisbio.stages import FINE_CODE
    s = (Path(__file__).resolve().parents[1] / "src" / "tennisbio" / "stages.py").read_text(encoding="utf-8")
    region = s[s.index("def _fine_model_files"):s.index("\n_TIMES: dict = {}")]
    missing = set(re.findall(r"from \.([\w.]+) import", region)) - set(FINE_CODE)
    assert not missing, missing


def test_actions_job_waits_for_the_running_job_instead_of_leaving_the_request_to_the_next_cycle():
    """Request #237 (05-11 01:55 and 06-11 23:26): the GitHub Actions job found another cycle running and left in 2 s,
    so the request waited for the 10-min cycle (22 min on 05-11). Now: every cycle that launched this one (parent,
    grandparent, ...) is not «another analysis»; a cycle that only waits for news (Esperar-Novedades) does not hold the
    Actions job; and the Actions job waits until the PC is free, then does the request (with the newer script if it
    changed meanwhile). The loop's 10-min cycles still leave at once when busy."""
    import re
    ps1 = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()
    anc = ps1[ps1.index("function Antecesores"):]
    anc = anc[:anc.index("\n}\n")]
    assert "ParentProcessId" in anc and "-lt 12" in anc            # walks up the chain, bounded
    busy = ps1[ps1.index("function Otros-Analisis"):]
    busy = busy[:busy.index("\n}\n")]
    assert "$MisAntecesores -notcontains $_.ProcessId" in busy and "ciclo_esperando.txt" in busy
    assert "if ($env:GITHUB_ACTIONS)" in busy                       # only the Actions job ignores the waiting cycle
    wait = ps1[ps1.index("function Esperar-Novedades"):]
    wait = wait[:wait.index("\n}\n")]
    assert '"$PID" | Set-Content $esp' in wait and wait.count("Remove-Item $esp") == 2
    # the Actions job waits (bounded below the workflow's 72 h timeout), then goes on; others still leave when busy
    i_wait = ps1.index("if ($ocupado -and $env:GITHUB_ACTIONS)")
    i_leave = ps1.index('if ($ocupado) { Senal-Vida "otro analisis en marcha')
    assert i_wait < i_leave
    block = ps1[i_wait:i_leave]
    assert "Start-Sleep" in block and "$ocupado = Otros-Analisis" in block and "Relanzar" in block
    hours = float(re.search(r"TotalHours -lt (\d+)", block).group(1))
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pc.yml").read_text(encoding="utf-8")
    assert hours * 60 < int(re.search(r"timeout-minutes: (\d+)", wf).group(1))
    assert "concurrency:" in wf and "cancel-in-progress: false" in wf   # one Actions job at a time, none cancelled


def test_what_a_code_change_needs_goes_to_the_single_queue(tmp_path):
    """R28 (13-11): the cycle never runs the recompute itself (outside the queue it held back the queue's orders and
    shared the iGPU): decide queues its flow behind what was asked and tells the cycle «nada»."""
    from auto_cycle import FLOW_OF, QUEUE_PRIORITY, to_queue
    got = []
    assert to_queue("medidas", submit=lambda f: got.append(f) or 0) == "nada" and got == ["medidas_prueba"]
    assert to_queue("informe", submit=lambda f: got.append(f) or 0) == "nada" and got[-1] == "informe_prueba"
    assert to_queue("nada", submit=lambda f: got.append(f) or 0) == "nada" and len(got) == 2
    from tennisbio.orchestrator import flows
    fl = flows()
    assert set(FLOW_OF.values()) <= set(fl) and QUEUE_PRIORITY > 5
    assert [p["script"][0] for p in fl["medidas_prueba"]["pasos"]] == ["scripts/auto_cycle.py", "scripts/recompute_measures.py",
                                                                     "scripts/auto_cycle.py"]


def test_the_queue_takes_a_lower_priority_after_what_was_asked(tmp_path, monkeypatch):
    from tennisbio import orchestrator as O
    from tennisbio.app.db import DB
    db = DB(tmp_path / "q.db")
    O.ensure_schema(db) if hasattr(O, "ensure_schema") else None
    a = O.submit(db, "comando", args=["run", "--all"], source="t")
    b = O.submit(db, "flujo", args=["medidas_prueba"], source="ciclo", priority=9)
    c = O.submit(db, "comando", args=["audit"], source="t")
    order = [r["id"] for r in db.q("SELECT id FROM jobs WHERE state='pendiente' ORDER BY priority, id")]
    assert order == [a, c, b]
