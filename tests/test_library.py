"""The definitive storage (docs/almacenamiento.md): one test (or more) for every row of its case table
(nominal, edge, corner, error), plus the naming rules and the migration of the current output folders."""
import errno
import json
import os
import re
import shutil
from pathlib import Path, PureWindowsPath

import pytest

from tennisbio import library as lib
from tennisbio.library import (Library, LibraryError, analysis_dir, match_slug, player_slug, plan_migration,
                               apply, verify, migrate, read_journal)
from tennisbio.pipeline import video_sample

ALLOWED = re.compile(r"^[a-z0-9_-]+$")
AO = dict(date="2023-01-28", tournament="Australian Open", round="F", players=["Elena Rybakina", "Aryna Sabalenka"])


def video(p: Path, seed: str, size: int = 3000) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((seed.encode() * (size // len(seed) + 1))[:size])
    return p


@pytest.fixture
def L(tmp_path):
    with Library(tmp_path / "biblioteca") as library:
        yield library


# ---------------------------------------------------------------- names

def test_player_slug_rules():
    assert player_slug("Elena Rybakina") == "rybakina-elena"
    assert player_slug("Rybakina, Elena") == "rybakina-elena"
    assert player_slug("Елена Рыбакина") == "rybakina-elena"           # Cyrillic, same folder
    assert player_slug("Iga Świątek") == "swiatek-iga"
    assert player_slug("Barbora Krejčíková") == "krejcikova-barbora"
    assert player_slug("Olga Danilović") == "danilovic-olga"
    assert player_slug("Ольга Даниловић") == "danilovic-olga"           # Serbian Cyrillic (ћ)
    assert player_slug("Julia Görges") == "gorges-julia"
    assert player_slug("Anna-Lena Friedsam") == "friedsam-anna-lena"
    assert player_slug("Beatriz Haddad Maia") == "maia-beatriz-haddad"   # without a comma: last word
    assert player_slug("Haddad Maia, Beatriz") == "haddad-maia-beatriz"
    with pytest.raises(LibraryError, match="letras"):
        player_slug("??? !!!")


def test_long_names_are_cut_with_fingerprint_and_stay_distinct():
    a = player_slug("Maria Antonieta de las Nieves Fernandez Gutierrez de la Concepcion Primera")
    b = player_slug("Maria Antonieta de las Nieves Fernandez Gutierrez de la Concepcion Segunda")
    assert len(a) <= 40 and len(b) <= 40 and a != b and ALLOWED.match(a)


def test_match_slug_nominal_sorted_by_surname():
    s = match_slug("2023-01-28", "Australian Open", "F", ["Elena Rybakina", "Aryna Sabalenka"], "abcdef123456")
    assert s == "2023-01-28_australian-open_f_rybakina-sabalenka"
    assert match_slug("2023-01-28", "Australian Open", "F", ["Aryna Sabalenka", "Elena Rybakina"]) == s


def test_match_slug_only_lowercase_ascii_and_bounded():
    s = match_slug("2024-06-08", "Roland-Garros Paris — Tournoi Préféré " * 4, "Final ÉPREUVE",
                   ["Елена Рыбакина", "Iga Świątek"], "f00dbeef9999")
    assert ALLOWED.match(s) and s == s.lower()
    assert len(s) <= 80 and s.endswith("f00dbe")            # cut + 6 characters of the fingerprint


def test_same_surname_adds_the_given_name():
    s = match_slug("2017-01-28", "Australian Open", "F", ["Venus Williams", "Serena Williams"])
    assert s.endswith("_williams-serena-williams-venus")


def test_unknown_date_uses_fingerprint():
    s = match_slug(None, "Wimbledon", "R1", ["Elena Rybakina", "Aryna Sabalenka"], "a1b2c3d4e5f6")
    assert s.startswith("sin-fecha_a1b2c3_wimbledon")
    assert match_slug("31-31-2023", "W", "R1", ["A B"], "123456789").startswith("sin-fecha_123456")
    assert lib.match_year(None) == "sin-fecha" and lib.match_year("2023-01-28") == "2023"


def test_paths_analysis_tests_and_strokes(tmp_path):
    root = tmp_path / "biblioteca"
    assert analysis_dir(root, "Elena Rybakina", "forehand") == root / "analisis/rybakina-elena/forehand"
    assert analysis_dir(root, "rybakina-elena", "derecha") == root / "analisis/rybakina-elena/forehand"
    assert lib.export_dir(root, "rybakina-elena", "reves") == root / "exportar/rybakina-elena/backhand"
    assert lib.tests_dir(root, "_poc9_largo") == root / "pruebas/poc9_largo"
    with pytest.raises(LibraryError, match="Golpe desconocido"):
        analysis_dir(root, "rybakina-elena", "lob")


def test_library_root_from_config(tmp_path):
    assert lib.library_root({"paths": {"output": str(tmp_path / "output")}}) == tmp_path / "biblioteca"
    assert lib.library_root({"paths": {"library": str(tmp_path / "x")}}) == tmp_path / "x"


# ---------------------------------------------------------------- Nominal

def test_nominal_new_match(L, tmp_path):
    v = video(tmp_path / "videos/2023_AO_F.mp4", "ao-final")
    r = L.add_video(v, surface="dura", **AO)
    assert r.created and r.slug == "2023-01-28_australian-open_f_rybakina-sabalenka"
    assert r.dir == L.root / "partidos/2023" / r.slug
    data = json.loads((r.dir / "partido.json").read_text(encoding="utf-8"))
    assert data["torneo"] == "Australian Open" and data["superficie"] == "dura"
    assert data["emisiones"][0]["segmentos"][0]["huella"] == video_sample(v)
    assert [j["carpeta"] for j in data["jugadoras"]] == ["rybakina-elena", "sabalenka-aryna"]
    assert L.find_by_video(v) == r.slug and L.video_status(r.slug) == "disponible"
    assert L.analysis_dir("Elena Rybakina", "forehand") == L.root / "analisis/rybakina-elena/forehand"
    assert L.strokes_dir(r.slug, "Elena Rybakina") == r.dir / "golpes/rybakina-elena"
    for p in L.root.rglob("*"):                              # every name the library makes is [a-z0-9_-.]
        assert re.match(r"^[a-z0-9_.-]+$", p.name), p


def test_nominal_rival_reuses_the_cheap_pass(L, tmp_path):
    r = L.add_video(video(tmp_path / "v.mp4", "x"), **AO)
    stages = L.stages_dir(r.slug)
    mine, rival = L.strokes_dir(r.slug, "Elena Rybakina"), L.strokes_dir(r.slug, "Aryna Sabalenka")
    assert mine.parent == rival.parent == r.dir / "golpes" and stages == r.dir / "etapas"
    assert rival.name == "sabalenka-aryna" and L.matches() == [r.slug]


# ---------------------------------------------------------------- Edge (límite)

def test_edge_renamed_or_moved_video(L, tmp_path):
    v = video(tmp_path / "videos/a.mp4", "moved")
    r = L.add_video(v, **AO)
    (r.dir / "etapas").mkdir()
    (r.dir / "etapas/scenes.json").write_text("[]")
    before = (r.dir / "etapas/scenes.json").stat().st_mtime_ns
    new = tmp_path / "videos/2023/AO final renombrado.mp4"
    new.parent.mkdir(parents=True)
    shutil.move(v, new)
    r2 = L.add_video(new)                                    # no data given: recognised by content
    assert r2.slug == r.slug and r2.moved and not r2.created
    assert L.match(r.slug)["emisiones"][0]["segmentos"][0]["ruta"] == str(new)
    assert (r.dir / "etapas/scenes.json").stat().st_mtime_ns == before          # nothing recomputed
    assert L.add_video(new).moved is False                   # same path again: nothing changes


def test_edge_video_deleted_or_usb_unplugged(L, tmp_path):
    v = video(tmp_path / "usb_e/a.mp4", "usb")
    r = L.add_video(v, **AO)
    (r.dir / "golpes/rybakina-elena").mkdir(parents=True)
    (r.dir / "golpes/rybakina-elena/strokes.json").write_text("[]")
    v.unlink()
    assert L.video_status(r.slug) == "vídeo no disponible"
    assert L.video_paths(r.slug) == [None]
    assert (r.dir / "golpes/rybakina-elena/strokes.json").exists()            # results kept
    video(tmp_path / "usb_f/sub/a.mp4", "usb")               # the USB comes back with another letter
    found = L.relocate([tmp_path / "usb_f"])
    assert list(found.values()) == [str(tmp_path / "usb_f/sub/a.mp4")]
    assert L.video_status(r.slug) == "disponible"


def test_edge_match_in_several_files(L, tmp_path):
    a = L.add_video(video(tmp_path / "p1.mp4", "part-one"), segment=1, **AO)
    b = L.add_video(video(tmp_path / "p2.mp4", "part-two"), segment=2, **AO)
    assert a.slug == b.slug and b.segment == 2 and not b.created
    assert L.video_paths(a.slug) == [tmp_path / "p1.mp4", tmp_path / "p2.mp4"]
    with pytest.raises(LibraryError, match="segmento 2"):
        L.add_video(video(tmp_path / "p2b.mp4", "part-two-bis"), segment=2, **AO)
    c = L.add_video(video(tmp_path / "p3.mp4", "part-three"), match=a.slug)     # explicit: next segment
    assert c.segment == 3 and L.matches() == [a.slug]
    (tmp_path / "p2.mp4").unlink()
    assert L.video_status(a.slug) == "vídeo no disponible"   # a segment missing: not complete


def test_edge_summary_or_incomplete_match(L, tmp_path):
    r = L.add_video(video(tmp_path / "resumen.mp4", "highlights"), incomplete=True, **AO)
    d = L.match(r.slug)
    assert d["incompleto"] is True and "incompleto" in d["nota"].lower()


# ---------------------------------------------------------------- Corner (esquina)

def test_corner_same_final_from_another_channel(L, tmp_path):
    a = L.add_video(video(tmp_path / "eurosport.mp4", "es"), channel="eurosport", **AO)
    b = L.add_video(video(tmp_path / "espn.mp4", "espn"), channel="espn", **AO)
    assert a.slug == b.slug and b.emission == 2
    ems = L.match(a.slug)["emisiones"]
    assert [e["cadena"] for e in ems] == ["eurosport", "espn"]
    assert L.stages_dir(a.slug, 2) == a.dir / "etapas/emision-2"
    assert L.find_by_video(tmp_path / "espn.mp4") == a.slug


def test_corner_two_identical_matches_get_suffix(L, tmp_path):
    a = L.add_video(video(tmp_path / "m1.mp4", "first"), **AO)
    b = L.add_video(video(tmp_path / "m2.mp4", "second"), **AO)
    c = L.add_video(video(tmp_path / "m3.mp4", "third"), **AO)
    assert b.slug == a.slug + "-2" and c.slug == a.slug + "-3" and b.created
    assert sorted(L.matches()) == sorted([a.slug, b.slug, c.slug])


def test_corner_unknown_date(L, tmp_path):
    v = video(tmp_path / "x.mp4", "undated")
    r = L.add_video(v, tournament="Wimbledon", round="R1", players=["Elena Rybakina", "Aryna Sabalenka"])
    assert r.slug.startswith("sin-fecha_" + video_sample(v)[:6]) and r.dir.parent.name == "sin-fecha"
    r2 = L.add_video(video(tmp_path / "y.mp4", "bad-date"), date="el día de la final", tournament="W")
    assert r2.slug.startswith("sin-fecha_") and "fecha no reconocida" in L.match(r2.slug)["nota"]
    r3 = L.add_video(video(tmp_path / "z.mp4", "undated-2"), tournament="Wimbledon", round="R1",
                     players=["Elena Rybakina", "Aryna Sabalenka"])
    assert r3.slug != r.slug                                 # two undated videos are never merged on a guess


def test_corner_same_surname(L, tmp_path):
    r = L.add_video(video(tmp_path / "w.mp4", "williams"), date="2017-01-28", tournament="AO", round="F",
                    players=["Serena Williams", "Venus Williams"])
    assert r.slug.endswith("williams-serena-williams-venus")
    assert {j["carpeta"] for j in L.match(r.slug)["jugadoras"]} == {"williams-serena", "williams-venus"}


def test_corner_non_latin_and_long_names(L, tmp_path):
    r = L.add_video(video(tmp_path / "ru.mp4", "cyr"), date="2023-10-01", tournament="Кубок Кремля " * 6,
                    round="Финал", players=["Елена Рыбакина", "Арина Соболенко " * 5])
    assert ALLOWED.match(r.slug) and len(r.slug) <= 80 and r.slug.startswith("2023-10-01_kubok-kremlya")
    assert len(str(PureWindowsPath(r"C:\tenis\biblioteca", *r.dir.relative_to(L.root).parts))) < 240
    assert L.save_player("Елена Рыбакина", aliases=["RYBAKINA E.", "Elena Rybakina"]) == "rybakina-elena"
    card = (L.root / "jugadoras/rybakina-elena/ficha.yaml").read_text(encoding="utf-8")
    assert "Елена Рыбакина" in card and "RYBAKINA E." in card


def test_corner_long_windows_path(tmp_path):
    assert lib.root_warning(Path(r"C:\tenis\biblioteca")) == ""
    deep = Path("C:/" + "/".join(["carpeta-muy-larga-de-usuario"] * 3))
    assert "demasiado anidada" in lib.root_warning(deep)
    # the deepest path of a library at C:\tenis\biblioteca stays below 240
    slug = match_slug("2023-01-28", "x" * 200, "y" * 50, ["Z" * 80 + " W" * 30], "abcdef")
    deepest = PureWindowsPath(r"C:\tenis\biblioteca", "partidos", "2023", slug, "golpes",
                              player_slug("Z" * 80 + " W" * 30), "series", "s" * 40 + ".npz")
    assert len(str(deepest)) < 240
    with pytest.raises(LibraryError, match="Windows no la abre"):
        lib.check_length(Path("C:/" + "a" * 250))
    msgs = []
    Library(tmp_path / ("p" * 60) / ("q" * 60), log=msgs.append).close()
    assert msgs and "demasiado anidada" in msgs[0]


# ---------------------------------------------------------------- Error

def test_error_disk_full_half_way_leaves_nothing(L, tmp_path, monkeypatch):
    v = video(tmp_path / "a.mp4", "full")

    def full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(lib.os, "fsync", full)
    with pytest.raises(LibraryError, match="Disco lleno"):
        L.add_video(v, **AO)
    assert L.matches() == [] and not (L.root / "partidos").exists()       # not even an empty folder
    assert not list(L.root.rglob("*.tmp"))
    monkeypatch.undo()
    r = L.add_video(v, **AO)                                 # resumed: done once, no duplicate
    assert L.matches() == [r.slug] and r.slug.endswith("sabalenka")


def test_error_disk_full_keeps_the_previous_file(L, tmp_path, monkeypatch):
    r = L.add_video(video(tmp_path / "a.mp4", "keep"), **AO)
    before = (r.dir / "partido.json").read_bytes()
    shutil.move(tmp_path / "a.mp4", tmp_path / "b.mp4")
    monkeypatch.setattr(lib.os, "replace", lambda a, b: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    with pytest.raises(LibraryError, match="Disco lleno"):
        L.add_video(tmp_path / "b.mp4")
    assert (r.dir / "partido.json").read_bytes() == before and not list(r.dir.glob(".*tmp"))


def test_error_damaged_file(L, tmp_path):
    r = L.add_video(video(tmp_path / "a.mp4", "dmg"), **AO)
    (r.dir / "etapas").mkdir()
    (r.dir / "etapas/score.json").write_text('{"cut in ha')
    (r.dir / "partido.json").write_text("{not json")
    found = L.repair(r.slug)
    assert any("partido.json dañado" in m for m in found)
    assert any("etapas/score.json" in m and "recalcula" in m for m in found)
    assert json.loads((r.dir / "partido.json").read_text(encoding="utf-8"))["partido"] == r.slug
    assert list(r.dir.glob("partido.danado-*.json"))          # the damaged one is kept aside
    assert L.damaged_files(r.slug) == [r.dir / "etapas/score.json"]


def test_error_damaged_index_is_rebuilt(tmp_path):
    root = tmp_path / "biblioteca"
    with Library(root) as L:
        a = L.add_video(video(tmp_path / "a.mp4", "a"), **AO).slug
        b = L.add_video(video(tmp_path / "b.mp4", "b"), segment=2, **AO).slug
        c = L.add_video(video(tmp_path / "c.mp4", "c"), date="2024-07-13", tournament="Wimbledon", round="F",
                        players=["Elena Rybakina", "Jasmine Paolini"]).slug
    assert a == b
    (root / "datos/tennisbio.db").write_bytes(b"this is not a sqlite database at all" * 100)
    msgs = []
    with Library(root, log=msgs.append) as L:
        assert sorted(L.matches()) == sorted([a, c])
        assert L.find_by_video(tmp_path / "b.mp4") == a and L.match(a)["emisiones"][0]["segmentos"][1]["segmento"] == 2
        assert any("dañado" in m for m in msgs)
    assert list((root / "datos").glob("tennisbio.danado-*.db"))                 # kept, not deleted
    (root / "datos/tennisbio.db").unlink()                   # lost: rebuilt as well
    with Library(root) as L:
        assert sorted(L.matches()) == sorted([a, c])


def test_error_damaged_match_file_does_not_block_rebuild(tmp_path):
    root = tmp_path / "biblioteca"
    with Library(root) as L:
        a = L.add_video(video(tmp_path / "a.mp4", "a"), **AO)
        c = L.add_video(video(tmp_path / "c.mp4", "c"), date="2024-07-13", tournament="W", players=["A B"])
    (a.dir / "partido.json").write_text("garbage")
    with Library(root) as L:
        warns = L.rebuild()
        assert L.matches() == [c.slug] and warns and "dañado" in warns[0]
    assert (a.dir / "partido.json").read_text() == "garbage"                    # left for the user


def test_error_no_permission(L, tmp_path, monkeypatch):
    v = video(tmp_path / "a.mp4", "perm")

    def denied(a, b):
        raise PermissionError(errno.EACCES, "Access is denied", str(b))

    monkeypatch.setattr(lib.os, "replace", denied)
    with pytest.raises(LibraryError) as e:
        L.add_video(v, **AO)
    assert "Sin permiso para escribir" in str(e.value) and "nada a medias" in str(e.value)
    assert L.matches() == [] and not list(L.root.rglob("*.tmp")) and not list(L.root.rglob("partido.json"))


def test_error_source_video(L, tmp_path):
    with pytest.raises(LibraryError, match="No se encuentra el vídeo"):
        L.add_video(tmp_path / "nope.mp4", **AO)
    (tmp_path / "empty.mp4").write_bytes(b"")
    with pytest.raises(LibraryError, match="vacío"):
        L.add_video(tmp_path / "empty.mp4", **AO)
    with pytest.raises(LibraryError, match="ningún partido"):
        L.match("2099-01-01_x")


# ---------------------------------------------------------------- migration

PLAYERS = {"rybakina": "Elena Rybakina", "sabalenka": "Aryna Sabalenka"}


def old_output(tmp_path) -> tuple[Path, Path]:
    """A current <output> tree: one real match, its analysis, reports, test runs and things not ours."""
    out = tmp_path / "output"
    v = video(tmp_path / "videos/2023_AO_F.mp4", "the-final")
    m = out / "2023-ao-f"
    (m / "series").mkdir(parents=True)
    (m / "windows").mkdir()
    (m / "manifest.json").write_text('{"scenes": {}}')
    (m / "video.json").write_text(json.dumps({"fp": "123-456", "size": v.stat().st_size, "mtime": 1,
                                              "sample": video_sample(v)}))
    (m / "partido.json").write_text(json.dumps({"opponent": "Aryna Sabalenka", "tournament": "Australian Open",
                                                "date": "2023-01-28", "surface": "dura", "round": "F",
                                                "player": "rybakina"}))
    (m / "scenes.json").write_text("[]")
    (m / "players.npz").write_bytes(b"\x00" * 500)
    (m / "strokes.json").write_text("[1, 2]")
    (m / "strokes_opponent.json").write_text("[3]")
    (m / "series/a.npz").write_bytes(b"\x01" * 200)
    (m / "windows/w1.mp4").write_bytes(b"\x02" * 300)
    a = out / "analisis/rybakina_forehand"
    (a / "actual").mkdir(parents=True)
    (a / "actual/index.html").write_text("<html>")
    (a / "v1").mkdir()
    (a / "v1/index.html").write_text("<html>v1")
    (out / "informe_derecha").mkdir()
    (out / "informe_derecha/index.html").write_text("old")
    (out / "exportar_sabalenka_reves").mkdir()
    (out / "exportar_sabalenka_reves/resumen.pdf").write_bytes(b"%PDF")
    s = out / "_smoke/smoke_clip"
    s.mkdir(parents=True)
    (s / "manifest.json").write_text("{}")
    (out / "_poc9_largo/x").mkdir(parents=True)
    (out / "_poc9_largo/x/manifest.json").write_text("{}")
    (out / "notas_sueltas").mkdir()
    (out / "notas_sueltas/a.txt").write_text("not ours")
    (out / "datos").mkdir()
    return out, v


def snapshot(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def test_migration_plan_and_apply(tmp_path):
    out, v = old_output(tmp_path)
    before = snapshot(out)
    root = tmp_path / "biblioteca"
    stats = migrate(out, root, log=lambda m: None, players=PLAYERS, catalog={})
    assert stats["problemas"] == [] and stats["hechas"] == stats["total"]
    m = root / "partidos/2023/2023-01-28_australian-open_f_rybakina-sabalenka"
    assert (m / "etapas/scenes.json").exists() and (m / "etapas/manifest.json").exists()
    assert (m / "etapas/players.npz").exists() and (m / "etapas/video.json").exists()
    assert (m / "etapas/partido_origen.json").exists()
    assert (m / "golpes/rybakina-elena/strokes.json").read_text() == "[1, 2]"
    assert (m / "golpes/rybakina-elena/series/a.npz").exists() and (m / "golpes/rybakina-elena/windows/w1.mp4").exists()
    data = json.loads((m / "partido.json").read_text(encoding="utf-8"))
    assert data["origen"] == "2023-ao-f" and data["superficie"] == "dura"
    assert data["emisiones"][0]["segmentos"][0]["huella"] == video_sample(v)
    assert (root / "analisis/rybakina-elena/forehand/actual/index.html").exists()
    assert (root / "analisis/rybakina-elena/forehand/v1/index.html").exists()
    assert (root / "analisis/rybakina-elena/forehand/informe-antiguo/index.html").exists()
    assert (root / "exportar/sabalenka-aryna/backhand/antiguo/resumen.pdf").exists()
    assert (root / "pruebas/smoke/smoke_clip/manifest.json").exists()             # tests never beside real ones
    assert (root / "pruebas/poc9_largo/x/manifest.json").exists()
    assert not (root / "partidos" / "smoke_clip").exists()
    assert not list(root.rglob("notas_sueltas"))                                   # not ours: left in place
    assert snapshot(out) == before                                                 # the old folders untouched
    with Library(root) as L:                                 # the index knows it, the video by its content
        slug = m.name
        assert L.matches() == [slug] and L.video_status(slug) == "vídeo no disponible"
        assert L.relocate([tmp_path / "videos"]) and L.video_status(slug) == "disponible"
        assert L.find_by_video(v) == slug


def test_migration_is_idempotent(tmp_path):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    first = migrate(out, root, log=lambda m: None, players=PLAYERS, catalog={})
    tree = snapshot(root / "partidos")
    again = migrate(out, root, log=lambda m: None, players=PLAYERS, catalog={})
    assert again["hechas"] == 0 and again["saltadas"] == first["total"]
    assert snapshot(root / "partidos") == tree


def test_migration_interrupted_is_resumed_without_duplicates(tmp_path, monkeypatch):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = plan_migration(out, root, players=PLAYERS, catalog={})
    journal = root / "datos/migracion.jsonl"
    real, calls = lib._run_op, []

    def cut(o, dst):
        calls.append(o.id)
        if len(calls) == 5:
            raise KeyboardInterrupt                         # power cut half-way
        return real(o, dst)

    monkeypatch.setattr(lib, "_run_op", cut)
    with pytest.raises(KeyboardInterrupt):
        apply(ops, journal, root, log=lambda m: None)
    assert len(read_journal(journal)) == 4
    monkeypatch.setattr(lib, "_run_op", real)
    with open(journal, "a", encoding="utf-8") as f:
        f.write('{"op": "copy_fi')                          # a journal line cut by the crash: ignored
    stats = apply(ops, journal, root, log=lambda m: None)
    assert stats["saltadas"] == 4 and stats["hechas"] == len(ops) - 4
    lines = [json.loads(x)["op"] for x in journal.read_text(encoding="utf-8").splitlines() if x.endswith("}")]
    assert len(lines) == len(set(lines)) == len(ops)
    assert verify(ops, root) == [] and not list(root.rglob("*.partial")) and not list(root.rglob("*.tmp"))


def test_migration_crash_between_copy_and_journal(tmp_path):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = plan_migration(out, root, players=PLAYERS, catalog={})
    journal = root / "datos/migracion.jsonl"
    apply(ops, journal, root, log=lambda m: None)
    journal.unlink()                                        # copies done, journal lost
    stats = apply(ops, journal, root, log=lambda m: None)   # recognised as done: no duplicate, no error
    assert stats["hechas"] == len(ops) and verify(ops, root) == []
    assert not list(root.rglob("*-2"))


def test_migration_partial_copy_is_redone(tmp_path):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = plan_migration(out, root, players=PLAYERS, catalog={})
    tree = next(o for o in ops if o.kind == "copy_tree" and o.dst.endswith("/series"))
    partial = root / (tree.dst + ".partial")
    partial.mkdir(parents=True)
    (partial / "a.npz").write_bytes(b"\x01" * 7)            # a copy cut half-way
    apply(ops, root / "datos/migracion.jsonl", root, log=lambda m: None)
    assert (root / tree.dst / "a.npz").stat().st_size == 200 and not partial.exists()


def test_migration_disk_full_mid_copy_then_resumed(tmp_path, monkeypatch):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = plan_migration(out, root, players=PLAYERS, catalog={})
    journal = root / "datos/migracion.jsonl"
    real, n = shutil.copy2, []

    def full(src, dst, *a, **k):
        n.append(src)
        if len(n) == 3:
            Path(dst).write_bytes(b"half")                  # half a file, then the disk is full
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(lib.shutil, "copy2", full)
    with pytest.raises(LibraryError, match="Disco lleno"):
        apply(ops, journal, root, log=lambda m: None)
    assert not [p for p in root.rglob("*") if p.is_file() and p.read_bytes() == b"half"]   # nothing half-written
    monkeypatch.setattr(lib.shutil, "copy2", real)
    apply(ops, journal, root, log=lambda m: None)
    assert verify(ops, root) == []


def test_migration_disk_full_inside_a_folder_copy(tmp_path, monkeypatch):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = plan_migration(out, root, players=PLAYERS, catalog={})
    journal = root / "datos/migracion.jsonl"
    real = shutil.copytree

    def full(src, dst, *a, **k):
        if Path(src).name == "series":
            Path(dst).mkdir(parents=True)
            (Path(dst) / "a.npz").write_bytes(b"half")
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(lib.shutil, "copytree", full)
    with pytest.raises(LibraryError, match="Disco lleno"):
        apply(ops, journal, root, log=lambda m: None)
    series = next(o.dst for o in ops if o.dst.endswith("/series"))
    assert not (root / series).exists() and not list(root.rglob("*.partial"))
    monkeypatch.setattr(lib.shutil, "copytree", real)
    apply(ops, journal, root, log=lambda m: None)
    assert verify(ops, root) == [] and (root / series / "a.npz").stat().st_size == 200


def test_migration_not_enough_space_stops_before_copying(tmp_path, monkeypatch):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    monkeypatch.setattr(lib, "_free_bytes", lambda p: 10.0)
    with pytest.raises(LibraryError, match="No hay espacio"):
        migrate(out, root, log=lambda m: None, players=PLAYERS, catalog={})
    assert not (root / "partidos").exists()


def test_migration_permission_error(tmp_path, monkeypatch):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = plan_migration(out, root, players=PLAYERS, catalog={})

    def denied(*a, **k):
        raise PermissionError(errno.EACCES, "Access is denied")

    monkeypatch.setattr(lib.shutil, "copytree", denied)
    monkeypatch.setattr(lib.shutil, "copy2", denied)
    with pytest.raises(LibraryError, match="Sin permiso para escribir"):
        apply(ops, root / "datos/migracion.jsonl", root, log=lambda m: None)
    assert not list(root.rglob("*.partial")) and not list(root.rglob("*.tmp"))


def test_migration_collisions_and_duplicates(tmp_path):
    out, v = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    with Library(root) as L:                                # the library already has a match with that name
        L.add_video(video(tmp_path / "other.mp4", "another-broadcast"), **AO)
    shutil.copytree(out / "2023-ao-f", out / "2023-ao-f-copia")        # same video analysed twice
    v2 = video(tmp_path / "videos/rematch.mp4", "rematch")              # same day/tournament/round/players
    shutil.copytree(out / "2023-ao-f", out / "2023-ao-f-bis")
    rec = json.loads((out / "2023-ao-f-bis/video.json").read_text())
    rec["sample"] = video_sample(v2)
    (out / "2023-ao-f-bis/video.json").write_text(json.dumps(rec))
    ops = plan_migration(out, root, players=PLAYERS, catalog={})
    dsts = {o.dst for o in ops if o.kind == "write_json"}
    base = "partidos/2023/2023-01-28_australian-open_f_rybakina-sabalenka"
    assert dsts == {f"{base}-2/partido.json", f"{base}-3/partido.json"}
    assert any(o.dst == "pruebas/duplicados/2023-ao-f-copia" for o in ops)


def test_migration_uses_catalogue_when_no_match_file(tmp_path):
    out, _ = old_output(tmp_path)
    (out / "2023-ao-f/partido.json").unlink()
    cat = {"2023-ao-f": {"player": "rybakina", "opponent": "Aryna Sabalenka", "tournament": "Australian Open",
                         "date": "2023-01-28", "round": "F"}}
    ops = plan_migration(out, tmp_path / "biblioteca", players=PLAYERS, catalog=cat)
    assert any(o.dst.endswith("2023-01-28_australian-open_f_rybakina-sabalenka/partido.json") for o in ops)


def test_migration_of_nothing(tmp_path):
    assert plan_migration(tmp_path / "missing", tmp_path / "b", players={}, catalog={}) == []


def test_error_index_cannot_be_opened(tmp_path, monkeypatch):
    def locked(*a, **k):
        raise lib.sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(lib.sqlite3, "connect", locked)
    with pytest.raises(LibraryError, match="permiso de escritura"):
        Library(tmp_path / "biblioteca")
    assert not list((tmp_path / "biblioteca").rglob("*.db"))


def test_error_folder_copy_reports_disk_full(tmp_path, monkeypatch):
    out, _ = old_output(tmp_path)
    root = tmp_path / "biblioteca"
    ops = [o for o in plan_migration(out, root, players=PLAYERS, catalog={}) if o.kind == "copy_tree"][:1]

    def gathered(src, dst, *a, **k):
        Path(dst).mkdir(parents=True)
        raise shutil.Error([(str(src), str(dst), "[Errno 28] No space left on device")])

    monkeypatch.setattr(lib.shutil, "copytree", gathered)
    with pytest.raises(LibraryError, match="Disco lleno"):
        apply(ops, root / "datos/migracion.jsonl", root, log=lambda m: None)
    assert not list(root.rglob("*.partial"))
