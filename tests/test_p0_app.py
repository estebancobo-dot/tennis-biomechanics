"""P0.5a (15-11, #305): the new application (ui/ built into app/p0/index.html) with made-up data, walked in a browser."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from tennisbio.app import p0_app

ROOT = Path(__file__).resolve().parents[1]
# pieces of the walk that later steps bring (docs/p0_plan.md §3 bis): the situations' table cells come with P0.5c
PENDING = {"no está: [data-cell]"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_built_page_is_the_one_of_its_sources():
    """The interface is built in Claude's cloud (the PC has no Node) and the build goes to the repository: it must be
    the build of the sources that are there (scripts/construir_ui.py writes their fingerprint)."""
    build = _load("construir_ui", ROOT / "scripts" / "construir_ui.py")
    stamp = (ROOT / "src" / "tennisbio" / "app" / "p0" / "huella.txt").read_text(encoding="utf-8").strip()
    assert stamp == build.fingerprint(), "ui/ cambió sin volver a construir: python scripts/construir_ui.py"


def test_the_data_go_into_the_page_safely():
    d = p0_app.ejemplo()
    d["known"] = ["</script><script>alert(1)</script>"]
    html = p0_app.pagina(d)
    assert p0_app.SLOT not in html and "<\\/script><script>alert(1)<\\/script>" in html
    assert "</script><script>alert(1)" not in html
    assert d["ejemplo"] is True and all("ejemplo" in p["name"] for p in d["players"])


def test_the_example_is_walked_without_errors():
    """Every screen, panel, phase and tab of the application opens without a JavaScript error and nothing overflows at
    the desktop widths (#301) — the same walk as the validated mockup's (design/p0/recorrer_maqueta.py)."""
    pytest.importorskip("playwright")
    walk = _load("recorrer_maqueta", ROOT / "design" / "p0" / "recorrer_maqueta.py")
    html = p0_app.pagina(p0_app.ejemplo())
    for w, h in ((1920, 1080), (1280, 800)):
        r = walk.walk(html, w, h)
        assert [e for e in r["errores"] if e not in PENDING] == [], r["errores"]
        assert r["desborde"] == {}, r["desborde"]
        names = set(r["estados"])
        for s in walk.MANAGEMENT + ("partido_ficha", "anadir_1", "anadir_5", "golpes", "golpe"):
            assert s in names, s
        assert sum(n.startswith("leccion_fase_") for n in names) == 9
        assert all(f"mas_{s}" in names for s in walk.MORE)
        assert "Datos de ejemplo" in r["estados"]["inicio"]
