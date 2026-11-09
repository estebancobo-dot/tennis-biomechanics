"""The code fingerprint of a stage (10-11): only the code it runs counts, as syntax."""
from tennisbio import pipeline as P

SRC = '''
K = 3
J = 9

def helper(x):
    """doc"""
    return x * K

def other(x):
    return x + J

def st_a(ctx):
    # comment
    return helper(1)

def st_b(ctx):
    return other(2)
'''


def test_reachable_ignores_other_stages_comments_and_docstrings():
    a = P._reachable_src(SRC, "st_a")
    assert "other" not in a and "J" not in a
    assert P._reachable_src(SRC.replace("return other(2)", "return other(3)"), "st_a") == a      # another stage
    assert P._reachable_src(SRC.replace("# comment", "# changed"), "st_a") == a                  # a comment
    assert P._reachable_src(SRC.replace('"""doc"""', '"""new doc"""'), "st_a") == a               # a docstring
    assert P._reachable_src(SRC.replace("K = 3", "K = 4"), "st_a") != a                          # its constant
    assert P._reachable_src(SRC.replace("x * K", "x - K"), "st_a") != a                          # its helper


def test_fine_fingerprint_is_stable_and_differs_by_stage():
    from tennisbio import stages
    f = P.code_fingerprint(stages.FINE_CODE, "st_fine")
    assert f == P.code_fingerprint(stages.FINE_CODE, "st_fine")
    # the identity stage (v10 on 09-11) is not part of what the fine pass runs
    from pathlib import Path
    src = Path(stages.__file__).read_text(encoding="utf-8")
    assert "clean_games" not in P._reachable_src(src, "st_fine")
