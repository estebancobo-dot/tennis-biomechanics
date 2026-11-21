"""P0.5e-D (21-11): the PC's application checked with the cloud's real results without the PC: a real browser opens each
stroke's panel and the body layer must be drawn on her points; only numbers leave the session."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tennisbio.app import p0_app
from tennisbio.infra import poc_app

ROOT = Path(__file__).resolve().parents[1]


def test_the_rule_counts_videos_and_bodies_on_her_points():
    ok = {"ancho": 1280, "puntos": 3, "dibujados": 3}
    rows = [ok] * 19 + [{"ancho": 1280, "puntos": 3, "dibujados": 1}]
    s = poc_app.summarise(rows, [])
    assert s["con_video"] == 20 and s["cuerpo_en_sus_puntos"] == 19 and s["regla"]["pasa"] is True   # 95 %
    assert poc_app.summarise(rows[:18] + [{"ancho": 0}, {"error": "4"}], [])["regla"]["pasa"] is False
    assert poc_app.summarise([ok], ["TypeError: x"])["regla"]["pasa"] is False                       # a page error
    assert poc_app.summarise([], [])["regla"]["pasa"] is False


def test_a_real_browser_finds_her_body_drawn_on_her_points(tmp_path):
    pytest.importorskip("playwright")
    if not shutil.which("ffmpeg"):
        pytest.skip("sin ffmpeg")
    media = tmp_path / "nube" / "informe_derecha"
    (media / "series").mkdir(parents=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=25:d=3",
                    "-c:v", "libvpx", "-b:v", "200k", str(media / "clip.webm")], check=True)
    pts = [160, 40, 155, 35, 165, 35, 150, 38, 170, 38, 140, 70, 180, 70, 130, 100, 190, 100, 125, 130, 195, 130,
           145, 140, 175, 140, 140, 180, 180, 180, 138, 220, 182, 220]
    ser = {"fps": 25, "first": 0, "impact": 25, "n": 75, "kp": [pts] * 75}
    (media / "series" / "s1.js").write_text(f'window.SERIES["s1"]={json.dumps(ser)};', encoding="utf-8")
    d = p0_app.ejemplo()
    d["medios"] = "nube/informe_derecha/"
    d["strokes"][0].update(id="s1", video="clip.webm", series="series/s1.js", vImpact=1.0, quality=1.0)
    page = tmp_path / "app.html"
    page.write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>' + p0_app.pagina(d) + "</body></html>",
                    encoding="utf-8")
    res = poc_app.probe(page, 200, channel="")
    rows = {r["id"]: r for r in res["filas"]}
    assert rows["s1"]["ancho"] == 320 and rows["s1"]["puntos"] == 3 and rows["s1"]["dibujados"] == 3, rows["s1"]
    assert not res["errores_pagina"]
    others = [r for k, r in rows.items() if k != "s1"]
    assert others and all(r["estado"] == "sin-video" for r in others)          # the example's strokes have no video


def test_the_page_is_made_as_the_window_makes_it(tmp_path, monkeypatch):
    from tennisbio.app import p0_ventana
    seen = {}

    def fake(out_root, store, work, cloud_dir=None, page_dir=None):
        seen.update(out_root=out_root, cloud_dir=cloud_dir, page_dir=page_dir)
        return {**p0_app.ejemplo(), "medios": "../nube/informe_derecha/"}, "el informe de la nube (hecho el x)"
    monkeypatch.setattr(p0_ventana, "build_data", fake)
    page, info = poc_app.make_page(tmp_path)
    assert page.exists() and seen["cloud_dir"] == tmp_path / "nube" and seen["page_dir"] == tmp_path / "aplicacion_nueva"
    assert info["origen"].startswith("el informe de la nube") and info["medios"] == "../nube/informe_derecha/"


def test_kaggle_brings_the_results_and_chrome_then_probes():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    j = correr.parse_job('{"accion": "medir", "prueba": "app"}')
    assert correr.poc_args(j, Path("/d/models/models"), None) == ["--raiz", "/d/models/app"]
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert '"install", "--with-deps", "chrome"' in src and 'bring_results(vol, models.parent / "app" / "nube")' in src
    assert "from tennisbio.app import p0_nube" in src
