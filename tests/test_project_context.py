"""Request #136 «¿lo puedes añadir al contexto o fichero base?» (13-10): the views per stroke the user asked for are in
the project's base file (CLAUDE.md, read at the start of every session), each one tied to its check in the audit,
and the base file points to the state and to the registry of requests. Run on the PC with the other tests
(pruebas.xml), so the audit ties #136 to this module."""
import re
from pathlib import Path

from tennisbio.audit import PETITIONS

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ["La bola y ella", "Bajar y subir", "Base", "Tronco al terminar"]


def _section(md: str, title: str) -> str:
    m = re.search(r"^## " + re.escape(title) + r".*?$(.*?)(?=^## |\Z)", md, re.M | re.S)
    return m.group(1) if m else ""


def test_the_views_per_stroke_are_in_the_base_file():
    md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    sec = _section(md, "Vistas por golpe pedidas por el usuario")
    assert sec, "CLAUDE.md sin la sección «Vistas por golpe pedidas por el usuario»"
    missing = [v for v in VIEWS if f"- **{v}**:" not in sec]
    assert not missing, missing
    assert "su comprobación en la auditoría" in sec


def test_each_view_of_the_base_file_has_its_check_in_the_audit():
    src = (ROOT / "src" / "tennisbio" / "audit.py").read_text(encoding="utf-8")
    assert not [v for v in VIEWS if f"«{v}»" not in src]
    rules = [r for r in PETITIONS.values() if type(r) is str]
    for v in VIEWS:
        assert any(re.search(r, f"«{v}»: fotogramas") for r in rules), v


def test_the_base_file_points_to_where_a_session_starts():
    md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for doc in ("docs/estado_proyecto.md", "docs/matriz_cobertura.md"):
        assert f"`{doc}`" in md and (ROOT / doc).exists(), doc
