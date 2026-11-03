"""A match whose annotations do not line up with its video is told apart by its numbers (03-11)."""
from tennisbio.validation import recall_eval as R


def _sm(gt, found, outside):
    steps = {k: 0 for k in R.STEPS}
    steps["fuera_de_camara"] = outside
    steps["encontrado"] = found
    return {"total": {"gt": gt, "found": found, "recall": found / gt}, "steps": steps,
            "precision": {"precision": 0.9}, "by_side": {"near": {"recall": 0.5}, "far": {"recall": 0.5}}}


def test_quarter_final_like_match_is_misaligned_and_normal_ones_are_not():
    assert R.misaligned(_sm(131, 1, 82))
    assert not R.misaligned(_sm(141, 133, 0))
    assert not R.misaligned(_sm(154, 116, 2))
    assert not R.misaligned(_sm(10, 0, 10))           # too few to say
    assert not R.misaligned(_sm(100, 40, 60))         # strokes are found: a real camera problem, not the annotations


def test_markdown_gives_the_headline_without_it_and_each_match():
    pm = [{"match": "A", "summary": _sm(131, 1, 82)}, {"match": "B", "summary": _sm(141, 133, 0)}]
    md = "\n".join(R._valid_lines({"summary_valid": _sm(141, 133, 0), "excluded": ["A"], "per_match": pm}))
    assert "Sin A" in md and "133 de 141" in md and "A (desfasado)" in md and "| B |" in md
