"""The one registry of matches (10-11, phase A): config/matches.yaml and the folders are sources; every entry point
reads the registry (the application's database)."""
import json

from tennisbio import registry
from tennisbio.catalog import load_matches


def _env(tmp_path):
    cfgd = tmp_path / "config"
    (cfgd / "players").mkdir(parents=True)
    (cfgd / "players" / "ryb.yaml").write_text("name: Elena Rybakina\nhand: right\nheight_m: 1.84\n", encoding="utf-8")
    (cfgd / "matches.yaml").write_text("matches:\n  - id: m1\n    video: m1.mp4\n    player: ryb\n    opponent: X\n"
                                       "  - id: m2\n    video: m2.mp4\n    player: ryb\n", encoding="utf-8")
    vids = tmp_path / "videos"
    vids.mkdir()
    out = tmp_path / "output"
    (out / "m1").mkdir(parents=True)
    (out / "m1" / "manifest.json").write_text("{}", encoding="utf-8")
    cfg = {"paths": {"output": str(out), "videos": str(vids), "data": str(tmp_path / "datos")}}
    return cfg, cfgd, out


def test_without_the_database_the_catalogue_as_it_is(tmp_path):
    cfg, cfgd, out = _env(tmp_path)
    ms = load_matches(cfg, cfgd)
    assert [m.id for m in ms] == ["m1", "m2"] and all("match_dir" not in m.extra for m in ms)


def test_sync_then_every_entry_point_reads_the_registry(tmp_path):
    cfg, cfgd, out = _env(tmp_path)
    assert registry.sync(cfg, cfgd)["matches"] == 2
    ms = {m.id: m for m in load_matches(cfg, cfgd)}
    assert set(ms) == {"m1", "m2"}
    assert ms["m1"].extra["match_dir"] == str(out / "m1") and ms["m1"].opponent == "X"     # its folder, its metadata
    db = registry.open_db(cfg)
    db.x("UPDATE matches SET state='archivado' WHERE id='m2'")
    v = tmp_path / "videos" / "m3.mp4"
    v.write_bytes(b"x")
    db.x("INSERT INTO videos (sample, size, path) VALUES ('s3', 1, ?)", str(v))
    db.x("INSERT INTO matches (id, video, player, state) VALUES ('m3', 's3', 'ryb', 'nuevo')")     # added in the app
    db.x("INSERT INTO matches (id, video, player, state) VALUES ('smoke:m1', 's3', 'ryb', 'nuevo')")  # a test run
    db.close()
    assert [m.id for m in load_matches(cfg, cfgd)] == ["m1", "m3"]


def test_yaml_source_keeps_the_catalogue_alone(tmp_path):
    cfg, cfgd, out = _env(tmp_path)
    registry.sync(cfg, cfgd)
    cfg["registry"] = {"source": "yaml"}
    assert all("match_dir" not in m.extra for m in load_matches(cfg, cfgd))


def test_cli_registry_list_writes_json(tmp_path, monkeypatch):
    cfg, cfgd, out = _env(tmp_path)
    from tennisbio import cli
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "load_matches", lambda c: load_matches(c, cfgd))
    f = tmp_path / "reg.json"
    assert cli.main(["registry", "list", "--json", str(f)]) == 0
    assert [r["id"] for r in json.loads(f.read_text(encoding="utf-8"))] == ["m1", "m2"]
