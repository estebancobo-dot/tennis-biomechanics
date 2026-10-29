import numpy as np

from tennisbio import findings as F
from tennisbio.export import fmt_t, slug, title_card, wrap, font


def _data(n=120, seed=1):
    rng = np.random.default_rng(seed)
    st = []
    for i in range(n):
        err = i % 4 == 0
        st.append({"id": f"m-{i:03d}", "frac": i / n, "set": 1 + 2 * i // n, "pressure": bool(i % 3 == 0),
                   "tAvail": 1.4, "fast": False, "sit": {"neutra": True}, "outcome": "error" if err else "sigue",
                   "outcomeDetail": "out" if err else "rally", "stance": "abierto", "quality": .8, "face": {},
                   "m": {"rFaceImp": rng.normal(4, 3) - (10 if err else 0), "xf": rng.normal(20, 3)}})
    metrics = [{"k": "rFaceImp", "g": "racket", "name": "Cara en el impacto", "unit": "°", "dec": 0, "noise": 3.0, "rel": 2},
               {"k": "xf", "g": "body", "name": "X-factor", "unit": "°", "dec": 1, "noise": 3.0, "rel": 2}]
    return {"strokes": st, "metrics": metrics, "matches": [{"id": "m", "rival": "X"}], "review": 0, "noise_validated": True}


def test_discover_finds_the_planted_difference_and_explains_it():
    data = _data()
    dist = F.distributions(data)
    F.representativeness(data, dist)
    finds = F.discover(data)
    top = finds[0]
    assert top.k == "rFaceImp" and top.title.endswith("en los errores")
    assert top.verdict[0] == "good" and top.effect.d < -7
    concl = F.conclusions(data, dist, finds)
    c = next(c for c in concl if c.finding is top)
    assert "cara más abierta" in c.text and c.strokes and all(s["outcome"] == "error" for s in c.strokes)


def test_typical_is_near_the_group_median():
    data = _data()
    errs = [s for s in data["strokes"] if s["outcome"] == "error"]
    t = F.typical(errs, "rFaceImp", 3.0)
    md = np.median([s["m"]["rFaceImp"] for s in errs])
    assert abs(t["m"]["rFaceImp"] - md) < 3.0


def test_text_helpers():
    assert fmt_t(-0.001) == "+0,00 s" and fmt_t(-0.4) == "−0,40 s"
    assert slug("Cara en el impacto: más abierta (errores)") == "cara_en_el_impacto_mas_abierta_errores"
    assert F.fmt(1234.5, 1) == "1.234,5"
    lines = wrap("una frase bastante larga para partirla en varias líneas", font("regular", 20), 150)
    assert len(lines) > 1
    img = title_card([("Título con acentos: presión", "bold", 40, (255, 255, 255))])
    assert img.shape == (720, 1280, 3) and img.mean() > 10


def test_stroke_videos_in_parallel_processes(tmp_path):
    """28-10 (B-5): the stroke videos are drawn by several processes at once; the same videos come out as with
    one process, and a broken window does not stop the others."""
    import json
    import subprocess
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("tsp", Path(__file__).with_name("test_stroke_page.py"))
    tsp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tsp)
    stroke_and_series = tsp.stroke_and_series
    from tennisbio.catalog import Match, Player
    from tennisbio.export import export
    s, ser = stroke_and_series()
    d = tmp_path / "out" / "m1"
    (d / "series").mkdir(parents=True)
    (d / "windows").mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=duration={ser['n'] / 50}:size=640x720:rate=50",
                    "-pix_fmt", "yuv420p", str(d / "windows" / "w.mp4")], check=True, timeout=120)
    (d / "series" / "x.json").write_text(json.dumps(ser), encoding="utf-8")
    rows = []
    for k in range(3):
        r = dict(s, window="w.mp4" if k < 2 else "missing.mp4", match_time_s=30.0 + 10 * k)
        rows.append(r)
    (d / "strokes.json").write_text(json.dumps(rows), encoding="utf-8")
    m = [Match("m1", None, Player("p", "P", height_m=1.84))]
    logs = []
    export(m, tmp_path / "out", tmp_path / "par", workers=2, log=logs.append)
    export(m, tmp_path / "out", tmp_path / "seq", workers=1, log=lambda *_: None)
    par = sorted(p.name for p in (tmp_path / "par" / "golpes").glob("*.mp4"))
    seq = sorted(p.name for p in (tmp_path / "seq" / "golpes").glob("*.mp4"))
    assert par == seq and len(par) == 2
    # a fine pass run again rewrites the same series (newer date, same content): nothing is encoded again
    import os
    import time as _t
    later = _t.time() + 5
    os.utime(d / "series" / "x.json", (later, later))
    again = []
    export(m, tmp_path / "out", tmp_path / "seq", workers=1, log=again.append)
    assert any("Golpes: 0 nuevos" in line for line in again), again
    (d / "series" / "x.json").write_text(json.dumps(ser) + " ", encoding="utf-8")    # changed: encoded again
    again = []
    export(m, tmp_path / "out", tmp_path / "seq", workers=1, log=again.append)
    assert any("Golpes: 2 nuevos" in line for line in again), again
