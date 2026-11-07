import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_catalog as A  # noqa: E402
from tennisbio.pipeline import video_sample  # noqa: E402


def test_a_renamed_video_keeps_its_match(tmp_path, monkeypatch):
    videos, out, cfgdir = tmp_path / "videos", tmp_path / "output", tmp_path / "config"
    videos.mkdir(), out.mkdir(), cfgdir.mkdir()
    v = videos / "tennis-yusipopen-final.mp4"
    v.write_bytes(b"x" * 300000)
    monkeypatch.setattr(A, "CONFIG_DIR", cfgdir)
    monkeypatch.setattr(A, "load_config", lambda: {"paths": {"videos": str(videos), "output": str(out)}})
    monkeypatch.setattr(sys, "argv", ["auto_catalog"])
    A.main()
    mid = yaml.safe_load((cfgdir / "matches.yaml").read_text(encoding="utf-8"))["matches"][0]["id"]
    (out / mid).mkdir()
    (out / mid / "video.json").write_text(json.dumps({"sample": video_sample(v)}))
    v.rename(videos / "US Open 2026 final Sabalenka Rybakina.mp4")
    A.main()
    ms = yaml.safe_load((cfgdir / "matches.yaml").read_text(encoding="utf-8"))["matches"]
    assert [(m["id"], m["video"]) for m in ms] == [(mid, "US Open 2026 final Sabalenka Rybakina.mp4")]


def test_a_new_video_names_its_player(tmp_path):
    """07-11: a match of Sinner copied next to Rybakina's is his, not the default player's."""
    (tmp_path / "players").mkdir()
    for pid, name in (("rybakina", "Elena Rybakina"), ("sabalenka", "Aryna Sabalenka"), ("sinner", "Jannik Sinner")):
        (tmp_path / "players" / f"{pid}.yaml").write_text(f"name: {name}\nhand: right\n", encoding="utf-8")
    assert A.player_of("Wimbledon 2026 final Sinner vs Alcaraz", "rybakina", tmp_path) == "sinner"
    assert A.player_of("US Open 2026 final Sabalenka Rybakina", "rybakina", tmp_path) == "rybakina"
    assert A.player_of("Roland Garros 2026 R3", "rybakina", tmp_path) == "rybakina"
    assert A.player_of("Sinner Sabalenka exhibition", "rybakina", tmp_path) == "rybakina"   # two named: the default


def test_held_videos_wait_until_the_base_is_closed(tmp_path, monkeypatch):
    videos, out, cfgdir = tmp_path / "videos", tmp_path / "output", tmp_path / "config"
    videos.mkdir(), out.mkdir(), cfgdir.mkdir()
    (videos / "old final.mp4").write_bytes(b"x")
    (videos / "Zverev Alexander - Sinner Jannik - Indian Wells - 2026 - Semi final.mkv").write_bytes(b"x")
    monkeypatch.setattr(A, "CONFIG_DIR", cfgdir)
    monkeypatch.setattr(A, "load_config", lambda: {"paths": {"videos": str(videos), "output": str(out)},
                                                   "catalog": {"hold": ["Zverev Alexander - Sinner Jannik - Indian Wells - 2026 - Semi final.mkv"]}})
    monkeypatch.setattr(sys, "argv", ["auto_catalog"])
    A.main()
    ms = yaml.safe_load((cfgdir / "matches.yaml").read_text(encoding="utf-8"))["matches"]
    assert [m["video"] for m in ms] == ["old final.mp4"]


def test_the_real_config_holds_the_users_new_videos():
    from tennisbio.config import load_config
    hold = (load_config().get("catalog") or {}).get("hold") or []
    assert any("Sinner" in h for h in hold) and any("Pegula" in h for h in hold)
