"""Requests #50 (progress and monitoring visible) and #66 (dates and durations in the logs): each stage says its
progress (%, time spent, time left) in the log and in <output>/progreso.json; every script and every request of the
PC writes when it started and when it ended. Run on the PC with the other tests (pruebas.xml), so the audit ties
both requests to this module; the audit also reads the real progreso.json and logs (audit.infrastructure_items)."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

from tennisbio import pipeline
from tennisbio.audit import log_dates

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "scripts" / "windows"


def test_a_stage_says_its_progress_in_the_log_and_in_progreso_json(tmp_path):
    lines = []
    d = tmp_path / "out" / "m1"
    d.mkdir(parents=True)
    ctx = pipeline.Context(SimpleNamespace(id="m1"), {}, d, log=lines.append, _prog={"stage": "fine"})
    ctx.progress(0, 10, "ventanas", every_s=0)
    ctx.progress(5, 10, "ventanas", every_s=0)
    p = json.loads((tmp_path / "out" / "progreso.json").read_text(encoding="utf-8"))
    assert (p["partido"], p["etapa"], p["hecho"], p["total"], p["porcentaje"]) == ("m1", "fine", 5, 10, 50.0)
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", p["hora"]) and "quedan_s" in p and "segundos" in p
    assert any(re.search(r"fine:\s+50 % \(5/10 ventanas\) · .+ · quedan ≈ ", ln) for ln in lines), lines
    ctx.progress(10, 10, "ventanas", every_s=3600)                 # the end is always said, whatever the interval
    assert json.loads((tmp_path / "out" / "progreso.json").read_text(encoding="utf-8"))["porcentaje"] == 100.0


def test_python_output_is_not_buffered_in_the_windows_scripts():
    """Without PYTHONUNBUFFERED the window showed nothing until the end (12-10)."""
    com = (WIN / "comun.ps1").read_text(encoding="ascii")
    assert '$env:PYTHONUNBUFFERED = "1"' in com


def test_every_step_of_the_double_click_scripts_has_its_date_and_the_run_its_total():
    com = (WIN / "comun.ps1").read_text(encoding="ascii")
    assert re.search(r"==> \[\{0:yyyy-MM-dd HH:mm:ss\}\]", com) and "paso terminado en" in com
    assert re.search(r"Empezado \{0:yyyy-MM-dd HH:mm:ss\} - terminado \{1:yyyy-MM-dd HH:mm:ss\} - duracion total", com)
    bad = []
    for f in WIN.glob("*.ps1"):
        t = f.read_text(encoding="ascii")
        if "Start-Transcript" in t and "Resumen-Tiempo" not in t:
            bad.append(f"{f.name}: graba su registro sin «Empezado … duracion total»")
    assert not bad, bad


def _actions(text: str) -> dict[str, str]:
    """Each request action of ciclo_automatico.ps1 → its block of code."""
    parts = re.split(r'(?=if \(\$p\["accion"\] -eq "[^"]+"\))', text)
    return {re.match(r'if \(\$p\["accion"\] -eq "([^"]+)"\)', p).group(1): p for p in parts[1:]}


def test_every_request_log_says_when_it_started_and_when_it_ended():
    """04-11 on the PC: «prevision» wrote when it started but never when it ended (the audit found it)."""
    acts = _actions((WIN / "ciclo_automatico.ps1").read_text(encoding="ascii"))
    assert len(acts) >= 15
    bad = []
    for name, body in acts.items():
        if "Set-Content $lg" not in body:
            continue                                   # its log is a transcript of a double-click script
        if not re.search(r'"Peticion \$\(\$p\[.id.\]\): .*\(\$\(Get-Date -Format s\)\)"', body):
            bad.append(f"{name}: sin la fecha de inicio")
        if not re.search(r"termina \$\(Get-Date -Format s\)", body):
            bad.append(f"{name}: sin «termina fecha»")
    assert not bad, bad


def test_the_audit_reads_the_logs_as_the_pc_writes_them():
    ok = "Peticion 98: prevision (2026-11-04T13:47:38)\n# Previsión\ncodigo de salida: 0; termina 2026-11-04T13:48:02\n"
    assert log_dates(ok, 86400) == ""
    assert log_dates(ok.rsplit("codigo", 1)[0], 86400) != ""
