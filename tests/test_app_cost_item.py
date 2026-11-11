import json

from tennisbio.audit import APP_COST_ITEM, app_cost_item


def _w(tmp_path, **r):
    (tmp_path / "capturas_diag").mkdir(exist_ok=True)
    (tmp_path / "capturas_diag" / "app_recursos.json").write_text(json.dumps(r), encoding="utf-8")
    return app_cost_item([tmp_path], today="2026-11-12")


def test_a_light_window_passes_and_a_heavy_or_broken_one_fails(tmp_path):
    assert app_cost_item([tmp_path])["status"] == "aviso"                        # never measured
    it = _w(tmp_path, fecha="2026-11-12 01:00:00", cpu_media_pct=1.2, cpu_max_pct=3.0, ram_max_mb=420, procesos=6)
    assert it["name"] == APP_COST_ITEM and it["status"] == "ok"
    assert _w(tmp_path, fecha="2026-11-12 01:00:00", cpu_media_pct=12.0, ram_max_mb=420)["status"] == "falta"
    assert _w(tmp_path, fecha="2026-11-12 01:00:00", cpu_media_pct=1.0, ram_max_mb=2000)["status"] == "falta"
    assert _w(tmp_path, fecha="2026-11-12", error="la ventana se cerró sola (código 1)")["status"] == "falta"
    assert _w(tmp_path, fecha="2026-10-01 01:00:00", cpu_media_pct=1.0, ram_max_mb=300)["status"] == "aviso"   # old
