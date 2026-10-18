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
    assert '-Execute "wscript.exe"' in comun and '"ciclo v4"' in comun and "tenis-ciclo.vbs" in comun
    assert "oculto.vbs" in (win / "ciclo_bucle.ps1").read_text(encoding="utf-8")


def test_request_borrar_only_old_speed_test_folders():
    """«accion: borrar» removes only folders named _poc, _pocN or _pocN_M: never the long run or _smoke."""
    import re

    ps1 = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()
    block = ps1[ps1.index('$p["accion"] -eq "borrar"'):]
    block = block[:block.index("} else {")]
    rx = re.search(r"-notmatch '([^']+)'", block).group(1)
    for ok in ("_poc", "_poc3", "_poc3_4", "_poc5_35", "_poc7_4"):
        assert re.match(rx, ok), ok
    for no in ("_poc9_largo", "_smoke", "_poc_x", "..", "_poc3\\..", "videos", ""):
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
    assert "work" not in block


def test_request_ventana_paints_the_app_screens_with_the_real_index():
    """«accion: ventana»: every screen of the application painted with the real index (read-only, no window
    opened to the user), its check and screenshots uploaded to pc-logs; the app's extra is installed by the
    cycle and the installer (otherwise each cycle's sync would remove pywebview)."""
    win = Path(__file__).resolve().parents[1] / "scripts" / "windows"
    ps1 = (win / "ciclo_automatico.ps1").read_text(encoding="utf-8")
    block = ps1[ps1.index('$p["accion"] -eq "ventana"'):]
    block = block[:block.index("} elseif")]
    assert "uv run --extra app tennisbio app comprobar $s --real" in block and "prueba_ventana.log" in block
    comun = (win / "comun.ps1").read_text(encoding="utf-8")
    assert comun.isascii() and "--extra app" in comun and "capturas_app" in comun
    assert '"--extra", "app"' in (win / "instalar.ps1").read_text(encoding="utf-8")
    vbs = (Path(__file__).resolve().parents[1] / "Tennisbio.vbs").read_text(encoding="utf-8")
    assert vbs.isascii() and "tennisbio app ventana" in vbs and ", 0, False" in vbs
