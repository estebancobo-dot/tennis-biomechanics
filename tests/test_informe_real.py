"""scripts/informe_real.py (14-11): a cloud report page rebuilt with today's template and «Aprende» content, checked in
a browser, keeps the page's data."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
CHROMIUM = Path("/opt/pw-browsers/chromium")


def _page(tmp_path):
    from test_learn_web import synthetic

    from tennisbio.catalog import Match, Player
    from tennisbio.report import build

    d = tmp_path / "m1"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps(synthetic(80, timing=True)), encoding="utf-8")
    (d / "probe.json").write_text(json.dumps({"duration": 3600}))
    return build([Match("m1", None, Player("p", "P"))], tmp_path)


def test_rebuild_keeps_the_data_and_takes_todays_content(tmp_path):
    import informe_real

    from tennisbio.learn import content

    src = _page(tmp_path)
    old = informe_real.page_data(src.read_text(encoding="utf-8"))
    old["learn"] = {"stale": True}                                   # as a page made by older code
    stale = tmp_path / "old.html"
    stale.write_text(src.read_text(encoding="utf-8").replace(informe_real.MARK + json.dumps(informe_real.page_data(src.read_text(encoding="utf-8")), ensure_ascii=False),
                                                             informe_real.MARK + json.dumps(old, ensure_ascii=False)), encoding="utf-8")
    assert informe_real.page_data(stale.read_text(encoding="utf-8"))["learn"] == {"stale": True}
    out = informe_real.rebuild(stale, tmp_path / "new" / "index.html")
    new = informe_real.page_data(out.read_text(encoding="utf-8"))
    assert new["learn"] == json.loads(json.dumps(content(), ensure_ascii=False))
    assert {k: v for k, v in new.items() if k != "learn"} == {k: v for k, v in old.items() if k != "learn"}


@pytest.mark.skipif(not CHROMIUM.exists(), reason="sin navegador para la prueba de la web")
def test_check_runs_the_audit_checks(tmp_path):
    import informe_real

    out = informe_real.rebuild(_page(tmp_path), tmp_path / "new" / "index.html")
    r = informe_real.check(out, str(CHROMIUM))
    assert not r["errors"] and len(r["lesson"]["phases"]) == 9
    assert all("key_words" in row for row in r["lesson"]["phases"])
    assert r["entry"]["entry"]["vid_bottom"] <= 900 and not r["entry"]["failures"]
