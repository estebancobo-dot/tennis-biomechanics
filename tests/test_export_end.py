"""Request 232 (27-10: the backhand export hung, twice): the audit says, for every export folder beside the reports
(not only the forehand one), whether its last export ended; an export cut or hung is «falta», never «ok»."""
import json
import os

from tennisbio.audit import export_end_items, file_tree_items, petition_items
from tennisbio.export import END_RECORD


def _folder(root, name, *, pdf_at=None, pila_at=None, en_curso=None, record=None):
    d = root / name
    (d / "golpes").mkdir(parents=True)
    (d / "golpes" / "g1.mp4").write_bytes(b"x")
    for fn, at in (("resumen.pdf", pdf_at), ("pila.txt", pila_at)):
        if at is not None:
            (d / fn).write_text("x", encoding="utf-8")
            os.utime(d / fn, (at, at))
    if en_curso is not None:
        (d / "en_curso.txt").write_text(en_curso, encoding="utf-8")
    if record is not None:
        (d / END_RECORD).write_text(json.dumps(record), encoding="utf-8")
    return d


def _by_name(items):
    return {i["name"].split(": ", 1)[1]: i for i in items}


def test_every_export_folder_is_checked_not_only_the_forehand(tmp_path):
    _folder(tmp_path, "exportar_derecha", record={"ended": "2026-11-04 17:41:52", "seconds": 600, "strokes": 450,
                                                  "videos": 450, "failed": []})
    _folder(tmp_path, "exportar_reves", record={"ended": "2026-11-04 17:54:01", "seconds": 300, "strokes": 289,
                                                "videos": 289, "failed": []})
    (tmp_path / "informe_derecha").mkdir()            # not an export
    it = _by_name(export_end_items(tmp_path))
    assert set(it) == {"exportar_derecha", "exportar_reves"}
    assert all(i["status"] == "ok" for i in it.values()) and "289 vídeos de 289 golpes" in it["exportar_reves"]["detail"]


def test_a_cut_or_hung_export_is_a_failure(tmp_path):
    # cut by the Windows script after 10 min without moving: en_curso.txt short of the total, no end record
    _folder(tmp_path, "exportar_reves", pdf_at=1000, pila_at=5000, en_curso="m-0123 2026-10-27 09:24:00 37/289")
    # hung on its first stroke (no en_curso.txt yet): the summary PDF is older than this export's start
    _folder(tmp_path, "exportar_saque", pdf_at=1000, pila_at=5000)
    it = _by_name(export_end_items(tmp_path))
    assert it["exportar_reves"]["status"] == "falta" and "37/289" in it["exportar_reves"]["detail"]
    assert it["exportar_saque"]["status"] == "falta" and "no terminó" in it["exportar_saque"]["detail"]


def test_strokes_that_could_not_be_exported_are_a_failure(tmp_path):
    _folder(tmp_path, "exportar_reves", record={"ended": "x", "seconds": 60, "strokes": 3, "videos": 2,
                                                "failed": [{"id": "m-007", "error": "índice fuera de rango"}]})
    i = _by_name(export_end_items(tmp_path))["exportar_reves"]
    assert i["status"] == "falta" and "m-007" in i["detail"]


def test_an_export_before_the_end_record_is_judged_by_its_dates(tmp_path):
    _folder(tmp_path, "exportar_reves", pdf_at=9000, pila_at=5000, en_curso="m-288 2026-11-04 17:54:01 289/289")
    _folder(tmp_path, "exportar_saque", pdf_at=9000)                       # no pila.txt: older than the 27-10 code
    it = _by_name(export_end_items(tmp_path))
    assert it["exportar_reves"]["status"] == "ok"
    assert it["exportar_saque"]["status"] == "aviso"


def test_an_export_that_stops_leaves_no_end_record(tmp_path, monkeypatch):
    """The record of the export before is removed when the next one starts: one that dies or is killed half way
    does not inherit the «terminó» of the one before."""
    import pytest
    from tennisbio import export as E
    d = _folder(tmp_path, "exportar_reves", record={"ended": "antes", "seconds": 1, "strokes": 1, "videos": 1, "failed": []})

    def dies(*a, **k):
        assert not (d / END_RECORD).exists()        # already gone while it runs
        raise KeyboardInterrupt
    monkeypatch.setattr(E, "_export", dies)
    monkeypatch.setattr(E.shutil, "which", lambda _: "ffmpeg")
    with pytest.raises(KeyboardInterrupt):
        E.export([], tmp_path, d)
    assert not (d / END_RECORD).exists() and (d / "pila.txt").exists()
    assert export_end_items(tmp_path)[0]["status"] == "falta"        # no record and no PDF of this export


def test_request_232_sees_the_backhand_export(tmp_path):
    """The items reach #232 through its rule («Exportación»): a hung backhand export makes the request fail."""
    rep = tmp_path / "informe_derecha"
    rep.mkdir()
    _folder(tmp_path, "exportar_reves", pdf_at=1000, pila_at=5000, en_curso="m-0123 2026-10-27 09:24:00 37/289")
    items = file_tree_items([], rep, tmp_path)
    assert any(i["name"] == "Exportación terminada: exportar_reves" and i["status"] == "falta" for i in items)
    p = next(i for i in petition_items(items) if i["name"].startswith("#232 "))
    assert p["status"] == "falta" and "exportar_reves" in p["detail"]


def test_the_export_summary_fails_with_an_empty_video_or_no_pdf(tmp_path):
    # 11-12 (R1 of the review of the Base): «Exportación: resumen PDF y un vídeo por golpe» had never been seen failing
    rep = tmp_path / "informe_derecha"
    rep.mkdir()
    g = tmp_path / "exportar_derecha" / "golpes"
    g.mkdir(parents=True)
    (g / "a.mp4").write_bytes(b"x" * 10)
    (g / "b.mp4").write_bytes(b"")                                    # empty: the export did not write it
    name = "Exportación: resumen PDF y un vídeo por golpe"
    it = next(i for i in file_tree_items([], rep, tmp_path) if i["name"] == name)
    assert it["status"] == "falta" and "vacíos: b.mp4" in it["detail"] and "falta resumen.pdf" in it["detail"]
    (g / "b.mp4").write_bytes(b"x" * 10)
    (tmp_path / "exportar_derecha" / "resumen.pdf").write_bytes(b"%PDF-1.4 x")
    assert next(i for i in file_tree_items([], rep, tmp_path) if i["name"] == name)["status"] == "ok"
