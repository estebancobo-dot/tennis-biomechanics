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
