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
