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
