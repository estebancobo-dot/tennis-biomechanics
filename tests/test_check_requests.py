"""The register of user requests cannot hide anything (docs/revision_peticiones_19-10.md)."""
import json
import sys
from pathlib import Path

from tennisbio import audit as A
from tennisbio import requests_check as R

ROOT = Path(__file__).resolve().parents[1]
HEAD = "| # | Petición | Estado | Dónde está (código) | Dónde se ve en la web | Cómo se valida solo | Qué falta |\n|---|---|---|---|---|---|---|\n"


def _reg(tmp_path, rows: str) -> Path:
    p = tmp_path / "reg.md"
    p.write_text(HEAD + rows, encoding="utf-8")
    return p


def test_real_register_is_consistent():
    rows = R.parse()
    assert len(rows) >= 217
    assert R.problems(rows) == []
    assert R.header_problems(R.REGISTER, rows) == []


def test_requests_the_user_repeated_are_in_the_register_and_not_done():
    """The three requests lost before 19-10 must be rows, and stay visible until they are built."""
    rows = {r.n: r for r in R.parse()}
    text = {n: r.text.lower() for n, r in rows.items()}
    for words in ("golpe angulado", "bola corta baja cerca de la red", "bola corta alta cerca de la red", "volea a media pista"):
        hit = [n for n, t in text.items() if words in t]
        assert hit, words
        # until built: when one becomes HECHO, test_real_register_is_consistent already demands its evidence
        assert all(rows[n].status in ("PARCIAL", "FALTA", "HECHO") for n in hit)
        assert any(rows[n].status != "HECHO" for n in hit) or all(rows[n].code not in R.EMPTY for n in hit)
    pend = R.pending_markdown()
    assert "SIN TERMINAR" in pend and "angulado" in pend and "volea a media pista" in pend


def test_canonical_statuses():
    assert R.canonical("HECHO") == "HECHO"
    assert R.canonical("HECHO (como «no medible»)") == "NO MEDIBLE"
    assert R.canonical("NO (pendiente por diseño)") == "FALTA"
    assert R.canonical("NO APLICA (19-10)") == "NO APLICA"
    assert R.canonical("PARCIAL (19-10)") == "PARCIAL"
    assert R.canonical("**FALTA**") == "FALTA"
    assert R.canonical("") is None
    assert R.canonical("listo") is None


def test_errors_are_caught(tmp_path):
    p = _reg(tmp_path,
             "| 1 | sin estado | | `learn.py` | — | — | — |\n"
             "| 2 | hecho sin prueba | HECHO | — | — | — | — |\n"
             "| 3 | hecho con código inventado | HECHO | `learn.NO_EXISTE_ESTO`, `no_existe.py` | — | — | — |\n"
             "| 4 | a medias sin decir qué falta | PARCIAL | `learn.py` | — | — | — |\n"
             "| 4 | número repetido | HECHO | `learn.CONDITIONS` | — | — | — |\n"
             "| 5 | bien | HECHO | `learn.CONDITIONS`, `technique.contact_type`, `report_template.html` | — | — | — |\n")
    errs = "\n".join(R.problems(R.parse(p)))
    assert "#1: sin estado" in errs
    assert "#2: HECHO sin prueba" in errs
    assert "learn.NO_EXISTE_ESTO" in errs and "no_existe.py" in errs
    assert "#4: PARCIAL sin decir qué falta" in errs
    assert "#4: número repetido" in errs
    assert "#5" not in errs


def test_header_counts_must_match(tmp_path):
    p = tmp_path / "reg.md"
    p.write_text("| Estado | Nº |\n|---|---|\n| HECHO | 2 |\n| PARCIAL | 0 |\n| FALTA | 1 |\n| NO MEDIBLE | 0 |\n"
                 "| NO APLICA | 0 |\n| **Total** | **3** |\n\n" + HEAD +
                 "| 1 | a | HECHO | `learn.CONDITIONS` | — | — | — |\n| 2 | b | FALTA | — | — | — | todo |\n", encoding="utf-8")
    errs = R.header_problems(p)
    assert any("HECHO" in e for e in errs) and any("total" in e for e in errs)


def test_pending_lists_falta_first():
    rows = [R.Row(1, "uno", "PARCIAL", "`learn.py`", "", "", "algo"), R.Row(2, "dos", "FALTA", "", "", "", "todo"),
            R.Row(3, "tres", "HECHO", "`learn.py`", "", "", "")]
    md = R.pending_markdown(rows)
    assert "SIN TERMINAR: 2 de 3" in md
    assert md.index("#2 [FALTA]") < md.index("#1 [PARCIAL]")
    assert "#3" not in md


def test_audit_never_hides_unfinished_requests(monkeypatch):
    rows = [(1, "pedida y sin hacer (19-10 08:11)", "FALTA"), (2, "a medias con nota", "PARCIAL"),
            (3, "a medias sin regla", "PARCIAL"), (4, "hecha con nota", "HECHO"), (5, "no aplica", "NO APLICA")]
    monkeypatch.setattr(A, "parse_petitions", lambda: rows)
    monkeypatch.setattr(A, "PETITIONS", {1: A.Note("x"), 2: A.Note("proceso"), 4: A.Note("proceso")})
    st = {i["name"].split(" ")[0]: i["status"] for i in A.petition_items([])}
    assert st == {"#1": "falta", "#2": "aviso", "#3": "aviso", "#4": "ok"}


def test_audit_markdown_starts_with_the_unfinished_requests():
    res = {"stroke": "forehand", "near": 0, "summary": {"ok": 1, "falta": 0, "pocos datos": 0, "aviso": 0},
           "items": [{"req": 1, "area": "x", "name": "algo", "status": "ok", "detail": ""}]}
    md = A.to_markdown(res)
    assert md.index("Peticiones del usuario SIN TERMINAR") < md.index("## 1.")


def test_variants_the_user_named_are_reported_missing(tmp_path):
    res = A.audit([], None)
    names = {i["name"]: i["status"] for i in res["items"] if i["area"] == "Situaciones"}
    for label in A.VARIANTS_NOT_BUILT:
        assert names.get(label) == "falta"


def test_automatic_review_shows_the_unfinished_requests(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import auto_cycle
    new, old = tmp_path / "a.json", tmp_path / "b.json"
    for f in (new, old):
        f.write_text(json.dumps({"items": [{"name": "x", "area": "y", "status": "ok", "detail": ""}]}), encoding="utf-8")
    verdict, md = auto_cycle.review(new, old, [])
    assert verdict == "OK"
    assert "SIN TERMINAR" in md and md.index("SIN TERMINAR") < 400


def test_check_requests_script_passes_on_the_real_register(capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_requests
    assert check_requests.main([]) == 0
    assert "SIN TERMINAR" in capsys.readouterr().out
