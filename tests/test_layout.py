import json

from tennisbio import layout
from tennisbio.catalog import Match, Player


def _setup(tmp_path, active: bool):
    out, lib = tmp_path / "output", tmp_path / "biblioteca"
    out.mkdir()
    video = tmp_path / "videos" / "final.mp4"
    video.parent.mkdir()
    video.write_bytes(b"x" * 5000)
    cfg = {"paths": {"output": str(out), "library": str(lib)}}
    if active:
        assert layout.activate(lib, {"problemas": []})
    m = Match("us-open-final", video, Player("rybakina", "Elena Rybakina"), opponent="Aryna Sabalenka",
              tournament="US Open", date="2026-09-12", round="F")
    return out, lib, cfg, m


def test_before_the_switch_the_flat_folder(tmp_path):
    out, lib, cfg, m = _setup(tmp_path, active=False)
    assert layout.library_active(cfg) is None
    assert layout.dir_of(out, m, cfg) == out / "us-open-final"


def test_after_the_switch_the_library_folder_found_by_the_video(tmp_path):
    out, lib, cfg, m = _setup(tmp_path, active=True)
    d = layout.dir_of(out, m, cfg)
    assert d.parent.parent == lib / "partidos" and d.parent.name == "2026"
    assert (d / "etapas").is_dir()
    assert json.loads((d / "partido.json").read_text(encoding="utf-8"))["jugadora"] == "rybakina-elena"
    moved = m.video.rename(tmp_path / "videos" / "renombrado.mp4")     # same content, new name: same folder
    m.video = moved
    assert layout.dir_of(out, m, cfg) == d
    assert layout.dir_of(tmp_path / "otra_raiz", m, cfg) == tmp_path / "otra_raiz" / "us-open-final"   # test runs


def test_no_switch_when_the_copy_has_problems(tmp_path):
    assert not layout.activate(tmp_path / "lib", {"problemas": ["Falta partidos/x"]})
    assert not (tmp_path / "lib" / "datos" / layout.ACTIVE).exists()


def test_a_migrated_match_recomputes_nothing(tmp_path, monkeypatch):
    from tennisbio import library, pipeline

    reg, calls = {}, []
    monkeypatch.setattr(pipeline, "STAGES", reg)

    @pipeline.stage("scenes", "1", outputs=("scenes.json",))
    def scenes(ctx):
        calls.append("scenes"); ctx.path("scenes.json").write_text("{}")

    @pipeline.stage("fine", "1", deps=("scenes",), outputs=("strokes.json",))
    def fine(ctx):
        calls.append("fine"); ctx.path("strokes.json").write_text("[]")
        ctx.path("windows").mkdir(exist_ok=True); ctx.path("windows/w1.mp4").write_bytes(b"v")

    out, lib, cfg, m = _setup(tmp_path, active=False)
    flat = out / m.id
    assert pipeline.run(pipeline.Context(m, cfg, flat, log=lambda *_: None)) == ["scenes", "fine"]
    stats = library.migrate(out, lib, log=lambda *_: None, players={"rybakina": "Elena Rybakina"},
                            catalog={m.id: {"date": m.date, "tournament": m.tournament, "round": m.round,
                                            "players": ["Elena Rybakina", "Aryna Sabalenka"], "player": "rybakina"}},
                            main_player="rybakina")
    assert stats["problemas"] == [] and layout.activate(lib, stats)
    d = layout.dir_of(out, m, cfg)
    assert (d / "etapas" / "scenes.json").exists() and (d / "etapas" / "manifest.json").exists()
    assert (d / "golpes" / "rybakina-elena" / "strokes.json").exists()
    assert (d / "golpes" / "rybakina-elena" / "windows" / "w1.mp4").exists()
    assert pipeline.run(pipeline.Context(m, cfg, d, log=lambda *_: None)) == []          # nothing again
    assert calls == ["scenes", "fine"]
    assert (flat / "strokes.json").exists()                                             # the old folder stays
