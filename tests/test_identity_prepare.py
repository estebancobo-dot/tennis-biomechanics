"""09-11: preparing the identity click used «<output>/<match id>», not the match's real folder (layout.dir_of): the
cheap pass of the 4 reference matches was redone from scratch in new folders, and a click there would not reach
the analysis."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import identity_prepare as IP  # noqa: E402


def test_it_uses_the_real_match_folder_and_skips_clicked_matches(tmp_path, monkeypatch, capsys):
    out_root = tmp_path / "output"
    real = out_root / "sin-fecha_abc123_rybakina"
    real.mkdir(parents=True)
    m_done = SimpleNamespace(id="old-match", video=str(tmp_path / "v.mp4"))
    m_new = SimpleNamespace(id="new-match", video=str(tmp_path / "w.mp4"))
    seen = []
    monkeypatch.setattr(IP, "load_config", lambda: {"paths": {"output": str(out_root)}})
    monkeypatch.setattr(IP, "load_matches", lambda cfg: [m_done, m_new])
    import tennisbio.layout as layout
    monkeypatch.setattr(layout, "dir_of", lambda root, m, cfg=None: real if m.id == "old-match" else out_root / "sin-fecha_new_x")
    monkeypatch.setattr(IP.ic, "state", lambda d: {"possible": False, "done": d == real, "pick": None})
    monkeypatch.setattr(IP.ic, "photos", lambda d, v: [])
    monkeypatch.setattr(IP.pipeline, "run", lambda ctx, stages: seen.append(ctx.dir))
    monkeypatch.setattr(IP.pipeline, "Context", lambda m, cfg, d, log=None: SimpleNamespace(dir=d))
    monkeypatch.setattr(sys, "argv", ["identity_prepare", str(tmp_path / "fotos")])
    IP.main()
    assert seen == [out_root / "sin-fecha_new_x"]                       # the clicked match is not run again
    st = json.loads((tmp_path / "fotos" / "estado.json").read_text(encoding="utf-8"))
    assert st["old-match"]["clic_hecho"] and "new-match" in st
    assert not (out_root / "old-match").exists() and not (out_root / "new-match").exists()
